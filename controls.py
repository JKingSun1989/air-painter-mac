"""Mouse and two-finger dwell controls, rendered with OpenCV."""
import cv2
from config import FRAME_W, FRAME_H, TOPBAR_H, SIDEBAR_W, PALETTE
from chinese_text import draw_text as text
from ui_labels import TOOL_NAMES, INPUT_NAMES, MODE_NAMES, COLOR_NAMES

BUTTONS = [("start", "开始", 270, 370), ("stop", "暂停", 380, 480),
           ("undo", "撤销", 490, 590), ("clear", "清空", 600, 700),
           ("save", "保存 PNG", 710, 840), ("redo", "重做", 850, 950),
           ("transparent", "透明 PNG", 960, 1090)]
TOOL_BUTTONS = [("tool:pen", "画笔 [P]", 270, 355), ("tool:line", "直线 [L]", 365, 450),
                ("tool:rectangle", "矩形 [R]", 460, 545), ("tool:ellipse", "椭圆 [O]", 555, 650),
                ("smooth", "平滑", 660, 770), ("background", "背景", 780, 900),
                ("input", "输入", 910, 1000)]
MODE_BUTTONS = [("time", "时间 TIME [K]", 132, 280),
                ("flower", "花朵演示 [J]", 290, 438),
                ("time_reset", "回到花苞 [N]", 448, 596)]


