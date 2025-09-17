import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import argparse
import array
import json
import logging
import signal
import threading
import time
import asyncio
import os
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except Exception:  # noqa: W0703
    tk = None

import pyaudio
from pythonosc import udp_client

try:
    from PIL import Image, ImageDraw
    import pystray
except Exception:  # noqa: W0703
    pystray = None

from modules.communication.ipc_client import check_existing_instance
from modules.communication.ipc_server import start_server
from modules.audio_devices import get_device_name, list_input_devices
from modules.ltc import LibLTC, find_libltc

INSTANCE_PORT = 12321
INSTANCE_KEY = "LTCOSCReader"

# Default configuration used when no config file is found.
DEFAULT_CONFIG = {
    "osc_ip": "127.0.0.1",
    "osc_port": 9000,
    "osc_address": "/ltc",
    "audio_device_index": None,
    "channel": 0,
    "sample_rate": 48000,
    "fps": 30,
    "timecode_offset": 0.0,
    "stop_timeout": 0.5,
    "pause_detection_time": 0.2,
}

_ipc_loop = None
_ipc_server_task = None
_tray_icon = None
_restart_event = threading.Event()


def _open_settings_window(config_path: str, restart_cb, current_device_index=None) -> None:
    """Open a small Tkinter window to edit configuration.

    ``restart_cb`` will be called after saving to trigger a restart.
    ``current_device_index`` is the actually used device index (may differ from config due to fallback).
    """
    if tk is None:
        logging.error("tkinter is not available")
        return

    cfg = load_config(config_path)

    devices = list_input_devices()
    device_names = [name for _, name in devices]
    idx_to_name = {idx: name for idx, name in devices}
    name_to_idx = {name: idx for idx, name in devices}

    win = tk.Tk()
    win.title("LTC OSC Settings")

    # OSC IP
    tk.Label(win, text="OSC IP").grid(row=0, column=0, sticky="w")
    ip_var = tk.StringVar(value=cfg.get("osc_ip", "127.0.0.1"))
    tk.Entry(win, textvariable=ip_var).grid(row=0, column=1, pady=2, padx=5)

    # OSC Port
    tk.Label(win, text="OSC Port").grid(row=1, column=0, sticky="w")
    port_var = tk.StringVar(value=str(cfg.get("osc_port", 9000)))
    tk.Entry(win, textvariable=port_var).grid(row=1, column=1, pady=2, padx=5)

    # OSC Address
    tk.Label(win, text="OSC Address").grid(row=2, column=0, sticky="w")
    addr_var = tk.StringVar(value=cfg.get("osc_address", "/ltc"))
    tk.Entry(win, textvariable=addr_var).grid(row=2, column=1, pady=2, padx=5)

    # Audio device
    tk.Label(win, text="Audio Device").grid(row=3, column=0, sticky="w")
    # Use actual device index if provided, otherwise use config value
    actual_device_index = current_device_index if current_device_index is not None else cfg.get(
        "audio_device_index")
    current_name = idx_to_name.get(actual_device_index,
                                   device_names[0] if device_names else "")
    device_var = tk.StringVar(value=current_name)
    ttk.Combobox(win, textvariable=device_var, values=device_names,
                 state="readonly").grid(row=3, column=1, pady=2, padx=5)

    # Channel
    tk.Label(win, text="Channel").grid(row=4, column=0, sticky="w")
    channel_var = tk.StringVar(value=str(cfg.get("channel", 0)))
    ttk.Combobox(win, textvariable=channel_var, values=["0", "1"],
                 state="readonly").grid(row=4, column=1, pady=2, padx=5)

    # Sample rate
    tk.Label(win, text="Sample Rate").grid(row=5, column=0, sticky="w")
    sr_var = tk.StringVar(value=str(cfg.get("sample_rate", 48000)))
    ttk.Combobox(win, textvariable=sr_var, values=["44100", "48000"],
                 state="readonly").grid(row=5, column=1, pady=2, padx=5)

    # FPS
    tk.Label(win, text="FPS").grid(row=6, column=0, sticky="w")
    fps_display = ["24", "25", "23.976", "29.97ndf", "30", "59.97", "60"]
    fps_var = tk.StringVar(value=str(cfg.get("fps", 30)))
    ttk.Combobox(win, textvariable=fps_var, values=fps_display,
                 state="readonly").grid(row=6, column=1, pady=2, padx=5)

    # Timecode Offset
    tk.Label(win, text="Timecode Offset (秒.フレーム)").grid(
        row=7, column=0, sticky="w")
    offset_var = tk.StringVar(value=str(cfg.get("timecode_offset", 0.0)))
    offset_entry = tk.Entry(win, textvariable=offset_var)
    offset_entry.grid(row=7, column=1, pady=2, padx=5)

    # Add validation for offset entry
    def validate_offset(value):
        try:
            float(value)
            return True
        except ValueError:
            return value == "" or value == "-"

    vcmd = (win.register(validate_offset), '%P')
    offset_entry.config(validate='key', validatecommand=vcmd)

    # Stop Timeout
    tk.Label(win, text="Stop Timeout (秒)").grid(row=8, column=0, sticky="w")
    timeout_var = tk.StringVar(value=str(cfg.get("stop_timeout", 0.5)))
    timeout_entry = tk.Entry(win, textvariable=timeout_var)
    timeout_entry.grid(row=8, column=1, pady=2, padx=5)

    # Add validation for timeout entry
    def validate_timeout(value):
        try:
            val = float(value)
            return val > 0  # Must be positive
        except ValueError:
            return value == ""

    vcmd_timeout = (win.register(validate_timeout), '%P')
    timeout_entry.config(validate='key', validatecommand=vcmd_timeout)

    def on_save():
        try:
            offset_value = float(offset_var.get()) if offset_var.get() else 0.0
        except ValueError:
            messagebox.showerror("Error", "オフセット値は数値で入力してください")
            return

        try:
            timeout_value = float(
                timeout_var.get()) if timeout_var.get() else 0.5
            if timeout_value <= 0:
                raise ValueError("Timeout must be positive")
        except ValueError:
            messagebox.showerror("Error", "Stop Timeout は正の数値で入力してください")
            return

        new_cfg = {
            "osc_ip": ip_var.get(),
            "osc_port": int(port_var.get()),
            "osc_address": addr_var.get(),
            "audio_device_index": name_to_idx.get(device_var.get(), 0),
            "channel": int(channel_var.get()),
            "sample_rate": int(sr_var.get()),
            "fps": float(fps_var.get().replace("ndf", "")),
            "timecode_offset": offset_value,
            "stop_timeout": timeout_value,
        }
        try:
            with open(config_path, "w", encoding="utf-8") as fh:
                json.dump(new_cfg, fh, indent=2)
            messagebox.showinfo("LTC OSC", "設定を保存しました")
            win.destroy()
            restart_cb()
        except Exception as exc:  # noqa: W0703
            messagebox.showerror("Error", str(exc))

    tk.Button(win, text="更新", command=on_save).grid(row=9, column=0,
                                                    columnspan=2, pady=5)

    win.mainloop()


