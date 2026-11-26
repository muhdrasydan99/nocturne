# main.py
import os
import re
import json
import hashlib
import sys
import time
import math
import bisect
import wave
import struct
import shutil
import tempfile
import subprocess
import urllib.request
import zipfile
from datetime import datetime
from PySide6.QtCore import Qt, QTimer, QRect, QRectF, QPointF, QSize, QUrl, QThread, QEvent, Signal
from PySide6.QtGui import (
    QColor, QPainter, QPen, QBrush, QLinearGradient, QRadialGradient, QPainterPath,
    QPixmap, QIcon, QTextFormat, QTextCharFormat,
    QFont, QTextCursor, QAction, QFontDatabase, QKeySequence, QShortcut
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QSoundEffect
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPlainTextEdit, QTextEdit, QLabel, QPushButton, QLineEdit,
    QListWidget, QListWidgetItem, QSplitter, QFileDialog,
    QSlider, QTabWidget, QFrame, QToolTip, QSpinBox, QMessageBox,
    QDialog, QGridLayout, QInputDialog, QCheckBox, QComboBox, QFormLayout,
    QProgressBar, QScrollArea, QSizePolicy, QMenu, QButtonGroup
)

from lyric_engine import (
    LEXICON, ONLINE_CURATED_CATALOG, RHYME_PALETTE, ensure_offline_corpora,
    analyze_lyrics, rate_lyrics_comprehensive, find_rhymes_for_word,
    fetch_url_text, parse_wordlist_content, search_github_wordlists,
    fetch_repo_wordlist_files
)

def safe_qfont(family: str, size: int, bold: bool = False) -> QFont:
    """Constructs a QFont with a guaranteed positive point size (> 0)."""
    pt = max(1, int(size) if size is not None else 12)
    qf = QFont(family or "Segoe UI", pt)
    qf.setPointSize(pt)
    qf.setBold(bool(bold))
    qf.setStyleStrategy(QFont.PreferAntialias)
    return qf


# =====================================================================
# NOCTURNE NEON CRESCENT + SOUNDWAVE APP ICON GENERATOR
# =====================================================================
def create_nocturne_icon_pixmap(size: int = 64) -> QPixmap:
    """Renders the Nocturne neon purple crescent + 3 soundwaves + stars icon at crisp DPI."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for custom_name in ("nocturne_icon.png", "nocturne_icon_exact.jpg", "icon.png"):
        custom_path = os.path.join(base_dir, custom_name)
        if os.path.exists(custom_path):
            raw_pm = QPixmap(custom_path)
            if not raw_pm.isNull():
                out = QPixmap(size, size)
                out.fill(Qt.transparent)
                p = QPainter(out)
                p.setRenderHint(QPainter.Antialiasing)
                p.setRenderHint(QPainter.SmoothPixmapTransform)
                clip = QPainterPath()
                clip.addRoundedRect(QRectF(0, 0, size, size), size * 0.22, size * 0.22)
                p.setClipPath(clip)
                p.drawPixmap(0, 0, size, size, raw_pm)
                p.end()
                return out

    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)

    s = float(size)
    bg_path = QPainterPath()
    bg_path.addRoundedRect(QRectF(s * 0.03, s * 0.03, s * 0.94, s * 0.94), s * 0.22, s * 0.22)

    bg_grad = QLinearGradient(0, 0, s, s)
    bg_grad.setColorAt(0.0, QColor("#120A24"))
    bg_grad.setColorAt(0.55, QColor("#080510"))
    bg_grad.setColorAt(1.0, QColor("#160B2E"))
    p.fillPath(bg_path, QBrush(bg_grad))

    p.setPen(QPen(QColor("#3B1D6E"), max(1.0, s * 0.02)))
    p.drawPath(bg_path)

    glow = QRadialGradient(QPointF(s * 0.42, s * 0.50), s * 0.44)
    glow.setColorAt(0.0, QColor(168, 85, 247, 85))
    glow.setColorAt(0.6, QColor(126, 34, 206, 28))
    glow.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.fillPath(bg_path, QBrush(glow))

    stars = [
        (0.23, 0.14, 0.018, "#8B5CF6"),
        (0.16, 0.24, 0.011, "#6D28D9"),
        (0.11, 0.45, 0.015, "#7C3AED"),
        (0.67, 0.19, 0.016, "#8B5CF6"),
        (0.75, 0.28, 0.010, "#6D28D9"),
        (0.19, 0.85, 0.016, "#7C3AED"),
        (0.28, 0.81, 0.010, "#6D28D9"),
        (0.66, 0.86, 0.011, "#7C3AED"),
    ]
    p.setPen(Qt.NoPen)
    for sx, sy, sr, scol in stars:
        p.setBrush(QColor(scol))
        p.drawEllipse(QPointF(s * sx, s * sy), max(0.8, s * sr), max(0.8, s * sr))

    outer_c = QPainterPath()
    outer_c.addEllipse(QPointF(s * 0.43, s * 0.50), s * 0.28, s * 0.28)
    inner_c = QPainterPath()
    inner_c.addEllipse(QPointF(s * 0.54, s * 0.47), s * 0.23, s * 0.23)
    crescent = outer_c.subtracted(inner_c)

    p.setPen(QPen(QColor(192, 132, 252, 95), max(1.6, s * 0.045), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(QColor(46, 16, 101, 130))
    p.drawPath(crescent)

    rim_grad = QLinearGradient(s * 0.15, s * 0.22, s * 0.55, s * 0.78)
    rim_grad.setColorAt(0.0, QColor("#E9D5FF"))
    rim_grad.setColorAt(0.5, QColor("#C084FC"))
    rim_grad.setColorAt(1.0, QColor("#9333EA"))
    p.setPen(QPen(QBrush(rim_grad), max(1.2, s * 0.026), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(QColor(28, 12, 58, 180))
    p.drawPath(crescent)

    wave_origin = QPointF(s * 0.53, s * 0.48)
    wave_specs = [
        (0.11, -38, 76, "#A855F7"),
        (0.19, -42, 84, "#9333EA"),
        (0.27, -45, 90, "#7E22CE"),
    ]
    for r_mul, start_deg, span_deg, w_col in wave_specs:
        r = s * r_mul
        rect = QRectF(wave_origin.x() - r, wave_origin.y() - r, r * 2, r * 2)
        glow_c = QColor(w_col)
        glow_c.setAlpha(90)
        p.setPen(QPen(glow_c, max(1.8, s * 0.052), Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, start_deg * 16, span_deg * 16)
        p.setPen(QPen(QColor(w_col), max(1.2, s * 0.032), Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, start_deg * 16, span_deg * 16)

    p.end()
    return pm


def get_nocturne_app_icon() -> QIcon:
    icon = QIcon()
    for sz in (16, 24, 32, 48, 64, 128):
        icon.addPixmap(create_nocturne_icon_pixmap(sz))
    return icon


def build_dropdown_arrow_svg() -> str:
    """Creates a crisp high-contrast SVG chevron icon so QComboBox arrows are always visible."""
    svg_path = os.path.join(tempfile.gettempdir(), "nocturne_chevron_down.svg")
    svg_code = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" '
        'fill="none" stroke="#E9D5FF" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="6 9 12 15 18 9"></polyline>'
        '</svg>'
    )
    try:
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg_code)
    except Exception:
        pass
    return svg_path.replace("\\", "/")


def build_obsidian_qss() -> str:
    arrow_url = build_dropdown_arrow_svg()
    return f"""