def hit_test(x, y):
    if 671 <= y < 696:
        for action, _, x1, x2 in MODE_BUTTONS:
            if x1 <= x < x2:
                return action
    if 6 <= y < 39:
        for action, _, x1, x2 in TOOL_BUTTONS:
            if x1 <= x < x2:
                return action
    if 48 <= y < 88:
        for action, _, x1, x2 in BUTTONS:
            if x1 <= x < x2:
                return action
    if 12 <= x < SIDEBAR_W - 12 and TOPBAR_H <= y < TOPBAR_H + len(PALETTE) * 72:
        return "color:" + str(int((y - TOPBAR_H) // 72))
    if 12 <= x < SIDEBAR_W - 12 and 614 <= y < 654:
        return "eraser"
    if 12 <= x < SIDEBAR_W - 12 and 666 <= y < 710:
        return "quit"
    if 125 <= x < 260 and 6 <= y < 39:
        return "group"
    if 125 <= x < 260 and 48 <= y < 88:
        return "finish"
    return None


def render_time_panel(frame, state):
    hint = "暂时丢失手部，花朵保持当前状态" if state.state == "TIME_LOST" else "捏合是花苞，逐渐张开手指让花朵盛开"
    text(frame, hint, (145, FRAME_H-68), .48, (65, 100, 72), max_width=930)


class DwellControl:
    def __init__(self, seconds=0.7):
        self.seconds = seconds
        self.reset()

    def reset(self):
        self.target = None
        self.started = 0
        self.fired = False

    def update(self, target, now):
        if target != self.target:
            self.target, self.started, self.fired = target, now, False
        if target and not self.fired and now - self.started >= self.seconds:
            self.fired = True
            return target
        return None

    def progress(self, now):
        return min(1.0, max(0.0, (now - self.started) / self.seconds)) if self.target else 0


def render_controls(frame, engine, fps, mode, message, input_mode="hand", completed_id=None,
                    application_mode="DRAW", time_state=None):
    time_mode = application_mode == "TIME"
    cv2.rectangle(frame, (0, 0), (FRAME_W, TOPBAR_H), (24, 24, 30), -1)
    text(frame, "隔空绘画", (18, 30), 0.55)
    # Use the existing gap before the tool buttons, without moving old targets.
    cv2.rectangle(frame, (125, 6), (260, 39), (65, 100, 45) if engine.group_mode else (55, 55, 65), -1)
    text(frame, f"分组：{engine.group_strokes} 笔" if engine.group_mode else "分组：关 [G]", (133, 28), 0.47, max_width=120)
    cv2.rectangle(frame, (125, 48), (260, 88), (65, 100, 45) if completed_id is not None else (55, 55, 65), -1)
    text(frame, f"已完成 #{completed_id}" if completed_id is not None else "完成 [F]", (135, 74), 0.48, max_width=115)
    for action, label, x1, x2 in TOOL_BUTTONS:
        active = not time_mode and action == "tool:" + engine.tool
        if action == "smooth":
            label = f"平滑 {engine.smoother.alpha:.2f}"
        elif action == "background":
            label = "背景：" + ("白" if engine.export_background == "white" else "黑")
        elif action == "input":
            label = INPUT_NAMES[input_mode] + " [M]"
        cv2.rectangle(frame, (x1, 6), (x2, 39), (65, 100, 45) if active else (55, 55, 65), -1)
        text(frame, label, (x1 + 8, 28), 0.47, (115, 115, 125) if time_mode else (230, 230, 230), max_width=x2-x1-16)
    text(frame, f"{fps:.0f} 帧/秒", (1010, 28), 0.45, max_width=85)
    for action, label, x1, x2 in BUTTONS:
        active = not time_mode and ((action == "start" and engine.enabled) or (action == "stop" and not engine.enabled))
        cv2.rectangle(frame, (x1, 48), (x2, 88), (65, 100, 45) if active else (55, 55, 65), -1)
        text(frame, label, (x1 + 14, 74), 0.5, (115, 115, 125) if time_mode else (230, 230, 230), max_width=x2-x1-28)
    text(frame, "TIME 模式" if time_mode else "已开始" if engine.enabled else "已暂停", (18, 74), 0.55,
         (110, 230, 110) if time_mode or engine.enabled else (180, 180, 180))
    cv2.rectangle(frame, (0, TOPBAR_H), (SIDEBAR_W, FRAME_H), (24, 24, 30), -1)
    for i, item in enumerate(PALETTE):
        y = TOPBAR_H + i * 72
        cv2.rectangle(frame, (12, y + 6), (SIDEBAR_W - 12, y + 64), item["bgr"], -1)
        if engine.color_idx == i and engine.tool != "eraser":
            cv2.rectangle(frame, (9, y + 3), (SIDEBAR_W - 9, y + 67), (255, 255, 255), 2)
        text(frame, f"{i + 1} {COLOR_NAMES[item['name']]}", (20, y + 43), 0.48, (35, 35, 35) if i >= 3 else (255, 255, 255))
    cv2.rectangle(frame, (12, 614), (SIDEBAR_W - 12, 654),
                  (65, 100, 45) if engine.tool == "eraser" else (55, 55, 65), -1)
    text(frame, "橡皮擦 [E]", (20, 640), 0.47, max_width=82)
    cv2.rectangle(frame, (12, 666), (SIDEBAR_W - 12, 710), (55, 55, 110), -1)
    text(frame, "退出 [Q]", (22, 694), 0.5, max_width=80)
    cv2.rectangle(frame, (SIDEBAR_W, FRAME_H - 54), (FRAME_W, FRAME_H), (24, 24, 30), -1)
    for action, label, x1, x2 in MODE_BUTTONS:
        if action == "time" and time_mode:
            label = "返回绘画 [K]"
        active = time_mode and action == "time"
        cv2.rectangle(frame, (x1, 671), (x2, 696), (65, 100, 45) if active else (55, 55, 65), -1)
        text(frame, label, (x1+8, 690), .43,
             (115, 115, 125) if action == "time_reset" and not time_mode else (230, 230, 230), max_width=x2-x1-16)
    text(frame, "捏合 → 张开盛开 | 合拢收回 | Q 退出" if time_mode else "捏合拖动 | 空格暂停 | S/T 保存 | Q 退出",
         (610, FRAME_H - 32), .4, max_width=475)
    status = f"TIME / {MODE_NAMES.get(mode, mode)} | K 返回绘画，N 回到花苞" if time_mode else f"{INPUT_NAMES[input_mode]} / {MODE_NAMES.get(mode, mode)} | {TOOL_NAMES[engine.tool]}：{engine.brush_width} 像素 | 对象：{len(engine.objects)} | 平滑：{engine.smoother.alpha:.2f} | 撤销：{len(engine.history)} / 重做：{len(engine.redo_history)} | +/- 笔宽，[/] 平滑"
    text(frame, message or status,
         (SIDEBAR_W + 12, FRAME_H - 10), 0.43, max_width=FRAME_W-SIDEBAR_W-24)
    if completed_id is not None:
        cv2.rectangle(frame, (270, TOPBAR_H + 8), (830, TOPBAR_H + 48), (30, 65, 30), -1)
        text(frame, f"对象 #{completed_id} 已完成，捏合笔迹即可拖动", (285, TOPBAR_H + 35), 0.6, (140, 255, 140), max_width=530)
