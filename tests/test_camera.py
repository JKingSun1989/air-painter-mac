import unittest
from unittest.mock import Mock, call, patch

import cv2

import camera


class CameraBackendTests(unittest.TestCase):
    @patch("camera.platform.system", return_value="Windows")
    @patch("cv2.VideoCapture")
    def test_windows_tries_directshow_then_media_foundation(self, capture, _system):
        failed = Mock()
        failed.isOpened.return_value = False
        opened = Mock()
        opened.isOpened.return_value = True
        capture.side_effect = [failed, opened]

        result = camera.open_camera(2)

        self.assertIs(result, opened)
        self.assertEqual(capture.call_args_list, [
            call(2, cv2.CAP_DSHOW), call(2, cv2.CAP_MSMF)
        ])
        failed.release.assert_called_once_with()

    @patch("camera.platform.system", return_value="Windows")
    @patch("cv2.VideoCapture")
    def test_windows_camera_error_includes_privacy_guidance(self, capture, _system):
        failed = Mock()
        failed.isOpened.return_value = False
        capture.return_value = failed

        with self.assertRaisesRegex(RuntimeError, "允许桌面应用访问摄像头"):
            camera.open_camera()

        self.assertEqual(capture.call_count, 3)
        self.assertEqual(failed.release.call_count, 3)

    @patch("camera.platform.system", return_value="Windows")
    def test_windows_permission_is_managed_by_operating_system(self, _system):
        self.assertEqual(camera.camera_permission(), "system_managed")
        camera.require_camera_permission()


if __name__ == "__main__":
    unittest.main()
