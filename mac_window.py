"""Keep OpenCV's window key ASCII and set the visible title as Unicode."""
import sys

import cv2


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
    else:
        cv2.setWindowTitle(handle, title)
