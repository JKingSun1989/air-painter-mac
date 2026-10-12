# 本机验证结果

这是本机开发与验收的历史记录。`test-output/` 日志及历史截图不随源码包分发；当前功能与公开截图见 [验证说明](docs/VERIFICATION.md)。

日期：2026-10-11。机器：Apple M1 Pro / ARM64，macOS 27.0，独立虚拟环境 Python 3.11.15。

## 验证结果

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 上游源码与许可证 | 已检查实际代码，保留 MIT 许可证与版权 | `upstream/`、`LICENSE`、`README_MAC.md` |
| Python / 依赖兼容性 | 固定版本安装成功，`pip check` 通过 | `requirements.txt`、`requirements.lock.txt` |
| 官方模型完整性 | SHA-256 校验通过 | `test-output/live_camera.json` |
| 摄像头授权 | macOS 授权成功 | `test-output/live_camera.json` |
| 实际摄像头 + 模型 | 成功读取 30 帧，原始分辨率 1760×1328 | `test-output/live_camera.json` |
| 真实窗口 20 秒测试 | 328 帧，正常结束 | `test-output/live_window.json` |
| 真实窗口 60 秒测试 | 986 帧，约 16.4 FPS，正常结束 | `test-output/live_window_60s.json` |
| 真实模型识别官方手部图片 | 21 帧均识别，21 个关键点，食指 Draw 手势正确 | `test-output/model_integration.json` |
| 官方图片 → 实际窗口 → 操作控制 | 32 帧，鼠标与键盘开始/停止、红蓝绿、整笔撤销、清屏恢复、保存、笔宽、骨架、退出成功 | `test-output/ui_integration.json` |
| 保存结果 | 从 PNG 重新读取，像素与画布完全一致；共验证 7 种颜色 | `test-output/model-paintings/`、`test-output/ui-paintings/` |
| 功能单元测试 | 29 项通过，包括平滑减抖、撤销重做、透明导出、形状预览确认、白底边缘和配置容错 | `tests/test_painter.py`、`tests/test_shapes_preferences.py` |
| 安装 / 启动器 | `setup.sh` 完成，`.app` 构建与本地签名成功 | `scripts/build-app.sh`、`Air Painter.app` |

真实摄像头测试期间用户不在电脑前，因此这些摄像头帧没有识别到手。已验证摄像头读取、窗口显示和本地推理连续运行，手势到绘画与控制操作通过官方手部图片驱动的真实推理完成；尚未验证真人在此摄像头前的光线、遮挡、姿势及操作体验。没有录制或保存用户摄像头画面。

## 已修复问题

- 默认 Python 3.14 不直接用于旧项目，选用独立 Python 3.11 环境。
- MediaPipe 0.10.21 / 0.10.18 的 universal2 包内错误平台标签，改为 0.10.32 原生 ARM64 包；不修改第三方包元数据。
- OpenCV 与 MediaPipe 间依赖可能安装两套 `cv2`，固定使用 `opencv-contrib-python`。
- 命令行 Python 缺少摄像头用途声明，增加带 `NSCameraUsageDescription` 的本地 `.app` 启动器。
- 原项目拇指自然伸出时无法食指绘画，改为允许拇指伸出；张掌改为抬笔。
- 每帧 EMA 整数取整产生粘滞，改为保留浮点状态；坐标突跳在平滑前断开轨迹。
- 停止、换色、丢失手部后可能误连线，统一重置笔划与平滑状态。
- 清屏不可恢复、没有撤销，加入最多 30 步的整笔快照，清屏也可撤销。
- 保存路径依赖当前目录、秒级文件名可能覆盖，改为项目固定路径及微秒命名；检查写入失败。
- MediaPipe 导入可能写入主目录的缓存，改为项目内缓存。

部分本机图像预处理需要 OpenGL 上下文，在受限执行沙箱中可能不可用；模型和窗口测试已经在正常 macOS 桌面环境中执行通过。正式使用 `start.sh` 启动本地应用。

## 新增功能验证

