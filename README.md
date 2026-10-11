# オシロスコープXY表示 (ESP32 + Python)
[English version](README.en.md)

動画の輪郭を抽出して、ESP32のDAC出力からオシロスコープのXYモードに描画するプロジェクトです。Bad Apple!! などの白黒動画を、音と一緒に表示できます。

<img width="1969" height="1108" alt="20261011_171955" src="https://github.com/user-attachments/assets/727520e0-ab58-4adf-bd94-0694a97b28b8" />

<img width="2274" height="1280" alt="20261011_181339" src="https://github.com/user-attachments/assets/7285bdf1-ef20-46de-93fc-fc34570173f0" />


## ⚠️ 既知の問題（協力者募集）

**動きが激しいシーン（フランが出てくる場面など）で表示が崩れます。** 解像度、点数、通信速度を変えても直りませんでした。原因に心当たりのある方、修正案をIssueやPull Requestで教えてください！
- 崩れた表示の写真: <img width="1818" height="1024" alt="20261011_171922" src="https://github.com/user-attachments/assets/62315128-57f0-43c2-b8da-995e2d44ca63" />


詳しくは [試したこと](#試したこと) と [原因の仮説](#原因の仮説未確認) を見てください。

## 仕組み

```
動画 → [PC: Python] 輪郭抽出 → 点列(x,y) → シリアル → [ESP32] → DAC(GPIO25=X, GPIO26=Y) → オシロ(XYモード)
```

### PC側 (`aaaosiro.py`)

1. ffpyplayerで動画を再生し、音声に合わせてフレームを取り出す（遅れたフレームは捨てる）
2. グレースケール化して `RES x RES`（既定128x128）に縮小し、二値化
3. `cv2.findContours` で輪郭の点を取り出す（画面の端の点は除外）
4. 点数が `MAX_PTS` を超えたら、等間隔に間引く
5. 座標を0〜250に変換して、1フレーム分をまとめてシリアル送信

### 通信フォーマット

- 1点 = 2バイト（`x`, `y`、どちらも0〜250）
- フレームの終わり = `0xFF`（座標は250以下なので、座標と衝突しない）
- 通信速度: 921600 bps（PCとESP32で必ず同じにすること）

### ESP32側

- 受信と描画を別コアで動かす
  - コア1（`loop`）: 受信して、バックバッファに点列を溜める。`0xFF` が来たらバッファを切り替える
  - コア0（描画タスク）: 現在のバッファの点列を、ひたすらループして描き続ける
- オシロは残像で絵を見せるので、同じ点列を高速に繰り返し描画し続けるのが重要です

## 必要なもの

- ESP32（DAC付きのもの）:自分はこれを使いました <img width="1231" height="643" alt="image" src="https://github.com/user-attachments/assets/9001f5a8-5032-40ed-82ae-d38e97bd604d" />

- オシロスコープ（XYモード対応）※アナログオシロスコープ推奨です
- 配線: GPIO25 → オシロ CH1（X）、GPIO26 → オシロ CH2（Y）、GND共通
- オシロの設定: XYモード、**両チャンネルDCカップリング**（ACだと絵がずれていきます）

## 使い方

### 1. ESP32

`esp32/oscilloscope/oscilloscope.ino` をESP32に書き込みます。

- Arduino IDEのバージョン / ESP32ボードパッケージのバージョン: Arduino IDE 2.6.8　esp32 ボードパッケージ 3.3.10
- `driver/dac.h`（旧DACドライバ）を使っています

### 2. PC

```
pip install opencv-python pyserial numpy ffpyplayer
```

`aaaosiro.py` の冒頭の設定を環境に合わせて変更します。

| 設定 | 内容 |
|---|---|
| `VIDEO` | 再生する動画ファイル |
| `PORT` | ESP32のシリアルポート（例: `COM3`） |
| `BAUD` | 通信速度（ESP32側の `Serial.begin` と同じにする） |
| `LOOP` | `True` でループ再生、`False` で1回再生して終了 |
| `AUDIO` | `True` で音も再生 |
| `RES` | 解析解像度（上げると細かくなるが点が増える） |
| `MAX_PTS` | 1フレームの点数上限（ESP32側の `MAX_P` 以下にする） |
| `PRIORITIZE_LARGE` | 点が多いとき、大きな輪郭を優先して細かい輪郭を捨てる |
| `DEBUG` | 30フレームごとに点数を表示 |

実行:

```
python aaaosiro.py
```

## 動画について

**動画と音声ファイルはこのリポジトリに含まれていません。** Bad Apple!! などの素材は著作権があるため、各自で用意してください。`.gitignore` で `*.mp4` を除外しています。

## 試したこと

| 試したこと | 結果 |
|---|---|
| ESP32単体で1200点の円を描画 | きれいに表示される（DAC出力速度と配線は問題なし） |
| ESP32側で受信と描画を別コアに分離し、点列をループ描画 | 大きく改善 |
| Canny → 二値化+`findContours`（線が二重になるのを防ぐ） | 改善 |
| 画面全体の外枠を「輪郭ごと」除外 → 「端の点だけ」除外 | 前者は激しいシーンで本物の輪郭まで消えていたため修正 |
| 解像度 64 → 128 | 細かくなった |
| `MAX_PTS` 800 | 点がスカスカになり悪化 |
| `MAX_PTS` 1200 | 改善 |
| `MAX_PTS` 2400 + 2000000 bps | 改善せず |
| 大きな輪郭を優先して細かい輪郭を捨てる（`PRIORITIZE_LARGE`） | 改善せず |

## 原因の仮説（未確認）

あくまで仮説で、検証できていません。

1. **点数が足りない**: 細かい線が多いシーンでは輪郭の点が `MAX_PTS` を大きく超え、間引きで点がスカスカになって形が読めなくなる
2. **1周の描画が遅くなる**: 点数を増やすと1周にかかる時間が延び、ちらつく
3. **送信が追いつかない**: 点数が多いシーンで、シリアルの帯域に余裕がなくなる
4. **Z軸（輝度）がない**: 輪郭と輪郭の間の移動線が消せず、細かい絵ほど目立つ

改善のアイデア:

- 輪郭を頂点に簡略化（`approxPolyDP`）して送り、ESP32側で線を補間して描く
- 点の描画順を最適化して、移動距離を短くする
- DACの書き込みをレジスタ直書きにして、描画速度を上げる

## ライセンス

MIT License <!-- LICENSEファイルを追加する -->

---

## English summary

Draws the outlines of a video (e.g. Bad Apple!!) on an oscilloscope in XY mode, using an ESP32's two 8-bit DACs (GPIO25 = X, GPIO26 = Y). A Python script extracts contours with OpenCV and sends `(x, y)` byte pairs over serial (frame terminator `0xFF`, coordinates 0–250). The ESP32 receives on one core and continuously redraws the latest point list on the other. Audio is played in sync with ffpyplayer.

**Known issue / help wanted:** frames with a lot of detail or motion are displayed incorrectly. Changing resolution, point budget and baud rate did not fix it. See "試したこと" (what I tried) and "原因の仮説" (hypotheses) above. Issues and pull requests are very welcome!

The video file is not included (copyright). Please provide your own.
