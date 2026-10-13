"""Build the narrated GitHub demo from real app-rendered frames and synthetic input.

Requires this project's Mac environment plus macOS `say` and an ffmpeg build
with H.264/AAC encoding. No webcam, real hand image, or user drawing is used.
"""
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import ai_virtual_painter as app
from config import FRAME_H, FRAME_W
from painter_core import PaintEngine
from test_drag import hand

FPS = 15
VIDEO_W, VIDEO_H = 1920, 1080
OUTPUT = ROOT / "docs/videos/air-painter-demo.mp4"
PREVIEW = ROOT / "docs/videos/air-painter-demo-poster.png"
SPOKEN_SCRIPTS = [
    ("cover", "一只手，就能在空中画线、画形状、移动图形，还能控制花朵盛开。接下来带你看看 AI 隔空绘画的主要功能。"),
    ("drawing", "伸出食指就能开始绘画。画笔支持七种颜色，笔触会顺着手指实时出现，彩色闪光和暖色火星也会沿笔迹散开。"),
    ("particles", "每次落笔后，画面都会出现彩色闪光和暖色火星。它们跟随笔尖，只装饰实时预览，不会进入画作和导出的图片。"),
    ("shapes", "画笔之外还有直线、矩形和椭圆。按下工具后移动食指预览，抬笔确认；尺寸、颜色都保留在独立笔画里。"),
    ("groups", "一幅画可以分多笔完成。按 G 开启分组，换色继续画；按 F 完成后，整组笔画会作为一个独立对象。"),
    ("objects", "捏合拇指和食指，抓住五角星后拖动，再松开。圆形保持原位。你还可以重新抓住五角星继续移动，抓取偏移和图形颜色都不变。"),
    ("editing", "选中橡皮擦可以抹去局部笔迹。按 Z 撤销、按 Y 重做，也能清屏后撤销恢复；画作编辑一直保留在本机。"),
    ("export", "普通 PNG 可选黑色或白色背景，透明 PNG 则保留透明通道。保存的只有绘画，不包括摄像头、界面和预览粒子。"),
    ("mouse", "除了隔空手绘，也可以切换为鼠标绘画。空格开始或暂停，工具按钮和快捷键都能完成绘画操作。"),
    ("local", "摄像头模式每帧只检测一只手，复用 MediaPipe 手部关键点。本地完成识别、画布合成和设置保存，不上传画面。"),
    ("flower", "进入时间模式，捏合时花苞闭合；逐渐张开手指，花瓣就同步舒展，完全张开时刚好盛开。重新合拢，动画便倒退回花苞。"),
    ("close", "这就是 AI 隔空绘画的主要功能：画笔、形状、分组、移动、编辑、导出、鼠标模式和可逆花朵动画。"),
    ("offline", "电脑没有摄像头，或不想启用摄像头时，可以直接选择无摄像头模式。这里用鼠标绘画，主要工具仍然可用。"),
]
CHAPTERS = {
    "cover": ("一只手 · 隔空创作", "隔空绘画的主要功能演示", "LOCAL DEMO"),
    "drawing": ("食指画笔 · 七种颜色", "7 种颜色 · 一笔画出花朵", "DRAW"),
    "particles": ("彩色闪光 · 暖色火星", "粒子跟随笔尖，仅显示在实时预览", "PARTICLES"),
    "shapes": ("线条 · 矩形 · 椭圆", "预览后抬笔确认，作为独立笔画编辑", "SHAPES"),
    "groups": ("多笔分组", "G 开始分组 · F 确认整组对象", "GROUP"),
    "objects": ("捏合抓取 · 拖动 · 重抓", "五角星移动，圆形留在原位", "OBJECTS"),
    "editing": ("橡皮擦 · 撤销 · 重做", "Z 撤销 · Y 重做 · C 清屏", "EDIT"),
    "export": ("PNG · 透明 PNG", "支持黑底、白底与透明通道", "EXPORT"),
    "mouse": ("鼠标绘画 · 空格暂停", "也可以完全关闭摄像头使用鼠标", "MOUSE"),
    "local": ("单手识别 · 本地运行", "MediaPipe Hand Landmarker · 无图像上传", "ON DEVICE"),
    "flower": ("花苞 → 盛开 → 花苞", "捏合到张开播放，合拢即可倒放", "TIME"),
    "close": ("开源 · Mac 原生应用", "源码、安装步骤和全部测试见 GitHub README", "OPEN SOURCE"),
    "offline": ("无需摄像头 · 鼠标创作", "不启用摄像头，直接用鼠标继续绘画", "OFFLINE"),
}


