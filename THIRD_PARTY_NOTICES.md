# 第三方来源

## 原项目

- 项目：<https://github.com/moizaiqbal40-ops/ai_virtual_painter>
- 原作者版权：Copyright (c) 2026 Moeeza Iqbal。
- 许可：MIT，完整原文保留在根目录 [LICENSE](LICENSE)。
- 审计基线：`c4c68b1d699d60a59f8e2ac1fb09ec4ddb7104c8`。
- 原代码、依赖和 README 保留在 `upstream/`。当前 README 描述 Mac 改造版本，原版双手功能不是当前版本功能。

## air-canvas

- 项目：<https://github.com/medhanshcodezz/air-canvas>
- 基线：`fb72f58ea9bf98c8e243352cd3ca088764cbd833`。
- `drawing_objects.py` 的点到线段距离算法改编自 `aircanvas/geometry.py`。
- 许可：MIT，完整原文见 [third_party/air-canvas-LICENSE](third_party/air-canvas-LICENSE)。

## 其他参考代码

曾阅读 Hand-Gesture-Drag-Drop 和 Gesture-Controlled-Virtual-Puzzle-Game 的实际代码，借鉴对象列表与包围盒检测；未复制其主循环或将其作为运行时依赖。项目、提交及采用方式见 [DRAG_IMPLEMENTATION.md](DRAG_IMPLEMENTATION.md)。

## 运行时库与外部资源

Python、MediaPipe、OpenCV、NumPy、Pillow 和 PyObjC 均由使用者的安装环境提供，遵循各自许可；源码包不包含这些库的二进制或系统字体。

MediaPipe Hand Landmarker 模型由 `setup.sh` 从 Google 官方地址下载，SHA-256 固定校验。官方测试图片由使用者按 README 下载。两种资源不包含在发布的源码包中，本项目 MIT 声明不覆盖它们。

`docs/images/` 中的截图由本项目程序生成，使用合成手部输入，不包含真人摄像头图像或用户画作。