QMainWindow, QWidget, QDialog {{
    background-color: #09090B;
    color: #F4F4F5;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}}
QScrollArea {{
    background-color: transparent;
    border: none;
}}
QSplitter::handle {{
    background-color: #1F1F28;
    width: 3px;
}}
QSplitter::handle:hover {{
    background-color: #A855F7;
}}
QFrame#PanelCard {{
    background-color: transparent;
    border: 1px solid #23232E;
    border-radius: 8px;
}}
QFrame#ProfileCard {{
    background-color: #12121A;
    border: 1px solid #2E2E3F;
    border-radius: 16px;
}}
QFrame#ProfileCard:hover {{
    background-color: #1B1329;
    border: 1px solid #A855F7;
}}
QLabel {{
    color: #E4E4E7;
}}
QLabel#SectionHeader {{
    color: #C084FC;
    font-weight: 800;
    font-size: 11px;
    letter-spacing: 1.1px;
    text-transform: uppercase;
}}
QLabel#TitleLogo {{
    background-color: transparent;
    color: #FFFFFF;
    font-weight: 800;
    font-size: 16px;
    letter-spacing: 1px;
}}
QLabel#BadgeStat {{
    background-color: #181820;
    border: 1px solid #4C1D95;
    color: #E9D5FF;
    padding: 4px 10px;
    border-radius: 6px;
    font-family: 'Consolas', 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 700;
}}
QPushButton {{
    background-color: #181820;
    color: #F4F4F5;
    border: 1px solid #323240;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: #261938;
    border-color: #A855F7;
    color: #FFFFFF;
}}
QPushButton:disabled {{
    background-color: #121217;
    color: #636370;
    border-color: #22222B;
}}
QPushButton#PrimaryBtn {{
    background-color: #7E22CE;
    border: 1px solid #B066FF;
    color: #FFFFFF;
    font-weight: 700;
}}
QPushButton#PrimaryBtn:hover {{
    background-color: #9333EA;
}}
QPushButton#DangerBtn {{
    background-color: #2A1215;
    border: 1px solid #991B1B;
    color: #FECACA;
}}
QPushButton#DangerBtn:hover {{
    background-color: #450A0A;
    border-color: #EF4444;
    color: #FFFFFF;
}}
QPushButton#ProfileBtn {{
    background-color: #221236;
    border: 1px solid #8B5CF6;
    color: #F3E8FF;
    padding: 5px 12px;
    border-radius: 14px;
    font-weight: 700;
}}
QPushButton#ProfileBtn:hover {{
    background-color: #3B0764;
    border-color: #D8B4FE;
}}
QPushButton#SidebarToggleBtn {{
    background-color: #15151E;
    border: 1px solid #3B285C;
    color: #D8B4FE;
    padding: 4px 9px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 700;
}}
QPushButton#SidebarToggleBtn:hover {{
    background-color: #291844;
    border-color: #A855F7;
    color: #FFFFFF;
}}
QPushButton#SidebarToggleBtn:checked {{
    background-color: #2A1447;
    border-color: #9333EA;
    color: #F3E8FF;
}}
QFrame#CollapsedSidebarStrip {{
    background-color: #0E0E13;
    border: 1px solid #23232E;
    border-radius: 8px;
}}
QPushButton#EdgeArrowBtn {{
    background-color: #161620;
    border: 1px solid #3B285C;
    color: #D8B4FE;
    border-radius: 5px;
    padding: 0px;
    font-size: 11px;
    font-weight: 800;
}}
QPushButton#EdgeArrowBtn:hover {{
    background-color: #4C1D95;
    border-color: #C084FC;
    color: #FFFFFF;
}}
QPushButton#GearBtn {{
    background-color: #181820;
    border: 1px solid #4C1D95;
    color: #D8B4FE;
    font-size: 16px;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 6px;
}}
QPushButton#GearBtn:hover {{
    background-color: #3B0764;
    border-color: #A855F7;
    color: #FFFFFF;
}}
QPushButton:checked {{
    background-color: #581C87;
    border-color: #C084FC;
    color: #FFFFFF;
}}
QLineEdit, QSpinBox {{
    background-color: #101015;
    border: 1px solid #323240;
    border-radius: 6px;
    padding: 6px 10px;
    color: #FFFFFF;
    selection-background-color: #7E22CE;
}}
QLineEdit:focus, QSpinBox:focus {{
    border-color: #A855F7;
    background-color: #14141C;
}}
QComboBox {{
    background-color: #121218;
    border: 1px solid #3F3F4E;
    border-radius: 6px;
    padding: 6px 30px 6px 10px;
    color: #FFFFFF;
    font-weight: 600;
    min-height: 20px;
}}
QComboBox:hover {{
    border-color: #A855F7;
    background-color: #191924;
}}
QComboBox:on, QComboBox:focus {{
    border-color: #C084FC;
    background-color: #191924;
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border-left: 1px solid #323240;
    background-color: #211833;
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
}}
QComboBox::drop-down:hover {{
    background-color: #581C87;
}}
QComboBox::down-arrow {{
    image: url("{arrow_url}");
    width: 12px;
    height: 12px;
}}
QComboBox QAbstractItemView {{
    background-color: #13131A;
    border: 1px solid #8B5CF6;
    border-radius: 6px;
    color: #F4F4F5;
    padding: 4px;
    outline: none;
    selection-background-color: #6B21A8;
    selection-color: #FFFFFF;
}}
QComboBox QAbstractItemView::item {{
    min-height: 26px;
    padding: 4px 10px;
    border-radius: 4px;
    color: #F4F4F5;
    background-color: #13131A;
}}
QComboBox QAbstractItemView::item:hover {{
    background-color: #2E1065;
    color: #FFFFFF;
}}
QComboBox QAbstractItemView::item:selected {{
    background-color: #6B21A8;
    color: #FFFFFF;
}}
QCheckBox {{
    spacing: 8px;
    color: #F4F4F5;
    font-weight: 500;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #525263;
    background-color: #101015;
}}
QCheckBox::indicator:checked {{
    background-color: #7E22CE;
    border-color: #D8B4FE;
}}
QListWidget {{
    background-color: transparent;
    border: 1px solid #23232E;
    border-radius: 6px;
    padding: 4px;
    outline: none;
    color: #F4F4F5;
}}
QListWidget::item {{
    padding: 6px 8px;
    border-radius: 4px;
    color: #E4E4E7;
}}
QListWidget::item:hover {{
    background-color: #1E152B;
    color: #FFFFFF;
}}
QListWidget::item:selected {{
    background-color: #4C1D95;
    color: #FFFFFF;
    border-left: 3px solid #C084FC;
}}
QTabWidget::pane {{
    border: 1px solid #23232E;
    border-radius: 6px;
    background-color: transparent;
}}
QTabBar::tab {{
    background-color: #121218;
    color: #A1A1AA;
    padding: 7px 12px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 600;
    font-size: 11px;
}}
QTabBar::tab:hover {{
    color: #F4F4F5;
    background-color: #1B1B24;
}}
QTabBar::tab:selected {{
    background-color: #26143D;
    color: #F3E8FF;
    border-bottom: 2px solid #C084FC;
}}
QSlider::groove:horizontal {{
    height: 5px;
    background: #2C2C38;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: #B066FF;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QProgressBar {{
    background-color: #14141C;
    border: 1px solid #2E2E3D;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: #A855F7;
    border-radius: 3px;
}}
QToolTip {{
    background-color: #181424;
    color: #F4F4F5;
    border: 1px solid #8B5CF6;
    padding: 6px 8px;
    border-radius: 6px;
    font-size: 12px;
}}
QMenu {{
    background-color: #13131A;
    border: 1px solid #6B21A8;
    color: #F4F4F5;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 14px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: #581C87;
    color: #FFFFFF;
}}
QScrollBar:vertical {{
    background: #0B0B0F;
    width: 8px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: #323240;
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: #8B5CF6;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    background: none;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
"""


DEFAULT_STUDIO_SETTINGS = {
    "font_family": "SF Pro",
    "font_size": 15,
    "font_bold": True,
    "word_wrap": True,
    "show_gutter": True,
    "flow_warn_threshold": 6,
    "rhyme_window": 4,
    "rhyme_granularity": "syllable",
    "debounce_ms": 200,
    "highlight_rhymes": True,
    "highlight_near_rhymes": True,
    "autosave_seconds": 0,
    "default_bpm": 140,
    "default_volume": 80,
}

SF_PRO_FONT_SOURCES = [
    (
        "SF-Pro-Display-Regular.otf",
        "https://raw.githubusercontent.com/sahibjotsaggu/San-Francisco-Pro-Fonts/master/SF-Pro-Display-Regular.otf",
    ),
    (
        "SF-Pro-Display-Bold.otf",
        "https://raw.githubusercontent.com/sahibjotsaggu/San-Francisco-Pro-Fonts/master/SF-Pro-Display-Bold.otf",
    ),
    (
        "SF-Pro-Text-Regular.otf",
        "https://raw.githubusercontent.com/sahibjotsaggu/San-Francisco-Pro-Fonts/master/SF-Pro-Text-Regular.otf",
    ),
]

SYMBOL_FONT_BLACKLIST = {
    "wingdings", "wingdings 2", "wingdings 3", "webdings", "symbol",
    "marlett", "ms outlook", "mt extra", "bookshelf symbol 7",
    "segoe mdl2 assets", "segoe fluent icons", "hololens mdl2 assets",
}


# =====================================================================
# BUNDLED "SF PRO" FONT LOADER & CLEAN FONT FILTER
# =====================================================================
def get_fonts_directory() -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundled = os.path.join(sys._MEIPASS, "fonts")
        if os.path.exists(bundled):
            return bundled
    base = os.path.dirname(os.path.abspath(__file__))
    fdir = os.path.join(base, "fonts")
    os.makedirs(fdir, exist_ok=True)
    return fdir


def register_local_fonts() -> list[str]:
    """Loads all .ttf/.otf fonts from ./fonts/ into QFontDatabase and maps 'SF Pro'."""
    fdir = get_fonts_directory()
    loaded_families = []
    if os.path.exists(fdir):
        for fname in sorted(os.listdir(fdir)):
            if fname.lower().endswith((".ttf", ".otf")):
                fpath = os.path.join(fdir, fname)
                fid = QFontDatabase.addApplicationFont(fpath)
                if fid != -1:
                    loaded_families.extend(QFontDatabase.applicationFontFamilies(fid))

    QFont.insertSubstitutions(
        "SF Pro",
        ["SF Pro Display", "SF Pro Text", "San Francisco", "Segoe UI", "Inter", "Arial"],
    )
    return sorted(list(set(loaded_families)))


class SFProProvisionWorker(QThread):
    fonts_installed = Signal()

    def run(self):
        fdir = get_fonts_directory()
        downloaded_any = False
        for filename, url in SF_PRO_FONT_SOURCES:
            dest = os.path.join(fdir, filename)
            if os.path.exists(dest) and os.path.getsize(dest) > 10000:
                continue
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "NOCTURNE-Lyricist-DAW/1.0"})
                with urllib.request.urlopen(req, timeout=12) as resp:
                    data = resp.read()
                if len(data) > 10000:
                    with open(dest, "wb") as wf:
                        wf.write(data)
                    downloaded_any = True
            except Exception:
                pass
        if downloaded_any:
            self.fonts_installed.emit()


def get_all_available_fonts() -> list[str]:
    """Returns 'SF Pro' + all valid Latin-capable fonts (filtering out broken symbol fonts & fonts missing '&')."""
    from PySide6.QtGui import QFontMetrics
    valid_fonts = {"SF Pro"}
    for fam in QFontDatabase.families():
        low = fam.strip().lower()
        if not low or low.startswith("@") or low in SYMBOL_FONT_BLACKLIST:
            continue
        systems = QFontDatabase.writingSystems(fam)
        if systems and systems == [QFontDatabase.Symbol]:
            continue
        if fam != "SF Pro":
            qfm = QFontMetrics(safe_qfont(fam, 12))
            if not (qfm.inFont("A") and qfm.inFont("a") and qfm.inFont("&")):
                continue
        valid_fonts.add(fam)

    sf_priority = [f for f in ["SF Pro", "SF Pro Display", "SF Pro Text"] if f in valid_fonts]
    others = sorted([f for f in valid_fonts if f not in sf_priority], key=lambda s: s.lower())
    return sf_priority + others


# =====================================================================
# INTERACTIVE CIRCULAR PERCENTAGE GAUGE & RATE MY LYRICS UI
# =====================================================================
class RatingRingWidget(QWidget):
    """Custom QPainter circular progress ring with animated percentage sweep."""
    def __init__(self, size: int = 82):
        super().__init__()
        self.setFixedSize(size, size)
        self.current_val = 0.0
        self.target_val = 0.0
        self.ring_color = QColor("#A855F7")
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(16)
        self.anim_timer.timeout.connect(self._step_animation)

    def set_score(self, score: int, hex_color: str = "#A855F7", animate: bool = True):
        self.target_val = max(0.0, min(100.0, float(score)))
        self.ring_color = QColor(hex_color)
        if not animate:
            self.current_val = self.target_val
            self.update()
            return
        self.current_val = 0.0
        self.anim_timer.start()

    def _step_animation(self):
        diff = self.target_val - self.current_val
        if abs(diff) < 0.6:
            self.current_val = self.target_val
            self.anim_timer.stop()
        else:
            self.current_val += max(1.2, diff * 0.16)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        margin = 8
        rect = QRectF(margin, margin, w - 2 * margin, h - 2 * margin)

        bg_pen = QPen(QColor("#272736"), 7, Qt.SolidLine, Qt.RoundCap)
        p.setPen(bg_pen)
        p.drawArc(rect, 0, 360 * 16)

        if self.current_val > 0:
            fg_pen = QPen(self.ring_color, 7, Qt.SolidLine, Qt.RoundCap)
            p.setPen(fg_pen)
            span_angle = int(-(self.current_val / 100.0) * 360 * 16)
            p.drawArc(rect, 90 * 16, span_angle)

        p.setPen(QColor("#FFFFFF"))
        num_font = safe_qfont("Segoe UI", max(13, int(w * 0.21)), bold=True)
        p.setFont(num_font)
        p.drawText(rect, Qt.AlignCenter, f"{round(self.current_val)}%")


class LyricRatingDialog(QDialog):
    """Interactive Scorecard modal with animated gauge, category bars, and click-to-jump line highlights."""
    def __init__(self, parent, rating_data: dict, on_jump_line_callback):
        super().__init__(parent)
        self.data = rating_data
        self.on_jump_line = on_jump_line_callback
        self.setWindowTitle("NOCTURNE // Rate My Lyrics — Pen Scorecard")
        self.setWindowIcon(get_nocturne_app_icon())
        self.resize(640, 660)
        self.build_ui()

    def build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        hero = QFrame()
        hero.setObjectName("PanelCard")
        hero_lay = QHBoxLayout(hero)
        hero_lay.setContentsMargins(18, 14, 18, 14)
        hero_lay.setSpacing(18)

        self.gauge = RatingRingWidget(size=108)
        self.gauge.set_score(self.data["overall"], self.data["color"], animate=True)
        hero_lay.addWidget(self.gauge)

        meta_col = QVBoxLayout()
        meta_col.setSpacing(6)
        tier_lbl = QLabel(self.data["tier"])
        tier_lbl.setTextFormat(Qt.PlainText)
        tier_lbl.setStyleSheet(f"color: {self.data['color']}; font-size: 18px; font-weight: 800; letter-spacing: 0.5px;")
        meta_col.addWidget(tier_lbl)

        m = self.data["metrics"]
        stats_line = QLabel(
            f"{m['bars']} Bars  •  {m['words']} Words  •  {m['multie_chains']} Multies  •  {m['wordplay_hits']} Wordplay/Slang"
        )
        stats_line.setTextFormat(Qt.PlainText)
        stats_line.setStyleSheet("color: #E4E4E7; font-size: 12px; font-weight: 600;")
        meta_col.addWidget(stats_line)

        sub_note = QLabel("Scored across Multie chains, Double Entendre, Cadence Pocket, Structure & Vocab.")
        sub_note.setWordWrap(True)
        sub_note.setStyleSheet("color: #A1A1AA; font-size: 11px;")
        meta_col.addWidget(sub_note)
        hero_lay.addLayout(meta_col, 1)

        layout.addWidget(hero)

        layout.addWidget(QLabel("TECHNICAL BREAKDOWN", objectName="SectionHeader"))
        bars_card = QFrame()
        bars_card.setObjectName("PanelCard")
        bars_grid = QGridLayout(bars_card)
        bars_grid.setContentsMargins(14, 12, 14, 12)
        bars_grid.setSpacing(10)

        bd = self.data["breakdown"]
        categories = [
            ("🔥 Multies & Rhyme Schemes (30%)", bd["multies"], "#A855F7"),
            ("⚡ Wordplay & Double Entendre (25%)", bd["wordplay"], "#C084FC"),
            ("🌊 Flow & Cadence Pocket (20%)", bd["flow"], "#38BDF8"),
            ("🏗 Song Structure & Sections (15%)", bd["structure"], "#34D399"),
            ("🧠 Vocabulary & Bilingual Mix (10%)", bd["vocab"], "#FBBF24"),
        ]
        for row_idx, (label_txt, val, col_hex) in enumerate(categories):
            lbl = QLabel(label_txt)
            lbl.setStyleSheet("color: #F4F4F5; font-size: 12px; font-weight: 600;")
            pbar = QProgressBar()
            pbar.setRange(0, 100)
            pbar.setValue(val)
            pbar.setTextVisible(False)
            pbar.setFixedHeight(8)
            pbar.setStyleSheet(f"""
                QProgressBar {{ background-color: #181820; border: 1px solid #2E2E3D; border-radius: 4px; }}
                QProgressBar::chunk {{ background-color: {col_hex}; border-radius: 3px; }}
            """)
            pct = QLabel(f"{val}%")
            pct.setFixedWidth(42)
            pct.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            pct.setStyleSheet(f"color: {col_hex}; font-family: 'Consolas'; font-weight: 700; font-size: 12px;")

            bars_grid.addWidget(lbl, row_idx, 0)
            bars_grid.addWidget(pbar, row_idx, 1)
            bars_grid.addWidget(pct, row_idx, 2)

        layout.addWidget(bars_card)

        layout.addWidget(QLabel("DETECTED HIGHLIGHTS (CLICK ANY LINE TO JUMP IN EDITOR)", objectName="SectionHeader"))
        self.hl_list = QListWidget()
        self.hl_list.setMinimumHeight(115)
        self.hl_list.setMaximumHeight(145)
        if self.data["highlights"]:
            for h in self.data["highlights"]:
                item = QListWidgetItem(f"{h['badge']}   —   {h['detail']}")
                item.setData(Qt.UserRole, h["line"])
                self.hl_list.addItem(item)
        else:
            self.hl_list.addItem(QListWidgetItem("No multi-syllabic chains or double entendres flagged yet."))
        self.hl_list.itemClicked.connect(self.on_highlight_clicked)
        layout.addWidget(self.hl_list)

        layout.addWidget(QLabel("STUDIO PEN COACH FEEDBACK", objectName="SectionHeader"))
        tips_box = QPlainTextEdit()
        tips_box.setReadOnly(True)
        tips_box.setMinimumHeight(80)
        tips_box.setMaximumHeight(100)
        tips_box.setStyleSheet("""
            QPlainTextEdit {
                background-color: #110D1B;
                border: 1px solid #4C1D95;
                border-radius: 6px;
                color: #F3E8FF;
                font-size: 12px;
                padding: 8px;
            }
        """)
        tips_box.setPlainText("\n".join(f"• {t}" for t in self.data["tips"]))
        layout.addWidget(tips_box)

        btn_close = QPushButton("Back to Lyric Canvas")
        btn_close.setObjectName("PrimaryBtn")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignRight)

    def on_highlight_clicked(self, item: QListWidgetItem):
        line_num = item.data(Qt.UserRole)
        if isinstance(line_num, int):
            self.on_jump_line(line_num)


# =====================================================================
# PROFILE PIN SECURITY HELPERS
# =====================================================================
def hash_pin(pin: str) -> str:
    return hashlib.sha256(f"nocturne_salt_{pin.strip()}".encode("utf-8")).hexdigest()


def get_profile_meta(profile_dir: str) -> dict:
    meta_file = os.path.join(profile_dir, "profile_meta.json")
    if os.path.exists(meta_file):
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"pin_hash": None}


def save_profile_meta(profile_dir: str, meta: dict):
    os.makedirs(profile_dir, exist_ok=True)
    meta_file = os.path.join(profile_dir, "profile_meta.json")
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def is_profile_locked(profile_dir: str) -> bool:
    return bool(get_profile_meta(profile_dir).get("pin_hash"))


class PinPromptDialog(QDialog):
    def __init__(self, parent, profile_name: str, expected_hash: str):
        super().__init__(parent)
        self.expected_hash = expected_hash
        self.setWindowTitle(f"Unlock Profile // {profile_name}")
        self.setWindowIcon(get_nocturne_app_icon())
        self.setFixedSize(360, 230)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)

        lock_lbl = QLabel(f"🔒 {profile_name}")
        lock_lbl.setTextFormat(Qt.PlainText)
        lock_lbl.setAlignment(Qt.AlignCenter)
        lock_lbl.setStyleSheet("color: #D8B4FE; font-size: 16px; font-weight: 800;")
        layout.addWidget(lock_lbl)

        sub = QLabel("Enter your Profile PIN to unlock:")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color: #E4E4E7; font-size: 12px;")
        layout.addWidget(sub)

        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.Password)
        self.pin_input.setAlignment(Qt.AlignCenter)
        self.pin_input.setMaxLength(12)
        self.pin_input.setPlaceholderText("••••")
        self.pin_input.setStyleSheet("font-size: 18px; letter-spacing: 6px; padding: 8px;")
        self.pin_input.returnPressed.connect(self.verify_pin)
        layout.addWidget(self.pin_input)

        self.err_lbl = QLabel("")
        self.err_lbl.setAlignment(Qt.AlignCenter)
        self.err_lbl.setStyleSheet("color: #FCA5A5; font-size: 11px; font-weight: 600;")
        layout.addWidget(self.err_lbl)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_unlock = QPushButton("Unlock")
        btn_unlock.setObjectName("PrimaryBtn")
        btn_unlock.clicked.connect(self.verify_pin)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_unlock)
        layout.addLayout(btn_row)

    def verify_pin(self):
        entered = self.pin_input.text().strip()
        if hash_pin(entered) == self.expected_hash:
            self.accept()
        else:
            self.err_lbl.setText("Incorrect PIN. Try again.")
            self.pin_input.clear()
            self.pin_input.setFocus()


# =====================================================================
# BUILT-IN STUDIO METRONOME (100% OFFLINE SYNTHESIZED CLICKS)
# =====================================================================
class MetronomeEngine:
    def __init__(self, on_tick_callback):
        self.on_tick = on_tick_callback
        self.bpm = 140
        self.beats_per_bar = 4
        self.current_beat = 0
        self.running = False

        self.hi_wav = os.path.join(tempfile.gettempdir(), "nocturne_engine_metro_hi.wav")
        self.lo_wav = os.path.join(tempfile.gettempdir(), "nocturne_engine_metro_lo.wav")
        self._generate_click_wav(self.hi_wav, freq=1250.0, amp=0.65)
        self._generate_click_wav(self.lo_wav, freq=820.0, amp=0.45)

        self.sound_hi = None
        self.sound_lo = None
        if os.name != "nt":
            self.sound_hi = QSoundEffect()
            self.sound_hi.setSource(QUrl.fromLocalFile(self.hi_wav))
            self.sound_hi.setVolume(0.85)

            self.sound_lo = QSoundEffect()
            self.sound_lo.setSource(QUrl.fromLocalFile(self.lo_wav))
            self.sound_lo.setVolume(0.75)

        self.timer = QTimer()
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self._tick)

    def _generate_click_wav(self, filepath: str, freq: float, amp: float):
        sample_rate = 44100
        duration_sec = 0.035
        n_samples = int(sample_rate * duration_sec)
        with wave.open(filepath, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            frames = bytearray()
            for i in range(n_samples):
                t = i / sample_rate
                envelope = math.exp(-t * 95.0)
                val = int(32767 * amp * envelope * math.sin(2.0 * math.pi * freq * t))
                frames.extend(struct.pack("<h", max(-32768, min(32767, val))))
            wf.writeframes(bytes(frames))

    def set_bpm(self, bpm: int):
        self.bpm = max(40, min(260, bpm))
        if self.running:
            self.timer.setInterval(round(60000.0 / self.bpm))

    def set_beats_per_bar(self, beats: int):
        self.beats_per_bar = beats
        self.current_beat = 0

    def start(self):
        self.running = True
        self.current_beat = 0
        self._tick()
        self.timer.start(round(60000.0 / self.bpm))

    def stop(self):
        self.running = False
        self.timer.stop()
        self.current_beat = 0
        self.on_tick(0)

    def _play_engine_click(self, is_high: bool):
        if os.name == "nt":
            try:
                import winsound
                wav_path = self.hi_wav if is_high else self.lo_wav
                winsound.PlaySound(
                    wav_path,
                    winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
                )
                return
            except Exception:
                pass
        sfx = self.sound_hi if is_high else self.sound_lo
        if sfx is not None:
            sfx.play()

    def _tick(self):
        beat_num = (self.current_beat % self.beats_per_bar) + 1
        self._play_engine_click(beat_num == 1)
        self.on_tick(beat_num)
        self.current_beat += 1


# =====================================================================
# BACKGROUND WORKERS FOR ONLINE SLANG & LANGUAGE DOWNLOADS
# =====================================================================
class OnlineDownloadWorker(QThread):
    finished_ok = Signal(str, int)
    failed = Signal(str)

    def __init__(self, pack_name: str, url: str, is_json: bool = False):
        super().__init__()
        self.pack_name = pack_name
        self.url = url
        self.is_json = is_json

    def run(self):
        try:
            raw = fetch_url_text(self.url, timeout=20)
            words = parse_wordlist_content(raw, is_json=self.is_json)
            if not words:
                self.failed.emit("Downloaded file contained no valid vocabulary words.")
                return
            total = LEXICON.add_language_pack(self.pack_name, words)
            self.finished_ok.emit(self.pack_name, total)
        except Exception as e:
            self.failed.emit(str(e))


class GitHubSearchWorker(QThread):
    repos_ready = Signal(list)
    files_ready = Signal(list)
    failed = Signal(str)

    def __init__(self, mode: str, query_or_repo: str, branch: str = "main"):
        super().__init__()
        self.mode = mode
        self.target = query_or_repo
        self.branch = branch

    def run(self):
        try:
            if self.mode == "repos":
                res = search_github_wordlists(self.target)
                self.repos_ready.emit(res)
            else:
                res = fetch_repo_wordlist_files(self.target, self.branch)
                self.files_ready.emit(res)
        except Exception as e:
            self.failed.emit(str(e))


class BeatWaveformAnalyzerWorker(QThread):
    """Background waveform analyzer to extract BPM, downbeat drop, and beat timestamps."""
    analysis_ready = Signal(str, float, list)
    analysis_failed = Signal(str, str)

    def __init__(self, audio_path: str):
        super().__init__()
        self.audio_path = audio_path

    def _align_beat_grid_to_downbeat(self, y, sr: int, beat_times_ms: list[float], bpm_val: float) -> list[float]:
        """Shifts the beat grid phase to the strongest low-end/transient downbeat (Beat 1 of 4)."""
        import numpy as np
        if len(beat_times_ms) < 4:
            return beat_times_ms

        beat_period_ms = 60000.0 / max(40.0, min(260.0, bpm_val))
        # Measure transient energy around each detected beat within +/- 35ms
        win = max(1, int(sr * 0.035))
        energies = []
        for t_ms in beat_times_ms[:32]:
            center = int((t_ms / 1000.0) * sr)
            s = max(0, center - win)
            e = min(len(y), center + win)
            if e > s:
                seg = y[s:e]
                energies.append(float(np.sqrt(np.mean(seg * seg))))
            else:
                energies.append(0.0)

        # Find which phase (0, 1, 2, or 3) has the strongest average downbeat energy
        phase_scores = [0.0, 0.0, 0.0, 0.0]
        for idx, eng in enumerate(energies):
            phase_scores[idx % 4] += eng
        best_phase = int(np.argmax(phase_scores))

        aligned = beat_times_ms[best_phase:]
        # Backfill earlier beats before first detected beat down to >= 0ms
        while aligned and (aligned[0] - beat_period_ms) >= 0.0:
            aligned.insert(0, aligned[0] - beat_period_ms)
        return aligned

    def _load_mono_audio_fallback(self, target_sr: int = 22050):
        """Fallback audio loader using wave or ffmpeg when librosa audio backend fails."""
        import numpy as np
        ext = os.path.splitext(self.audio_path)[1].lower()
        wav_to_read = self.audio_path
        temp_wav = None

        try:
            if ext != ".wav":
                temp_wav = os.path.join(
                    tempfile.gettempdir(),
                    f"nocturne_probe_{abs(hash(self.audio_path))}.wav"
                )
                cmd = [
                    "ffmpeg", "-y", "-i", self.audio_path,
                    "-ac", "1", "-ar", str(target_sr), "-f", "wav", temp_wav
                ]
                creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags, check=True)
                wav_to_read = temp_wav

            with wave.open(wav_to_read, "rb") as wf:
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                sr = wf.getframerate()
                n_frames = wf.getnframes()
                raw = wf.readframes(n_frames)

            if sampwidth == 2:
                arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            elif sampwidth == 4:
                arr = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
            else:
                arr = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0

            if n_channels > 1:
                arr = arr.reshape(-1, n_channels).mean(axis=1)
            return arr, sr
        finally:
            if temp_wav and os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except Exception:
                    pass

    def _analyze_with_numpy_onset(self, y, sr: int):
        """Pure-NumPy onset autocorrelation BPM & beat grid tracker."""
        import numpy as np
        hop = 512
        frame_len = 1024
        if len(y) < frame_len * 4:
            return None, []

        # Frame RMS energy envelope + half-wave rectified spectral/energy flux
        n_frames = (len(y) - frame_len) // hop
        frames = np.lib.stride_tricks.as_strided(
            y,
            shape=(n_frames, frame_len),
            strides=(y.strides[0] * hop, y.strides[0])
        )
        rms = np.sqrt(np.mean(frames * frames, axis=1) + 1e-12)
        onset = np.maximum(0.0, np.diff(rms, prepend=rms[0]))
        if np.max(onset) > 0:
            onset = onset / np.max(onset)

        fps = sr / float(hop)
        min_lag = max(1, int(round(fps * 60.0 / 200.0)))
        max_lag = max(min_lag + 1, int(round(fps * 60.0 / 65.0)))

        ac = np.correlate(onset - np.mean(onset), onset - np.mean(onset), mode="full")
        ac = ac[len(ac) // 2:]
        search_slice = ac[min_lag:min(max_lag, len(ac))]
        if len(search_slice) == 0:
            return None, []

        best_lag = min_lag + int(np.argmax(search_slice))
        bpm_val = 60.0 * fps / float(best_lag)
        while bpm_val < 75.0:
            bpm_val *= 2.0
        while bpm_val > 185.0:
            bpm_val /= 2.0

        beat_period_ms = 60000.0 / bpm_val
        duration_ms = (len(y) / float(sr)) * 1000.0

        # Find best phase offset in the first 2 seconds
        step_ms = 10.0
        best_phase_ms = 0.0
        best_score = -1.0
        onset_times_ms = (np.arange(len(onset)) * hop / float(sr)) * 1000.0

        phase = 0.0
        while phase < beat_period_ms:
            grid = np.arange(phase, min(duration_ms, phase + beat_period_ms * 32), beat_period_ms)
            idxs = np.clip(np.searchsorted(onset_times_ms, grid), 0, len(onset) - 1)
            score = float(np.sum(onset[idxs]))
            if score > best_score:
                best_score = score
                best_phase_ms = phase
            phase += step_ms

        beat_times_ms = list(np.arange(best_phase_ms, duration_ms, beat_period_ms))
        return float(bpm_val), beat_times_ms

    def run(self):
        try:
            y = None
            sr = 22050
            bpm_val = None
            beat_times_ms = []

            try:
                import numpy as np
                import librosa

                y, sr = librosa.load(self.audio_path, sr=22050, mono=True)
                if y is not None and len(y) >= sr:
                    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
                    tempo, beat_frames = librosa.beat.beat_track(
                        onset_envelope=onset_env,
                        sr=sr,
                        start_bpm=130.0,
                        trim=False,
                    )
                    if hasattr(tempo, "__len__"):
                        bpm_val = float(np.asarray(tempo).reshape(-1)[0]) if len(tempo) > 0 else 140.0
                    else:
                        bpm_val = float(tempo)

                    beat_times_sec = librosa.frames_to_time(beat_frames, sr=sr)
                    beat_times_ms = [float(t * 1000.0) for t in beat_times_sec]

                    if len(beat_times_ms) >= 4:
                        diffs = np.diff(beat_times_ms)
                        valid_diffs = diffs[(diffs > 220.0) & (diffs < 1500.0)]
                        if len(valid_diffs) > 0:
                            bpm_val = 60000.0 / float(np.median(valid_diffs))
            except Exception:
                y, sr = self._load_mono_audio_fallback(22050)
                bpm_val, beat_times_ms = self._analyze_with_numpy_onset(y, sr)

            if y is None or len(y) < sr or bpm_val is None or len(beat_times_ms) < 4:
                self.analysis_failed.emit(self.audio_path, "Could not detect beat grid.")
                return

            bpm_val = max(40.0, min(260.0, float(bpm_val)))
            beat_times_ms = self._align_beat_grid_to_downbeat(y, sr, beat_times_ms, bpm_val)
            self.analysis_ready.emit(self.audio_path, bpm_val, beat_times_ms)
        except Exception as e:
            self.analysis_failed.emit(self.audio_path, str(e))

# =====================================================================
# PROFILE SETTINGS DIALOG
# =====================================================================
class ProfileSettingsDialog(QDialog):
    def __init__(self, parent, profiles_root: str, profile_name: str, can_delete: bool = True):
        super().__init__(parent)
        self.profiles_root = profiles_root
        self.profile_name = profile_name
        self.can_delete = can_delete
        self.new_profile_name = profile_name
        self.was_deleted = False

        self.setWindowTitle(f"Edit Profile // {profile_name}")
        self.setWindowIcon(get_nocturne_app_icon())
        self.setFixedSize(510, 530)
        self.build_ui()

    def build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        p_dir = os.path.join(self.profiles_root, self.profile_name)
        vault_dir = os.path.join(p_dir, "tracks_vault")
        track_count = len([f for f in os.listdir(vault_dir) if f.endswith(".json")]) if os.path.exists(vault_dir) else 0

        slang_count = 0
        slang_file = os.path.join(p_dir, "custom_slang.json")
        if os.path.exists(slang_file):
            try:
                with open(slang_file, "r", encoding="utf-8") as f:
                    slang_count = len(json.load(f))
            except Exception:
                pass

        packs_count = 0
        packs_file = os.path.join(p_dir, "language_packs.json")
        if os.path.exists(packs_file):
            try:
                with open(packs_file, "r", encoding="utf-8") as f:
                    packs_count = len(json.load(f))
            except Exception:
                pass

        locked = is_profile_locked(p_dir)
        lock_badge = "🔒 PIN Protected" if locked else "🔓 Unlocked"

        info_card = QFrame()
        info_card.setObjectName("PanelCard")
        info_lay = QVBoxLayout(info_card)
        self.lbl_title = QLabel(f"👤 {self.profile_name}   ({lock_badge})")
        self.lbl_title.setTextFormat(Qt.PlainText)
        self.lbl_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #FFFFFF;")
        lbl_stats = QLabel(f"{track_count} Saved Tracks  •  {slang_count} Custom Slang  •  {packs_count} Language Packs")
        lbl_stats.setStyleSheet("color: #D8B4FE; font-size: 12px;")
        info_lay.addWidget(self.lbl_title)
        info_lay.addWidget(lbl_stats)
        layout.addWidget(info_card)

        layout.addWidget(QLabel("RENAME PROFILE", objectName="SectionHeader"))
        rename_row = QHBoxLayout()
        self.rename_input = QLineEdit(self.profile_name)
        btn_rename = QPushButton("Rename")
        btn_rename.setObjectName("PrimaryBtn")
        btn_rename.clicked.connect(self.rename_profile)
        rename_row.addWidget(self.rename_input)
        rename_row.addWidget(btn_rename)
        layout.addLayout(rename_row)

        layout.addWidget(QLabel("PROFILE SECURITY (PIN LOCK)", objectName="SectionHeader"))
        pin_row = QHBoxLayout()
        self.pin_edit_input = QLineEdit()
        self.pin_edit_input.setEchoMode(QLineEdit.Password)
        self.pin_edit_input.setMaxLength(12)
        self.pin_edit_input.setPlaceholderText("Enter new 4-8 digit PIN...")
        btn_set_pin = QPushButton("🔒 Set / Update PIN")
        btn_set_pin.setObjectName("PrimaryBtn")
        btn_set_pin.clicked.connect(self.set_profile_pin)

        self.btn_remove_pin = QPushButton("Remove PIN")
        self.btn_remove_pin.setEnabled(locked)
        self.btn_remove_pin.clicked.connect(self.remove_profile_pin)

        pin_row.addWidget(self.pin_edit_input)
        pin_row.addWidget(btn_set_pin)
        pin_row.addWidget(self.btn_remove_pin)
        layout.addLayout(pin_row)

        layout.addWidget(QLabel("BACKUP & DATA MANAGEMENT", objectName="SectionHeader"))
        btn_backup = QPushButton("📦 Export Full Profile Backup (.ZIP)")
        btn_backup.clicked.connect(self.backup_profile_zip)
        layout.addWidget(btn_backup)

        btn_clone = QPushButton("🧬 Duplicate / Clone Profile")
        btn_clone.clicked.connect(self.clone_profile)
        layout.addWidget(btn_clone)

        layout.addStretch()

        bottom_row = QHBoxLayout()
        if self.can_delete:
            btn_del = QPushButton("🗑 Delete Profile")
            btn_del.setObjectName("DangerBtn")
            btn_del.clicked.connect(self.delete_profile)
            bottom_row.addWidget(btn_del)

        bottom_row.addStretch()
        btn_close = QPushButton("Done")
        btn_close.clicked.connect(self.accept)
        bottom_row.addWidget(btn_close)
        layout.addLayout(bottom_row)

    def set_profile_pin(self):
        pin = self.pin_edit_input.text().strip()
        if len(pin) < 4:
            QMessageBox.warning(self, "PIN Too Short", "Please enter at least 4 characters/digits for your PIN.")
            return
        p_dir = os.path.join(self.profiles_root, self.profile_name)
        meta = get_profile_meta(p_dir)
        meta["pin_hash"] = hash_pin(pin)
        save_profile_meta(p_dir, meta)
        self.pin_edit_input.clear()
        self.btn_remove_pin.setEnabled(True)
        self.lbl_title.setText(f"👤 {self.profile_name}   (🔒 PIN Protected)")
        QMessageBox.information(self, "Profile Locked", f"PIN lock enabled for '{self.profile_name}'.")

    def remove_profile_pin(self):
        p_dir = os.path.join(self.profiles_root, self.profile_name)
        meta = get_profile_meta(p_dir)
        meta["pin_hash"] = None
        save_profile_meta(p_dir, meta)
        self.btn_remove_pin.setEnabled(False)
        self.lbl_title.setText(f"👤 {self.profile_name}   (🔓 Unlocked)")
        QMessageBox.information(self, "PIN Removed", f"PIN lock removed from '{self.profile_name}'.")

    def rename_profile(self):
        raw = self.rename_input.text().strip()
        safe = "".join(c for c in raw if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
        if not safe:
            QMessageBox.warning(self, "Invalid Name", "Please enter a valid profile name.")
            return
        if safe == self.profile_name:
            return

        old_path = os.path.join(self.profiles_root, self.profile_name)
        new_path = os.path.join(self.profiles_root, safe)
        if os.path.exists(new_path):
            QMessageBox.warning(self, "Already Exists", f"A profile named '{safe}' already exists.")
            return

        try:
            os.rename(old_path, new_path)
            self.profile_name = safe
            self.new_profile_name = safe
            self.setWindowTitle(f"Edit Profile // {safe}")
            locked = is_profile_locked(new_path)
            self.lbl_title.setText(f"👤 {safe}   ({'🔒 PIN Protected' if locked else '🔓 Unlocked'})")
            QMessageBox.information(self, "Renamed", f"Profile renamed to '{safe}'.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not rename profile folder:\n{e}")

    def backup_profile_zip(self):
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        default_name = f"NOCTURNE_Backup_{self.profile_name}_{stamp}.zip"
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Profile Backup", default_name, "ZIP Archive (*.zip)"
        )
        if not save_path:
            return

        p_dir = os.path.join(self.profiles_root, self.profile_name)
        try:
            with zipfile.ZipFile(save_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(p_dir):
                    for file in files:
                        full_p = os.path.join(root, file)
                        rel_p = os.path.relpath(full_p, p_dir)
                        zf.write(full_p, rel_p)
            QMessageBox.information(self, "Backup Complete", f"Profile backed up to:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Backup Failed", str(e))

    def clone_profile(self):
        name, ok = QInputDialog.getText(
            self, "Clone Profile", "Enter name for cloned profile:", text=f"{self.profile_name}_Copy"
        )
        if not ok or not name.strip():
            return
        safe = "".join(c for c in name.strip() if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
        if not safe:
            return
        src = os.path.join(self.profiles_root, self.profile_name)
        dst = os.path.join(self.profiles_root, safe)
        if os.path.exists(dst):
            QMessageBox.warning(self, "Exists", f"Profile '{safe}' already exists.")
            return
        shutil.copytree(src, dst)
        QMessageBox.information(self, "Cloned", f"Created cloned profile '{safe}'.")

    def delete_profile(self):
        reply = QMessageBox.question(
            self, "Delete Profile",
            f"Permanently delete profile '{self.profile_name}' and all its tracks?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            shutil.rmtree(os.path.join(self.profiles_root, self.profile_name), ignore_errors=True)
            self.was_deleted = True
            self.accept()


# =====================================================================
# NOCTURNE STUDIO SETTINGS DIALOG
# =====================================================================
class NocturneSettingsDialog(QDialog):
    def __init__(self, parent, current_settings: dict, vault_dir: str, on_apply_callback):
        super().__init__(parent)
        self.settings = dict(current_settings)
        self.vault_dir = vault_dir
        self.on_apply = on_apply_callback

        self.setWindowTitle("NOCTURNE // Studio Settings")
        self.setWindowIcon(get_nocturne_app_icon())
        self.setFixedSize(600, 560)
        self.build_ui()

    def build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        hdr = QLabel("⚙ NOCTURNE STUDIO PREFERENCES")
        hdr.setObjectName("SectionHeader")
        layout.addWidget(hdr)

        tabs = QTabWidget()

        # --- TAB 1: EDITOR & TYPOGRAPHY ---
        ed_tab = QWidget()
        ed_layout = QVBoxLayout(ed_tab)
        ed_layout.setContentsMargins(16, 16, 16, 16)
        ed_layout.setSpacing(12)

        ed_form = QFormLayout()
        ed_form.setSpacing(10)

        self.font_combo = QComboBox()
        self.font_combo.setEditable(False)
        self.font_combo.setMaxVisibleItems(18)
        self.font_combo.setMinimumWidth(260)
        all_fonts = get_all_available_fonts()
        self.font_combo.addItems(all_fonts)
        idx = self.font_combo.findText(self.settings.get("font_family", "SF Pro"), Qt.MatchFixedString)
        if idx >= 0:
            self.font_combo.setCurrentIndex(idx)
        self.font_combo.currentTextChanged.connect(self.update_font_preview)
        ed_form.addRow(f"Lyric Editor Font ({len(all_fonts)}):", self.font_combo)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(11, 36)
        self.font_size_spin.setSuffix(" pt")
        self.font_size_spin.setValue(self.settings.get("font_size", 15))
        self.font_size_spin.valueChanged.connect(self.update_font_preview)
        ed_form.addRow("Font Size:", self.font_size_spin)

        self.chk_bold = QCheckBox("Use Bold Font Weight in Lyric Canvas")
        self.chk_bold.setChecked(self.settings.get("font_bold", True))
        self.chk_bold.stateChanged.connect(self.update_font_preview)
        ed_form.addRow("", self.chk_bold)

        self.chk_wrap = QCheckBox("Word Wrap Long Bars")
        self.chk_wrap.setChecked(self.settings.get("word_wrap", True))
        ed_form.addRow("", self.chk_wrap)

        self.chk_gutter = QCheckBox("Show Live Syllable Counter Gutter")
        self.chk_gutter.setChecked(self.settings.get("show_gutter", True))
        ed_form.addRow("", self.chk_gutter)

        self.flow_thresh_spin = QSpinBox()
        self.flow_thresh_spin.setRange(3, 12)
        self.flow_thresh_spin.setSuffix(" syllables")
        self.flow_thresh_spin.setValue(self.settings.get("flow_warn_threshold", 6))
        ed_form.addRow("Flow Cadence Warning Jump:", self.flow_thresh_spin)

        ed_layout.addLayout(ed_form)

        ed_layout.addWidget(QLabel("LIVE FONT & AMPERSAND (&) PREVIEW", objectName="SectionHeader"))
        self.font_preview_lbl = QLabel()
        self.font_preview_lbl.setTextFormat(Qt.PlainText)
        self.font_preview_lbl.setAlignment(Qt.AlignCenter)
        self.font_preview_lbl.setMinimumHeight(62)
        ed_layout.addWidget(self.font_preview_lbl)
        ed_layout.addStretch()

        self.update_font_preview()
        tabs.addTab(ed_tab, "Editor & Typography")

        # --- TAB 2: RHYME & HIGHLIGHT ENGINE ---
        eng_tab = QWidget()
        eng_form = QFormLayout(eng_tab)
        eng_form.setContentsMargins(16, 16, 16, 16)
        eng_form.setSpacing(12)

        self.rhyme_win_spin = QSpinBox()
        self.rhyme_win_spin.setRange(2, 10)
        self.rhyme_win_spin.setSuffix(" lines")
        self.rhyme_win_spin.setValue(self.settings.get("rhyme_window", 4))
        eng_form.addRow("Rhyme Detection Range:", self.rhyme_win_spin)

        self.granularity_combo = QComboBox()
        self.granularity_combo.addItem("Rhyming syllables only (e.g. 'mite' in dynamite)", "syllable")
        self.granularity_combo.addItem("Whole words", "word")
        gi = self.granularity_combo.findData(self.settings.get("rhyme_granularity", "syllable"))
        self.granularity_combo.setCurrentIndex(max(0, gi))
        eng_form.addRow("Highlight Rhymes By:", self.granularity_combo)

        self.debounce_spin = QSpinBox()
        self.debounce_spin.setRange(100, 1000)
        self.debounce_spin.setSingleStep(50)
        self.debounce_spin.setSuffix(" ms")
        self.debounce_spin.setValue(self.settings.get("debounce_ms", 200))
        eng_form.addRow("Analysis Refresh Delay:", self.debounce_spin)

        self.chk_hl_rhymes = QCheckBox("Highlight End & Internal Rhymes")
        self.chk_hl_rhymes.setChecked(self.settings.get("highlight_rhymes", True))
        eng_form.addRow("", self.chk_hl_rhymes)

        self.chk_hl_near = QCheckBox("Dotted Amber Underline on Near-Rhymes (time ~ mine)")
        self.chk_hl_near.setChecked(self.settings.get("highlight_near_rhymes", True))
        eng_form.addRow("", self.chk_hl_near)

        tabs.addTab(eng_tab, "Rhyme & Highlights")

        # --- TAB 3: AUDIO & WORKSPACE ---
        ws_tab = QWidget()
        ws_form = QFormLayout(ws_tab)
        ws_form.setContentsMargins(16, 16, 16, 16)
        ws_form.setSpacing(12)

        self.autosave_combo = QComboBox()
        self.autosave_combo.addItem("Off (Manual Save Only)", 0)
        self.autosave_combo.addItem("Every 30 Seconds", 30)
        self.autosave_combo.addItem("Every 60 Seconds", 60)
        self.autosave_combo.addItem("Every 2 Minutes", 120)
        cur_as = self.settings.get("autosave_seconds", 0)
        as_idx = self.autosave_combo.findData(cur_as)
        if as_idx >= 0:
            self.autosave_combo.setCurrentIndex(as_idx)
        ws_form.addRow("Auto-Save Current Track:", self.autosave_combo)

        self.def_bpm_spin = QSpinBox()
        self.def_bpm_spin.setRange(60, 220)
        self.def_bpm_spin.setValue(self.settings.get("default_bpm", 140))
        ws_form.addRow("Default Studio BPM:", self.def_bpm_spin)

        self.def_vol_spin = QSpinBox()
        self.def_vol_spin.setRange(0, 100)
        self.def_vol_spin.setSuffix(" %")
        self.def_vol_spin.setValue(self.settings.get("default_volume", 80))
        ws_form.addRow("Default Beat Volume:", self.def_vol_spin)

        btn_open_folder = QPushButton("📂 Open Local Track Vault Folder")
        btn_open_folder.clicked.connect(self.open_vault_folder)
        ws_form.addRow("Local Storage:", btn_open_folder)

        tabs.addTab(ws_tab, "Audio & Workspace")
        layout.addWidget(tabs)

        btn_row = QHBoxLayout()
        btn_reset = QPushButton("Reset Defaults")
        btn_reset.clicked.connect(self.reset_defaults)
        btn_row.addWidget(btn_reset)
        btn_row.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Save & Apply")
        btn_save.setObjectName("PrimaryBtn")
        btn_save.clicked.connect(self.save_and_apply)

        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def update_font_preview(self):
        fam = self.font_combo.currentText() or "SF Pro"
        sz = self.font_size_spin.value()
        bold = self.chk_bold.isChecked()
        qfont = safe_qfont(fam, sz, bold=bold)
        self.font_preview_lbl.setFont(qfont)
        self.font_preview_lbl.setText("Heavy is the crown & soul / Susun kata tajam & padu")
        self.font_preview_lbl.setStyleSheet("""
            background-color: #101016;
            border: 1px solid #4C1D95;
            border-radius: 6px;
            color: #FFFFFF;
            padding: 8px;
        """)

    def open_vault_folder(self):
        if os.path.exists(self.vault_dir):
            os.startfile(self.vault_dir)

    def reset_defaults(self):
        self.settings = dict(DEFAULT_STUDIO_SETTINGS)
        self.on_apply(self.settings)
        self.accept()

    def save_and_apply(self):
        chosen_font = self.font_combo.currentText() or "SF Pro"
        self.settings.update({
            "font_family": chosen_font,
            "font_size": self.font_size_spin.value(),
            "font_bold": self.chk_bold.isChecked(),
            "word_wrap": self.chk_wrap.isChecked(),
            "show_gutter": self.chk_gutter.isChecked(),
            "flow_warn_threshold": self.flow_thresh_spin.value(),
            "rhyme_window": self.rhyme_win_spin.value(),
            "rhyme_granularity": self.granularity_combo.currentData() or "syllable",
            "debounce_ms": self.debounce_spin.value(),
            "highlight_rhymes": self.chk_hl_rhymes.isChecked(),
            "highlight_near_rhymes": self.chk_hl_near.isChecked(),
            "autosave_seconds": self.autosave_combo.currentData(),
            "default_bpm": self.def_bpm_spin.value(),
            "default_volume": self.def_vol_spin.value(),
        })
        self.on_apply(self.settings)
        self.accept()


# =====================================================================
# CHROME-STYLE PROFILE LAUNCHER DIALOG (WITH NOCTURNE ICON)
# =====================================================================
class ProfileLauncherDialog(QDialog):
    def __init__(self, profiles_root: str):
        super().__init__()
        self.profiles_root = profiles_root
        os.makedirs(self.profiles_root, exist_ok=True)
        self.selected_profile = None

        self.setWindowTitle("NOCTURNE // Select Studio Profile")
        self.setWindowIcon(get_nocturne_app_icon())
        self.setFixedSize(760, 540)
        self.ensure_default_profile()
        self.build_ui()

    def ensure_default_profile(self):
        existing = [
            d for d in os.listdir(self.profiles_root)
            if os.path.isdir(os.path.join(self.profiles_root, d))
        ]
        if not existing:
            os.makedirs(os.path.join(self.profiles_root, "Main_Studio", "tracks_vault"), exist_ok=True)

    def build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 22, 32, 24)
        layout.setSpacing(12)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        brand_row.addStretch()

        icon_lbl = QLabel()
        icon_lbl.setPixmap(create_nocturne_icon_pixmap(38))
        icon_lbl.setFixedSize(38, 38)
        icon_lbl.setStyleSheet("background: transparent;")
        brand_row.addWidget(icon_lbl)

        header = QLabel("nocturne")
        header.setStyleSheet("background: transparent; color: #C084FC; font-size: 15px; font-weight: 800; letter-spacing: 2px;")
        brand_row.addWidget(header)

        brand_row.addStretch()
        layout.addLayout(brand_row)

        title = QLabel("Who's writing today?")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("background: transparent; color: #FFFFFF; font-size: 24px; font-weight: 800;")
        layout.addWidget(title)

        sub = QLabel("Choose or create your profile.")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("background: transparent; color: #B4B4BE; font-size: 12px;")
        layout.addWidget(sub)

        self.grid_container = QWidget()
        self.grid = QGridLayout(self.grid_container)
        self.grid.setSpacing(14)
        layout.addWidget(self.grid_container)
        layout.addStretch()

        bottom_bar = QHBoxLayout()
        btn_restore = QPushButton("📥 Restore Profile from Backup (.ZIP)")
        btn_restore.clicked.connect(self.restore_profile_from_zip)
        bottom_bar.addStretch()
        bottom_bar.addWidget(btn_restore)
        bottom_bar.addStretch()
        layout.addLayout(bottom_bar)

        self.refresh_cards()

    def refresh_cards(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        profiles = sorted([
            d for d in os.listdir(self.profiles_root)
            if os.path.isdir(os.path.join(self.profiles_root, d))
        ])

        col_count = 3
        for idx, prof_name in enumerate(profiles):
            card = self.create_profile_card(prof_name, can_delete=(len(profiles) > 1))
            self.grid.addWidget(card, idx // col_count, idx % col_count)

        add_idx = len(profiles)
        card_qss = """
            QFrame#ProfileCard {
                background-color: #12121A;
                border: 1px solid #2E2E3F;
                border-radius: 16px;
            }
            QFrame#ProfileCard:hover {
                background-color: #1B1329;
                border: 1px solid #A855F7;
            }
        """

        add_card = QFrame()
        add_card.setObjectName("ProfileCard")
        add_card.setAttribute(Qt.WA_StyledBackground, True)
        add_card.setStyleSheet(card_qss)
        add_card.setFixedSize(214, 184)
        add_card.setCursor(Qt.PointingHandCursor)
        add_layout = QVBoxLayout(add_card)
        add_layout.setContentsMargins(16, 16, 16, 16)
        add_layout.setSpacing(10)
        add_layout.addStretch()

        plus_lbl = QLabel("+")
        plus_lbl.setAlignment(Qt.AlignCenter)
        plus_lbl.setFixedSize(56, 56)
        plus_lbl.setStyleSheet("""
            background-color: #161622;
            border: 1px dashed #8B5CF6;
            border-radius: 28px;
            color: #D8B4FE;
            font-size: 24px;
            font-weight: 600;
        """)
        add_layout.addWidget(plus_lbl, alignment=Qt.AlignCenter)

        txt_lbl = QLabel("New Profile")
        txt_lbl.setAlignment(Qt.AlignCenter)
        txt_lbl.setStyleSheet("background: transparent; color: #F4F4F5; font-size: 14px; font-weight: 700;")
        add_layout.addWidget(txt_lbl)

        sub_add = QLabel("Create workspace")
        sub_add.setAlignment(Qt.AlignCenter)
        sub_add.setStyleSheet("background: transparent; color: #8E8EA0; font-size: 11px;")
        add_layout.addWidget(sub_add)

        add_layout.addStretch()
        add_card.mousePressEvent = lambda e: self.create_new_profile()
        self.grid.addWidget(add_card, add_idx // col_count, add_idx % col_count)

    def create_profile_card(self, prof_name: str, can_delete: bool) -> QFrame:
        p_dir = os.path.join(self.profiles_root, prof_name)
        vault_dir = os.path.join(p_dir, "tracks_vault")
        track_count = len([f for f in os.listdir(vault_dir) if f.endswith(".json")]) if os.path.exists(vault_dir) else 0
        locked = is_profile_locked(p_dir)

        slang_count = 0
        slang_file = os.path.join(p_dir, "custom_slang.json")
        if os.path.exists(slang_file):
            try:
                with open(slang_file, "r", encoding="utf-8") as f:
                    slang_count = len(json.load(f))
            except Exception:
                pass

        card = QFrame()
        card.setObjectName("ProfileCard")
        card.setAttribute(Qt.WA_StyledBackground, True)
        card.setStyleSheet("""
            QFrame#ProfileCard {
                background-color: #12121A;
                border: 1px solid #2E2E3F;
                border-radius: 16px;
            }
            QFrame#ProfileCard:hover {
                background-color: #1B1329;
                border: 1px solid #A855F7;
            }
        """)
        card.setFixedSize(214, 184)
        card.setCursor(Qt.PointingHandCursor)

        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(14, 10, 10, 16)
        c_layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.addStretch()
        edit_btn = QPushButton("⚙")
        edit_btn.setFixedSize(26, 26)
        edit_btn.setToolTip("Profile Settings (Rename, PIN Lock, Backup)")
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 13px;
                color: #8E8EA0;
                font-size: 13px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #26183B;
                border: 1px solid #7C3AED;
                color: #F3E8FF;
            }
        """)
        edit_btn.clicked.connect(lambda: self.open_profile_settings(prof_name, can_delete))
        top_row.addWidget(edit_btn)
        c_layout.addLayout(top_row)

        initials = "".join([part[0].upper() for part in prof_name.replace("_", " ").split()[:2]]) or "NX"
        avatar = QLabel("🔒" if locked else initials)
        avatar.setTextFormat(Qt.PlainText)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setFixedSize(56, 56)
        avatar.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7E22CE, stop:1 #3B0764);
            border: 2px solid #C084FC;
            border-radius: 28px;
            color: #FFFFFF;
            font-size: 20px;
            font-weight: 800;
        """)
        c_layout.addWidget(avatar, alignment=Qt.AlignCenter)

        c_layout.addSpacing(2)

        display_name = prof_name.replace("_", " ")
        name_lbl = QLabel(display_name)
        name_lbl.setTextFormat(Qt.PlainText)
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setStyleSheet("background: transparent; color: #FFFFFF; font-size: 15px; font-weight: 700;")
        c_layout.addWidget(name_lbl)

        meta_lbl = QLabel(f"{track_count} Tracks  •  {slang_count} Slang")
        meta_lbl.setTextFormat(Qt.PlainText)
        meta_lbl.setAlignment(Qt.AlignCenter)
        meta_lbl.setStyleSheet("""
            background-color: #191924;
            border: 1px solid #2A2A3B;
            border-radius: 10px;
            color: #C4B5FD;
            font-size: 11px;
            font-weight: 600;
            padding: 3px 10px;
        """)
        c_layout.addWidget(meta_lbl, alignment=Qt.AlignCenter)
        c_layout.addStretch()

        card.mousePressEvent = lambda e, name=prof_name: self.choose_profile(name)
        return card

    def verify_access_if_locked(self, prof_name: str) -> bool:
        p_dir = os.path.join(self.profiles_root, prof_name)
        meta = get_profile_meta(p_dir)
        pin_h = meta.get("pin_hash")
        if not pin_h:
            return True
        dlg = PinPromptDialog(self, prof_name, pin_h)
        return dlg.exec() == QDialog.Accepted

    def open_profile_settings(self, prof_name: str, can_delete: bool):
        if not self.verify_access_if_locked(prof_name):
            return
        dlg = ProfileSettingsDialog(self, self.profiles_root, prof_name, can_delete=can_delete)
        dlg.exec()
        self.refresh_cards()

    def choose_profile(self, prof_name: str):
        if not self.verify_access_if_locked(prof_name):
            return
        self.selected_profile = prof_name
        self.accept()

    def create_new_profile(self):
        name, ok = QInputDialog.getText(
            self, "New Studio Profile", "Enter artist or profile name:"
        )
        if ok and name.strip():
            safe = "".join(c for c in name.strip() if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
            if not safe:
                return
            p_dir = os.path.join(self.profiles_root, safe)
            os.makedirs(os.path.join(p_dir, "tracks_vault"), exist_ok=True)
            self.refresh_cards()

    def restore_profile_from_zip(self):
        zip_path, _ = QFileDialog.getOpenFileName(
            self, "Select Profile Backup (.ZIP)", "", "ZIP Archive (*.zip)"
        )
        if not zip_path:
            return
        base_guess = os.path.splitext(os.path.basename(zip_path))[0].replace("NOCTURNE_Backup_", "")
        name, ok = QInputDialog.getText(
            self, "Restore Profile", "Enter profile name for restored backup:", text=base_guess[:24]
        )
        if not ok or not name.strip():
            return
        safe = "".join(c for c in name.strip() if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
        if not safe:
            return
        target_dir = os.path.join(self.profiles_root, safe)
        os.makedirs(target_dir, exist_ok=True)
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(target_dir)
            os.makedirs(os.path.join(target_dir, "tracks_vault"), exist_ok=True)
            self.refresh_cards()
            QMessageBox.information(self, "Restored", f"Profile '{safe}' restored successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Restore Failed", str(e))


# =====================================================================
# CUSTOM SLANG & ONLINE LANGUAGE ADD-ON LIBRARY DIALOG
# =====================================================================
class LexiconManagerDialog(QDialog):
    def __init__(self, parent, on_updated_callback):
        super().__init__(parent)
        self.on_updated = on_updated_callback
        self.dl_worker = None
        self.search_worker = None
        self.gh_repos = []
        self.gh_files = []

        self.setWindowTitle("NOCTURNE // Slang & Language Add-on Libraries")
        self.setWindowIcon(get_nocturne_app_icon())
        self.resize(750, 590)
        self.build_ui()
        self.refresh_lists()

    def build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        tabs = QTabWidget()

        # --- TAB 1: BROWSE & SEARCH ONLINE ---
        online_tab = QWidget()
        o_layout = QVBoxLayout(online_tab)
        o_layout.setSpacing(10)

        o_layout.addWidget(QLabel("1 - CLICK CURATED ONLINE LANGUAGE & SLANG PACKS (BETA)", objectName="SectionHeader"))
        cat_filter_row = QHBoxLayout()
        self.catalog_filter_input = QLineEdit()
        self.catalog_filter_input.setPlaceholderText("Filter built-in online catalog (e.g. Indonesian, Spanish, Tagalog, Slang)...")
        self.catalog_filter_input.textChanged.connect(self.filter_curated_catalog)
        btn_dl_curated = QPushButton("⬇ Download Selected Pack")
        btn_dl_curated.setObjectName("PrimaryBtn")
        btn_dl_curated.clicked.connect(self.download_selected_curated)
        cat_filter_row.addWidget(self.catalog_filter_input)
        cat_filter_row.addWidget(btn_dl_curated)
        o_layout.addLayout(cat_filter_row)

        self.curated_list = QListWidget()
        self.curated_list.setMaximumHeight(145)
        self.curated_list.itemDoubleClicked.connect(self.download_selected_curated)
        o_layout.addWidget(self.curated_list)

        o_layout.addWidget(QLabel("LIVE WEB SEARCH (GITHUB WORDLISTS & SLANG REPOS)", objectName="SectionHeader"))
        gh_search_row = QHBoxLayout()
        self.gh_query_input = QLineEdit()
        self.gh_query_input.setPlaceholderText("Search any language or slang online (e.g. malay, javanese, korean romaji, hip hop)...")
        self.gh_query_input.returnPressed.connect(self.run_github_repo_search)
        btn_gh_search = QPushButton("🔍 Search Online")
        btn_gh_search.setObjectName("PrimaryBtn")
        btn_gh_search.clicked.connect(self.run_github_repo_search)
        gh_search_row.addWidget(self.gh_query_input)
        gh_search_row.addWidget(btn_gh_search)
        o_layout.addLayout(gh_search_row)

        gh_split = QHBoxLayout()
        self.gh_repo_list = QListWidget()
        self.gh_repo_list.itemClicked.connect(self.on_github_repo_clicked)
        gh_split.addWidget(self.gh_repo_list, 1)

        self.gh_file_list = QListWidget()
        self.gh_file_list.itemDoubleClicked.connect(self.download_selected_github_file)
        gh_split.addWidget(self.gh_file_list, 1)
        o_layout.addLayout(gh_split)

        gh_action_row = QHBoxLayout()
        self.online_status_lbl = QLabel("Ready — Select a pack or search online (saved offline after download)")
        self.online_status_lbl.setTextFormat(Qt.PlainText)
        self.online_status_lbl.setStyleSheet("color: #B4B4BE; font-size: 11px;")
        btn_dl_gh_file = QPushButton("⬇ Import Selected Repo File")
        btn_dl_gh_file.clicked.connect(self.download_selected_github_file)
        gh_action_row.addWidget(self.online_status_lbl)
        gh_action_row.addStretch()
        gh_action_row.addWidget(btn_dl_gh_file)
        o_layout.addLayout(gh_action_row)

        self.online_progress = QProgressBar()
        self.online_progress.setRange(0, 0)
        self.online_progress.setVisible(False)
        o_layout.addWidget(self.online_progress)

        self.filter_curated_catalog("")
        tabs.addTab(online_tab, "🌐 Browse & Search Online")

        # --- TAB 2: CUSTOM SLANG ---
        slang_tab = QWidget()
        s_layout = QVBoxLayout(slang_tab)
        s_layout.setSpacing(10)

        s_layout.addWidget(QLabel("ADD CUSTOM SLANG / WORDPLAY", objectName="SectionHeader"))
        form_row = QHBoxLayout()
        self.slang_word_input = QLineEdit()
        self.slang_word_input.setPlaceholderText("Slang word (e.g. kacip, on lock, tapau)")
        self.slang_tag_input = QLineEdit("CUSTOM SLANG")
        self.slang_tag_input.setFixedWidth(145)
        form_row.addWidget(self.slang_word_input)
        form_row.addWidget(self.slang_tag_input)
        s_layout.addLayout(form_row)

        meaning_row = QHBoxLayout()
        self.slang_meaning_input = QLineEdit()
        self.slang_meaning_input.setPlaceholderText("Meaning / Double entendre note (appears on hover)...")
        btn_add_slang = QPushButton("+ Add Slang")
        btn_add_slang.setObjectName("PrimaryBtn")
        btn_add_slang.clicked.connect(self.add_slang)
        meaning_row.addWidget(self.slang_meaning_input)
        meaning_row.addWidget(btn_add_slang)
        s_layout.addLayout(meaning_row)

        s_layout.addWidget(QLabel("SAVED CUSTOM SLANG IN THIS PROFILE", objectName="SectionHeader"))
        self.slang_list = QListWidget()
        s_layout.addWidget(self.slang_list)

        btn_del_slang = QPushButton("Delete Selected Slang")
        btn_del_slang.clicked.connect(self.delete_selected_slang)
        s_layout.addWidget(btn_del_slang, alignment=Qt.AlignRight)

        tabs.addTab(slang_tab, "Custom Slang")

        # --- TAB 3: INSTALLED & LOCAL IMPORT ---
        pack_tab = QWidget()
        p_layout = QVBoxLayout(pack_tab)
        p_layout.setSpacing(10)

        p_layout.addWidget(QLabel("IMPORT LOCAL FILE OR PASTE VOCABULARY", objectName="SectionHeader"))
        pack_top = QHBoxLayout()
        self.pack_name_input = QLineEdit()
        self.pack_name_input.setPlaceholderText("Language Pack Name (e.g. Perak Slang, Japanese Romaji)")
        btn_import_file = QPushButton("📂 Import Local .TXT / .JSON")
        btn_import_file.setObjectName("PrimaryBtn")
        btn_import_file.clicked.connect(self.import_pack_file)
        pack_top.addWidget(self.pack_name_input)
        pack_top.addWidget(btn_import_file)
        p_layout.addLayout(pack_top)

        self.bulk_words_input = QPlainTextEdit()
        self.bulk_words_input.setMaximumHeight(82)
        self.bulk_words_input.setPlaceholderText(
            "Or paste/type custom vocabulary words here (separated by spaces, commas, or new lines)..."
        )
        self.bulk_words_input.setStyleSheet("background-color: #101015; border: 1px solid #323240; border-radius: 6px; padding: 6px; color: #FFFFFF;")
        p_layout.addWidget(self.bulk_words_input)

        btn_add_bulk = QPushButton("+ Add Pasted Words to Language Pack")
        btn_add_bulk.clicked.connect(self.add_bulk_words)
        p_layout.addWidget(btn_add_bulk, alignment=Qt.AlignRight)

        p_layout.addWidget(QLabel("INSTALLED OFFLINE PACKS IN THIS PROFILE", objectName="SectionHeader"))
        self.packs_list = QListWidget()
        p_layout.addWidget(self.packs_list)

        pack_actions = QHBoxLayout()
        btn_toggle_pack = QPushButton("Enable / Disable Selected Pack")
        btn_toggle_pack.clicked.connect(self.toggle_selected_pack)
        btn_del_pack = QPushButton("Delete Selected Pack")
        btn_del_pack.clicked.connect(self.delete_selected_pack)
        pack_actions.addWidget(btn_toggle_pack)
        pack_actions.addStretch()
        pack_actions.addWidget(btn_del_pack)
        p_layout.addLayout(pack_actions)

        tabs.addTab(pack_tab, "Installed & Local Packs")
        layout.addWidget(tabs)

    def filter_curated_catalog(self, query: str):
        q = query.strip().lower()
        self.curated_list.clear()
        for entry in ONLINE_CURATED_CATALOG:
            if not q or q in entry["name"].lower() or q in entry["desc"].lower() or q in entry["category"].lower():
                item = QListWidgetItem(f"[{entry['category']}]  {entry['name']}  —  {entry['desc']}")
                item.setData(Qt.UserRole, entry)
                self.curated_list.addItem(item)

    def start_background_download(self, pack_name: str, url: str, is_json: bool = False):
        if self.dl_worker and self.dl_worker.isRunning():
            return
        self.online_progress.setVisible(True)
        self.online_status_lbl.setText(f"Downloading '{pack_name}' from internet...")
        self.dl_worker = OnlineDownloadWorker(pack_name, url, is_json=is_json)
        self.dl_worker.finished_ok.connect(self.on_download_finished)
        self.dl_worker.failed.connect(self.on_download_failed)
        self.dl_worker.start()

    def on_download_finished(self, pack_name: str, total_words: int):
        self.online_progress.setVisible(False)
        self.online_status_lbl.setText(f"✅ Installed '{pack_name}' ({total_words:,} words) — Ready offline!")
        self.refresh_lists()
        self.on_updated()
        QMessageBox.information(
            self, "Download Complete",
            f"Successfully installed '{pack_name}' ({total_words:,} words).\nIt is now saved offline in your profile!"
        )

    def on_download_failed(self, err_msg: str):
        self.online_progress.setVisible(False)
        self.online_status_lbl.setText("❌ Download failed. Check internet connection or try another source.")
        QMessageBox.warning(self, "Online Fetch Error", f"Could not download pack:\n{err_msg}")

    def download_selected_curated(self):
        item = self.curated_list.currentItem()
        if not item:
            QMessageBox.information(self, "Select Pack", "Select a language or slang pack from the list first.")
            return
        entry = item.data(Qt.UserRole)
        is_json = entry["url"].lower().endswith(".json")
        self.start_background_download(entry["name"], entry["url"], is_json=is_json)

    def run_github_repo_search(self):
        q = self.gh_query_input.text().strip()
        if not q:
            return
        self.online_progress.setVisible(True)
        self.online_status_lbl.setText(f"Searching GitHub repositories for '{q}'...")
        self.gh_repo_list.clear()
        self.gh_file_list.clear()

        self.search_worker = GitHubSearchWorker("repos", q)
        self.search_worker.repos_ready.connect(self.on_github_repos_loaded)
        self.search_worker.failed.connect(self.on_download_failed)
        self.search_worker.start()

    def on_github_repos_loaded(self, repos: list):
        self.online_progress.setVisible(False)
        self.gh_repos = repos
        if not repos:
            self.online_status_lbl.setText("No repositories found. Try a broader keyword (e.g. 'spanish words').")
            return
        self.online_status_lbl.setText(f"Found {len(repos)} repositories — Click a repo on the left to view files.")
        for r in repos:
            item = QListWidgetItem(f"★ {r['stars']}  {r['full_name']} — {r['description'][:55]}")
            item.setData(Qt.UserRole, r)
            self.gh_repo_list.addItem(item)

    def on_github_repo_clicked(self, item: QListWidgetItem):
        repo = item.data(Qt.UserRole)
        self.online_progress.setVisible(True)
        self.online_status_lbl.setText(f"Listing wordlist files in {repo['full_name']}...")
        self.gh_file_list.clear()

        self.search_worker = GitHubSearchWorker("files", repo["full_name"], repo["branch"])
        self.search_worker.files_ready.connect(lambda files: self.on_github_files_loaded(repo["full_name"], files))
        self.search_worker.failed.connect(self.on_download_failed)
        self.search_worker.start()

    def on_github_files_loaded(self, repo_name: str, files: list):
        self.online_progress.setVisible(False)
        if not files:
            self.online_status_lbl.setText(f"No .txt/.json wordlists found in {repo_name}.")
            return
        self.online_status_lbl.setText("Double-click any file on the right to download & install.")
        for f in files:
            item = QListWidgetItem(f"📄 {f['path']}  ({f['size_kb']} KB)")
            item.setData(Qt.UserRole, (repo_name, f))
            self.gh_file_list.addItem(item)

    def download_selected_github_file(self):
        item = self.gh_file_list.currentItem()
        if not item:
            return
        repo_name, f_info = item.data(Qt.UserRole)
        clean_pack_name = f"{repo_name.split('/')[-1]}_{os.path.splitext(os.path.basename(f_info['path']))[0]}"
        self.start_background_download(clean_pack_name, f_info["raw_url"], is_json=f_info["is_json"])

    def refresh_lists(self):
        self.slang_list.clear()
        for w, info in sorted(LEXICON.custom_slang.items()):
            self.slang_list.addItem(f"{w}  [{info.get('tag', 'SLANG')}]  —  {info.get('meaning', '')}")

        self.packs_list.clear()
        for pname, pdata in sorted(LEXICON.language_packs.items()):
            status = "ACTIVE" if pdata.get("enabled", True) else "DISABLED"
            count = len(pdata.get("words", []))
            item = QListWidgetItem(f"[{status}]  {pname}  ({count:,} words)")
            item.setData(Qt.UserRole, pname)
            self.packs_list.addItem(item)

    def add_slang(self):
        w = self.slang_word_input.text().strip()
        m = self.slang_meaning_input.text().strip()
        t = self.slang_tag_input.text().strip()
        if not w or not m:
            QMessageBox.warning(self, "Missing Info", "Enter both the slang word and its meaning.")
            return
        LEXICON.add_custom_slang(w, m, t)
        self.slang_word_input.clear()
        self.slang_meaning_input.clear()
        self.refresh_lists()
        self.on_updated()

    def delete_selected_slang(self):
        item = self.slang_list.currentItem()
        if not item:
            return
        word = item.text().split("  [")[0].strip()
        LEXICON.remove_custom_slang(word)
        self.refresh_lists()
        self.on_updated()

    def import_pack_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Word List", "", "Text or JSON Files (*.txt *.json)"
        )
        if not path:
            return
        pname = self.pack_name_input.text().strip() or os.path.splitext(os.path.basename(path))[0]
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            raw = f.read()
        words = parse_wordlist_content(raw, is_json=path.lower().endswith(".json"))
        total = LEXICON.add_language_pack(pname, words)
        self.refresh_lists()
        self.on_updated()
        QMessageBox.information(self, "Pack Imported", f"Loaded '{pname}' ({total:,} words) into offline engine.")

    def add_bulk_words(self):
        pname = self.pack_name_input.text().strip() or "Custom_Vocab"
        raw = self.bulk_words_input.toPlainText()
        words = re.findall(r"[a-zA-Z0-9'-]+", raw)
        if not words:
            return
        total = LEXICON.add_language_pack(pname, words)
        self.bulk_words_input.clear()
        self.refresh_lists()
        self.on_updated()
        QMessageBox.information(self, "Words Added", f"Updated '{pname}' ({total:,} total words).")

    def toggle_selected_pack(self):
        item = self.packs_list.currentItem()
        if not item:
            return
        pname = item.data(Qt.UserRole)
        curr = LEXICON.language_packs.get(pname, {}).get("enabled", True)
        LEXICON.toggle_language_pack(pname, not curr)
        self.refresh_lists()
        self.on_updated()

    def delete_selected_pack(self):
        item = self.packs_list.currentItem()
        if not item:
            return
        pname = item.data(Qt.UserRole)
        LEXICON.delete_language_pack(pname)
        self.refresh_lists()
        self.on_updated()

    def closeEvent(self, event):
        for worker in (self.dl_worker, self.search_worker):
            if worker is not None and worker.isRunning():
                worker.quit()
                if not worker.wait(1200):
                    worker.terminate()
                    worker.wait(400)
        super().closeEvent(event)


# =====================================================================
# LYRIC EDITOR (DEFAULT SF PRO + IN-EDITOR SEARCH HIGHLIGHTS)
# =====================================================================
class RhymeDot(QPushButton):
    """Interactive 9px rhyme scheme dot: Left-click to Solo/Isolate, Right-click to Jump."""
    solo_toggled = Signal(int)
    jump_requested = Signal(int)

    def __init__(self, group_idx: int, vivid_hex: str, parent=None):
        super().__init__(parent)
        self.group_idx = group_idx
        self.vivid_hex = vivid_hex
        self.is_solo = False
        self.active_count = 0

        self.setFixedSize(9, 9)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(lambda: self.solo_toggled.emit(self.group_idx))
        self._refresh_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.jump_requested.emit(self.group_idx)
            return
        super().mousePressEvent(event)

    def update_state(self, word_count: int, multie_count: int, sample_words: list[str], is_solo: bool):
        self.active_count = word_count
        self.is_solo = is_solo

        if word_count == 0:
            self.setToolTip(f"Rhyme Group {self.group_idx + 1} · Inactive")
        else:
            samples = ", ".join(dict.fromkeys(sample_words))[:42]
            self.setToolTip(
                f"Group {self.group_idx + 1}: {word_count} words · {multie_count} multies\n"
                f"Words: {samples}\n"
                f"• Left-click: Solo / Isolate scheme\n"
                f"• Right-click: Jump to next word"
            )
        self._refresh_style()

    def _refresh_style(self):
        if self.is_solo:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.vivid_hex};
                    border: 2px solid #FFFFFF;
                    border-radius: 4px;
                    padding: 0px;
                }}
            """)
        elif self.active_count > 0:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.vivid_hex};
                    border: none;
                    border-radius: 4px;
                    padding: 0px;
                }}
                QPushButton:hover {{
                    border: 1px solid #FFFFFF;
                }}
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #272732;
                    border: 1px solid #3F3F4E;
                    border-radius: 4px;
                    padding: 0px;
                }
            """)
            

        
class SyllableGutter(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_gutter(event)


class LyricEditor(QPlainTextEdit):
    def __init__(
        self,
        on_word_selected_callback,
        on_analysis_updated_callback,
        on_quick_add_slang_callback,
        on_cursor_word_changed_callback=None,
        on_timestamp_clicked_callback=None,
        on_set_pronunciation_callback=None,
    ):
        super().__init__()
        self.on_set_pronunciation = on_set_pronunciation_callback
        self.on_word_selected = on_word_selected_callback
        self.on_analysis_updated = on_analysis_updated_callback
        self.on_quick_add_slang = on_quick_add_slang_callback
        self.on_cursor_word_changed = on_cursor_word_changed_callback
        self.on_timestamp_clicked = on_timestamp_clicked_callback
        self.line_syllables = {}
        self.token_map = []
        self.search_spans = []
        self.solo_rhyme_group = None
        self.solo_special_mode = None  # None | "multies" | "wordplay"
        self.last_detected_word = ""
        self.cfg = dict(DEFAULT_STUDIO_SETTINGS)
        self.setMouseTracking(True)

        # Hold right-click on a coloured rhyme = temporary solo of that colour
        self._hold_group = None
        self._hold_active = False
        self._hold_saved = (None, None)
        self._suppress_menu = False
        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.setInterval(200)
        self._hold_timer.timeout.connect(self._begin_hold_solo)

        self.gutter = SyllableGutter(self)
        self.blockCountChanged.connect(self.update_gutter_width)
        self.updateRequest.connect(self.update_gutter)
        self.cursorPositionChanged.connect(self.on_cursor_moved)
        self.textChanged.connect(self.schedule_analysis)

        self.analysis_timer = QTimer(self)
        self.analysis_timer.setSingleShot(True)
        self.analysis_timer.setInterval(200)
        self.analysis_timer.timeout.connect(self.run_analysis)

        self.cursor_word_timer = QTimer(self)
        self.cursor_word_timer.setSingleShot(True)
        self.cursor_word_timer.setInterval(150)
        self.cursor_word_timer.timeout.connect(self._emit_cursor_word)

        self.apply_settings(self.cfg)
        self.highlight_current_line()

    def apply_settings(self, cfg: dict):
        self.cfg = dict(cfg)
        font_family = self.cfg.get("font_family", "SF Pro")
        size = max(11, int(self.cfg.get("font_size", 15) or 15))
        bold = self.cfg.get("font_bold", True)
        word_wrap = self.cfg.get("word_wrap", True)

        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #09090B;
                color: #F4F4F5;
                border: none;
                padding-left: 14px;
                selection-background-color: #6B21A8;
            }
        """)

        font = safe_qfont(font_family, size, bold=bold)
        self.setFont(font)
        self.document().setDefaultFont(font)
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth if word_wrap else QPlainTextEdit.NoWrap)

        self.analysis_timer.setInterval(self.cfg.get("debounce_ms", 200))
        self.gutter.setVisible(self.cfg.get("show_gutter", True))
        self.update_gutter_width(0)
        self.run_analysis()

    def set_editor_font_size(self, size: int):
        self.cfg["font_size"] = max(11, int(size))
        self.apply_settings(self.cfg)

    def set_search_spans(self, spans: list[tuple[int, int]]):
        self.search_spans = spans
        self.apply_visual_highlights()

    def jump_to_line(self, line_index: int):
        block = self.document().findBlockByNumber(line_index)
        if block.isValid():
            cur = QTextCursor(block)
            cur.select(QTextCursor.LineUnderCursor)
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            self.setFocus()

    def gutter_width(self):
        if not self.cfg.get("show_gutter", True):
            return 0
        size = max(11, int(self.cfg.get("font_size", 15) or 15))
        return max(56, int(size * 3.4))

    def update_gutter_width(self, _):
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def update_gutter(self, rect, dy):
        if dy:
            self.gutter.scroll(0, dy)
        else:
            self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_gutter_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.gutter.setGeometry(QRect(cr.left(), cr.top(), self.gutter_width(), cr.height()))

    def paint_gutter(self, event):
        if not self.cfg.get("show_gutter", True):
            return
        painter = QPainter(self.gutter)
        painter.fillRect(event.rect(), QColor("#09090B"))

        painter.setPen(QColor("#23232E"))
        painter.drawLine(self.gutter.width() - 1, event.rect().top(), self.gutter.width() - 1, event.rect().bottom())

        block = self.firstVisibleBlock()
        block_num = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        block_h = round(self.blockBoundingRect(block).height())
        bottom = top + block_h

        size = max(11, int(self.cfg.get("font_size", 15) or 15))
        gutter_font = safe_qfont("Consolas", max(10, int(size * 0.72)), bold=True)
        painter.setFont(gutter_font)

        warn_thresh = self.cfg.get("flow_warn_threshold", 6)
        line_h = max(1, self.fontMetrics().height())

        prev_syl = None
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                info = self.line_syllables.get(block_num)
                if info and not info["is_header"] and info["syllables"] > 0:
                    syl = info["syllables"]
                    if prev_syl and abs(syl - prev_syl) >= warn_thresh:
                        painter.setPen(QColor("#FBBF24"))
                    else:
                        painter.setPen(QColor("#C084FC"))
                    painter.drawText(
                        0, top, self.gutter.width() - 10,
                        line_h,
                        Qt.AlignRight | Qt.AlignVCenter,
                        f"{syl:02d}"
                    )
                    prev_syl = syl
                else:
                    painter.setPen(QColor("#52525B"))
                    painter.drawText(
                        0, top, self.gutter.width() - 10,
                        line_h,
                        Qt.AlignRight | Qt.AlignVCenter,
                        "·"
                    )

            block = block.next()
            top = bottom
            block_h = round(self.blockBoundingRect(block).height())
            bottom = top + block_h
            block_num += 1

    def on_cursor_moved(self):
        self.highlight_current_line()
        self.cursor_word_timer.start()

    def _extract_word_at_cursor(self) -> str:
        cur = self.textCursor()
        block = cur.block()
        line_txt = block.text()
        stripped = line_txt.strip()
        if not stripped or (stripped.startswith("[") and stripped.endswith("]")):
            return ""

        pos_in_block = cur.positionInBlock()
        if pos_in_block > 0 and (pos_in_block >= len(line_txt) or not re.match(r"[A-Za-z0-9'-]", line_txt[pos_in_block])):
            probe = pos_in_block - 1
            while probe > 0 and line_txt[probe].isspace():
                probe -= 1
            check_cur = QTextCursor(block)
            check_cur.setPosition(block.position() + probe)
            check_cur.select(QTextCursor.WordUnderCursor)
            word = check_cur.selectedText().strip()
        else:
            cur.select(QTextCursor.WordUnderCursor)
            word = cur.selectedText().strip()

        clean = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", word)
        return clean if len(clean) >= 2 else ""

    def _emit_cursor_word(self):
        if not self.on_cursor_word_changed:
            return
        word = self._extract_word_at_cursor()
        if word:
            self.last_detected_word = word.lower()
            self.on_cursor_word_changed(word)

    def highlight_current_line(self):
        self.apply_visual_highlights()

    def schedule_analysis(self):
        self.analysis_timer.start()

    def run_analysis(self):
        text = self.toPlainText()
        result = analyze_lyrics(
            text,
            rhyme_window=self.cfg.get("rhyme_window", 4),
            granularity=self.cfg.get("rhyme_granularity", "syllable"),
        )
        self.line_syllables = {item["line"]: item for item in result["lines"]}
        self.token_map = result["tokens"]
        self.apply_visual_highlights()
        self.gutter.update()
        self.on_analysis_updated(result)
        self.cursor_word_timer.start()

    def apply_visual_highlights(self):
        selections = []
        doc = self.document()

        # 0. Jika mod Solo aktif, malapkan semua teks dasar secara seragam dahulu
        is_solo_active = (self.solo_special_mode is not None) or (self.solo_rhyme_group is not None)
        if is_solo_active and doc.characterCount() > 1:
            dim_all_sel = QTextEdit.ExtraSelection()
            dim_cur = QTextCursor(doc)
            dim_cur.select(QTextCursor.Document)
            dim_all_sel.cursor = dim_cur
            dim_all_sel.format.setForeground(QColor("#525260"))
            selections.append(dim_all_sel)

        # 1. Highlight baris semasa
        line_sel = QTextEdit.ExtraSelection()
        line_sel.format.setBackground(QColor("#121218"))
        if is_solo_active:
            line_sel.format.setForeground(QColor("#525260"))
        line_sel.format.setProperty(QTextFormat.FullWidthSelection, True)
        line_sel.cursor = self.textCursor()
        line_sel.cursor.clearSelection()
        selections.append(line_sel)

        block = doc.firstBlock()
        while block.isValid():
            raw_line = block.text()
            txt = raw_line.strip()
            if txt.startswith("[") and txt.endswith("]") and not re.match(r"^\[\d{1,2}:\d{2}\]$", txt):
                hdr_sel = QTextEdit.ExtraSelection()
                hdr_sel.format.setForeground(QColor("#D8B4FE"))
                hdr_sel.format.setFontWeight(QFont.Bold)
                cur = QTextCursor(block)
                cur.select(QTextCursor.BlockUnderCursor)
                hdr_sel.cursor = cur
                selections.append(hdr_sel)

            for ts_m in re.finditer(r"\[\d{1,2}:\d{2}\]", raw_line):
                ts_sel = QTextEdit.ExtraSelection()
                ts_sel.format.setBackground(QColor("#0E2433"))
                ts_sel.format.setForeground(QColor("#67E8F9"))
                ts_sel.format.setFontWeight(QFont.Bold)
                cur = QTextCursor(block)
                cur.setPosition(block.position() + ts_m.start())
                cur.setPosition(block.position() + ts_m.end(), QTextCursor.KeepAnchor)
                ts_sel.cursor = cur
                selections.append(ts_sel)
            block = block.next()

        hl_rhymes = self.cfg.get("highlight_rhymes", True)

        doc_len = max(0, doc.characterCount() - 1)
        if self.cfg.get("highlight_near_rhymes", True) and not is_solo_active:
            for tok in self.token_map:
                if tok.get("near_rhyme") and tok["rhyme_group"] is None and tok["end"] <= doc_len:
                    near_sel = QTextEdit.ExtraSelection()
                    near_cur = QTextCursor(doc)
                    near_cur.setPosition(tok["start"])
                    near_cur.setPosition(tok["end"], QTextCursor.KeepAnchor)
                    near_sel.cursor = near_cur
                    near_fmt = QTextCharFormat()
                    near_fmt.setUnderlineStyle(QTextCharFormat.DotLine)
                    near_fmt.setUnderlineColor(QColor("#FBBF24"))
                    near_sel.format = near_fmt
                    selections.append(near_sel)
        syllable_mode = self.cfg.get("rhyme_granularity", "syllable") == "syllable"

        for tok in self.token_map:
            if tok["end"] > doc_len:
                continue  # analysis is slightly stale relative to the text being typed
            has_rhyme = hl_rhymes and (tok["rhyme_group"] is not None)
            if not has_rhyme:
                continue

            span_s, span_e = tok["start"], tok["end"]
            if has_rhyme and syllable_mode:
                span_s = max(tok["start"], min(tok.get("rhyme_start", tok["start"]), tok["end"]))
                span_e = min(tok["end"], max(tok.get("rhyme_end", tok["end"]), span_s))

            sel = QTextEdit.ExtraSelection()
            cur = QTextCursor(doc)
            cur.setPosition(span_s)
            cur.setPosition(span_e, QTextCursor.KeepAnchor)
            sel.cursor = cur

            fmt = QTextCharFormat()
            if self.solo_rhyme_group is not None:
                if has_rhyme and tok["color_idx"] == self.solo_rhyme_group:
                    bg_hex, fg_hex = RHYME_PALETTE[self.solo_rhyme_group]
                    fmt.setBackground(QColor(bg_hex))
                    fmt.setForeground(QColor(fg_hex))
                else:
                    fmt.setForeground(QColor("#525260"))
            elif has_rhyme:
                bg_hex, fg_hex = RHYME_PALETTE[tok["color_idx"]]
                fmt.setBackground(QColor(bg_hex))
                fmt.setForeground(QColor(fg_hex))
                    
            sel.format = fmt
            selections.append(sel)

        for s_start, s_end in self.search_spans:
            sel = QTextEdit.ExtraSelection()
            cur = QTextCursor(doc)
            cur.setPosition(s_start)
            cur.setPosition(s_end, QTextCursor.KeepAnchor)
            sel.cursor = cur

            fmt = QTextCharFormat()
            fmt.setBackground(QColor("#D97706"))
            fmt.setForeground(QColor("#FFFFFF"))
            fmt.setFontWeight(QFont.Bold)
            sel.format = fmt
            selections.append(sel)

        self.setExtraSelections(selections)

    # --- Hold right-click on a rhyme colour: quick temporary solo --------------------
    def _rhyme_token_at(self, pt):
        if not self.cfg.get("highlight_rhymes", True):
            return None
        pos = self.cursorForPosition(pt).position()
        loose = None
        for tok in self.token_map:
            if tok["rhyme_group"] is None:
                continue
            if tok["start"] <= pos < tok["end"]:
                return tok
            if pos == tok["end"] and loose is None:
                loose = tok
        return loose

    def _begin_hold_solo(self):
        if self._hold_group is None or self._hold_active:
            return
        self._hold_saved = (self.solo_rhyme_group, self.solo_special_mode)
        self.solo_rhyme_group = self._hold_group
        self.solo_special_mode = None
        self._hold_active = True
        self._suppress_menu = True  # the release must not pop the context menu
        self.apply_visual_highlights()

    def _end_hold_solo(self):
        self._hold_timer.stop()
        self._hold_group = None
        if self._hold_active:
            self.solo_rhyme_group, self.solo_special_mode = self._hold_saved
            self._hold_active = False
            self.apply_visual_highlights()
            QTimer.singleShot(250, self._clear_menu_suppress)

    def _clear_menu_suppress(self):
        self._suppress_menu = False

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            tok = self._rhyme_token_at(event.position().toPoint())
            if tok is not None:
                self._hold_group = tok["color_idx"]
                self._hold_timer.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton:
            was_holding = self._hold_active
            self._end_hold_solo()
            if was_holding:
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        if self._suppress_menu or self._hold_active:
            event.accept()
            return
        menu = self.createStandardContextMenu()
        cursor = self.textCursor()
        selected = cursor.selectedText().replace("\u2029", " ").strip()
        # If multiple words or a whole verse/song is selected, target the single word under the mouse instead
        if not selected or len(selected) > 32 or len(selected.split()) > 2:
            word_cursor = self.cursorForPosition(event.pos())
            word_cursor.select(QTextCursor.WordUnderCursor)
            selected = word_cursor.selectedText().strip()

        if selected and re.search(r"[A-Za-z0-9]", selected):
            preview = (selected[:24].rstrip() + "…") if len(selected) > 24 else selected
            menu.addSeparator()
            act_slang = QAction(f"➕ Add '{preview}' to Custom Slang...", self)
            act_slang.triggered.connect(lambda: self.on_quick_add_slang(selected))
            menu.addAction(act_slang)

            if self.on_set_pronunciation:
                act_pron = QAction(f"🗣 Set how I pronounce '{preview}'...", self)
                act_pron.triggered.connect(lambda: self.on_set_pronunciation(selected))
                menu.addAction(act_pron)

            act_rhyme = QAction(f"🔍 Inspect Rhymes for '{preview}'", self)
            act_rhyme.triggered.connect(lambda: self.on_word_selected(selected))
            menu.addAction(act_rhyme)

        menu.exec(event.globalPos())

    def mouseDoubleClickEvent(self, event):
        click_cur = self.cursorForPosition(event.position().toPoint())
        block = click_cur.block()
        pos_in_line = click_cur.positionInBlock()
        line_txt = block.text()
        for ts_m in re.finditer(r"\[(\d{1,2}):(\d{2})\]", line_txt):
            if ts_m.start() <= pos_in_line <= ts_m.end():
                mins = int(ts_m.group(1))
                secs = int(ts_m.group(2))
                target_ms = (mins * 60 + secs) * 1000
                if self.on_timestamp_clicked:
                    self.on_timestamp_clicked(target_ms)
                return

        super().mouseDoubleClickEvent(event)
        cursor = self.textCursor()
        selected = cursor.selectedText().strip()
        if selected:
            self.on_word_selected(selected)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        cursor = self.cursorForPosition(event.position().toPoint())
        pos = cursor.position()

        for tok in self.token_map:
            if tok["start"] <= pos <= tok["end"]:
                tip_parts = []
                if tok.get("multie_count", 0) >= 2:
                    tip_parts.append(f"🔥 MULTIE CHAIN ({tok.get('multie_count', 0)}x syllables) [{tok['lang']}]")
                elif tok["rhyme_group"] is not None:
                    tail = self.toPlainText()[tok["rhyme_start"]:tok["rhyme_end"]]
                    tail_note = f" • rhymes on '{tail}'" if tok.get("is_syllable_rhyme") else ""
                    tip_parts.append(f"🎵 RHYME MATCH ({tok['syllables']} syl){tail_note} [{tok['lang']}]")
                near = tok.get("near_rhyme")
                if near and tok["rhyme_group"] is None and self.cfg.get("highlight_near_rhymes", True):
                    tip_parts.append(f"≈ NEAR RHYME with '{near['partner_word']}' ({near['category']}, {near['confidence']:.0f}%)")
                if tok.get("is_repeat"):
                    tip_parts.append("🔁 Repeated end word")
                if tok.get("pron_override"):
                    tip_parts.append("🗣 Using your custom pronunciation")
                if tok.get("wordplay"):
                    tip_parts.append(tok["wordplay"])

                if tip_parts:
                    QToolTip.showText(event.globalPosition().toPoint(), "\n\n".join(tip_parts), self)
                    return
        QToolTip.hideText()