def _create_image():
    """Create tray icon image."""
    image = Image.new("RGB", (64, 64), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((8, 8, 56, 56), fill=(0, 128, 255))
    return image


def _setup_tray(settings, exit_cb, config_path, restart_cb, device_name=None, reader=None):
    """Start system tray icon."""
    if pystray is None:
        return None

    icon = pystray.Icon("ltc_reader", _create_image(), "LTC Reader")

    settings_menu = pystray.Menu(
        pystray.MenuItem(
            f"OSC {settings['osc_ip']}:{settings['osc_port']}",
            None,
            enabled=False,
        ),
        pystray.MenuItem(
            f"Address {settings['osc_address']}",
            None,
            enabled=False,
        ),
        pystray.MenuItem(
            f"Device {device_name or settings['audio_device_index']}",
            None,
            enabled=False,
        ),
        pystray.MenuItem(
            f"Channel {settings['channel']}",
            None,
            enabled=False,
        ),
        pystray.MenuItem(
            f"Rate {settings['sample_rate']}Hz",
            None,
            enabled=False,
        ),
        pystray.MenuItem(
            f"FPS {settings.get('fps', 30)}",
            None,
            enabled=False,
        ),
        pystray.MenuItem(
            f"Offset {settings.get('timecode_offset', 0.0):.2f}s",
            None,
            enabled=False,
        ),
    )

    icon.menu = pystray.Menu(
        pystray.MenuItem("設定", settings_menu),
        pystray.MenuItem(
            "設定変更...",
            lambda _icon, _item: threading.Thread(
                target=_open_settings_window,
                args=(config_path, restart_cb,
                      reader.device_index if reader else None),
                daemon=True,
            ).start(),
        ),
        pystray.MenuItem("Exit", lambda: exit_cb("[Exit] Tray")),
    )

    threading.Thread(target=icon.run, daemon=True).start()

    return icon


def _run_ipc_server():
    """Run IPC server in a dedicated event loop."""
    global _ipc_loop, _ipc_server_task
    _ipc_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_ipc_loop)
    _ipc_server_task = _ipc_loop.create_task(
        start_server(INSTANCE_PORT, INSTANCE_KEY)
    )
    try:
        _ipc_loop.run_forever()
    finally:
        if _ipc_server_task:
            _ipc_server_task.cancel()
            try:
                _ipc_loop.run_until_complete(_ipc_server_task)
            except Exception:
                pass
        _ipc_loop.close()


