import unittest

from doctor import expected_packages


class DoctorRequirementTests(unittest.TestCase):
    def test_platform_markers_filter_macos_only_dependencies(self):
        requirements = [
            "mediapipe==0.10.32",
            "pyobjc-framework-AVFoundation==11.1; sys_platform == 'darwin'",
        ]
        self.assertEqual(expected_packages(requirements, "win32"), {"mediapipe": "0.10.32"})
        self.assertEqual(expected_packages(requirements, "darwin"), {
            "mediapipe": "0.10.32",
            "pyobjc-framework-AVFoundation": "11.1",
        })


if __name__ == "__main__":
    unittest.main()
