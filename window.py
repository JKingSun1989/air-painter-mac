"""Create an OpenCV window with a Unicode title on supported desktops."""
import ctypes
import sys

import cv2


def _set_windows_title(handle, title):
    """Use the wide Win32 API because some OpenCV builds use ANSI titles."""
    user32 = ctypes.windll.user32
    user32.FindWindowW.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p)
    user32.FindWindowW.restype = ctypes.c_void_p
    user32.SetWindowTextW.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p)
    user32.SetWindowTextW.restype = ctypes.c_bool
    hwnd = user32.FindWindowW(None, handle)
    if hwnd:
        return bool(user32.SetWindowTextW(hwnd, title))
    return False


def create_window(handle, title):
    cv2.namedWindow(handle, cv2.WINDOW_AUTOSIZE)
    if sys.platform == "darwin":
        # OpenCV 4.11's Cocoa backend formats UTF-8 bytes with NSString "%s",
        # which garbles Chinese. PyObjC passes a real Unicode NSString instead.
        from AppKit import NSApplication
        for window in NSApplication.sharedApplication().windows():
            if str(window.title()) == handle and window.isVisible():
                window.setTitle_(title)
                return
        raise RuntimeError("绘画窗口创建失败，请重新启动。")
    if sys.platform == "win32":
        if not _set_windows_title(handle, title):
            cv2.setWindowTitle(handle, title)
        return
    cv2.setWindowTitle(handle, title)