def make_path(scene, points, frames_each=1, gesture="Draw", ratio=.8):
    for first, last in zip(points, points[1:]):
        for j in range(1, frames_each + 1):
            t = j / frames_each
            position = (round(first[0]*(1-t)+last[0]*t), round(first[1]*(1-t)+last[1]*t))
            scene["events"].append(dict(points=hand(position, ratio, gesture), key=255, mouse=None, scene=scene["key"]))


def idle(scene, count=3, point=(600, 590), gesture="Idle"):
    for _ in range(count):
        scene["events"].append(dict(points=hand(point, .8, gesture), key=255, mouse=None, scene=scene["key"]))


def key(scene, value, settle=3):
    idle(scene, settle)
    scene["events"].append(dict(points=hand((600, 590), .8, "Idle"), key=ord(value), mouse=None, scene=scene["key"]))
    idle(scene, 2)


def draw_poly(scene, points, frames_each=2):
    idle(scene, 2, points[0], "Draw")
    make_path(scene, points, frames_each)
    idle(scene, 3, points[-1], "Idle")


def petal_points(center, angle, length=112, half_width=34, steps=10):
    direction = np.array((math.cos(angle), math.sin(angle)))
    normal = np.array((-direction[1], direction[0]))
    root = np.asarray(center, dtype=float)
    u = np.linspace(0, 1, steps)
    mid = root + u[:,None]*length*direction + (np.sin(np.pi*u)*8)[:,None]*normal
    width = np.sin(np.pi*u)*half_width
    outline = np.vstack((mid + width[:,None]*normal,
                         (mid-width[:,None]*normal)[::-1]))
    return [tuple(np.rint(p).astype(int)) for p in np.vstack((outline, outline[:1]))]


