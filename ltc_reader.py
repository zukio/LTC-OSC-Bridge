import argparse
import array
import json
import logging
import signal
import threading
import time
import asyncio
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

_ipc_loop = None
_ipc_server_task = None
_tray_icon = None


def _open_settings_window(config_path: str) -> None:
    """Open a small Tkinter window to edit configuration."""
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
    current_name = idx_to_name.get(cfg.get("audio_device_index"),
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

    def on_save():
        new_cfg = {
            "osc_ip": ip_var.get(),
            "osc_port": int(port_var.get()),
            "osc_address": addr_var.get(),
            "audio_device_index": name_to_idx.get(device_var.get(), 0),
            "channel": int(channel_var.get()),
            "sample_rate": int(sr_var.get()),
            "fps": float(fps_var.get().replace("ndf", "")),
        }
        try:
            with open(config_path, "w", encoding="utf-8") as fh:
                json.dump(new_cfg, fh, indent=2)
            messagebox.showinfo("LTC OSC", "設定を保存しました")
            win.destroy()
        except Exception as exc:  # noqa: W0703
            messagebox.showerror("Error", str(exc))

    tk.Button(win, text="更新", command=on_save).grid(row=7, column=0,
                                                  columnspan=2, pady=5)

    win.mainloop()


def _create_image():
    """Create tray icon image."""
    image = Image.new("RGB", (64, 64), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((8, 8, 56, 56), fill=(0, 128, 255))
    return image


def _setup_tray(settings, exit_cb, config_path, device_name=None):
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
    )

    icon.menu = pystray.Menu(
        pystray.MenuItem("設定", settings_menu),
        pystray.MenuItem(
            "設定変更...",
            lambda: threading.Thread(
                target=_open_settings_window, args=(config_path,), daemon=True
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
        self.address = address

    def send(self, message: str):
        for attempt in range(3):
            try:
                self.client.send_message(self.address, message)
                return
            except Exception as exc:
                logging.warning("OSC send failed (%d/3): %s", attempt + 1, exc)
                time.sleep(0.1)
        # give up silently


class LTCReader:
    def __init__(self, config: dict):
        self.sample_rate = int(config.get("sample_rate", 48000))
        self.device_index = config.get("audio_device_index")
        self.channel = int(config.get("channel", 0))
        self.chunk_size = 512
        self.pa = pyaudio.PyAudio()
        if self.device_index is None:
            logging.error("Audio device index not specified")
            raise SystemExit(1)
        info = self.pa.get_device_info_by_index(self.device_index)
        self.device_name = get_device_name(self.device_index) or info.get("name")
        self.num_channels = int(info.get("maxInputChannels", 1))
        logging.info(
            "Input device: '%s' (index: %d)",
            self.device_name,
            self.device_index,
        )
        self.stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=self.num_channels,
            rate=self.sample_rate,
            input=True,
            input_device_index=self.device_index,
            frames_per_buffer=self.chunk_size,
        )
        self.fps = float(config.get("fps", 30))
        self.decoder = LibLTC(find_libltc(), self.sample_rate, self.fps)
        self.osc = OSCClient(
            config.get("osc_ip", "127.0.0.1"),
            int(config.get("osc_port", 9000)),
            config.get("osc_address", "/ltc"),
        )
        self.running = True
        signal.signal(signal.SIGINT, self._on_sigint)

    def _on_sigint(self, *_):
        self.running = False

    def loop(self):
        logging.info("Starting LTC decode loop...")
        while self.running:
            data = self.stream.read(
                self.chunk_size, exception_on_overflow=False)
            samples = array.array('h', data)
            if self.num_channels > 1:
                samples = samples[self.channel::self.num_channels]
            self.decoder.write(samples)
            # print("Samples:", samples[:10])
            # print("Samples len:", len(samples))
            for stime in self.decoder.read():
                tc = f"{stime.hours:02d}:{stime.mins:02d}:{stime.secs:02d}:{stime.frame:02d}"
                logging.debug("Decoded %s", tc)
                # print("Decoded %s", tc)
                self.osc.send(tc)
        self.close()

    def close(self):
        self.stream.stop_stream()
        self.stream.close()
        self.pa.terminate()
        self.decoder.close()


def load_config(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def main() -> None:
    parser = argparse.ArgumentParser(description="LTC to OSC bridge")
    parser.add_argument("--config", required=True, help="path to config.json")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    config = load_config(args.config)

    # check existing instance
    if check_existing_instance(INSTANCE_PORT, INSTANCE_KEY):
        print("既に起動しています。")
        return

    server_thread = threading.Thread(target=_run_ipc_server, daemon=True)
    server_thread.start()

    reader = LTCReader(config)

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

    signal.signal(
        signal.SIGINT, lambda sig, frame: exit_handler("[Exit] Signal Interrupt")
    )

    global _tray_icon
    _tray_icon = _setup_tray(config, exit_handler, args.config, reader.device_name)

    try:
        reader.loop()
    finally:
        exit_handler("[Exit] Normal")


if __name__ == "__main__":
    main()
