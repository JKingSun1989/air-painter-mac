# 发布前验证

环境：Apple M1 Pro / ARM64、macOS 27.0、Python 3.11.15。未全面验证 Intel Mac、macOS 13 和 Python 3.12；macOS 13+ 是启动器声明的最低系统版本。

原有 78 项单元测试已在 macOS 本机和 Windows Actions（Python 3.11/3.12）通过。2026-10-13 在 64 位 Windows 11 / Python 3.11.9 下，加入 4 项 Windows 启动器回归测试后，共 82 项通过；回归测试覆盖含空格及中文的项目路径、参数传递、退出状态、诊断失败阻止启动，以及中文 Windows PowerShell 的脚本编码读取。Windows Actions 增加 PowerShell 5.1 / 7 语法检查矩阵，新提交的远程结果以 Actions 为准。

本机 USB 摄像头检查成功读取 30 帧（640×480），并完成本地 MediaPipe 推理。生产窗口连续启动测试正常结束，其中一次 99 帧中有 1 帧识别到单手；该结果只证明摄像头、模型和窗口链路可运行，不表示全部真人绘画/拖动/TIME 手势或识别率已经验收。测试报告仅保留统计，不上传摄像头画面。

10 个集成脚本通过：`test_model.py`、`test_ui.py`、`test_mouse_ui.py`、`test_shapes_ui.py`、`test_hand_shapes.py`、`test_drag_ui.py`、`test_particles_ui.py`、`test_group_done_ui.py`、`test_exit_ui.py`、`test_time_ui.py`，另有 `doctor.py` 环境检查。

TIME 在实际 OpenCV 窗口和生产循环中执行 107 帧合成单手输入，验证捏合到完全张开、合拢倒放、平移不推进、短暂丢失冻结、长时间丢失安全停止、归零、模式切换，以及原对象、粒子和撤销重做隔离。相机和模型工厂各调用一次；另有 5 帧无摄像头测试验证旧进度条点击无效、归零与回到绘画。

前台脚本与原生 `.app` 启动器在临时目录中用无摄像头 TIME 演示验证通过，严格签名校验通过。真实模型测试使用官方手部图片；没有把真人摄像头开合体验或不同光线下识别率记为自动化通过。

截图 [半开放](images/flower-half.png)、[完全盛开](images/flower-bloom.png) 为本地合成输入的测试产物，已移除时间进度条和百分比。

## 复测

完成 `./setup.sh` 后运行：

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/test_time_ui.py
.venv/bin/python scripts/test_drag_ui.py
.venv/bin/python scripts/test_particles_ui.py
```

窗口脚本需要已登录的 macOS 图形会话。`test_model.py`、`test_ui.py`、`test_hand_shapes.py` 还需要按根目录 README 下载官方测试图片。

历史开发记录见 [TEST_REPORT.md](../TEST_REPORT.md)。其中 `test-output/` 日志和截图可通过测试生成，不随源码包分发；历史记录包含已替换的左右位移版本，当前 TIME 以开合手势为准。

## 真人验收

1. 按 J 进入 TIME，捏合约 0.1 秒，慢慢张开至完整盛开，再合拢回花苞。
2. 半开手势保持不变，左右、上下移动并改变与摄像头的距离，花朵应基本保持；小幅抖动不应反复重置。
3. 遮挡约 0.3 秒，恢复第一帧不跳变；遮挡超过 1 秒后安全停止，张开再捏合恢复。
4. 按 N 回到花苞，按 K 回到绘画；没有额外线条，抬笔后继续绘画。
5. 分别绘制、移动两个对象，验证互不影响；验证分组、撤销重做、粒子和 PNG 导出。

退出前保存 PNG；对象工程不会跨运行自动恢复。
