import unittest
from unittest.mock import patch

import window


class WindowPlatformTests(unittest.TestCase):
    @patch("window._set_windows_title", return_value=True)
    @patch("window.cv2.setWindowTitle")
    @patch("window.cv2.namedWindow")
    @patch("window.sys.platform", "win32")
    def test_windows_sets_unicode_title_through_win32_api(self, named, fallback, set_title):
        window.create_window("Air Painter", "AI 隔空绘画")
        named.assert_called_once_with("Air Painter", window.cv2.WINDOW_AUTOSIZE)
        set_title.assert_called_once_with("Air Painter", "AI 隔空绘画")
        fallback.assert_not_called()

    @patch("window._set_windows_title", return_value=False)
    @patch("window.cv2.setWindowTitle")
    @patch("window.cv2.namedWindow")
    @patch("window.sys.platform", "win32")
    def test_windows_falls_back_to_opencv_title(self, named, fallback, set_title):
        window.create_window("Air Painter", "AI 隔空绘画")
        named.assert_called_once()
        set_title.assert_called_once_with("Air Painter", "AI 隔空绘画")
        fallback.assert_called_once_with("Air Painter", "AI 隔空绘画")


if __name__ == "__main__":
    unittest.main()