新增：橡皮擦、重做、透明背景 PNG、鼠标绘画、完全无需摄像头的鼠标模式；同时改为 Finder / 终端使用相同环境诊断入口。

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 新版摄像头 / 真实窗口 | 前台启动 6 秒、98 帧，正常结束 | `test-output/live_window_v2.json` |
| 新版无摄像头窗口 | 前台启动 2 秒、92 帧，摄像头为空、未运行模型 | `test-output/foreground_mouse_launch.json` |
| 鼠标绘画真实窗口测试 | 21 帧，连续笔划、橡皮擦、撤销/重做、透明保存、暂停和退出全部通过 | `test-output/mouse_integration.json` |
| 透明导出 | 读取实际 PNG，确认 4 通道、Alpha 与画布一致、擦除处为 0、抗锯齿边缘颜色正确 | `test-output/mouse-paintings/`、`tests/test_painter.py` |
| 原功能回归 | 32 帧官方手部图片真实推理及原控制测试通过 | `test-output/ui_integration.json` |
| 模型回归 | 21 帧、7 种颜色、保存及清屏恢复通过 | `test-output/model_integration.json` |
| `.app` 构建 / 签名 | 构建通过，严格签名校验与 Info.plist 校验通过 | `scripts/build-app.sh` |

新版 `.app` 双击启动测试发现：macOS 将更新前的本地二进制哈希作为“文稿”目录权限身份，更新后再次要求授权，Python 进程在读取虚拟环境配置时等待系统弹窗。已加入目录用途声明、稳定的本地签名标识和 `--foreground` 启动方式；没有修改 TCC 数据库、自动点击授权或绕过系统权限。用户目前不在电脑前，所以新版 `.app` 的最终目录授权后启动尚未验证；新版代码已通过当前已授权终端中的真实摄像头、实际窗口及全部新增功能测试。

当前推荐的已验证启动命令：

```bash
./start.sh --foreground
```

## 形状与设置验证

新增直线、矩形、椭圆工具；实时预览、抬笔确认和取消；普通 PNG 黑/白背景；本地设置保存与恢复。

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 形状与配置实际窗口 | 两次打开窗口，预览未修改原画布、确认/取消/撤销/重做、白底及透明保存、配置恢复均通过 | `test-output/shapes_integration.json` |
| 食指 → 形状 | 真实 MediaPipe 模型运行 26 帧，其中 18 帧识别手部；成功预览并确认三种形状 | `test-output/hand_shapes_integration.json` |
| 新版真实摄像头 | 5 秒、81 帧，正常退出；无人举手，未验证真人形状操作体验 | `test-output/live_window_v3.json` |
| 原功能回归 | 鼠标绘画、擦除、重做及原手部识别窗口测试仍通过 | `test-output/mouse_integration.json`、`test-output/ui_integration.json` |
| 配置异常 | 无文件、损坏 JSON、无效类型/值恢复默认；写入失败保留旧配置并清理临时文件 | `tests/test_shapes_preferences.py` |
| 白底边缘 | 普通 PNG 背景为白色，抗锯齿边缘无黑边；不改变透明 PNG | `tests/test_shapes_preferences.py` |

本次未修改原生启动器，沿用已验证的前台启动方式。个人配置未被自动化测试覆盖；窗口测试使用独立临时配置或 `--no-settings`。

## 捏合抓取、拖动与释放验证

日期：2026-10-11。先读取三个指定参考仓库实际代码及 MIT 许可证，再在现有架构中接入独立对象层和手势状态机；源码提交与复用说明见 [DRAG_IMPLEMENTATION.md](DRAG_IMPLEMENTATION.md)。没有增加依赖、模型实例或云端 API。

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 单元测试与原功能回归 | 42 项通过，包含原有 29 项和新增 13 项 | `tests/test_drag.py`、`tests/test_painter.py`、`tests/test_shapes_preferences.py` |
| 五角星绘制及右移 | 在生产应用主循环、真实窗口中用食指输入绘制，捏合右移后原始颜色/Alpha 像素完全相同 | `test-output/drag_integration.json`、`test-output/drag-paintings/01_star_drawn.png`、`02_star_released_right.png` |
| 圆形独立移动 | 用食指输入绘制圆形并移动，五角星对象位置及像素保持不变 | `test-output/drag-paintings/03_circle_drawn.png`、`04_circle_moved_star_unchanged.png` |
| 释放、再次抓取、无尾线 | 释放后画布不变；再次抓取同一五角星，最终只有两个对象，无拖动路径笔迹 | `test-output/drag-paintings/05_star_regrabbed.png`、`tests/test_drag.py` |
| 滞回与短暂防抖 | 阈值附近短暂闭合不抓取、不绘画；拖动中松开阈值附近抖动不释放 | `tests/test_drag.py`、169 帧实际窗口验收 |
| 手部丢失及突跳 | 短暂丢失冻结并重设偏移；0.65 秒丢失安全释放，保持闭合不能自动重新抓取；突跳不瞬移 | `tests/test_drag.py` |
| 多笔、多色分组 | 多笔组成一个对象，完成后下一笔建立新对象，移动后红/蓝像素保持 | `tests/test_drag.py` |
| 命中、偏移、边界 | 空心中心及擦除洞不命中；重叠时只移动最上层；亚像素和工具栏边缘抓取不跳动 | `tests/test_drag.py` |
| 移动撤销/重做、透明导出 | 一次移动一个历史步骤；PNG 重新读取后与移动后的 RGBA 导出完全一致 | `test-output/drag_integration.json` |
| 原真实模型窗口回归 | 官方图片识别、绘画与控制 32 帧通过；食指形状预览/抬笔确认 26 帧通过 | `test-output/ui_integration.json`、`test-output/hand_shapes_integration.json` |
| 原鼠标及形状设置回归 | 鼠标绘画、擦除、透明保存、暂停；形状预览取消、白底保存、设置恢复均通过 | `test-output/mouse_integration.json`、`test-output/shapes_integration.json` |

