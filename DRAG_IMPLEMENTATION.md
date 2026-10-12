# 捏合抓取实现与源码审计

日期：2026-10-11。在现有 Mac 项目上增加功能；保留 MediaPipe Tasks、摄像头封装、OpenCV 窗口、绘画工具、导出、历史和设置。

## 先读实际源码

三个仓库均通过浅克隆读取实际 Python 文件及许可证，核对的提交如下。

| 项目与源码 | 提交 | 实际算法与本次采用方式 |
| --- | --- | --- |
| [Hand-Gesture-Drag-Drop / main.py](https://github.com/naakaarafr/Hand-Gesture-Drag-Drop/blob/99d708f7aebf080b6cf5a3b2d71cdcd44e04411b/main.py) | `99d708f7aebf080b6cf5a3b2d71cdcd44e04411b` | 使用 landmark 8 / 12 的固定像素距离，包围盒内直接将矩形中心赋值为食指位置；借鉴包围盒初筛，未直接复制其主循环。 |
| [Gesture-Controlled-Virtual-Puzzle-Game / main.py](https://github.com/ahsinmemon/Gesture-Controlled-Virtual-Puzzle-Game-using-OpenCV-MediaPipe/blob/0ba0524b427be09e2c8c020c25a95f0ab725578b/main.py) | `0ba0524b427be09e2c8c020c25a95f0ab725578b` | 使用 landmark 8 / 12、固定距离 30，拼图对象列表及矩形范围检测；借鉴独立对象列表，未引入 cvzone、拼图图像或窗口实现。 |
| [air-canvas / geometry.py](https://github.com/medhanshcodezz/air-canvas/blob/fb72f58ea9bf98c8e243352cd3ca088764cbd833/aircanvas/geometry.py)、[render.py](https://github.com/medhanshcodezz/air-canvas/blob/fb72f58ea9bf98c8e243352cd3ca088764cbd833/aircanvas/render.py)、[hand.py](https://github.com/medhanshcodezz/air-canvas/blob/fb72f58ea9bf98c8e243352cd3ca088764cbd833/aircanvas/hand.py) | `fb72f58ea9bf98c8e243352cd3ca088764cbd833` | 独立图形、连续笔迹提交、点到线段的夹紧投影及图形距离检测；复用并改编 `segment_distances`，用于可见笔迹轮廓命中。 |

前两个示例没有手掌归一化、滞回、防抖、抓取点偏移或追踪丢失保护，因此不能原样满足本次要求。第三个项目使用旧版 MediaPipe Hands 和向量渲染；本项目继续保留已验证的 Tasks API 与像素橡皮擦，只复用适合的几何和对象管理方法。

复制改编的距离函数在 `drawing_objects.py` 标明来源，原 MIT 许可证保留在 `third_party/air-canvas-LICENSE`。参考仓库没有作为运行时依赖安装。

## 最小架构改动

- `drawing_objects.py`：裁剪后的独立颜色/Alpha 位图、只读像素、整数平移、包围盒及轮廓距离命中、source-over 合成。
- `painter_core.py`：继续维护现有 `canvas` / `alpha` 接口；绘画时记录当前对象层，抬笔后提交。历史同时保存对象及画布；橡皮擦修改命中区域的对象像素，移动后可显示原先被遮住的其他对象。
- `hand_interaction.py`：从现有 21 个关键点计算捏合并驱动 DRAW / IDLE / DRAG。未增加模型实例。
- `ai_virtual_painter.py`：在原手部输入位置接入状态机，其他输入、窗口、保存、退出路径继续复用。
- `controls.py`：利用原工具栏空隙增加 GROUP / DONE，保留旧按钮坐标；显示对象数量、DRAG 状态和抓取包围框。

保留原色板、笔宽、EMA、工具、鼠标模式、30 步历史、设置格式和原生启动器。分组默认关闭，可通过 G / F 或按钮组成多笔对象；捏合开始会完成当前分组。

## 手势参数与安全行为

捏合比例为 `distance(4, 8) / max(distance(0, 9), distance(5, 17))`，在像素坐标中计算，避免画面宽高比影响距离。手掌小于 12 像素时暂停输入。

| 参数 | 默认值 / 行为 |
| --- | --- |
| 闭合阈值 | 比例 ≤ 0.28 |
| 松开阈值 | 比例 ≥ 0.46 |
| 防抖 | 连续维持约 0.10 秒，闭合和松开分别计时 |
| 接近捏合 | 闭合候选出现即抬笔；比例在两阈值之间抖动时继续抬笔 |
| 抓取点 | 4 / 8 中点；记录对象原点与平滑后抓取点的偏移 |
| 命中 | 包围盒扩大 18 像素后初筛，再检验可见 Alpha 或到笔迹轮廓的距离；识别空心区域及擦除洞 |
| 层级 | 从最上层开始，单次捏合只锁定一个对象；移动保持原层级 |
| 追踪丢失 | 冻结；短暂恢复时重新设置偏移；≥ 0.65 秒释放，张开后才允许重新抓取 |
| 坐标突跳 | 单帧 > 150 像素重新设置偏移，避免瞬移 |
| 释放后绘画 | 先观察到张掌或两指抬笔，再允许食指绘画，防止释放尾线 |
| 历史 | 拖动期间不写每帧历史，释放后实际移动计一步；空抓不计步 |

移动使用现有 EMA 系数，只平移位图原点，不做像素重采样。边界限制不把已跨工具栏边缘的笔迹在抓取瞬间推走。

## 验证与边界

42 项单元测试通过，其中原有 29 项、新增 13 项。新增单元测试覆盖六个验收场景，以及多色分组、空心/擦除洞命中、重叠对象、偏移、边界、亚像素抓取、追踪丢失、暂停、历史和导出。

实际窗口验收通过 `scripts/test_drag_ui.py` 执行生产主循环，使用合成 21 点输入绘制五角星和圆形、分别移动、释放、再次抓取、防抖及导出。结果在 `test-output/drag_integration.json`，阶段 PNG 在 `test-output/drag-paintings/`。真实模型回归使用已有官方图片测试脚本；真人捏合和不同光线、遮挡下的体验尚未验收。

对象保留在本次运行内，PNG 不保存可编辑对象结构。没有增加项目文件格式、图片导入、鼠标移动工具、自动几何识别或云端调用。
