# LTC-OSC-Bridge (Python + libltc)

LTC（Timecode）を**オーディオ入力からリアルタイム解析**し、**OSC**で他アプリ（Node-RED / TouchDesigner など）に送信するためのツールです。Windowsでタスクトレイアプリケーションとして動作し、設定値をGUIから変更できます。

---

## What It Does

- マイクやライン入力などから LTC 信号を取得（モノラル or ステレオ）
- `libltc` を使ってリアルタイムに LTC をデコード
- デコード結果（HH:MM:SS:FF形式のTimecode）を OSC メッセージで送信
- タイムコードにオフセットを適用可能（±999秒まで、100分の1秒精度）
- タイムコードの開始/停止状態をリアルタイム検知し、OSC で状態も送信

---

## Installation

Release版のバイナリは [Releases](https://github.com/zukio/LTC-OSC-Bridge/releases/) からダウンロードできます。

---

## Usage

1. `ltc_reader.exe` を実行
2. タスクトレイアイコンから設定を確認／終了

### 必要条件

- Windows 10+
- `.exe` と同じ階層に `libs/libltc.dll` があること
- オーディオデバイスにLTC音声が流れていること

### 推奨構成

- LTC信号のサンプルファイル（例: `LTC.wav`）を任意のプレイヤーで再生
- VB-Audio Virtual Cable を使用し、LTC信号を "CABLE Input" にループバック

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
  "fps": 30,
  "timecode_offset": 0.0,
  "stop_timeout": 0.5
}
```

- `timecode_offset`: タイムコードに適用するオフセット（秒単位、100分の1秒まで指定可能）
- `stop_timeout`: タイムコード停止を検知するまでの時間（秒単位、デフォルト: 0.5秒）

`config.json` が存在しない場合でも、上記の初期値で起動します。

## OSC メッセージ

アプリケーションは以下のOSCメッセージを送信します：

- **タイムコード**: `/ltc` (デフォルト) - `HH:MM:SS:FF` 形式の文字列
  - 例: `"12:34:56:15"`
- **ステータス+タイムコード**: `/ltc/status` (デフォルト) - `[ステータス文字列, タイムコード文字列]` の配列
  - 例: `["running", "12:34:56:15"]` または `["stopped", "12:34:56:15"]`

### TimeCoreとの連携例

TimeCoreなどのタイムコード生成デバイスでは以下のように活用できます：

1. **開始時** (`["stopped", "12:34:56:15"]` → `["running", "12:34:56:16"]`): 受信したタイムコードで同期
2. **動作中** (`["running", "..."]`): 内部クロックを使用（入力タイムコードは参考程度）
3. **停止時** (`["running", "..."]` → `["stopped", "..."]`): タイムコード生成を停止

ステータス変化時のみ `/ltc/status` が送信され、継続的に `/ltc` でタイムコード文字列が送信されます。

## 開発・カスタマイズ

リポジトリをクローンして、必要なパッケージをインストールします。

```bash
pip install -r requirements.txt
```

### 各ブランチの用途

- `main`: タスクトレイアプリケーション（タスクトレイから設定値を編集可）
- `savepoint`: タスクトレイアプリケーション（タスクトレイから変更不可）
- `dev`: LTC信号をOSCのパースするPythonスクリプトのみ（他プロジェクト組み込み用）

---

## Requirements

- Python 3.9+
- [libltc](https://github.com/x42/libltc)（Windows: `.dll`, Mac/Linux: `.so`）
- Python packages:
  - `pyaudio`
  - `python-osc`
