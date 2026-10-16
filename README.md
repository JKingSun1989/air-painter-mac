# AI Air Painter

**English** · [简体中文](README.zh-CN.md)

Draw in the air with one hand, pinch to move your artwork, group strokes, and control a reversible flower animation by opening and closing your fingers. Hand tracking, drawing, and animation run locally on your computer. No account or cloud AI API is required.

## Demo

https://github.com/user-attachments/assets/4b30909b-5cf7-4863-87cb-e9a810ed5660

The video demonstrates the brush and particles, geometric shapes, multi-stroke groups, independent object dragging and re-grabbing, eraser, undo/redo, PNG export, mouse mode, single-hand tracking, and the flower animation. The interaction is driven by synthetic single-hand landmarks; the video does not show a real camera feed and is not a camera-recognition accuracy test.

[Download the MP4](docs/videos/air-painter-demo.mp4) · [Video generation script](scripts/create_demo_video.py)

## Features

- Draw with your index finger. Use the freehand brush, line, rectangle, or ellipse tools, seven colors, and an eraser.
- Create independent drawing objects. Pinch near a stroke to grab, drag, release, and move it again later.
- Group strokes in multiple colors. Undo and redo up to 30 actions; brief hand-tracking loss is handled safely.
- Add colorful sparks and warm embers while drawing. Particles appear in the preview and are not added to the artwork.
- Export regular or transparent PNGs. Mouse drawing and a no-camera mode are also available.
- Explore the reversible flower demo: pinch to form a bud, then open your fingers to make it bloom; close your fingers to rewind it. There is no progress bar.
- Use the macOS native `.app` launcher or the Windows launch scripts. Settings are saved locally.

The app tracks one hand. Switch between drawing and TIME modes with a button or keyboard shortcut to keep gestures unambiguous.

## Requirements

- macOS 13 or later, or 64-bit Windows 11 (Windows 10 is also supported).
- Python 3.11 or 3.12.
- A camera for hand tracking. Mouse mode and the flower demo can run without one.

Windows setup and unit tests have been verified in GitHub Actions. USB camera capture, local inference, and window startup have also been tested on Windows 11. Full real-hand gesture behavior and recognition under different lighting conditions still need manual testing. Linux is not supported.

## Install and run

Download the [latest source package from GitHub Releases](https://github.com/JKingSun1989/air-painter-mac/releases/latest), or clone this repository and run the commands for your platform from its root directory.

### macOS

Install the command line tools and Python if needed:

```bash
xcode-select --install
brew install python@3.11
```

Then install and launch:

```bash
# Restore executable permissions if they were not preserved during extraction.
chmod +x setup.sh start.sh scripts/build-app.sh
./setup.sh
./start.sh --foreground
```

`setup.sh` creates a virtual environment, installs pinned dependencies, downloads and verifies the MediaPipe model from Google, and builds `Air Painter.app` locally. Internet access is needed for the first setup. Hand tracking and drawing run locally afterward. You can also double-click `Air Painter.app` in the project folder; keep it alongside the project files, virtual environment, and model.

At first launch, allow camera access when macOS asks. If the project is in Documents, macOS may also ask for folder access. Run `./start.sh --foreground` in Terminal to see permission errors. The app starts paused; click **Start** or press **Space** to draw.

### Windows

Double-click `setup_windows.cmd`, then double-click `start_windows.cmd`. You can also use PowerShell:

```powershell
./setup.ps1
./start_windows.ps1
```

If the camera is unavailable on first launch, enable camera access and **Let desktop apps access your camera** under **Settings → Privacy & security → Camera**.

### Optional modes

```bash
# Flower opening/closing demo
./start.sh --foreground --time-demo

# Mouse drawing without a camera
./start.sh --foreground --no-camera
```

On Windows, run `start_windows.cmd --no-camera --time-demo` for the flower demo without a camera.

## Controls

| Action | Control |
| --- | --- |
| Draw | Extend only the index finger |
| Move an object | Pinch near a stroke, keep pinching while moving, then open your fingers to release |
| Group multiple strokes | `G` to start grouping, `F` to finish the group |
| Start / pause | `Space` |
| Brush / line / rectangle / ellipse | `P` / `L` / `R` / `O` |
| Undo / redo | `Z` / `Y` |
| Save regular / transparent PNG | `S` / `T` |
| TIME mode / return to drawing | `K` |
| Flower demo / reset to bud | `J` / `N` |
| Quit | **Quit** button, `Q`, or `Esc` |

The app does not preserve an editable canvas after quitting, so export your work as a PNG first. Preferences are saved in `settings.json`; artwork is saved in `paintings/`. These local files are excluded from the source package. See the [macOS guide](README_MAC.md) and [Windows guide](README_WINDOWS.md) for platform-specific details.

## Technology

Python 3.11/3.12, MediaPipe Hand Landmarker Tasks in VIDEO mode (one hand), OpenCV, NumPy, and Pillow. macOS uses PyObjC, AVFoundation, and AppKit for native camera permissions and app launching. Windows uses the OpenCV camera backend and PowerShell launch scripts.

| File | Responsibility |
| --- | --- |
| `ai_virtual_painter.py` | Camera, one model inference per frame, and the main window loop |
| `painter_core.py`, `drawing_objects.py` | Canvas, drawing objects, groups, hit testing, and history |
| `hand_interaction.py` | DRAW / IDLE / DRAG states, normalized pinch detection, hysteresis, and debounce |
| `gesture_time.py`, `flower_animation.py` | Finger-opening time mapping and deterministic, reversible flower rendering |
| `controls.py`, `chinese_text.py` | Chinese interface and buttons |
| `camera.py`, `window.py` | macOS / Windows camera and window adapters |
| `scripts/Launcher.m`, `scripts/build-app.sh` | Native macOS launcher and local app build |

## Tests

After installing the environment, run:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/test_time_ui.py
.venv/bin/python scripts/test_drag_ui.py
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The 78 unit tests passed locally on macOS and in Windows Actions on Python 3.11 and 3.12. After four Windows launcher regression tests were added, all 82 tests passed on Windows 11 with Python 3.11.9. Ten window integration scripts passed in a macOS desktop session. USB camera capture, local inference, and window startup have been tested on Windows 11; full real-hand gestures still need manual verification. Automated TIME and pinch tests use synthetic one-hand landmarks and do not establish real-camera recognition accuracy. See Actions for the latest remote test results.

To run the real-model image test, download its public test image (not included in the source package):

```bash
mkdir -p test-output
curl -fL -o test-output/pointing_up.jpg https://storage.googleapis.com/mediapipe-assets/pointing_up.jpg
.venv/bin/python scripts/test_model.py
```

See [Verification notes](docs/VERIFICATION.md) for results, limitations, and manual test steps.

## Attribution and license

Adapted from [moizaiqbal40-ops/ai_virtual_painter](https://github.com/moizaiqbal40-ops/ai_virtual_painter). The original copyright notice for Moeeza Iqbal and the [MIT license](LICENSE) are preserved. The original project description and code are in `upstream/`.

The point-to-segment distance implementation is adapted from [medhanshcodezz/air-canvas](https://github.com/medhanshcodezz/air-canvas); source attribution and its original MIT license are in [Third-party notices](THIRD_PARTY_NOTICES.md). Other third-party libraries, models, and test images retain their respective licenses and are not relicensed as this project's code.

For instructions on publishing your own GitHub repository, see [Publishing guide](PUBLISHING.md).