class OSCClient:
    def __init__(self, ip: str, port: int, address: str):
        self.client = udp_client.SimpleUDPClient(ip, port)
        self.base_address = address
        self.decode_address = address + "/decode"  # Timecode decode results
        self.status_running_address = address + "/status-running"  # Running status
        self.status_paused_address = address + "/status-paused"  # Paused status
        self.status_stopped_address = address + "/status-stopped"  # Stopped status
        self.status_reset_address = address + "/status-reset"  # Reset status

    def send(self, message: str):
        """Send timecode message to /ltc/decode address."""
        for attempt in range(3):
            try:
                self.client.send_message(self.decode_address, message)
                return
            except Exception as exc:
                logging.warning(
                    "OSC decode send failed (%d/3): %s", attempt + 1, exc)
                time.sleep(0.1)
        # give up silently

    def send_status(self, status: str, timecode: str = None):
        """Send timecode status to appropriate status address."""
        if status == "running":
            address = self.status_running_address
        elif status == "paused":
            address = self.status_paused_address
        elif status == "stopped":
            address = self.status_stopped_address
        elif status == "reset":
            address = self.status_reset_address
        else:
            logging.warning(f"Unknown status: {status}")
            return

        message = timecode if timecode else status

        for attempt in range(3):
            try:
                self.client.send_message(address, message)
                return
            except Exception as exc:
                logging.warning(
                    "OSC status send failed (%d/3): %s", attempt + 1, exc)
                time.sleep(0.1)
        # give up silently

    def send_reset(self, timecode: str = "00:00:00:00"):
        """Send reset status message."""
        self.send_status("reset", timecode)


class TimecodeStatusMonitor:
    """Monitor timecode start/stop/pause status."""

    def __init__(self, timeout=2.0, pause_detection_time=0.2):
        self.timeout = timeout
        self.pause_detection_time = pause_detection_time  # Time to detect pause
        self.status = "stopped"  # "stopped", "running", "paused"
        self.last_timecode = None
        self.last_received_time = None
        self.last_change_time = None  # Time when timecode last changed

    def update_timecode(self, timecode):
        """Update with new timecode and check for status changes."""
        current_time = time.time()
        status_changed = False
        reset_detected = False
        old_status = self.status

        # Always update when we receive any timecode
        self.last_received_time = current_time

        # Check for reset condition (00:00:00:00)
        if timecode == "00:00:00:00":
            reset_detected = True

        # Check if timecode value has changed
        if self.last_timecode != timecode:
            self.last_change_time = current_time

            # If we were stopped or paused and now timecode is changing, we're running
            if self.status in ["stopped", "paused"]:
                self.status = "running"
                status_changed = True
                logging.info(f"Timecode STARTED (from {old_status})")
        else:
            # Same timecode value - check if we should transition to paused
            if self.status == "running" and self.last_change_time:
                time_since_change = current_time - self.last_change_time
                if time_since_change > self.pause_detection_time:
                    self.status = "paused"
                    status_changed = True
                    logging.info("Timecode PAUSED")

        self.last_timecode = timecode
        return status_changed, old_status, reset_detected

    def check_timeout(self):
        """Check if timecode has timed out and update status accordingly."""
        if not self.last_received_time:
            return False, None

        current_time = time.time()
        status_changed = False
        old_status = self.status

        # Check for timeout (indicating stop)
        if self.status in ["running", "paused"] and (current_time - self.last_received_time) > self.timeout:
            self.status = "stopped"
            status_changed = True
            logging.info("Timecode STOPPED")

        return status_changed, old_status

    def get_status(self):
        """Get current status."""
        return {
            "status": self.status,
            "last_timecode": self.last_timecode,
            "last_received_time": self.last_received_time,
            "last_change_time": self.last_change_time
        }


