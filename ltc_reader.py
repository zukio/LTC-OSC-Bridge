import argparse
import array
import ctypes
import json
import logging
import os
import platform
import signal
import time

import pyaudio
from pythonosc import udp_client

LTC_FRAME_BIT_COUNT = 80

class LTCFrame(ctypes.Structure):
    _fields_ = [("data", ctypes.c_uint8 * 10)]

class LTCFrameExt(ctypes.Structure):
    _fields_ = [
        ("ltc", LTCFrame),
        ("off_start", ctypes.c_longlong),
        ("off_end", ctypes.c_longlong),
        ("reverse", ctypes.c_int),
        ("biphase_tics", ctypes.c_float * LTC_FRAME_BIT_COUNT),
        ("sample_min", ctypes.c_uint8),
        ("sample_max", ctypes.c_uint8),
        ("volume", ctypes.c_double),
    ]

class SMPTETimecode(ctypes.Structure):
    _fields_ = [
        ("timezone", ctypes.c_char * 6),
        ("years", ctypes.c_uint8),
        ("months", ctypes.c_uint8),
        ("days", ctypes.c_uint8),
        ("hours", ctypes.c_uint8),
        ("mins", ctypes.c_uint8),
        ("secs", ctypes.c_uint8),
        ("frame", ctypes.c_uint8),
    ]

class LibLTC:
    """Minimal wrapper for libltc decoder."""
    def __init__(self, lib_path: str, sample_rate: int, fps: float):
        self.lib = ctypes.cdll.LoadLibrary(lib_path)
        self.lib.ltc_decoder_create.argtypes = [ctypes.c_int, ctypes.c_int]
        self.lib.ltc_decoder_create.restype = ctypes.c_void_p
        self.lib.ltc_decoder_free.argtypes = [ctypes.c_void_p]
        self.lib.ltc_decoder_free.restype = ctypes.c_int
        self.lib.ltc_decoder_write_s16.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_short),
            ctypes.c_size_t,
            ctypes.c_longlong,
        ]
        self.lib.ltc_decoder_write_s16.restype = None
        self.lib.ltc_decoder_read.argtypes = [ctypes.c_void_p, ctypes.POINTER(LTCFrameExt)]
        self.lib.ltc_decoder_read.restype = ctypes.c_int
        self.lib.ltc_frame_to_time.argtypes = [ctypes.POINTER(SMPTETimecode), ctypes.POINTER(LTCFrame), ctypes.c_int]
        self.lib.ltc_frame_to_time.restype = None
        apv = int(sample_rate / fps)
        self.decoder = self.lib.ltc_decoder_create(apv, 10)
        self.posinfo = 0
    def write(self, samples):
        if not samples:
            return
        arr_type = ctypes.c_short * len(samples)
        c_samples = arr_type(*samples)
        self.lib.ltc_decoder_write_s16(self.decoder, c_samples, len(samples), self.posinfo)
        self.posinfo += len(samples)
    def read(self):
        frame = LTCFrameExt()
        while self.lib.ltc_decoder_read(self.decoder, ctypes.byref(frame)):
            stime = SMPTETimecode()
            self.lib.ltc_frame_to_time(ctypes.byref(stime), ctypes.byref(frame.ltc), 0)
            yield stime
    def close(self):
        if self.decoder:
            self.lib.ltc_decoder_free(self.decoder)
            self.decoder = None

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

def find_libltc() -> str:
    base = os.path.join(os.path.dirname(__file__), "libs")
    if platform.system() == "Windows":
        candidates = [os.path.join(base, "libltc.dll"), "libltc.dll"]
    elif platform.system() == "Darwin":
        candidates = [os.path.join(base, "libltc.dylib"), "libltc.dylib", os.path.join(base, "libltc.so")]
    else:
        candidates = [
            os.path.join(base, "libltc.so"),
            "libltc.so",
            "/usr/lib/x86_64-linux-gnu/libltc.so",
            "/usr/lib/x86_64-linux-gnu/libltc.so.11",
        ]
    for c in candidates:
        if os.path.exists(c):
            return c
    raise FileNotFoundError("libltc library not found")

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
        self.num_channels = int(info.get("maxInputChannels", 1))
        logging.info("Input device: '%s' (index: %d)", info.get("name"), self.device_index)
        self.stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=self.num_channels,
            rate=self.sample_rate,
            input=True,
            input_device_index=self.device_index,
            frames_per_buffer=self.chunk_size,
        )
        fps = 30.0
        self.decoder = LibLTC(find_libltc(), self.sample_rate, fps)
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
            data = self.stream.read(self.chunk_size, exception_on_overflow=False)
            samples = array.array('h', data)
            if self.num_channels > 1:
                samples = samples[self.channel::self.num_channels]
            self.decoder.write(samples)
            for stime in self.decoder.read():
                tc = f"{stime.hours:02d}:{stime.mins:02d}:{stime.secs:02d}:{stime.frame:02d}"
                logging.debug("Decoded %s", tc)
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
    reader = LTCReader(config)
    reader.loop()

if __name__ == "__main__":
    main()
