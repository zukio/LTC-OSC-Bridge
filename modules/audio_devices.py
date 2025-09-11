import pyaudio
import sys


def list_input_devices():
    """Return a list of tuples (index, name) for available input devices."""
    pa = pyaudio.PyAudio()
    devices = []
    try:
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                name = info.get("name")
                devices.append((i, name))
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


def show_devices_info():
    """デバイス一覧を詳細情報付きで表示する"""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    pa = pyaudio.PyAudio()
    print("=== Available Audio Input Devices ===")
    print(f"Total devices: {pa.get_device_count()}")
    print()

    devices = list_input_devices()

    for i, name in devices:
        try:
            info = pa.get_device_info_by_index(i)
            max_input_channels = info.get('maxInputChannels', 0)
            sample_rate = info.get('defaultSampleRate', 0)
            host_api = info.get('hostApi', -1)

            print(
                f"Index: {i:2d} | Channels: {max_input_channels:2d} | Name: {name}")
            print(
                f"         Sample Rate: {sample_rate} Hz | Host API: {host_api}")
            print()

        except Exception as e:
            print(f"Index: {i:2d} | ERROR: {e}")
            print()

    pa.terminate()

    print(f"\n=== Summary: {len(devices)} input devices found ===")
    for i, name in devices:
        print(f"{i:2d}: {name}")

    print("\nconfig.json の audio_device_index に上記のIndexを指定してください。")


def main():
    """コマンドラインから直接実行された場合のエントリーポイント"""
    show_devices_info()


if __name__ == "__main__":
    main()