捏合窗口验收使用合成 21 点手部关键点，并以受控时间覆盖防抖边界；窗口与应用循环真实执行，但没有真实摄像头输入或真实模型捏合输出。原有真实模型回归通过官方图片验证，不能替代真人在当前摄像头前的捏合体验。没有录制或保存用户摄像头画面，也未覆盖个人配置。

程序内已有画作的旧进程不会自动升级或转成新对象；先保存 PNG 并退出，再使用 `./start.sh --foreground` 加载新版。对象只在当前运行中保留，PNG 不包含可编辑对象结构。

## 退出操作修复

用户报告无法退出后，通过 SIGINT 正常结束正在运行的进程，日志确认“已退出”。尚未复现用户当时具体的鼠标或键盘操作，因此没有将问题归因于窗口死锁。

新增左下角 EXIT 按钮，直接设置退出请求，不依赖键盘焦点或输入法；保留 Q / Esc，补充 Ctrl+Q。收到启动器发送的 SIGTERM 时正常退出循环、结束拖动、保存设置并释放摄像头和模型；关闭窗口后的属性查询异常按窗口已关闭处理。

`scripts/test_exit_ui.py` 在四个实际 OpenCV 窗口中验证鼠标 EXIT、Ctrl+Q、SIGTERM 和窗口关闭，各在一帧后退出。摄像头和模型使用夹具；均验证释放/关闭、设置保存及信号处理器恢复，结果为 `test-output/exit_integration.json`。42 项单元测试再次通过。

## DONE / F 完成分组反馈修复

原实现的 DONE / F 只清除内部活动组编号，完成后无明显视觉确认；食指仍伸出时，下一帧又开始新笔画。现改为返回完成对象，显示绿色整组包围框、DONE 编号和 READY 提示，GROUP 显示当前笔画数；完成后先等待抬笔再允许新笔画，保持捏合拖动可立即使用。空组不再报告完成了对象。

`scripts/test_group_done_ui.py` 使用合成手部关键点驱动生产循环，分别通过 F 按键和 DONE 鼠标回调完成两笔红/蓝分组；两次实际窗口各 36 帧通过。验证了组计数归零、绿色框和提示、食指保持伸出不会继续落笔、直接捏合能移动两笔，以及抬笔后的新绘画建立另一个组。报告为 `test-output/group_done_integration.json`，完成截图为 `test-output/group-done/keyboard_f_done.png` 与 `mouse_done_done.png`。

43 项单元测试通过，169 帧独立图形拖动窗口回归也通过。自动化输入未验证实体键盘焦点或中文输入法，也不替代真人摄像头体验；当前正在运行的旧进程需要重启后加载修复，修复过程没有关闭它或改动其中的画作。

## 中文界面

窗口标题、按钮、颜色名称、手势/输入状态、操作提示、保存和错误提示、分组完成反馈均已改为中文。内部动作、设置键和快捷键保持原值，按钮命中坐标保持不变。

OpenCV 的原生文字接口不支持中文，改为 Pillow 使用本机 `Hiragino Sans GB` 字体生成抗锯齿文字遮罩，在 OpenCV 图像上只合成文字区域；缓存字体及文字遮罩。Pillow 12.3.0 已在原虚拟环境和 `requirements.lock.txt` 中，现明确加入 `requirements.txt` 供环境检查验证，无需下载字体。