class LTCReader:
    def __init__(self, config: dict, config_path: str = "config.json"):
        self.config_path = config_path
        self.sample_rate = int(config.get("sample_rate", 48000))
        self.device_index = config.get("audio_device_index")
        self.channel = int(config.get("channel", 0))
        self.chunk_size = 512
        self.pa = pyaudio.PyAudio()

        # audio_device_index の検証とフォールバック
        if self.device_index is None:
            # デフォルトデバイスを探す
            self.device_index = self._find_default_input_device()
            if self.device_index is None:
                logging.error("No audio input device available")
                raise SystemExit(1)
            logging.warning(
                "Audio device index not specified, using default device: %d", self.device_index)

        # デバイスの有効性を確認
        try:
            info = self.pa.get_device_info_by_index(self.device_index)
            if info.get("maxInputChannels", 0) <= 0:
                raise ValueError("Selected device has no input channels")
        except Exception as e:
            logging.error("Invalid audio device index %d: %s",
                          self.device_index, e)
            # フォールバックデバイスを探す
            fallback_index = self._find_default_input_device()
            if fallback_index is not None:
                logging.warning(
                    "Falling back to default device: %d", fallback_index)
                self.device_index = fallback_index
                info = self.pa.get_device_info_by_index(self.device_index)
            else:
                logging.error("No fallback device available")
                raise SystemExit(1)

        device_name = get_device_name(
            self.device_index) or info.get("name")
        # デバイス名の文字化け対策
        try:
            self.device_name = device_name.encode(
                'cp932').decode('utf-8', errors='ignore')
        except (UnicodeEncodeError, UnicodeDecodeError, AttributeError):
            self.device_name = f"Device {self.device_index}"
        self.num_channels = int(info.get("maxInputChannels", 1))
        logging.info(
            "Input device: '%s' (index: %d)",
            self.device_name,
            self.device_index,
        )

        # Try to open audio stream with error handling
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                self.stream = self.pa.open(
                    format=pyaudio.paInt16,
                    channels=self.num_channels,
                    rate=self.sample_rate,
                    input=True,
                    input_device_index=self.device_index,
                    frames_per_buffer=self.chunk_size,
                )
                break  # Success, exit retry loop
            except OSError as e:
                logging.warning(
                    f"Failed to open audio stream (attempt {attempt + 1}/{max_attempts}): {e}")

                if attempt == max_attempts - 1:  # Last attempt
                    # Try to find any available input device
                    logging.error(
                        "All attempts failed, searching for any available input device...")
                    available_devices = list_input_devices()

                    for alt_index, alt_name in available_devices:
                        if alt_index != self.device_index:  # Skip the failing device
                            try:
                                logging.info(
                                    f"Trying alternative device: '{alt_name}' (index: {alt_index})")
                                alt_info = self.pa.get_device_info_by_index(
                                    alt_index)

                                self.stream = self.pa.open(
                                    format=pyaudio.paInt16,
                                    channels=min(self.num_channels, int(
                                        alt_info.get("maxInputChannels", 1))),
                                    rate=self.sample_rate,
                                    input=True,
                                    input_device_index=alt_index,
                                    frames_per_buffer=self.chunk_size,
                                )

                                # Update device info if successful
                                self.device_index = alt_index
                                self.device_name = alt_name
                                self.num_channels = int(
                                    alt_info.get("maxInputChannels", 1))

                                # Update config file with new device index
                                config["audio_device_index"] = alt_index
                                self._save_config(config, self.config_path)

                                logging.info(
                                    f"Successfully using alternative device: '{alt_name}' (index: {alt_index})")
                                logging.info(
                                    f"Config updated with new device index: {alt_index}")
                                break

                            except OSError as alt_e:
                                logging.warning(
                                    f"Alternative device {alt_index} also failed: {alt_e}")
                                continue
                    else:
                        # No working device found
                        logging.error("No working audio input device found")
                        raise SystemExit(1)
                    break
        self.fps = float(config.get("fps", 30))
        self.timecode_offset = float(config.get("timecode_offset", 0.0))

        # Validate and adjust timecode_offset if necessary
        self.timecode_offset = self._validate_and_adjust_offset(
            self.timecode_offset, self.fps)

        self.decoder = LibLTC(find_libltc(), self.sample_rate, self.fps)
        self.osc = OSCClient(
            config.get("osc_ip", "127.0.0.1"),
            int(config.get("osc_port", 9000)),
            config.get("osc_address", "/ltc"),
        )

        # Initialize timecode status monitor
        stop_timeout = float(config.get("stop_timeout", 0.5))
        pause_detection_time = float(config.get("pause_detection_time", 0.2))
        self.status_monitor = TimecodeStatusMonitor(
            timeout=stop_timeout,
            pause_detection_time=pause_detection_time
        )

        # Log offset information for user reference
        if self.timecode_offset != 0:
            offset_frames = round(self.timecode_offset * self.fps)
            logging.info(
                f"Timecode offset: {self.timecode_offset:.3f}s = {offset_frames} frames @ {self.fps}fps")

        self.running = True
        signal.signal(signal.SIGINT, self._on_sigint)

    def _validate_and_adjust_offset(self, offset, fps):
        """Validate and adjust timecode offset to ensure frame count is within valid range."""
        offset_seconds = int(offset)
        offset_frames_decimal = offset - offset_seconds

        # Convert decimal part to frame count (e.g., 0.05 -> 5 frames)
        offset_frames = int(round(abs(offset_frames_decimal) * 100))

        # Check if frame count exceeds fps limit
        # For 29.97fps, valid frames are 0-29, so max_frames = 29
        max_frames = int(fps) if fps == int(fps) else int(fps) - 1
        if fps == 29.97:
            max_frames = 29
        elif fps == 23.976:
            max_frames = 23
        elif fps == 59.97:
            max_frames = 59
        else:
            max_frames = int(fps) - 1

        if offset_frames > max_frames:
            # Adjust: convert excess frames to seconds
            excess_frames = offset_frames - max_frames
            additional_seconds = excess_frames // (max_frames + 1)
            remaining_frames = excess_frames % (max_frames + 1)

            # Apply sign correction
            sign = 1 if offset_frames_decimal >= 0 else -1
            adjusted_seconds = offset_seconds + (additional_seconds * sign)
            adjusted_frames = remaining_frames if offset_frames_decimal >= 0 else -remaining_frames

            adjusted_offset = adjusted_seconds + (adjusted_frames / 100.0)

            logging.warning(
                f"Timecode offset adjusted: {offset:.3f} -> {adjusted_offset:.3f} "
                f"(frames {offset_frames} -> {remaining_frames} @ {fps}fps)"
            )
            return adjusted_offset

        return offset

    def _find_default_input_device(self) -> int | None:
        """利用可能な入力デバイスの中から最初のものを返す"""
        devices = list_input_devices()
        return devices[0][0] if devices else None

    def _on_sigint(self, *_):
        self.running = False

    def _apply_timecode_offset(self, hours, minutes, seconds, frames):
        """Apply offset to timecode and handle wraparound."""
        # Convert timecode to total frames for precise calculation
        total_frames = hours * 3600 * self.fps + minutes * \
            60 * self.fps + seconds * self.fps + frames

        # Parse offset in decimal format (e.g., 1.05 = 1 second + 5 frames)
        offset_seconds = int(self.timecode_offset)
        offset_frames_decimal = self.timecode_offset - offset_seconds

        # Convert decimal part to frame count, handling negative values properly
        if offset_frames_decimal >= 0:
            offset_frames = int(round(offset_frames_decimal * 100))
        else:
            offset_frames = -int(round(abs(offset_frames_decimal) * 100))

        # Calculate total offset frames and apply
        total_offset_frames = offset_seconds * self.fps + offset_frames
        total_frames += total_offset_frames

        # Handle negative values (wrap to previous day)
        frames_per_day = 24 * 3600 * self.fps
        if total_frames < 0:
            total_frames += frames_per_day

        # Handle values >= 24 hours (wrap to next day)
        total_frames = total_frames % frames_per_day

        # Convert back to timecode components
        new_hours = int(total_frames // (3600 * self.fps))
        remaining_frames = total_frames % (3600 * self.fps)

        new_minutes = int(remaining_frames // (60 * self.fps))
        remaining_frames = remaining_frames % (60 * self.fps)

        new_seconds = int(remaining_frames // self.fps)
        new_frames = int(remaining_frames % self.fps)

        return new_hours, new_minutes, new_seconds, new_frames

    def loop(self):
        logging.info("Starting LTC decode loop...")

        # Send initial status message (stopped state)
        logging.info("Sending initial status: stopped")
        self.osc.send_status("stopped")

        last_timeout_check = time.time()

        while self.running:
            data = self.stream.read(
                self.chunk_size, exception_on_overflow=False)
            samples = array.array('h', data)
            if self.num_channels > 1:
                samples = samples[self.channel::self.num_channels]
            self.decoder.write(samples)

            timecode_found = False

            # Process all available timecodes
            for stime in self.decoder.read():
                timecode_found = True
                # Apply timecode offset
                hours, minutes, seconds, frames = self._apply_timecode_offset(
                    stime.hours, stime.mins, stime.secs, stime.frame
                )
                tc = f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"

                # Monitor status changes
                status_changed, old_status, reset_detected = self.status_monitor.update_timecode(
                    tc)

                # Send reset message if detected
                if reset_detected:
                    logging.info(f"Sending reset status: timecode: {tc}")
                    self.osc.send_reset(tc)

                # Send status change if needed
                if status_changed:
                    # Send status with timecode via OSC
                    current_status = self.status_monitor.status
                    logging.info(
                        f"Sending status: {current_status}, timecode: {tc}")
                    self.osc.send_status(current_status, tc)

                logging.debug("Decoded %s (offset applied)", tc)
                # Send timecode only
                self.osc.send(tc)

            # Always check for timeout periodically
            current_time = time.time()
            # Check every 100ms
            if (current_time - last_timeout_check) > 0.1:
                timeout_status_changed, old_status = self.status_monitor.check_timeout()
                if timeout_status_changed:
                    current_status = self.status_monitor.status
                    logging.info(f"Sending timeout status: {current_status}")
                    self.osc.send_status(
                        current_status, self.status_monitor.last_timecode)
                last_timeout_check = current_time

        self.close()

    def close(self):
        self.stream.stop_stream()
        self.stream.close()
        self.pa.terminate()
        self.decoder.close()

    def _save_config(self, config: dict, config_path: str = "config.json") -> None:
        """Save configuration to JSON file."""
        try:
            with open(config_path, "w", encoding="utf-8") as fh:
                json.dump(config, fh, indent=2, ensure_ascii=False)
            logging.info(f"Config saved to {config_path}")
        except Exception as e:
            logging.error(f"Failed to save config: {e}")


def load_config(path: str) -> dict:
    """Load configuration from JSON file or return defaults if missing."""
    if not os.path.isfile(path):
        logging.info("Config file '%s' not found, using defaults", path)
        return DEFAULT_CONFIG.copy()
    with open(path, "r", encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as exc:
            logging.error("Failed to parse config file: %s", exc)
            return DEFAULT_CONFIG.copy()
    # Merge defaults for missing values
    cfg = DEFAULT_CONFIG.copy()
    cfg.update(data)
    return cfg


def _run_once(config_path: str) -> None:
    config = load_config(config_path)

    server_thread = threading.Thread(target=_run_ipc_server, daemon=True)
    server_thread.start()

    reader = LTCReader(config, config_path)

    def exit_handler(reason: str):
        global _tray_icon
        logging.info("Shutting down: %s", reason)
        reader.running = False
        if _tray_icon:
            _tray_icon.stop()
            _tray_icon = None
        if _ipc_loop:
            def _cancel_server():
                if _ipc_server_task:
                    _ipc_server_task.cancel()
            _ipc_loop.call_soon_threadsafe(_cancel_server)
            _ipc_loop.call_soon_threadsafe(_ipc_loop.stop)
        server_thread.join(timeout=1)

    def restart_cb() -> None:
        _restart_event.set()
        reader.running = False

    signal.signal(
        signal.SIGINT, lambda sig, frame: exit_handler(
            "[Exit] Signal Interrupt")
    )

    global _tray_icon
    _tray_icon = _setup_tray(
        config, exit_handler, config_path, restart_cb, reader.device_name, reader
    )

    try:
        reader.loop()
    finally:
        exit_handler("[Exit] Normal")


def main() -> None:
    parser = argparse.ArgumentParser(description="LTC to OSC bridge")
    parser.add_argument(
        "--config",
        default="config.json",
        help="path to config.json (optional)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="[%(levelname)s] %(message)s")

    if check_existing_instance(INSTANCE_PORT, INSTANCE_KEY):
        print("既に起動しています。")
        return

    while True:
        _run_once(args.config)
        if not _restart_event.is_set():
            break
        _restart_event.clear()


if __name__ == "__main__":
    main()
