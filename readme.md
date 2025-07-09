# LTC-OSC-Bridge (Python + libltc)

LTC（Linear Timecode）信号を**オーディオ入力からリアルタイム解析**し、**OSCプロトコル**で他アプリ（Node-RED / TouchDesigner など）に送信するためのPythonツールです。

---

## What It Does

- マイクやライン入力などから LTC 信号を取得（モノラル or ステレオ）
- `libltc` を使ってリアルタイムに LTC をデコード
- デコード結果（HH:MM:SS:FF形式のTimecode）を OSC メッセージで送信

---

## Requirements

- Python 3.9+
- [libltc](https://github.com/x42/libltc)（Windows: `.dll`, Mac/Linux: `.so`）
- Python packages:
  - `pyaudio`
  - `python-osc`

---

## Installation

```bash
pip install pyaudio python-osc
