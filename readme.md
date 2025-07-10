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

Release版のバイナリは [Releases](https://github.com/yourusername/LTC-OSC-Bridge/releases) からダウンロードできます。

---

## Usage

### 必要条件

- Windows 10+
- `.exe` と同じ階層に `libs/libltc.dll` があること
- オーディオデバイスにLTC音声が流れていること

### Configuration

`config.json` で次の項目を設定できます。実行中はトレイメニューから
GUI設定ウィンドウを開き、値を変更して保存すると自動的に再起動します。

```json
{
  "osc_ip": "127.0.0.1",
  "osc_port": 9000,
  "osc_address": "/ltc",
  "audio_device_index": 1,
  "channel": 0,
  "sample_rate": 48000,
  "fps": 30
}
```

## 開発・カスタマイズ

リポジトリをクローンして、必要なパッケージをインストールします。

```bash
pip install -r requirements.txt
```

### 各ブランチの用途

- `main`: タスクトレイアプリケーション（タスクトレイから設定値を編集可）
- `savepoint`: タスクトレイアプリケーション（タスクトレイから変更不可）
- `dev`: LTC信号をOSCのパースするPythonスクリプトのみ（他プロジェクト組み込み用）