def make_story():
    result = []
    for slug, voice in SPOKEN_SCRIPTS:
        title, subtitle, tag = CHAPTERS[slug]
        result.append(dict(key=slug, title=title, subtitle=subtitle, tag=tag,
                           voice=voice, events=[]))
    by = {item["key"]:item for item in result}
    s = by["cover"]
    s["events"].extend(dict(points=None,key=255,mouse=None,scene="cover") for _ in range(16))
    key(s, " ")
    key(s, "h")  # Hide synthetic skeleton overlay while retaining cursor feedback.

    # Seven independent pastel petals and a green stem/leaves.
    s = by["drawing"]
    colors = list("1234567")
    for index in range(7):
        key(s, colors[index])
        angle = -math.pi/2 + index*math.tau/7
        draw_poly(s, petal_points((590,315), angle), 1)
    key(s, "2")
    draw_poly(s, [(590,410),(585,448),(590,494),(590,544),(595,577)], 2)
    draw_poly(s, petal_points((570,470), math.pi, 68, 19, 7), 1)
    draw_poly(s, petal_points((605,500), -.36, 65, 19, 7), 1)
    # Seven-colour palette remains visible in the actual app UI.

    # The app's existing preview particles follow the fingertip as a stroke is drawn.
    s=by["particles"]
    key(s,"p")
    draw_poly(s,[(165,620),(215,580),(265,630),(320,570),(375,620),(430,575),(485,620),
                 (540,575),(595,620),(650,575),(705,620),(760,575),(820,610)],3)

    # Three familiar tools, drawn as independently committed examples.
    s = by["shapes"]
    key(s,"l"); draw_poly(s, [(190,500),(330,480),(450,500)], 6)
    key(s,"r"); draw_poly(s, [(400,480),(555,575),(400,575),(400,480)], 5)
    key(s,"o"); draw_poly(s, [(740,510),(760,460),(815,440),(870,460),(890,510),(870,560),(815,580),(760,560),(740,510)], 3)
    key(s,"p")

    # Two strokes form one group, then F confirms it as a separate object.
    s = by["groups"]
    key(s,"g")
    draw_poly(s, [(830,205),(900,205),(915,240),(865,265),(815,240),(830,205)], 4)
    key(s,"4")
    draw_poly(s, [(815,220),(865,260),(915,220)], 5)
    key(s,"f")
    idle(s,10, (600,590))

    # Individual star and circle; grab, move, release, and re-grab the same star.
    s = by["objects"]
    key(s,"p"); key(s,"1")
    star = [(270+58*math.cos(-math.pi/2+i*4*math.pi/5),
             260+58*math.sin(-math.pi/2+i*4*math.pi/5)) for i in range(6)]
    draw_poly(s, [tuple(map(round,p)) for p in star],2)
    key(s,"3")
    circle = [(860+67*math.cos(t),490+67*math.sin(t)) for t in np.linspace(0,math.tau,26)]
    draw_poly(s,[tuple(map(round,p)) for p in circle],1)
    idle(s,4, (600,590))
    # Click at a visible star vertex, then drag right while continuously pinched.
    # Drawing points use the index tip (40 px left); the pinch center must
    # therefore target the actual first star vertex at x=230.
    make_path(s,[(230,202)]*4,1,ratio=.2)
    make_path(s,[(260,202),(305,212),(355,230),(400,252)],2,ratio=.2)
    make_path(s,[(400,252)]*3,1,ratio=.8)
    idle(s,5,(400,252))
    make_path(s,[(400,252)]*4,1,ratio=.2)
    make_path(s,[(370,252),(340,252),(310,252)],2,ratio=.2)
    make_path(s,[(310,252)]*3,1,ratio=.8)
    idle(s,7,(310,252))

    # Undo and redo a stroke without replacing the drawing; then show the eraser.
    s=by["editing"]
    key(s,"z"); idle(s,5,(350,252)); key(s,"y"); idle(s,5,(350,252))
    key(s,"e")
    draw_poly(s,[(260,260),(282,253),(305,247)],3)
    key(s,"z"); idle(s,4,(350,252)); key(s,"y"); idle(s,8,(350,252))
    key(s,"p"); key(s,"2")

    # Clear then undo the clear, demonstrating that the drawing remains recoverable.
    key(s,"c"); idle(s,4,(350,252)); key(s,"z"); idle(s,8,(350,252))

    s=by["export"]
    key(s,"b"); key(s,"s"); idle(s,8,(590,590)); key(s,"t"); idle(s,8,(590,590)); key(s,"b")

    # In the camera-backed process switch to MOUSE and draw with real app mouse callbacks.
    s=by["mouse"]
    key(s,"m")
    for j,point in enumerate([(650,565),(670,530),(700,505),(740,495),(780,515),(805,550),(800,590)]):
        kind= "down" if j==0 else "up" if j==6 else "move"
        s["events"].append(dict(points=hand((600,590),.8,"Idle"),key=255,mouse=(kind,*point),scene=s["key"]))
    key(s," ")  # pause, then resume with space
    key(s," ")
    key(s,"m")

    # Camera-free mouse drawing is captured in a separate --no-camera app launch.
    s=by["offline"]
    s["events"].append(dict(points=None,key=ord(" "),mouse=None,scene="offline"))
    s["events"].extend(dict(points=None,key=255,mouse=None,scene="offline") for _ in range(2))
    for j,point in enumerate([(650,565),(675,525),(715,505),(755,515),(790,550),(780,590)]):
        kind="down" if j==0 else "up" if j==5 else "move"
        s["events"].append(dict(points=None,key=255,mouse=(kind,*point),scene="offline"))
    s["events"].extend(dict(points=None,key=255,mouse=None,scene="offline") for _ in range(8))

    # The flower follows the live normalized pinch aperture: closed → open → closed.
    s=by["flower"]
    key(s,"j")
    for aperture in np.linspace(.20,1.35,110):
        s["events"].append(dict(points=hand((700,360),float(aperture)),key=255,mouse=None,scene="flower"))
    for aperture in np.linspace(1.35,.20,90):
        s["events"].append(dict(points=hand((700,360),float(aperture)),key=255,mouse=None,scene="flower"))
    key(s,"n")
    for aperture in np.linspace(.20,1.35,60):
        s["events"].append(dict(points=hand((700,360),float(aperture)),key=255,mouse=None,scene="flower"))
    idle(s,12,(700,360),"Idle")
    key(s,"k")

    s=by["close"]
    idle(s,12,(700,600),"Idle")
    s["events"].extend(dict(points=None,key=255,mouse=None,scene="close") for _ in range(30))
    return result


