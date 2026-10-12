"""Environment diagnostics; optionally test actual camera frames and inference."""
import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / ".cache"))
MODEL_SHA256 = "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", action="store_true", help="实际申请权限、读取摄像头并执行模型")
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    info = {"python": sys.version.split()[0], "executable": sys.executable,
            "macos": platform.mac_ver()[0], "architecture": platform.machine(), "checks": {}}
    errors = []
    if sys.version_info[:2] not in ((3, 11), (3, 12)):
        errors.append("请使用 Python 3.11 或 3.12 运行 setup.sh。")
    if platform.system() != "Darwin":
        errors.append("此启动方案面向 macOS。")
    result = subprocess.run([sys.executable, "-m", "pip", "check"], capture_output=True, text=True)
    info["checks"]["dependencies"] = (result.stdout + result.stderr).strip()
    if result.returncode:
        errors.append("依赖检查失败，请运行 ./setup.sh 修复。")
    expected = {}
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        if "==" in line:
            name, version = line.split(";", 1)[0].strip().split("==")
            expected[name] = version
    info["packages"] = {}
    for name, version in expected.items():
        try:
            installed = metadata.version(name)
            info["packages"][name] = installed
            if installed != version:
                errors.append(f"{name} 需要 {version}，当前 {installed}。请运行 ./setup.sh。")
        except metadata.PackageNotFoundError:
            errors.append(f"缺少 {name}，请运行 ./setup.sh。")
    model_path = ROOT / "hand_landmarker.task"
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest() if model_path.is_file() else "missing"
    info["checks"]["model_sha256"] = digest
    if digest != MODEL_SHA256:
        errors.append("本地模型缺失或校验失败，请运行 ./setup.sh 重新下载。")
    if not errors:
        try:
            from mac_camera import camera_permission, require_camera_permission, open_camera
            info["checks"]["camera_permission"] = camera_permission()
            if args.camera:
                require_camera_permission()
                info["checks"]["camera_permission"] = camera_permission()
                from ai_virtual_painter import create_landmarker
                import mediapipe as mp
                import cv2
                cap = None
                try:
                    cap = open_camera(args.camera_index)
                    with create_landmarker() as model:
                        count = hands = 0
                        started = time.monotonic()
                        last_ts = -1
                        resolution = None
                        for _ in range(30):
                            ok, frame = cap.read()
                            if not ok or frame is None:
                                raise RuntimeError("摄像头读取失败。")
                            resolution = [frame.shape[1], frame.shape[0]]
                            rgb = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)
                            timestamp = max(last_ts + 1, int((time.monotonic() - started) * 1000))
                            last_ts = timestamp
                            detected = model.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp)
                            count += 1
                            hands += bool(detected.hand_landmarks)
                        info["checks"]["live_camera"] = {"frames": count, "resolution": resolution,
                            "frames_with_hands": hands, "elapsed_seconds": round(time.monotonic() - started, 2)}
                finally:
                    if cap is not None:
                        cap.release()
        except Exception as exc:
            errors.append(str(exc))
    info["ok"] = not errors
    info["errors"] = errors
    print(json.dumps(info, indent=2, ensure_ascii=False), flush=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
