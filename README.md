# AI 隔空绘画 · Air Painter for Mac

通过一只手在摄像头前绘画、捏合移动图形，或张开手指让花苞盛开。中文界面，手部识别、图形处理和动画全部在本机运行，无需账号或云端 AI API。

## 完整功能演示

https://github.com/user-attachments/assets/4b30909b-5cf7-4863-87cb-e9a810ed5660

视频依次演示画笔与粒子、几何形状、多笔分组、独立对象拖动与重抓、橡皮擦、撤销重做、PNG 导出、鼠标模式、单手识别和花朵开合。动作输入由合成单手关键点驱动，不包含真人摄像头画面；这段视频用于演示交互流程，不代表真人摄像头识别率测试。

[下载 MP4](docs/videos/air-painter-demo.mp4) · [视频生成脚本](scripts/create_demo_video.py)

## 功能

- 食指隔空绘画；自由画笔、直线、矩形、椭圆、7 种颜色、橡皮擦。
- 独立绘画对象；拇指与食指捏合抓取、拖动和释放，支持反复移动。
- 多笔、多色分组；30 步撤销与重做，手部丢失保护。
- 彩色闪光和暖色火星特效，仅显示在预览，不写入画作。
- 普通及透明背景 PNG 导出，鼠标绘画与无需摄像头模式。
- TIME 花朵演示：捏合是花苞，逐渐张开同步展开，充分张开完成盛开；合拢可倒放。无进度条。
- macOS 原生 `.app` 启动器、摄像头权限说明和本地设置保存。

仅支持单手；通过按钮或快捷键切换绘画与 TIME，避免手势冲突。

## 安装与启动

需要 macOS 13+、Python 3.11（也接受 3.12）和 Xcode Command Line Tools。已验证环境为 Apple Silicon / Python 3.11；其他 Mac 与 Python 3.12 尚未全面验证。不提供 Windows、Linux 支持。

下载源码或克隆自己的仓库后，在项目根目录执行：

```bash
# 没有这些工具时先安装：
xcode-select --install
brew install python@3.11

# 解压方式未保留执行权限时先执行：
chmod +x setup.sh start.sh scripts/build-app.sh
./setup.sh
./start.sh --foreground
```

`setup.sh` 创建 `.venv`、安装固定依赖、从 Google 官方地址下载并校验 MediaPipe 模型，再在本机编译 `Air Painter.app`。首次安装需要联网；日常推理和绘画在本机执行。安装完成后可双击项目里的 `Air Painter.app`，请保持它与项目文件、虚拟环境和模型在同一目录。

首次使用按 macOS 提示允许摄像头访问；若项目位于“文稿”目录，也可能需要目录访问权限。权限问题可先使用 `./start.sh --foreground` 查看提示。

程序默认暂停，点击“开始”或按空格开始绘画。

```bash
# 花朵开合演示
./start.sh --foreground --time-demo

# 无摄像头鼠标绘画
./start.sh --foreground --no-camera
```

## 常用操作

| 操作 | 方法 |
| --- | --- |
| 绘画 | 仅伸出食指 |
| 移动对象 | 在笔迹附近捏合，保持捏合移动，张开释放 |
| 多笔分组 | G 开启分组，F 完成当前组 |
| 开始 / 暂停 | 空格 |
| 画笔 / 直线 / 矩形 / 椭圆 | P / L / R / O |
| 撤销 / 重做 | Z / Y |
| 保存普通 / 透明 PNG | S / T |
| TIME / 返回绘画 | K |
| 花朵演示 / 回到花苞 | J / N |
| 退出 | 左下角“退出”、Q 或 Esc |

退出后不会保留可编辑画布，请先保存 PNG。设置保存在 `settings.json`，画作保存在 `paintings/`；二者均不进入源码包。详细行为、快捷键和异常处理见 [Mac 使用说明](README_MAC.md)。

## 技术与结构

Python 3.11、MediaPipe Hand Landmarker Tasks VIDEO（仅一只手）、OpenCV、NumPy、Pillow，以及 PyObjC / AVFoundation / AppKit。

| 文件 | 职责 |
| --- | --- |
| `ai_virtual_painter.py` | 摄像头、单次模型推理和窗口主循环 |
| `painter_core.py`、`drawing_objects.py` | 画布、对象、分组、命中检测与历史 |
| `hand_interaction.py` | DRAW / IDLE / DRAG，归一化捏合、滞回与防抖 |
| `gesture_time.py`、`flower_animation.py` | 手指开合映射与确定性可逆花朵渲染 |
| `controls.py`、`chinese_text.py` | 中文界面与按钮 |
| `scripts/Launcher.m`、`scripts/build-app.sh` | 原生启动器及本机构建 |

## 测试

安装环境后执行：

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/test_time_ui.py
.venv/bin/python scripts/test_drag_ui.py
```

当前 72 项单元测试和 10 个集成脚本已通过。窗口集成测试需要 macOS 图形会话；TIME / 捏合验收使用合成单手关键点，真实模型回归使用官方图片，不代表真人摄像头下的识别率已验证。

运行真实模型图片测试前，下载公开测试资源（不包含在源码包中）：

```bash
mkdir -p test-output
curl -fL -o test-output/pointing_up.jpg https://storage.googleapis.com/mediapipe-assets/pointing_up.jpg
.venv/bin/python scripts/test_model.py
```

更多结果、限制与人工测试步骤见 [验证说明](docs/VERIFICATION.md)。

## 来源与许可

基于 [moizaiqbal40-ops/ai_virtual_painter](https://github.com/moizaiqbal40-ops/ai_virtual_painter) 改造，保留原作者 Moeeza Iqbal 的版权声明及 [MIT LICENSE](LICENSE)。原版说明和代码保存在 `upstream/`。

点到线段距离实现改编自 [medhanshcodezz/air-canvas](https://github.com/medhanshcodezz/air-canvas)，源码标注及原 MIT 许可证见 [第三方说明](THIRD_PARTY_NOTICES.md)。参考代码审计见 [DRAG_IMPLEMENTATION.md](DRAG_IMPLEMENTATION.md)。第三方库、模型和测试图片遵循各自的许可，不重新许可为本项目代码。

准备上传自己的 GitHub 仓库见 [PUBLISHING.md](PUBLISHING.md)。