def narrator_audio(chapters, folder):
    pieces=[folder/f"voice-{index:02}.aiff" for index in range(len(chapters))]
    padded=[]
    for index,(path,chapter) in enumerate(zip(pieces,chapters)):
        pause=max(0,chapter["frame_count"]/FPS-chapter["voice_duration"])
        destination=folder/f"chapter-{index:02}.wav"
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-i",str(path),"-f","lavfi","-t",f"{pause:.3f}","-i",
            "anullsrc=channel_layout=mono:sample_rate=48000","-filter_complex","[0:a][1:a]concat=n=2:v=0:a=1[out]",
            "-map","[out]","-c:a","pcm_s16le","-y",str(destination)],check=True)
        padded.append(destination)
    concat=folder/"audio-list.txt"
    concat.write_text("".join(f"file '{path.as_posix()}'\n" for path in padded))
    audio=folder/"narration.m4a"
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-f","concat","-safe","0","-i",str(concat),
                    "-c:a","aac","-b:a","160k","-ar","48000","-movflags","+faststart","-y",str(audio)],check=True)
    durations=[]
    for path in pieces:
        value=subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(path)],text=True)
        durations.append(float(value.strip()))
    return audio


def build_ui():
    w,h=VIDEO_W,VIDEO_H
    y,x=np.mgrid[:h,:w].astype(np.float32)
    mix=np.clip(y/h,0,1)[...,None]
    top=np.array([14,20,33],np.float32)
    bottom=np.array([22,32,48],np.float32)
    rgb=np.clip(top*(1-mix)+bottom*mix,0,255).astype(np.uint8)
    accent=np.zeros((h,w,3),np.uint8)
    cv2.circle(accent,(320,825),350,(38,30,58),-1,cv2.LINE_AA)
    rgb=cv2.add(rgb,cv2.GaussianBlur(accent,(0,0),130))
    fonts=[Path(p) for p in ("/System/Library/Fonts/Hiragino Sans GB.ttc","/System/Library/Fonts/STHeiti Medium.ttc")]
    font_path=next((p for p in fonts if p.is_file()),None)
    if font_path is None: raise RuntimeError("macOS 中文字体不可用")
    screen_font=ImageFont.truetype(str(font_path),27)
    caption_font=ImageFont.truetype(str(font_path),25)
    badge_font=ImageFont.truetype(str(font_path),19)
    top_font=ImageFont.truetype(str(font_path),22)
    hero_font=ImageFont.truetype(str(font_path),53)
    body_font=ImageFont.truetype(str(font_path),26)
    tiny_font=ImageFont.truetype(str(font_path),18)
    corner=np.zeros((864,1320),np.uint8)
    cv2.rectangle(corner,(16,0),(1303,863),255,-1)
    for pt in ((16,16),(1303,16),(16,847),(1303,847)):
        cv2.circle(corner,pt,16,255,-1,cv2.LINE_AA)
    return rgb, (font_path,screen_font,caption_font,badge_font,top_font,hero_font,body_font,tiny_font),corner


