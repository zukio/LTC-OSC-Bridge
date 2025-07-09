import pyaudio


def list_input_devices():
    """Return a list of tuples (index, name) for available input devices."""
    pa = pyaudio.PyAudio()
    devices = []
    try:
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                devices.append((i, info.get("name")))
    finally:
        pa.terminate()
    return devices


def get_device_name(index: int) -> str | None:
    """Return the device name for the given index or None if not found."""
    pa = pyaudio.PyAudio()
    try:
        info = pa.get_device_info_by_index(index)
        return info.get("name")
    except Exception:
        return None
    finally:
        pa.terminate()
