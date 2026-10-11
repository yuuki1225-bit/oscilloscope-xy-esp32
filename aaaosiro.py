import cv2
import serial
import time
import numpy as np
from ffpyplayer.player import MediaPlayer   # pip install ffpyplayer

# ===== 設定 =====
VIDEO = 'bad_apple.mp4'
PORT = 'COM3'
BAUD = 921600               # ESP32側のSerial.beginと必ず同じにする
LOOP = True                 # True: ループ再生 / False: 1回再生して終了
AUDIO = True                # True: 音も同時に再生 / False: 無音
RES = 128                   # 解析解像度
MAX_PTS = 1200              # 1フレームの点数上限（ESP32側のMAX_P以下にすること）
PRIORITIZE_LARGE = False    # True: 点が多いとき大きな輪郭を優先し細かい輪郭を捨てる False: 全体から等間隔に間引く
DEBUG = True                # 30フレームごとに点数を表示する
# =================

SCALE = 250 / (RES - 1)     # 座標を0〜250に収める（0xFFは終端マーカー用）
CENTER = bytes([125, 125, 0xFF])

ser = serial.Serial(PORT, BAUD)
dbg_count = 0


def frame_to_packet(img):
    """ffpyplayerのImageから、ESP32に送るパケットを作る"""
    global dbg_count
    w, h = img.get_size()
    rgb = np.frombuffer(img.to_bytearray()[0], dtype=np.uint8).reshape(h, w, 3)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    small = cv2.resize(gray, (RES, RES), interpolation=cv2.INTER_AREA)

    _, bw = cv2.threshold(small, 128, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(bw, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

    pts = []
    for c in contours:
        p = c[:, 0, :]
        # 画面の端にある点だけを除外する（輪郭ごと捨てない）
        keep = (p[:, 0] > 0) & (p[:, 0] < RES - 1) & (p[:, 1] > 0) & (p[:, 1] < RES - 1)
        p = p[keep]
        if len(p) < 3:                      # 小さなゴミは除外
            continue
        pts.append(p)

    if not pts:
        return CENTER

    total = sum(len(p) for p in pts)

    if total > MAX_PTS:
        if PRIORITIZE_LARGE:
            pts.sort(key=len, reverse=True)
            chosen, left = [], MAX_PTS
            for p in pts:
                if len(p) <= left:
                    chosen.append(p)
                    left -= len(p)
            if not chosen:
                p = pts[0]
                chosen = [p[np.linspace(0, len(p) - 1, MAX_PTS).astype(int)]]
            allp = np.concatenate(chosen)
        else:
            allp = np.concatenate(pts)
            allp = allp[np.linspace(0, len(allp) - 1, MAX_PTS).astype(int)]
    else:
        allp = np.concatenate(pts)

    if DEBUG:
        dbg_count += 1
        if dbg_count % 30 == 0:
            print(f"raw {total} -> sent {len(allp)} points")

    xs = np.minimum(250, (allp[:, 0] * SCALE).astype(int))
    ys = np.minimum(250, ((RES - 1 - allp[:, 1]) * SCALE).astype(int))  # 上下反転

    arr = np.empty(len(allp) * 2, dtype=np.uint8)
    arr[0::2] = xs
    arr[1::2] = ys
    return arr.tobytes() + b'\xff'          # 0xFFでフレーム終端


def open_player():
    opts = {'sync': 'audio'}                # 音声を基準に映像の時刻を合わせる
    if not AUDIO:
        opts['an'] = True                   # 音声を無効化
        opts['sync'] = 'video'
    return MediaPlayer(VIDEO, ff_opts=opts)


def next_frame(player):
    """次に送るフレームを取り出す。表示時刻を過ぎて遅れているフレームは捨てる"""
    latest = None
    while True:
        frame, val = player.get_frame()
        if val == 'eof':
            return 'eof'
        if frame is None:
            return latest
        latest = (frame[0], val)
        if val > 0:                         # まだ表示時刻前ならこれを使う
            return latest


player = open_player()
try:
    while True:
        res = next_frame(player)

        if res == 'eof':
            if LOOP:
                player.close_player()
                player = open_player()
                continue
            break

        if res is None:
            time.sleep(0.002)
            continue

        img, wait = res
        t_start = time.perf_counter()
        pkt = frame_to_packet(img)
        # 表示時刻までの残り時間だけ待ってから送る
        remain = wait - (time.perf_counter() - t_start)
        if remain > 0:
            time.sleep(remain)
        ser.write(pkt)
finally:
    ser.write(CENTER)                       # 終了時は中央に点を出して止める
    player.close_player()