def wrap_lines(draw,text,font,width):
    result=[];line=""
    for character in text:
        candidate=line+character
        if line and draw.textbbox((0,0),candidate,font=font)[2]>width:
            result.append(line);line=character
        else:line=candidate
    if line:result.append(line)
    return result


def compose(ui, chapter, chapter_index, total, fonts, corner, seconds):
    _, screen_font, subtitle_font, badge_font, top_font, hero_font, body_font, tiny_font=fonts
    canvas=BASE.copy()
    image=Image.fromarray(canvas)
    draw=ImageDraw.Draw(image)
    # Header brand, compact chapter count and system labels.
    draw.rounded_rectangle((88,52,106,70),radius=7,fill=(133,220,173))
    draw.text((120,48),"AI 隔空绘画",font=top_font,fill=(233,240,246))
    draw.text((120,78),"AIR PAINTER  /  MACOS",font=ImageFont.truetype(fonts[0],15),fill=(139,160,180))
    draw.rounded_rectangle((1530,48,1836,91),radius=21,fill=(28,47,59),outline=(58,82,89),width=1)
    draw.ellipse((1550,63,1562,75),fill=(137,221,174))
    draw.text((1575,57),"合成关键点 · 本地演示",font=top_font,fill=(194,219,208))
    # Feature narrative panel.
    draw.text((94,202),chapter["tag"],font=badge_font,fill=(140,224,177))
    draw.rounded_rectangle((94,237,174,242),radius=3,fill=(94,204,148))
    draw.text((94,278),f"{chapter_index+1:02d}",font=ImageFont.truetype(fonts[0],21),fill=(114,141,159))
    title_lines=wrap_lines(draw,chapter["title"],hero_font,400)
    yy=330
    for line in title_lines[:3]:
        draw.text((94,yy),line,font=hero_font,fill=(242,246,246));yy+=68
    yy+=20
    for line in wrap_lines(draw,chapter["subtitle"],body_font,392)[:4]:
        draw.text((98,yy),line,font=body_font,fill=(170,193,201));yy+=44
    draw.rounded_rectangle((94,716,454,858),radius=18,fill=(22,34,48),outline=(47,67,79),width=1)
    draw.text((116,735),"解说",font=badge_font,fill=(137,220,176))
    lines=wrap_lines(draw,chapter["voice"],subtitle_font,318)
    for i,line in enumerate(lines[:4]):
        draw.text((116,770+i*31),line,font=subtitle_font,fill=(217,226,229))
    # Distilled app screen: actual BGR image captured inside the production loop.
    rgb_ui=cv2.cvtColor(cv2.resize(ui,(1320,864),interpolation=cv2.INTER_LANCZOS4),cv2.COLOR_BGR2RGB)
    screen=Image.fromarray(rgb_ui)
    frame=Image.new("RGBA",(1320,864),(0,0,0,0))
    frame.paste(screen,mask=Image.fromarray(corner))
    shadow=Image.new("RGBA",image.size,(0,0,0,0))
    shadow_draw=ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((516,139,1857,1017),radius=20,fill=(0,0,0,145))
    shadow=shadow.filter(__import__('PIL.ImageFilter',fromlist=['GaussianBlur']).GaussianBlur(22))
    image=image.convert("RGBA");image.alpha_composite(shadow)
    image.alpha_composite(frame,(526,133))
    draw=ImageDraw.Draw(image)
    # Chapter navigation dots are labels only; the app screen has no timeline bar.
    draw.text((526,1030),"功能演示  /  单手 · 鼠标 · TIME",font=tiny_font,fill=(119,147,158))
    draw.text((1745,1030),f"{seconds//60:02d}:{seconds%60:02d}",font=tiny_font,fill=(128,154,163))
    return np.asarray(image.convert("RGB"),dtype=np.uint8)


