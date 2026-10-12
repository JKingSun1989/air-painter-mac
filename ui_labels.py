"""Chinese display labels; internal action names and settings stay stable."""
TOOL_NAMES = {"pen": "画笔", "eraser": "橡皮擦", "line": "直线", "rectangle": "矩形", "ellipse": "椭圆"}
INPUT_NAMES = {"hand": "隔空", "mouse": "鼠标"}
MODE_NAMES = {"DRAW": "绘画", "IDLE": "抬笔", "DRAG": "拖动", "Draw": "绘画", "Idle": "抬笔",
              "Select": "选择", "Paused": "已暂停", "No hand": "未检测到手", "Mouse": "鼠标",
              "Resize": "调整笔宽", "Erase": "擦除"}
MODE_NAMES.update({"TIME_IDLE": "待捏合", "TIME_OPEN": "手指开合控制", "TIME_LOST": "暂时丢失手部", "INACTIVE": "未启用"})
HAND_NAMES = {"Left": "左手", "Right": "右手", "Hand": "手部"}
COLOR_NAMES = {"Red": "红色", "Green": "绿色", "Blue": "蓝色", "Yellow": "黄色",
               "Purple": "紫色", "Cyan": "青色", "White": "白色"}
