"""Math2Geo 的 Qt 界面。

配色和布局参考「绘制区域」那版设计：浅绿标题栏、药丸标签页、白色卡片。
主页面负责上传、日志和任务；设置页分成模型、题目、绘图和其他四块。
"""

from __future__ import annotations

import glob
import json
import math
import os
import shutil
import sys
import ctypes
from ctypes import wintypes
import tempfile
import time
from datetime import datetime

from PySide6.QtCore import (
    QAbstractAnimation,
    QAbstractNativeEventFilter,
    QEasingCurve,
    QTime,
    QEvent,
    QObject,
    QPoint,
    QRectF,
    QUrl,
    QPointF,
    QRect,
    QRectF,
    QSize,
    QPropertyAnimation,
    Qt,
    QThread,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QGuiApplication,
    QIcon,
    QKeySequence,
    QMovie,
    QPainter,
    QPalette,
    QPainterPath,
    QPen,
    QRegion,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QGraphicsOpacityEffect,
    QSizeGrip,
    QSplitter,
    QSystemTrayIcon,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QKeySequenceEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
    QTextBrowser,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
    QColorDialog,
)

from . import __version__, pipeline

REPO_URL = "https://github.com/Mu-Jiji/math2geo"
ENABLE_FREE_API = False

PROVIDERS = [
    # 名称, Base URL, 默认模型, 开放平台地址
    ("深度求索 DeepSeek", "https://api.deepseek.com/v1", "deepseek-flash", "https://platform.deepseek.com/"),
    ("智谱 GLM", "https://open.bigmodel.cn/api/paas/v4", "glm-4-flash", "https://open.bigmodel.cn/"),
    ("月之暗面 Kimi", "https://api.moonshot.cn/v1", "moonshot-v1-8k", "https://platform.kimi.com/"),
    (
        "阿里巴巴 通义千问",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "qwen-plus",
        "https://platform.qianwenai.com/docs/developer-guides/getting-started/first-api-call",
    ),
    ("腾讯 混元", "https://api.hunyuan.cloud.tencent.com/v1", "hunyuan-turbo", "https://cloud.tencent.com/document/product/1729/111008"),
    ("小米 MiMo", "https://api.xiaomimimo.com/v1", "mimo-v2.6-pro", "https://mimo.mi.com/"),
    ("OpenAI ChatGPT", "https://api.openai.com/v1", "gpt-4o-mini", "https://platform.openai.com/"),
    ("Anthropic Claude", "https://api.anthropic.com/v1", "claude-sonnet-4", "https://platform.claude.com/"),
    ("免费 API", "", "", ""),
    ("其他（自定义）", "", "", ""),
]

CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "math2geo")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

VERSE = {
    "main": "#1F5C46",
    "aux": "#8FD3A8",
    "bg": "#F3F8F4",
    "header1": "#8FD3A8",
    "header2": "#A9DFBC",
    "ink": "#0F3D2E",
    "muted": "#5D6B63",
    "border": "#D9E8DE",
    "tab_active": "#A8D8B9",
}

DEFAULTS = {
    "model": {
        "mode": "cloud",
        "provider": "深度求索 DeepSeek",
        "model": "deepseek-flash",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "",
        "key_env": "MATH2GEO_API_KEY",
        "name": "deepseek-flash",
        "temperature": 0.2,
        "max_tokens": 4000,
        "timeout": 120,
        "classroom": False,
        "free_provider": "",
        "api_presets": [],
        "api_passcode": "",
        "api_passcode_set": False,
        "api_auto_enter": True,
        "api_confirm": True,
        "show_price": False,
        "pricing": {
            "currency": "CNY",
            "in": 2.0,
            "out": 8.0,
            "peak_enabled": False,
            "peak_start": "09:00",
            "peak_end": "18:00",
            "lunch_enabled": False,
            "lunch_start": "12:00",
            "lunch_end": "14:00",
            "weekdays": [1, 2, 3, 4, 5],
            "extra_dates": "",
            "off_in": 1.0,
            "off_out": 4.0,
        },
    },
    "problem": {
        "include": True,
        "prompt": "",
        "mode": "原文",
        "answer": True,
        "detail": "简单",
        "difficulty": False,
        "breakthrough": False,
    },
    "draw": {
        "target": "GeoGebra",
        "dimension": "2D",
        "section_azimuth": 35,
        "section_elevation": 20,
        "section_snap": 15,
        "axes": False,
        "grid": False,
        "extra": False,
        "format": "SVG",
        "dpi": 190,
        "main": VERSE["main"],
        "aux": VERSE["aux"],
        "aux_style": "虚线",
    },
    "other": {"outdir": os.path.abspath("out"), "background": "plain", "anim_startup": True, "anim_title": True, "anim_speed": 1.0, "notify_sound": True, "notify_sound_path": "", "notify_windows": True, "offline_bundle": False, "capture_hotkey": "Ctrl+Alt+S", "capture_confirm": True},
}


def load_config() -> dict:
    data = json.loads(json.dumps(DEFAULTS))
    try:
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            saved = json.load(fh)
        for section, values in saved.items():
            if section == "version":
                continue
            if isinstance(values, dict):
                data.setdefault(section, {}).update(values)
        version = saved.get("version") or 0
        if version < 2:
            # v2：默认 4000 tokens，控制单题成本
            if int(data["model"].get("max_tokens", 0)) > 6000:
                data["model"]["max_tokens"] = 4000
            data["problem"]["detail"] = "简单"
        data["version"] = 2
    except (OSError, ValueError):
        data["version"] = 1
    return data


CACHE_DIR = os.path.join(CONFIG_DIR, "cache")
ASSET_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")
INTRO_WEBP = os.path.join(ASSET_DIR, "intro.webp")
TITLE_WEBP = os.path.join(ASSET_DIR, "title.webp")
TITLE_END_PNG = os.path.join(ASSET_DIR, "title_end.png")
WINDOW_PATH = os.path.join(CONFIG_DIR, "window.json")


def load_window_state() -> dict:
    try:
        with open(WINDOW_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_window_state(data: dict) -> None:
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(WINDOW_PATH, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass


def save_config(data: dict) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------ 小部件



class HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def nativeEventFilter(self, eventType, message):
        if sys.platform == "win32":
            try:
                msg = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
                if msg.message == 0x0312:
                    self.callback()
                    return True, 0
            except Exception:
                pass
        return False, 0


class CaptureOverlay(QDialog):
    selected = Signal(QPixmap)
    cancelled = Signal()

    def __init__(self, screen, parent=None):
        super().__init__(parent)
        self._screen = screen
        self._pix = screen.grabWindow(0)
        self._origin = None
        self._rect = QRect()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setGeometry(screen.geometry())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self._pix)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 105))
        if not self._rect.isNull():
            painter.fillRect(self._rect, QColor(255, 255, 255, 26))
            painter.setPen(QPen(QColor("#8FD3A8"), 3))
            painter.drawRect(self._rect)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(20, 30, 24, 220))
        tip = "拖动框选截图区域    Esc / 右键取消"
        tw = painter.fontMetrics().horizontalAdvance(tip) + 36
        painter.drawRoundedRect(QRect((self.width() - tw) // 2, 22, tw, 36), 10, 10)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(QRect((self.width() - tw) // 2, 22, tw, 36), Qt.AlignmentFlag.AlignCenter, tip)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self.close()
            self.cancelled.emit()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.position().toPoint()
            self._rect = QRect(self._origin, self._origin)
            self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._origin is not None:
            self._rect = QRect(self._origin, event.position().toPoint()).normalized()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._origin is not None:
            rect = QRect(self._origin, event.position().toPoint()).normalized()
            self.close()
            if rect.width() > 8 and rect.height() > 8:
                dpr = self._screen.devicePixelRatio() or 1.0
                pix_rect = QRect(int(rect.x()*dpr), int(rect.y()*dpr),
                                 int(rect.width()*dpr), int(rect.height()*dpr))
                self.selected.emit(self._pix.copy(pix_rect))
            else:
                self.cancelled.emit()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            self.cancelled.emit()
        else:
            super().keyPressEvent(event)


class Shell(QFrame):
    """窗口内容底板：圆角 + 可选网格 / 点网背景。"""

    STEP = 26

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Shell")
        self.mode = "plain"

    def set_mode(self, mode: str) -> None:
        self.mode = mode if mode in ("plain", "grid", "dots") else "plain"
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = 0.0 if bool(self.property("max")) else 10.0
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.setClipPath(path)
        painter.fillPath(path, QColor(VERSE["bg"]))

        if self.mode == "grid":
            pen = QPen(QColor(31, 92, 70, 24))
            pen.setWidth(1)
            painter.setPen(pen)
            y = self.STEP
            while y < self.height():
                painter.drawLine(QPointF(0, y), QPointF(self.width(), y))
                y += self.STEP
            x = self.STEP
            while x < self.width():
                painter.drawLine(QPointF(x, 0), QPointF(x, self.height()))
                x += self.STEP
        elif self.mode == "dots":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(31, 92, 70, 55))
            y = self.STEP
            while y < self.height():
                x = self.STEP
                while x < self.width():
                    painter.drawEllipse(QPointF(x, y), 1.1, 1.1)
                    x += self.STEP
                y += self.STEP

        painter.setClipping(False)
        pen = QPen(QColor(31, 92, 70, 50))
        pen.setWidthF(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)


class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")


class Pill(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("Tab")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class ModeSwitch(QFrame):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ModeSwitch")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(200, 40)
        self.setAttribute(Qt.WidgetAttribute.WA_NoMousePropagation, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(8)
        self.icon = QLabel()
        self.icon.setFixedSize(24, 24)
        self.text = QLabel("二维模式")
        self.text.setObjectName("ModeSwitchText")
        self.switch = QLabel()
        self.switch.setFixedSize(18, 18)
        lay.addWidget(self.icon)
        lay.addWidget(self.text, 1)
        lay.addWidget(self.switch)
        self.set_mode(False)

    def set_mode(self, is3d: bool) -> None:
        base = os.path.join(os.path.dirname(__file__), "..", "assets")
        icon_name = "mode3d.png" if is3d else "mode2d.png"
        pix = QPixmap(os.path.join(base, icon_name))
        if not pix.isNull():
            self.icon.setPixmap(pix.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation))
        else:
            self.icon.setText("◈" if is3d else "▱")
        sw = QPixmap(os.path.join(base, "mode_switch.png"))
        if not sw.isNull():
            self.switch.setPixmap(sw.scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation))
        else:
            self.switch.setText("⇄")
        self.text.setText("三维模式" if is3d else "二维模式")
        self.setToolTip("当前为三维，点击切换到二维" if is3d else "当前为二维，点击切换到三维")

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class ColorPicker(QPushButton):
    """色板：点击选预设色或自定义。"""

    colors = ["#1F5C46", "#8FD3A8", "#2B6CB0", "#E8590C", "#8A9199", "#16181D", "#B7791F"]

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._color = color
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(34)
        self.setMinimumWidth(150)
        self.clicked.connect(self._open)
        self._refresh()

    def color(self) -> str:
        return self._color

    def set_color(self, color: str) -> None:
        if color:
            self._color = color
            self._refresh()

    def _refresh(self) -> None:
        self.setStyleSheet(
            f"QPushButton {{ background:#FFFFFF; border:1px solid {VERSE['border']}; border-radius:8px;"
            f" padding-left:30px; text-align:left; color:{VERSE['ink']}; }}"
            f"QPushButton::icon {{ }}"
        )
        self.setText(f"  {self._color.upper()}")
        pm = QPixmap(18, 18)
        pm.fill(QColor(self._color))
        self.setIcon(pm)

    def _open(self) -> None:
        menu = QMenu(self)
        for c in self.colors:
            act = menu.addAction(c.upper())
            pm = QPixmap(14, 14)
            pm.fill(QColor(c))
            act.setIcon(pm)
            act.triggered.connect(lambda _=False, col=c: self.set_color(col))
        menu.addSeparator()
        act = menu.addAction("自定义…")
        act.triggered.connect(self._custom)
        menu.exec(self.mapToGlobal(QPoint(0, self.height())))

    def _custom(self) -> None:
        col = QColorDialog.getColor(QColor(self._color), self, "选择颜色")
        if col.isValid():
            self.set_color(col.name())



def _tick_icon() -> str:
    """生成一个白色对勾 PNG，供 QSS 的 checkbox 使用。"""
    path = os.path.join(tempfile.gettempdir(), "math2geo_check.png")
    if os.path.exists(path):
        return path
    pm = QPixmap(18, 18)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor("#FFFFFF"))
    pen.setWidthF(2.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawLine(4, 9, 7, 13)
    p.drawLine(7, 13, 14, 5)
    p.end()
    pm.save(path)
    return path


def _cloud_pixmap(size: int = 64) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#2F6B52"))
    s = size / 64.0
    p.drawEllipse(int(12 * s), int(30 * s), int(22 * s), int(22 * s))
    p.drawEllipse(int(22 * s), int(20 * s), int(26 * s), int(26 * s))
    p.drawEllipse(int(36 * s), int(30 * s), int(20 * s), int(20 * s))
    p.drawRoundedRect(int(12 * s), int(38 * s), int(44 * s), int(14 * s), int(7 * s), int(7 * s))
    # 向上的箭头（白色）
    pen = QPen(QColor("#FFFFFF"))
    pen.setWidthF(3.2 * s)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawLine(int(32 * s), int(44 * s), int(32 * s), int(30 * s))
    p.drawLine(int(26 * s), int(36 * s), int(32 * s), int(30 * s))
    p.drawLine(int(38 * s), int(36 * s), int(32 * s), int(30 * s))
    p.end()
    return pm


class GripHandle(QWidget):
    """小方块手柄：按住拖动，发出相对按下点的位移。"""

    dragged = Signal(int, int)
    pressed = Signal()

    def __init__(self, cursor=Qt.CursorShape.SizeFDiagCursor, parent=None):
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self.setCursor(cursor)
        self.setToolTip("拖动调整大小")
        self._start = None

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(211, 231, 220, 160))
        p.drawRoundedRect(0, 0, w, h, 4, 4)
        p.setBrush(QColor("#5D6B63"))
        cx, cy = w // 2, h // 2
        for row in (-1, 1):
            for col in (-1, 1):
                p.drawEllipse(cx + col * 2 - 1, cy + row * 2 - 1, 2, 2)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.globalPosition().toPoint()
            self.pressed.emit()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._start is not None:
            now = event.globalPosition().toPoint()
            self.dragged.emit(now.x() - self._start.x(), now.y() - self._start.y())
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._start = None
        event.accept()