def allocate_chapters(chapters, voice_durations):
    offset=0
    for chapter,duration in zip(chapters,voice_durations):
        events=chapter["events"]
        if not events:
            events=[dict(points=None,key=255,mouse=None,scene=chapter["key"])]
            chapter["events"]=events
        count=max(len(events),int(math.ceil((duration+.45)*FPS)))
        last=events[-1]
        events.extend([dict(last,key=255,mouse=None) for _ in range(count-len(events))])
        if chapter["key"] in ("close","offline"):
            events[-1]["key"]=ord("q")
        chapter.update(first_frame=offset,frame_count=count,duration_seconds=count/FPS,voice_duration=duration)
        offset+=count
    return offset


BASE=None


def main():
    global BASE
    ffmpeg=shutil.which("ffmpeg")
    if not ffmpeg:raise RuntimeError("请安装 ffmpeg 后再生成演示视频")
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    chapters=make_story()
    with tempfile.TemporaryDirectory(prefix="air-painter-demo-") as temporary:
        temp=Path(temporary)
        durations=[]
        for index,chapter in enumerate(chapters):
            path=temp/f"voice-{index:02}.aiff"
            subprocess.run(["say","-v","Tingting","-r","190","-o",str(path),chapter["voice"]],check=True)
            value=subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(path)],text=True)
            durations.append(float(value.strip()))
        total_frames=allocate_chapters(chapters,durations)
        narration=narrator_audio(chapters,temp)
        chapters_by_key={chapter["key"]:chapter for chapter in chapters}
        export_dir=ROOT/"test-output/demo-paintings"
        export_dir.mkdir(parents=True,exist_ok=True)
        BASE,fonts,corner=build_ui()
        clock=[0.0]
        total_frame=[0]
        capture_reports=[]
        audioframes=total_frames/FPS
        # libx264 creates a universally playable, fast-start H.264 MP4.
        encoder=subprocess.Popen([ffmpeg,"-hide_banner","-loglevel","error","-f","rawvideo","-pix_fmt","rgb24",
             "-s",f"{VIDEO_W}x{VIDEO_H}","-r",str(FPS),"-i","-","-i",str(narration),"-map","0:v:0","-map","1:a:0",
             "-vf","fps=24,format=yuv420p","-c:v","libx264","-preset","medium","-crf","20","-profile:v","high",
             "-c:a","aac","-b:a","160k","-movflags","+faststart","-t",f"{audioframes:.3f}","-y",str(OUTPUT)],stdin=subprocess.PIPE)
        def writer(window,app_frame):
            session=active_session[0]
            session["frame"]+=1
            if session["frame"]>=len(session["timeline"]):raise RuntimeError("录制画面超过预设视频脚本")
            spec=session["timeline"][session["frame"]]
            chapter=chapters_by_key[spec["scene"]]
            rgb=compose(app_frame,chapter,list(chapters_by_key).index(chapter["key"]),len(chapters),fonts,corner,total_frame[0]//FPS)
            encoder.stdin.write(rgb.tobytes())
            if chapter["key"]=="flower" and abs(session["frame"]-session["chapter_starts"]["flower"]-int(chapter["frame_count"]*.48))<=1:
                cv2.imwrite(str(PREVIEW),app_frame)
            total_frame[0]+=1
        active_session=[None]
        def save_png(engine,directory=None,transparent=False):
            return original_save(engine,directory=export_dir,transparent=transparent)
        original_save=PaintEngine.save

        def run_session(session_chapters,no_camera):
            timeline=[event for chapter in session_chapters for event in chapter["events"]]
            chapter_starts={}
            start=0
            for chapter in session_chapters:
                chapter_starts[chapter["key"]]=start
                start+=chapter["frame_count"]
            session={"timeline":timeline,"chapter_starts":chapter_starts,"frame":-1,"mouse":None,"camera":None,"model":None}
            active_session[0]=session
            camera_released=[False]
            model_closed=[False]
            class Camera:
                def read(self):
                    if session["frame"]+1>=len(timeline):return False,None
                    spec=timeline[session["frame"]+1]
                    points=spec["points"]
                    landmarks=[] if points is None else [[SimpleNamespace(x=(x+1e-6)/FRAME_W,y=(y+1e-6)/FRAME_H) for x,y in points]]
                    session["model"].next=landmarks
                    clock[0]+=1/FPS
                    return True,np.full((FRAME_H,FRAME_W,3),(54,65,72),np.uint8)
                def release(self):camera_released[0]=True
            class Model:
                def __init__(self):self.next=[];self.calls=0
                def detect_for_video(self,image,timestamp):
                    self.calls+=1
                    hands=self.next or []
                    return SimpleNamespace(hand_landmarks=hands,handedness=[[SimpleNamespace(category_name="Right")]] if hands else [])
                def close(self):model_closed[0]=True
            camera,model=(None,None) if no_camera else (Camera(),Model())
            session.update(camera=camera,model=model)
            def wait_key(delay):
                spec=timeline[session["frame"]]
                if spec["mouse"] is not None and session["mouse"] is not None:
                    kind,x,y=spec["mouse"]
                    event={"down":cv2.EVENT_LBUTTONDOWN,"move":cv2.EVENT_MOUSEMOVE,"up":cv2.EVENT_LBUTTONUP}[kind]
                    session["mouse"](event,x,y,cv2.EVENT_FLAG_LBUTTON if kind!="up" else 0,None)
                return spec["key"]
            report=temp/f"app-report-{len(capture_reports)}.json"
            argv=["ai_virtual_painter.py","--no-settings","--smoothing","1","--report",str(report)]
            if no_camera:argv.append("--no-camera")
            with patch.object(sys,"argv",argv), patch.object(app,"require_camera_permission"), \
                 patch.object(app,"open_camera",return_value=camera), patch.object(app,"create_landmarker",return_value=model), \
                 patch.object(app,"create_window"), patch.object(cv2,"setMouseCallback",side_effect=lambda window,callback:session.__setitem__("mouse",callback)), \
                 patch.object(cv2,"imshow",side_effect=writer), patch.object(cv2,"waitKey",side_effect=wait_key), \
                 patch.object(cv2,"getWindowProperty",return_value=1), patch.object(cv2,"destroyAllWindows"), \
                 patch.object(app.time,"monotonic",side_effect=lambda:clock[0]), patch.object(PaintEngine,"save",new=save_png):
                app.main()
            assert session["frame"]+1==len(timeline),(session["frame"]+1,len(timeline))
            if no_camera:
                assert session["camera"] is None and session["model"] is None
            else:
                assert camera_released[0] and model_closed[0] and model.calls==len(timeline)
                assert session["camera"] is camera and session["model"] is model
            capture_report=json.loads(report.read_text())
            assert capture_report["frames"]==len(timeline)
            if not no_camera:assert capture_report["frames_with_hands"]>0 and capture_report["max_hands"]<=1
            capture_reports.append(capture_report)
        try:
            hand_chapters=[c for c in chapters if c["key"]!="offline"]
            run_session(hand_chapters,no_camera=False)
            run_session([chapters_by_key["offline"]],no_camera=True)
            assert total_frame[0]==total_frames
            encoder.stdin.close()
            if encoder.wait(timeout=90):raise RuntimeError("ffmpeg 视频编码失败")
        except BaseException:
            if encoder.stdin and not encoder.stdin.closed:encoder.stdin.close()
            encoder.kill();encoder.wait()
            raise
        data=subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration,size:stream=codec_name,width,height,avg_frame_rate",
                                      "-of","json",str(OUTPUT)],text=True)
        result=json.loads(data)
        result["capture_frames"]=total_frame[0];result["captures"]=capture_reports
        result["chapters"]=[{"name":c["title"],"duration":round(c["duration_seconds"],2)} for c in chapters]
        (ROOT/"test-output/demo-video.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
        print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
