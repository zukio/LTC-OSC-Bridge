# LTC-OSC-Bridge (Python + libltc)

LTC（Timecode）を**オーディオ入力からリアルタイム解析**し、**OSC**で他アプリ（Node-RED / TouchDesigner など）に送信するためのツールです。Windowsでタスクトレイアプリケーションとして動作し、設定値をGUIから変更できます。

---

## What It Does

- マイクやライン入力などから LTC 信号を取得（モノラル or ステレオ）
- `libltc` を使ってリアルタイムに LTC をデコード
- デコード結果（HH:MM:SS:FF形式のTimecode）を OSC メッセージで送信
- タイムコードにオフセットを適用可能（秒.フレーム形式で直感的設定）
- タイムコードの開始/停止状態をリアルタイム検知
- 用途別に分離されたOSCアドレスで受信側の実装が簡潔

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
  "fps": 29.97,
  "timecode_offset": 1.05,
  "stop_timeout": 0.5
}
```

**注意**: `osc_address` は基準アドレスです。v2.0では以下のように展開されます：

- タイムコード: `{osc_address}/decode` (例: `/ltc/decode`)
- 開始ステータス: `{osc_address}/status-running` (例: `/ltc/status-running`)  
- 停止ステータス: `{osc_address}/status-stopped` (例: `/ltc/status-stopped`)

### timecode_offset 設定方法

`timecode_offset` では **秒.フレーム** の形式でオフセット値を指定します：

- **整数部分**: 秒数（±999秒まで）
- **小数部分**: フレーム数（2桁まで、fps設定に基づく）

#### 設定例

- `1.05` = 1秒 + 5フレーム のオフセット
- `-2.15` = マイナス2秒 - 15フレーム のオフセット
- `0.00` = オフセットなし
- `10.29` = 10秒 + 29フレーム のオフセット（30fps時）

#### 注意事項

- フレーム数は設定されたfps値を超えることはできません（29.97fpsの場合、0-29まで）
- 無効なフレーム数が指定された場合、自動的に有効範囲に調整されます
- この形式により、タイムコード表示（HH:MM:SS:FF）と同じ感覚で直感的にオフセットを設定できます

#### 動作例

元のタイムコードが `12:34:56:10` で、オフセット設定が `1.05` の場合：

- オフセット適用前: `12:34:56:10`
- オフセット適用後: `12:34:57:15` (1秒5フレーム追加)

フレームレートが29.97fpsの場合、1秒 = 約29.97フレームなので、1.05の設定は正確に1秒5フレームのオフセットを意味します。

### その他の設定項目

- `fps`: フレームレート（24, 25, 29.97, 30, 59.97, 60をサポート）
- `stop_timeout`: タイムコード停止を検知するまでの時間（秒単位、デフォルト: 0.5秒）

`config.json` が存在しない場合でも、上記の初期値で起動します。

## OSC メッセージ

アプリケーションは以下のOSCメッセージを送信します：

### v2.0 新方式（推奨）

- **タイムコード（継続送信）**: `/ltc/decode` - `HH:MM:SS:FF` 形式の文字列
  - 例: `"12:34:56:15"`
- **ステータス（開始時）**: `/ltc/status-running` - タイムコード文字列
  - 例: `"12:34:56:16"` (開始時のタイムコード)
- **ステータス（停止時）**: `/ltc/status-stopped` - タイムコード文字列
  - 例: `"12:34:56:20"` (停止時のタイムコード)

### 受信側での実装例

```javascript
// Node-RED / TouchDesigner 例
/ltc/decode → 常時タイムコード表示更新
/ltc/status-running → レコーディング開始処理
/ltc/status-stopped → レコーディング停止処理
```

### TimeCoreとの連携例

TimeCoreなどのタイムコード生成デバイスでは以下のように活用できます：

1. **開始時** (`/ltc/status-running` 受信): 受信したタイムコードで同期開始
2. **動作中** (`/ltc/decode` 継続受信): 内部クロックを使用（参考情報として利用）
3. **停止時** (`/ltc/status-stopped` 受信): タイムコード生成を停止

各アドレスが用途別に分離されているため、受信側での処理が非常にシンプルになります。

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
