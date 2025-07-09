# LTC-OSC-Bridge プログラム仕様書：Python製 LTCリアルタイムデコーダ with OSC送信

## 目的

LTC（Linear Timecode）信号を音声入力（ライン/マイク）からリアルタイムで解析し、現在のタイムコードを OSC プロトコルで Node-RED や TouchDesigner などへ送信する。

---

## システム構成

```
[オーディオ入力（LTC音声）]
     ↓
[pyaudio（WASAPIまたはASIO）]
     ↓
[libltc（ctypesまたはCFFI経由で連携）]
     ↓
[デコード済み Timecode 文字列]
     ↓
[python-osc]
     ↓
[OSCクライアント（Node-RED, TouchDesigner など）]
```

---

## 使用技術・ライブラリ

| 役割      | 技術/ライブラリ             | 備考                              |
| ------- | -------------------- | ------------------------------- |
| 音声入力    | `pyaudio`            | WindowsではWASAPIまたはMME経由、要インストール |
| LTCデコード | `libltc`（C） + ctypes | `libltc.dll/.so` を呼び出し          |
| OSC送信   | `python-osc`         | UDPベース、TouchDesignerやNode-RED対応 |
| プロセス制御  | Python 3.11+         | GUIなし、CLI起動で常駐                  |

---

## 入力仕様

| 項目        | 内容                                    |
| --------- | ------------------------------------- |
| 音声入力      | モノラルまたはステレオ（指定チャンネル選択可能）              |
| サンプリング周波数 | 48kHz（推奨）、44.1kHz でも動作可               |
| LTC信号     | オーディオとして取り込まれたパルス型信号（〜2kHzのマンチェスター符号） |

---

## 出力仕様（OSC）

| 項目   | 内容                                      |
| ---- | --------------------------------------- |
| 宛先IP | `127.0.0.1`（configで指定可）                 |
| ポート  | `9000`（例）                               |
| アドレス | `/ltc`（固定）                              |
| 値    | 文字列 `"01:02:03:12"` の形式（HH\:MM\:SS\:FF） |
| 周期   | 1/30秒 or 1/25秒（信号に準拠）                   |

---

## 設定項目（`config.json`）

```json
{
  "osc_ip": "127.0.0.1",
  "osc_port": 9000,
  "osc_address": "/ltc",
  "audio_device_index": 1,
  "channel": 0,
  "sample_rate": 48000
}
```

---

## 動作例ログ

```
[INFO] Input device: 'USB Audio CODEC' (index: 1)
[INFO] Starting LTC decode loop...
[OSC] 00:12:34:18
[OSC] 00:12:34:19
[OSC] 00:12:34:20
...
```

---

## エラーハンドリング

| 状況            | 処理                            |
| ------------- | ----------------------------- |
| 音声デバイスが取得できない | 起動時に警告ログ + 終了                 |
| LTC信号の同期が取れない | `/ltc_sync_lost` のOSC送信（今後拡張） |
| ネットワーク送信失敗    | 自動リトライ（最大3回）し、以後黙ってスキップ       |

---

## 拡張予定（Ver.2.0構想）

* `/ltc/frames` `/ltc/hours` など個別情報送信
* UDPだけでなくWebSocket送信も対応
* TouchDesigner向けOSC Bundle形式
* GUI設定（PySide or tkinter）

---

## 開発ロードマップ（最小構成Ver.1.0）

1. `libltc` の Pythonバインディング準備（ctypesで DLL/SO 読み込み）
2. `pyaudio` でマイクから入力バッファ取得（512〜1024sample/chunk）
3. 音声バッファを libltc に渡して `ltc_decoder` で処理
4. デコード結果を OSC (`python-osc`) で `/ltc` に送信
5. Ctrl+C 終了対応

---

## 完成後の実行例

```bash
python ltc_reader.py --config config.json
```