# =====================================================================
# FULL VAULT & RECYCLE BIN WINDOW
# =====================================================================
class FullVaultWindow(QDialog):
    """Dedicated full-screen/large window to browse all tracks, view Date Created, and manage Recycle Bin."""
    def __init__(
        self,
        parent,
        profile_name: str,
        vault_dir: str,
        trash_dir: str,
        on_open_track_callback,
        on_vault_changed_callback,
        start_tab: int = 0,
    ):
        super().__init__(parent)
        self.profile_name = profile_name
        self.vault_dir = vault_dir
        self.trash_dir = trash_dir
        self.on_open_track = on_open_track_callback
        self.on_vault_changed = on_vault_changed_callback

        self.setWindowTitle(f"NOCTURNE // Full Track Vault & Recycle Bin — {profile_name}")
        self.setWindowIcon(get_nocturne_app_icon())
        self.resize(900, 580)
        self.build_ui()
        self.refresh_all()
        self.tabs.setCurrentIndex(start_tab)

    def build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        top_hdr = QHBoxLayout()
        title_lbl = QLabel(f"🗄 FULL TRACK VAULT // {self.profile_name.upper()}")
        title_lbl.setTextFormat(Qt.PlainText)
        title_lbl.setStyleSheet("color: #C084FC; font-size: 14px; font-weight: 800; letter-spacing: 1px;")
        top_hdr.addWidget(title_lbl)
        top_hdr.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setFixedWidth(290)
        self.search_input.setPlaceholderText("🔍 Search title, date, or lyrics...")
        self.search_input.textChanged.connect(self.refresh_all)
        top_hdr.addWidget(self.search_input)
        layout.addLayout(top_hdr)

        self.tabs = QTabWidget()

        # --- TAB 1: ACTIVE VAULT ---
        active_tab = QWidget()
        a_lay = QVBoxLayout(active_tab)
        a_lay.setSpacing(10)

        a_split = QSplitter(Qt.Horizontal)

        self.active_list = QListWidget()
        self.active_list.currentItemChanged.connect(self.on_active_selected)
        self.active_list.itemDoubleClicked.connect(self.open_selected_active)
        a_split.addWidget(self.active_list)

        a_preview_box = QFrame()
        a_preview_box.setObjectName("PanelCard")
        ap_lay = QVBoxLayout(a_preview_box)
        ap_lay.setContentsMargins(12, 12, 12, 12)
        ap_lay.setSpacing(8)

        self.active_meta_lbl = QLabel("Select a track to inspect details & lyrics")
        self.active_meta_lbl.setTextFormat(Qt.PlainText)
        self.active_meta_lbl.setWordWrap(True)
        self.active_meta_lbl.setStyleSheet("color: #D8B4FE; font-size: 12px; font-weight: 700;")
        ap_lay.addWidget(self.active_meta_lbl)

        self.active_preview = QPlainTextEdit()
        self.active_preview.setReadOnly(True)
        self.active_preview.setStyleSheet(
            "background-color: #09090B; border: 1px solid #23232E; border-radius: 6px; "
            "color: #F4F4F5; font-size: 13px; padding: 8px;"
        )
        ap_lay.addWidget(self.active_preview)
        a_split.addWidget(a_preview_box)
        a_split.setSizes([380, 480])
        a_lay.addWidget(a_split, 1)

        a_btns = QHBoxLayout()
        btn_del_to_bin = QPushButton("🗑 Move to Recycle Bin")
        btn_del_to_bin.setObjectName("DangerBtn")
        btn_del_to_bin.clicked.connect(self.move_selected_to_bin)
        a_btns.addWidget(btn_del_to_bin)

        a_btns.addStretch()

        btn_open_editor = QPushButton("⚡ Open in Lyric Editor")
        btn_open_editor.setObjectName("PrimaryBtn")
        btn_open_editor.clicked.connect(self.open_selected_active)
        a_btns.addWidget(btn_open_editor)
        a_lay.addLayout(a_btns)

        self.tabs.addTab(active_tab, "📁 Active Tracks (0)")

        # --- TAB 2: RECYCLE BIN ---
        bin_tab = QWidget()
        b_lay = QVBoxLayout(bin_tab)
        b_lay.setSpacing(10)

        b_split = QSplitter(Qt.Horizontal)

        self.bin_list = QListWidget()
        self.bin_list.currentItemChanged.connect(self.on_bin_selected)
        b_split.addWidget(self.bin_list)

        b_preview_box = QFrame()
        b_preview_box.setObjectName("PanelCard")
        bp_lay = QVBoxLayout(b_preview_box)
        bp_lay.setContentsMargins(12, 12, 12, 12)
        bp_lay.setSpacing(8)

        self.bin_meta_lbl = QLabel("Deleted tracks are kept here until restored or permanently deleted")
        self.bin_meta_lbl.setTextFormat(Qt.PlainText)
        self.bin_meta_lbl.setWordWrap(True)
        self.bin_meta_lbl.setStyleSheet("color: #FCA5A5; font-size: 12px; font-weight: 700;")
        bp_lay.addWidget(self.bin_meta_lbl)

        self.bin_preview = QPlainTextEdit()
        self.bin_preview.setReadOnly(True)
        self.bin_preview.setStyleSheet(
            "background-color: #09090B; border: 1px solid #23232E; border-radius: 6px; "
            "color: #D4D4D8; font-size: 13px; padding: 8px;"
        )
        bp_lay.addWidget(self.bin_preview)
        b_split.addWidget(b_preview_box)
        b_split.setSizes([380, 480])
        b_lay.addWidget(b_split, 1)

        b_btns = QHBoxLayout()
        btn_perm_del = QPushButton("🔥 Delete Permanently")
        btn_perm_del.setObjectName("DangerBtn")
        btn_perm_del.clicked.connect(self.permanently_delete_selected)
        b_btns.addWidget(btn_perm_del)

        btn_empty_bin = QPushButton("Empty Recycle Bin")
        btn_empty_bin.clicked.connect(self.empty_recycle_bin)
        b_btns.addWidget(btn_empty_bin)

        b_btns.addStretch()

        btn_restore = QPushButton("♻ Restore to Vault")
        btn_restore.setObjectName("PrimaryBtn")
        btn_restore.clicked.connect(self.restore_selected_from_bin)
        b_btns.addWidget(btn_restore)
        b_lay.addLayout(b_btns)

        self.tabs.addTab(bin_tab, "🗑 Recycle Bin (0)")
        layout.addWidget(self.tabs, 1)

    def _scan_folder(self, folder: str, query: str) -> list[dict]:
        os.makedirs(folder, exist_ok=True)
        items = []
        for fname in os.listdir(folder):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(folder, fname)
            safe_name = fname[:-5]
            try:
                st = os.stat(fpath)
                ctime = st.st_ctime
                mtime = st.st_mtime
            except Exception:
                ctime = mtime = 0.0

            data = {}
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass

            title = data.get("title") or safe_name
            created_str = data.get("created_at") or (
                datetime.fromtimestamp(ctime).strftime("%d %b %Y • %I:%M %p") if ctime else "Unknown"
            )
            updated_str = data.get("updated_at") or (
                datetime.fromtimestamp(mtime).strftime("%d %b %Y • %I:%M %p") if mtime else ""
            )
            deleted_str = data.get("deleted_at", "")
            lyrics = data.get("lyrics", "")
            stash = data.get("stash", "")

            if query:
                blob = f"{safe_name} {title} {created_str} {updated_str} {lyrics} {stash}".lower()
                if query not in blob:
                    continue

            items.append({
                "safe_name": safe_name,
                "filepath": fpath,
                "title": title,
                "created_at": created_str,
                "updated_at": updated_str,
                "deleted_at": deleted_str,
                "bpm": data.get("bpm", 140),
                "lyrics": lyrics,
                "stash": stash,
                "sort_ts": mtime,
            })

        items.sort(key=lambda x: x["sort_ts"], reverse=True)
        return items

    def refresh_all(self):
        q = self.search_input.text().strip().lower()

        self.active_list.clear()
        active_entries = self._scan_folder(self.vault_dir, q)
        for entry in active_entries:
            lines_cnt = len([l for l in entry["lyrics"].splitlines() if l.strip()])
            item = QListWidgetItem(
                f"{entry['title']}  ({lines_cnt} lines • {entry['bpm']} BPM)\n"
                f"📅 Created: {entry['created_at']}"
            )
            item.setData(Qt.UserRole, entry)
            item.setSizeHint(QSize(0, 48))
            self.active_list.addItem(item)
        self.tabs.setTabText(0, f"📁 Active Tracks ({len(active_entries)})")
        if self.active_list.count() > 0:
            self.active_list.setCurrentRow(0)
        else:
            self.active_meta_lbl.setText("No tracks found in Active Vault.")
            self.active_preview.clear()

        self.bin_list.clear()
        bin_entries = self._scan_folder(self.trash_dir, q)
        for entry in bin_entries:
            del_note = f"  |  🗑 Deleted: {entry['deleted_at']}" if entry["deleted_at"] else ""
            item = QListWidgetItem(
                f"{entry['title']}\n"
                f"📅 Created: {entry['created_at']}{del_note}"
            )
            item.setData(Qt.UserRole, entry)
            item.setSizeHint(QSize(0, 48))
            self.bin_list.addItem(item)
        self.tabs.setTabText(1, f"🗑 Recycle Bin ({len(bin_entries)})")
        if self.bin_list.count() > 0:
            self.bin_list.setCurrentRow(0)
        else:
            self.bin_meta_lbl.setText("Recycle Bin is empty.")
            self.bin_preview.clear()

    def on_active_selected(self, current: QListWidgetItem, _prev):
        if not current:
            return
        entry = current.data(Qt.UserRole)
        words = len(re.findall(r"[A-Za-z0-9'-]+", entry["lyrics"]))
        self.active_meta_lbl.setText(
            f"{entry['title']}  •  {entry['bpm']} BPM  •  {words} words\n"
            f"📅 Date Created: {entry['created_at']}   |   🕒 Last Saved: {entry['updated_at']}"
        )
        preview_txt = entry["lyrics"] or "(Empty lyric sheet)"
        if entry["stash"].strip():
            preview_txt += f"\n\n--- PUNCHLINE SCRAPBOOK ---\n{entry['stash']}"
        self.active_preview.setPlainText(preview_txt)

    def on_bin_selected(self, current: QListWidgetItem, _prev):
        if not current:
            return
        entry = current.data(Qt.UserRole)
        self.bin_meta_lbl.setText(
            f"{entry['title']}  •  📅 Created: {entry['created_at']}  •  🗑 Deleted: {entry['deleted_at']}"
        )
        self.bin_preview.setPlainText(entry["lyrics"] or "(Empty lyric sheet)")

    def open_selected_active(self):
        item = self.active_list.currentItem()
        if not item:
            return
        entry = item.data(Qt.UserRole)
        self.on_open_track(entry["safe_name"])
        self.accept()

    def move_selected_to_bin(self):
        item = self.active_list.currentItem()
        if not item:
            return
        entry = item.data(Qt.UserRole)
        reply = QMessageBox.question(
            self,
            "Move to Recycle Bin",
            f"Move '{entry['title']}' to Recycle Bin?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        os.makedirs(self.trash_dir, exist_ok=True)
        try:
            with open(entry["filepath"], "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {"title": entry["title"], "lyrics": entry["lyrics"]}
        data["deleted_at"] = datetime.now().strftime("%d %b %Y • %I:%M %p")
        dst_path = os.path.join(self.trash_dir, f"{entry['safe_name']}.json")
        if os.path.exists(dst_path):
            stamp = datetime.now().strftime("%H%M%S")
            dst_path = os.path.join(self.trash_dir, f"{entry['safe_name']}_{stamp}.json")
        with open(dst_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        if os.path.exists(entry["filepath"]):
            os.remove(entry["filepath"])
        self.refresh_all()
        self.on_vault_changed()

    def restore_selected_from_bin(self):
        item = self.bin_list.currentItem()
        if not item:
            return
        entry = item.data(Qt.UserRole)
        try:
            with open(entry["filepath"], "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {"title": entry["title"], "lyrics": entry["lyrics"]}
        data.pop("deleted_at", None)
        dst_path = os.path.join(self.vault_dir, f"{entry['safe_name']}.json")
        if os.path.exists(dst_path):
            stamp = datetime.now().strftime("%H%M%S")
            dst_path = os.path.join(self.vault_dir, f"{entry['safe_name']}_restored_{stamp}.json")
        with open(dst_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        if os.path.exists(entry["filepath"]):
            os.remove(entry["filepath"])
        self.refresh_all()
        self.on_vault_changed()

    def permanently_delete_selected(self):
        item = self.bin_list.currentItem()
        if not item:
            return
        entry = item.data(Qt.UserRole)
        reply = QMessageBox.warning(
            self,
            "Permanent Delete",
            f"Permanently delete '{entry['title']}'? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes and os.path.exists(entry["filepath"]):
            os.remove(entry["filepath"])
            self.refresh_all()
            self.on_vault_changed()

    def empty_recycle_bin(self):
        if self.bin_list.count() == 0:
            return
        reply = QMessageBox.warning(
            self,
            "Empty Recycle Bin",
            f"Permanently delete all {self.bin_list.count()} track(s) in Recycle Bin?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            for fname in os.listdir(self.trash_dir):
                if fname.endswith(".json"):
                    try:
                        os.remove(os.path.join(self.trash_dir, fname))
                    except Exception:
                        pass
            self.refresh_all()
            self.on_vault_changed()


# =====================================================================
# MODAL DIM OVERLAY (50% BACKDROP WHEN ANY DIALOG OPENS)
# =====================================================================
class ModalDimOverlay(QWidget):
    """Automatically dims the main window by 50% whenever any child QDialog is visible."""
    def __init__(self, parent_window: QMainWindow):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.hide()

        self._sync_scheduled = False
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)
        parent_window.installEventFilter(self)
        parent_window.destroyed.connect(self._cleanup)

    def _cleanup(self):
        app = QApplication.instance()
        if app:
            app.removeEventFilter(self)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 128))

    def _schedule_sync(self):
        if self._sync_scheduled:
            return
        self._sync_scheduled = True
        QTimer.singleShot(10, self._sync_overlay_state)

    def _sync_overlay_state(self):
        self._sync_scheduled = False
        if not self.parent_window or not self.parent_window.isVisible():
            return

        has_dialog = any(
            isinstance(w, QDialog) and w.isVisible()
            for w in QApplication.topLevelWidgets()
        )
        if has_dialog:
            target_rect = self.parent_window.rect()
            if self.geometry() != target_rect:
                self.setGeometry(target_rect)
            if not self.isVisible():
                self.raise_()
                self.show()
        else:
            if self.isVisible():
                self.hide()

    def eventFilter(self, watched, event):
        etype = event.type()
        if watched is self.parent_window and etype == QEvent.Resize:
            if self.isVisible():
                self.setGeometry(self.parent_window.rect())
        elif isinstance(watched, QDialog) and etype in (QEvent.Show, QEvent.Hide, QEvent.Close):
            self._schedule_sync()
        return super().eventFilter(watched, event)


# =====================================================================
# MAIN STUDIO WINDOW
# =====================================================================
class ElidedLabel(QLabel):
    """QLabel yang memendekkan teks panjang (...) secara automatik tanpa melebarkan sidebar."""
    def __init__(self, text: str = "", elide_mode=Qt.ElideRight, parent=None):
        super().__init__(text, parent)
        self._full_text = text
        self._elide_mode = elide_mode
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._update_elided_text()

    def setText(self, text: str):
        self._full_text = text
        self.setToolTip(text if text else "")
        self._update_elided_text()

    def text(self) -> str:
        return self._full_text

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self):
        avail_w = (self.width() - 4) if self.width() > 24 else 230
        elided = self.fontMetrics().elidedText(self._full_text, self._elide_mode, avail_w)
        super().setText(elided)


class BeatSeekBar(QWidget):
    """Interactive audio seekbar with clickable/draggable scrubbing and visual timestamp marker pins."""
    seek_requested = Signal(int)
    scrub_started = Signal()
    scrub_finished = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(22)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self.duration_ms = 0
        self.position_ms = 0
        self.markers = []  # list of {"time_ms": int, "label": str}
        self._dragging = False

    def set_duration(self, duration_ms: int):
        self.duration_ms = max(0, int(duration_ms))
        self.update()

    def set_position(self, pos_ms: int):
        if not self._dragging:
            self.position_ms = max(0, int(pos_ms))
            self.update()

    def set_markers(self, markers: list[dict]):
        self.markers = list(markers)
        self.update()

    def _x_to_ms(self, x: float) -> int:
        if self.duration_ms <= 0:
            return 0
        pad = 6.0
        usable = max(1.0, self.width() - pad * 2.0)
        ratio = max(0.0, min(1.0, (x - pad) / usable))
        return int(ratio * self.duration_ms)

    def _ms_to_x(self, ms: int) -> float:
        pad = 6.0
        usable = max(1.0, self.width() - pad * 2.0)
        if self.duration_ms <= 0:
            return pad
        ratio = max(0.0, min(1.0, ms / float(self.duration_ms)))
        return pad + ratio * usable

    def _format_ms(self, ms: int) -> str:
        sec = max(0, int(ms // 1000))
        return f"{sec // 60:02d}:{sec % 60:02d}"

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.duration_ms > 0:
            click_x = event.position().x()
            snapped_ms = None
            for m in self.markers:
                mx = self._ms_to_x(m["time_ms"])
                if abs(click_x - mx) <= 6.0:
                    snapped_ms = int(m["time_ms"])
                    break
            target_ms = snapped_ms if snapped_ms is not None else self._x_to_ms(click_x)
            self._dragging = True
            self.position_ms = target_ms
            self.update()
            self.scrub_started.emit()
            self.seek_requested.emit(target_ms)

    def mouseMoveEvent(self, event):
        x = event.position().x()
        if self._dragging and self.duration_ms > 0:
            target_ms = self._x_to_ms(x)
            self.position_ms = target_ms
            self.update()
            self.seek_requested.emit(target_ms)
            return

        if self.duration_ms > 0:
            for m in self.markers:
                mx = self._ms_to_x(m["time_ms"])
                if abs(x - mx) <= 6.0:
                    QToolTip.showText(
                        event.globalPosition().toPoint(),
                        f"📍 {self._format_ms(m['time_ms'])} — {m['label']}",
                        self,
                    )
                    return
            hover_ms = self._x_to_ms(x)
            QToolTip.showText(event.globalPosition().toPoint(), self._format_ms(hover_ms), self)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._dragging:
            self._dragging = False
            target_ms = self._x_to_ms(event.position().x())
            self.position_ms = target_ms
            self.update()
            self.scrub_finished.emit(target_ms)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        pad = 6.0
        track_h = 6.0
        cy = self.height() / 2.0
        track_rect = QRectF(pad, cy - track_h / 2.0, max(1.0, self.width() - pad * 2.0), track_h)

        # Base groove
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#232332"))
        p.drawRoundedRect(track_rect, 3.0, 3.0)

        # Played fill
        if self.duration_ms > 0 and self.position_ms > 0:
            cur_x = self._ms_to_x(self.position_ms)
            fill_rect = QRectF(pad, cy - track_h / 2.0, max(0.0, cur_x - pad), track_h)
            grad = QLinearGradient(pad, 0, cur_x, 0)
            grad.setColorAt(0.0, QColor("#7E22CE"))
            grad.setColorAt(1.0, QColor("#C084FC"))
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(fill_rect, 3.0, 3.0)

        # Marker pins on timeline
        if self.duration_ms > 0:
            for m in self.markers:
                mx = self._ms_to_x(m["time_ms"])
                p.setPen(QPen(QColor("#22D3EE"), 2.0))
                p.drawLine(QPointF(mx, cy - 7.0), QPointF(mx, cy + 7.0))
                p.setBrush(QColor("#67E8F9"))
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(mx, cy - 7.0), 2.5, 2.5)

        # Playhead knob
        head_x = self._ms_to_x(self.position_ms)
        p.setPen(QPen(QColor("#F3E8FF"), 1.5))
        p.setBrush(QColor("#A855F7"))
        p.drawEllipse(QPointF(head_x, cy), 5.5, 5.5)


class NocturneMainWindow(QMainWindow):
    def __init__(self, profiles_root: str, profile_name: str, on_switch_profile_callback):
        super().__init__()
        self.profiles_root = profiles_root
        self.profile_name = profile_name
        self.profile_dir = os.path.join(self.profiles_root, self.profile_name)
        self.on_switch_profile = on_switch_profile_callback
        self.switch_requested = False

        LEXICON.load_profile(self.profile_dir)

        self.setWindowTitle(f"nocturne | {profile_name} — Untitled_Track_01")
        self.setWindowIcon(get_nocturne_app_icon())
        self.resize(1480, 910)

        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(0.8)
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)
        self.player.setLoops(QMediaPlayer.Infinite)
        self.player.positionChanged.connect(self._on_player_position_changed)
        self.player.durationChanged.connect(self._on_player_duration_changed)
        self.player.playbackStateChanged.connect(self._on_player_state_changed)

        self.metronome = MetronomeEngine(on_tick_callback=self.on_metronome_tick)

        self.beat_path = None
        self.beat_duration_ms = 0
        self.beat_markers = []
        self._is_scrubbing_seekbar = False
        self.is_playing = False
        self.is_looping = True
        self.metro_mode = "OFF"
        self._tap_timestamps = []

        self.seek_ui_timer = QTimer(self)
        self.seek_ui_timer.setInterval(50)
        self.seek_ui_timer.timeout.connect(self._update_seekbar_ui)
        self.seek_ui_timer.start()
        self.beat_sync_offset_ms = 0.0
        self.detected_bpm = None
        self.detected_beat_times_ms = []
        self.auto_beat_grid_active = False
        self._updating_bpm_from_auto = False
        self._beat_analyzer_worker = None
        self._active_workers = []
        self._last_synced_beat_idx = -1
        self._standalone_metro_start = 0.0
        self._auto_clock_start_perf = None
        self._auto_clock_base_ms = 0.0
        self._last_raw_player_pos_ms = 0
        self._init_zero_latency_clicks()

        self.metro_sync_timer = QTimer(self)
        self.metro_sync_timer.setTimerType(Qt.PreciseTimer)
        self.metro_sync_timer.setInterval(4)
        self.metro_sync_timer.timeout.connect(self._poll_metronome_master_clock)
        self._last_left_width = 330
        self._last_right_width = 360

        self.search_matches = []
        self.current_search_idx = -1
        self.last_rating_result = None

        self.vault_dir = os.path.join(self.profile_dir, "tracks_vault")
        self.trash_dir = os.path.join(self.profile_dir, "tracks_trash")
        os.makedirs(self.vault_dir, exist_ok=True)
        os.makedirs(self.trash_dir, exist_ok=True)
        self.current_track_created_at = None
        self.settings_file = os.path.join(self.profile_dir, "settings.json")
        self.studio_settings = dict(DEFAULT_STUDIO_SETTINGS)

        self._is_loading_track = False
        self.realtime_vault_timer = QTimer(self)
        self.realtime_vault_timer.setSingleShot(True)
        self.realtime_vault_timer.setInterval(600)
        self.realtime_vault_timer.timeout.connect(self._on_realtime_track_modified)

        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.autosave_silent)

        self.rate_scan_timer = QTimer(self)
        self.rate_scan_timer.setInterval(120)
        self.rate_scan_timer.timeout.connect(self._step_rate_scan)
        self.rate_scan_step = 0

        self.build_ui()
        self.load_profile_settings()
        self.load_vault_list()
        self.load_starter_demo()

        find_sc = QShortcut(QKeySequence("Ctrl+F"), self)
        find_sc.activated.connect(self.focus_lyric_search)

        esc_sc = QShortcut(QKeySequence("Escape"), self)
        esc_sc.activated.connect(self._on_escape_pressed)

        pin_sc = QShortcut(QKeySequence("Ctrl+M"), self)
        pin_sc.activated.connect(self.add_marker_at_current_time)

        stamp_sc = QShortcut(QKeySequence("Ctrl+T"), self)
        stamp_sc.activated.connect(self.stamp_timestamp_on_current_line)

        self.dim_overlay = ModalDimOverlay(self)
        
    def closeEvent(self, event):
        if getattr(self, "realtime_vault_timer", None) and self.realtime_vault_timer.isActive():
            self.realtime_vault_timer.stop()
            self.save_track()
        if hasattr(self, "metro_sync_timer") and self.metro_sync_timer.isActive():
            self.metro_sync_timer.stop()
        if hasattr(self, "player"):
            self.player.stop()
        for w in list(getattr(self, "_active_workers", [])):
            if w.isRunning():
                w.quit()
                if not w.wait(1500):
                    w.terminate()
                    w.wait(500)
        super().closeEvent(event)
        
    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(8)

        # --- TOP BAR ---
        top_bar = QFrame()
        top_bar.setObjectName("PanelCard")
        top_bar.setFixedHeight(56)
        top_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(12, 6, 12, 6)
        top_layout.setSpacing(8)

        app_icon_lbl = QLabel()
        app_icon_lbl.setPixmap(create_nocturne_icon_pixmap(30))
        app_icon_lbl.setFixedSize(30, 30)
        top_layout.addWidget(app_icon_lbl)

        logo = QLabel("nocturne")
        logo.setObjectName("TitleLogo")
        top_layout.addWidget(logo)

        self.btn_profile_cfg = QPushButton(f"👤 {self.profile_name}")
        self.btn_profile_cfg.setObjectName("ProfileBtn")
        self.btn_profile_cfg.setFixedHeight(32)
        self.btn_profile_cfg.setToolTip("Edit Profile (Rename, PIN Lock, Backup .ZIP)")
        self.btn_profile_cfg.clicked.connect(self.open_active_profile_settings)
        top_layout.addWidget(self.btn_profile_cfg)

        btn_switch = QPushButton("⇄")
        btn_switch.setToolTip("Switch Profile")
        btn_switch.setFixedSize(36, 32)
        btn_switch.clicked.connect(self.trigger_profile_switch)
        top_layout.addWidget(btn_switch)

        self.track_title_input = QLineEdit("Untitled_Track_01")
        self.track_title_input.setFixedSize(185, 32)
        self.track_title_input.setPlaceholderText("Track Title...")
        self.track_title_input.textChanged.connect(self.schedule_realtime_vault_update)
        self.track_title_input.textChanged.connect(
            lambda txt: self.setWindowTitle(f"nocturne | {self.profile_name} — {txt.strip() or 'Untitled_Track_01'}")
        )
        top_layout.addWidget(self.track_title_input)

        btn_save = QPushButton("Save Track")
        btn_save.setObjectName("PrimaryBtn")
        btn_save.setFixedHeight(32)
        btn_save.clicked.connect(self.save_track)
        top_layout.addWidget(btn_save)

        btn_new = QPushButton("+ New")
        btn_new.setFixedHeight(32)
        btn_new.setToolTip("Create a new track and immediately add it to the Vault")
        btn_new.clicked.connect(self.new_track)
        top_layout.addWidget(btn_new)

        btn_lexicon = QPushButton("📚 Slang Packs")
        btn_lexicon.setFixedHeight(32)
        btn_lexicon.clicked.connect(self.open_lexicon_manager)
        top_layout.addWidget(btn_lexicon)

        top_layout.addStretch()

        self.stat_rhymes = QLabel("RHYMES: 0")
        self.stat_rhymes.setObjectName("BadgeStat")
        self.stat_rhymes.setFixedHeight(30)
        top_layout.addWidget(self.stat_rhymes)

        btn_gear = QPushButton("⚙")
        btn_gear.setObjectName("GearBtn")
        btn_gear.setFixedSize(38, 32)
        btn_gear.setToolTip("Nocturne Studio Settings")
        btn_gear.clicked.connect(self.open_studio_settings)
        top_layout.addWidget(btn_gear)

        root_layout.addWidget(top_bar, 0)

        # --- MAIN 3-PANE SPLITTER ---
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(5)

        # ==========================================
        # LEFT PANE
        # ==========================================
        self.left_panel = QFrame()
        self.left_panel.setObjectName("PanelCard")
        self.left_panel.setMinimumWidth(315)
        self.left_panel.setMaximumWidth(440)
        left_outer_layout = QVBoxLayout(self.left_panel)
        left_outer_layout.setContentsMargins(2, 2, 2, 2)
        left_outer_layout.setSpacing(0)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll_body = QWidget()
        left_scroll_body.setStyleSheet("background-color: transparent;")
        left_layout = QVBoxLayout(left_scroll_body)
        left_layout.setContentsMargins(10, 10, 10, 12)
        left_layout.setSpacing(8)

        vault_hdr_row = QHBoxLayout()
        self.vault_header_lbl = QLabel(f"VAULT // {self.profile_name.upper()}", objectName="SectionHeader")
        self.vault_header_lbl.setTextFormat(Qt.PlainText)
        vault_hdr_row.addWidget(self.vault_header_lbl)
        vault_hdr_row.addStretch()

        btn_hide_left_inline = QPushButton("◀")
        btn_hide_left_inline.setObjectName("EdgeArrowBtn")
        btn_hide_left_inline.setFixedSize(24, 22)
        btn_hide_left_inline.setToolTip("Collapse Left Sidebar")
        btn_hide_left_inline.clicked.connect(lambda: self.set_left_sidebar_visible(False))
        vault_hdr_row.addWidget(btn_hide_left_inline)
        left_layout.addLayout(vault_hdr_row)

        self.vault_search_input = QLineEdit()
        self.vault_search_input.setPlaceholderText("🔍 Filter tracks by title or lyrics...")
        self.vault_search_input.textChanged.connect(self.load_vault_list)
        left_layout.addWidget(self.vault_search_input)

        self.vault_list = QListWidget()
        self.vault_list.setMinimumHeight(74)
        self.vault_list.setMaximumHeight(92)
        self.vault_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.vault_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.vault_list.setStyleSheet("QListWidget::item { padding: 3px 6px; font-size: 11px; }")
        self.vault_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.vault_list.customContextMenuRequested.connect(self.show_vault_context_menu)
        self.vault_list.itemClicked.connect(self.open_track_from_vault)
        left_layout.addWidget(self.vault_list)

        vault_actions_row = QHBoxLayout()
        vault_actions_row.setSpacing(4)

        btn_full_vault = QPushButton("⛶ Full Vault")
        btn_full_vault.setStyleSheet("padding: 4px 7px; font-size: 11px;")
        btn_full_vault.setToolTip("Open Full Vault Window")
        btn_full_vault.clicked.connect(lambda: self.open_full_vault_dialog(start_tab=0))
        vault_actions_row.addWidget(btn_full_vault, 2)

        self.btn_recycle_bin = QPushButton("🗑 Bin (0)")
        self.btn_recycle_bin.setStyleSheet("padding: 4px 7px; font-size: 11px;")
        self.btn_recycle_bin.setToolTip("Open Recycle Bin to Restore or Permanently Delete Tracks")
        self.btn_recycle_bin.clicked.connect(lambda: self.open_full_vault_dialog(start_tab=1))
        vault_actions_row.addWidget(self.btn_recycle_bin, 2)

        btn_del_vault_item = QPushButton("✕")
        btn_del_vault_item.setObjectName("DangerBtn")
        btn_del_vault_item.setFixedWidth(30)
        btn_del_vault_item.setStyleSheet("padding: 4px 0px; font-size: 11px;")
        btn_del_vault_item.setToolTip("Move Selected Track to Recycle Bin")
        btn_del_vault_item.clicked.connect(self.delete_selected_vault_track)
        vault_actions_row.addWidget(btn_del_vault_item)

        left_layout.addLayout(vault_actions_row)

        # Beat Deck + Metronome
        left_layout.addWidget(QLabel("BEAT PLAYER", objectName="SectionHeader"))
        beat_box = QFrame()
        beat_box.setStyleSheet("background-color: #13131B; border: 1px solid #2D2244; border-radius: 6px; padding: 6px;")
        beat_layout = QVBoxLayout(beat_box)
        beat_layout.setSpacing(6)

        self.beat_label = ElidedLabel("No beat loaded (.mp3 / .wav)")
        self.beat_label.setTextFormat(Qt.PlainText)
        self.beat_label.setStyleSheet("color: #D4D4D8; font-size: 11px; font-weight: 600; border: none;")
        beat_layout.addWidget(self.beat_label)

        beat_btns = QHBoxLayout()
        beat_btns.setSpacing(4)
        self.btn_load_beat = QPushButton("Load Beat")
        self.btn_load_beat.setFixedHeight(26)
        self.btn_load_beat.setStyleSheet("padding: 4px 6px; font-size: 11px;")
        self.btn_load_beat.clicked.connect(self.on_load_or_unload_beat_clicked)

        self.btn_play_beat = QPushButton("▶ Play")
        self.btn_play_beat.setFixedSize(62, 26)
        self.btn_play_beat.clicked.connect(self.toggle_beat_playback)

        self.btn_loop = QPushButton("🔁 Loop: ON")
        self.btn_loop.setCheckable(True)
        self.btn_loop.setChecked(True)
        self.btn_loop.setFixedSize(78, 26)
        self.btn_loop.clicked.connect(self.toggle_loop)

        beat_btns.addWidget(self.btn_load_beat, 1)
        beat_btns.addWidget(self.btn_play_beat)
        beat_btns.addWidget(self.btn_loop)
        beat_layout.addLayout(beat_btns)

        self._update_play_button_state()
        self._update_loop_button_state()

        # Seekbar + Time Readout Row
        seek_row = QHBoxLayout()
        seek_row.setSpacing(6)
        self.beat_seekbar = BeatSeekBar()
        self.beat_seekbar.scrub_started.connect(self._on_seek_scrub_started)
        self.beat_seekbar.seek_requested.connect(self._on_seek_requested)
        self.beat_seekbar.scrub_finished.connect(self._on_seek_scrub_finished)
        seek_row.addWidget(self.beat_seekbar, 1)

        self.lbl_beat_time = QLabel("00:00 / 00:00")
        self.lbl_beat_time.setStyleSheet(
            "background: transparent; border: none; color: #C4B5FD; "
            "font-family: 'Consolas', monospace; font-size: 10px; font-weight: 700;"
        )
        seek_row.addWidget(self.lbl_beat_time)
        beat_layout.addLayout(seek_row)

        # Timestamp Marker Pinning & Section Jump Row
        marker_ctrl_row = QHBoxLayout()
        marker_ctrl_row.setSpacing(4)

        self.btn_pin_marker = QPushButton("📍 Pin")
        self.btn_pin_marker.setFixedHeight(23)
        self.btn_pin_marker.setMinimumWidth(0)
        self.btn_pin_marker.setToolTip("Pin timestamp marker at current playback time (Ctrl+M)")
        self.btn_pin_marker.setStyleSheet("""
            QPushButton {
                background-color: #0E2433;
                border: 1px solid #0891B2;
                color: #67E8F9;
                padding: 2px 5px;
                font-size: 10px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #15364D;
                border-color: #22D3EE;
                color: #FFFFFF;
            }
        """)
        self.btn_pin_marker.clicked.connect(self.add_marker_at_current_time)
        marker_ctrl_row.addWidget(self.btn_pin_marker)

        self.btn_stamp_line = QPushButton("⏱ Stamp")
        self.btn_stamp_line.setFixedHeight(23)
        self.btn_stamp_line.setMinimumWidth(0)
        self.btn_stamp_line.setToolTip("Insert [MM:SS] timestamp on current lyric line (Ctrl+T)")
        self.btn_stamp_line.setStyleSheet("""
            QPushButton {
                background-color: #1F1433;
                border: 1px solid #7C3AED;
                color: #E9D5FF;
                padding: 2px 5px;
                font-size: 10px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #3B0764;
                border-color: #C084FC;
                color: #FFFFFF;
            }
        """)
        self.btn_stamp_line.clicked.connect(self.stamp_timestamp_on_current_line)
        marker_ctrl_row.addWidget(self.btn_stamp_line)

        self.marker_combo = QComboBox()
        self.marker_combo.setMinimumWidth(0)
        self.marker_combo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.marker_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.marker_combo.setFixedHeight(23)
        self.marker_combo.setToolTip("Jump to pinned timestamp marker (Right-click for Rename/Delete)")
        self.marker_combo.setStyleSheet("""
            QComboBox {
                padding: 2px 16px 2px 5px;
                font-size: 10px;
                font-weight: 600;
                min-height: 18px;
            }
            QComboBox::drop-down {
                width: 15px;
            }
        """)
        self.marker_combo.activated.connect(self._on_marker_combo_selected)
        self.marker_combo.setContextMenuPolicy(Qt.CustomContextMenu)
        self.marker_combo.customContextMenuRequested.connect(self._show_marker_context_menu)
        marker_ctrl_row.addWidget(self.marker_combo, 1)

        beat_layout.addLayout(marker_ctrl_row)
        self._refresh_markers_ui()

        bpm_row = QHBoxLayout()
        bpm_row.setSpacing(4)
        lbl_bpm = QLabel("BPM:")
        lbl_bpm.setStyleSheet("background: transparent; border: none; font-size: 11px;")
        bpm_row.addWidget(lbl_bpm)

        self.bpm_spin = QSpinBox()
        self.bpm_spin.setRange(40, 260)
        self.bpm_spin.setValue(140)
        self.bpm_spin.setFixedWidth(78)
        self.bpm_spin.setStyleSheet("padding: 3px 2px 3px 5px; font-size: 11px;")
        self.bpm_spin.valueChanged.connect(self._on_bpm_spin_changed)
        bpm_row.addWidget(self.bpm_spin)

        self.btn_tap_bpm = QPushButton("TAP")
        self.btn_tap_bpm.setFixedSize(32, 24)
        self.btn_tap_bpm.setToolTip("Tap along to the beat to calculate BPM automatically")
        self.btn_tap_bpm.setStyleSheet("""
            QPushButton {
                background-color: #1D152C;
                border: 1px solid #6D28D9;
                color: #E9D5FF;
                border-radius: 5px;
                padding: 0px;
                font-size: 10px;
                font-weight: 800;
            }
            QPushButton:hover {
                background-color: #581C87;
                border-color: #C084FC;
                color: #FFFFFF;
            }
        """)
        self.btn_tap_bpm.clicked.connect(self.on_tap_tempo)
        bpm_row.addWidget(self.btn_tap_bpm)

        lbl_vol = QLabel("Vol:")
        lbl_vol.setStyleSheet("background: transparent; border: none; font-size: 11px;")
        bpm_row.addWidget(lbl_vol)

        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setMinimumWidth(24)
        self.vol_slider.valueChanged.connect(lambda v: self.audio_output.setVolume(v / 100.0))
        bpm_row.addWidget(self.vol_slider, 1)
        beat_layout.addLayout(bpm_row)

        metro_row = QHBoxLayout()
        metro_row.setSpacing(3)
        self.btn_metro = QPushButton("⏱ Metro: OFF")
        self.btn_metro.setCheckable(True)
        self.btn_metro.setFixedSize(96, 24)
        self.btn_metro.setStyleSheet("padding: 3px 4px; font-size: 11px; font-weight: 600;")
        self.btn_metro.clicked.connect(self.toggle_metronome)
        metro_row.addWidget(self.btn_metro)

        self.metro_sig_combo = QComboBox()
        self.metro_sig_combo.addItem("4/4", 4)
        self.metro_sig_combo.addItem("3/4", 3)
        self.metro_sig_combo.addItem("6/8", 6)
        self.metro_sig_combo.setFixedWidth(62)
        self.metro_sig_combo.setStyleSheet("""
            QComboBox {
                padding: 3px 14px 3px 5px;
                font-size: 11px;
                font-weight: 700;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 15px;
                border-left: 1px solid #323240;
            }
        """)
        self.metro_sig_combo.view().setMinimumWidth(84)
        self.metro_sig_combo.view().setStyleSheet("""
            QListView {
                background-color: #13131A;
                border: 1px solid #8B5CF6;
                border-radius: 6px;
                padding: 3px;
                outline: none;
            }
            QListView::item {
                min-height: 24px;
                padding: 3px 6px;
                color: #F4F4F5;
                font-size: 11px;
                font-weight: 600;
            }
            QListView::item:selected {
                background-color: #6B21A8;
                color: #FFFFFF;
            }
        """)
        self.metro_sig_combo.currentIndexChanged.connect(self.on_metro_sig_changed)
        metro_row.addWidget(self.metro_sig_combo)

        metro_row.addStretch(1)

        self.metro_leds = []
        for _ in range(4):
            led = QLabel()
            led.setFixedSize(9, 9)
            led.setStyleSheet("background-color: #2E2E3D; border: 1px solid #3F3F4E; border-radius: 4px; padding: 0px;")
            self.metro_leds.append(led)
            metro_row.addWidget(led)

        self.btn_anchor_beat1 = QPushButton("1!")
        self.btn_anchor_beat1.setFixedSize(24, 22)
        self.btn_anchor_beat1.setToolTip("Sync manually")
        self.btn_anchor_beat1.setStyleSheet("""
            QPushButton {
                background-color: #1A1626;
                border: 1px solid #581C87;
                color: #D8B4FE;
                border-radius: 4px;
                padding: 0px;
                font-size: 10px;
                font-weight: 800;
            }
            QPushButton:hover {
                background-color: #6B21A8;
                border-color: #C084FC;
                color: #FFFFFF;
            }
        """)
        self.btn_anchor_beat1.clicked.connect(self.anchor_downbeat_now)
        metro_row.addWidget(self.btn_anchor_beat1)

        beat_layout.addLayout(metro_row)
        left_layout.addWidget(beat_box)

        # Punchline Vault (Scrapbook)
        left_layout.addWidget(QLabel("PUNCHLINE VAULT (SCRAPBOOK)", objectName="SectionHeader"))
        self.stash_editor = QPlainTextEdit()
        self.stash_editor.setMinimumHeight(64)
        self.stash_editor.setMaximumHeight(82)
        self.stash_editor.setPlaceholderText("Drop loose bars, hooks, or slang ideas here...")
        self.stash_editor.textChanged.connect(self.schedule_realtime_vault_update)
        self.stash_editor.setStyleSheet("""
            QPlainTextEdit {
                background-color: transparent;
                border: 1px solid #23232E;
                border-radius: 6px;
                color: #DDD6FE;
                font-size: 12px;
                padding: 6px;
            }
        """)
        left_layout.addWidget(self.stash_editor)

        # Rate My Lyrics (Interactive Pen Meter)
        left_layout.addWidget(QLabel("RATE MY LYRICS // PEN METER", objectName="SectionHeader"))
        rate_box = QFrame()
        rate_box.setStyleSheet("""
            QFrame {
                background-color: #130F1F;
                border: 1px solid #4C1D95;
                border-radius: 8px;
            }
        """)
        rate_layout = QVBoxLayout(rate_box)
        rate_layout.setContentsMargins(10, 10, 10, 10)
        rate_layout.setSpacing(8)

        gauge_row = QHBoxLayout()
        gauge_row.setSpacing(10)

        self.sidebar_gauge = RatingRingWidget(size=80)
        gauge_row.addWidget(self.sidebar_gauge)

        mini_stats_col = QVBoxLayout()
        mini_stats_col.setSpacing(4)

        self.rate_tier_lbl = QLabel("READY TO SCAN")
        self.rate_tier_lbl.setTextFormat(Qt.PlainText)
        self.rate_tier_lbl.setStyleSheet("color: #D8B4FE; font-size: 11px; font-weight: 800; letter-spacing: 0.4px; border: none;")
        mini_stats_col.addWidget(self.rate_tier_lbl)

        self.mini_multie_lbl = QLabel("Multies: —  •  Flow: —")
        self.mini_multie_lbl.setTextFormat(Qt.PlainText)
        self.mini_multie_lbl.setStyleSheet("color: #F4F4F5; font-size: 11px; border: none;")
        mini_stats_col.addWidget(self.mini_multie_lbl)

        self.mini_wp_lbl = QLabel("Wordplay / DE: —")
        self.mini_wp_lbl.setTextFormat(Qt.PlainText)
        self.mini_wp_lbl.setStyleSheet("color: #F4F4F5; font-size: 11px; border: none;")
        mini_stats_col.addWidget(self.mini_wp_lbl)

        self.mini_struct_lbl = QLabel("Structure & Vocab: —")
        self.mini_struct_lbl.setTextFormat(Qt.PlainText)
        self.mini_struct_lbl.setStyleSheet("color: #D4D4D8; font-size: 11px; border: none;")
        mini_stats_col.addWidget(self.mini_struct_lbl)

        gauge_row.addLayout(mini_stats_col, 1)
        rate_layout.addLayout(gauge_row)

        self.rate_scan_bar = QProgressBar()
        self.rate_scan_bar.setRange(0, 100)
        self.rate_scan_bar.setValue(0)
        self.rate_scan_bar.setTextVisible(False)
        self.rate_scan_bar.setFixedHeight(6)
        self.rate_scan_bar.setVisible(False)
        rate_layout.addWidget(self.rate_scan_bar)

        rate_btn_row = QHBoxLayout()
        rate_btn_row.setSpacing(5)
        self.btn_rate_now = QPushButton("⚡ Rate Lyrics")
        self.btn_rate_now.setObjectName("PrimaryBtn")
        self.btn_rate_now.setMinimumWidth(0)
        self.btn_rate_now.setStyleSheet("padding: 5px 6px; font-size: 11px;")
        self.btn_rate_now.clicked.connect(self.trigger_rate_my_lyrics)
        rate_btn_row.addWidget(self.btn_rate_now, 1)

        self.btn_rate_details = QPushButton("📊 Details")
        self.btn_rate_details.setMinimumWidth(0)
        self.btn_rate_details.setStyleSheet("padding: 5px 6px; font-size: 11px;")
        self.btn_rate_details.setToolTip("Open Full Interactive Lyric Scorecard & Line Highlights")
        self.btn_rate_details.clicked.connect(self.open_rating_breakdown_dialog)
        rate_btn_row.addWidget(self.btn_rate_details, 1)

        rate_layout.addLayout(rate_btn_row)
        left_layout.addWidget(rate_box)
        left_layout.addStretch()

        left_scroll.setWidget(left_scroll_body)
        left_outer_layout.addWidget(left_scroll)

        # ==========================================
        # CENTER PANE
        # ==========================================
        self.center_panel = QFrame()
        self.center_panel.setObjectName("PanelCard")
        self.center_panel.setMinimumWidth(420)
        center_layout = QVBoxLayout(self.center_panel)
        center_layout.setContentsMargins(6, 8, 6, 6)
        center_layout.setSpacing(6)

        editor_toolbar = QHBoxLayout()
        editor_toolbar.setContentsMargins(10, 0, 10, 0)
        editor_toolbar.setSpacing(6)

        self.rhyme_badge = QLabel("Rhymes:")
        self.rhyme_badge.setCursor(Qt.PointingHandCursor)
        self.rhyme_badge.setToolTip("Click to clear Solo rhyme filter")
        self.rhyme_badge.setStyleSheet("color: #B4B4BE; font-size: 11px; font-weight: 600;")
        self.rhyme_badge.mousePressEvent = lambda _e: self.toggle_rhyme_solo(None)
        editor_toolbar.addWidget(self.rhyme_badge)

        self.rhyme_badge.setVisible(False)
        self.solo_rhyme_group = None
        self.rhyme_dots = []

        for idx, (bg_hex, fg_hex) in enumerate(RHYME_PALETTE):
            _c = QColor(bg_hex)
            # brighter twin of the highlight colour, keeping its own hue/saturation/lightness character
            vivid_color = QColor.fromHsl(
                max(0, _c.hslHue()), min(255, _c.hslSaturation() + 30), min(185, _c.lightness() + 60)
            ).name()

            dot = RhymeDot(idx, vivid_color)
            dot.setVisible(False)
            dot.solo_toggled.connect(self.toggle_rhyme_solo)
            dot.jump_requested.connect(self.jump_to_rhyme_group)
            editor_toolbar.addWidget(dot)
            self.rhyme_dots.append(dot)

        self.rhyme_sep1 = QLabel("|")
        self.rhyme_sep1.setStyleSheet("color: #3F3F4E; font-size: 11px;")
        self.rhyme_sep1.setVisible(False)
        editor_toolbar.addWidget(self.rhyme_sep1)

        self.solo_special_mode = None

        

        editor_toolbar.addStretch()

        self.font_tag_lbl = QLabel("Aa")
        self.font_tag_lbl.setTextFormat(Qt.PlainText)
        self.font_tag_lbl.setToolTip("Font: SF Pro Bold")
        self.font_tag_lbl.setStyleSheet("background: transparent; color: #8E8EA0; font-size: 12px; font-weight: 700;")
        editor_toolbar.addWidget(self.font_tag_lbl)

        self.font_slider = QSlider(Qt.Horizontal)
        self.font_slider.setRange(11, 36)
        self.font_slider.setValue(15)
        self.font_slider.setFixedWidth(96)
        self.font_slider.setToolTip("Adjust Lyric Editor Font Size")
        self.font_slider.valueChanged.connect(self.on_font_slider_changed)
        editor_toolbar.addWidget(self.font_slider)

        self.font_size_label = QLabel("15pt")
        self.font_size_label.setStyleSheet("background: transparent; color: #C4B5FD; font-family: 'Consolas'; font-size: 11px; font-weight: 700;")
        self.font_size_label.setFixedWidth(34)
        editor_toolbar.addWidget(self.font_size_label)

        center_layout.addLayout(editor_toolbar)

        self.find_bar_widget = QWidget()
        self.find_bar_widget.setStyleSheet("background: transparent;")
        self.find_bar_widget.setVisible(False)
        find_bar = QHBoxLayout(self.find_bar_widget)
        find_bar.setContentsMargins(10, 2, 10, 2)
        self.lyric_search_input = QLineEdit()
        self.lyric_search_input.setPlaceholderText("🔍 Search in current lyrics (Ctrl+F)...")
        self.lyric_search_input.setFixedHeight(30)
        self.lyric_search_input.textChanged.connect(self.perform_lyric_search)
        self.lyric_search_input.returnPressed.connect(self.next_search_match)
        find_bar.addWidget(self.lyric_search_input)

        self.search_count_lbl = QLabel("0 / 0")
        self.search_count_lbl.setStyleSheet("color: #D4D4D8; font-family: 'Consolas'; font-size: 11px; font-weight: 600; padding: 0 4px;")
        find_bar.addWidget(self.search_count_lbl)

        btn_prev_match = QPushButton("▲")
        btn_prev_match.setFixedSize(30, 30)
        btn_prev_match.setToolTip("Previous Match")
        btn_prev_match.clicked.connect(self.prev_search_match)
        find_bar.addWidget(btn_prev_match)

        btn_next_match = QPushButton("▼")
        btn_next_match.setFixedSize(30, 30)
        btn_next_match.setToolTip("Next Match")
        btn_next_match.clicked.connect(self.next_search_match)
        find_bar.addWidget(btn_next_match)

        btn_clear_search = QPushButton("✕")
        btn_clear_search.setFixedSize(30, 30)
        btn_clear_search.setToolTip("Close Search (Esc)")
        btn_clear_search.clicked.connect(self.clear_lyric_search)
        find_bar.addWidget(btn_clear_search)

        center_layout.addWidget(self.find_bar_widget)

        self.lyric_editor = LyricEditor(
            on_word_selected_callback=self.lookup_rhyme_word,
            on_analysis_updated_callback=self.update_stats_badges,
            on_quick_add_slang_callback=self.quick_add_slang_word,
            on_cursor_word_changed_callback=self.on_editor_cursor_word_changed,
            on_timestamp_clicked_callback=self.jump_to_beat_timestamp_ms,
            on_set_pronunciation_callback=self.set_word_pronunciation,
        )
        self.lyric_editor.textChanged.connect(lambda: self.perform_lyric_search(self.lyric_search_input.text(), auto_jump=False))
        self.lyric_editor.textChanged.connect(self.schedule_realtime_vault_update)
        center_layout.addWidget(self.lyric_editor)

        # ==========================================
        # RIGHT PANE
        # ==========================================
        self.right_panel = QFrame()
        self.right_panel.setObjectName("PanelCard")
        self.right_panel.setMinimumWidth(315)
        self.right_panel.setMaximumWidth(460)
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(10, 12, 10, 12)
        right_layout.setSpacing(10)

        r_hdr_row = QHBoxLayout()
        r_hdr_row.setSpacing(4)
        r_hdr_lbl = QLabel("RHYME ENGINE", objectName="SectionHeader")
        r_hdr_lbl.setMinimumWidth(0)
        r_hdr_row.addWidget(r_hdr_lbl)
        r_hdr_row.addStretch()

        self.btn_live_rhyme = QPushButton("⚡ Live")
        self.btn_live_rhyme.setCheckable(True)
        self.btn_live_rhyme.setChecked(True)
        self.btn_live_rhyme.setMinimumWidth(0)
        self.btn_live_rhyme.setStyleSheet("padding: 2px 6px; font-size: 10px;")
        self.btn_live_rhyme.setToolTip("Auto-detect rhymes & matching lines in realtime while typing")
        r_hdr_row.addWidget(self.btn_live_rhyme)

        btn_quick_lex = QPushButton("+ Slang")
        btn_quick_lex.setMinimumWidth(0)
        btn_quick_lex.setStyleSheet("padding: 2px 6px; font-size: 10px;")
        btn_quick_lex.clicked.connect(self.open_lexicon_manager)
        r_hdr_row.addWidget(btn_quick_lex)

        btn_hide_right_inline = QPushButton("▶")
        btn_hide_right_inline.setObjectName("EdgeArrowBtn")
        btn_hide_right_inline.setFixedSize(22, 22)
        btn_hide_right_inline.setToolTip("Collapse Right Sidebar")
        btn_hide_right_inline.clicked.connect(lambda: self.set_right_sidebar_visible(False))
        r_hdr_row.addWidget(btn_hide_right_inline)
        right_layout.addLayout(r_hdr_row)

        search_row = QHBoxLayout()
        search_row.setSpacing(4)
        self.rhyme_search_input = QLineEdit()
        self.rhyme_search_input.setMinimumWidth(0)
        self.rhyme_search_input.setPlaceholderText("Auto-detecting as you type...")
        self.rhyme_search_input.returnPressed.connect(
            lambda: self.lookup_rhyme_word(self.rhyme_search_input.text(), from_live=False)
        )
        btn_search = QPushButton("Find")
        btn_search.setObjectName("PrimaryBtn")
        btn_search.setMinimumWidth(0)
        btn_search.setStyleSheet("padding: 5px 10px; font-size: 11px;")
        btn_search.clicked.connect(
            lambda: self.lookup_rhyme_word(self.rhyme_search_input.text(), from_live=False)
        )
        search_row.addWidget(self.rhyme_search_input, 1)
        search_row.addWidget(btn_search)
        right_layout.addLayout(search_row)

        self.inspected_meta = QLabel("Type or click any word in lyrics for realtime detection")
        self.inspected_meta.setTextFormat(Qt.PlainText)
        self.inspected_meta.setMinimumWidth(0)
        self.inspected_meta.setStyleSheet("color: #D8B4FE; font-weight: 700; font-size: 11px;")
        right_layout.addWidget(self.inspected_meta)

        self.matching_lines_hdr = QLabel("RHYMING LINES IN LYRICS (0)", objectName="SectionHeader")
        right_layout.addWidget(self.matching_lines_hdr)

        self.list_matching_lines = QListWidget()
        self.list_matching_lines.setMinimumHeight(60)
        self.list_matching_lines.setMaximumHeight(80)
        self.list_matching_lines.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_matching_lines.setTextElideMode(Qt.ElideRight)
        self.list_matching_lines.setStyleSheet("QListWidget::item { padding: 3px 6px; font-size: 11px; }")
        self.list_matching_lines.setToolTip("Click any matching line to jump to it in the editor")
        self.list_matching_lines.itemClicked.connect(self.on_matching_line_clicked)
        right_layout.addWidget(self.list_matching_lines)

        self._rhyme_filter = "ALL"
        self._rhyme_buckets = {"ALL": [], "EN": [], "BM": [], "PACKS": [], "SLANT": []}

        chip_row = QHBoxLayout()
        chip_row.setSpacing(4)
        self._rhyme_chip_group = QButtonGroup(self)
        self._rhyme_chip_group.setExclusive(True)

        chip_qss = """
            QPushButton {
                background-color: #161620;
                color: #A1A1AA;
                border: 1px solid #2A2A38;
                border-radius: 10px;
                padding: 3px 8px;
                font-size: 10px;
                font-weight: 700;
            }
            QPushButton:hover {
                border-color: #A855F7;
                color: #FFFFFF;
            }
            QPushButton:checked {
                background-color: #3B0764;
                color: #F3E8FF;
                border-color: #C084FC;
            }
        """
        for label, key in [
            ("All", "ALL"),
            ("EN+Slang", "EN"),
            ("BM+Pasar", "BM"),
            ("Packs", "PACKS"),
            ("Slant", "SLANT"),
        ]:
            chip = QPushButton(label)
            chip.setCheckable(True)
            chip.setChecked(key == "ALL")
            chip.setMinimumWidth(0)
            chip.setCursor(Qt.PointingHandCursor)
            chip.setStyleSheet(chip_qss)
            chip.clicked.connect(lambda _checked, k=key: self._set_rhyme_filter(k))
            self._rhyme_chip_group.addButton(chip)
            chip_row.addWidget(chip)

        right_layout.addLayout(chip_row)

        self.list_rhymes = QListWidget()
        self.list_rhymes.setMinimumWidth(0)
        self.list_rhymes.itemDoubleClicked.connect(self.insert_rhyme_into_editor)
        right_layout.addWidget(self.list_rhymes)

        right_layout.addWidget(QLabel("WORDPLAY / DOUBLE ENTENDRE LAB", objectName="SectionHeader"))
        self.wordplay_box = QPlainTextEdit()
        self.wordplay_box.setReadOnly(True)
        self.wordplay_box.setMaximumHeight(175)
        self.wordplay_box.setStyleSheet("""
            QPlainTextEdit {
                background-color: #110D1B;
                border: 1px solid #4C1D95;
                border-radius: 6px;
                color: #F3E8FF;
                font-size: 12px;
                padding: 8px;
            }
        """)
        right_layout.addWidget(self.wordplay_box)

        # Collapsed Left Edge Strip
        self.left_collapsed_strip = QFrame()
        self.left_collapsed_strip.setObjectName("CollapsedSidebarStrip")
        self.left_collapsed_strip.setFixedWidth(28)
        self.left_collapsed_strip.setVisible(False)
        l_strip_lay = QVBoxLayout(self.left_collapsed_strip)
        l_strip_lay.setContentsMargins(2, 8, 2, 8)
        btn_expand_left = QPushButton("▶")
        btn_expand_left.setObjectName("EdgeArrowBtn")
        btn_expand_left.setFixedSize(22, 34)
        btn_expand_left.setToolTip("Open Left Sidebar (Vault, Beat Deck & Pen Meter)")
        btn_expand_left.clicked.connect(lambda: self.set_left_sidebar_visible(True))
        l_strip_lay.addWidget(btn_expand_left, alignment=Qt.AlignHCenter)
        l_strip_lay.addStretch()

        # Collapsed Right Edge Strip
        self.right_collapsed_strip = QFrame()
        self.right_collapsed_strip.setObjectName("CollapsedSidebarStrip")
        self.right_collapsed_strip.setFixedWidth(28)
        self.right_collapsed_strip.setVisible(False)
        r_strip_lay = QVBoxLayout(self.right_collapsed_strip)
        r_strip_lay.setContentsMargins(2, 8, 2, 8)
        btn_expand_right = QPushButton("◀")
        btn_expand_right.setObjectName("EdgeArrowBtn")
        btn_expand_right.setFixedSize(22, 34)
        btn_expand_right.setToolTip("Open Right Sidebar (Rhyme & Wordplay Engine)")
        btn_expand_right.clicked.connect(lambda: self.set_right_sidebar_visible(True))
        r_strip_lay.addWidget(btn_expand_right, alignment=Qt.AlignHCenter)
        r_strip_lay.addStretch()

        self.main_splitter.addWidget(self.left_panel)
        self.main_splitter.addWidget(self.center_panel)
        self.main_splitter.addWidget(self.right_panel)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 0)
        self.main_splitter.setSizes([315, 785, 360])
        self.main_splitter.splitterMoved.connect(self._on_splitter_dragged)

        workspace_row = QHBoxLayout()
        workspace_row.setContentsMargins(0, 0, 0, 0)
        workspace_row.setSpacing(6)
        workspace_row.addWidget(self.left_collapsed_strip)
        workspace_row.addWidget(self.main_splitter, 1)
        workspace_row.addWidget(self.right_collapsed_strip)

        root_layout.addLayout(workspace_row, 1)

    # --- SIDEBAR HIDE / OPEN CONTROLS ---
    def _on_splitter_dragged(self, _pos: int, _index: int):
        sizes = self.main_splitter.sizes()
        if self.left_panel.isVisible() and sizes[0] >= 315:
            self._last_left_width = sizes[0]
        if self.right_panel.isVisible() and sizes[2] >= 315:
            self._last_right_width = sizes[2]

    def set_left_sidebar_visible(self, visible: bool):
        sizes = self.main_splitter.sizes()
        if not visible and self.left_panel.isVisible() and sizes[0] >= 315:
            self._last_left_width = sizes[0]

        self.left_panel.setVisible(visible)
        self.left_collapsed_strip.setVisible(not visible)

        if visible:
            total = max(960, self.main_splitter.width())
            r_w = sizes[2] if self.right_panel.isVisible() else 0
            l_w = max(315, min(440, self._last_left_width))
            c_w = max(420, total - l_w - r_w)
            self.main_splitter.setSizes([l_w, c_w, r_w])

    def set_right_sidebar_visible(self, visible: bool):
        sizes = self.main_splitter.sizes()
        if not visible and self.right_panel.isVisible() and sizes[2] >= 315:
            self._last_right_width = sizes[2]

        self.right_panel.setVisible(visible)
        self.right_collapsed_strip.setVisible(not visible)

        if visible:
            total = max(960, self.main_splitter.width())
            l_w = sizes[0] if self.left_panel.isVisible() else 0
            r_w = max(315, min(460, self._last_right_width))
            c_w = max(420, total - l_w - r_w)
            self.main_splitter.setSizes([l_w, c_w, r_w])

    # --- RATE MY LYRICS INTERACTIVE FLOW ---
    def trigger_rate_my_lyrics(self):
        self.rate_scan_step = 0
        self.rate_scan_bar.setVisible(True)
        self.rate_scan_bar.setValue(15)
        self.btn_rate_now.setEnabled(False)
        self.rate_tier_lbl.setText("SCANNING MULTIES...")
        self.rate_scan_timer.start()

    def _step_rate_scan(self):
        self.rate_scan_step += 1
        if self.rate_scan_step == 1:
            self.rate_scan_bar.setValue(45)
            self.rate_tier_lbl.setText("CHECKING WORDPLAY...")
        elif self.rate_scan_step == 2:
            self.rate_scan_bar.setValue(78)
            self.rate_tier_lbl.setText("ANALYZING CADENCE...")
        else:
            self.rate_scan_timer.stop()
            self.rate_scan_bar.setValue(100)
            self.rate_scan_bar.setVisible(False)
            self.btn_rate_now.setEnabled(True)
            self._finalize_lyric_rating(animate=True)

    def _finalize_lyric_rating(self, animate: bool = True):
        res = rate_lyrics_comprehensive(
            self.lyric_editor.toPlainText(),
            rhyme_window=self.studio_settings.get("rhyme_window", 4),
        )
        self.last_rating_result = res
        self.sidebar_gauge.set_score(res["overall"], res["color"], animate=animate)
        self.rate_tier_lbl.setText(res["tier"])
        self.rate_tier_lbl.setStyleSheet(f"color: {res['color']}; font-size: 11px; font-weight: 800; border: none;")

        bd = res["breakdown"]
        self.mini_multie_lbl.setText(f"Multies: {bd['multies']}%  •  Flow: {bd['flow']}%")
        self.mini_wp_lbl.setText(f"Wordplay / DE: {bd['wordplay']}%")
        self.mini_struct_lbl.setText(f"Structure: {bd['structure']}%  •  Vocab: {bd['vocab']}%")

    def open_rating_breakdown_dialog(self):
        self._finalize_lyric_rating(animate=False)
        dlg = LyricRatingDialog(
            self,
            rating_data=self.last_rating_result,
            on_jump_line_callback=self.lyric_editor.jump_to_line,
        )
        dlg.exec()

    # --- IN-EDITOR LYRIC SEARCH BAR ---
    def focus_lyric_search(self):
        self.find_bar_widget.setVisible(True)
        self.lyric_search_input.setFocus()
        self.lyric_search_input.selectAll()

    def _on_escape_pressed(self):
        if self.find_bar_widget.isVisible():
            self.clear_lyric_search()

    def perform_lyric_search(self, query: str, auto_jump: bool = True):
        q = query.strip()
        self.search_matches = []
        self.current_search_idx = -1

        if not q:
            self.lyric_editor.set_search_spans([])
            self.search_count_lbl.setText("0 / 0")
            return

        text = self.lyric_editor.toPlainText()
        for m in re.finditer(re.escape(q), text, flags=re.IGNORECASE):
            self.search_matches.append((m.start(), m.end()))

        self.lyric_editor.set_search_spans(self.search_matches)
        if self.search_matches:
            self.current_search_idx = 0
            self.search_count_lbl.setText(f"1 / {len(self.search_matches)}")
            if auto_jump:
                self._jump_to_match(0)
        else:
            self.search_count_lbl.setText("0 / 0")

    def _jump_to_match(self, idx: int):
        if not self.search_matches:
            return
        start, end = self.search_matches[idx]
        cur = self.lyric_editor.textCursor()
        cur.setPosition(start)
        cur.setPosition(end, QTextCursor.KeepAnchor)
        self.lyric_editor.setTextCursor(cur)
        self.lyric_editor.ensureCursorVisible()
        self.search_count_lbl.setText(f"{idx + 1} / {len(self.search_matches)}")

    def next_search_match(self):
        if not self.search_matches:
            return
        self.current_search_idx = (self.current_search_idx + 1) % len(self.search_matches)
        self._jump_to_match(self.current_search_idx)

    def prev_search_match(self):
        if not self.search_matches:
            return
        self.current_search_idx = (self.current_search_idx - 1) % len(self.search_matches)
        self._jump_to_match(self.current_search_idx)

    def clear_lyric_search(self):
        self.lyric_search_input.clear()
        self.search_matches = []
        self.current_search_idx = -1
        self.lyric_editor.set_search_spans([])
        self.search_count_lbl.setText("0 / 0")
        self.find_bar_widget.setVisible(False)
        self.lyric_editor.setFocus()

    # --- ZERO-LATENCY CLICK & LOCKED AUTO-SYNC METRONOME ---
    def _build_click_wav_file(self, filepath: str, freq_hz: float, duration_ms: int = 24):
        sample_rate = 44100
        num_samples = int(sample_rate * (duration_ms / 1000.0))
        with wave.open(filepath, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            frames = bytearray()
            for i in range(num_samples):
                t = i / sample_rate
                env = math.exp(-t * 150.0)
                val = math.sin(2.0 * math.pi * freq_hz * t) * env
                sample = max(-32767, min(32767, int(val * 30000)))
                frames.extend(struct.pack("<h", sample))
            wf.writeframes(bytes(frames))

    def _init_zero_latency_clicks(self):
        tmp_dir = tempfile.gettempdir()
        self._hi_wav = os.path.join(tmp_dir, "nocturne_metro_hi_v2.wav")
        self._lo_wav = os.path.join(tmp_dir, "nocturne_metro_lo_v2.wav")

        try:
            self._build_click_wav_file(self._hi_wav, 1320.0, 28)
            self._build_click_wav_file(self._lo_wav, 880.0, 24)
        except Exception:
            pass

        self._hi_wav_bytes = None
        self._lo_wav_bytes = None
        for attr, path in (("_hi_wav_bytes", self._hi_wav), ("_lo_wav_bytes", self._lo_wav)):
            if path and os.path.exists(path):
                try:
                    with open(path, "rb") as wf:
                        setattr(self, attr, wf.read())
                except Exception:
                    pass

        self._hi_pool = []
        self._lo_pool = []
        self._hi_pool_idx = 0
        self._lo_pool_idx = 0
        self._use_winsound_fast = (
            os.name == "nt" and bool(self._hi_wav_bytes) and bool(self._lo_wav_bytes)
        )

        if not self._use_winsound_fast:
            for _ in range(4):
                sfx_hi = QSoundEffect(self)
                sfx_hi.setSource(QUrl.fromLocalFile(self._hi_wav))
                sfx_hi.setLoopCount(1)
                sfx_hi.setVolume(0.90)
                self._hi_pool.append(sfx_hi)

                sfx_lo = QSoundEffect(self)
                sfx_lo.setSource(QUrl.fromLocalFile(self._lo_wav))
                sfx_lo.setLoopCount(1)
                sfx_lo.setVolume(0.75)
                self._lo_pool.append(sfx_lo)

    def _play_metro_click(self, is_downbeat: bool):
        if getattr(self, "_use_winsound_fast", False):
            raw_bytes = self._hi_wav_bytes if is_downbeat else self._lo_wav_bytes
            if raw_bytes:
                try:
                    import winsound
                    winsound.PlaySound(
                        raw_bytes,
                        winsound.SND_MEMORY | winsound.SND_ASYNC | winsound.SND_NODEFAULT
                    )
                    return
                except Exception:
                    pass

        pool = self._hi_pool if is_downbeat else self._lo_pool
        wav_path = self._hi_wav if is_downbeat else self._lo_wav
        played_via_qt = False

        if pool:
            idx = self._hi_pool_idx if is_downbeat else self._lo_pool_idx
            sfx = pool[idx % len(pool)]
            if is_downbeat:
                self._hi_pool_idx = (idx + 1) % len(pool)
            else:
                self._lo_pool_idx = (idx + 1) % len(pool)

            if sfx.status() == QSoundEffect.Ready:
                if sfx.isPlaying():
                    sfx.stop()
                sfx.play()
                played_via_qt = True

        if not played_via_qt and os.name == "nt" and wav_path and os.path.exists(wav_path):
            try:
                import winsound
                winsound.PlaySound(
                    wav_path,
                    winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
                )
            except Exception:
                pass

    def _reset_auto_clock(self, start_perf: float | None = None, base_ms: float = 0.0):
        """Locks the master beat clock onto perf_counter immediately from base_ms (default 0 ms)."""
        self._auto_clock_start_perf = time.perf_counter() if start_perf is None else start_perf
        self._auto_clock_base_ms = float(base_ms)
        self._last_raw_player_pos_ms = int(base_ms)
        self._last_synced_beat_idx = -1

    def _clear_auto_clock(self):
        self._auto_clock_start_perf = None
        self._auto_clock_base_ms = 0.0
        self._last_raw_player_pos_ms = 0
        self._last_synced_beat_idx = -1

    def _get_current_track_pos_ms(self, now_perf: float | None = None) -> float:
        """Returns smooth, drift-free playback position in ms without jumping on telemetry jitter."""
        if now_perf is None:
            now_perf = time.perf_counter()
        if self._auto_clock_start_perf is None:
            raw_pos = float(max(0, self.player.position()))
            self._reset_auto_clock(start_perf=now_perf, base_ms=raw_pos)
            return raw_pos
        return self._auto_clock_base_ms + (now_perf - self._auto_clock_start_perf) * 1000.0

    def _on_player_position_changed(self, pos_ms: int):
        """Re-anchors master clock when hardware audio starts, loops, or seeks."""
        if not self.is_playing or not self.beat_path:
            return
        if self._auto_clock_start_perf is None or pos_ms < 0:
            return

        now_perf = time.perf_counter()
        expected_pos_ms = self._auto_clock_base_ms + (now_perf - self._auto_clock_start_perf) * 1000.0
        prev_raw = self._last_raw_player_pos_ms

        started_output = (prev_raw == 0 and pos_ms > 0)
        wrapped_loop = (pos_ms + 250) < prev_raw
        jumped_seek = abs(float(pos_ms) - expected_pos_ms) > 350.0 and pos_ms > 50

        if started_output or wrapped_loop or jumped_seek:
            self._reset_auto_clock(start_perf=now_perf, base_ms=float(pos_ms))

        self._last_raw_player_pos_ms = pos_ms

    def _on_player_state_changed(self, state):
        if state == QMediaPlayer.StoppedState and not self.is_playing:
            self._clear_auto_clock()

    def _start_waveform_beat_analysis(self, path: str):
        if not path or not os.path.exists(path):
            return
        self.detected_bpm = None
        self.detected_beat_times_ms = []
        self.auto_beat_grid_active = False

        old_worker = self._beat_analyzer_worker
        if old_worker is not None:
            try:
                if old_worker.isRunning():
                    old_worker.analysis_ready.disconnect()
                    old_worker.analysis_failed.disconnect()
            except RuntimeError:
                pass
            except Exception:
                pass
            self._beat_analyzer_worker = None

        self.beat_label.setText(f"🎵 {os.path.basename(path)}  (Analyzing waveform...)")
        worker = BeatWaveformAnalyzerWorker(path)
        worker.analysis_ready.connect(self._on_waveform_analysis_ready)
        worker.analysis_failed.connect(self._on_waveform_analysis_failed)

        self._active_workers.append(worker)
        worker.finished.connect(lambda w=worker: self._cleanup_worker(w))

        self._beat_analyzer_worker = worker
        worker.start()

    def _cleanup_worker(self, worker):
        if self._beat_analyzer_worker is worker:
            self._beat_analyzer_worker = None
        if worker in self._active_workers:
            self._active_workers.remove(worker)
        try:
            worker.deleteLater()
        except RuntimeError:
            pass

    def _on_waveform_analysis_ready(self, path: str, bpm_val: float, beat_times_ms: list):
        if path != self.beat_path:
            return
        self.detected_bpm = float(bpm_val)
        self.detected_beat_times_ms = list(beat_times_ms)
        self.auto_beat_grid_active = len(self.detected_beat_times_ms) >= 4
        if self.auto_beat_grid_active:
            self.beat_sync_offset_ms = float(self.detected_beat_times_ms[0])

        rounded_bpm = max(40, min(260, round(self.detected_bpm)))
        self.beat_label.setText(f"🎵 {os.path.basename(path)}  [{rounded_bpm} BPM]")

        if getattr(self, "metro_mode", "OFF") == "AUTO":
            self._apply_detected_waveform_tempo(rounded_bpm)
            if self.is_playing:
                self._start_precision_metro_clock(lock_from_zero=False)

    def _on_waveform_analysis_failed(self, path: str, _err: str):
        if path != self.beat_path:
            return
        self.detected_bpm = None
        self.detected_beat_times_ms = []
        self.auto_beat_grid_active = False
        self.beat_label.setText(f"🎵 {os.path.basename(path)}")

    def _apply_detected_waveform_tempo(self, bpm_int: int):
        self._updating_bpm_from_auto = True
        try:
            self.bpm_spin.setValue(bpm_int)
            self.metronome.set_bpm(bpm_int)
        finally:
            self._updating_bpm_from_auto = False
        self._last_synced_beat_idx = -1

    def anchor_downbeat_now(self):
        """Manual 1! override: immediately fires Beat 1 and stores exact downbeat offset without corrupting player clock."""
        now_perf = time.perf_counter()
        if self.is_playing and self.beat_path:
            smooth_pos_ms = self._get_current_track_pos_ms(now_perf)
            self.beat_sync_offset_ms = smooth_pos_ms
            self.auto_beat_grid_active = False
            self._last_synced_beat_idx = -1
            if getattr(self, "metro_mode", "OFF") == "OFF":
                self._set_metro_mode("ON")
        else:
            self._standalone_metro_start = now_perf
            self._last_synced_beat_idx = -1

        self._advance_clock_to(now_perf, force_beat_zero=True)

    def _start_precision_metro_clock(self, lock_from_zero: bool = True):
        self.metronome.stop()
        now_perf = time.perf_counter()
        if lock_from_zero and not (self.is_playing and self.beat_path and self._auto_clock_start_perf is not None):
            raw_pos = float(max(0, self.player.position())) if (self.is_playing and self.beat_path) else 0.0
            self._reset_auto_clock(start_perf=now_perf, base_ms=raw_pos)
        self._standalone_metro_start = now_perf
        self._last_synced_beat_idx = -1
        if not self.metro_sync_timer.isActive():
            self.metro_sync_timer.start()
        self._poll_metronome_master_clock(now_perf=now_perf)

    def _stop_precision_metro_clock(self):
        self.metronome.stop()
        if self.metro_sync_timer.isActive():
            self.metro_sync_timer.stop()
        if not self.is_playing:
            self._clear_auto_clock()
        self._last_synced_beat_idx = -1
        self.on_metronome_tick(0)

    def _advance_clock_to(self, now_perf: float, force_beat_zero: bool = False):
        mode = getattr(self, "metro_mode", "OFF")
        beats_per_bar = self.metro_sig_combo.currentData() or 4

        if self.is_playing and self.beat_path:
            smooth_pos_ms = self._get_current_track_pos_ms(now_perf)

            # In AUTO mode with detected waveform beat grid, lock directly onto waveform beats
            if mode == "AUTO" and self.auto_beat_grid_active and len(self.detected_beat_times_ms) >= 4:
                grid = self.detected_beat_times_ms
                if smooth_pos_ms < grid[0] and not force_beat_zero:
                    return
                idx = 0 if force_beat_zero else max(0, bisect.bisect_right(grid, smooth_pos_ms) - 1)
                beat_idx = idx

                # Dynamically update BPM readout if local waveform spacing shifts (e.g. tempo switch)
                if 0 <= idx < len(grid) - 1:
                    local_dt = grid[idx + 1] - grid[idx]
                    if 220.0 < local_dt < 1500.0:
                        inst_bpm = max(40, min(260, round(60000.0 / local_dt)))
                        if abs(inst_bpm - self.bpm_spin.value()) >= 1:
                            self._updating_bpm_from_auto = True
                            try:
                                self.bpm_spin.setValue(inst_bpm)
                                self.metronome.set_bpm(inst_bpm)
                            finally:
                                self._updating_bpm_from_auto = False
            else:
                bpm = max(40, self.bpm_spin.value())
                beat_ms = 60000.0 / bpm
                if smooth_pos_ms < float(self.beat_sync_offset_ms) and not force_beat_zero:
                    return
                rel_ms = max(0.0, smooth_pos_ms - float(self.beat_sync_offset_ms))
                beat_idx = 0 if force_beat_zero else int(rel_ms // beat_ms)
        else:
            bpm = max(40, self.bpm_spin.value())
            beat_ms = 60000.0 / bpm
            elapsed_ms = max(0.0, (now_perf - self._standalone_metro_start) * 1000.0)
            beat_idx = 0 if force_beat_zero else int(elapsed_ms // beat_ms)

        if beat_idx != self._last_synced_beat_idx:
            self._last_synced_beat_idx = beat_idx
            beat_in_bar = (beat_idx % beats_per_bar) + 1
            self._play_metro_click(is_downbeat=(beat_in_bar == 1))
            self.on_metronome_tick(beat_in_bar)

    def _poll_metronome_master_clock(self, now_perf: float | None = None):
        mode = getattr(self, "metro_mode", "OFF")
        if mode == "OFF":
            self._stop_precision_metro_clock()
            return

        if now_perf is None:
            now_perf = time.perf_counter()

        if self.is_playing and self.beat_path:
            self._advance_clock_to(now_perf)
        else:
            if mode == "AUTO":
                self.on_metronome_tick(0)
                return
            self._advance_clock_to(now_perf)

    def on_tap_tempo(self):
        now = time.monotonic()
        if self._tap_timestamps and (now - self._tap_timestamps[-1]) > 2.0:
            self._tap_timestamps.clear()

        self._tap_timestamps.append(now)
        if len(self._tap_timestamps) > 8:
            self._tap_timestamps = self._tap_timestamps[-8:]

        self.btn_tap_bpm.setText("●")
        QTimer.singleShot(110, lambda: self.btn_tap_bpm.setText("TAP"))

        if len(self._tap_timestamps) >= 2:
            intervals = [
                self._tap_timestamps[i] - self._tap_timestamps[i - 1]
                for i in range(1, len(self._tap_timestamps))
            ]
            avg_sec = sum(intervals) / len(intervals)
            if avg_sec > 0:
                tapped_bpm = max(40, min(260, round(60.0 / avg_sec)))
                self.auto_beat_grid_active = False
                self.bpm_spin.setValue(tapped_bpm)

    def _on_bpm_spin_changed(self, bpm: int):
        self.metronome.set_bpm(bpm)
        if getattr(self, "_updating_bpm_from_auto", False):
            return

        # Manual BPM override switches off waveform grid lock and re-anchors phase smoothly from current playhead
        self.auto_beat_grid_active = False
        perf_now = time.perf_counter()
        if self.is_playing and self.beat_path:
            smooth_pos_ms = self._get_current_track_pos_ms(perf_now)
            self.beat_sync_offset_ms = smooth_pos_ms
            self._last_synced_beat_idx = -1
        else:
            self._standalone_metro_start = perf_now
            self._last_synced_beat_idx = -1

    def toggle_metronome(self):
        cur = getattr(self, "metro_mode", "OFF")
        if cur == "OFF":
            self._set_metro_mode("ON")
        elif cur == "ON":
            if self.beat_path:
                self._set_metro_mode("AUTO")
            else:
                self._set_metro_mode("OFF")
        else:
            self._set_metro_mode("OFF")

    def _set_metro_mode(self, mode: str):
        self.metro_mode = mode
        if mode == "OFF":
            self.btn_metro.setChecked(False)
            self.btn_metro.setText("⏱ Metro: OFF")
            self.btn_metro.setStyleSheet("""
                QPushButton {
                    background-color: #181820;
                    border: 1px solid #323240;
                    color: #F4F4F5;
                    padding: 3px 4px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #261938;
                    border-color: #A855F7;
                    color: #FFFFFF;
                }
            """)
            self._stop_precision_metro_clock()
        elif mode == "ON":
            self.btn_metro.setChecked(True)
            self.btn_metro.setText("🟠 Metro: ON")
            self.btn_metro.setStyleSheet("""
                QPushButton {
                    background-color: #2A1F0D;
                    border: 1px solid #F59E0B;
                    color: #FCD34D;
                    padding: 3px 4px;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #382911;
                    border-color: #FBBF24;
                    color: #FFFFFF;
                }
            """)
            self._start_precision_metro_clock(lock_from_zero=True)
        elif mode == "AUTO":
            self.btn_metro.setChecked(True)
            self.btn_metro.setText("🔵 Metro: AUTO")
            self.btn_metro.setStyleSheet("""
                QPushButton {
                    background-color: #0E2433;
                    border: 1px solid #06B6D4;
                    color: #67E8F9;
                    padding: 3px 4px;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #133145;
                    border-color: #22D3EE;
                    color: #FFFFFF;
                }
            """)
            if self.detected_bpm is not None and len(self.detected_beat_times_ms) >= 4:
                self.auto_beat_grid_active = True
                self.beat_sync_offset_ms = float(self.detected_beat_times_ms[0])
                self._apply_detected_waveform_tempo(max(40, min(260, round(self.detected_bpm))))
            if self.is_playing:
                self._start_precision_metro_clock(lock_from_zero=False)
            else:
                self._stop_precision_metro_clock()

    def _update_beat_button_state(self):
        if not hasattr(self, "btn_load_beat"):
            return
        if self.beat_path:
            self.btn_load_beat.setText("Unload Beat")
            self.btn_load_beat.setStyleSheet("""
                QPushButton {
                    background-color: #24131B;
                    border: 1px solid #7F1D1D;
                    color: #FCA5A5;
                    padding: 4px 6px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #450A0A;
                    border-color: #EF4444;
                    color: #FFFFFF;
                }
            """)
        else:
            self.btn_load_beat.setText("Load Beat")
            self.btn_load_beat.setStyleSheet("padding: 4px 6px; font-size: 11px;")

    def _update_play_button_state(self):
        if not hasattr(self, "btn_play_beat"):
            return
        if self.is_playing:
            self.btn_play_beat.setText("⏹ Stop")
            self.btn_play_beat.setStyleSheet("""
                QPushButton {
                    background-color: #7F1D1D;
                    border: 1px solid #EF4444;
                    color: #FFFFFF;
                    padding: 4px 6px;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #991B1B;
                    border-color: #FCA5A5;
                    color: #FFFFFF;
                }
            """)
        else:
            self.btn_play_beat.setText("▶ Play")
            self.btn_play_beat.setStyleSheet("""
                QPushButton {
                    background-color: #7E22CE;
                    border: 1px solid #B066FF;
                    color: #FFFFFF;
                    padding: 4px 6px;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #9333EA;
                    border-color: #D8B4FE;
                    color: #FFFFFF;
                }
            """)

    def _update_loop_button_state(self):
        if not hasattr(self, "btn_loop"):
            return
        if self.is_looping:
            self.btn_loop.setText("🔁 Loop: ON")
            self.btn_loop.setStyleSheet("""
                QPushButton {
                    background-color: #581C87;
                    border: 1px solid #C084FC;
                    color: #F3E8FF;
                    padding: 4px 6px;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #6B21A8;
                    border-color: #E9D5FF;
                    color: #FFFFFF;
                }
            """)
        else:
            self.btn_loop.setText("🔁 Loop: OFF")
            self.btn_loop.setStyleSheet("""
                QPushButton {
                    background-color: #181820;
                    border: 1px solid #323240;
                    color: #A1A1AA;
                    padding: 4px 6px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #261938;
                    border-color: #A855F7;
                    color: #FFFFFF;
                }
            """)
        
    def on_load_or_unload_beat_clicked(self):
        if self.beat_path:
            self.unload_beat()
        else:
            self.load_beat_file()

# --- SEEKBAR & TIMESTAMP MARKERS ---
    def _format_time_ms(self, ms: int) -> str:
        sec = max(0, int(ms // 1000))
        return f"{sec // 60:02d}:{sec % 60:02d}"

    def _on_player_duration_changed(self, duration_ms: int):
        self.beat_duration_ms = max(0, int(duration_ms))
        if hasattr(self, "beat_seekbar"):
            self.beat_seekbar.set_duration(self.beat_duration_ms)
        self._update_seekbar_ui()

    def _get_live_playback_ms(self) -> int:
        if not self.beat_path:
            return 0
        if self.is_playing:
            pos = int(max(0.0, self._get_current_track_pos_ms()))
            if self.beat_duration_ms > 0:
                pos = min(pos, self.beat_duration_ms)
            return pos
        return max(0, int(self.player.position()))

    def _update_seekbar_ui(self):
        if not hasattr(self, "beat_seekbar") or self._is_scrubbing_seekbar:
            return
        cur_ms = self._get_live_playback_ms()
        dur_ms = self.beat_duration_ms
        self.beat_seekbar.set_position(cur_ms)
        self.lbl_beat_time.setText(f"{self._format_time_ms(cur_ms)} / {self._format_time_ms(dur_ms)}")

    def _on_seek_scrub_started(self):
        self._is_scrubbing_seekbar = True

    def _on_seek_requested(self, target_ms: int):
        if not self.beat_path:
            return
        clamped = max(0, min(target_ms, self.beat_duration_ms or target_ms))
        self.lbl_beat_time.setText(f"{self._format_time_ms(clamped)} / {self._format_time_ms(self.beat_duration_ms)}")
        self.player.setPosition(clamped)
        if self.is_playing:
            self._reset_auto_clock(start_perf=time.perf_counter(), base_ms=float(clamped))

    def _on_seek_scrub_finished(self, target_ms: int):
        self._is_scrubbing_seekbar = False
        self._on_seek_requested(target_ms)

    def jump_to_beat_timestamp_ms(self, target_ms: int, auto_play: bool = True):
        """Jumps directly to target_ms on the loaded beat and keeps metronome synced."""
        if not self.beat_path:
            QMessageBox.information(self, "No Beat", "Load a beat first to jump to timestamps.")
            return
        clamped = max(0, min(int(target_ms), self.beat_duration_ms or int(target_ms)))
        if not self.is_playing and auto_play:
            if self.auto_beat_grid_active and self.detected_beat_times_ms:
                self.beat_sync_offset_ms = float(self.detected_beat_times_ms[0])
            self._reset_auto_clock(start_perf=time.perf_counter(), base_ms=float(clamped))
            self.player.setLoops(QMediaPlayer.Infinite if self.is_looping else 1)
            self.player.setPosition(clamped)
            self.player.play()
            self.is_playing = True
            self._update_play_button_state()
            if getattr(self, "metro_mode", "OFF") in ("ON", "AUTO"):
                self._start_precision_metro_clock(lock_from_zero=False)
        else:
            self.player.setPosition(clamped)
            if self.is_playing:
                self._reset_auto_clock(start_perf=time.perf_counter(), base_ms=float(clamped))
        self.beat_seekbar.set_position(clamped)
        self.lbl_beat_time.setText(f"{self._format_time_ms(clamped)} / {self._format_time_ms(self.beat_duration_ms)}")

    def _guess_current_section_label(self) -> str:
        """Reads nearest [Header] above cursor in lyric editor for smart marker naming."""
        cur_block = self.lyric_editor.textCursor().block()
        probe = cur_block
        while probe.isValid():
            txt = probe.text().strip()
            if txt.startswith("[") and txt.endswith("]") and not re.match(r"^\[\d{1,2}:\d{2}\]$", txt):
                clean = txt.strip("[]").strip()
                if clean:
                    return clean[:24]
            probe = probe.previous()
        return f"Marker {len(self.beat_markers) + 1}"

    def add_marker_at_current_time(self):
        if not self.beat_path:
            QMessageBox.information(self, "No Beat", "Load a beat first before pinning markers.")
            return
        cur_ms = self._get_live_playback_ms()
        default_lbl = self._guess_current_section_label()
        label, ok = QInputDialog.getText(
            self,
            "Pin Beat Timestamp Marker",
            f"Label for {self._format_time_ms(cur_ms)} (e.g. Hook, Verse 1, Drop):",
            text=default_lbl,
        )
        if not ok:
            return
        clean_lbl = label.strip() or default_lbl
        # Replace existing marker within 500ms if re-pinning same spot
        self.beat_markers = [m for m in self.beat_markers if abs(m["time_ms"] - cur_ms) > 500]
        self.beat_markers.append({"time_ms": int(cur_ms), "label": clean_lbl})
        self.beat_markers.sort(key=lambda m: m["time_ms"])
        self._refresh_markers_ui()
        self.save_track()

    def stamp_timestamp_on_current_line(self):
        """Inserts or replaces [MM:SS] at the start of the active lyric line."""
        if not self.beat_path:
            QMessageBox.information(self, "No Beat", "Load a beat first to stamp timestamps.")
            return
        cur_ms = self._get_live_playback_ms()
        tag = f"[{self._format_time_ms(cur_ms)}]"

        cur = self.lyric_editor.textCursor()
        block = cur.block()
        line_txt = block.text()

        # Replace leading [MM:SS] if line already has one, else prepend
        existing = re.match(r"^(\s*)\[\d{1,2}:\d{2}\]\s*", line_txt)
        edit_cur = QTextCursor(block)
        if existing:
            edit_cur.setPosition(block.position() + len(existing.group(1)))
            edit_cur.setPosition(block.position() + existing.end(), QTextCursor.KeepAnchor)
            edit_cur.insertText(f"{tag} ")
        else:
            edit_cur.setPosition(block.position())
            edit_cur.insertText(f"{tag} ")
        self.lyric_editor.setFocus()

    def _refresh_markers_ui(self):
        if hasattr(self, "beat_seekbar"):
            self.beat_seekbar.set_markers(self.beat_markers)
        if not hasattr(self, "marker_combo"):
            return
        self.marker_combo.blockSignals(True)
        self.marker_combo.clear()
        if not self.beat_markers:
            self.marker_combo.addItem("No markers pinned", None)
        else:
            for idx, m in enumerate(self.beat_markers):
                self.marker_combo.addItem(
                    f"📍 {self._format_time_ms(m['time_ms'])} • {m['label']}",
                    idx,
                )
        self.marker_combo.blockSignals(False)

    def _on_marker_combo_selected(self, combo_idx: int):
        marker_idx = self.marker_combo.itemData(combo_idx)
        if isinstance(marker_idx, int) and 0 <= marker_idx < len(self.beat_markers):
            self.jump_to_beat_timestamp_ms(self.beat_markers[marker_idx]["time_ms"], auto_play=True)

    def _show_marker_context_menu(self, pos):
        if not self.beat_markers:
            return
        combo_idx = self.marker_combo.currentIndex()
        marker_idx = self.marker_combo.itemData(combo_idx)
        if not isinstance(marker_idx, int) or not (0 <= marker_idx < len(self.beat_markers)):
            return

        m = self.beat_markers[marker_idx]
        menu = QMenu(self)
        act_jump = QAction(f"▶ Jump to {self._format_time_ms(m['time_ms'])} ({m['label']})", self)
        act_jump.triggered.connect(lambda: self.jump_to_beat_timestamp_ms(m["time_ms"], auto_play=True))
        menu.addAction(act_jump)

        act_rename = QAction("✏ Rename Marker...", self)
        act_rename.triggered.connect(lambda: self._rename_marker(marker_idx))
        menu.addAction(act_rename)

        act_del = QAction("🗑 Delete Marker", self)
        act_del.triggered.connect(lambda: self._delete_marker(marker_idx))
        menu.addAction(act_del)

        act_clear = QAction("Clear All Markers", self)
        act_clear.triggered.connect(self._clear_all_markers)
        menu.addAction(act_clear)

        menu.exec(self.marker_combo.mapToGlobal(pos))

    def _rename_marker(self, idx: int):
        if not (0 <= idx < len(self.beat_markers)):
            return
        cur_lbl = self.beat_markers[idx]["label"]
        new_lbl, ok = QInputDialog.getText(self, "Rename Marker", "Marker name:", text=cur_lbl)
        if ok and new_lbl.strip():
            self.beat_markers[idx]["label"] = new_lbl.strip()
            self._refresh_markers_ui()
            self.save_track()

    def _delete_marker(self, idx: int):
        if 0 <= idx < len(self.beat_markers):
            self.beat_markers.pop(idx)
            self._refresh_markers_ui()
            self.save_track()

    def _clear_all_markers(self):
        self.beat_markers = []
        self._refresh_markers_ui()
        self.save_track()

    def load_beat_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Beat File", "", "Audio Files (*.mp3 *.wav *.flac *.ogg *.m4a)"
        )
        if path:
            if self.is_playing:
                self.player.stop()
                self.is_playing = False
                self._clear_auto_clock()
                self._update_play_button_state()
            self.beat_path = path
            self.beat_duration_ms = 0
            self.beat_markers = []
            self.beat_sync_offset_ms = 0.0
            if hasattr(self, "beat_seekbar"):
                self.beat_seekbar.set_duration(0)
                self.beat_seekbar.set_position(0)
                self.lbl_beat_time.setText("00:00 / 00:00")
            self._refresh_markers_ui()
            self.player.setSource(QUrl.fromLocalFile(path))
            self._update_beat_button_state()
            self._start_waveform_beat_analysis(path)
            if getattr(self, "metro_mode", "OFF") == "OFF":
                self._set_metro_mode("AUTO")
            self.save_track()

    def unload_beat(self):
        self.player.stop()
        self.player.setSource(QUrl())
        self.is_playing = False
        self.beat_path = None
        self.beat_duration_ms = 0
        self.beat_markers = []
        self.beat_sync_offset_ms = 0.0
        self.detected_bpm = None
        self.detected_beat_times_ms = []
        self.auto_beat_grid_active = False
        self._clear_auto_clock()
        if hasattr(self, "beat_seekbar"):
            self.beat_seekbar.set_duration(0)
            self.beat_seekbar.set_position(0)
            self.lbl_beat_time.setText("00:00 / 00:00")
        self._refresh_markers_ui()
        self._update_play_button_state()
        self.beat_label.setText("No beat loaded (.mp3 / .wav / .flac)")
        self._update_beat_button_state()
        if getattr(self, "metro_mode", "OFF") == "AUTO":
            self._set_metro_mode("OFF")
        else:
            self._last_synced_beat_idx = -1
        self.save_track()

    def toggle_beat_playback(self):
        if not self.beat_path:
            QMessageBox.information(self, "No Beat", "Load an .mp3 or .wav beat first.")
            return
        if not self.is_playing:
            if self.auto_beat_grid_active and self.detected_beat_times_ms:
                self.beat_sync_offset_ms = float(self.detected_beat_times_ms[0])
            self._reset_auto_clock(start_perf=time.perf_counter(), base_ms=0.0)
            self.player.setLoops(QMediaPlayer.Infinite if self.is_looping else 1)
            self.player.setPosition(0)
            self.player.play()
            self.is_playing = True
            self._update_play_button_state()
            if getattr(self, "metro_mode", "OFF") in ("ON", "AUTO"):
                self._start_precision_metro_clock(lock_from_zero=False)
        else:
            self.player.stop()
            self.player.setPosition(0)
            self.is_playing = False
            self._clear_auto_clock()
            self._update_play_button_state()
            if getattr(self, "metro_mode", "OFF") == "AUTO":
                self._stop_precision_metro_clock()
            else:
                self._standalone_metro_start = time.perf_counter()
                self._last_synced_beat_idx = -1

    def on_metro_sig_changed(self):
        beats = self.metro_sig_combo.currentData() or 4
        self.metronome.set_beats_per_bar(beats)
        self._last_synced_beat_idx = -1

    def on_metronome_tick(self, beat_num: int):
        off_style = "background-color: #2E2E3D; border: 1px solid #3F3F4E; border-radius: 4px; padding: 0px;"
        beat1_style = "background-color: #C084FC; border: 1px solid #F3E8FF; border-radius: 4px; padding: 0px;"
        sub_style = "background-color: #38BDF8; border: 1px solid #BAE6FD; border-radius: 4px; padding: 0px;"

        for idx, led in enumerate(self.metro_leds):
            if beat_num == 0:
                led.setStyleSheet(off_style)
            elif (idx + 1) == ((beat_num - 1) % 4) + 1:
                led.setStyleSheet(beat1_style if beat_num == 1 else sub_style)
            else:
                led.setStyleSheet(off_style)

    # --- SETTINGS & FONT SLIDER ---
    def on_font_slider_changed(self, size: int):
        clamped = max(11, int(size))
        self.font_size_label.setText(f"{clamped}pt")
        self.studio_settings["font_size"] = clamped
        self.lyric_editor.set_editor_font_size(clamped)
        self.save_profile_settings()

    def apply_studio_settings(self, new_cfg: dict, is_initial_load: bool = False):
        old_cfg = dict(self.studio_settings)
        self.studio_settings = dict(new_cfg)
        self.save_profile_settings()

        f_family = self.studio_settings.get("font_family", "SF Pro")
        f_bold = " Bold" if self.studio_settings.get("font_bold", True) else ""
        self.font_tag_lbl.setToolTip(f"Active Font: {f_family}{f_bold}")

        f_size = max(11, int(self.studio_settings.get("font_size", 15) or 15))
        self.font_slider.blockSignals(True)
        self.font_slider.setValue(f_size)
        self.font_slider.blockSignals(False)
        self.font_size_label.setText(f"{f_size}pt")

        self.lyric_editor.apply_settings(self.studio_settings)

        

        if is_initial_load or self.studio_settings.get("default_bpm", 140) != old_cfg.get("default_bpm", 140):
            self.bpm_spin.setValue(self.studio_settings.get("default_bpm", 140))

        if is_initial_load or self.studio_settings.get("default_volume", 80) != old_cfg.get("default_volume", 80):
            self.vol_slider.setValue(self.studio_settings.get("default_volume", 80))

        as_sec = self.studio_settings.get("autosave_seconds", 0)
        if as_sec > 0:
            self.autosave_timer.start(as_sec * 1000)
        else:
            self.autosave_timer.stop()

    def open_studio_settings(self):
        dlg = NocturneSettingsDialog(
            self,
            current_settings=self.studio_settings,
            vault_dir=self.vault_dir,
            on_apply_callback=self.apply_studio_settings
        )
        dlg.exec()

    def load_profile_settings(self):
        loaded = dict(DEFAULT_STUDIO_SETTINGS)
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    loaded.update(json.load(f))
            except Exception:
                pass
        self.apply_studio_settings(loaded, is_initial_load=True)

    def save_profile_settings(self):
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(self.studio_settings, f, indent=2)
        except Exception:
            pass

    # --- PROFILE SETTINGS & SWITCHING ---
    def open_active_profile_settings(self):
        profiles = [
            d for d in os.listdir(self.profiles_root)
            if os.path.isdir(os.path.join(self.profiles_root, d))
        ]
        dlg = ProfileSettingsDialog(
            self,
            profiles_root=self.profiles_root,
            profile_name=self.profile_name,
            can_delete=(len(profiles) > 1)
        )
        dlg.exec()

        if dlg.was_deleted:
            self.trigger_profile_switch()
            return

        if dlg.new_profile_name != self.profile_name:
            self.profile_name = dlg.new_profile_name
            self.profile_dir = os.path.join(self.profiles_root, self.profile_name)
            self.vault_dir = os.path.join(self.profile_dir, "tracks_vault")
            self.trash_dir = os.path.join(self.profile_dir, "tracks_trash")
            os.makedirs(self.trash_dir, exist_ok=True)
            self.settings_file = os.path.join(self.profile_dir, "settings.json")
            LEXICON.load_profile(self.profile_dir)

            cur_title = self.track_title_input.text().strip() or "Untitled_Track_01"
            self.setWindowTitle(f"nocturne | {self.profile_name} — {cur_title}")
            self.btn_profile_cfg.setText(f"👤 {self.profile_name}")
            self.vault_header_lbl.setText(f"VAULT // {self.profile_name.upper()}")
            self.load_vault_list()

    def trigger_profile_switch(self):
        if getattr(self, "realtime_vault_timer", None) and self.realtime_vault_timer.isActive():
            self.realtime_vault_timer.stop()
            self.save_track()
        self.player.stop()
        self._stop_precision_metro_clock()
        self.autosave_timer.stop()
        self.save_profile_settings()
        self.switch_requested = True
        self.close()
        self.on_switch_profile()

    # --- LEXICON & SLANG ACTIONS ---
    def open_lexicon_manager(self):
        dlg = LexiconManagerDialog(self, on_updated_callback=self.lyric_editor.run_analysis)
        dlg.exec()

    def quick_add_slang_word(self, word: str):
        meaning, ok = QInputDialog.getText(
            self,
            "Add Custom Slang",
            f"Enter slang meaning or wordplay note for '{word}':"
        )
        if ok and meaning.strip():
            LEXICON.add_custom_slang(word, meaning.strip(), "CUSTOM SLANG")
            self.lyric_editor.run_analysis()
            self.lookup_rhyme_word(word)

    def set_word_pronunciation(self, word: str):
        clean = re.sub(r"^[^A-Za-z0-9']+|[^A-Za-z0-9']+$", "", word or "")
        if not clean:
            return
        current = LEXICON.pron_overrides.get(clean.lower(), {}).get("spec", "")
        spec, ok = QInputDialog.getText(
            self,
            "How do you say it?",
            f"How do you pronounce '{clean}'?\n\n"
            "Type a respelling or a word it sounds like (e.g.  nite  or  sounds like fight),\n"
            "or ARPAbet (e.g.  N AY1 T).  Leave empty to reset to the default.",
            text=current,
        )
        if not ok:
            return
        if not spec.strip():
            LEXICON.remove_pronunciation(clean)
        elif not LEXICON.set_pronunciation(clean, spec):
            QMessageBox.warning(self, "Pronunciation", f"Couldn't understand '{spec}'. Try a respelling like 'nite'.")
            return
        self.lyric_editor.run_analysis()
        self.lookup_rhyme_word(clean)

    # --- RHYME & ANALYSIS ---
    def update_stats_badges(self, result: dict):
        self.stat_rhymes.setText(f"RHYMES: {result['total_rhymes']}")
        self.sync_rhyme_dots(result.get("tokens", []))

    def toggle_rhyme_solo(self, group_idx: int | None):
        if group_idx is None:
            self.solo_rhyme_group = None
            self.solo_special_mode = None
            self.rhyme_badge.setText("Rhymes:")
            self.rhyme_badge.setStyleSheet("color: #B4B4BE; font-size: 11px; font-weight: 600;")
        elif self.solo_rhyme_group == group_idx and self.solo_special_mode is None:
            self.solo_rhyme_group = None
            self.rhyme_badge.setText("Rhymes:")
            self.rhyme_badge.setStyleSheet("color: #B4B4BE; font-size: 11px; font-weight: 600;")
        else:
            self.solo_special_mode = None
            self.solo_rhyme_group = group_idx
            self.rhyme_badge.setText(f"Solo G{group_idx + 1}:")
            self.rhyme_badge.setStyleSheet("color: #F3E8FF; font-size: 11px; font-weight: 800;")

        self.lyric_editor.solo_rhyme_group = self.solo_rhyme_group
        self.lyric_editor.solo_special_mode = self.solo_special_mode
        self.lyric_editor.apply_visual_highlights()
        self.sync_rhyme_dots(self.lyric_editor.token_map)

    

    def jump_to_rhyme_group(self, group_idx: int):
        tokens = self.lyric_editor.token_map
        matches = [
            t for t in tokens
            if t["rhyme_group"] is not None and t["color_idx"] == group_idx
        ]
        if not matches:
            return

        cur_pos = self.lyric_editor.textCursor().position()
        next_tok = next((t for t in matches if t["start"] > cur_pos), matches[0])

        cursor = self.lyric_editor.textCursor()
        cursor.setPosition(next_tok["start"])
        cursor.setPosition(next_tok["end"], QTextCursor.KeepAnchor)
        self.lyric_editor.setTextCursor(cursor)
        self.lyric_editor.ensureCursorVisible()
        self.lyric_editor.setFocus()

    def sync_rhyme_dots(self, tokens: list[dict]):
        if not hasattr(self, "rhyme_dots"):
            return
        any_rhyme_active = False

        for idx, dot in enumerate(self.rhyme_dots):
            grp_tokens = [
                t for t in tokens
                if t["rhyme_group"] is not None and t["color_idx"] == idx
            ]
            has_words = len(grp_tokens) > 0
            if has_words:
                any_rhyme_active = True

            # Jika warna yang sedang di-Solo sudah tiada dalam teks, matikan Solo secara automatik
            if not has_words and self.solo_rhyme_group == idx and self.solo_special_mode is None:
                self.solo_rhyme_group = None
                self.rhyme_badge.setText("Rhymes:")
                self.rhyme_badge.setStyleSheet("color: #B4B4BE; font-size: 11px; font-weight: 600;")
                self.lyric_editor.solo_rhyme_group = None
                self.lyric_editor.apply_visual_highlights()

            dot.setVisible(has_words)
            multie_cnt = sum(1 for t in grp_tokens if t.get("multie_count", 0) >= 2)
            samples = [t["word"] for t in grp_tokens]
            dot.update_state(
                word_count=len(grp_tokens),
                multie_count=multie_cnt,
                sample_words=samples,
                is_solo=(self.solo_rhyme_group == idx and self.solo_special_mode is None),
            )

        self.rhyme_badge.setVisible(any_rhyme_active)
        if hasattr(self, "rhyme_sep1"):
            self.rhyme_sep1.setVisible(any_rhyme_active)

    def on_editor_cursor_word_changed(self, word: str):
        if hasattr(self, "btn_live_rhyme") and self.btn_live_rhyme.isChecked():
            self.lookup_rhyme_word(word, from_live=True)

    def _find_rhyming_lines_in_editor(self, target_word: str, rhyme_data: dict) -> list[tuple[int, str, str]]:
        full_text = self.lyric_editor.toPlainText()
        if not full_text.strip():
            return []

        target_low = target_word.lower()
        candidate_words = {target_low}
        for key in ("perfect_en", "perfect_bm", "perfect_custom", "slant"):
            for raw_entry in rhyme_data.get(key, []):
                cleaned = re.sub(r"\s*\[.*?\]|\s*\(slang\)|\s*🔥", "", raw_entry).strip().lower()
                if cleaned:
                    candidate_words.add(cleaned)

        target_groups = set()
        for tok in self.lyric_editor.token_map:
            tok_txt = full_text[tok["start"]:tok["end"]].strip().lower()
            if tok_txt == target_low and tok.get("rhyme_group") is not None:
                target_groups.add(tok["rhyme_group"])

        for tok in self.lyric_editor.token_map:
            if tok.get("rhyme_group") in target_groups:
                tok_txt = full_text[tok["start"]:tok["end"]].strip().lower()
                if tok_txt:
                    candidate_words.add(tok_txt)

        vowel_tail_match = re.search(r"[aeiouy][a-z]*$", target_low)
        target_tail = vowel_tail_match.group(0) if vowel_tail_match and len(vowel_tail_match.group(0)) >= 2 else ""

        cur_line_idx = self.lyric_editor.textCursor().blockNumber()
        matched_lines = []

        for idx, line in enumerate(full_text.splitlines()):
            stripped = line.strip()
            if not stripped or (stripped.startswith("[") and stripped.endswith("]")):
                continue

            words_in_line = re.findall(r"[A-Za-z0-9'-]+", stripped)
            hit_word = None
            for w in words_in_line:
                w_low = w.lower()
                if idx == cur_line_idx and w_low == target_low:
                    continue
                if w_low in candidate_words:
                    hit_word = w
                    break
                if target_tail and len(w_low) >= 3 and w_low != target_low and w_low.endswith(target_tail):
                    hit_word = w
                    break

            if hit_word:
                matched_lines.append((idx, stripped, hit_word))

        return matched_lines

    def on_matching_line_clicked(self, item: QListWidgetItem):
        line_idx = item.data(Qt.UserRole)
        if isinstance(line_idx, int):
            self.lyric_editor.jump_to_line(line_idx)

    def lookup_rhyme_word(self, word: str, from_live: bool = False):
        w = word.strip()
        if not w:
            return
        if not self.rhyme_search_input.hasFocus():
            self.rhyme_search_input.setText(w)

        data = find_rhymes_for_word(w)
        prefix = "⚡ Live" if from_live else "Target"
        self.inspected_meta.setText(
            f"{prefix}: '{data['word']}'  •  {data['syllables']} Syl  •  [{data['lang']}]"
        )

        matching_lines = self._find_rhyming_lines_in_editor(data["word"], data)
        self.matching_lines_hdr.setText(f"RHYMING LINES IN LYRICS ({len(matching_lines)})")
        self.list_matching_lines.clear()
        if matching_lines:
            for line_idx, line_txt, hit_word in matching_lines:
                item = QListWidgetItem(f"L{line_idx + 1:02d} [{hit_word}]:  {line_txt}")
                item.setData(Qt.UserRole, line_idx)
                self.list_matching_lines.addItem(item)
        else:
            empty_item = QListWidgetItem("No other lines in lyrics rhyme with this word yet")
            empty_item.setFlags(Qt.NoItemFlags)
            self.list_matching_lines.addItem(empty_item)

        en_items = data["perfect_en"]
        bm_items = data["perfect_bm"]
        pack_items = data["perfect_custom"]
        slant_items = data["slant"]

        seen = set()
        all_items = []
        for entry in en_items + bm_items + pack_items + slant_items:
            if entry not in seen:
                seen.add(entry)
                all_items.append(entry)

        self._rhyme_buckets = {
            "ALL": all_items,
            "EN": en_items,
            "BM": bm_items,
            "PACKS": pack_items,
            "SLANT": slant_items,
        }
        self._refresh_rhyme_list()

        self.wordplay_box.setPlainText(data["wordplay"])

    def _set_rhyme_filter(self, key: str):
        self._rhyme_filter = key
        self._refresh_rhyme_list()

    def _refresh_rhyme_list(self):
        self.list_rhymes.clear()
        for entry in self._rhyme_buckets.get(self._rhyme_filter, []):
            self.list_rhymes.addItem(QListWidgetItem(entry))

    def insert_rhyme_into_editor(self, item: QListWidgetItem):
        raw = item.text()
        word = re.sub(r"\s*\[.*?\]|\s*\(slang\)|\s*🔥", "", raw).strip()
        cursor = self.lyric_editor.textCursor()
        cursor.insertText(word + " ")
        self.lyric_editor.setFocus()

    def toggle_loop(self):
        self.is_looping = self.btn_loop.isChecked()
        self.player.setLoops(QMediaPlayer.Infinite if self.is_looping else 1)
        self._update_loop_button_state()

    # --- VAULT STORAGE, TIMESTAMPS & VAULT SEARCH ---
    def autosave_silent(self):
        if self.lyric_editor.toPlainText().strip():
            self.save_track()

    def _sanitize_track_filename(self, title: str) -> str:
        safe = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).strip()
        return safe or "Untitled_Track"

    def save_track(self):
        title = self.track_title_input.text().strip() or "Untitled_Track"
        safe_name = self._sanitize_track_filename(title)
        filepath = os.path.join(self.vault_dir, f"{safe_name}.json")
        now_dt = datetime.now()
        now_str = now_dt.strftime("%d %b %Y • %I:%M %p")

        created_at = self.current_track_created_at
        if not created_at and os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as rf:
                    old_data = json.load(rf)
                created_at = old_data.get("created_at")
            except Exception:
                pass
        if not created_at:
            created_at = now_str
        self.current_track_created_at = created_at

        payload = {
            "title": title,
            "bpm": self.bpm_spin.value(),
            "beat_path": self.beat_path,
            "markers": self.beat_markers,
            "lyrics": self.lyric_editor.toPlainText(),
            "stash": self.stash_editor.toPlainText(),
            "created_at": created_at,
            "updated_at": now_str,
            "updated_iso": now_dt.isoformat(),
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        self.load_vault_list(select_filename=safe_name)

    def schedule_realtime_vault_update(self):
        if getattr(self, "_is_loading_track", False):
            return
        if hasattr(self, "realtime_vault_timer"):
            self.realtime_vault_timer.start()

    def _on_realtime_track_modified(self):
        if getattr(self, "_is_loading_track", False):
            return
        title = self.track_title_input.text().strip() or "Untitled_Track"
        safe_name = self._sanitize_track_filename(title)
        filepath = os.path.join(self.vault_dir, f"{safe_name}.json")
        if os.path.exists(filepath) or self.lyric_editor.toPlainText().strip():
            self.save_track()

    def _add_vault_row_widget(self, safe_name: str, display_title: str, timestamp_str: str) -> QListWidgetItem:
        item = QListWidgetItem()
        item.setData(Qt.UserRole, safe_name)
        item.setToolTip(f"{display_title}\n🕒 Updated: {timestamp_str}")
        item.setSizeHint(QSize(0, 28))
        self.vault_list.addItem(item)

        row_w = QWidget()
        row_w.setStyleSheet("background: transparent;")
        row_lay = QHBoxLayout(row_w)
        row_lay.setContentsMargins(6, 2, 6, 2)
        row_lay.setSpacing(6)

        title_lbl = ElidedLabel(display_title)
        title_lbl.setTextFormat(Qt.PlainText)
        title_lbl.setMinimumWidth(0)
        title_lbl.setStyleSheet("color: #F4F4F5; font-size: 11px; font-weight: 600; background: transparent;")
        row_lay.addWidget(title_lbl, 1)

        date_lbl = QLabel(timestamp_str)
        date_lbl.setTextFormat(Qt.PlainText)
        date_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        date_lbl.setStyleSheet("color: #D8B4FE; font-family: 'Consolas', monospace; font-size: 10px; background: transparent;")
        row_lay.addWidget(date_lbl, 0)

        self.vault_list.setItemWidget(item, row_w)
        return item

    def update_trash_badge(self):
        if not hasattr(self, "btn_recycle_bin"):
            return
        os.makedirs(self.trash_dir, exist_ok=True)
        trash_count = len([f for f in os.listdir(self.trash_dir) if f.endswith(".json")])
        self.btn_recycle_bin.setText(f"🗑 Bin ({trash_count})")

    def load_vault_list(self, select_filename: str | None = None):
        self.vault_list.clear()
        self.update_trash_badge()
        if not os.path.exists(self.vault_dir):
            return
        q = self.vault_search_input.text().strip().lower() if hasattr(self, "vault_search_input") else ""

        entries = []
        for fname in os.listdir(self.vault_dir):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(self.vault_dir, fname)
            safe_name = fname[:-5]
            try:
                st = os.stat(fpath)
                mtime = st.st_mtime
            except Exception:
                mtime = 0.0

            display_title = safe_name
            timestamp_str = datetime.fromtimestamp(mtime).strftime("%d %b • %I:%M %p") if mtime else ""
            lyrics_txt = ""
            stash_txt = ""

            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                display_title = data.get("title") or safe_name
                if data.get("updated_iso"):
                    dt_obj = datetime.fromisoformat(data["updated_iso"])
                    timestamp_str = dt_obj.strftime("%d %b • %I:%M %p")
                elif data.get("updated_at"):
                    timestamp_str = data["updated_at"]
                elif data.get("created_at"):
                    timestamp_str = data["created_at"]
                lyrics_txt = data.get("lyrics", "")
                stash_txt = data.get("stash", "")
            except Exception:
                pass

            if q:
                if (
                    q not in safe_name.lower()
                    and q not in display_title.lower()
                    and q not in timestamp_str.lower()
                    and q not in lyrics_txt.lower()
                    and q not in stash_txt.lower()
                ):
                    continue

            entries.append((mtime, safe_name, display_title, timestamp_str))

        entries.sort(key=lambda x: x[0], reverse=True)

        target_item = None
        for _, safe_name, display_title, timestamp_str in entries:
            item = self._add_vault_row_widget(safe_name, display_title, timestamp_str)
            if select_filename and safe_name == select_filename:
                target_item = item

        if target_item:
            self.vault_list.setCurrentItem(target_item)

    def open_track_by_safe_name(self, safe_name: str):
        filepath = os.path.join(self.vault_dir, f"{safe_name}.json")
        if not os.path.exists(filepath):
            return

        if getattr(self, "realtime_vault_timer", None) and self.realtime_vault_timer.isActive():
            self.realtime_vault_timer.stop()
            self.save_track()

        self._is_loading_track = True
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.track_title_input.setText(data.get("title", safe_name))
            self.bpm_spin.setValue(data.get("bpm", 140))
            self.lyric_editor.setPlainText(data.get("lyrics", ""))
            self.stash_editor.setPlainText(data.get("stash", ""))
            self.current_track_created_at = data.get("created_at")
            bp = data.get("beat_path")
            saved_markers = data.get("markers") or []
            if bp and os.path.exists(bp):
                if os.path.abspath(bp) != os.path.abspath(self.beat_path or ""):
                    if self.is_playing:
                        self.player.stop()
                        self.is_playing = False
                        self._clear_auto_clock()
                        self._update_play_button_state()
                    self.beat_path = bp
                    self.beat_duration_ms = 0
                    self.beat_sync_offset_ms = 0.0
                    self.player.setSource(QUrl.fromLocalFile(bp))
                    self._start_waveform_beat_analysis(bp)
                self.beat_markers = list(saved_markers)
                self._refresh_markers_ui()
                if getattr(self, "metro_mode", "OFF") == "OFF":
                    self._set_metro_mode("AUTO")
            else:
                if self.is_playing:
                    self.player.stop()
                    self.is_playing = False
                    self._clear_auto_clock()
                    self._update_play_button_state()
                self.player.setSource(QUrl())
                self.beat_path = None
                self.beat_duration_ms = 0
                self.beat_markers = []
                self.beat_sync_offset_ms = 0.0
                self.detected_bpm = None
                self.detected_beat_times_ms = []
                self.auto_beat_grid_active = False
                if hasattr(self, "beat_seekbar"):
                    self.beat_seekbar.set_duration(0)
                    self.beat_seekbar.set_position(0)
                    self.lbl_beat_time.setText("00:00 / 00:00")
                self._refresh_markers_ui()
                self.beat_label.setText("No beat loaded (.mp3 / .wav / .flac)")
                if getattr(self, "metro_mode", "OFF") == "AUTO":
                    self._set_metro_mode("OFF")
            self.toggle_rhyme_solo(None)
            self._update_beat_button_state()
            self._finalize_lyric_rating(animate=False)
        finally:
            self._is_loading_track = False
        self.load_vault_list(select_filename=safe_name)

    def open_track_from_vault(self, item: QListWidgetItem):
        safe_name = item.data(Qt.UserRole) or item.text().splitlines()[0].strip()
        self.open_track_by_safe_name(safe_name)

    def move_track_to_trash(self, safe_name: str):
        src_path = os.path.join(self.vault_dir, f"{safe_name}.json")
        if not os.path.exists(src_path):
            return
        try:
            with open(src_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {"title": safe_name}

        title_display = data.get("title", safe_name)
        reply = QMessageBox.question(
            self,
            "Move to Recycle Bin",
            f"Move '{title_display}' to Recycle Bin?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        os.makedirs(self.trash_dir, exist_ok=True)
        data["deleted_at"] = datetime.now().strftime("%d %b %Y • %I:%M %p")
        dst_path = os.path.join(self.trash_dir, f"{safe_name}.json")
        if os.path.exists(dst_path):
            stamp = datetime.now().strftime("%H%M%S")
            dst_path = os.path.join(self.trash_dir, f"{safe_name}_{stamp}.json")

        with open(dst_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.remove(src_path)
        self.load_vault_list()

    def delete_selected_vault_track(self):
        item = self.vault_list.currentItem()
        if not item:
            QMessageBox.information(self, "Select Track", "Select a track in the Vault list first.")
            return
        safe_name = item.data(Qt.UserRole)
        if safe_name:
            self.move_track_to_trash(safe_name)

    def show_vault_context_menu(self, pos):
        item = self.vault_list.itemAt(pos)
        menu = QMenu(self)
        if item:
            safe_name = item.data(Qt.UserRole)
            act_open = QAction("⚡ Open Track", self)
            act_open.triggered.connect(lambda: self.open_track_by_safe_name(safe_name))
            menu.addAction(act_open)

            act_del = QAction("🗑 Move to Recycle Bin", self)
            act_del.triggered.connect(lambda: self.move_track_to_trash(safe_name))
            menu.addAction(act_del)
            menu.addSeparator()

        act_full = QAction("⛶ Open Full Vault Window", self)
        act_full.triggered.connect(lambda: self.open_full_vault_dialog(start_tab=0))
        menu.addAction(act_full)

        act_bin = QAction("♻ Open Recycle Bin", self)
        act_bin.triggered.connect(lambda: self.open_full_vault_dialog(start_tab=1))
        menu.addAction(act_bin)

        menu.exec(self.vault_list.mapToGlobal(pos))

    def open_full_vault_dialog(self, start_tab: int = 0):
        dlg = FullVaultWindow(
            self,
            profile_name=self.profile_name,
            vault_dir=self.vault_dir,
            trash_dir=self.trash_dir,
            on_open_track_callback=self.open_track_by_safe_name,
            on_vault_changed_callback=self.load_vault_list,
            start_tab=start_tab,
        )
        dlg.exec()

    def _generate_unique_new_track_title(self) -> str:
        idx = 1
        while True:
            candidate = f"New_Track_{idx:02d}"
            if (
                not os.path.exists(os.path.join(self.vault_dir, f"{candidate}.json"))
                and not os.path.exists(os.path.join(self.trash_dir, f"{candidate}.json"))
            ):
                return candidate
            idx += 1

    def new_track(self):
        if getattr(self, "realtime_vault_timer", None) and self.realtime_vault_timer.isActive():
            self.realtime_vault_timer.stop()
            self.save_track()

        if self.is_playing:
            self.player.stop()
            self.is_playing = False
        self.player.setSource(QUrl())
        self.beat_path = None
        self.beat_duration_ms = 0
        self.beat_markers = []
        self.beat_sync_offset_ms = 0.0
        self.detected_bpm = None
        self.detected_beat_times_ms = []
        self.auto_beat_grid_active = False
        self._clear_auto_clock()
        if hasattr(self, "beat_seekbar"):
            self.beat_seekbar.set_duration(0)
            self.beat_seekbar.set_position(0)
            self.lbl_beat_time.setText("00:00 / 00:00")
        self._refresh_markers_ui()
        self._update_play_button_state()
        self.beat_label.setText("No beat loaded (.mp3 / .wav / .flac)")
        self._update_beat_button_state()
        if getattr(self, "metro_mode", "OFF") == "AUTO":
            self._set_metro_mode("OFF")
        else:
            self._last_synced_beat_idx = -1

        new_title = self._generate_unique_new_track_title()
        self.current_track_created_at = None
        self.track_title_input.setText(new_title)
        self.lyric_editor.clear()
        self.stash_editor.clear()
        self.toggle_rhyme_solo(None)
        self.sidebar_gauge.set_score(0, "#A855F7", animate=False)
        self.rate_tier_lbl.setText("READY TO SCAN")
        self.save_track()
        self.lyric_editor.setFocus()

    def load_starter_demo(self):
        existing = [f for f in sorted(os.listdir(self.vault_dir)) if f.endswith(".json")]
        if existing:
            self.load_vault_list()
            first_item = self.vault_list.item(0)
            if first_item:
                self.vault_list.setCurrentItem(first_item)
                self.open_track_from_vault(first_item)
            return

        demo_lyrics = (
            "[Verse 1]\n"
            "Heavy is the crown when I step in the night\n"
            "Pen bleeding truth every line that I write\n"
            "No cap on the grind, got the ice on my sole\n"
            "Put my heart in the booth, yeah I gave it my soul\n\n"
            "[Verse 2 - Bilingual / Slang Switch]\n"
            "Dari jalan gelap sampai lampu terang tinggi\n"
            "Gua susun kata tajam dengan senang hati\n"
            "Bukan sembang kencang, ini memang padu\n"
            "Setiap bar yang gua ludah buat lawan kaku\n"
        )
        self.lyric_editor.setPlainText(demo_lyrics)
        self.lookup_rhyme_word("soul")
        self._finalize_lyric_rating(animate=False)


# =====================================================================
# APPLICATION CONTROLLER
# =====================================================================
class NocturneAppController:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.profiles_root = os.path.join(self.base_dir, "profiles")
        self.main_window = None

    def launch_profile_picker(self):
        picker = ProfileLauncherDialog(self.profiles_root)
        if picker.exec() == QDialog.Accepted and picker.selected_profile:
            self.main_window = NocturneMainWindow(
                profiles_root=self.profiles_root,
                profile_name=picker.selected_profile,
                on_switch_profile_callback=self.launch_profile_picker
            )
            self.main_window.show()
        else:
            if not self.main_window or self.main_window.switch_requested:
                QApplication.quit()


if __name__ == "__main__":
    ensure_offline_corpora()
    app = QApplication(sys.argv)
    app.setWindowIcon(get_nocturne_app_icon())

    base_font = safe_qfont("Segoe UI", 10, bold=False)
    app.setFont(base_font)

    register_local_fonts()
    sf_worker = SFProProvisionWorker()
    sf_worker.fonts_installed.connect(register_local_fonts)
    sf_worker.start()

    app.setStyleSheet(build_obsidian_qss())
    controller = NocturneAppController()
    controller.launch_profile_picker()
    sys.exit(app.exec())