已检查 `test-output/ui_preview.png` 和 `test-output/group-done/mouse_done_done.png`：中文正常显示，工具按钮、底部提示、分组确认及手部标签没有乱码或溢出。43 项单元测试、72 帧分组完成/整组移动窗口测试、21 帧鼠标绘画与透明保存、四种退出窗口测试通过；`doctor.py` 依赖检查通过。缓存预热后 100 次中文操作栏渲染平均约 0.99 ms/帧，此数字仅衡量操作栏，不包括摄像头和模型。

## 手指绘画粒子特效

日期：2026-10-12。复用项目已有的上游 `Particles` 结构，新增沿平滑食指轨迹发射、径向散开、亮芯与闪光、按秒渐隐；将每粒子复制全画面的旧绘制方式改为小区域合成。粒子上限严格为 180；抬笔、手部丢失和追踪突跳不会在笔画间补一段粒子轨迹。功能在本机执行，没有新增依赖。

48 项单元测试通过，新增 5 项覆盖容量、寿命、不同帧率发射、抬笔/突跳、散开渐隐和画布边界裁剪。50 帧实际窗口测试 `scripts/test_particles_ui.py` 使用合成 21 点手部输入，验证红/蓝火花随画笔变色、渐隐、每帧渲染不修改画布/Alpha，以及擦除、拖动、暂停、鼠标绘画不发射粒子。实际导出的 RGBA PNG 重新读取后与画布导出完全相同，特效不写入保存的画作。

结果在 `test-output/particles_integration.json`；预览截图为 `test-output/particles/red_sparks.png`、`blue_sparks.png`。两次分组完成/整组移动窗口回归各 36 帧通过。180 粒子的渲染在本机 30 次测试中平均约 4.78 ms/帧，仅测量粒子绘制，不代表整体摄像头或模型帧率。窗口粒子验收使用受控输入，尚未替代真人实际摄像头绘画体验。

## 暖色火星与原生标题修复

日期：2026-10-12。保留原彩色闪光，叠加较小的橙金色火星：向外飞散、短渐变拖尾、重力下落、由金黄冷却为橙红并渐隐。两类粒子共用 180 个的总容量限制，抬笔/突跳重置两类发射器，清空、拖动、擦除和暂停同时清理两类残留特效。

50 项单元测试通过，新增混合容量/清理和火星暖色拖尾/重力/寿命验证。更新后的 50 帧实际窗口测试确认两类粒子同时存在，且 RGBA PNG 仍不含预览特效，结果与截图沿用 `test-output/particles_integration.json` 和 `test-output/particles/`。