class HelpDialog(QDialog):
    """帮助文档窗口：用原生控件排版，保证与主界面字体一致。"""

    BLOCKS = [
        ("h1", "如何使用 Math2Geo"),
        ("sub", "编辑于2026.11.7"),
        ("h2", "什么是 Math2Geo"),
        ("p", "Math2Geo 是一个通过上传题目内容（支持 Word 文档以及图片）得到题目相关图像的数学工具。图像可选择通过 GeoGebra 或几何画板输出（几何画板尚未充分测试），其中 GeoGebra 的流程更完善：\n\n直接打开输出文件夹里的 html 文件即可，只需要浏览器，无需安装 GeoGebra。"),
        ("h2", "工作原理"),
        ("p", "上传题目 → AI 理解 → 自动作图 → GeoGebra / 几何画板\n\n本软件支持调用本地模型或云端 API 来处理数学题目并绘制几何图像。正常情况下，本地模型的处理效率与最终输出质量远不及云端模型，因此建议优先选择云端 API。"),
        ("p", "AI 通过预设的文字要求直接输出作图方案，实测每轮对话约 30 秒甚至更短，消耗的 token 量在 5000–6000 不等（token 预算可设置），费用约 0.01–0.02 元（以 deepseek-flash 为例）。"),
        ("h2", "如何使用"),
        ("p", "选择一个中意的模型供应商（推荐深度求索的 DeepSeek 模型；价格较低，思维缜密，逻辑通透，整体质量尚可）\n\n以 DeepSeek 为例："),
        ("img", "image01.jpg"),
        ("li", "点击进入模型的 API 开放平台，注册并登录账号，选择充值余额；"),
        ("img", "image02.jpg"),
        ("li", "充值完成后点击「API Keys」，选择「创建 API Keys」，随意输入一个名字（例如 Math2Geo）；"),
        ("img", "image03.jpg"),
        ("li", "复制 Key，粘贴到 Math2Geo 的 API Key 一栏；"),
        ("img", "image04.jpg"),
        ("warn", "⚠注意⚠\n\n API Key 是非常重要的个人财产，必须保管好，不能让其他人看到，否则可能被盗用并消耗你的 token。\n\n如果在班级等公共环境使用，可以连续点击 3 次「教室模式」锁死环境变量，再给「用户 API 配置」设置密码。这样在不知道密码的情况下可以极大程度保护你的 API Key。\n\n但由于配置终究要写到本地，这种方法只防君子不防小人。如果发现 API 调用异常，很可能是 Key 被盗用，请立即删除该 Key。"),
        ("img", "image05.jpg"),
        ("p", "其余供应商的操作大致相同，但需要进入对应模型文档查看模型名称与 API 地址，填入相应栏目。"),
        ("img", "image06.jpg"),
        ("img", "image07.jpg"),
        ("img", "image09.jpg"),
        ("note", "配置好 API 后即可使用 AI 绘图。其中可以到「其他设置」中修改文件输出目录，在「绘制区域」选择上传题目或是拖拽题目文件至上传区，也可以选择隐藏程序窗口并截图（可自定义热键）上传，点击右下角的「开始绘制」即可。\n\n绘制完成会直接输出文件，日志区域可以看到耗费时间、消耗 token 与预估费用；右侧「已完成任务」可以直接打开文件或文件夹。\n\n注：输出文件夹名称取自题目图片原本的名称。"),
        ("img", "image10.jpg"),
        ("p", "此外，可以在「题目设置」的「作图提示词」中增加作图具体需求。但不建议随意在此更改作图规则，若不小心更改导致绘制功能无法正常使用，可以点击「恢复默认」"),
        ("img", "image15.png"),
        ("p", "若需要绘制立体几何类的题目，可在「绘图设置」中勾选「三维（空间直角坐标系）」或在「绘图区域」上传栏目右上角快速切换；勾选「二维（平面直角坐标系）」则默认以斜二测画法输出，勾选则使用 3D 绘图绘制。"),
        ("img", "image16.png"),
        ("p", "输出的 html 文件中，左半部分是原生的 GeoGebra 作图区，上方显示题目内容，难度系数，突破点等可选内容（需在「题目设置」打开），右侧为解答步骤，下方可以复制命令至 GeoGebra。"),
        ("img", "image18.png"),
        ("p", "在 3D 绘图的输出文件中可以选择隐藏/显示坐标轴，控制旋转截面，同样可以复制指令至 GeoGebra（Beta）。"),
        ("img", "image17.png"),
        ("h2", "常见问题"),
        ("p", "Temperature：模型回答时的语气，数值越高越有人情味，越容易犯错。"),
        ("p", "最大输出 token：每次任务的 token 上限。"),
        ("p", "请求超时：允许单次通信的最长时间。"),
        ("p", "高峰 / 低谷单价：目前仅限 DeepSeek ，按不同时间段收费。（其他模型暂未设置不同时段收费）"),
        ("img", "image11.jpg"),
        ("p", "DPI：图片清晰度，数值越高越清晰。"),
        ("img", "image12.jpg"),
        ("p", "动画：启动加载页面与标题「Math2Geo」的矢量动画。"),
        ("p", "缓存：Python 运行时产生的临时文件，不会清理清理已输出的题目且不影响正常使用。"),
        ("img", "image13.jpg"),
        ("qa", ("显示输出不合法怎么办？", "多半是模型抽风，多试几次。")),
        ("qa", ("无法打开 GitHub？", "可以先稍后再试；如果持续无法访问，可使用 Watt Toolkit 加速 GitHub 连接。")),
        ("h2", "API 连接错误码"),
        ("p", "点击「测试连接」时，程序会按 HTTP 状态码给出对应说明："),
        ("table", (
            ["HTTP 状态码", "含义", "处理建议"],
            [
                ["200", "连接成功", "API 可访问"],
                ["400", "请求参数错误", "检查模型名、Base URL 与请求参数"],
                ["401", "API Key 无效或未授权", "重新填写/确认 API Key"],
                ["403", "无权限或额度不足", "检查账户权限与余额"],
                ["404", "Base URL / 路径错误", "检查地址，通常以 /v1 结尾"],
                ["408", "请求超时", "增大超时时间或重试"],
                ["429", "频率限制或额度用尽", "稍后重试，或检查额度"],
                ["500/502/503/504", "服务端 / 网关错误", "稍后重试，或更换服务商"],
                ["无 HTTP 码", "网络异常", "检查网络、代理或 DNS"],
            ],
        )),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("帮助文档")
        self.setMinimumSize(1000, 760)
        if parent is not None:
            self.setWindowIcon(parent.windowIcon())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._text_labels: list[tuple[QLabel, float, str, int, int]] = []
        self._image_labels: list[tuple[QLabel, QPixmap]] = []
        self.text_scale = 1.0
        self.image_width = 850

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(20, 8, 20, 0)
        toolbar.setSpacing(6)
        toolbar.addStretch(1)

        def tool_button(text, slot):
            button = QPushButton(text)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFixedSize(42, 26)
            button.setStyleSheet(
                "QPushButton { background:#FFFFFF; border:1px solid #D9E8DE; border-radius:8px;"
                " padding:0; color:#223A2E; font-size:13px; }"
                "QPushButton:hover { background:#F2FAF5; }"
            )
            button.clicked.connect(slot)
            return button

        toolbar.addWidget(QLabel("文字"))
        toolbar.addWidget(tool_button("A−", lambda: self._change_text(-0.1)))
        self.text_status = QLabel("100%")
        self.text_status.setFixedWidth(44)
        self.text_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toolbar.addWidget(self.text_status)
        toolbar.addWidget(tool_button("A+", lambda: self._change_text(0.1)))
        toolbar.addSpacing(14)

        toolbar.addWidget(QLabel("图片"))
        toolbar.addWidget(tool_button("−", lambda: self._change_image(-50)))
        self.image_status = QLabel("850px")
        self.image_status.setFixedWidth(56)
        self.image_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toolbar.addWidget(self.image_status)
        toolbar.addWidget(tool_button("+", lambda: self._change_image(50)))
        toolbar.addSpacing(14)

        reset = QPushButton("重置")
        reset.setCursor(Qt.CursorShape.PointingHandCursor)
        reset.setFixedSize(52, 26)
        reset.setStyleSheet(
            "QPushButton { background:#FFFFFF; border:1px solid #D9E8DE; border-radius:8px;"
            " padding:0; color:#223A2E; font-size:13px; }"
            "QPushButton:hover { background:#F2FAF5; }"
        )
        reset.clicked.connect(self._reset_view)
        toolbar.addWidget(reset)
        outer.addLayout(toolbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: #FFFFFF; border: none; }")
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        content = QWidget()
        content.setStyleSheet("background: #FFFFFF;")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(36, 28, 36, 28)
        lay.setSpacing(10)

        for kind, payload in self.BLOCKS:
            if kind == "h1":
                self._add_label(lay, payload, 22, "#0F3D2E", 700)
            elif kind == "sub":
                self._add_label(lay, payload, 11, "#5D6B63", 400)
                lay.addSpacing(8)
            elif kind == "h2":
                lay.addSpacing(14)
                self._add_label(lay, payload, 16, "#1F5C46", 700)
                line = QFrame()
                line.setFixedHeight(1)
                line.setStyleSheet("background: #D9E8DE;")
                lay.addWidget(line)
            elif kind == "p":
                self._add_label(lay, payload, 11, "#223A2E", 400)
            elif kind == "li":
                self._add_label(lay, "•  " + payload, 11, "#223A2E", 400, indent=14)
            elif kind in ("warn", "note"):
                lay.addWidget(self._make_callout(payload, kind))
            elif kind == "img":
                self._add_image(lay, payload)
            elif kind == "table":
                headers, rows = payload
                table = QTableWidget(len(rows), len(headers))
                table.setHorizontalHeaderLabels(headers)
                table.verticalHeader().setVisible(False)
                table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
                table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
                table.setShowGrid(True)
                table.setStyleSheet(
                    "QTableWidget { background:#FFFFFF; border:1px solid #D9E8DE;"
                    " border-radius:8px; gridline-color:#E6EFE8; }"
                    "QHeaderView::section { background:#F2FAF5; color:#1F5C46;"
                    " font-weight:700; border:none; padding:7px; }"
                )
                table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
                table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
                for r, row in enumerate(rows):
                    for c, value in enumerate(row):
                        item = QTableWidgetItem(str(value))
                        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                        table.setItem(r, c, item)
                table.setMinimumHeight(36 * (len(rows) + 1) + 8)
                lay.addWidget(table)

            elif kind == "qa":
                q, a = payload[0], payload[1]
                extra = payload[2] if len(payload) > 2 else ()
                images = [extra] if isinstance(extra, str) else list(extra)
                self._add_label(lay, "Q：" + q, 11, "#0F3D2E", 700)
                for name in images:
                    self._add_image(lay, name)
                self._add_label(lay, "A：" + a, 11, "#4A5B52", 400)

        lay.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(20, 10, 20, 14)
        footer.addStretch(1)
        close = QPushButton("关闭")
        close.setObjectName("Ghost")
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        outer.addLayout(footer)

    def _add_label(self, lay, text, size, color, weight, indent=0) -> None:
        label = self._make_label(text, size, color, weight, indent)
        self._text_labels.append((label, float(size), color, weight, indent))
        lay.addWidget(label)

    def _add_image(self, lay, filename: str) -> None:
        path = os.path.join(ASSET_DIR, "help", filename)
        pix = QPixmap(path)
        if pix.isNull():
            return
        image = QLabel()
        image.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        image.setPixmap(
            pix.scaledToWidth(self.image_width, Qt.TransformationMode.SmoothTransformation)
        )
        image.setStyleSheet("background: transparent; padding: 4px 0;")
        self._image_labels.append((image, pix))
        lay.addWidget(image)

    def _change_text(self, delta: float) -> None:
        self.text_scale = max(0.8, min(1.5, round(self.text_scale + delta, 2)))
        self.text_status.setText(f"{int(round(self.text_scale * 100))}%")
        for label, size, color, weight, indent in self._text_labels:
            label.setStyleSheet(self._label_style(size * self.text_scale, color, weight, indent))

    def _change_image(self, delta: int) -> None:
        self.image_width = max(500, min(900, self.image_width + delta))
        self.image_status.setText(f"{self.image_width}px")
        for label, pix in self._image_labels:
            label.setPixmap(
                pix.scaledToWidth(self.image_width, Qt.TransformationMode.SmoothTransformation)
            )

    def _reset_view(self) -> None:
        self.text_scale = 1.0
        self.image_width = 850
        self.text_status.setText("100%")
        self.image_status.setText("850px")
        for label, size, color, weight, indent in self._text_labels:
            label.setStyleSheet(self._label_style(size, color, weight, indent))
        for label, pix in self._image_labels:
            label.setPixmap(
                pix.scaledToWidth(850, Qt.TransformationMode.SmoothTransformation)
            )

    @staticmethod
    def _label_style(size: float, color: str, weight: int, indent: int) -> str:
        return (
            f"color: {color}; background: transparent; font-size: {size:.1f}pt;"
            f" font-weight: {'bold' if weight >= 600 else 'normal'}; padding-left: {indent}px;"
        )

    @staticmethod
    def _make_label(text, size, color, weight, indent=0):
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setStyleSheet(HelpDialog._label_style(size, color, weight, indent))
        return label

    def _make_callout(self, text, kind):
        frame = QFrame()
        if kind == "warn":
            frame.setStyleSheet(
                "QFrame { background: #FFF4E5; border-left: 4px solid #E0A040; border-radius: 8px; }"
            )
        else:
            frame.setStyleSheet(
                "QFrame { background: #F1F8F3; border-left: 4px solid #8FD3A8; border-radius: 8px; }"
            )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 12, 16, 12)
        label = QLabel(text)
        label.setWordWrap(True)
        color = "#4A3A22" if kind == "warn" else "#223A2E"
        label.setStyleSheet(HelpDialog._label_style(11, color, 400, 0))
        self._text_labels.append((label, 11.0, color, 400, 0))
        lay.addWidget(label)
        return frame




class SectionDirectionPreview(QWidget):
    """显示空间截面法向量的小预览。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.azimuth = 35.0
        self.elevation = 20.0
        self.setMinimumSize(210, 150)
        self.setMaximumHeight(150)

    def set_angles(self, azimuth: float, elevation: float) -> None:
        self.azimuth = azimuth
        self.elevation = elevation
        self.update()

    @staticmethod
    def _project(x: float, y: float, z: float) -> tuple[float, float]:
        return (x - y) * 0.78, z - (x + y) * 0.38

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#FBFDFC"))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)

        cx = self.width() / 2
        cy = self.height() / 2 + 8
        radius = min(self.width(), self.height()) * 0.34

        # 球体参考线
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(QColor("#D9E8DE"))
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.drawEllipse(QPointF(cx, cy), radius, radius * 0.48)
        painter.drawEllipse(QPointF(cx, cy), radius * 0.48, radius)

        def draw_axis(vx, vy, vz, color, label):
            px, py = self._project(vx, vy, vz)
            painter.setPen(QPen(QColor(color), 1.4))
            painter.drawLine(QPointF(cx, cy), QPointF(cx + px * radius, cy - py * radius))
            painter.setPen(QColor(color))
            f = painter.font()
            f.setPointSize(8)
            painter.setFont(f)
            painter.drawText(QPointF(cx + px * radius * 1.12 - 3, cy - py * radius * 1.12 + 3), label)

        draw_axis(1, 0, 0, "#C06A5A", "x")
        draw_axis(0, 1, 0, "#5A8FC0", "y")
        draw_axis(0, 0, 1, "#4E8C68", "z")

        az = math.radians(self.azimuth)
        el = math.radians(self.elevation)
        nx = math.cos(el) * math.cos(az)
        ny = math.cos(el) * math.sin(az)
        nz = math.sin(el)
        px, py = self._project(nx, ny, nz)
        end = QPointF(cx + px * radius, cy - py * radius)
        painter.setPen(QPen(QColor("#1F5C46"), 2.2))
        painter.drawLine(QPointF(cx, cy), end)
        painter.setBrush(QColor("#1F5C46"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(end, 4.2, 4.2)
        painter.setBrush(QColor("#8FD3A8"))
        painter.drawEllipse(QPointF(cx, cy), 3.2, 3.2)


class AnimatedCombo(QComboBox):
    """下拉框：展开淡入，收回淡出，避免只有展开动画。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._closing = False
        self._popup_anim = None

    def showPopup(self) -> None:
        super().showPopup()
        popup = self.view().window()
        popup.setWindowOpacity(0.0)
        anim = QPropertyAnimation(popup, b"windowOpacity", self)
        anim.setDuration(120)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start()
        self._popup_anim = anim

    def hidePopup(self) -> None:
        if self._closing:
            return
        popup = self.view().window()
        if not popup.isVisible():
            super().hidePopup()
            return
        self._closing = True
        anim = QPropertyAnimation(popup, b"windowOpacity", self)
        anim.setDuration(120)
        anim.setStartValue(popup.windowOpacity())
        anim.setEndValue(0.0)
        anim.finished.connect(self._finish_hide)
        anim.start()
        self._popup_anim = anim

    def _finish_hide(self) -> None:
        self._closing = False
        super().hidePopup()



def default_plan_prompt() -> str:
    path = os.path.join(os.path.dirname(__file__), "templates", "plan_prompt.txt")
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return "你是数学作图助手，读题后输出作图方案 JSON。"


class PromptDialog(QDialog):
    """编辑作图提示词；修改未保存时关闭会提示。"""

    def __init__(self, parent, cfg: dict):
        super().__init__(parent)
        self.cfg = cfg
        self.default_text = default_plan_prompt()
        self.original_text = (cfg["problem"].get("prompt") or "").strip() or self.default_text
        self._dirty = False

        self.setWindowTitle("编辑作图提示词")
        self.setMinimumSize(900, 720)
        if parent is not None:
            self.setWindowIcon(parent.windowIcon())

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 16)
        lay.setSpacing(10)

        title = QLabel("作图提示词")
        title.setStyleSheet("font-size:16px; font-weight:700; color:#0F3D2E;")
        lay.addWidget(title)
        tip = QLabel("发送给模型的系统提示词。保存后仅本机生效；点击「恢复默认」可还原模板。")
        tip.setObjectName("Hint")
        tip.setWordWrap(True)
        lay.addWidget(tip)

        self.editor = QPlainTextEdit()
        self.editor.setPlainText(self.original_text)
        self.editor.setFont(QFont("Consolas", 10))
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.editor.setStyleSheet(
            "QPlainTextEdit { background:#FBFDFC; border:1px solid #D9E8DE; border-radius:10px;"
            " padding:10px; color:#223A2E; font-size:12px; }"
        )
        self.editor.textChanged.connect(self._on_changed)
        lay.addWidget(self.editor, 1)

        row = QHBoxLayout()
        restore = QPushButton("恢复默认")
        restore.setObjectName("Ghost")
        restore.clicked.connect(self._restore_default)
        row.addWidget(restore)
        row.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(self.reject)
        save = QPushButton("保存")
        save.setObjectName("Primary")
        save.clicked.connect(self._save)
        row.addWidget(cancel)
        row.addWidget(save)
        lay.addLayout(row)

    def _on_changed(self) -> None:
        self._dirty = self.editor.toPlainText().strip() != self.original_text.strip()

    def _restore_default(self) -> None:
        self.editor.setPlainText(self.default_text)
        self.editor.setFocus()

    def _save(self) -> None:
        text = self.editor.toPlainText()
        if not text.strip() or text.strip() == self.default_text.strip():
            self.cfg["problem"]["prompt"] = ""
        else:
            self.cfg["problem"]["prompt"] = text
        save_config(self.cfg)
        self.original_text = text
        self._dirty = False
        super().done(QDialog.DialogCode.Accepted)

    def done(self, result: int) -> None:
        if result == QDialog.DialogCode.Rejected and self._dirty:
            answer = QMessageBox.question(
                self,
                "提示词未保存",
                "提示词有未保存的修改，是否保存？",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if answer == QMessageBox.StandardButton.Cancel:
                return
            if answer == QMessageBox.StandardButton.Save:
                self._save()
                return
        super().done(result)


class WinButton(QPushButton):
    """标题栏右上角的自绘按钮（最小化 / 最大化 / 还原 / 关闭）。"""

    def __init__(self, kind: str = "max", parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(46, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setObjectName("WinBtn")
        self.setToolTip({"min": "最小化", "max": "最大化", "restore": "还原", "close": "关闭"}.get(kind, ""))

    def set_kind(self, kind: str) -> None:
        if kind != self.kind:
            self.kind = kind
            self.update()

    def enterEvent(self, event) -> None:
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        hover = self.underMouse()
        close = self.kind == "close"
        if close and hover:
            bg, fg = QColor("#C42B1C"), QColor("#FFFFFF")
        elif hover:
            bg, fg = QColor("#E9E9E9"), QColor("#1A1A1A")
        else:
            bg, fg = QColor(0, 0, 0, 0), QColor("#1A1A1A")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRect(self.rect())

        pen = QPen(fg)
        pen.setWidthF(1.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        cx = self.width() / 2
        cy = self.height() / 2
        half = 5.0
        if self.kind == "min":
            painter.drawLine(QPointF(cx - half, cy), QPointF(cx + half, cy))
        elif self.kind == "max":
            painter.drawRoundedRect(QRectF(cx - half, cy - half, half * 2, half * 2), 1.0, 1.0)
        elif self.kind == "restore":
            painter.drawRoundedRect(QRectF(cx - half + 2.5, cy - half - 2.5, half * 2 - 1.5, half * 2 - 1.5), 1.0, 1.0)
            painter.drawRoundedRect(QRectF(cx - half - 1.5, cy - half + 2.5, half * 2 - 1.5, half * 2 - 1.5), 1.0, 1.0)
        else:
            painter.drawLine(QPointF(cx - half, cy - half), QPointF(cx + half, cy + half))
            painter.drawLine(QPointF(cx + half, cy - half), QPointF(cx - half, cy + half))


class PanelGrips(QObject):
    """给一个卡片装四个角上的拖拽点，拖动任一个都能拉伸对应分栏。"""

    def __init__(self, card: QWidget, splitter, axis: str, invert: bool = False):
        super().__init__(card)
        self.card = card
        self.splitter = splitter
        self.axis = axis
        self.invert = invert
        self.base = None
        cursor = Qt.CursorShape.SizeVerCursor if axis == "v" else Qt.CursorShape.SizeHorCursor
        self.handles = []
        for _ in range(4):
            grip = GripHandle(cursor, card)
            grip.pressed.connect(self._on_press)
            grip.dragged.connect(self._on_drag)
            self.handles.append(grip)
        card.installEventFilter(self)
        self.relayout()

    def eventFilter(self, obj, event) -> bool:
        if obj is self.card and event.type() == QEvent.Type.Resize:
            self.relayout()
        return False

    def relayout(self) -> None:
        w, h = self.card.width(), self.card.height()
        size = 12
        points = [(3, 3), (w - size - 3, 3), (3, h - size - 3), (w - size - 3, h - size - 3)]
        for grip, (x, y) in zip(self.handles, points):
            grip.setFixedSize(size, size)
            grip.move(x, y)
            grip.raise_()
            grip.show()

    def _on_press(self) -> None:
        self.base = self.splitter.sizes()

    def _on_drag(self, dx: int, dy: int) -> None:
        base = self.base
        if not base or len(base) < 2:
            return
        delta = dy if self.axis == "v" else dx
        if self.invert:
            delta = -delta
        total = sum(base)
        first = max(150, min(base[0] + delta, total - 200))
        self.splitter.setSizes([first, total - first])


def _arrow_icon() -> str:
    path = os.path.join(tempfile.gettempdir(), "math2geo_arrow.png")
    if os.path.exists(path):
        return path
    pm = QPixmap(14, 10)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor("#33503F"))
    pen.setWidthF(1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawLine(2, 3, 7, 8)
    p.drawLine(7, 8, 12, 3)
    p.end()
    pm.save(path)
    return path

class Toast(QWidget):
    """右上角完成提示：从右向左滑入，底部倒计时条，结束后向上隐退。"""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("Toast")
        self.setFixedSize(340, 96)
        self.hide()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 10)
        outer.setSpacing(4)
        self.title = QLabel("绘制完成")
        self.title.setStyleSheet("font-size:14px; font-weight:700; color:#0F3D2E;")
        self.body = QLabel("")
        self.body.setStyleSheet("font-size:12px; color:#5D6B63;")
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(4)
        self.bar.setRange(0, 1000)
        self.bar.setValue(1000)
        outer.addWidget(self.title)
        outer.addWidget(self.body)
        outer.addWidget(self.bar)

        self.setStyleSheet(
            "QWidget#Toast { background:#FFFFFF; border:1px solid #CFE6D8; border-left:4px solid #1F5C46;"
            " border-radius:12px; }"
            "QProgressBar { background:#E8F3EC; border:none; border-radius:2px; }"
            "QProgressBar::chunk { background:#1F5C46; border-radius:2px; }"
        )
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(15, 61, 46, 60))
        self.setGraphicsEffect(shadow)

    def show_message(self, title: str, body: str, seconds: float = 4.0) -> None:
        self.setGraphicsEffect(None)
        self.title.setText(title)
        self.body.setText(body)
        parent = self.parentWidget()
        w = parent.width()
        start = QPoint(w + 10, 70)
        end = QPoint(w - self.width() - 22, 70)
        self.move(start)
        self.show()
        self.raise_()

        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(340)
        self._anim.setStartValue(start)
        self._anim.setEndValue(end)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

        self.bar.setRange(0, 1000)
        self.bar.setValue(1000)
        self._bar_anim = QPropertyAnimation(self.bar, b"value", self)
        self._bar_anim.setDuration(int(seconds * 1000))
        self._bar_anim.setStartValue(1000)
        self._bar_anim.setEndValue(0)
        self._bar_anim.start()
        QTimer.singleShot(int(seconds * 1000), self._hide_up)

    def _hide_up(self) -> None:
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(260)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        anim.finished.connect(self.hide)
        anim.start()
        self._out = anim



class Splash(QWidget):
    """启动动画：无边框小窗，播放 assets/intro.webp；可点击跳过。"""

    finished = Signal()

    def __init__(self, speed: float = 1.0):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(692, 449)
        self.setWindowTitle("Math2Geo")
        self.setStyleSheet(
            "QFrame#SplashCard { background: transparent; border: none; }"
        )
        card = QFrame(self)
        card.setObjectName("SplashCard")
        card.setGeometry(0, 0, 692, 449)
        label = QLabel(card)
        label.setGeometry(16, 16, 660, 383)
        self.movie = QMovie(INTRO_WEBP)
        self.movie.setCacheMode(QMovie.CacheMode.CacheNone)
        self.movie.setSpeed(max(20, int(speed * 100)))
        self.movie.setScaledSize(QSize(660, 383))
        label.setMovie(self.movie)
        hint = QLabel("双击任意位置跳过 · 可在设置里调整倍速", card)
        hint.setStyleSheet("background: transparent; color: #8A9A91; font-size: 11px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setGeometry(16, 402, 660, 30)
        self._closing = False
        self._finish_pending = False
        self._deadline = time.monotonic() + 30

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#D9E8DE"), 1.0))
        painter.setBrush(QColor("#FBF9F5"))
        painter.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 12, 12)

    def show_centered(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(geo.center() - self.rect().center())
        self.show()
        self.movie.start()
        self.movie.frameChanged.connect(self._maybe_finish)
        QTimer.singleShot(200, self._check_finish)

    def _maybe_finish(self, frame: int) -> None:
        if frame >= self.movie.frameCount() - 1 and not self._finish_pending:
            self._finish_pending = True
            QTimer.singleShot(600, self._finish)

    def _check_finish(self) -> None:
        if self._closing:
            return
        if self.movie.currentFrameNumber() >= self.movie.frameCount() - 1:
            self._maybe_finish(self.movie.currentFrameNumber())
            return
        if time.monotonic() > self._deadline:
            self._finish()
            return
        QTimer.singleShot(120, self._check_finish)

    def _finish(self) -> None:
        if self._closing:
            return
        self._closing = True
        self.movie.stop()
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(180)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)

        def done() -> None:
            self.close()
            self.finished.emit()

        anim.finished.connect(done)
        anim.start()
        self._fade = anim

    def mouseDoubleClickEvent(self, event) -> None:
        self._finish()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._finish()
        else:
            super().keyPressEvent(event)



class ConnectionTester(QThread):
    done = Signal(bool, int, str)

    def __init__(self, base_url: str, key: str, provider: str, parent=None):
        super().__init__(parent)
        self.base_url = base_url.rstrip("/")
        self.key = key
        self.provider = provider

    def run(self) -> None:
        try:
            import requests

            headers = {"Authorization": f"Bearer {self.key}"}
            if "Anthropic" in self.provider or "Claude" in self.provider:
                headers = {"x-api-key": self.key, "anthropic-version": "2023-06-01"}
            url = self.base_url + "/models"
            resp = requests.get(url, headers=headers, timeout=10)
            self.done.emit(resp.status_code < 400, resp.status_code, resp.text[:300])
        except Exception as exc:  # noqa: BLE001
            self.done.emit(False, 0, f"{type(exc).__name__}: {exc}")


class Worker(QThread):
    log = Signal(str)
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, kwargs: dict):
        super().__init__()
        self.kwargs = kwargs

    def run(self) -> None:
        try:
            result = pipeline.run(log=self.log.emit, **self.kwargs)
            self.done.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


# ------------------------------------------------------------------ 主窗口


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.setWindowTitle("Math2Geo")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self._native_frame = True
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMinimumSize(760, 540)
        screen = QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            width = min(1180, max(900, area.width() - 100))
            height = min(900, max(640, area.height() - 100))
        else:
            width, height = 1180, 900
        self.resize(width, height)
        self._restore_max = False
        self._restore_geometry()
        self._intro_played = False
        self._geo_anim = None
        self._minimizing = False
        self._suppress_min = False
        self._restore_geo = None
        self._zoom_shot = None
        self._classroom_count = 0
        self._capture_overlay = None
        self._applying_config = False
        self._tray_icon = None
        self._mci_alias = "math2geo_sound"
        self._hotkey_id = 0x4D32
        self._hotkey_filter = HotkeyFilter(self._on_global_hotkey)
        _qapp = QApplication.instance()
        if _qapp is not None:
            _qapp.installNativeEventFilter(self._hotkey_filter)
        self._classroom_last = 0.0
        self._last_provider_index = 0
        self._drag_pos = None
        self._resizing = False
        self._resize_edges = Qt.Edge(0)
        self._resize_geo = None
        self._resize_global = None
        self.worker: Worker | None = None
        self.current_file = ""
        self.tasks: list[dict] = []

        icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setObjectName("Root")
        self.setFont(QFont("Microsoft YaHei UI", 9))
        self.setStyleSheet(self._qss())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._outer = outer

        self.shell = Shell()
        outer.addWidget(self.shell)

        shell_lay = QVBoxLayout(self.shell)
        shell_lay.setContentsMargins(0, 0, 0, 0)
        shell_lay.setSpacing(0)

        body = QVBoxLayout()
        body.setContentsMargins(20, 16, 20, 18)
        body.setSpacing(12)
        shell_lay.addLayout(body, 1)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.addStretch(1)
        right_col = QVBoxLayout()
        right_col.setSpacing(8)
        self.help_btn = QPushButton("?  帮助文档")
        self.help_btn.setObjectName("Ghost")
        self.help_btn.setFixedHeight(32)
        self.help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.help_btn.setToolTip("打开帮助文档（F1）")
        self.help_btn.clicked.connect(self._show_help)
        right_col.addWidget(self.help_btn)
        self.repo_btn = QPushButton("前往仓库")
        self.repo_btn.setObjectName("Ghost")
        self.repo_btn.setFixedHeight(32)
        self.repo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.repo_btn.setToolTip("前往 GitHub 仓库")
        self.repo_btn.clicked.connect(self._open_repo)
        right_col.addWidget(self.repo_btn)
        top_row.addLayout(right_col)
        body.addLayout(top_row)

        welcome = QLabel()
        welcome.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        welcome.setCursor(Qt.CursorShape.PointingHandCursor)
        welcome.installEventFilter(self)
        self.welcome = welcome
        self._title_end = QPixmap(TITLE_END_PNG)
        self._title_ratio = (
            self._title_end.width() / self._title_end.height()
            if not self._title_end.isNull()
            else 800 / 148
        )
        self.title_movie = None
        movie = QMovie(TITLE_WEBP)
        if movie.isValid():
            movie.setCacheMode(QMovie.CacheMode.CacheNone)
            movie.finished.connect(self._on_title_finished)
            movie.frameChanged.connect(self._maybe_title_done)
            self.title_movie = movie
        self._title_played = False
        self._title_done = False
        if self._title_end.isNull() and self.title_movie is None:
            welcome.setText("Welcome to Math2Geo !")
            welcome.setObjectName("Welcome")
        body.addWidget(welcome)

        body.addLayout(self._tabs())

        self.stack = QStackedWidget()
        self.stack.addWidget(self._page_draw())
        self.stack.addWidget(self._scroll_page(self._page_model()))
        self.stack.addWidget(self._scroll_page(self._page_problem()))
        self.stack.addWidget(self._scroll_page(self._page_draw_settings()))
        self.stack.addWidget(self._scroll_page(self._page_other()))
        body.addWidget(self.stack, 1)
        body.addLayout(self._footer())

        self.toast = Toast(self)
        QApplication.instance().installEventFilter(self)
        self._apply_config()
        self.log("系统初始化完成")
        self.log("等待上传题目…")
        QShortcut(QKeySequence("F1"), self, activated=self._show_help)
        QTimer.singleShot(60, lambda: self._fade_in(self.stack.widget(0), 320))
        self._update_welcome()

    # ---------- 样式

    def _qss(self) -> str:
        tick = _tick_icon().replace("\\", "/")
        arrow = _arrow_icon().replace("\\", "/")
        return f"""
        QWidget#Root {{ background: #F3F8F4; }}
        QFrame#Shell {{ background: transparent; border: none; }}
        QWidget {{ font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI"; }}
        QLabel {{ color: {VERSE['ink']}; font-size: 12px; }}
        QLabel#Welcome {{ font-size: 34px; font-weight: 800; color: {VERSE['ink']}; }}
        QLabel#Hint {{ color: {VERSE['muted']}; font-size: 12px; }}
        QLabel#Section {{ color: {VERSE['ink']}; font-size: 15px; font-weight: 700; }}
        QFrame#Card {{ background: #FFFFFF; border: 1px solid {VERSE['border']}; border-radius: 14px; }}
        QFrame#Sheet {{ background: #FFFFFF; border: 1px solid {VERSE['border']}; border-radius: 16px; }}
        QFrame#Sheet QFrame#Card {{ background: transparent; border: none; }}
        QFrame#Header {{ background: #F3F3F3; border-bottom: 1px solid #E5E5E5; }}
        QPushButton#Tab {{ background: #FFFFFF; border: 1px solid {VERSE['border']}; border-radius: 12px;
                           padding: 8px 20px; color: #33503F; font-size: 12px; }}
        QPushButton#Tab:hover {{ background: #F2FAF5; }}
        QPushButton#Tab:checked {{ background: {VERSE['tab_active']}; border-color: #8FC9A4;
                                   color: {VERSE['ink']}; font-weight: 700; }}
        QPushButton#WinBtn {{ background: transparent; border: none; }}
        QPushButton#Primary {{ background: {VERSE['main']}; color: #FFFFFF; border: none; border-radius: 10px;
                               padding: 10px 26px; font-size: 12px; font-weight: 700; }}
        QPushButton#Primary:hover {{ background: #2A6F55; }}
        QPushButton#Primary:disabled {{ background: #A9C7B7; }}
        QPushButton#Ghost {{ background: #FFFFFF; border: 1px solid {VERSE['border']}; border-radius: 10px;
                             padding: 9px 18px; color: {VERSE['ink']}; }}
        QPushButton#Ghost:hover {{ background: #F2FAF5; }}
        QComboBox::down-arrow {{ image: url("{arrow}"); width: 12px; height: 8px; }}
        QComboBox::drop-down {{ border: none; background: transparent; width: 24px;
                                border-top-right-radius: 10px; border-bottom-right-radius: 10px; }}
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTimeEdit {{
            background: #FBFDFC; border: 1px solid {VERSE['border']}; border-radius: 10px;
            padding: 7px 10px; color: #223A2E; font-size: 12px; selection-background-color: #A8D8B9;
        }}
        QCheckBox {{ spacing: 8px; color: #223A2E; font-size: 12px; }}
        QRadioButton {{ spacing: 8px; color: #223A2E; font-size: 12px; }}
        QRadioButton::indicator {{ width: 16px; height: 16px; border-radius: 8px;
                                   border: 1px solid #B9D3C3; background: #FFFFFF; }}
        QRadioButton::indicator:checked {{ background: #FFFFFF; border: 5px solid {VERSE['main']}; }}
        QSlider::groove:horizontal {{ height: 4px; background: #E3EFE8; border-radius: 2px; }}
        QSlider::sub-page:horizontal {{ background: #8FD3A8; border-radius: 2px; }}
        QSlider::add-page:horizontal {{ background: #E3EFE8; border-radius: 2px; }}
        QSlider::handle:horizontal {{ width: 14px; margin: -5px 0; border-radius: 7px;
                                      background: {VERSE['main']}; }}
        QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid #B9D3C3;
                                background: #FFFFFF; }}
        QCheckBox::indicator:checked {{ background: {VERSE['main']}; border-color: {VERSE['main']}; image: url("{tick}"); }}
        QSpinBox::up-button, QDoubleSpinBox::up-button {{
            subcontrol-origin: border; subcontrol-position: top right; width: 18px; border: none; }}
        QSpinBox::down-button, QDoubleSpinBox::down-button {{
            subcontrol-origin: border; subcontrol-position: bottom right; width: 18px; border: none; }}
        QScrollArea {{ border: none; background: transparent; }}
        QScrollBar:vertical {{ width: 6px; background: transparent; }}
        QScrollBar::handle:vertical {{ background: #CFE3D6; border-radius: 4px; min-height: 30px; }}
        QSplitter::handle {{ background: transparent; }}
        QSplitter::handle:hover {{ background: transparent; }}
        QSplitter::handle:pressed {{ background: transparent; }}
        QFrame#ModeSwitch {{ background: #FFFFFF; border: 2px solid #8FC9A4; border-radius: 12px; }}
        QFrame#ModeSwitch:hover {{ background: #F2FAF5; }}
        QLabel#ModeSwitchText {{ color: #1F5C46; font-size: 12px; font-weight: 800; border: none; }}
        QFrame#DropZone[drag="true"] {{ border-color: {VERSE['main']}; background: #EDF8F1; }}
        QProgressBar {{ background: #E8F3EC; border: none; border-radius: 3px; }}
        QProgressBar::chunk {{ background: {VERSE['main']}; border-radius: 3px; }}
        QSlider::groove:horizontal {{ height: 10px; border-radius: 5px; background: #DCEFE3; }}
        QSlider::sub-page:horizontal {{ background: {VERSE['main']}; border-radius: 5px; }}
        QSlider::add-page:horizontal {{ background: #DCEFE3; border-radius: 5px; }}
        QSlider::handle:horizontal {{ width: 18px; height: 18px; margin: -4px 0;
                                      border-radius: 9px; background: {VERSE['main']}; }}
        QScrollBar:horizontal {{ height: 10px; background: transparent; margin: 0 8px; }}
        QScrollBar::handle:horizontal {{ background: #CFE3D6; border-radius: 5px; min-width: 28px; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
        QScrollBar:vertical {{ width: 10px; background: transparent; margin: 8px 0; }}
        QScrollBar::handle:vertical {{ background: #CFE3D6; border-radius: 5px; min-height: 30px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """

    def _header(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("Header")
        bar.setFixedHeight(32)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 0, 0, 0)
        lay.setSpacing(6)

        logo = QLabel()
        icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.png")
        pix = QPixmap(icon_path)
        if not pix.isNull():
            logo.setPixmap(pix.scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            logo.setText("🌿")
        title = QLabel("Math2Geo")
        title.setStyleSheet("color:#1A1A1A; font-size:12px; font-weight:600;")
        lay.addWidget(logo)
        lay.addSpacing(4)
        lay.addWidget(title)
        lay.addStretch(1)
        self.min_btn = WinButton("min")
        self.min_btn.clicked.connect(self._animated_minimize)
        self.max_btn = WinButton("max")
        self.max_btn.clicked.connect(self._toggle_max)
        self.close_btn = WinButton("close")
        self.close_btn.clicked.connect(self.close)
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(0)
        for btn in (self.min_btn, self.max_btn, self.close_btn):
            btn_row.addWidget(btn)
        lay.addLayout(btn_row)
        return bar

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(243, 248, 244))
        painter.drawRect(self.rect())
        painter.end()

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.WindowStateChange:
            was_min = bool(event.oldState() & Qt.WindowState.WindowMinimized)
            now_min = bool(self.windowState() & Qt.WindowState.WindowMinimized)

            maxed = self.isMaximized()
            self._outer.setContentsMargins(0, 0, 0, 0)
            if hasattr(self, "max_btn"):
                self.max_btn.set_kind("restore" if maxed else "max")
            for w in (self.shell, self.shell.findChild(QFrame, "Header")):
                if w is None:
                    continue
                w.setProperty("max", maxed)
                w.style().unpolish(w)
                w.style().polish(w)
        super().changeEvent(event)

    def _open_repo(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("前往仓库")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(
            "<b>要前往 GitHub 仓库吗？</b><br><br>"
            f'<a href="{REPO_URL}">前往仓库</a><br><br>'
            '如果无法连接，可使用 '
            '<a href="https://steampp.net/">Watt Toolkit</a> 加速 GitHub。'
        )
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QMessageBox.StandardButton.No)
        box.button(QMessageBox.StandardButton.Yes).setText("前往仓库")
        box.button(QMessageBox.StandardButton.No).setText("取消")
        label = box.findChild(QLabel)
        if label is not None:
            label.setOpenExternalLinks(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        if box.exec() == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(QUrl(REPO_URL))

    def _show_help(self) -> None:
        dialog = HelpDialog(self)
        dialog.exec()

    def _restore_geometry(self) -> None:
        state = load_window_state()
        if not state:
            return
        try:
            rect = QRect(int(state["x"]), int(state["y"]), int(state["w"]), int(state["h"]))
        except Exception:
            return
        if rect.width() < self.minimumWidth() or rect.height() < self.minimumHeight():
            return
        screens = QApplication.screens()
        best = None
        best_area = 0
        for screen in screens:
            inter = screen.availableGeometry().intersected(rect)
            area = inter.width() * inter.height()
            if area > best_area:
                best, best_area = screen, area
        needed = max(1, rect.width() * rect.height())
        if best is None or best_area < needed * 0.2:
            rect.moveCenter(QApplication.primaryScreen().availableGeometry().center())
        else:
            avail = best.availableGeometry()
            if rect.width() > avail.width():
                rect.setWidth(avail.width())
            if rect.height() > avail.height():
                rect.setHeight(avail.height())
        self.setGeometry(rect)
        self._restore_max = bool(state.get("maximized"))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._restore_max:
            self._restore_max = False
            QTimer.singleShot(0, self.showMaximized)
        QTimer.singleShot(180, self._start_title_anim)

    def wants_splash(self) -> bool:
        return bool(self.cfg["other"].get("anim_startup", True)) and os.path.exists(INTRO_WEBP)

    def run(self) -> None:
        if self.wants_splash():
            speed = float(self.cfg["other"].get("anim_speed", 1.0) or 1.0)
            self._splash = Splash(speed=speed)
            self._splash.finished.connect(self._after_splash)
            self._splash.show_centered()
        else:
            self._prepare_entrance()
            self.show()
            self._start_entrance()

    def _after_splash(self) -> None:
        self._prepare_entrance()
        self.show()
        self.raise_()
        self.activateWindow()
        self._start_entrance()

    def _taskbar_target(self) -> QRect:
        screen = self.screen() or QApplication.primaryScreen()
        area = screen.availableGeometry()
        width, height = 180, 100
        cx = self.geometry().center().x()
        cx = max(area.left() + width // 2, min(cx, area.right() - width // 2))
        return QRect(cx - width // 2, area.bottom() - height, width, height)

    def _make_zoom_overlay(self) -> QLabel:
        overlay = QLabel(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        overlay.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        overlay.setScaledContents(True)
        overlay.setPixmap(self._zoom_shot)
        return overlay

    def _animated_minimize(self) -> None:
        if self._minimizing:
            return
        self._minimizing = True
        self._restore_geo = self.geometry()
        self._zoom_shot = self.grab()
        target = self._taskbar_target()

        overlay = self._make_zoom_overlay()
        overlay.setGeometry(self.geometry())
        overlay.show()
        self.setWindowOpacity(0.0)

        geo = QPropertyAnimation(overlay, b"geometry", self)
        geo.setDuration(210)
        geo.setStartValue(self.geometry())
        geo.setEndValue(target)
        geo.setEasingCurve(QEasingCurve.Type.InCubic)

        def done() -> None:
            overlay.close()
            self._minimizing = False
            self._suppress_min = True
            self.showMinimized()
            QTimer.singleShot(500, lambda: setattr(self, "_suppress_min", False))

        geo.finished.connect(done)
        geo.start()
        self._min_geo_anim = geo

    def _animated_restore(self) -> None:
        if self._minimizing or self._zoom_shot is None:
            return
        target = self._restore_geo or self.geometry()
        if not target.isValid():
            return
        overlay = self._make_zoom_overlay()
        overlay.setGeometry(self._taskbar_target())
        overlay.show()
        self.setWindowOpacity(0.0)

        geo = QPropertyAnimation(overlay, b"geometry", self)
        geo.setDuration(230)
        geo.setStartValue(self._taskbar_target())
        geo.setEndValue(target)
        geo.setEasingCurve(QEasingCurve.Type.OutCubic)

        def done() -> None:
            overlay.close()
            self.setWindowOpacity(1.0)

        geo.finished.connect(done)
        geo.start()
        self._restore_geo_anim = geo

    def _apply_dwm_rounding(self) -> None:
        if sys.platform != "win32":
            return
        try:
            import ctypes

            hwnd = int(self.winId())
            preference = ctypes.c_int(2)  # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(preference), ctypes.sizeof(preference)
            )
        except Exception:
            pass

    def _prepare_entrance(self) -> None:
        self._entrance_target_geo = None
        if self._restore_max or self.isMaximized():
            self.setWindowOpacity(1.0)
            return
        geo = self.geometry()
        if geo.width() < 20 or geo.height() < 20:
            self.setWindowOpacity(1.0)
            return
        self._entrance_target_geo = QRect(geo)
        small = QRect(geo)
        small.setWidth(int(geo.width() * 0.92))
        small.setHeight(int(geo.height() * 0.92))
        small.moveCenter(geo.center())
        self.setGeometry(small)
        self.setWindowOpacity(0.0)

    def _start_entrance(self) -> None:
        target = getattr(self, "_entrance_target_geo", None)
        if target is None:
            self.setWindowOpacity(1.0)
            return

        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(260)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)

        geo = QPropertyAnimation(self, b"geometry", self)
        geo.setDuration(300)
        geo.setStartValue(self.geometry())
        geo.setEndValue(target)
        geo.setEasingCurve(QEasingCurve.Type.OutCubic)

        def done() -> None:
            self.setGeometry(target)
            self.setWindowOpacity(1.0)

        geo.finished.connect(done)
        geo.start()
        fade.start()
        self._entrance_anim = (geo, fade)

    def _fade_widget(self, widget, duration: int = 400, delay: int = 0) -> None:
        if widget is None:
            return

        def start() -> None:
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
            anim = QPropertyAnimation(effect, b"opacity", self)
            anim.setDuration(duration)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)

            def done() -> None:
                if widget.graphicsEffect() is effect:
                    widget.setGraphicsEffect(None)

            anim.finished.connect(done)
            anim.start()
            self._fade_anim = anim

        QTimer.singleShot(delay, start)

    def _update_welcome(self) -> None:
        if not hasattr(self, "welcome"):
            return
        target = int(max(78, min(150, self.width() * 0.105)))
        max_w = max(320, self.width() - 120)
        if target * self._title_ratio > max_w:
            target = max(64, int(max_w / max(0.01, self._title_ratio)))
        self.welcome.setVisible(self.height() >= 720)
        target_w = int(target * self._title_ratio)
        if self.title_movie is not None and not self._title_done:
            self.title_movie.setScaledSize(QSize(target_w, target))
            self.welcome.setMovie(self.title_movie)
        elif not self._title_end.isNull():
            pix = self._title_end.scaled(
                target_w * 2,
                target * 2,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            pix.setDevicePixelRatio(2.0)
            self.welcome.setPixmap(pix)
        self.welcome.setFixedHeight(target)

    def _start_title_anim(self) -> None:
        if self._title_played:
            return
        self._title_played = True
        if not bool(self.cfg["other"].get("anim_title", True)) or self.title_movie is None:
            self._title_done = True
            self._update_welcome()
            return
        speed = float(self.cfg["other"].get("anim_speed", 1.0) or 1.0)
        self.title_movie.setSpeed(max(20, int(speed * 100)))
        self.title_movie.start()
        self._title_deadline = time.monotonic() + 30
        QTimer.singleShot(200, self._check_title)

    def _check_title(self) -> None:
        if self._title_done:
            return
        if self.title_movie.currentFrameNumber() >= self.title_movie.frameCount() - 1:
            self._on_title_finished()
            return
        if time.monotonic() > self._title_deadline:
            self._on_title_finished()
            return
        QTimer.singleShot(120, self._check_title)

    def _replay_title(self) -> None:
        if self.title_movie is None:
            return
        if not bool(self.cfg["other"].get("anim_title", True)):
            self.toast.show_message("标题动画已关闭", "在「其他设置」里打开「主界面标题动画」", 2.4)
            return
        self._title_done = False
        self._title_played = True
        self.title_movie.stop()
        self.title_movie.jumpToFrame(0)
        self._update_welcome()
        speed = float(self.cfg["other"].get("anim_speed", 1.0) or 1.0)
        self.title_movie.setSpeed(max(20, int(speed * 100)))
        self.title_movie.start()
        self._title_deadline = time.monotonic() + 30
        QTimer.singleShot(200, self._check_title)

    def _maybe_title_done(self, frame: int) -> None:
        if self.title_movie is not None and frame >= self.title_movie.frameCount() - 1:
            self._on_title_finished()

    def _on_title_finished(self) -> None:
        if self._title_done:
            return
        self._title_done = True
        if self.title_movie is not None:
            self.title_movie.stop()
        self._update_welcome()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_welcome()
        if hasattr(self, "section_preview"):
            self.section_preview.setVisible(self.width() >= 860)

    def closeEvent(self, event) -> None:
        try:
            if self._tray_icon is not None:
                self._tray_icon.hide()
        except Exception:
            pass
        try:
            if sys.platform == "win32":
                ctypes.windll.user32.UnregisterHotKey(None, self._hotkey_id)
        except Exception:
            pass
        if os.environ.get("MATH2GEO_NO_WINDOW_STATE"):
            super().closeEvent(event)
            return
        geo = self.normalGeometry() if self.isMaximized() else self.geometry()
        save_window_state(
            {
                "x": geo.x(),
                "y": geo.y(),
                "w": geo.width(),
                "h": geo.height(),
                "maximized": self.isMaximized(),
            }
        )
        super().closeEvent(event)

    def _toggle_max(self) -> None:
        if self._geo_anim is not None and self._geo_anim.state() == QAbstractAnimation.State.Running:
            return
        if self.isMaximized():
            normal = getattr(self, "_normal_geo", None) or self.normalGeometry()
            current = self.geometry()
            self.showNormal()
            self.setGeometry(current)
            self._animate_geometry(normal)
        else:
            self._normal_geo = self.geometry()
            target = self.screen().availableGeometry()
            self._animate_geometry(target, self.showMaximized)

    def _animate_geometry(self, target, on_done=None) -> None:
        anim = QPropertyAnimation(self, b"geometry", self)
        anim.setDuration(240)
        anim.setStartValue(self.geometry())
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        if on_done is not None:
            anim.finished.connect(on_done)
        anim.start()
        self._geo_anim = anim

    # ---------- 拖动

    def mousePressEvent(self, event) -> None:
        if getattr(self, "_native_frame", False):
            return
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 32:
            if self.isMaximized():
                geo = getattr(self, "_normal_geo", None) or self.normalGeometry()
                ratio = event.globalPosition().x() / max(1, self.width())
                self.showNormal()
                self.setGeometry(geo)
                self._drag_pos = QPoint(
                    int(geo.width() * ratio),
                    int(event.globalPosition().y() - geo.top()),
                )
            else:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseDoubleClickEvent(self, event) -> None:
        if getattr(self, "_native_frame", False):
            return
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 32:
            widget = self.childAt(event.position().toPoint())
            while widget is not None:
                if isinstance(widget, WinButton):
                    return
                widget = widget.parentWidget()
            self._toggle_max()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        self._resizing = False
        self._resize_edges = Qt.Edge(0)
        self._resize_geo = None
        self._resize_global = None

    # ---------- 标签页

    def _tabs(self):
        row = QHBoxLayout()
        row.setSpacing(12)
        logo = QLabel()
        icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.png")
        pix = QPixmap(icon_path)
        if not pix.isNull():
            logo.setPixmap(pix.scaled(26, 26, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            row.addWidget(logo)
            row.addSpacing(6)
        self.tab_group = []
        self.tab_buttons = QButtonGroup(self)
        self.tab_buttons.setExclusive(True)
        for i, name in enumerate(["绘制区域", "模型预设", "题目设置", "绘图设置", "其他设置"]):
            btn = Pill(name)
            self.tab_buttons.addButton(btn, i)
            btn.clicked.connect(lambda _=False, idx=i: self._switch(idx))
            row.addWidget(btn)
            self.tab_group.append(btn)
        row.addStretch(1)
        self.tab_group[0].setChecked(True)
        return row

    def _switch(self, idx: int) -> None:
        if idx == self.stack.currentIndex():
            return
        for i, btn in enumerate(self.tab_group):
            btn.setChecked(i == idx)
        self.stack.setCurrentIndex(idx)
        self._fade_in(self.stack.currentWidget())

    def _fade_in(self, widget, duration: int = 220) -> None:
        if widget is None:
            return
        if widget.graphicsEffect() is not None:
            widget.setGraphicsEffect(None)
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def _done() -> None:
            if widget.graphicsEffect() is effect:
                widget.setGraphicsEffect(None)

        anim.finished.connect(_done)
        anim.start()
        self._page_anim = anim

    # ---------- 边框缩放

    def _edges_at(self, global_pos: QPoint) -> Qt.Edge:
        if getattr(self, "_native_frame", False):
            return Qt.Edge(0)
        rect = self.frameGeometry()
        m = 7
        x = global_pos.x() - rect.x()
        y = global_pos.y() - rect.y()
        edges = Qt.Edge(0)
        if x <= m:
            edges |= Qt.Edge.LeftEdge
        elif x >= rect.width() - m:
            edges |= Qt.Edge.RightEdge
        if y <= m:
            edges |= Qt.Edge.TopEdge
        elif y >= rect.height() - m:
            edges |= Qt.Edge.BottomEdge
        return edges

    def eventFilter(self, obj, event) -> bool:
        try:
            inside = isinstance(obj, QWidget) and (obj is self or self.isAncestorOf(obj))
        except RuntimeError:
            return False
        if obj is getattr(self, "welcome", None) and event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            self._replay_title()
            return True
        if inside:
            etype = event.type()
            if self._resizing and etype == QEvent.Type.MouseMove:
                self._do_resize(event.globalPosition().toPoint())
                return True
            if etype == QEvent.Type.MouseMove:
                self._set_resize_cursor(self._edges_at(event.globalPosition().toPoint()))
            elif etype == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                edges = self._edges_at(event.globalPosition().toPoint())
                if edges:
                    self._start_resize(edges, event.globalPosition().toPoint())
                    return True
            elif etype == QEvent.Type.MouseButtonRelease and self._resizing:
                self._resizing = False
                return True
        return super().eventFilter(obj, event)

    def _start_resize(self, edges: Qt.Edge, global_pos: QPoint) -> None:
        self._resizing = True
        self._resize_edges = edges
        self._resize_geo = self.geometry()
        self._resize_global = global_pos

    def _do_resize(self, global_pos: QPoint) -> None:
        base = self._resize_geo
        if base is None:
            return
        dx = global_pos.x() - self._resize_global.x()
        dy = global_pos.y() - self._resize_global.y()
        left, top, right, bottom = base.left(), base.top(), base.right(), base.bottom()
        minw, minh = self.minimumWidth(), self.minimumHeight()
        if self._resize_edges & Qt.Edge.LeftEdge:
            left = min(base.left() + dx, right - minw + 1)
        if self._resize_edges & Qt.Edge.RightEdge:
            right = max(base.right() + dx, left + minw - 1)
        if self._resize_edges & Qt.Edge.TopEdge:
            top = min(base.top() + dy, bottom - minh + 1)
        if self._resize_edges & Qt.Edge.BottomEdge:
            bottom = max(base.bottom() + dy, top + minh - 1)
        self.setGeometry(left, top, right - left + 1, bottom - top + 1)

    def _set_resize_cursor(self, edges: Qt.Edge) -> None:
        cursor = Qt.CursorShape.ArrowCursor
        if edges in (Qt.Edge.LeftEdge, Qt.Edge.RightEdge):
            cursor = Qt.CursorShape.SizeHorCursor
        elif edges in (Qt.Edge.TopEdge, Qt.Edge.BottomEdge):
            cursor = Qt.CursorShape.SizeVerCursor
        elif edges in (Qt.Edge.LeftEdge | Qt.Edge.TopEdge, Qt.Edge.RightEdge | Qt.Edge.BottomEdge):
            cursor = Qt.CursorShape.SizeFDiagCursor
        elif edges in (Qt.Edge.RightEdge | Qt.Edge.TopEdge, Qt.Edge.LeftEdge | Qt.Edge.BottomEdge):
            cursor = Qt.CursorShape.SizeBDiagCursor
        self.setCursor(cursor)


    def _footer(self):
        wrap = QVBoxLayout()
        wrap.setContentsMargins(0, 2, 0, 0)
        wrap.setSpacing(6)

        self.busy = QProgressBar()
        self.busy.setRange(0, 0)
        self.busy.setFixedHeight(3)
        self.busy.setTextVisible(False)
        self.busy.setVisible(False)
        wrap.addWidget(self.busy)

        row = QHBoxLayout()
        self.save_btn = QPushButton("保存设置")
        self.save_btn.setObjectName("Ghost")
        self.save_btn.clicked.connect(self._save_clicked)
        self.start_btn = QPushButton("开始绘制")
        self.start_btn.setObjectName("Primary")
        self.start_btn.clicked.connect(self._start)
        row.addWidget(self.save_btn)
        row.addStretch(1)
        self.version_label = QLabel(f"版本 {__version__}")
        self.version_label.setObjectName("Hint")
        row.addWidget(self.version_label)
        row.addSpacing(12)
        row.addWidget(self.start_btn)
        wrap.addLayout(row)
        return wrap

    # ---------- 页面：绘制区域

    def _page_draw(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(12)

        card = Card()
        card.setMinimumHeight(220)
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(18, 18, 18, 18)

        self.drop = QFrame()
        self.drop.setObjectName("DropZone")
        self.drop.setAcceptDrops(True)
        self.drop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.drop.setMinimumHeight(150)
        drop_lay = QVBoxLayout(self.drop)
        drop_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_lay.setSpacing(6)
        icon = QLabel()
        icon.setPixmap(_cloud_pixmap(64))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        big = QLabel("拖动或点击选择上传题目")
        big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        big.setStyleSheet("font-size:24px; font-weight:800; color:#123B2C;")
        hint1 = QLabel("（云端 API 处理建议控制文件大小）")
        hint1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint1.setObjectName("Hint")
        hint2 = QLabel("支持图片、Word 文档或直接输入题目文字")
        hint2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint2.setObjectName("Hint")
        self.choose_btn = QPushButton("选择文件")
        self.choose_btn.setObjectName("Primary")
        self.choose_btn.setFixedWidth(160)
        self.choose_btn.clicked.connect(self._pick_file)

        drop_lay.addWidget(icon)
        drop_lay.addWidget(big)
        drop_lay.addWidget(hint1)
        drop_lay.addWidget(hint2)
        drop_lay.addSpacing(6)
        action_row = QHBoxLayout()
        action_row.addStretch(1)
        action_row.addWidget(self.choose_btn)
        self.capture_btn = QPushButton("截图识别")
        self.capture_btn.setObjectName("Ghost")
        self.capture_btn.setFixedWidth(140)
        self.capture_btn.clicked.connect(self._start_capture)
        action_row.addWidget(self.capture_btn)
        action_row.addStretch(1)
        drop_lay.addLayout(action_row)
        self.capture_hint = QLabel("截图热键：Ctrl+Alt+S")
        self.capture_hint.setObjectName("Hint")
        self.capture_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_lay.addWidget(self.capture_hint)

        self.mode_badge = ModeSwitch(card)
        self.mode_badge.clicked.connect(self._toggle_mode)
        self.mode_badge.raise_()

        def _place_badge(_e=None):
            if hasattr(self, "mode_badge") and self.mode_badge.parent() is card:
                x = card.width() - self.mode_badge.width() - 18
                self.mode_badge.move(max(8, x), 18)
                self.mode_badge.raise_()

        self.drop.resizeEvent = lambda e: (QFrame.resizeEvent(self.drop, e), _place_badge())
        card.resizeEvent = lambda e: (QFrame.resizeEvent(card, e), _place_badge())
        self._place_mode_badge = _place_badge

        QTimer.singleShot(80, _place_badge)
        self.drop.mouseReleaseEvent = self._drop_mouse_release
        self.drop.dragEnterEvent = self._drag_enter
        self.drop.dropEvent = self._drop

        card_lay.addWidget(self.drop)

        self.file_chip = QLabel("")
        self.file_chip.setObjectName("Hint")
        self.file_chip.setVisible(False)
        card_lay.addWidget(self.file_chip)

        log_card = self._log_card()
        task_card = self._tasks_card()

        bottom = QSplitter(Qt.Orientation.Horizontal)
        bottom.setChildrenCollapsible(False)
        bottom.setHandleWidth(6)
        bottom.addWidget(log_card)
        bottom.addWidget(task_card)
        bottom.setSizes([640, 460])

        split = QSplitter(Qt.Orientation.Vertical)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(6)
        split.addWidget(card)
        split.addWidget(bottom)
        split.setSizes([300, 420])
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)

        lay.addWidget(split, 1)
        return page

        def on_press() -> None:
            state["base"] = splitter.sizes()

        def on_drag(dx: int, dy: int) -> None:
            base = state["base"]
            if not base or len(base) < 2:
                return
            delta = dy if axis == "v" else dx
            if invert:
                delta = -delta
            total = sum(base)
            first = max(150, min(base[0] + delta, total - 200))
            splitter.setSizes([first, total - first])

        grip.pressed.connect(on_press)
        grip.dragged.connect(on_drag)

    def _log_card(self) -> QWidget:
        card = Card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 14)
        title = QLabel("日志查看")
        title.setObjectName("Section")
        lay.addWidget(title)
        self.logbox = QPlainTextEdit()
        self.logbox.setObjectName("Log")
        self.logbox.setReadOnly(True)
        self.logbox.setMinimumHeight(80)
        lay.addWidget(self.logbox, 1)
        return card

    def _tasks_card(self) -> QWidget:
        card = Card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 14)
        head = QHBoxLayout()
        title = QLabel("已完成任务")
        title.setObjectName("Section")
        head.addWidget(title)
        head.addStretch(1)
        self.task_count = QLabel("0")
        self.task_count.setObjectName("Hint")
        head.addWidget(self.task_count)
        lay.addLayout(head)

        self.task_area = QScrollArea()
        self.task_area.setWidgetResizable(True)
        self.task_area.setStyleSheet("background: transparent;")
        self.task_area.viewport().setStyleSheet("background: transparent;")
        holder = QWidget()
        self.task_layout = QVBoxLayout(holder)
        self.task_layout.setContentsMargins(0, 4, 0, 0)
        self.task_layout.setSpacing(8)
        self.task_layout.addStretch(1)
        self.task_area.setWidget(holder)
        lay.addWidget(self.task_area, 1)
        empty = QLabel("还没有完成的题目")
        empty.setObjectName("Hint")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.task_layout.insertWidget(0, empty)
        self.empty_label = empty
        return card

    # ---------- 页面：模型预设

    def _scroll_page(self, inner: QWidget) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        sheet = QFrame()
        sheet.setObjectName("Sheet")
        sheet_lay = QVBoxLayout(sheet)
        sheet_lay.setContentsMargins(0, 0, 0, 0)
        sheet_lay.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("background: transparent;")
        scroll.viewport().setStyleSheet("background: transparent;")
        holder = QWidget()
        lay = QVBoxLayout(holder)
        lay.setContentsMargins(0, 0, 0, 14)
        lay.setSpacing(0)
        inner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay.addWidget(inner, 1)
        scroll.setWidget(holder)
        sheet_lay.addWidget(scroll)
        outer.addWidget(sheet)
        return page

    def _page_model(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        card = Card()
        box = QVBoxLayout(card)
        box.setContentsMargins(16, 14, 16, 16)
        box.setSpacing(10)

        mode_row = QHBoxLayout()
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        for idx, text in enumerate(("本地模型", "云端 API")):
            btn = Pill(text)
            btn.setFixedSize(132, 38)
            self.mode_group.addButton(btn, idx)
            mode_row.addWidget(btn)
        self.rb_local = self.mode_group.button(0)
        self.rb_cloud = self.mode_group.button(1)
        self.rb_cloud.setChecked(True)
        self.mode_group.idClicked.connect(self._mode_changed)
        mode_row.addStretch(1)
        self.user_api_btn = QPushButton("用户 API 配置")
        self.user_api_btn.setObjectName("Tab")
        self.user_api_btn.setFixedSize(132, 38)
        self.user_api_btn.clicked.connect(self._open_user_api_config)
        mode_row.addWidget(self.user_api_btn)
        box.addLayout(mode_row)

        self.model_stack = QStackedWidget()
        self.model_stack.addWidget(self._local_form())
        self.model_stack.addWidget(self._cloud_form())
        self.model_stack.setCurrentIndex(1)
        box.addWidget(self.model_stack)
        self._preset_sync_timer = QTimer(self)
        self._preset_sync_timer.setSingleShot(True)
        self._preset_sync_timer.setInterval(300)
        self._preset_sync_timer.timeout.connect(self._sync_active_preset)
        for w in (self.cloud_base, self.cloud_name, self.cloud_key, self.cloud_key_env):
            w.textChanged.connect(lambda *_: self._preset_sync_timer.start())
        for w in (self.cloud_temp, self.cloud_tokens, self.cloud_timeout):
            w.valueChanged.connect(lambda *_: self._preset_sync_timer.start())
        self.provider_combo.currentTextChanged.connect(lambda *_: self._preset_sync_timer.start())

        self.price_check = QCheckBox("显示价格")
        self.price_check.toggled.connect(self._price_toggled)
        box.addWidget(self.price_check)
        box.addWidget(self._price_form())
        lay.addWidget(card)
        lay.addStretch(1)
        return page

    def _local_form(self) -> QWidget:
        w = QWidget()
        form = QVBoxLayout(w)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)
        self.local_addr = self._row(form, "模型地址", QLineEdit("http://127.0.0.1:11434/v1"))
        self.local_base = self._row(form, "Base URL", QLineEdit("http://127.0.0.1:11434/v1"))
        self.local_temp = self._row(form, "Temperature", self._temp_spin())
        self.local_tokens = self._row(form, "最大输出 tokens", self._tokens_spin())
        self.local_timeout = self._row(form, "请求超时", self._timeout_spin())
        form.addStretch(1)
        return w

    def _cloud_form(self) -> QWidget:
        w = QWidget()
        form = QVBoxLayout(w)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)

        self.provider_combo = self._combo()
        for orig, item in enumerate(PROVIDERS):
            name = item[0]
            if name == "免费 API" and not ENABLE_FREE_API:
                continue
            self.provider_combo.addItem(name, orig)
        provider_row = QHBoxLayout()
        provider_label = QLabel("服务商")
        provider_label.setFixedWidth(110)
        provider_row.addWidget(provider_label)
        provider_row.addWidget(self.provider_combo, 1)
        self.test_btn = QPushButton("测试连接")
        self.test_btn.setObjectName("Ghost")
        self.test_btn.clicked.connect(self._test_connection)
        provider_row.addWidget(self.test_btn)
        form.addLayout(provider_row)
        self.cloud_provider = self.provider_combo
        self.test_status = QLabel("")
        self.test_status.setObjectName("Hint")
        self.provider_combo.currentIndexChanged.connect(self._provider_changed)

        self.provider_link = QLabel()
        self.provider_link.setOpenExternalLinks(True)
        self.provider_link.setStyleSheet("font-size:12px;")
        form.addWidget(self.provider_link)

        self.free_panel = QWidget()
        self.free_panel.setObjectName("FreePanel")
        self.free_panel.setStyleSheet(
            "QWidget#FreePanel { background:#FBFDFC; border:1px solid #D9E8DE; border-radius:10px; }"
        )
        free_lay = QVBoxLayout(self.free_panel)
        free_lay.setContentsMargins(14, 12, 14, 12)
        free_lay.setSpacing(8)
        free_title = QLabel("ChatAnywhere（第三方）")
        free_title.setStyleSheet("font-size:15px; font-weight:700; color:#0F3D2E; border:none;")
        free_lay.addWidget(free_title)
        free_desc = QLabel(
            '免费/低价转发 OpenAI 接口，适合试用。前往 '
            '<a href="https://chatanywhere.tech/console/overview">ChatAnywhere 控制台</a> 申请 Key。'
        )
        free_desc.setWordWrap(True)
        free_desc.setOpenExternalLinks(True)
        free_desc.setStyleSheet("border:none;")
        free_lay.addWidget(free_desc)
        free_hint = QLabel(
            '无法进入 GitHub？下载 <a href="https://steampp.net/">Watt Toolkit</a> 尝试加速 GitHub。'
        )
        free_hint.setWordWrap(True)
        free_hint.setOpenExternalLinks(True)
        free_hint.setStyleSheet("border:none;")
        free_lay.addWidget(free_hint)
        free_confirm = QPushButton("无法打开 Watt Toolkit ?")
        free_confirm.setObjectName("Ghost")
        free_confirm.clicked.connect(
            lambda: QMessageBox.information(self, "提示", "若网站失效请自行搜寻加速 GitHub 的办法。")
        )
        free_lay.addWidget(free_confirm, alignment=Qt.AlignmentFlag.AlignLeft)
        free_more = QLabel(
            '>>更多API？查看GitHub上由他人搭建的'
            '<a href="https://github.com/kirito8/free-newapi">导航文档</a>'
        )
        free_more.setWordWrap(True)
        free_more.setOpenExternalLinks(True)
        free_more.setStyleSheet("border:none;")
        free_lay.addWidget(free_more)
        self.free_use_btn = QPushButton("使用 ChatAnywhere")
        self.free_use_btn.setObjectName("Primary")
        self.free_use_btn.setStyleSheet(
            "QPushButton { background:#1F5C46; color:#FFFFFF; border:none; border-radius:8px;"
            " padding:9px 18px; font-weight:700; }"
            "QPushButton:hover { background:#2A6F55; }"
        )
        self.free_use_btn.clicked.connect(self._use_chatanywhere)
        free_lay.addWidget(self.free_use_btn)
        self.free_panel.setVisible(False)
        form.addWidget(self.free_panel)

        self.cloud_base = self._row(form, "Base URL", QLineEdit("https://api.deepseek.com/v1"))
        key = QLineEdit()
        key.setEchoMode(QLineEdit.EchoMode.Password)
        self.cloud_key = self._row(form, "API Key", key)

        form.addWidget(self.test_status)

        self.env_toggle = QPushButton("环境变量 ▾")
        self.env_toggle.setObjectName("Ghost")
        self.env_toggle.setCheckable(True)
        self.env_toggle.toggled.connect(self._toggle_env_row)
        self.env_row = QWidget()
        env_lay = QHBoxLayout(self.env_row)
        env_lay.setContentsMargins(0, 0, 0, 0)
        env_label = QLabel("Key 环境变量")
        env_label.setFixedWidth(110)
        self.cloud_key_env = QLineEdit("MATH2GEO_API_KEY")
        env_lay.addWidget(env_label)
        env_lay.addWidget(self.cloud_key_env, 1)
        self.env_row.setMaximumHeight(0)
        self.env_row.setVisible(False)

        self.classroom_btn = QPushButton("教室模式（连续点击3次锁定API Key内容）")
        self.classroom_btn.setObjectName("Ghost")
        self.classroom_btn.clicked.connect(self._classroom_click)
        env_tools = QHBoxLayout()
        env_tools.addWidget(self.env_toggle)
        env_tools.addWidget(self.classroom_btn)
        env_tools.addStretch(1)
        form.addLayout(env_tools)
        self.classroom_hint = QLabel("锁定后 API Key / 环境变量只能在本页的「用户 API 配置」中查看或修改。")
        self.classroom_hint.setObjectName("Hint")
        self.classroom_hint.setWordWrap(False)
        self.classroom_hint.setFixedHeight(20)
        form.addWidget(self.classroom_hint)
        form.addWidget(self.env_row)

        self.cloud_name = self._row(form, "模型名称", QLineEdit("deepseek-flash"))
        self.cloud_temp = self._row(form, "Temperature", self._temp_spin())
        self.cloud_tokens = self._row(form, "最大输出 tokens", self._tokens_spin())
        self.cloud_timeout = self._row(form, "请求超时", self._timeout_spin())
        self._provider_changed(self.provider_combo.currentIndex())
        form.addStretch(1)
        return w

    def _price_form(self) -> QWidget:
        self.price_box = Card()
        box = QVBoxLayout(self.price_box)
        box.setContentsMargins(18, 14, 18, 16)
        box.setSpacing(10)
        tip = QLabel("费用 = 输入 token × 单价 + 输出 token × 单价（单价：元 / 百万 tokens）")
        tip.setObjectName("Hint")
        box.addWidget(tip)

        self.currency = self._row(box, "计价货币", self._combo())
        self.currency.addItems(["CNY", "USD"])

        self.price_in = self._row(box, "输入单价", self._price_spin())
        self.price_out = self._row(box, "输出单价", self._price_spin())

        self.chk_peak = QCheckBox("启用高峰 / 低谷不同单价")
        self.chk_peak.toggled.connect(self._peak_toggled)
        box.addWidget(self.chk_peak)

        self.peak_box = QWidget()
        peak = QVBoxLayout(self.peak_box)
        peak.setContentsMargins(24, 0, 0, 0)
        peak.setSpacing(6)

        row = QHBoxLayout()
        row.addWidget(QLabel("高峰时段"))
        self.peak_start = QTimeEdit()
        self.peak_start.setDisplayFormat("HH:mm")
        self.peak_end = QTimeEdit()
        self.peak_end.setDisplayFormat("HH:mm")
        row.addWidget(self.peak_start)
        row.addWidget(QLabel("至"))
        row.addWidget(self.peak_end)
        row.addStretch(1)
        peak.addLayout(row)

        lunch = QHBoxLayout()
        self.chk_lunch = QCheckBox("午间低谷")
        self.lunch_start = QTimeEdit()
        self.lunch_start.setDisplayFormat("HH:mm")
        self.lunch_end = QTimeEdit()
        self.lunch_end.setDisplayFormat("HH:mm")
        lunch.addWidget(self.chk_lunch)
        lunch.addWidget(self.lunch_start)
        lunch.addWidget(QLabel("至"))
        lunch.addWidget(self.lunch_end)
        lunch.addStretch(1)
        peak.addLayout(lunch)

        wd = QHBoxLayout()
        wd.addWidget(QLabel("高峰星期"))
        self.week_boxes = []
        for i, name in enumerate(["一", "二", "三", "四", "五", "六", "日"], start=1):
            cb = QCheckBox(name)
            cb.setProperty("day", i)
            self.week_boxes.append(cb)
            wd.addWidget(cb)
        wd.addStretch(1)
        peak.addLayout(wd)

        self.extra_dates = self._row(peak, "额外低谷日期", QLineEdit())
        self.extra_dates.setPlaceholderText("YYYY-MM-DD，逗号分隔，可留空")
        self.off_in = self._row(peak, "低谷输入单价", self._price_spin())
        self.off_out = self._row(peak, "低谷输出单价", self._price_spin())

        apply_btn = QPushButton("应用 DeepSeek 默认价（deepseek-flash）")
        apply_btn.setObjectName("Ghost")
        apply_btn.clicked.connect(self._apply_default_price)
        peak.addWidget(apply_btn)
        box.addWidget(self.peak_box)

        return self.price_box

    def _peak_toggled(self, on: bool) -> None:
        self.peak_box.setVisible(on)

    def _apply_default_price(self) -> None:
        self.currency.setCurrentText("CNY")
        self.price_in.setValue(2.0)
        self.price_out.setValue(8.0)
        self.off_in.setValue(1.0)
        self.off_out.setValue(4.0)
        self.chk_peak.setChecked(True)
        self.peak_start.setTime(QTime(9, 0))
        self.peak_end.setTime(QTime(18, 0))
        self.chk_lunch.setChecked(True)
        self.lunch_start.setTime(QTime(12, 0))
        self.lunch_end.setTime(QTime(14, 0))
        for cb in self.week_boxes:
            cb.setChecked(cb.property("day") <= 5)

    def _price_toggled(self, on: bool) -> None:
        self.price_box.setVisible(on)

    # ---------- 页面：题目设置

    def _page_problem(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        card = Card()
        box = QVBoxLayout(card)
        box.setContentsMargins(16, 14, 16, 16)
        box.setSpacing(10)

        self.chk_problem = QCheckBox("将题目添加到绘制文件中")
        box.addWidget(self.chk_problem)
        self.cmb_problem_mode = self._indent_combo(box, ["原文", "原图"])

        self.chk_answer = QCheckBox("同时输出答案和过程")
        box.addWidget(self.chk_answer)
        self.cmb_detail = self._indent_combo(box, ["简单", "答案", "丰富"])

        self.chk_difficulty = QCheckBox("增加题目难度显示（0~1 难度系数）(Beta)")
        box.addWidget(self.chk_difficulty)

        self.chk_breakthrough = QCheckBox("增加题目突破点 (Beta)")
        box.addWidget(self.chk_breakthrough)

        prompt_row = QHBoxLayout()
        prompt_tip = QLabel("作图提示词")
        prompt_tip.setObjectName("Hint")
        prompt_row.addWidget(prompt_tip)
        self.prompt_state = QLabel("默认预设")
        self.prompt_state.setStyleSheet("color:#5D6B63; font-size:12px;")
        prompt_row.addWidget(self.prompt_state)
        prompt_row.addSpacing(10)
        edit_prompt = QPushButton("编辑")
        edit_prompt.setObjectName("Ghost")
        edit_prompt.clicked.connect(self._edit_prompt)
        prompt_row.addWidget(edit_prompt)
        prompt_row.addStretch(1)
        box.addLayout(prompt_row)

        note = QLabel("答案与过程由模型生成；详细程度会改变步骤数量。")
        note.setObjectName("Hint")
        box.addWidget(note)
        lay.addWidget(card)
        lay.addStretch(1)
        return page

    # ---------- 页面：绘图设置

    def _page_draw_settings(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        card = Card()
        box = QVBoxLayout(card)
        box.setContentsMargins(16, 14, 16, 16)
        box.setSpacing(10)

        dim_row = QHBoxLayout()
        dim_row.addWidget(QLabel("输出维度"))
        self.rb_2d = QCheckBox("二维（平面直角坐标系）")#QRadioButton
        self.rb_3d = QCheckBox("三维（空间直角坐标系）")
        self.dim_group = QButtonGroup(self)
        self.dim_group.addButton(self.rb_2d, 2)
        self.dim_group.addButton(self.rb_3d, 3)
        self.rb_2d.setChecked(True)
        self.dim_group.idClicked.connect(self._dimension_changed)
        dim_row.addWidget(self.rb_2d)
        dim_row.addWidget(self.rb_3d)
        dim_row.addStretch(1)
        box.addLayout(dim_row)
        self.dim_hint = QLabel("二维：输出平面直角坐标系。")
        self.dim_hint.setObjectName("Hint")
        self.dim_hint.setWordWrap(True)
        box.addWidget(self.dim_hint)

        self.section_box = QWidget()
        sec = QHBoxLayout(self.section_box)
        sec.setContentsMargins(0, 6, 0, 0)
        sec.setSpacing(16)
        self.section_preview = SectionDirectionPreview()
        sec.addWidget(self.section_preview)

        right = QVBoxLayout()
        right.setSpacing(8)

        az_row = QHBoxLayout()
        az_row.addWidget(QLabel("方位角"))
        self.sec_az = QSlider(Qt.Orientation.Horizontal)
        self.sec_az.setRange(-180, 180)
        self.sec_az.setPageStep(15)
        self.sec_az.setTickInterval(15)
        self.sec_az.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.sec_az.setMinimumWidth(240)
        self.sec_az.setMaximumWidth(360)
        self.sec_az_spin = QSpinBox()
        self.sec_az_spin.setRange(-180, 180)
        self.sec_az_spin.setSuffix("°")
        self.sec_az_spin.setFixedWidth(76)
        az_row.addWidget(self.sec_az, 1)
        az_row.addWidget(self.sec_az_spin)
        right.addLayout(az_row)

        el_row = QHBoxLayout()
        el_row.addWidget(QLabel("仰角"))
        self.sec_el = QSlider(Qt.Orientation.Horizontal)
        self.sec_el.setRange(-90, 90)
        self.sec_el.setPageStep(15)
        self.sec_el.setTickInterval(15)
        self.sec_el.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.sec_el.setMinimumWidth(240)
        self.sec_el.setMaximumWidth(360)
        self.sec_el_spin = QSpinBox()
        self.sec_el_spin.setRange(-90, 90)
        self.sec_el_spin.setSuffix("°")
        self.sec_el_spin.setFixedWidth(76)
        el_row.addWidget(self.sec_el, 1)
        el_row.addWidget(self.sec_el_spin)
        right.addLayout(el_row)

        snap_row = QHBoxLayout()
        snap_row.addWidget(QLabel("角度吸附"))
        self.cmb_snap = self._combo()
        for text, value in (("15°", 15), ("5°", 5), ("30°", 30), ("关闭", 0)):
            self.cmb_snap.addItem(text, value)
        snap_row.addWidget(self.cmb_snap)
        snap_row.addStretch(1)
        right.addLayout(snap_row)

        quick_row = QHBoxLayout()
        quick_row.addWidget(QLabel("快速方向"))
        for text, az, el in (("正视", 0, 0), ("侧视", 90, 0), ("俯视", 0, 90), ("等轴测", 45, 35)):
            b = QPushButton(text)
            b.setObjectName("Ghost")
            b.clicked.connect(lambda _=False, a=az, e=el: self._set_section_preset(a, e))
            quick_row.addWidget(b)
        quick_row.addStretch(1)
        right.addLayout(quick_row)

        cut_row = QHBoxLayout()
        self.chk_section = QCheckBox("显示截面")
        self.chk_section.setChecked(True)
        cut_row.addWidget(self.chk_section)
        cut_row.addSpacing(10)
        cut_row.addWidget(QLabel("透明度"))
        self.sec_opacity = QSlider(Qt.Orientation.Horizontal)
        self.sec_opacity.setRange(0, 60)
        self.sec_opacity.setValue(12)
        self.sec_opacity.setMinimumWidth(240)
        self.sec_opacity.setMaximumWidth(360)
        self.sec_opacity_spin = QSpinBox()
        self.sec_opacity_spin.setRange(0, 60)
        self.sec_opacity_spin.setSuffix("%")
        self.sec_opacity_spin.setFixedWidth(66)
        cut_row.addWidget(self.sec_opacity, 1)
        cut_row.addWidget(self.sec_opacity_spin)
        cut_row.addStretch(1)
        right.addLayout(cut_row)

        offset_row = QHBoxLayout()
        offset_row.addWidget(QLabel("偏移"))
        self.sec_offset = QDoubleSpinBox()
        self.sec_offset.setRange(-5.0, 5.0)
        self.sec_offset.setSingleStep(0.1)
        self.sec_offset.setDecimals(1)
        self.sec_offset.setFixedWidth(80)
        offset_row.addWidget(self.sec_offset)
        offset_row.addStretch(1)
        right.addLayout(offset_row)

        factor_row = QHBoxLayout()
        factor_row.addWidget(QLabel("token 倍率"))
        self.sec_factor = QSlider(Qt.Orientation.Horizontal)
        self.sec_factor.setRange(100, 500)
        self.sec_factor.setSingleStep(1)
        self.sec_factor.setPageStep(10)
        self.sec_factor.setValue(250)
        self.sec_factor.setMinimumWidth(240)
        self.sec_factor.setMaximumWidth(360)
        self.sec_factor_value = QDoubleSpinBox()
        self.sec_factor_value.setRange(1.0, 5.0)
        self.sec_factor_value.setDecimals(2)
        self.sec_factor_value.setSingleStep(0.05)
        self.sec_factor_value.setSuffix("×")
        self.sec_factor_value.setFixedWidth(80)
        self._factor_guard = False

        def _slider_to_spin(v: int) -> None:
            if self._factor_guard:
                return
            self._factor_guard = True
            self.sec_factor_value.setValue(v / 100.0)
            self._factor_guard = False

        def _spin_to_slider(v: float) -> None:
            if self._factor_guard:
                return
            self._factor_guard = True
            self.sec_factor.setValue(int(round(v * 100)))
            self._factor_guard = False

        self.sec_factor.valueChanged.connect(_slider_to_spin)
        self.sec_factor_value.valueChanged.connect(_spin_to_slider)
        factor_row.addWidget(self.sec_factor, 1)
        factor_row.addWidget(self.sec_factor_value)
        factor_row.addStretch(1)
        right.addLayout(factor_row)

        style_row = QHBoxLayout()
        style_row.addWidget(QLabel("三维样式"))
        self.cmb_style_3d = self._combo()
        self.cmb_style_3d.addItems(["彩色实体", "简洁"])
        self.cmb_style_3d.setFixedWidth(120)
        style_row.addWidget(self.cmb_style_3d)
        style_row.addSpacing(12)
        self.chk_section_axes = QCheckBox("截面坐标轴")
        self.chk_section_axes.setChecked(True)
        style_row.addWidget(self.chk_section_axes)
        self.chk_section_shape = QCheckBox("截面图形")
        self.chk_section_shape.setChecked(True)
        style_row.addWidget(self.chk_section_shape)
        style_row.addStretch(1)
        right.addLayout(style_row)

        self.sec_opacity.valueChanged.connect(self.sec_opacity_spin.setValue)
        self.sec_opacity_spin.valueChanged.connect(self.sec_opacity.setValue)
        right.addStretch(1)
        sec.addLayout(right, 1)
        self.section_box.setVisible(False)
        box.addWidget(self.section_box)

        self._sec_guard = False
        self.sec_az.valueChanged.connect(self._on_sec_az_slider)
        self.sec_el.valueChanged.connect(self._on_sec_el_slider)
        self.sec_az_spin.valueChanged.connect(self._on_sec_az_spin)
        self.sec_el_spin.valueChanged.connect(self._on_sec_el_spin)

        self.cmb_target = self._row(box, "输出方式", self._combo())
        self.cmb_target.addItems(["GeoGebra", "几何画板"])


        self.chk_axes = QCheckBox("显示坐标轴")
        self.chk_grid = QCheckBox("显示网格")
        row = QHBoxLayout()
        row.addWidget(self.chk_axes)
        row.addWidget(self.chk_grid)
        row.addStretch(1)
        box.addLayout(row)

        extra_row = QHBoxLayout()
        self.chk_extra = QCheckBox("额外生成")
        self.cmb_format = self._combo()
        self.cmb_format.addItems(["PNG", "SVG"])
        self.spin_dpi = QSpinBox()
        self.spin_dpi.setRange(72, 600)
        self.spin_dpi.setValue(190)
        self.spin_dpi.setFixedWidth(90)
        extra_row.addWidget(self.chk_extra)
        extra_row.addWidget(self.cmb_format)
        extra_row.addSpacing(10)
        extra_row.addWidget(QLabel("DPI"))
        extra_row.addWidget(self.spin_dpi)
        extra_row.addStretch(1)
        box.addLayout(extra_row)

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("主线条颜色"))
        self.main_color = ColorPicker(VERSE["main"])
        color_row.addWidget(self.main_color)
        color_row.addSpacing(16)
        color_row.addWidget(QLabel("辅助线颜色"))
        self.aux_color = ColorPicker(VERSE["aux"])
        color_row.addWidget(self.aux_color)
        self.cmb_aux_style = self._combo()
        self.cmb_aux_style.addItems(["虚线", "实线"])
        self.cmb_aux_style.setFixedWidth(90)
        color_row.addWidget(self.cmb_aux_style)
        color_row.addStretch(1)
        box.addLayout(color_row)

        preview = QLabel("颜色与线型会同时作用于预览图和 GeoGebra 图形。")
        preview.setObjectName("Hint")
        box.addWidget(preview)
        lay.addWidget(card)
        lay.addStretch(1)
        return page

    def _dimension_changed(self, *_args) -> None:
        is3d = self.rb_3d.isChecked()
        self.section_box.setVisible(is3d)
        self.dim_hint.setText(
            "三维：输出空间直角坐标系；下方设置截面法向量的方位角与仰角，拖动时按所选角度吸附。"
            "三维模式按下方「token 倍率」提高本次请求的最大输出 token 预算（1.00–5.00 倍）。"
            if is3d
            else "二维：输出平面直角坐标系。"
        )
        if hasattr(self, "mode_badge"):
            self._refresh_mode_badge()

    def _snap_angle(self, value: int) -> int:
        step = int(self.cmb_snap.currentData() or 0)
        if step <= 0:
            return value
        nearest = int(round(value / step) * step)
        return nearest if abs(value - nearest) <= 4 else value

    def _on_sec_az_slider(self, value: int) -> None:
        if self._sec_guard:
            return
        snapped = self._snap_angle(value)
        self._sec_guard = True
        if snapped != value:
            self.sec_az.setValue(snapped)
        self.sec_az_spin.setValue(snapped)
        self._sec_guard = False
        self._update_section_preview()

    def _on_sec_el_slider(self, value: int) -> None:
        if self._sec_guard:
            return
        snapped = self._snap_angle(value)
        self._sec_guard = True
        if snapped != value:
            self.sec_el.setValue(snapped)
        self.sec_el_spin.setValue(snapped)
        self._sec_guard = False
        self._update_section_preview()

    def _on_sec_az_spin(self, value: int) -> None:
        if self._sec_guard:
            return
        self._sec_guard = True
        self.sec_az.setValue(value)
        self._sec_guard = False
        self._update_section_preview()

    def _on_sec_el_spin(self, value: int) -> None:
        if self._sec_guard:
            return
        self._sec_guard = True
        self.sec_el.setValue(value)
        self._sec_guard = False
        self._update_section_preview()

    def _set_section_preset(self, azimuth: int, elevation: int) -> None:
        self._sec_guard = True
        self.sec_az.setValue(azimuth)
        self.sec_az_spin.setValue(azimuth)
        self.sec_el.setValue(elevation)
        self.sec_el_spin.setValue(elevation)
        self._sec_guard = False
        self._update_section_preview()

    def _update_section_preview(self) -> None:
        self.section_preview.set_angles(self.sec_az.value(), self.sec_el.value())

    # ---------- 页面：其他设置

    def _page_other(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        card = Card()
        box = QVBoxLayout(card)
        box.setContentsMargins(16, 14, 16, 16)
        box.setSpacing(10)

        self.chk_anim_startup = QCheckBox("启动动画")
        box.addWidget(self.chk_anim_startup)
        self.chk_anim_title = QCheckBox("主界面标题动画")
        box.addWidget(self.chk_anim_title)

        speed_row = QHBoxLayout()
        speed_row.addSpacing(26)
        speed_row.addWidget(QLabel("动画倍速"))
        self.cmb_anim_speed = self._combo()
        for text, value in (("0.75×", 0.75), ("1×", 1.0), ("1.25×", 1.25), ("1.5×", 1.5), ("2×", 2.0)):
            self.cmb_anim_speed.addItem(text, value)
        speed_row.addWidget(self.cmb_anim_speed, 1)
        box.addLayout(speed_row)

        self.chk_notify_windows = QCheckBox("Windows 系统通知")
        self.chk_notify_windows.setChecked(True)
        box.addWidget(self.chk_notify_windows)

        sound_row = QHBoxLayout()
        self.chk_notify_sound = QCheckBox("绘制完成提示音")
        self.chk_notify_sound.setChecked(True)
        sound_row.addWidget(self.chk_notify_sound)
        choose_sound = QPushButton("添加声音")
        choose_sound.setObjectName("Ghost")
        choose_sound.clicked.connect(self._choose_notify_sound)
        sound_row.addWidget(choose_sound)
        self.sound_label = self._combo()
        self.sound_label.setMinimumWidth(210)
        self.sound_label.addItem("默认系统提示音", "")
        self.sound_label.currentIndexChanged.connect(self._on_sound_selected)
        sound_row.addWidget(self.sound_label, 1)
        preview_sound = QPushButton("试听")
        preview_sound.setObjectName("Ghost")
        preview_sound.clicked.connect(self._preview_notify_sound)
        sound_row.addWidget(preview_sound)
        self.delete_sound_btn = QPushButton("删除该预设")
        self.delete_sound_btn.setObjectName("Ghost")
        self.delete_sound_btn.clicked.connect(self._reset_notify_sound)
        sound_row.addWidget(self.delete_sound_btn)
        box.addLayout(sound_row)

        hotkey_row = QHBoxLayout()
        hotkey_row.addWidget(QLabel("截图热键"))
        self.hotkey_edit = QKeySequenceEdit()
        self.hotkey_edit.setMaximumWidth(180)
        hotkey_row.addWidget(self.hotkey_edit)
        reset_hotkey = QPushButton("恢复默认")
        reset_hotkey.setObjectName("Ghost")
        reset_hotkey.clicked.connect(self._reset_hotkey)
        hotkey_row.addWidget(reset_hotkey)
        hotkey_hint = QLabel("全局生效，默认 Ctrl+Alt+S")
        hotkey_hint.setObjectName("Hint")
        hotkey_row.addWidget(hotkey_hint, 1)
        box.addLayout(hotkey_row)
        self.chk_capture_confirm = QCheckBox("截图后二次确认")
        self.chk_capture_confirm.setChecked(True)
        box.addWidget(self.chk_capture_confirm)

        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("界面主题"))
        self.theme_combo = self._combo()
        self.theme_combo.addItem("纯色", "plain")
        self.theme_combo.addItem("网格", "grid")
        self.theme_combo.addItem("点网", "dots")
        self.theme_combo.currentIndexChanged.connect(self._theme_changed)
        theme_row.addWidget(self.theme_combo, 1)
        box.addLayout(theme_row)

        row = QHBoxLayout()
        row.addWidget(QLabel("默认输出目录"))
        self.outdir_edit = QLineEdit(os.path.abspath("out"))
        self.outdir_edit.setReadOnly(True)
        row.addWidget(self.outdir_edit, 1)
        btn = QPushButton("更改")
        btn.setObjectName("Ghost")
        btn.clicked.connect(self._pick_outdir)
        row.addWidget(btn)
        box.addLayout(row)

        self.open_btn = QPushButton("打开输出目录")
        self.open_btn.setObjectName("Ghost")
        self.open_btn.clicked.connect(self._open_outdir)
        box.addWidget(self.open_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        self.chk_offline = QCheckBox("输出离线运行组件（deployggb.js）")
        self.chk_offline.setToolTip("把本地 deployggb.js 复制到输出目录，离线打开 HTML 时优先加载本地脚本")
        box.addWidget(self.chk_offline)

        box.addSpacing(10)
        cache_row = QHBoxLayout()
        cache_tip = QLabel("缓存：临时图标、日志记录与已完成任务列表（不会删除输出目录里的图形）")
        cache_tip.setObjectName("Hint")
        cache_tip.setWordWrap(True)
        cache_row.addWidget(cache_tip, 1)
        self.clear_cache_btn = QPushButton("清空缓存")
        self.clear_cache_btn.setObjectName("Ghost")
        self.clear_cache_btn.clicked.connect(self._clear_cache)
        cache_row.addWidget(self.clear_cache_btn)
        box.addLayout(cache_row)

        box.addSpacing(6)
        about = QLabel("配置保存在 %APPDATA%\\math2geo\\config.json，不会上传。")
        about.setObjectName("Hint")
        box.addWidget(about)
        lay.addWidget(card)

        lay.addStretch(1)
        copyright_label = QLabel(
            '<a href="https://github.com/Mu-Jiji" '
           'style="color:#8A9A91; text-decoration:none">'
          '©2026 Mu-Jiji @ GitHub All Rights Reserved</a>'
        )
        copyright_label.setObjectName("Hint")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copyright_label.setOpenExternalLinks(True)
        copyright_label.setStyleSheet("font-size:12px;")
        copyright_label.setCursor(Qt.CursorShape.PointingHandCursor)
        lay.addWidget(copyright_label)
        version_label = QLabel(f"版本：{__version__}")
        version_label.setObjectName("Hint")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("font-size:12px;")
        lay.addWidget(version_label)
        return page

    # ---------- 表单小工具

    def _section(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setObjectName("Section")
        return lab

    def _row(self, layout, label: str, widget):
        row = QHBoxLayout()
        lab = QLabel(label)
        lab.setFixedWidth(110)
        row.addWidget(lab)
        row.addWidget(widget, 1)
        layout.addLayout(row)
        return widget

    def _combo(self) -> QComboBox:
        combo = AnimatedCombo()
        combo.view().setStyleSheet(
            "QAbstractItemView { background:#FFFFFF; border:1px solid #D9E8DE; border-radius:10px;"
            " padding:4px; outline:0; selection-background-color:#D7EEDF; selection-color:#0F3D2E; }"
        )
        return combo

    def _indent_combo(self, layout, items) -> QComboBox:
        row = QHBoxLayout()
        row.addSpacing(26)
        combo = self._combo()
        combo.addItems(items)
        row.addWidget(combo)
        row.addStretch(1)
        layout.addLayout(row)
        return combo

    def _temp_spin(self) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(0.0, 2.0)
        s.setSingleStep(0.1)
        s.setValue(0.2)
        s.setDecimals(1)
        return s

    def _tokens_spin(self) -> QSpinBox:
        s = QSpinBox()
        s.setRange(256, 32000)
        s.setValue(4000)
        s.setSingleStep(256)
        return s

    def _timeout_spin(self) -> QSpinBox:
        s = QSpinBox()
        s.setRange(10, 600)
        s.setValue(120)
        s.setSuffix(" 秒")
        return s

    def _price_spin(self) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(0.0, 999.0)
        s.setDecimals(2)
        s.setValue(0.0)
        s.setSuffix(" / 百万 tokens")
        return s

    # ---------- 配置读写

    def _apply_config(self) -> None:
        self._applying_config = True
        m = self.cfg["model"]
        if m.get("mode") == "local":
            self.rb_local.setChecked(True)
            self.rb_cloud.setChecked(False)
            self.model_stack.setCurrentIndex(0)
        provider = m.get("provider") or "深度求索 DeepSeek"
        hidden_free = provider == "免费 API" and not ENABLE_FREE_API
        if hidden_free:
            provider = "深度求索 DeepSeek"
        idx = self.provider_combo.findText(provider)
        if idx < 0:
            idx = 0
        self.provider_combo.blockSignals(True)
        self.provider_combo.setCurrentIndex(idx)
        self.provider_combo.blockSignals(False)
        orig = self.provider_combo.itemData(idx)
        if orig is None:
            orig = idx
        orig = max(0, min(int(orig), len(PROVIDERS) - 1))
        self._provider_changed(idx, False)
        base_value = "" if hidden_free else m.get("base_url", "")
        name_value = "" if hidden_free else (m.get("name") or m.get("model", ""))
        self.cloud_base.setText(base_value or PROVIDERS[orig][1])
        self.cloud_name.setText(name_value or PROVIDERS[orig][2])
        self.cloud_key.setText(m.get("api_key", ""))
        env_name = (m.get("key_env") or "").strip()
        if not env_name or env_name.startswith("sk-"):
            env_name = "MATH2GEO_API_KEY"
        m["key_env"] = env_name
        for preset in m.get("api_presets") or []:
            p_env = (preset.get("key_env") or "").strip()
            if not p_env or p_env.startswith("sk-"):
                preset["key_env"] = "MATH2GEO_API_KEY"
        self.cloud_key_env.setText(env_name)
        self.cloud_temp.setValue(float(m.get("temperature", 0.2)))
        self.cloud_tokens.setValue(int(m.get("max_tokens", 3000)))
        self.cloud_timeout.setValue(int(m.get("timeout", 120)))
        self.local_addr.setText(m.get("local_addr", "http://127.0.0.1:11434/v1"))
        self.local_base.setText(m.get("local_base", "http://127.0.0.1:11434/v1"))
        self.local_temp.setValue(float(m.get("temperature", 0.2)))
        self.local_tokens.setValue(int(m.get("max_tokens", 3000)))
        self.local_timeout.setValue(int(m.get("timeout", 120)))
        self.price_check.setChecked(bool(m.get("show_price")))
        self.price_box.setVisible(bool(m.get("show_price")))
        pr = dict(DEFAULTS["model"]["pricing"])
        pr.update(m.get("pricing") or {})
        self.currency.setCurrentText(pr.get("currency", "CNY"))
        self.price_in.setValue(float(pr.get("in", 0)))
        self.price_out.setValue(float(pr.get("out", 0)))
        self.chk_peak.setChecked(bool(pr.get("peak_enabled")))
        self.peak_box.setVisible(bool(pr.get("peak_enabled")))
        self.peak_start.setTime(QTime.fromString(pr.get("peak_start", "09:00"), "HH:mm"))
        self.peak_end.setTime(QTime.fromString(pr.get("peak_end", "18:00"), "HH:mm"))
        self.chk_lunch.setChecked(bool(pr.get("lunch_enabled")))
        self.lunch_start.setTime(QTime.fromString(pr.get("lunch_start", "12:00"), "HH:mm"))
        self.lunch_end.setTime(QTime.fromString(pr.get("lunch_end", "14:00"), "HH:mm"))
        days = set(pr.get("weekdays") or [])
        for cb in self.week_boxes:
            cb.setChecked(cb.property("day") in days)
        self.extra_dates.setText(pr.get("extra_dates", ""))
        self.off_in.setValue(float(pr.get("off_in", 0)))
        self.off_out.setValue(float(pr.get("off_out", 0)))

        self._apply_lock_state()
        self._mode_changed(0 if m.get("mode") == "local" else 1)

        p = self.cfg["problem"]
        self.chk_problem.setChecked(bool(p.get("include", True)))
        self.cmb_problem_mode.setCurrentText(p.get("mode", "原文"))
        self.chk_answer.setChecked(bool(p.get("answer", True)))
        self.cmb_detail.setCurrentText(p.get("detail", "丰富"))
        self.chk_difficulty.setChecked(bool(p.get("difficulty")))
        self.chk_breakthrough.setChecked(bool(p.get("breakthrough")))
        self._refresh_prompt_state()

        d = self.cfg["draw"]
        dim = str(d.get("dimension", "2D"))
        is3d = dim.upper() == "3D"
        self.rb_3d.setChecked(is3d)
        self.rb_2d.setChecked(not is3d)
        self._dimension_changed()
        self._sec_guard = True
        self.sec_az.setValue(int(d.get("section_azimuth", 35)))
        self.sec_el.setValue(int(d.get("section_elevation", 20)))
        self.sec_az_spin.setValue(int(d.get("section_azimuth", 35)))
        self.sec_el_spin.setValue(int(d.get("section_elevation", 20)))
        self.chk_section.setChecked(bool(d.get("section_show", True)))
        self.sec_opacity.setValue(int(d.get("section_opacity", 12)))
        self.sec_offset.setValue(float(d.get("section_offset", 0.0)))
        self.sec_factor.setValue(int(round(float(d.get("token_factor_3d", 2.5)) * 100)))
        self.sec_factor_value.setValue(float(d.get("token_factor_3d", 2.5)))
        self.cmb_style_3d.setCurrentText(str(d.get("style_3d", "彩色实体")))
        self.chk_section_axes.setChecked(bool(d.get("section_axes", True)))
        self.chk_section_shape.setChecked(bool(d.get("section_shape", True)))
        self._sec_guard = False
        idx = self.cmb_snap.findData(int(d.get("section_snap", 15)))
        self.cmb_snap.setCurrentIndex(max(0, idx))
        self._update_section_preview()
        self.cmb_target.setCurrentText(d.get("target", "GeoGebra"))
        self.chk_axes.setChecked(bool(d.get("axes")))
        self.chk_grid.setChecked(bool(d.get("grid")))
        self.chk_extra.setChecked(bool(d.get("extra")))
        self.cmb_format.setCurrentText(d.get("format", "SVG"))
        self.spin_dpi.setValue(int(d.get("dpi", 190)))
        self.main_color.set_color(d.get("main", VERSE["main"]))
        self.aux_color.set_color(d.get("aux", VERSE["aux"]))
        self.cmb_aux_style.setCurrentText(d.get("aux_style", "虚线"))

        self.outdir_edit.setText(self.cfg["other"].get("outdir", os.path.abspath("out")))
        self.chk_offline.setChecked(bool(self.cfg["other"].get("offline_bundle", False)))
        mode = self.cfg["other"].get("background") or "plain"
        index = self.theme_combo.findData(mode)
        self.theme_combo.setCurrentIndex(max(0, index))
        self.shell.set_mode(mode)
        self.chk_anim_startup.setChecked(bool(self.cfg["other"].get("anim_startup", True)))
        self.chk_anim_title.setChecked(bool(self.cfg["other"].get("anim_title", True)))
        if not self.chk_anim_title.isChecked():
            self._title_done = True
            self._update_welcome()
        speed = float(self.cfg["other"].get("anim_speed", 1.0) or 1.0)
        idx = self.cmb_anim_speed.findData(speed)
        self.cmb_anim_speed.setCurrentIndex(max(0, idx))
        self.chk_notify_sound.setChecked(bool(self.cfg["other"].get("notify_sound", True)))
        self.chk_notify_windows.setChecked(bool(self.cfg["other"].get("notify_windows", True)))
        self._refresh_sound_label()
        self.chk_capture_confirm.setChecked(bool(self.cfg["other"].get("capture_confirm", True)))
        self.hotkey_edit.blockSignals(True)
        self.hotkey_edit.setKeySequence(QKeySequence(self.cfg["other"].get("capture_hotkey", "Ctrl+Alt+S")))
        self.hotkey_edit.blockSignals(False)
        if hasattr(self, "capture_hint"):
            self.capture_hint.setText(f"截图热键：{self.hotkey_edit.keySequence().toString()} · 可在「其他设置」修改")
        self._register_hotkey(self.hotkey_edit.keySequence().toString())
        self._applying_config = False
        if not getattr(self, "_hotkey_connected", False):
            self._hotkey_timer = QTimer(self)
            self._hotkey_timer.setSingleShot(True)
            self._hotkey_timer.setInterval(350)
            self._hotkey_timer.timeout.connect(self._apply_hotkey_edit)
            self.hotkey_edit.keySequenceChanged.connect(lambda *_: self._hotkey_timer.start())
            self.hotkey_edit.editingFinished.connect(self._apply_hotkey_edit)
            self._hotkey_connected = True

    def _sync_active_preset(self) -> None:
        if getattr(self, "_applying_config", False):
            return
        name = self.cfg.get("model", {}).get("api_active")
        if not name:
            return
        for p in self.cfg["model"].get("api_presets") or []:
            if p.get("name") == name:
                p.update({
                    "provider": self.provider_combo.currentText(),
                    "base_url": self.cloud_base.text().strip(),
                    "model": self.cloud_name.text().strip(),
                    "api_key": self.cloud_key.text().strip(),
                    "key_env": ("MATH2GEO_API_KEY" if (not self.cloud_key_env.text().strip() or self.cloud_key_env.text().strip().startswith("sk-")) else self.cloud_key_env.text().strip()),
                    "temperature": self.cloud_temp.value(),
                    "max_tokens": self.cloud_tokens.value(),
                    "timeout": self.cloud_timeout.value(),
                })
                save_config(self.cfg)
                return

    def _collect(self) -> dict:
        cfg = json.loads(json.dumps(self.cfg))
        m = cfg["model"]
        m["mode"] = "local" if self.rb_local.isChecked() else "cloud"
        m["provider"] = self.provider_combo.currentText()
        m["model"] = self.cloud_name.text().strip()
        m["name"] = m["model"]
        m["base_url"] = self.cloud_base.text().strip()
        if not self.cfg["model"].get("classroom"):
            m["api_key"] = self.cloud_key.text().strip()
            env_name = self.cloud_key_env.text().strip()
            m["key_env"] = "MATH2GEO_API_KEY" if (not env_name or env_name.startswith("sk-")) else env_name
        m["free_provider"] = self.cfg["model"].get("free_provider", "")
        m["temperature"] = self.cloud_temp.value()
        m["max_tokens"] = self.cloud_tokens.value()
        m["timeout"] = self.cloud_timeout.value()
        m["local_addr"] = self.local_addr.text().strip()
        m["local_base"] = self.local_base.text().strip()
        m["show_price"] = self.price_check.isChecked()
        m["pricing"] = {
            "currency": self.currency.currentText(),
            "in": self.price_in.value(),
            "out": self.price_out.value(),
            "peak_enabled": self.chk_peak.isChecked(),
            "peak_start": self.peak_start.time().toString("HH:mm"),
            "peak_end": self.peak_end.time().toString("HH:mm"),
            "lunch_enabled": self.chk_lunch.isChecked(),
            "lunch_start": self.lunch_start.time().toString("HH:mm"),
            "lunch_end": self.lunch_end.time().toString("HH:mm"),
            "weekdays": [cb.property("day") for cb in self.week_boxes if cb.isChecked()],
            "extra_dates": self.extra_dates.text().strip(),
            "off_in": self.off_in.value(),
            "off_out": self.off_out.value(),
        }

        p = cfg["problem"]
        p["include"] = self.chk_problem.isChecked()
        p["mode"] = self.cmb_problem_mode.currentText()
        p["answer"] = self.chk_answer.isChecked()
        p["detail"] = self.cmb_detail.currentText()
        p["difficulty"] = self.chk_difficulty.isChecked()
        p["breakthrough"] = self.chk_breakthrough.isChecked()

        d = cfg["draw"]
        d["target"] = self.cmb_target.currentText()
        d["dimension"] = "3D" if self.rb_3d.isChecked() else "2D"
        d["section_azimuth"] = self.sec_az.value()
        d["section_elevation"] = self.sec_el.value()
        d["section_snap"] = int(self.cmb_snap.currentData() or 0)
        d["section_show"] = self.chk_section.isChecked()
        d["section_opacity"] = self.sec_opacity.value()
        d["section_offset"] = float(self.sec_offset.value())
        d["token_factor_3d"] = float(self.sec_factor_value.value())
        d["style_3d"] = self.cmb_style_3d.currentText()
        d["section_axes"] = self.chk_section_axes.isChecked()
        d["section_shape"] = self.chk_section_shape.isChecked()
        d["axes"] = self.chk_axes.isChecked()
        d["grid"] = self.chk_grid.isChecked()
        d["extra"] = self.chk_extra.isChecked()
        d["format"] = self.cmb_format.currentText()
        d["dpi"] = self.spin_dpi.value()
        d["main"] = self.main_color.color()
        d["aux"] = self.aux_color.color()
        d["aux_style"] = self.cmb_aux_style.currentText()

        cfg["other"]["outdir"] = self.outdir_edit.text().strip()
        cfg["other"]["offline_bundle"] = self.chk_offline.isChecked()
        cfg["other"]["background"] = self.theme_combo.currentData() or "plain"
        cfg["other"]["anim_startup"] = self.chk_anim_startup.isChecked()
        cfg["other"]["anim_title"] = self.chk_anim_title.isChecked()
        cfg["other"]["anim_speed"] = float(self.cmb_anim_speed.currentData() or 1.0)
        cfg["other"]["notify_sound"] = self.chk_notify_sound.isChecked()
        cfg["other"]["notify_windows"] = self.chk_notify_windows.isChecked()
        cfg["other"]["notify_sound_path"] = self.cfg["other"].get("notify_sound_path", "")
        cfg["other"]["capture_hotkey"] = self.hotkey_edit.keySequence().toString() or "Ctrl+Alt+S"
        cfg["other"]["capture_confirm"] = self.chk_capture_confirm.isChecked()
        return cfg

    def _save_clicked(self) -> None:
        self.cfg = self._collect()
        save_config(self.cfg)
        self.log("设置已保存")
        self.toast.show_message("设置已保存", "已写入本机配置，下次启动自动加载", 2.5)

    # ---------- 动作

    def _toggle_env_row(self, on: bool) -> None:
        self.env_toggle.setText("环境变量 ▴" if on else "环境变量 ▾")
        if hasattr(self, "_env_anim") and self._env_anim is not None:
            self._env_anim.stop()
        target = max(36, self.env_row.sizeHint().height())
        if on:
            self.env_row.setVisible(True)
            self.env_row.setMaximumHeight(0)
        start = self.env_row.maximumHeight() if on else self.env_row.height()
        anim = QPropertyAnimation(self.env_row, b"maximumHeight", self)
        anim.setDuration(180)
        anim.setStartValue(0 if on else start)
        anim.setEndValue(target if on else 0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        if not on:
            def _collapse() -> None:
                self.env_row.setMaximumHeight(0)
                self.env_row.setVisible(False)

            anim.finished.connect(_collapse)
        anim.start()
        self._env_anim = anim

    def _reset_classroom_count(self) -> None:
        self._classroom_count = 0
        if hasattr(self, "classroom_btn"):
            self.classroom_btn.setText("教室模式（连续点击3次锁定）")

    def _classroom_click(self) -> None:
        now = time.monotonic()
        if now - self._classroom_last > 1.5:
            self._classroom_count = 0
        self._classroom_last = now
        self._classroom_count += 1
        if self._classroom_count < 3:
            self.classroom_btn.setText(f"教室模式（再点 {3 - self._classroom_count} 次）")
            if not hasattr(self, "_classroom_timer"):
                self._classroom_timer = QTimer(self)
                self._classroom_timer.setSingleShot(True)
                self._classroom_timer.timeout.connect(self._reset_classroom_count)
            self._classroom_timer.start(1600)
            return
        self._classroom_count = 0
        if hasattr(self, "_classroom_timer"):
            self._classroom_timer.stop()
        self.classroom_btn.setText("教室模式（连续点击3次锁定）")
        if self.cfg["model"].get("classroom"):
            self.toast.show_message("教室模式", "已经开启；请到用户 API 配置中解除或修改。", 2.5)
            return
        answer = QMessageBox.question(
            self,
            "开启教室模式",
            "开启后本界面将隐藏并锁定 API Key 与环境变量，\n"
            "只能在「用户 API 配置」中查看或修改。\n\n继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.cfg["model"]["classroom"] = True
            save_config(self.cfg)
            self._apply_lock_state()

    def _apply_lock_state(self) -> None:
        locked = bool(self.cfg["model"].get("classroom"))
        self.cloud_key.setDisabled(locked)
        if locked:
            self.cloud_key.clear()
            self.cloud_key.setPlaceholderText("已锁定，请在「用户 API 配置」中查看/修改")
            self.env_row.setMaximumHeight(0)
            self.env_row.setVisible(False)
            self.env_toggle.setVisible(False)
            self.classroom_hint.setText("教室模式已开启：API Key / 环境变量已锁定。")
        else:
            self.cloud_key.setPlaceholderText("")
            self.env_toggle.setVisible(True)
            self.classroom_hint.setText("锁定后 API Key / 环境变量只能在本页的「用户 API 配置」中查看或修改。")

    def _test_connection(self) -> None:
        key = self.cloud_key.text().strip() or os.environ.get(self.cloud_key_env.text().strip(), "")
        base = self.cloud_base.text().strip()
        if not key:
            self.toast.show_message("无法测试", "先填 API Key 或环境变量", 2.5)
            return
        if not base:
            self.toast.show_message("无法测试", "先填 Base URL", 2.5)
            return
        self.test_btn.setEnabled(False)
        self.test_status.setText("测试中…")
        self._tester = ConnectionTester(base, key, self.provider_combo.currentText(), self)
        self._tester.done.connect(self._connection_done)
        self._tester.start()

    def _connection_done(self, ok: bool, code: int, body: str) -> None:
        self.test_btn.setEnabled(True)
        if ok:
            self.test_status.setText(f"连接成功（HTTP {code}）")
            QMessageBox.information(self, "连接成功", f"云端 API 可访问。\nHTTP 状态码：{code}")
            return
        mapping = {
            400: "请求参数错误",
            401: "API Key 无效或未授权",
            403: "无权限，或余额/额度不足",
            404: "Base URL 或接口路径错误",
            408: "请求超时",
            429: "触发频率限制或额度用尽",
            500: "服务端内部错误",
            502: "网关错误",
            503: "服务暂不可用",
            504: "网关超时",
        }
        if code == 0:
            desc = "网络连接失败（没有 HTTP 错误码）"
        else:
            desc = mapping.get(code, f"HTTP {code}")
        self.test_status.setText(f"{desc}（{code}）" if code else desc)
        QMessageBox.warning(
            self,
            "连接失败",
            f"{desc}\nHTTP 状态码：{code}\n\n{body or '无返回内容'}",
        )

    def _use_chatanywhere(self) -> None:
        self.cfg["model"]["free_provider"] = "ChatAnywhere（第三方）"
        self.cloud_base.setText("https://api.chatanywhere.tech/v1")
        self.cloud_name.setText("gpt-4o-mini")
        self.provider_link.setText("免费 API：ChatAnywhere（第三方）")

    def _open_user_api_config(self) -> None:
        from .api_dialogs import ApiPresetManager, KeypadDialog

        model = self.cfg["model"]
        code = model.get("api_passcode") or ""
        if bool(model.get("api_passcode_set")) or bool(code):
            keypad = KeypadDialog(
                self,
                passcode=code,
                auto_enter=bool(model.get("api_auto_enter", True)),
                confirm_enabled=True,
            )
            if keypad.exec() != QDialog.DialogCode.Accepted:
                return
        manager = ApiPresetManager(self)
        manager.exec()
        self._apply_lock_state()
        self._mode_changed(0 if self.rb_local.isChecked() else 1)

    def _provider_changed(self, idx: int, interactive: bool = True) -> None:
        orig = self.provider_combo.itemData(idx)
        if orig is None:
            orig = idx
        orig = max(0, min(int(orig), len(PROVIDERS) - 1))
        name, base, model, url = PROVIDERS[orig]
        if name == "免费 API" and ENABLE_FREE_API:
            self.free_panel.setVisible(True)
            free = self.cfg["model"].get("free_provider") or ""
            if free:
                suffix = "" if "第三方" in free else "（第三方）"
                self.provider_link.setText(f"免费 API：{free}{suffix}")
            else:
                self.provider_link.setText("推荐使用 ChatAnywhere，若使用其他供应商，请注意你的个人隐私")
            return
        self.free_panel.setVisible(False)
        self._last_provider_index = orig
        if base:
            self.cloud_base.setText(base)
        if model:
            self.cloud_name.setText(model)
        if url:
            self.provider_link.setText(f'→ 前往 <a href="{url}">{name}</a> 官方 API 开放平台申请')
        else:
            self.provider_link.setText("自定义服务商：请自行填写 Base URL 与模型名称")

    def _mode_changed(self, idx: int) -> None:
        self.model_stack.setCurrentIndex(0 if idx == 0 else 1)
        cloud = idx == 1
        self.price_check.setVisible(cloud)
        self.price_box.setVisible(cloud and self.price_check.isChecked())

    def _refresh_mode_badge(self) -> None:
        if not hasattr(self, "mode_badge"):
            return
        self.mode_badge.set_mode(self.rb_3d.isChecked())

    def _toggle_mode(self) -> None:
        if self.rb_3d.isChecked():
            self.rb_2d.setChecked(True)
        else:
            self.rb_3d.setChecked(True)
        self._dimension_changed()

    def _hotkey_parts(self, text: str):
        seq = QKeySequence(text)
        if seq.count() == 0:
            return None
        combo = seq[0]
        km = combo.keyboardModifiers()
        mods = 0
        if km & Qt.KeyboardModifier.ControlModifier:
            mods |= 0x0002
        if km & Qt.KeyboardModifier.AltModifier:
            mods |= 0x0001
        if km & Qt.KeyboardModifier.ShiftModifier:
            mods |= 0x0004
        if km & Qt.KeyboardModifier.MetaModifier:
            mods |= 0x0008
        key = int(combo.key())
        if 0x41 <= key <= 0x5A or 0x30 <= key <= 0x39:
            vk = key
        elif int(Qt.Key.Key_F1) <= key <= int(Qt.Key.Key_F24):
            vk = 0x70 + (key - int(Qt.Key.Key_F1))
        else:
            return None
        return mods, vk

    def _apply_hotkey_edit(self) -> None:
        text = self.hotkey_edit.keySequence().toString() or "Ctrl+Alt+S"
        self.cfg["other"]["capture_hotkey"] = text
        save_config(self.cfg)
        self._register_hotkey(text)
        if hasattr(self, "capture_hint"):
            self.capture_hint.setText(f"截图热键：{text} · 可在「其他设置」修改")

    def _reset_hotkey(self) -> None:
        self.hotkey_edit.blockSignals(True)
        self.hotkey_edit.setKeySequence(QKeySequence("Ctrl+Alt+S"))
        self.hotkey_edit.blockSignals(False)
        self._apply_hotkey_edit()

    def _register_hotkey(self, text: str) -> None:
        if sys.platform != "win32":
            return
        try:
            user32 = ctypes.windll.user32
            user32.UnregisterHotKey(None, self._hotkey_id)
            parts = self._hotkey_parts(text)
            if not parts:
                self.log(f"截图热键无效：{text}")
                return
            mods, vk = parts
            if user32.RegisterHotKey(None, self._hotkey_id, mods | 0x4000, vk):
                self.log(f"截图热键已注册：{text}")
            else:
                self.log(f"截图热键注册失败：{text}（可能被占用）")
        except Exception as exc:
            self.log(f"截图热键注册失败：{exc}")

    def _on_global_hotkey(self) -> None:
        if self._capture_overlay is None:
            QTimer.singleShot(0, self._start_capture)

    def _start_capture(self) -> None:
        if self._capture_overlay is not None:
            return
        if self.worker and self.worker.isRunning():
            self.toast.show_message("正在绘制", "请等待当前任务完成", 2.5)
            return
        self._capture_was_max = self.isMaximized()
        self._capture_geometry = self.geometry()
        self.hide()
        QTimer.singleShot(180, self._show_capture_overlay)

    def _show_capture_overlay(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self._restore_after_capture()
            return
        overlay = CaptureOverlay(screen)
        self._capture_overlay = overlay
        overlay.selected.connect(self._on_capture_done)
        overlay.cancelled.connect(self._on_capture_cancel)
        overlay.showFullScreen()
        overlay.raise_()
        overlay.activateWindow()

    def _restore_after_capture(self) -> None:
        self._capture_overlay = None
        self._applying_config = False
        self._tray_icon = None
        self._mci_alias = "math2geo_sound"
        if getattr(self, "_capture_was_max", False):
            self.showMaximized()
        else:
            self.show()
            if getattr(self, "_capture_geometry", None) is not None:
                self.setGeometry(self._capture_geometry)
        self.raise_()
        self.activateWindow()

    def _on_capture_cancel(self) -> None:
        self._restore_after_capture()

    def _on_capture_done(self, pix: QPixmap) -> None:
        self._restore_after_capture()
        try:
            cache = os.path.join(os.environ.get("APPDATA", tempfile.gettempdir()), "math2geo", "captures")
            os.makedirs(cache, exist_ok=True)
            path = os.path.join(cache, f"shot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            if not pix.save(path, "PNG"):
                raise RuntimeError("保存截图失败")
            if self.cfg["other"].get("capture_confirm", True):
                box = QMessageBox(self)
                box.setWindowTitle("截图识别")
                box.setText("使用这张截图作为题目并开始识别？")
                box.setIconPixmap(pix.scaled(520, 360, Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation))
                ok_btn = box.addButton("开始识别", QMessageBox.ButtonRole.AcceptRole)
                box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
                no_more = QCheckBox("以后不再提示")
                box.setCheckBox(no_more)
                box.exec()
                if box.clickedButton() is not ok_btn:
                    try:
                        os.remove(path)
                    except OSError:
                        pass
                    return
                if no_more.isChecked():
                    self.cfg["other"]["capture_confirm"] = False
                    self.chk_capture_confirm.setChecked(False)
                    save_config(self.cfg)
            self._set_file(path)
            self.log(f"截图识别：{path}")
            QTimer.singleShot(300, self._start)
        except Exception as exc:
            self.toast.show_message("截图失败", str(exc)[:60], 3.0)

    def _drop_mouse_release(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        w = self.drop.childAt(event.position().toPoint())
        while w is not None:
            if w is getattr(self, "mode_badge", None):
                return
            w = w.parentWidget()
        self._pick_file()

    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择题目", "", "题目文件 (*.png *.jpg *.jpeg *.bmp *.webp *.docx *.txt *.md)"
        )
        if path:
            self._set_file(path)

    def _edit_prompt(self) -> None:
        dialog = PromptDialog(self, self.cfg)
        dialog.exec()
        self._refresh_prompt_state()

    def _refresh_prompt_state(self) -> None:
        custom = bool((self.cfg["problem"].get("prompt") or "").strip())
        self.prompt_state.setText("已自定义" if custom else "默认预设")
        self.prompt_state.setStyleSheet(
            "color:#1F5C46; font-size:12px; font-weight:600;"
            if custom
            else "color:#5D6B63; font-size:12px;"
        )

    def _refresh_sound_label(self) -> None:
        path = self.cfg["other"].get("notify_sound_path") or ""
        self.sound_label.blockSignals(True)
        self.sound_label.clear()
        self.sound_label.addItem("默认系统提示音", "")
        if path:
            self.sound_label.addItem(os.path.basename(path), path)
        self.sound_label.setCurrentIndex(self.sound_label.count() - 1 if path else 0)
        self.sound_label.blockSignals(False)
        self.sound_label.setToolTip(path)
        if path:
            self.sound_label.setStyleSheet("QComboBox { color:#223A2E; }")
        else:
            self.sound_label.setStyleSheet("QComboBox { color:#8A9A90; }")
        self.delete_sound_btn.setEnabled(bool(path))
        self.delete_sound_btn.setStyleSheet(
            "" if path else "QPushButton:disabled { color:#AAB7B0; border-color:#E6EFE8; }"
        )

    def _on_sound_selected(self, index: int) -> None:
        path = self.sound_label.itemData(index) or ""
        self.cfg["other"]["notify_sound_path"] = path
        self._refresh_sound_label()

    def _choose_notify_sound(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择完成提示音", "", "声音文件 (*.wav *.mp3);;所有文件 (*)"
        )
        if path:
            self.cfg["other"]["notify_sound_path"] = path
            self._refresh_sound_label()

    def _play_notify_sound(self) -> None:
        if not self.cfg["other"].get("notify_sound", True):
            return
        path = self.cfg["other"].get("notify_sound_path") or ""
        if path and os.path.exists(path):
            try:
                import ctypes
                winmm = ctypes.windll.winmm
                alias = self._mci_alias
                winmm.mciSendStringW(f"close {alias}", None, 0, 0)
                kind = "waveaudio" if path.lower().endswith(".wav") else "mpegvideo"
                cmd = f'open "{path}" type {kind} alias {alias}'
                if winmm.mciSendStringW(cmd, None, 0, 0) == 0:
                    winmm.mciSendStringW(f"play {alias}", None, 0, 0)
                    return
            except Exception:
                pass
            try:
                import winsound
                if path.lower().endswith(".wav"):
                    winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                    return
            except Exception:
                pass
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass

    def _show_windows_notification(self, title: str, body: str) -> None:
        if not self.cfg["other"].get("notify_windows", True):
            return
        try:
            if not QSystemTrayIcon.isSystemTrayAvailable():
                return
            if self._tray_icon is None:
                icon = QIcon(os.path.join(os.path.dirname(__file__), "..", "assets", "icon.png"))
                self._tray_icon = QSystemTrayIcon(icon, self)
                self._tray_icon.setToolTip("Math2Geo")
                self._tray_icon.show()
            self._tray_icon.showMessage(
                title,
                body,
                QSystemTrayIcon.MessageIcon.Information,
                6000,
            )
        except Exception:
            pass

    def _reset_notify_sound(self) -> None:
        self.cfg["other"]["notify_sound_path"] = ""
        self._refresh_sound_label()

    def _preview_notify_sound(self) -> None:
        self._play_notify_sound()

    def _pick_outdir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择输出目录", self.outdir_edit.text())
        if path:
            self.outdir_edit.setText(path)

    def _theme_changed(self) -> None:
        mode = self.theme_combo.currentData() or "plain"
        self.shell.set_mode(mode)
        self.cfg.setdefault("other", {})["background"] = mode

    def _cache_paths(self) -> list[str]:
        paths: list[str] = []
        if os.path.isdir(CACHE_DIR):
            paths.append(CACHE_DIR)
        temp_dir = os.path.join(tempfile.gettempdir(), "math2geo")
        if os.path.isdir(temp_dir):
            paths.append(temp_dir)
        paths.extend(glob.glob(os.path.join(tempfile.gettempdir(), "math2geo_*.png")))
        return paths

    def _cache_size(self) -> int:
        total = 0
        for path in self._cache_paths():
            if os.path.isfile(path):
                try:
                    total += os.path.getsize(path)
                except OSError:
                    pass
            elif os.path.isdir(path):
                for root, _dirs, files in os.walk(path):
                    for name in files:
                        try:
                            total += os.path.getsize(os.path.join(root, name))
                        except OSError:
                            pass
        return total

    @staticmethod
    def _fmt_size(size: int) -> str:
        value = float(size)
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024 or unit == "GB":
                return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
            value /= 1024
        return f"{value:.1f} GB"

    def _clear_cache_now(self) -> int:
        freed = self._cache_size()
        for path in self._cache_paths():
            try:
                if os.path.isfile(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path)
            except OSError:
                pass

        self.logbox.clear()
        for index in reversed(range(self.task_layout.count())):
            item = self.task_layout.itemAt(index)
            widget = item.widget() if item is not None else None
            if widget is not None and widget.objectName() == "TaskCard":
                self.task_layout.takeAt(index)
                widget.deleteLater()
        self.tasks.clear()
        self.task_count.setText("0")
        self.empty_label.setVisible(True)
        return freed

    def _clear_cache(self) -> None:
        if self.worker and self.worker.isRunning():
            self.toast.show_message("正在绘制", "等这次画完再清空缓存", 2.5)
            return
        freed = self._cache_size()
        logs = len(self.logbox.toPlainText().splitlines())
        tasks = len(self.tasks)
        answer = QMessageBox.question(
            self,
            "清空缓存",
            f"将删除 {self._fmt_size(freed)} 临时文件，并清空 {logs} 条日志和 {tasks} 条已完成任务。\n"
            "输出目录里的图形不会被删除，此操作不可撤销。\n\n继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        freed = self._clear_cache_now()
        self.toast.show_message("缓存已清空", f"释放 {self._fmt_size(freed)}，清空 {logs} 条日志、{tasks} 条任务", 3.0)

    def _open_outdir(self) -> None:
        path = self.outdir_edit.text()
        if os.path.isdir(path):
            os.startfile(path)  # type: ignore[attr-defined]

    def _drag_enter(self, event) -> None:
        if event.mimeData().hasUrls():
            self.drop.setProperty("drag", True)
            self.drop.style().unpolish(self.drop)
            self.drop.style().polish(self.drop)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:
        self.drop.setProperty("drag", False)
        self.drop.style().unpolish(self.drop)
        self.drop.style().polish(self.drop)

    def _drop(self, event) -> None:
        urls = event.mimeData().urls()
        if urls:
            self._set_file(urls[0].toLocalFile())

    def _set_file(self, path: str) -> None:
        self.current_file = path
        self.file_chip.setText(f"已选择：{path}")
        self.file_chip.setVisible(True)
        self._switch(0)

    def _log(self, text: str) -> None:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logbox.appendPlainText(f"[{stamp}] {text}")

    log = _log

    def _start(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        if not self.current_file:
            self.toast.show_message("请先选择题目", "支持图片 / Word / 文本", 2.5)
            return
        cfg = self._collect()
        self.cfg = cfg
        save_config(cfg)

        outroot = cfg["other"]["outdir"] or os.path.abspath("out")
        stem = os.path.splitext(os.path.basename(self.current_file))[0]
        outdir = os.path.join(outroot, stem)
        os.makedirs(outdir, exist_ok=True)

        model = cfg["model"]
        if model["mode"] == "local":
            key = "local"
            base = model["local_base"] or model["local_addr"]
            name = model["name"] or "local"
        else:
            key = model["api_key"] or os.environ.get(model["key_env"], "")
            base = model["base_url"]
            name = model["model"]

        options = {
            "main_color": cfg["draw"]["main"],
            "aux_color": cfg["draw"]["aux"],
            "aux_dashed": cfg["draw"]["aux_style"] == "虚线",
            "axes": cfg["draw"]["axes"],
            "grid": cfg["draw"]["grid"],
            "dpi": cfg["draw"]["dpi"],
            "extra_format": cfg["draw"]["format"].lower() if cfg["draw"]["extra"] else "",
            "offline_bundle": cfg["other"].get("offline_bundle", False),
            "include_problem": cfg["problem"]["include"],
            "answer_detail": cfg["problem"]["detail"],
            "show_difficulty": cfg["problem"]["difficulty"],
            "show_breakthrough": cfg["problem"]["breakthrough"],
            "prompt": cfg["problem"].get("prompt") or "",
            "dimension": cfg["draw"].get("dimension", "2D"),
            "section_azimuth": cfg["draw"].get("section_azimuth", 35),
            "section_elevation": cfg["draw"].get("section_elevation", 20),
            "section_show": cfg["draw"].get("section_show", True),
            "section_opacity": cfg["draw"].get("section_opacity", 12),
            "section_offset": cfg["draw"].get("section_offset", 0.0),
            "token_factor_3d": cfg["draw"].get("token_factor_3d", 2.5),
            "style_3d": cfg["draw"].get("style_3d", "彩色实体"),
            "section_axes": cfg["draw"].get("section_axes", True),
            "section_shape": cfg["draw"].get("section_shape", True),
        }

        kwargs = dict(
            image=None,
            text=None,
            outdir=outdir,
            title=stem,
            ai_key=key,
            ai_base=base,
            ai_model=name,
            ai_timeout=model["timeout"],
            ai_max_tokens=model["max_tokens"],
            ai_temperature=model["temperature"],
            options=options,
        )
        if self.current_file.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp")):
            kwargs["image"] = self.current_file
        else:
            text = self._read_text(self.current_file)
            if not text.strip():
                self.toast.show_message("读不到题目", "这个文件里没有文字", 2.5)
                return
            kwargs["text"] = text

        self.start_btn.setEnabled(False)
        self.start_btn.setText("绘制中…")
        self.busy.setVisible(True)
        self.log("题目解析开始")
        self._t0 = time.time()
        self._price_cfg = cfg["model"]
        self.worker = Worker(kwargs)
        self.worker.log.connect(self._log)
        self.worker.done.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _read_text(self, path: str) -> str:
        from . import docx_text

        return docx_text.read_text(path)

    def _on_done(self, result: dict) -> None:
        self.busy.setVisible(False)
        self.start_btn.setEnabled(True)
        self.start_btn.setText("开始绘制")
        elapsed = time.time() - getattr(self, "_t0", time.time())
        meta = result.get("meta") or {}
        usage = meta.get("usage") or {}
        tokens = int(usage.get("total_tokens") or 0)
        cost = self._cost(usage)
        self.log("解析完成，生成图形")
        self.log(f"用时 {elapsed:.1f}s，tokens {tokens}")
        bits = [f"用时 {elapsed:.1f}s", f"{tokens} tokens"]
        if cost:
            bits.append(cost)
        self.toast.show_message("绘制完成", "  ·  ".join(bits), 4.0)
        self._play_notify_sound()
        self._show_windows_notification("Math2Geo 绘制完成", "  ·  ".join(bits))
        self._add_task(result, elapsed, tokens, cost)

    def _on_failed(self, message: str) -> None:
        self.busy.setVisible(False)
        self.start_btn.setEnabled(True)
        self.start_btn.setText("开始绘制")
        self.log(f"失败：{message}")
        self.toast.show_message("绘制失败", message[:60], 4.0)

    def _is_peak(self, p: dict) -> bool:
        now = datetime.now()
        if now.isoweekday() not in (p.get("weekdays") or []):
            return False
        if now.strftime("%Y-%m-%d") in [x.strip() for x in (p.get("extra_dates") or "").split(",") if x.strip()]:
            return False
        t = now.strftime("%H:%M")
        start = p.get("peak_start", "09:00")
        end = p.get("peak_end", "18:00")
        in_peak = (start <= t < end) if start <= end else (t >= start or t < end)
        if not in_peak:
            return False
        if p.get("lunch_enabled"):
            lunch_s = p.get("lunch_start", "12:00")
            lunch_e = p.get("lunch_end", "14:00")
            if lunch_s <= t < lunch_e:
                return False
        return True

    def _cost(self, usage: dict) -> str:
        m = getattr(self, "_price_cfg", {}) or {}
        if not m.get("show_price"):
            return ""
        p = m.get("pricing") or {}
        peak = bool(p.get("peak_enabled")) and self._is_peak(p)
        if peak:
            pin, pout = float(p.get("in") or 0), float(p.get("out") or 0)
        else:
            pin, pout = float(p.get("off_in") or 0), float(p.get("off_out") or 0)
        inp = float(usage.get("prompt_tokens") or 0)
        out = float(usage.get("completion_tokens") or 0)
        if pin == 0 and pout == 0:
            return "费用未配置单价"
        symbol = "$" if p.get("currency") == "USD" else "¥"
        return f"{symbol}{(inp * pin + out * pout) / 1e6:.4f}"

    def _add_task(self, result: dict, elapsed: float, tokens: int, cost: str) -> None:
        self.empty_label.setVisible(False)
        card = QFrame()
        card.setObjectName("TaskCard")
        card.setStyleSheet(
            f"QFrame#TaskCard {{ background:#FBFDFC; border:1px solid {VERSE['border']}; border-radius:10px; }}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)

        head = QHBoxLayout()
        name = QLabel(result.get("stem") or "题目")
        name.setStyleSheet("font-weight:700; color:#123B2C;")
        head.addWidget(name)
        head.addStretch(1)
        when = QLabel(datetime.now().strftime("%H:%M:%S"))
        when.setObjectName("Hint")
        head.addWidget(when)
        lay.addLayout(head)

        info = QLabel(f"{elapsed:.1f}s · {tokens} tokens" + (f" · {cost}" if cost else ""))
        info.setObjectName("Hint")
        lay.addWidget(info)

        path = result.get("paths", {}).get("preview", "")
        path_lab = QLabel(path)
        path_lab.setObjectName("Hint")
        path_lab.setWordWrap(True)
        lay.addWidget(path_lab)

        btns = QHBoxLayout()
        paths = result.get("paths", {})
        figure = (
            paths.get("html")
            or paths.get("sketchpad")
            or paths.get("preview")
            or path
        )
        open_btn = QPushButton("打开图形" if figure else "打开预览")
        open_btn.setObjectName("Ghost")
        target = figure or path

        def _open_target() -> None:
            try:
                if not target or not os.path.exists(target):
                    self.toast.show_message("文件不存在", "输出文件可能已被移动或删除", 3.0)
                    return
                os.startfile(target)  # type: ignore[attr-defined]
            except Exception as exc:
                self.toast.show_message("打开失败", str(exc)[:60], 3.5)

        open_btn.clicked.connect(_open_target)
        folder_btn = QPushButton("打开目录")
        folder_btn.setObjectName("Ghost")

        def _open_folder() -> None:
            folder = os.path.dirname(target or path)
            try:
                if folder and os.path.isdir(folder):
                    os.startfile(folder)  # type: ignore[attr-defined]
                else:
                    self.toast.show_message("目录不存在", folder, 3.0)
            except Exception as exc:
                self.toast.show_message("打开失败", str(exc)[:60], 3.5)

        folder_btn.clicked.connect(_open_folder)
        btns.addWidget(open_btn)
        btns.addWidget(folder_btn)
        btns.addStretch(1)
        lay.addLayout(btns)

        self.task_layout.insertWidget(self.task_layout.count() - 1, card)
        card.setMaximumHeight(0)
        target_h = max(96, card.sizeHint().height())
        anim = QPropertyAnimation(card, b"maximumHeight", self)
        anim.setDuration(280)
        anim.setStartValue(0)
        anim.setEndValue(target_h)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._task_anim = anim
        self.tasks.append(result)
        self.task_count.setText(str(len(self.tasks)))


def main() -> int:
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei UI", 9))
    icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    win = MainWindow()
    win.run()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
