#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
オーディオデバイスリストを表示し、正しいdevice_indexを確認するためのスクリプト
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import pyaudio


def main():
    pa = pyaudio.PyAudio()

    print("=== Available Audio Input Devices ===")
    print(f"Total devices: {pa.get_device_count()}")
    print()

    input_devices = []

    for i in range(pa.get_device_count()):
        try:
            info = pa.get_device_info_by_index(i)
            max_input_channels = info.get('maxInputChannels', 0)

            if max_input_channels > 0:  # 入力可能デバイスのみ
                name = info.get('name', 'Unknown')
                sample_rate = info.get('defaultSampleRate', 0)
                host_api = info.get('hostApi', -1)

                print(
                    f"Index: {i:2d} | Channels: {max_input_channels:2d} | Name: {name}")
                print(
                    f"         Sample Rate: {sample_rate} Hz | Host API: {host_api}")
                print()

                input_devices.append((i, name, max_input_channels))

        except Exception as e:
            print(f"Index: {i:2d} | ERROR: {e}")
            print()

    pa.terminate()

    print(f"\n=== Summary: {len(input_devices)} input devices found ===")
    for i, name, channels in input_devices:
        print(f"{i:2d}: {name} ({channels} channels)")

    print("\nconfig.json の audio_device_index に上記のIndexを指定してください。")


if __name__ == "__main__":
    main()
