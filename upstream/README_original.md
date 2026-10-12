<div align="center">

# 🎨 AI Virtual Painter

### Draw in the air using real-time hand tracking.

</div>

## 💡 What It Is

A computer-vision drawing app that turns hand gestures into controls for drawing, selecting colors, resizing the brush, and erasing. I built it to explore how raw hand landmarks can become a smooth interactive experience.

## 🛠️ Tech Stack

- **Python**
- **OpenCV** — webcam capture and rendering
- **MediaPipe Tasks API** — hand landmark detection
- **NumPy** — geometry and numerical operations

## ⚙️ How It Works

```text
Webcam
  ↓
MediaPipe Hand Landmarks
  ↓
Gesture Geometry
  ↓
Draw / Select / Resize / Erase
  ↓
EMA Smoothing + Canvas
```

It supports up to **two hands**, with independent interaction state and gesture-based brush controls.

## 🚀 Run Locally

```bash
git clone https://github.com/moizaiqbal40-ops/ai_virtual_painter.git
cd ai_virtual_painter
pip install -r requirements.txt
```

Place the required `hand_landmarker.task` model file in the project root, then run:

```bash
python ai_virtual_painter.py
```

## ✨ What I Learned / Challenges

The tricky part was turning noisy real-time landmark coordinates into gestures that feel responsive, so I added smoothing and explicit interaction states instead of drawing directly from raw points.
