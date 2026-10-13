"""Desktop adaptation of moizaiqbal40-ops/ai_virtual_painter (MIT).
Reuses upstream MediaPipe Tasks loop, configuration, gesture geometry,
skeleton UI, palette and EMA drawing; adds explicit controls/history.
Original source and copyright are retained in upstream/ and LICENSE.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time
import signal

# Keep dependency caches inside the project, including on sandboxed launches.
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".cache/matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(Path(__file__).resolve().parent / ".cache"))

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

from config import FRAME_W, FRAME_H, SIDEBAR_W, TOPBAR_H, MODEL_PATH, PALETTE, MIN_BRUSH, MAX_BRUSH
from hand_utils import fingers_up, thumb_extended, classify_gesture
from ui import draw_skeleton, draw_hand_badge
from painter_core import PaintEngine
from hand_interaction import HandInteraction, pinch_measurement, PINCH_OPEN
from gesture_time import GestureTimeController
from flower_animation import FlowerAnimation
from controls import DwellControl, hit_test, render_controls, render_time_panel
from camera import require_camera_permission, open_camera
from preferences import DEFAULT_PATH, DEFAULTS, load_preferences, save_preferences
from ui_labels import TOOL_NAMES, INPUT_NAMES, COLOR_NAMES
from particles import Particles
from window import create_window

WINDOW = "Air Painter"
WINDOW_TITLE = "AI 隔空绘画"


def create_landmarker():
    if not Path(MODEL_PATH).is_file():
        raise RuntimeError("缺少本地手部模型，请运行 setup.sh（macOS）或 setup.ps1（Windows）。")
    options = mp_vision.HandLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH,
                                           delegate=mp_python.BaseOptions.Delegate.CPU),
        running_mode=mp_vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.6,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    return mp_vision.HandLandmarker.create_from_options(options)


def main():
    parser = argparse.ArgumentParser(description="本地 AI 隔空绘画")
    parser.add_argument("--camera", type=int, default=0, help="摄像头编号，默认 0")
    parser.add_argument("--smoothing", type=float, default=None, help="EMA 系数 (0,1]，覆盖保存的平滑设置")
    parser.add_argument("--smoke-seconds", type=float, default=0, help="自动结束，用于实际摄像头/窗口测试")
    parser.add_argument("--report", type=Path, help="保存测试统计；不保存摄像头画面")
    parser.add_argument("--no-camera", action="store_true", help="无需摄像头，以鼠标绘画")
    parser.add_argument("--settings", type=Path, default=DEFAULT_PATH, help="本地设置文件")
    parser.add_argument("--no-settings", action="store_true", help="不读取或保存设置，用于独立测试")
    parser.add_argument("--time-demo", action="store_true", help="启动后进入花朵时间演示")
    args = parser.parse_args()
    if args.smoothing is not None and not 0 < args.smoothing <= 1:
        parser.error("--smoothing 必须在 (0, 1] 内")
    preferences = DEFAULTS.copy() if args.no_settings else load_preferences(args.settings)
    smoothing = preferences["smoothing"] if args.smoothing is None else args.smoothing
    engine = PaintEngine(FRAME_W, FRAME_H, smoothing)
    engine.thickness = preferences["thickness"]
    engine.select_color(preferences["color_idx"])
    engine.set_tool(preferences["tool"])
    engine.export_background = preferences["export_background"]
    dwell = DwellControl()
    interaction = HandInteraction(engine, (SIDEBAR_W + 1, TOPBAR_H + 1, FRAME_W, FRAME_H - 54))
    particles = Particles()
    time_controller = GestureTimeController(smoothing=smoothing)
    flower = FlowerAnimation()
    application_mode = "DRAW"
    last_hand_points = None
    cap = landmarker = None
    frames = detected_frames = max_hands = 0
    started = time.monotonic()
    message, message_until = "点击“开始”或按空格，开始绘画", started + 5
    show_skeleton = preferences["show_skeleton"]
    mouse_actions = []
    mouse_held = False
    input_mode = "mouse" if args.no_camera else preferences["input_mode"]
    exit_reason = "quit"
    exit_requested = False
    completed_id, completed_until = None, 0.0

    def request_exit(signum, frame):
        nonlocal exit_requested, exit_reason
        exit_requested = True
        exit_reason = "termination_requested"

    def perform(action):
        nonlocal message, message_until, input_mode, mouse_held, exit_requested, exit_reason
        nonlocal completed_id, completed_until
        nonlocal application_mode
        if action in ("time", "flower"):
            target = "TIME" if action == "flower" or application_mode != "TIME" else "DRAW"
            ratio = pinch_measurement(last_hand_points)[0] if last_hand_points is not None else None
            held_pinch = ratio is not None and ratio < PINCH_OPEN
            interaction.reset(commit=False)
            # Cancel unconfirmed shapes, commit only already-drawn pen pixels.
            # No draw/undo/clear command is dispatched by a mode transition.
            engine.cancel_preview()
            interaction.block_draw = True
            interaction.require_open = held_pinch
            mouse_held = False
            particles.clear()
            completed_until = 0
            if target == "TIME":
                time_controller.smoother.alpha = engine.smoother.alpha
                time_controller.enter()
                message = "花朵演示：捏合是花苞，张开手指让花朵盛开"
            else:
                time_controller.release(require_open=held_pinch)
                message = "已返回绘画，先张掌或伸出两指抬笔，再继续绘画"
            application_mode = target
            dwell.reset()
            message_until = time.monotonic() + 4
            return
        if application_mode == "TIME":
            if action == "time_reset":
                time_controller.reset()
                message = "已回到花苞，捏合后逐渐张开手指"
            elif action == "quit":
                exit_requested = True
                exit_reason = "exit_button"
            else:
                message = "当前是 TIME 模式，按 K 返回绘画后使用绘画工具"
            message_until = time.monotonic() + 3
            return
        if action == "time_reset":
            message = "请先点击“时间”或“花朵演示”"
            message_until = time.monotonic() + 3
            return
        interaction.reset(commit=action != "cancel")
        particles.clear()
        if action == "cancel":
            engine.cancel_preview()
        else:
            engine.lift()
        mouse_held = False
        if action == "quit":
            exit_requested = True
            exit_reason = "exit_button"
        elif action == "start":
            engine.set_enabled(True)
            message = "已开始，可以绘画或捏合拖动"
        elif action == "stop":
            engine.set_enabled(False)
            message = "已暂停，点击“开始”或按空格继续"
        elif action == "undo":
            message = "已撤销上一操作" if engine.undo() else "没有可撤销的操作"
        elif action == "redo":
            message = "已重做上一操作" if engine.redo() else "没有可重做的操作"
        elif action == "eraser":
            engine.set_tool("pen" if engine.tool == "eraser" else "eraser")
            message = f"工具：{TOOL_NAMES[engine.tool]}"
        elif action.startswith("tool:"):
            engine.set_tool(action.split(":", 1)[1])
            message = f"工具：{TOOL_NAMES[engine.tool]}" + ("，拖动画出后抬笔确认" if engine.tool != "pen" else "")
        elif action == "cancel":
            message = "已取消形状预览"
        elif action == "group":
            engine.set_group_mode(not engine.group_mode)
            message = "已开启分组：多笔组成一个对象，按 F 完成" if engine.group_mode else "已关闭分组：每次抬笔生成独立对象"
        elif action == "finish":
            strokes = engine.group_strokes
            completed = engine.finish_object()
            completed_id = completed.id if completed is not None else None
            completed_until = time.monotonic() + 4 if completed is not None else 0
            if completed is None:
                message = "没有待完成的分组，请先开启“分组”并绘画，再点击“完成”"
                print("没有待完成的分组：请先开启 GROUP 并绘画。", flush=True)
            else:
                interaction.block_draw = True
                message = f"对象 #{completed.id} 已完成，共 {strokes} 笔。捏合即可移动，先抬笔再绘画" if engine.group_mode else f"对象 #{completed.id} 已完成，捏合即可移动；组合多笔请先开启“分组”"
                print(f"已完成对象 #{completed.id}" + (f"，包含 {strokes} 笔。" if engine.group_mode else "；当前 GROUP 未开启，多笔分组需在绘画前开启。"), flush=True)
        elif action == "smooth":
            values = (0.2, 0.35, 0.45, 0.65, 1.0)
            value = next((value for value in values if value > engine.smoother.alpha + 0.001), values[0])
            engine.set_smoothing(value)
            message = f"平滑系数：{value:.2f}，数值越小越平滑"
        elif action == "background":
            engine.export_background = "white" if engine.export_background == "black" else "black"
            message = "PNG 背景：" + ("白色" if engine.export_background == "white" else "黑色") + "，不影响透明导出"
        elif action == "input":
            input_mode = "hand" if input_mode == "mouse" and not args.no_camera else "mouse"
            message = f"输入方式：{INPUT_NAMES[input_mode]}"
        elif action == "clear":
            engine.clear()
            message = "已清空画布，可以撤销恢复"
        elif action in ("save", "transparent"):
            try:
                filename = engine.save(transparent=action == "transparent")
                print(f"已保存：{filename}", flush=True)
                message = f"已保存：{filename.name}"
            except OSError as exc:
                message = "保存失败，请检查文件夹权限和剩余磁盘空间"
                print(exc, file=sys.stderr, flush=True)
        elif action.startswith("color:"):
            engine.select_color(int(action.split(":")[1]))
            message = f"颜色：{COLOR_NAMES[PALETTE[engine.color_idx]['name']]}"
        message_until = time.monotonic() + 3

    def mouse(event, x, y, flags, param):
        nonlocal exit_requested, exit_reason
        if event == cv2.EVENT_LBUTTONDOWN:
            target = hit_test(x, y)
            if target == "quit":
                exit_requested = True
                exit_reason = "exit_button"
            elif target:
                mouse_actions.append(target)
            elif application_mode == "DRAW" and input_mode == "mouse":
                mouse_actions.append((event, x, y))
        elif application_mode == "DRAW" and input_mode == "mouse" and event in (cv2.EVENT_MOUSEMOVE, cv2.EVENT_LBUTTONUP):
            mouse_actions.append((event, x, y))

    if args.time_demo:
        perform("flower")
    previous_sigterm = signal.signal(signal.SIGTERM, request_exit)
    try:
        if not args.no_camera:
            require_camera_permission()
            landmarker = create_landmarker()
            cap = open_camera(args.camera)
        create_window(WINDOW, WINDOW_TITLE)
        cv2.setMouseCallback(WINDOW, mouse)
        print("隔空绘画已启动。空格：开始/暂停；Z：撤销；C：清空；S：保存；退出按钮 / Q / Esc：退出。", flush=True)
        started = previous_time = time.monotonic()
        particle_time = started
        last_timestamp = -1
        previous_label = None
        failed_reads = 0
        while True:
            # Consume a mode-button click before interpreting the next hand
            # frame, so the click cannot cause one last unintended paint stroke.
            while mouse_actions and isinstance(mouse_actions[0], str) and mouse_actions[0] in ("time", "flower"):
                perform(mouse_actions.pop(0))
            if exit_requested:
                break
            preview_background = 255 if engine.export_background == "white" else 45
            ok, frame = cap.read() if cap is not None else (True, np.full((FRAME_H, FRAME_W, 3), preview_background, np.uint8))
            if not ok or frame is None:
                failed_reads += 1
                if application_mode == "TIME":
                    time_controller.update(None, None, "TIME", time.monotonic())
                else:
                    engine.lift()
                particles.reset_emitter()
                if application_mode == "DRAW" and input_mode == "hand":
                    interaction.update(None, time.monotonic())
                dwell.reset()
                if failed_reads >= 15:
                    raise RuntimeError("摄像头连续读取失败。请重新连接摄像头，或关闭其他摄像头应用。")
                if cv2.waitKey(50) & 0xFF in (ord("q"), ord("Q"), 17, 27):
                    exit_reason = "quit"
                    break
                continue
            failed_reads = 0
            frame = cv2.resize(cv2.flip(frame, 1), (FRAME_W, FRAME_H))
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            now = time.monotonic()
            particle_dt = now - particle_time
            particle_time = now
            particles.update(particle_dt)
            timestamp = max(last_timestamp + 1, int((now - started) * 1000))
            last_timestamp = timestamp
            result = landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp) if landmarker is not None else None
            frames += 1
            landmarks = result.hand_landmarks if result is not None else []
            last_hand_points = None
            max_hands = max(max_hands, len(landmarks))
            detected_frames += bool(landmarks)
            mode = "No hand"
            cursor = None
            if landmarks:
                landmarks_px = [(int(lm.x * FRAME_W), int(lm.y * FRAME_H)) for lm in landmarks[0]]
                label = result.handedness[0][0].category_name if result.handedness else "Hand"
                if label != previous_label and application_mode == "DRAW" and input_mode == "hand":
                    engine.lift()
                    dwell.reset()
                    particles.reset_emitter()
                previous_label = label
                last_hand_points = landmarks_px
                if show_skeleton and application_mode == "DRAW":
                    draw_skeleton(frame, landmarks_px, (0, 255, 170))
                mode = classify_gesture(fingers_up(landmarks_px), thumb_extended(landmarks_px))
                index_pt = landmarks_px[8]
                if application_mode == "TIME":
                    result_time = time_controller.update(landmarks_px, None, "TIME", now)
                    mode, cursor = result_time.state, result_time.cursor
                    dwell.reset()
                elif input_mode == "hand":
                    mode, cursor, selecting = interaction.update(landmarks_px, now)
                    if mode == "DRAW":
                        completed_until = 0
                    if selecting:
                        action = dwell.update(hit_test(*index_pt), now)
                        if action:
                            perform(action)
                        cv2.circle(frame, index_pt, 12, (255, 255, 255), 2, cv2.LINE_AA)
                        cv2.ellipse(frame, index_pt, (18, 18), 0, -90,
                                    -90 + int(360 * dwell.progress(now)), (0, 220, 220), 3)
                    else:
                        dwell.reset()
                if application_mode == "DRAW":
                    draw_hand_badge(frame, label, landmarks_px[0], mode if engine.enabled else "Paused", engine.color)
            else:
                previous_label = None
                if application_mode == "TIME":
                    result_time = time_controller.update(None, None, "TIME", now)
                    mode, cursor = result_time.state, result_time.cursor
                elif input_mode == "hand":
                    mode, cursor, _ = interaction.update(None, now)
                dwell.reset()
            if exit_requested:
                break
            while mouse_actions:
                action = mouse_actions.pop(0)
                if isinstance(action, str):
                    perform(action)
                elif application_mode == "TIME":
                    mouse_held = False
                else:
                    event, x, y = action
                    if event == cv2.EVENT_LBUTTONDOWN:
                        engine.lift()
                        mouse_held = True
                    inside = SIDEBAR_W < x < FRAME_W and TOPBAR_H < y < FRAME_H - 54
                    if mouse_held and inside:
                        completed_until = 0
                        cursor = engine.draw((x, y), smooth=False)
                    elif not inside:
                        engine.lift()
                    if event == cv2.EVENT_LBUTTONUP:
                        mouse_held = False
                        engine.lift()
                dwell.reset()
                if exit_requested:
                    break
            if exit_requested:
                break
            if application_mode == "DRAW" and input_mode == "hand" and mode == "DRAW" and cursor is not None and engine.enabled and engine.previous is not None and engine.tool != "eraser":
                particles.follow(cursor, engine.color, particle_dt)
            else:
                particles.reset_emitter()
            if mode == "DRAG" or engine.tool == "eraser":
                particles.clear()
            if application_mode == "TIME":
                particles.clear()
                scene_height = FRAME_H - TOPBAR_H - 54
                frame[TOPBAR_H:TOPBAR_H+scene_height, SIDEBAR_W:] = flower.render(time_controller.progress, FRAME_W-SIDEBAR_W, scene_height)
                if last_hand_points is not None and show_skeleton:
                    draw_skeleton(frame, last_hand_points, (105, 155, 110))
                mode = time_controller.state
                cursor = time_controller.status.cursor
                render_time_panel(frame, time_controller.status)
            else:
                frame = engine.composite(frame)
                particles.draw(frame, bounds=interaction.bounds)
            completed = next((obj for obj in engine.objects if obj.id == completed_id), None) if application_mode == "DRAW" and now < completed_until else None
            if completed is not None and engine.dragged_id is None:
                x1, y1, x2, y2 = completed.bounds
                cv2.rectangle(frame, (x1 - 3, y1 - 3), (x2 + 3, y2 + 3), (100, 240, 100), 2)
            elif application_mode == "DRAW" and engine.active_group is not None and engine.dragged_id is None:
                x1, y1, x2, y2 = engine.active_group.bounds
                cv2.rectangle(frame, (x1 - 3, y1 - 3), (x2 + 3, y2 + 3), (255, 180, 80), 1)
            if engine.dragged_id is not None:
                dragged = next(obj for obj in engine.objects if obj.id == engine.dragged_id)
                x1, y1, x2, y2 = dragged.bounds
                cv2.rectangle(frame, (x1 - 3, y1 - 3), (x2 + 3, y2 + 3), (0, 220, 255), 1)
            if cursor:
                cursor = tuple(round(value) for value in cursor)
                cv2.circle(frame, cursor, 12 if application_mode == "TIME" else engine.brush_width // 2 + 6, (255, 255, 255), 1, cv2.LINE_AA)
            fps = 1 / max(time.monotonic() - previous_time, 0.001)
            previous_time = time.monotonic()
            render_controls(frame, engine, fps, mode if application_mode == "TIME" or input_mode == "hand" else "Mouse", message if now < message_until else "", input_mode,
                            completed_id=completed.id if completed is not None else None,
                            application_mode=application_mode, time_state=time_controller.status)
            cv2.imshow(WINDOW, frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 17, 27):
                break
            if key == 32:
                perform("stop" if engine.enabled else "start")
            elif key in (ord("z"), ord("u"), ord("Z"), ord("U"), 26):
                perform("undo")
            elif key in (ord("c"), ord("C")):
                perform("clear")
            elif key in (ord("y"), ord("Y")):
                perform("redo")
            elif key in (ord("e"), ord("E")):
                perform("eraser")
            elif key in (ord("t"), ord("T")):
                perform("transparent")
            elif key in (ord("m"), ord("M")):
                perform("input")
            elif key in (ord("p"), ord("P"), ord("l"), ord("L"), ord("r"), ord("R"), ord("o"), ord("O")):
                tools = {"p": "pen", "l": "line", "r": "rectangle", "o": "ellipse"}
                perform("tool:" + tools[chr(key).lower()])
            elif key in (ord("b"), ord("B")):
                perform("background")
            elif key in (ord("x"), ord("X")):
                perform("cancel")
            elif key in (ord("g"), ord("G")):
                perform("group")
            elif key in (ord("f"), ord("F")):
                perform("finish")
            elif key in (ord("s"), ord("S")):
                perform("save")
            elif key in (ord("k"), ord("K")):
                perform("time")
            elif key in (ord("j"), ord("J")):
                perform("flower")
            elif key in (ord("n"), ord("N")):
                perform("time_reset")
            elif ord("1") <= key <= ord("7"):
                perform(f"color:{key - ord('1')}")
            elif key in (ord("h"), ord("H")):
                show_skeleton = not show_skeleton
            elif key in (ord("+"), ord("="), ord("-")) and application_mode == "DRAW":
                interaction.reset()
                particles.reset_emitter()
                engine.lift()
                engine.thickness = max(MIN_BRUSH, min(MAX_BRUSH, engine.thickness + (-2 if key == ord("-") else 2)))
            elif key in (ord("["), ord("]")) and application_mode == "DRAW":
                interaction.reset()
                particles.reset_emitter()
                mouse_held = False
                engine.set_smoothing(round(max(0.05, min(1, engine.smoother.alpha + (-0.05 if key == ord("[") else 0.05))), 3))
            try:
                closed = cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1
            except cv2.error:
                closed = True  # Cocoa may remove the window before this lookup.
            if closed:
                exit_reason = "window_closed"
                break
            if args.smoke_seconds and time.monotonic() - started >= args.smoke_seconds:
                exit_reason = "smoke_complete"
                break
    finally:
        time_controller.release()
        engine.end_drag()
        engine.lift()
        if cap is not None:
            cap.release()
        if landmarker is not None:
            landmarker.close()
        cv2.destroyAllWindows()
        if not args.no_settings:
            try:
                save_preferences({"thickness": engine.thickness, "smoothing": engine.smoother.alpha,
                                  "tool": engine.tool, "color_idx": engine.color_idx,
                                  "input_mode": input_mode, "show_skeleton": show_skeleton,
                                  "export_background": engine.export_background}, args.settings)
            except OSError as exc:
                print(f"无法保存设置，绘画功能仍可用：{exc}", file=sys.stderr, flush=True)
        signal.signal(signal.SIGTERM, previous_sigterm)
    stats = {"frames": frames, "frames_with_hands": detected_frames, "max_hands": max_hands,
             "elapsed_seconds": round(time.monotonic() - started, 2), "exit_reason": exit_reason,
             "camera": args.camera if not args.no_camera else None, "window": WINDOW_TITLE,
             "window_handle": WINDOW,
             "local_inference": landmarker is not None, "input_mode": input_mode}
    stats.update(application_mode=application_mode, time_progress=time_controller.progress)
    print(json.dumps(stats, ensure_ascii=False), flush=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("已退出。")
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"启动或运行失败：{exc}", file=sys.stderr)
        sys.exit(1)