用户截图显示原生标题栏乱码，而画面内中文正常。复现表明 `cv2.setWindowTitle` 在当前 Cocoa 后端也会得到 `AI ÈöîÁ©∫ÁªòÁîª`。[OpenCV 4.11 Cocoa 源码](https://github.com/opencv/opencv/blob/4.11.0/modules/highgui/src/window_cocoa.mm) 使用 `NSString` 的 `%s` 格式处理窗口名。现将内部 OpenCV 句柄固定为 ASCII `Air Painter`，通过已安装的 PyObjC / AppKit 将可见原生标题设为 Unicode `AI 隔空绘画`，不改动窗口识别、鼠标回调和关闭逻辑。

已直接读取 macOS `NSWindow.title`，断言其精确等于 `AI 隔空绘画`，并验证 ASCII 句柄仍可查询窗口。四种实际窗口退出测试也全部通过，并在每个窗口中检查原生中文标题。之前的中文 QA 只覆盖画面内字体，本次补上标题栏验证。用户当前绘画进程未被关闭，需要保存画作并重启后加载两项更新。

## 单手时间操控与可逆花朵验证

以下为左右位移控制的初版记录；当前交互已按用户要求改为手指开合，见末尾“手指开合播放与移除进度条”。

日期：2026-10-12。新增 `GestureTimeController`、确定性的 `FlowerAnimation.render(progress, width, height)`、TIME / 花朵 / 归零按钮及 K / J / N 快捷键。摄像头、单手 MediaPipe Tasks VIDEO 推理和原生启动器沿用原架构，没有新增依赖、双手追踪、云端 API 或浏览器运行环境。

时间映射使用捏合起点进度与横向位移，复用原归一化捏合的 0.28 / 0.46 滞回、0.1 秒防抖及 EMA。进度限制在 0～1；松开、静止、上下移动保持进度。短暂丢失冻结并重新锚定，0.65 秒丢失安全释放。花朵用独立背景和 RGBA 花瓣图层，以进度计算各瓣的折叠角度、形状和色彩，不使用累积粒子模拟，支持随机访问及 1→0 回退。预览：[阶段图](test-output/time/flower_stages.png)、[半开界面](test-output/time/time_half.png)、[可逆动画 GIF](test-output/time/flower_reversible.gif)；GIF 为本地渲染展示，不是摄像头录制。

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 全部单元测试 | 70 项通过：原有 50 项、时间控制器 14 项、动画 5 项、重叠笔画像素保护 1 项 | `test-output/time-regression/00.log`、`tests/test_gesture_time.py`、`tests/test_flower_animation.py`、`tests/test_painter.py` |
| TIME 实际窗口集成 | 合成单手 111 帧，前进/倒退、保持/重抓、滞回/丢失、归零、键盘和鼠标切换全部通过；相机和模型工厂各调用一次，每帧仅推理一次 | `scripts/test_time_ui.py`、`test-output/time_integration.json` |
| TIME 与绘画隔离 | TIME 中原对象像素/Alpha/对象身份及撤销重做引用不变，不触发画线、拖对象或粒子；退出时保持捏合/食指伸出不生成尾线，抬笔后恢复绘画 | 同上 |
| 无摄像头时间轴 | 5 帧，鼠标 0→25→100→0、回到 DRAW，未申请权限或创建相机/模型 | 同上 |
| 环境与真实模型回归 | `doctor.py`、官方图片真实模型 21 帧 7 色、窗口真实模型绘画及食指形状均通过 | `test-output/time-regression/results.json`、`test-output/model_integration.json`、`test-output/ui_integration.json`、`test-output/hand_shapes_integration.json` |
| 原功能窗口回归 | 鼠标、形状/设置、对象拖动、粒子、分组完成及四种退出流程全部通过 | `test-output/time-regression/results.json` |
| 前台启动 | `start.sh --foreground --no-camera --no-settings --time-demo --smoke-seconds 1.5`，75 帧正常退出 | `test-output/time_startup.json` |
| 原生启动器 | `.app/Contents/MacOS/AirPainter` 同参数，76 帧正常退出；严格签名校验通过 | 同上、`test-output/time-regression/native_app_startup.log` |

全部 10 个集成脚本通过：`test_model.py`、`test_ui.py`、`test_mouse_ui.py`、`test_shapes_ui.py`、`test_hand_shapes.py`、`test_drag_ui.py`、`test_particles_ui.py`、`test_group_done_ui.py`、`test_exit_ui.py`、`test_time_ui.py`。启动验证在临时项目副本中执行，使用既有虚拟环境和模型，不覆盖个人设置、正式画作或应用日志。原生验证从终端执行已复制的启动器，不代表重新验证 Finder 的系统授权弹窗。

全量回归还发现原画布在重叠笔画抬笔后，少数抗锯齿边缘分量会改变 1～2，导致清屏撤销不能严格还原抬笔前像素。已在 `painter_core.py` 中让绘画中的局部区域和已完成对象使用相同的合成路径，保留原层级并只刷新笔迹附近区域。没有放宽旧测试；真实模型清屏还原测试和新增逐像素测试均通过。

自动化 TIME 测试使用合成关键点和受控时间；真实模型回归使用官方图片。**本次没有验证真人摄像头下的 TIME 手势识别率、实际操控延迟或遮挡体验**。没有关闭用户已有应用、录制用户摄像头画面或修改系统权限。运行中的旧窗口需先保存画作并退出，再启动新版。

人工验收步骤：

1. 正常启动，点击“开始”，画五角星和圆形，移动圆形确认五角星不动；建立一次可重做操作并记住原画布状态。
2. 按 J 或点击“花朵演示”。张开两指后捏合约 0.1 秒，缓慢右移至 25%、50%、75%、100%，再左移回 0%。花瓣应连续展开/合拢，进度不能越界。
3. 在中间进度保持手部静止 3 秒，再只上下移动；进度应保持。松手并换一个位置再次捏合，进度不应跳变；左右小幅抖动不应频繁抓取或释放。
4. 捏合拖动中遮挡手约 0.3 秒，恢复后进度应保持并从当前位置继续。遮挡超过 1 秒后应安全释放，仍捏合不能自动继续；张开再捏合应恢复。
5. 按 N 或点击“时间归零”，确认回到花苞；张开再捏合继续操作。在 TIME 中按 Z/Y/C/F、点击画布和工具按钮，应不改变原画布或对象。
6. 保持捏合或食指伸出时按 K 返回绘画，确认无新线条、图形不跟手移动，原对象和重做仍有效。先抬笔再伸食指绘画；验证分组、粒子和 PNG 导出仍正常。

当前时间进度与花朵只在本次运行中保留，花朵不纳入 PNG 画作导出；尚未实现其他演示场景。默认演示不自动播放，所有操作仍为单手。

## 手指开合播放与移除进度条

日期：2026-10-12。根据用户体验反馈，将 TIME 从捏合后左右位移改为拇指与食指的开合幅度控制：稳定捏合后回到花苞，逐渐张开同步展开，充分张开完成整个动画；合拢反向收回。保留单手、原摄像头、原 MediaPipe 实例和可逆花朵渲染。此次修改 `gesture_time.py`、`ai_virtual_painter.py`、`controls.py`、`ui_labels.py`、`tests/test_gesture_time.py`、`scripts/test_time_ui.py` 与使用文档；没有改动对象、粒子、依赖或原生启动器。

移除时间进度条、刻度、百分比、鼠标时间轴及其事件处理，花朵预览扩展到原时间轴区域。底部只保留开合提示与模式/回到花苞按钮。视觉检查 [半开界面](test-output/time/time_half.png) 通过，原时间轴点击和拖动不再改变动画。

复用手掌归一化的 landmark 4 / 8 间距及原捏合滞回/防抖。稳定捏合启动，间距比例 0.28→1.15 对应花苞→盛开，使用原 EMA 和 0.01 间距变化过滤；左右/上下平移与手掌尺寸变化不推进动画。捏合释放不停止展开。充分张开稳定 0.1 秒后精确达到 1，避免平滑残差让花朵停在未完成状态。短暂丢失冻结、恢复首帧保持；0.65 秒丢失安全停止，先张开再捏合恢复。动画跟随开合幅度，不使用独立定时自动播放。

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 单元测试 | 72 项通过，保留原 50 项；开合控制 16 项、动画 5 项、像素保护 1 项 | `tests/test_gesture_time.py`、`test-output/aperture-regression/results.json` |
| TIME 实际窗口 | 107 帧合成单手输入，完整开合播放、反向访问、平移不推进、抖动/丢失、模式切换、原对象和撤销重做保护通过；摄像头和模型各创建一次 | `test-output/time_integration.json` |
| 无摄像头实际窗口 | 5 帧，旧时间轴位置点击/拖动无效、归零及返回绘画通过；零摄像头/模型实例 | 同上 |
| 环境与原功能回归 | doctor 和全部 10 个集成脚本通过，包括真实模型官方图片、鼠标、形状、拖动、粒子、分组及退出 | `test-output/aperture-regression/results.json` 和同目录日志 |
| 前台与原生启动 | 临时项目副本无摄像头演示分别 85 / 86 帧，正常结束；原生签名校验通过 | `test-output/aperture-regression/startup.json` |

当前已有窗口保持运行，未自动重启或清空其中可能未保存的画作。需先保存并退出旧窗口，再打开新版。此次摄像头手势验收仍使用合成关键点，未声称通过真人开合体验；充分张开阈值的适用性需要真人验证。旧版 GIF 与初版测试描述保留为历史记录，当前 UI 以本节截图为准。

人工验收：

1. 按 J 进入花朵演示，拇指和食指捏合保持约 0.1 秒，确认花苞；缓慢张开到最大舒适幅度，确认完整盛开，再合拢回到花苞。
2. 保持半开手势，左右、上下移动和改变手与摄像头的距离，花朵应基本保持；在捏合释放阈值附近小幅抖动，不应反复重置或停止展开。
3. 短暂遮挡约 0.3 秒，恢复首帧保持；遮挡超过 1 秒后安全停止，张开再捏合恢复。按 N 回到花苞，再次捏合并展开。
4. 点击原时间轴区域应无作用；按 K 返回绘画时没有多余线条，抬笔后恢复绘画，原对象、分组、撤销重做、粒子和导出仍正常。
