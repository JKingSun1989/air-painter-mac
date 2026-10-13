"""Cross-platform camera access and macOS camera permission checks."""
import platform
import threading
import time

STATUS = {0: "not_determined", 1: "restricted", 2: "denied", 3: "authorized"}
MAC_HELP = "请在 系统设置 → 隐私与安全性 → 摄像头 中允许 Air Painter 或启动程序的应用，然后重新启动。"
WINDOWS_HELP = (
    "请在 Windows 设置 → 隐私和安全性 → 摄像头 中开启“摄像头访问”和“允许桌面应用访问摄像头”，"
    "并关闭占用摄像头的程序后重试。"
)


def camera_permission(request=False, timeout=45):
    system = platform.system()
    if system != "Darwin":
        return "system_managed" if system == "Windows" else "not_applicable"
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
    if platform.system() != "Darwin":
        return
    status = camera_permission(request=True)
    print(f"摄像头权限：{status}", flush=True)
    if status in ("denied", "restricted", "not_determined", "unknown"):
        raise RuntimeError(MAC_HELP + f"（当前状态：{status}）")


def open_camera(index=0):
    import cv2
    from config import FRAME_W, FRAME_H

    system = platform.system()
    if system == "Darwin":
        backends = [cv2.CAP_AVFOUNDATION]
    elif system == "Windows":
        # DirectShow starts quickly on many USB webcams; MSMF and CAP_ANY cover
        # newer built-in cameras and drivers that do not expose DirectShow.
        backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
    else:
        backends = [cv2.CAP_ANY]

    for backend in backends:
        cap = cv2.VideoCapture(index, backend)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
            return cap
        cap.release()

    hint = WINDOWS_HELP if system == "Windows" else MAC_HELP if system == "Darwin" else ""
    raise RuntimeError(f"无法打开摄像头 {index}。请检查摄像头连接、隐私权限并关闭占用摄像头的程序。{hint}")
