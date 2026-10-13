# Windows 使用说明

支持 64 位 Windows 10/11 与 Python 3.11 或 3.12。手势识别、绘画、对象拖动、TIME 花朵动画、导出和撤销重做复用同一套 Python 代码；摄像头通过 OpenCV 打开，并依次尝试 DirectShow、Media Foundation 和默认后端。

## 安装与启动

1. 安装 64 位 Python 3.11 或 3.12，并勾选 Python Launcher（`py.exe`）。
2. 下载并解压项目源码。
3. 双击 `setup_windows.cmd`。脚本会创建 `.venv`、安装依赖、下载 MediaPipe 手部模型并检查文件 SHA-256。
4. 双击 `start_windows.cmd` 启动。每次启动都会使用项目内的虚拟环境。

也可以在 PowerShell 中进入项目目录运行：

```powershell
./setup.ps1
./start_windows.ps1
```

第一次安装需要联网下载 Python 依赖和 MediaPipe 模型；运行时手部识别和绘画在本机完成。摄像头权限由 Windows 管理：打开“设置 → 隐私和安全性 → 摄像头”，启用“摄像头访问”和“允许桌面应用访问摄像头”。如果摄像头打不开，先关闭 Teams、Zoom、浏览器等正在使用摄像头的程序；可用 `start_windows.cmd --camera 1` 选择第二个摄像头。

## 运行方式

默认启动使用摄像头。花朵演示、鼠标绘画和集成测试可关闭摄像头：

```powershell
./start_windows.cmd --no-camera --time-demo
./start_windows.cmd --no-camera
```

窗口默认暂停，点击“开始”或按空格后绘画。所有快捷键和手势见根目录 README。绘画导出到项目下的 `paintings/`，偏好设置写入 `settings.json`；请先保存 PNG，退出时不会保存可编辑画布。

2026-10-13 已在 64 位 Windows 11 / Python 3.11.9 / USB 摄像头环境完成安装、模型校验、82 项单元测试及绘画窗口启动验证。摄像头读取和本地模型推理正常；这不代表不同光线下的识别率或全部真人手势已经验收。macOS 使用说明见 [README_MAC.md](README_MAC.md)。

安装脚本保留 UTF-8 BOM，确保 Windows 自带 PowerShell 5.1 正确读取中文。启动器支持路径及参数中的空格，并将程序退出状态返回给启动脚本。新增测试覆盖这些情况，Windows Actions 分别检查 PowerShell 5.1 和 PowerShell 7；远程结果以对应提交的 Actions 记录为准。
