# Oscilloscope XY Display (ESP32 + Python)

[日本語版はこちら](README.md)

Extracts the outlines of a video and draws them on an oscilloscope in XY mode, using the ESP32's DAC outputs. It works well with black-and-white videos such as Bad Apple!!, and plays the audio in sync.

<img width="1969" height="1108" alt="20261011_171955" src="https://github.com/user-attachments/assets/727520e0-ab58-4adf-bd94-0694a97b28b8" />

## ⚠️ Known issue (help wanted)

**Scenes with a lot of motion or fine detail (for example, the scene where Flandre appears) are displayed incorrectly.** Changing the resolution, the point budget and the baud rate did not fix it. If you have an idea about the cause or a fix, please open an Issue or a Pull Request!

- Example of the corrupted display: <img width="1818" height="1024" alt="20261011_171922" src="https://github.com/user-attachments/assets/62315128-57f0-43c2-b8da-995e2d44ca63" />

See [What I tried](#what-i-tried) and [Hypotheses (unverified)](#hypotheses-unverified) below.

## How it works

```
video → [PC: Python] contour extraction → point list (x, y) → serial → [ESP32] → DAC (GPIO25 = X, GPIO26 = Y) → oscilloscope (XY mode)
```

### PC side (`aaaosiro.py`)

1. Plays the video with ffpyplayer and takes frames in sync with the audio (frames that are late are dropped)
2. Converts to grayscale, resizes to `RES x RES` (128x128 by default) and binarizes
3. Extracts contour points with `cv2.findContours` (points on the image border are excluded)
4. If the number of points exceeds `MAX_PTS`, thins them out at even intervals
5. Converts coordinates to the 0–250 range and sends one whole frame over serial in a single write

### Serial protocol

- One point = 2 bytes (`x`, `y`, each 0–250)
- End of frame = `0xFF` (coordinates never exceed 250, so they cannot collide with it)
- Baud rate: 921600 bps (must be the same on the PC and the ESP32)

### ESP32 side

- Receiving and drawing run on separate cores
  - Core 1 (`loop`): receives bytes and fills the back buffer with the point list. When `0xFF` arrives, the buffers are swapped
  - Core 0 (render task): keeps looping over the current buffer and drawing it
- An oscilloscope shows a picture through persistence, so it is important to keep redrawing the same point list at high speed

## What you need

- An ESP32 with DAC outputs. This is the one I used: <img width="1231" height="643" alt="image" src="https://github.com/user-attachments/assets/9001f5a8-5032-40ed-82ae-d38e97bd604d" />
- An oscilloscope with XY mode (an analog oscilloscope is recommended)
- Wiring: GPIO25 → scope CH1 (X), GPIO26 → scope CH2 (Y), common GND
- Scope settings: XY mode, **both channels DC-coupled** (with AC coupling the picture drifts)

## Usage

### 1. ESP32

Upload `oscilloscope/oscilloscope.ino` to the ESP32.

- Arduino IDE 2.6.8 / esp32 board package 3.3.10
- Uses `driver/dac.h` (the legacy DAC driver)

### 2. PC

```
pip install opencv-python pyserial numpy ffpyplayer
```

Edit the settings at the top of `aaaosiro.py` to match your environment.

| Setting | Description |
|---|---|
| `VIDEO` | Video file to play |
| `PORT` | Serial port of the ESP32 (e.g. `COM3`) |
| `BAUD` | Baud rate (must match `Serial.begin` on the ESP32) |
| `LOOP` | `True` loops the video, `False` plays once and exits |
| `AUDIO` | `True` plays the audio as well |
| `RES` | Analysis resolution (higher is more detailed but produces more points) |
| `MAX_PTS` | Maximum number of points per frame (keep it at or below `MAX_P` on the ESP32) |
| `PRIORITIZE_LARGE` | When there are too many points, keep large contours and drop small ones |
| `DEBUG` | Print the point counts every 30 frames |

Run:

```
python aaaosiro.py
```

## About the video

**The video and audio files are not included in this repository.** Material such as Bad Apple!! is copyrighted, so please provide your own. `*.mp4` is excluded with `.gitignore`.

## What I tried

| What I tried | Result |
|---|---|
| Drawing a 1200-point circle from the ESP32 alone | Displayed cleanly (DAC speed and wiring are fine) |
| Separating receiving and drawing onto different cores, looping the point list | Big improvement |
| Canny → binarization + `findContours` (avoids doubled lines) | Improved |
| Removing the whole-image border contour "as a contour" → removing only the points on the border | The former also removed real contours in busy scenes, so I fixed it |
| Resolution 64 → 128 | More detailed |
| `MAX_PTS` 800 | Points became too sparse; worse |
| `MAX_PTS` 1200 | Improved |
| `MAX_PTS` 2400 + 2000000 bps | No improvement |
| Keeping large contours and dropping small ones (`PRIORITIZE_LARGE`) | No improvement |

## Hypotheses (unverified)

These are only hypotheses; none of them has been verified.

1. **Not enough points**: in scenes with many fine lines, the number of contour points is far above `MAX_PTS`, and thinning makes the points so sparse that the shapes become unreadable
2. **One drawing pass becomes too slow**: more points make each pass take longer, which causes flicker
3. **Serial bandwidth**: in scenes with many points there is little headroom left on the serial link
4. **No Z-axis (intensity) control**: the lines between contours cannot be blanked, and they stand out more the finer the picture is

Ideas for improvement:

- Simplify contours to vertices (`approxPolyDP`), send only those, and interpolate the lines on the ESP32
- Optimize the drawing order of the points to shorten the beam's travel distance
- Write the DAC registers directly to speed up drawing

## License

MIT License
