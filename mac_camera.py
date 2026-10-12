"""Check macOS camera authorization through the public AVFoundation API."""
import platform
import threading
import time

STATUS = {0: "not_determined", 1: "restricted", 2: "denied", 3: "authorized"}
HELP = "请在 系统设置 → 隐私与安全性 → 摄像头 中允许 Air Painter 或启动程序的应用，然后重新启动。"


def camera_permission(request=False, timeout=45):
    if platform.system() != "Darwin":
        return "not_applicable"
    import AVFoundation as av
    status = int(av.AVCaptureDevice.authorizationStatusForMediaType_(av.AVMediaTypeVideo))
    if status == 0 and request:
        from Foundation import NSRunLoop, NSDate
        done = threading.Event()
        def completed(granted):
            done.set()
        av.AVCaptureDevice.requestAccessForMediaType_completionHandler_(av.AVMediaTypeVideo, completed)
        deadline = time.monotonic() + timeout
        while not done.is_set() and time.monotonic() < deadline:
            NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))
        status = int(av.AVCaptureDevice.authorizationStatusForMediaType_(av.AVMediaTypeVideo))
    return STATUS.get(status, "unknown")


def require_camera_permission():
    status = camera_permission(request=True)
    print(f"摄像头权限：{status}", flush=True)
    if status in ("denied", "restricted", "not_determined", "unknown"):
        raise RuntimeError(HELP + f"（当前状态：{status}）")


def open_camera(index=0):
    import cv2
    from config import FRAME_W, FRAME_H
    cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION if platform.system() == "Darwin" else cv2.CAP_ANY)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"无法打开摄像头 {index}。请关闭占用摄像头的程序，或使用 --camera 1。" + HELP)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
    return cap
