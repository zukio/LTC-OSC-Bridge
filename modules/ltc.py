import ctypes
import os
import platform

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
        self.lib.ltc_decoder_read.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(LTCFrameExt),
        ]
        self.lib.ltc_decoder_read.restype = ctypes.c_int
        self.lib.ltc_frame_to_time.argtypes = [
            ctypes.POINTER(SMPTETimecode),
            ctypes.POINTER(LTCFrame),
            ctypes.c_int,
        ]
        self.lib.ltc_frame_to_time.restype = None
        apv = int(sample_rate / fps)
        self.decoder = self.lib.ltc_decoder_create(apv, 10)
        self.posinfo = 0

    def write(self, samples):
        if not samples:
            return
        arr_type = ctypes.c_short * len(samples)
        c_samples = arr_type(*samples)
        self.lib.ltc_decoder_write_s16(
            self.decoder, c_samples, len(samples), self.posinfo)
        self.posinfo += len(samples)

    def read(self):
        frame = LTCFrameExt()
        while self.lib.ltc_decoder_read(self.decoder, ctypes.byref(frame)):
            stime = SMPTETimecode()
            self.lib.ltc_frame_to_time(
                ctypes.byref(stime), ctypes.byref(frame.ltc), 0)
            yield stime

    def close(self):
        if self.decoder:
            self.lib.ltc_decoder_free(self.decoder)
            self.decoder = None


def find_libltc() -> str:
    base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "libs")
    if platform.system() == "Windows":
        candidates = [os.path.join(base, "libltc.dll"), "libltc.dll"]
    elif platform.system() == "Darwin":
        candidates = [
            os.path.join(base, "libltc.dylib"),
            "libltc.dylib",
            os.path.join(base, "libltc.so"),
        ]
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
