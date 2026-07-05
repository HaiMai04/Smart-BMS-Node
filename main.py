"""
Smart BMS HMI – main.py
Automotive-grade HMI for Electric Vehicle Battery Management System.
Architecture: QStackedWidget (5 pages) + QTimer (clock) + Event Log.
"""

import sys
import os
import can
import json
import time
import collections
# NOTE: pyqtgraph and bms_resources_rc are imported INSIDE MainWindow.__init__
# (after QApplication is created) to avoid the
# "QWidget: Must construct a QApplication before a QWidget" crash
# on embedded platforms such as BeagleBone / linuxfb.
pg = None   # module-level placeholder; real import happens in __init__

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QWidget, QLabel, QProgressBar, QPushButton,
    QFrame, QSlider, QListWidget, QListWidgetItem, QCheckBox,
    QScrollArea, QSizePolicy,
)
from PyQt5.QtCore import (
    QThread, pyqtSignal, Qt, QTimer, QDateTime, QTimeZone,
    QPropertyAnimation, QEasingCurve, pyqtProperty, QRect,
)
from PyQt5.QtGui import QFont, QColor, QPainter, QPainterPath, QBrush, QPen
from ui_main import Ui_Form

os.environ["QT_FONT_DPI"]              = "80"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_SCALE_FACTOR"]          = "1"

# ──────────────────────────────────────────────────────────────────────────────
# LAYOUT CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────
CONTENT_X = 171
CONTENT_Y = 60
CONTENT_W = 853
CONTENT_H = 470

# Cell-voltage colour thresholds
CELL_COLOR_HIGH = "#22c55e"   # > 3.7 V  – Green  (Good)
CELL_COLOR_MID  = "#3b82f6"   # 3.2–3.7 V – Blue   (OK)
CELL_COLOR_LOW  = "#eab308"   # < 3.2 V  – Yellow (Warning)

# ──────────────────────────────────────────────────────────────────────────────
# THEME DEFINITIONS  (Dark / Light)
# ──────────────────────────────────────────────────────────────────────────────
DARK_QSS = """
QMainWindow, QWidget {
    background-color: #0b1120;
    color: #e2e8f0;
    font-family: 'Segoe UI', 'Inter', sans-serif;
}
QFrame { border: none; }
QLabel { color: #e2e8f0; background: transparent; }
QListWidget {
    background-color: #111827;
    color: #e2e8f0;
    border: 1px solid #1f2937;
    border-radius: 8px;
    font-size: 12px;
}
QListWidget::item { padding: 6px 10px; border-bottom: 1px solid #1e293b; }
QListWidget::item:selected { background: #1e3a5f; color: #00e5ff; }
QSlider::groove:horizontal {
    height: 18px; border-radius: 9px;
    background: #475569;
}
QSlider::handle:horizontal {
    background: #e2e8f0; border: 1px solid #94a3b8;
    width: 24px; height: 24px; border-radius: 12px;
    margin: -3px 0px;
}
QSlider::handle:horizontal:hover {
    background: #00e5ff;
}
QSlider::sub-page:horizontal {
    background: #0ea5e9;
    border-radius: 9px;
}
QCheckBox { color: #94a3b8; font-size: 13px; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px;
    border: 2px solid #334155; background: #1e293b; }
QCheckBox::indicator:checked { background: #00e5ff; border-color: #00e5ff; }
QMessageBox, QDialog {
    background-color: #1e293b;
    color: #e2e8f0;
    border: 2px solid #334155;
    border-radius: 12px;
    font-family: 'Segoe UI', 'Inter', sans-serif;
}
QMessageBox QLabel, QDialog QLabel {
    color: #e2e8f0;
    font-size: 14px;
    background: transparent;
}
QMessageBox QPushButton, QDialog QPushButton {
    background-color: #dc2626;
    color: #ffffff;
    font-size: 13px;
    font-weight: bold;
    padding: 8px 24px;
    border-radius: 8px;
    border: 1px solid #ef4444;
    min-width: 80px;
}
QMessageBox QPushButton:hover, QDialog QPushButton:hover {
    background-color: #b91c1c;
}
"""

LIGHT_QSS = """
QMainWindow, QWidget {
    background-color: #f1f5f9;
    color: #0f172a;
    font-family: 'Segoe UI', 'Inter', sans-serif;
}
QFrame { border: none; background-color: #f1f5f9; }
QLabel { color: #0f172a; background: transparent; }
QListWidget {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    font-size: 12px;
}
QListWidget::item { padding: 6px 10px; border-bottom: 1px solid #e2e8f0; }
QListWidget::item:selected { background: #dbeafe; color: #1d4ed8; }
QSlider::groove:horizontal {
    height: 18px; border-radius: 9px;
    background: #cbd5e1;
}
QSlider::handle:horizontal {
    background: #ffffff; border: 1px solid #94a3b8;
    width: 24px; height: 24px; border-radius: 12px;
    margin: -3px 0px;
}
QSlider::handle:horizontal:hover {
    background: #2563eb;
}
QSlider::sub-page:horizontal {
    background: #3b82f6;
    border-radius: 9px;
}
QCheckBox { color: #475569; font-size: 13px; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px;
    border: 2px solid #94a3b8; background: #e2e8f0; }
QCheckBox::indicator:checked { background: #2563eb; border-color: #2563eb; }
QMessageBox, QDialog {
    background-color: #ffffff;
    color: #0f172a;
    border: 2px solid #94a3b8;
    border-radius: 12px;
    font-family: 'Segoe UI', 'Inter', sans-serif;
}
QMessageBox QLabel, QDialog QLabel {
    color: #0f172a;
    font-size: 14px;
    background: transparent;
}
QMessageBox QPushButton, QDialog QPushButton {
    background-color: #2563eb;
    color: #ffffff;
    font-size: 13px;
    font-weight: bold;
    padding: 8px 24px;
    border-radius: 8px;
    border: 1px solid #1d4ed8;
    min-width: 80px;
}
QMessageBox QPushButton:hover, QDialog QPushButton:hover {
    background-color: #1d4ed8;
}
"""

# Card template (dark / light variants injected at runtime)
def _card_style(bg, border):
    return (
        "QFrame { background-color: " + bg + "; border: 1px solid " + border + ";"
        " border-radius: 12px; }"
        " QLabel { background-color: transparent; border: none; color: #e2e8f0; }"
    )


# ──────────────────────────────────────────────────────────────────────────────
# HELPER: make_info_card
# ──────────────────────────────────────────────────────────────────────────────
def make_info_card(parent, title, value, unit,
                   val_color="#00e5ff", bg="#111827", border="#1f2937",
                   title_size=11, val_size=22):
    """Create a small info card widget. All font sizes clamped to >= 1."""
    card = QFrame(parent)
    card.setStyleSheet(_card_style(bg, border))
    card.setFrameShape(QFrame.StyledPanel)

    ts = max(1, int(title_size))
    vs = max(1, int(val_size))

    lbl_t = QLabel(title, card)
    lbl_t.setStyleSheet(
        "color: #94a3b8; font-size: " + str(ts) + "px;"
        " background: transparent; border: none;"
    )
    lbl_t.setGeometry(10, 8, 200, 18)

    lbl_v = QLabel(value, card)
    lbl_v.setStyleSheet(
        "color: " + val_color + "; font-size: " + str(vs) + "px;"
        " font-weight: bold; background: transparent; border: none;"
    )
    lbl_v.setGeometry(10, 28, 160, 30)

    lbl_u = QLabel(unit, card)
    lbl_u.setStyleSheet("color: #64748b; font-size: 11px; background: transparent; border: none;")
    lbl_u.setGeometry(10, 60, 180, 16)

    return card, lbl_v


def _get_cell_color(v):
    if v > 3.7:
        return CELL_COLOR_HIGH
    elif v >= 3.2:
        return CELL_COLOR_MID
    return CELL_COLOR_LOW


# ──────────────────────────────────────────────────────────────────────────────
# CUSTOM TOGGLE SWITCH WIDGET
# ──────────────────────────────────────────────────────────────────────────────
class ToggleSwitch(QWidget):
    """
    Compact animated toggle switch.
    - Width × Height: 80 × 38 px  (recommended)
    - Click anywhere on widget → toggles instantly
    - Emits `toggled(bool)` signal
    - Knob shows 🌙 (dark) or ☀️ (light) icon
    - Track: dark blue (#1e3a5f) for dark mode,
             amber  (#f59e0b) for light mode
    """
    toggled = pyqtSignal(bool)   # True = dark mode

    def __init__(self, parent=None, checked=True):
        super().__init__(parent)
        self.setFixedSize(80, 38)
        self.setCursor(Qt.PointingHandCursor)

        self._checked  = checked          # True = dark mode
        self._knob_x   = 44.0 if checked else 4.0   # left edge of knob

        # Smooth animation on _knob_x
        self._anim = QPropertyAnimation(self, b"knob_x", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)

    # ── animated property ─────────────────────────────────────────────
    def _get_knob_x(self):
        return self._knob_x

    def _set_knob_x(self, val):
        self._knob_x = val
        self.update()          # repaint

    knob_x = pyqtProperty(float, _get_knob_x, _set_knob_x)

    # ── public API ────────────────────────────────────────────────────
    def isChecked(self):
        return self._checked

    def setChecked(self, val: bool):
        if val == self._checked:
            return
        self._checked = val
        self._animate_to(44.0 if val else 4.0)
        self.toggled.emit(val)

    # ── click → toggle ────────────────────────────────────────────────
    def mousePressEvent(self, event):
        self.setChecked(not self._checked)

    def _animate_to(self, target_x: float):
        self._anim.stop()
        self._anim.setStartValue(self._knob_x)
        self._anim.setEndValue(target_x)
        self._anim.start()

    # ── paint ─────────────────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h  = self.width(), self.height()
        r     = h / 2          # track corner radius
        knob_d = h - 8         # knob diameter

        # Track colour: dark-blue (dark mode) or amber (light mode)
        track_col = QColor("#1e3a5f") if self._checked else QColor("#f59e0b")
        track_border = QColor("#0ea5e9") if self._checked else QColor("#d97706")

        # ── draw track ────────────────────────────────────────────────
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, r, r)
        p.fillPath(path, QBrush(track_col))
        p.setPen(QPen(track_border, 1.5))
        p.drawPath(path)

        # ── draw knob (white circle) ───────────────────────────────────
        knob_x = int(self._knob_x)
        knob_y = 4
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawEllipse(knob_x, knob_y, knob_d, knob_d)

        # ── draw icon inside knob ─────────────────────────────────────
        icon = "🌙" if self._checked else "☀️"
        p.setPen(QColor("#0b1120") if self._checked else QColor("#78350f"))
        font = p.font()
        font.setPixelSize(14)
        p.setFont(font)
        icon_rect = QRect(knob_x, knob_y, knob_d, knob_d)
        p.drawText(icon_rect, Qt.AlignCenter, icon)

        p.end()


# ──────────────────────────────────────────────────────────────────────────────
# CAN RECEIVER THREAD
# ──────────────────────────────────────────────────────────────────────────────
class CANReceiverThread(QThread):
    update_pack          = pyqtSignal(float, float)
    update_cells_1_2     = pyqtSignal(float, float)
    update_cells_3_4_etc = pyqtSignal(float, float, float, int, int)

    def run(self):
        bus = can.interface.Bus(channel='can0', bustype='socketcan')
        while True:
            msg = bus.recv(1.0)
            if msg is not None:
                if msg.arbitration_id == 0x103:
                    t_vol = int.from_bytes(msg.data[0:2], 'big', signed=False) / 100.0
                    t_cur = int.from_bytes(msg.data[2:4], 'big', signed=True)  / 100.0
                    c1    = int.from_bytes(msg.data[4:6], 'big', signed=False) / 100.0
                    c2    = int.from_bytes(msg.data[6:8], 'big', signed=False) / 100.0
                    self.update_pack.emit(t_vol, t_cur)
                    self.update_cells_1_2.emit(c1, c2)
                elif msg.arbitration_id == 0x104:
                    c3    = int.from_bytes(msg.data[0:2], 'big', signed=False) / 100.0
                    c4    = int.from_bytes(msg.data[2:4], 'big', signed=False) / 100.0
                    temp  = int.from_bytes(msg.data[4:6], 'big', signed=True)  / 100.0
                    fault = msg.data[6]
                    speed = msg.data[7]
                    self.update_cells_3_4_etc.emit(c3, c4, temp, fault, speed)


# ──────────────────────────────────────────────────────────────────────────────
# FLOATING ALERT WIDGET (Fault Code overlay – always on top)
# ──────────────────────────────────────────────────────────────────────────────
# Map from STM32 fault code → Vietnamese warning text
FAULT_MESSAGES = {
    0x01: "⚠️ CảNH BÁO: TỤT ÁP!",
    0x02: "⚠️ CảNH BÁO: QUÁ ÁP!",
    0x04: "⚠️ CảNH BÁO: QUÁ DÒNG!",
    0x08: "⚠️ CảNH BÁO: QUÁ NHIỆT!",
    0x10: "⚠️ CảNH BÁO: LỖI CÂN BẰỜNG CELL!",
    0x20: "⚠️ CảNH BÁO: LỖI GIAO TIẾP!",
}


class FloatingAlertWidget(QWidget):
    """
    Full-width banner that floats over the main window (child of QMainWindow).
    Shows whenever Fault_Code != 0.  Always stacks above QStackedWidget pages.
    """

    # Geometry constants (relative to parent window)
    BANNER_H = 64
    BANNER_Y = 60   # just below TopBar

    def __init__(self, parent: QMainWindow):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        # Size: full width of content area, fixed height
        w = parent.width()
        self.setGeometry(0, self.BANNER_Y, w, self.BANNER_H)

        # Background: vivid red
        self.setStyleSheet(
            "background-color: #b91c1c;"
            "border-bottom: 3px solid #fca5a5;"
            "border-top: 3px solid #fca5a5;"
        )

        # Icon
        lbl_icon = QLabel("🚨", self)
        lbl_icon.setStyleSheet(
            "font-size: 26px; color: #fff; background: transparent; border: none;"
        )
        lbl_icon.setGeometry(16, 12, 40, 40)

        # Message text
        self.lbl_msg = QLabel("", self)
        self.lbl_msg.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #ffffff;"
            "background: transparent; border: none; letter-spacing: 1px;"
        )
        self.lbl_msg.setGeometry(64, 8, w - 80, 48)
        self.lbl_msg.setWordWrap(False)

        self.hide()   # hidden by default

    def show_fault(self, fault_code: int):
        """Display the banner with the appropriate message for fault_code."""
        # Build message: show the highest-priority matching bit
        text = FAULT_MESSAGES.get(fault_code)
        if text is None:
            # Try each bit flag (bitfield)
            for bit, msg in FAULT_MESSAGES.items():
                if fault_code & bit:
                    text = msg
                    break
        if text is None:
            text = f"⚠️ CảNH BÁO: MÃ LỖI 0x{fault_code:02X}!"
        self.lbl_msg.setText(text)
        self.raise_()   # ensure on top of siblings
        self.show()

    def hide_fault(self):
        """Hide the banner when fault clears."""
        self.hide()


# ──────────────────────────────────────────────────────────────────────────────
# MAIN WINDOW
# ──────────────────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # ── Late imports: must come AFTER QApplication is created ────────────
        # pyqtgraph registers Qt objects internally at import time;
        # bms_resources_rc calls qInitResources() which can create QPixmaps.
        # Both require an existing QApplication (critical on linuxfb / eglfs).
        global pg
        if pg is None:
            import pyqtgraph as _pg
            pg = _pg
        try:
            import bms_resources_rc  # noqa: F401 – side-effect import
        except Exception:
            pass  # resource file optional; app still runs without icons

        self.ui = Ui_Form()

        # ── Silence QFont::setPointSize warnings from auto-generated ui_main.py
        # Qt Designer emits setPointSize(-1) as a sentinel for "use default".
        # On embedded platforms (linuxfb / eglfs) this triggers a warning per
        # widget.  Patch the method just for the duration of setupUi(), then
        # restore it so normal code is unaffected.
        _orig_set_point_size = QFont.setPointSize
        def _safe_set_point_size(self_font, size):
            _orig_set_point_size(self_font, max(1, size) if size < 1 else size)
        QFont.setPointSize = _safe_set_point_size
        try:
            self.ui.setupUi(self)
        finally:
            QFont.setPointSize = _orig_set_point_size   # always restore

        # ── Fix font sizes emitted by Qt Designer (setPointSize(-1)) ───────
        # On embedded low-DPI screens Qt warns: "Point size <= 0 (-1)".
        # -1 is Qt's sentinel for “use system default”, but some platform
        # plugins treat it as invalid. We clamp every child widget's font
        # to at least 1 pt to silence those warnings.
        self._fix_ui_font_sizes(self)

        # ── State / Data ──────────────────────────────────────────────────
        self.data_file      = "bms_data.json"
        self.soc            = 100.0
        self.soh            = 93.2
        self.capacity_ah    = 2.0          # 4S1P Li-ion 2000 mAh
        self.last_time      = time.time()
        self.current_speed  = 0
        self.smooth_range   = 312.0
        self.cell_volts     = [4.1, 4.1, 4.1, 4.1]
        self.peak_current   = 0.0
        # (Nội trở đã loại bỏ khỏi giao diện)
        self.t_cur_live     = 0.0       # last known current from CAN
        self.temp_live      = 25.0      # last known temperature
        self.is_dark_mode   = True
        self.charge_limit   = 100       # % SOC ceiling
        self._charging_started_logged = False   # debounce log flag
        self._is_charging        = False  # trạng thái sạc hiện tại
        self._idle_start_time    = None   # thời điểm bắt đầu idle (cho OCV settle)

        # ── Moving-average buffer for current (req. 3) ────────────────────
        # Motor loads produce noisy current readings.  Average the last 20
        # CAN frames before using the value for SOC counting and display.
        self._cur_buf = collections.deque(maxlen=20)

        # Active-alert state (key → bool)
        self._active_alerts: dict = {}

        self.load_data()

        self.volt_data = []
        self.time_data = []
        self.soh_data  = []
        self.ptr       = 0

        # ── Build UI ──────────────────────────────────────────────────────
        self._build_stacked_widget()
        self._connect_nav_buttons()

        # Set default page
        self.stacked.setCurrentIndex(0)
        self.ui.pushButton.setChecked(True)

        # Apply global theme based on is_dark_mode
        self._on_theme_toggled(self.is_dark_mode)

        # ── Real-time clock (GMT+7) ───────────────────────────────────────
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()          # immediate first tick

        # ── CAN Thread ───────────────────────────────────────────────────
        self.can_thread = CANReceiverThread()
        self.can_thread.update_cells_1_2.connect(self.display_cells_1_2)
        self.can_thread.update_cells_3_4_etc.connect(self.display_cells_3_4_etc)
        self.can_thread.update_pack.connect(self.display_pack_info)
        self.can_thread.start()

        # ── Floating fault-alert banner (req. 4) ────────────────────────────
        # Được tạo SAU CÙNG để nằm trên cùng trong z-order của QMainWindow.
        self.float_alert = FloatingAlertWidget(self)
        self.float_alert.raise_()

        # ── Sửa lỗi đánh máy Cell 4 (req. 1) ───────────────────────────────
        # label_17 là label tên trong frame_9 (khối mini-cell thứ 4).
        self.ui.label_17.setText('Cell 4')

        # ── Đổi nhãn 'Tốc độ' → 'Quãng đường' (req. 2) ────────────────────
        # label_40 là header label phía trên txt_distance trong frame_4.
        self.ui.label_40.setText('Quãng đường')

    # ─────────────────────────────────────────────────────────────────────
    # REAL-TIME CLOCK
    # ─────────────────────────────────────────────────────────────────────
    def _update_clock(self):
        """Update TopBar clock label to current time in GMT+7 (Vietnam)."""
        tz_vn = QTimeZone(b"Asia/Ho_Chi_Minh")
        now   = QDateTime.currentDateTime().toTimeZone(tz_vn)
        text  = now.toString("hh:mm:ss  -  dd/MM/yyyy")
        self.ui.label_43.setText(text)

    def _timestamp(self) -> str:
        """Return ISO-like timestamp string for event log (GMT+7)."""
        tz_vn = QTimeZone(b"Asia/Ho_Chi_Minh")
        now   = QDateTime.currentDateTime().toTimeZone(tz_vn)
        return now.toString("[hh:mm:ss dd/MM]")

    # ─────────────────────────────────────────────────────────────────────
    # EVENT LOG helper
    # ─────────────────────────────────────────────────────────────────────
    def _log_event(self, message: str, color: str = "#94a3b8"):
        """Prepend a timestamped entry to the History QListWidget."""
        entry = f"{self._timestamp()}  {message}"
        item  = QListWidgetItem(entry)
        item.setForeground(QColor(color))
        self.list_history.insertItem(0, item)   # newest on top

    # ──────────────────────────────────────────────────────────────────────
    # ACTIVE ALERTS helper
    # ──────────────────────────────────────────────────────────────────────
    def _set_alert(self, key: str, active: bool, message: str, color: str = "#ef4444"):
        """
        Manage real-time alerts in Page 3 (Alerts).
        Adds/removes a named row.  When a new alert fires it's also logged.
        """
        was_active = self._active_alerts.get(key, False)

        if active and not was_active:
            # New alert: add to active list + log
            self._active_alerts[key] = True
            item = QListWidgetItem("🔴  " + message)
            item.setForeground(QColor(color))
            item.setData(Qt.UserRole, key)          # store key for removal
            self.list_alerts.addItem(item)
            self._log_event("Cảnh báo: " + message, "#ef4444")

        elif not active and was_active:
            # Alert cleared
            self._active_alerts[key] = False
            for row in range(self.list_alerts.count()):
                if self.list_alerts.item(row).data(Qt.UserRole) == key:
                    self.list_alerts.takeItem(row)
                    break
            self._log_event("Đã giải quyết: " + message, "#22c55e")

        # Update "no alerts" placeholder visibility
        no_alert = self.list_alerts.count() == 0
        self.lbl_no_alert.setVisible(no_alert)

    # ─────────────────────────────────────────────────────────────────────
    # BUILD STACKED WIDGET
    # ─────────────────────────────────────────────────────────────────────
    def _build_stacked_widget(self):
        self.stacked = QStackedWidget(self)
        self.stacked.setGeometry(CONTENT_X, CONTENT_Y, CONTENT_W, CONTENT_H)

        pages = [
            self._build_page_overview,   # 0 – Tổng quan
            self._build_page_pack,       # 1 – Pin
            self._build_page_cell,       # 2 – Cell
            self._build_page_alerts,     # 3 – Cảnh báo (active)
            self._build_page_history,    # 4 – Lịch sử  (log)
            self._build_page_settings,   # 5 – Cài đặt
        ]
        for builder in pages:
            self.stacked.addWidget(builder())

    # ══════════════════════════════════════════════════════════════════════
    # PAGE 0 – TỔNG QUAN  (Dashboard)
    # ══════════════════════════════════════════════════════════════════════
    def _build_page_overview(self):
        """
        Layout 853×470
        ┌──────────────────────────┬─────────────────┐  y=0   h=300
        │  frame_4 (SOC/DTE/I)     │  frame_10+chart │
        ├────────────────┬──────────┴────────┬────────┤  y=303 h=165
        │ Cell cards ×4  │ Charging Info      │        │
        └────────────────┴───────────────────┴────────┘
        """
        page = QWidget()

        # ── Row A ─────────────────────────────────────────────────────────
        f4 = self.ui.frame_4
        f4.setParent(page)
        f4.setGeometry(0, 0, 530, 300)
        f4.show()

        f10 = self.ui.frame_10
        f10.setParent(page)
        f10.setGeometry(534, 0, 319, 300)
        f10.show()

        # pyqtgraph – Voltage pack chart
        self.graphWidget = pg.PlotWidget()
        self.graphWidget.setBackground('transparent')
        for ax in ('left', 'bottom'):
            self.graphWidget.getAxis(ax).setPen('#334155')
            self.graphWidget.getAxis(ax).setTextPen('#64748b')
        self.graphWidget.showGrid(x=False, y=True, alpha=0.25)
        self.graphWidget.setYRange(12.0, 17.0)
        self.graphWidget.setTitle(
            "<span style='color:#64748b;font-size:10px'>Điện áp Pack (V)</span>"
        )
        self.pen       = pg.mkPen(color=(0, 162, 255), width=2)
        self.data_line = self.graphWidget.plot(self.time_data, self.volt_data, pen=self.pen)
        chart_layout = QVBoxLayout(self.ui.frame_chart)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.addWidget(self.graphWidget)

        # ── Row B – Cell mini cards (4 × 131 px) ─────────────────────────
        for frame, x in [
            (self.ui.frame_5, 0),
            (self.ui.frame_7, 134),
            (self.ui.frame_8, 268),
            (self.ui.frame_9, 402),
        ]:
            frame.setParent(page)
            frame.setGeometry(x, 303, 131, 165)
            frame.show()

        # ── Row B – Charging Info card (x=536) ───────────────────────────
        chg_card = QFrame(page)
        chg_card.setGeometry(536, 303, 314, 165)
        chg_card.setStyleSheet(_card_style("#0f172a", "#1e293b"))

        # Title
        lbl_chg_title = QLabel("⚡  Thông tin Sạc", chg_card)
        lbl_chg_title.setStyleSheet(
            "color: #94a3b8; font-size: 12px; font-weight: bold;"
            "background: transparent; border: none;"
        )
        lbl_chg_title.setGeometry(12, 8, 290, 20)

        # ── Charging power
        lbl_pw_lbl = QLabel("Tốc độ sạc", chg_card)
        lbl_pw_lbl.setStyleSheet("color: #64748b; font-size: 10px; background: transparent; border: none;")
        lbl_pw_lbl.setGeometry(12, 34, 100, 16)

        self.lbl_charge_power = QLabel("--", chg_card)
        self.lbl_charge_power.setStyleSheet(
            "color: #34d399; font-size: 26px; font-weight: bold;"
            "background: transparent; border: none;"
        )
        self.lbl_charge_power.setGeometry(12, 50, 140, 36)

        lbl_pw_unit = QLabel("kW", chg_card)
        lbl_pw_unit.setStyleSheet("color: #475569; font-size: 11px; background: transparent; border: none;")
        lbl_pw_unit.setGeometry(12, 88, 60, 16)

        # Separator
        sep = QFrame(chg_card)
        sep.setGeometry(160, 30, 1, 115)
        sep.setStyleSheet("background: #1e293b; border: none;")

        # ── Time-to-full
        lbl_ttf_lbl = QLabel("Thời gian đầy", chg_card)
        lbl_ttf_lbl.setStyleSheet("color: #64748b; font-size: 10px; background: transparent; border: none;")
        lbl_ttf_lbl.setGeometry(172, 34, 130, 16)

        self.lbl_time_to_full = QLabel("--", chg_card)
        self.lbl_time_to_full.setStyleSheet(
            "color: #00e5ff; font-size: 18px; font-weight: bold;"
            "background: transparent; border: none;"
        )
        self.lbl_time_to_full.setGeometry(172, 52, 130, 28)

        lbl_ttf_unit = QLabel("hh giờ mm phút", chg_card)
        lbl_ttf_unit.setStyleSheet("color: #475569; font-size: 10px; background: transparent; border: none;")
        lbl_ttf_unit.setGeometry(172, 82, 130, 14)

        # ── Charge status bar
        self.lbl_chg_status = QLabel("● Không sạc", chg_card)
        self.lbl_chg_status.setStyleSheet(
            "color: #475569; font-size: 11px; background: transparent; border: none;"
        )
        self.lbl_chg_status.setGeometry(12, 138, 290, 18)

        return page

    # ══════════════════════════════════════════════════════════════════════
    # PAGE 1 – PIN  (Pack Info)
    # ══════════════════════════════════════════════════════════════════════
    def _build_page_pack(self):
        page = QWidget()

        title = QLabel("🔋   Thông tin Pack Pin", page)
        title.setStyleSheet(
            "color: #00ffcc; font-size: 17px; font-weight: bold;"
            "background: transparent; border: none;"
        )
        title.setGeometry(16, 8, 400, 32)

        # frame_11 (SOH / cycles block from ui_main)
        f11 = self.ui.frame_11
        f11.setParent(page)
        f11.setGeometry(16, 44, 530, 191)
        f11.show()

        # (Card Nội trở đã được loại bỏ theo yêu cầu)

        # Card – Dòng đỉnh
        card_pk, self.lbl_peak_cur = make_info_card(
            page, "Dòng đỉnh", "--", "A  (xả/sạc)",
            val_color="#ef4444", bg="#110e1a", border="#2d1f4e", val_size=24,
        )
        card_pk.setGeometry(700, 44, 140, 95)

        # Pack status card
        st_card = QFrame(page)
        st_card.setGeometry(552, 145, 288, 90)
        st_card.setStyleSheet(_card_style("#0f172a", "#1e293b"))

        self.lbl_pack_status = QLabel("● Hoạt động bình thường", st_card)
        self.lbl_pack_status.setStyleSheet(
            "color: #22c55e; font-size: 13px; font-weight: bold;"
            "background: transparent; border: none;"
        )
        self.lbl_pack_status.setGeometry(12, 12, 260, 22)

        self.lbl_pack_hint = QLabel(
            "Tất cả thông số trong ngưỡng an toàn.\n"
            "Tiếp tục theo dõi chu kỳ sạc.", st_card
        )
        self.lbl_pack_hint.setStyleSheet(
            "color: #64748b; font-size: 11px; background: transparent; border: none;"
        )
        self.lbl_pack_hint.setGeometry(12, 38, 265, 44)

        # frame_12 – Temperature
        f12 = self.ui.frame_12
        f12.setParent(page)
        f12.setGeometry(16, 240, 824, 95)
        f12.show()

        # SOH trend chart
        soh_card = QFrame(page)
        soh_card.setGeometry(16, 342, 824, 118)
        soh_card.setStyleSheet(_card_style("#111827", "#1f2937"))

        lbl_soh_ct = QLabel("📈  Xu hướng SOH theo thời gian thực", soh_card)
        lbl_soh_ct.setStyleSheet(
            "color: #94a3b8; font-size: 12px; background: transparent; border: none;"
        )
        lbl_soh_ct.setGeometry(10, 6, 350, 20)

        self.soh_graph = pg.PlotWidget(soh_card)
        self.soh_graph.setGeometry(0, 26, 824, 90)
        self.soh_graph.setBackground('transparent')
        for ax in ('left', 'bottom'):
            self.soh_graph.getAxis(ax).setPen('#334155')
            self.soh_graph.getAxis(ax).setTextPen('#64748b')
        self.soh_graph.showGrid(x=False, y=True, alpha=0.2)
        self.soh_graph.setYRange(80.0, 100.0)
        self.soh_graph.getAxis('bottom').setStyle(showValues=False)

        soh_pen       = pg.mkPen(color=(74, 222, 128), width=2)
        self.soh_line = self.soh_graph.plot([], [], pen=soh_pen)
        flat_line     = self.soh_graph.plot([], [], pen=pg.mkPen(None))
        self.soh_fill = pg.FillBetweenItem(
            self.soh_line, flat_line, brush=pg.mkBrush(74, 222, 128, 35)
        )
        self.soh_graph.addItem(self.soh_fill)

        return page

    # ══════════════════════════════════════════════════════════════════════
    # PAGE 2 – CELL  (4 vertical bars + Delta V)
    # ══════════════════════════════════════════════════════════════════════
    def _build_page_cell(self):
        page = QWidget()

        title = QLabel("⚡   Điện áp từng Cell", page)
        title.setStyleSheet(
            "color: #00ffcc; font-size: 17px; font-weight: bold;"
            "background: transparent; border: none;"
        )
        title.setGeometry(16, 8, 400, 32)

        # Legend
        leg_x = 500
        for txt, col in [("● > 3.7V  Tốt", "#22c55e"),
                          ("● 3.2–3.7V  OK", "#3b82f6"),
                          ("● < 3.2V  Cảnh báo", "#eab308")]:
            lbl = QLabel(txt, page)
            lbl.setStyleSheet(
                "color: " + col + "; font-size: 11px; background: transparent; border: none;"
            )
            lbl.setGeometry(leg_x, 12, 170, 18)
            leg_x += 120

        # 4 vertical bar cards
        BAR_W, BAR_H = 140, 280
        CARD_W, CARD_H = 170, 370
        gap     = (CONTENT_W - 4 * CARD_W) // 5
        start_x = gap

        self.cell_bars       = []
        self.cell_labels     = []
        self.cell_pct_labels = []

        for i in range(4):
            cx = start_x + i * (CARD_W + gap)
            v  = self.cell_volts[i]
            color = _get_cell_color(v)

            card = QFrame(page)
            card.setGeometry(cx, 44, CARD_W, CARD_H)
            card.setStyleSheet(_card_style("#111827", "#1f2937"))

            lbl_name = QLabel(f"CELL  {i + 1}", card)
            lbl_name.setAlignment(Qt.AlignCenter)
            lbl_name.setStyleSheet(
                "color: #64748b; font-size: 12px; font-weight: bold; letter-spacing: 2px;"
                "background: transparent; border: none;"
            )
            lbl_name.setGeometry(0, 10, CARD_W, 20)

            bar = QProgressBar(card)
            bar.setOrientation(Qt.Vertical)
            bar.setRange(300, 420)
            bar.setValue(int(v * 100))
            bar.setTextVisible(False)
            bar.setGeometry((CARD_W - BAR_W) // 2, 38, BAR_W, BAR_H)
            bar.setStyleSheet(
                "QProgressBar { background-color: #1a2436; border-radius: 8px; border: none; }"
                "QProgressBar::chunk { background-color: " + color + "; border-radius: 8px; }"
            )
            self.cell_bars.append(bar)

            lbl_v = QLabel(f"{v:.3f} V", card)
            lbl_v.setAlignment(Qt.AlignCenter)
            lbl_v.setStyleSheet(
                "color: " + color + "; font-size: 22px; font-weight: bold;"
                "background: transparent; border: none;"
            )
            lbl_v.setGeometry(0, 326, CARD_W, 28)
            self.cell_labels.append(lbl_v)

            pct = int(max(0, min(100, (v - 3.0) / 1.2 * 100)))
            lbl_pct = QLabel(f"{pct}%", card)
            lbl_pct.setAlignment(Qt.AlignCenter)
            lbl_pct.setStyleSheet(
                "color: #64748b; font-size: 13px; background: transparent; border: none;"
            )
            lbl_pct.setGeometry(0, 350, CARD_W, 18)
            self.cell_pct_labels.append(lbl_pct)

        # Điện áp TB (Average Voltage) footer bar
        avg_v = sum(self.cell_volts) / len(self.cell_volts)
        dv_card = QFrame(page)
        dv_card.setGeometry(16, 418, 820, 46)
        dv_card.setStyleSheet(_card_style("#0f172a", "#1e293b"))

        lbl_dv_t = QLabel("⚖️   Điện áp TB  (trung bình):", dv_card)
        lbl_dv_t.setStyleSheet(
            "color: #94a3b8; font-size: 12px; background: transparent; border: none;"
        )
        lbl_dv_t.setGeometry(14, 13, 300, 20)

        self.lbl_delta_v = QLabel(f"{avg_v:.3f}  V", dv_card)
        self.lbl_delta_v.setStyleSheet(
            "color: #f59e0b; font-size: 18px; font-weight: bold;"
            "background: transparent; border: none;"
        )
        self.lbl_delta_v.setGeometry(330, 8, 240, 28)

        self.lbl_dv_status = QLabel("● Cân bằng tốt", dv_card)
        self.lbl_dv_status.setStyleSheet(
            "color: #22c55e; font-size: 12px; background: transparent; border: none;"
        )
        self.lbl_dv_status.setGeometry(590, 13, 220, 20)

        return page

    # ══════════════════════════════════════════════════════════════════════
    # PAGE 3 – CẢNH BÁO  (Active alerts – real-time)
    # ══════════════════════════════════════════════════════════════════════
    def _build_page_alerts(self):
        page = QWidget()

        title = QLabel("🚨   Cảnh báo đang diễn ra", page)
        title.setStyleSheet(
            "color: #ef4444; font-size: 17px; font-weight: bold;"
            "background: transparent; border: none;"
        )
        title.setGeometry(16, 8, 500, 32)

        lbl_hint = QLabel(
            "Các cảnh báo tự động xuất hiện / biến mất theo thời gian thực.", page
        )
        lbl_hint.setStyleSheet(
            "color: #64748b; font-size: 11px; background: transparent; border: none;"
        )
        lbl_hint.setGeometry(16, 38, 700, 18)

        self.list_alerts = QListWidget(page)
        self.list_alerts.setGeometry(16, 62, 820, 390)
        self.list_alerts.setStyleSheet(
            "QListWidget { background: #0f172a; border: 1px solid #1e293b;"
            "  border-radius: 10px; font-size: 13px; }"
            "QListWidget::item { padding: 10px 14px; border-bottom: 1px solid #1e293b; }"
            "QListWidget::item:selected { background: #450a0a; color: #fca5a5; }"
        )

        # "no alerts" placeholder
        self.lbl_no_alert = QLabel(
            "✅  Không có cảnh báo nào.\nTất cả thông số trong ngưỡng an toàn.", page
        )
        self.lbl_no_alert.setAlignment(Qt.AlignCenter)
        self.lbl_no_alert.setStyleSheet(
            "color: #22c55e; font-size: 16px; background: transparent; border: none;"
        )
        self.lbl_no_alert.setGeometry(16, 62, 820, 390)
        self.lbl_no_alert.setVisible(True)

        return page

    # ══════════════════════════════════════════════════════════════════════
    # PAGE 4 – LỊCH SỬ  (Persistent event log)
    # ══════════════════════════════════════════════════════════════════════
    def _build_page_history(self):
        page = QWidget()

        title = QLabel("📋   Nhật ký Sự kiện", page)
        title.setStyleSheet(
            "color: #00ffcc; font-size: 17px; font-weight: bold;"
            "background: transparent; border: none;"
        )
        title.setGeometry(16, 8, 500, 32)

        lbl_hint = QLabel(
            "Lưu trữ vĩnh viễn – mới nhất trên đầu. "
            "Timestamp theo múi giờ GMT+7.", page
        )
        lbl_hint.setStyleSheet(
            "color: #64748b; font-size: 11px; background: transparent; border: none;"
        )
        lbl_hint.setGeometry(16, 36, 700, 18)

        # Clear button
        btn_clear = QPushButton("🗑  Xóa log", page)
        btn_clear.setGeometry(720, 10, 110, 30)
        btn_clear.setStyleSheet(
            "QPushButton { background: #1e293b; color: #94a3b8; border-radius: 8px;"
            "  font-size: 12px; border: 1px solid #334155; }"
            "QPushButton:hover { background: #334155; color: #e2e8f0; }"
        )

        self.list_history = QListWidget(page)
        self.list_history.setGeometry(16, 58, 820, 402)
        self.list_history.setStyleSheet(
            "QListWidget { background: #0b1120; border: 1px solid #1e293b;"
            "  border-radius: 10px; font-size: 12px; }"
            "QListWidget::item { padding: 8px 14px; border-bottom: 1px solid #1e293b; }"
            "QListWidget::item:selected { background: #1e3a5f; }"
        )

        btn_clear.clicked.connect(self.list_history.clear)

        # Log application start
        self._log_event("Ứng dụng khởi động", "#64748b")

        return page

    # ══════════════════════════════════════════════════════════════════════
    # PAGE 5 – CÀI ĐẶT  (Settings)
    # ══════════════════════════════════════════════════════════════════════
    def _build_page_settings(self):
        page = QWidget()

        title = QLabel("⚙️   Cài đặt Hệ thống", page)
        title.setStyleSheet(
            "color: #00ffcc; font-size: 17px; font-weight: bold;"
            "background: transparent; border: none;"
        )
        title.setGeometry(16, 8, 500, 32)

        # ── Section 1: Charge Limit ─────────────────────────────────────
        sec1 = QFrame(page)
        sec1.setGeometry(16, 55, 820, 145)
        sec1.setStyleSheet(_card_style("#111827", "#1f2937"))

        lbl_sec1 = QLabel("🔋  Giới hạn Sạc (Charge Limit)", sec1)
        lbl_sec1.setStyleSheet(
            "color: #00ffcc; font-size: 14px; font-weight: bold;"
            "background: transparent; border: none;"
        )
        lbl_sec1.setGeometry(16, 12, 400, 22)

        lbl_sec1_desc = QLabel(
            "Tự động ngắt sạc khi SOC đạt mức giới hạn. "
            "Khuyến nghị ≤ 80% để tăng tuổi thọ pin.", sec1
        )
        lbl_sec1_desc.setStyleSheet(
            "color: #64748b; font-size: 11px; background: transparent; border: none;"
        )
        lbl_sec1_desc.setGeometry(16, 38, 780, 18)

        # Slider
        self.slider_charge_limit = QSlider(Qt.Horizontal, sec1)
        self.slider_charge_limit.setRange(50, 100)
        self.slider_charge_limit.setSingleStep(5)
        self.slider_charge_limit.setPageStep(5)
        self.slider_charge_limit.setValue(self.charge_limit)
        self.slider_charge_limit.setGeometry(16, 68, 700, 28)

        self.lbl_charge_limit_val = QLabel(f"{self.charge_limit}%", sec1)
        self.lbl_charge_limit_val.setStyleSheet(
            "color: #00e5ff; font-size: 22px; font-weight: bold;"
            "background: transparent; border: none;"
        )
        self.lbl_charge_limit_val.setGeometry(730, 60, 76, 36)

        lbl_range = QLabel("50%                                                  100%", sec1)
        lbl_range.setStyleSheet("color: #475569; font-size: 10px; background: transparent; border: none;")
        lbl_range.setGeometry(16, 100, 700, 16)

        lbl_rec = QLabel("● Giới hạn hiện tại:", sec1)
        lbl_rec.setStyleSheet("color: #94a3b8; font-size: 11px; background: transparent; border: none;")
        lbl_rec.setGeometry(16, 120, 160, 16)

        self.lbl_limit_status = QLabel(f"{self.charge_limit}%  – Sẵn sàng", sec1)
        self.lbl_limit_status.setStyleSheet(
            "color: #22c55e; font-size: 11px; background: transparent; border: none;"
        )
        self.lbl_limit_status.setGeometry(178, 120, 400, 16)

        self.slider_charge_limit.valueChanged.connect(self._on_charge_limit_changed)

        # ── Section 2: Theme Toggle ─────────────────────────────────────
        sec2 = QFrame(page)
        sec2.setGeometry(16, 215, 820, 100)
        sec2.setStyleSheet(_card_style("#111827", "#1f2937"))

        lbl_sec2 = QLabel("Giao diện Tối / Sáng", sec2)
        lbl_sec2.setStyleSheet(
            "color: #00ffcc; font-size: 14px; font-weight: bold;"
            "background: transparent; border: none;"
        )
        lbl_sec2.setGeometry(16, 12, 300, 22)

        lbl_sec2_desc = QLabel(
            "Nhấn vào switch để chuyển giữa Dark Mode và Light Mode.", sec2
        )
        lbl_sec2_desc.setStyleSheet(
            "color: #64748b; font-size: 11px; background: transparent; border: none;"
        )
        lbl_sec2_desc.setGeometry(16, 36, 700, 18)

        # ── Compact ToggleSwitch ──────────────────────────────────────────
        self.theme_switch = ToggleSwitch(sec2, checked=self.is_dark_mode)
        self.theme_switch.move(16, 54)

        self.lbl_theme_status = QLabel(
            "🌙  Dark Mode" if self.is_dark_mode else "☀️  Light Mode", sec2
        )
        self.lbl_theme_status.setStyleSheet(
            "color: #00e5ff; font-size: 14px; font-weight: bold;"
            "background: transparent; border: none;"
        )
        self.lbl_theme_status.setGeometry(110, 57, 200, 30)

        self.theme_switch.toggled.connect(self._on_theme_toggled)


        # ── Section 3: System Info ──────────────────────────────────────
        sec3 = QFrame(page)
        sec3.setGeometry(16, 330, 820, 128)
        sec3.setStyleSheet(_card_style("#0f172a", "#1e293b"))

        lbl_sec3 = QLabel("ℹ️   Thông tin Hệ thống", sec3)
        lbl_sec3.setStyleSheet(
            "color: #94a3b8; font-size: 13px; font-weight: bold;"
            "background: transparent; border: none;"
        )
        lbl_sec3.setGeometry(16, 10, 400, 20)

        info_lines = [
            ("Phiên bản phần mềm", "BMS-HMI v2.0.0"),
            ("Giao thức CAN",      "SocketCAN  (can0)  500 kbps"),
            ("Dung lượng Pack",    "2.0 Ah  ·  4S1P Li-ion"),
            ("Múi giờ hệ thống",   "GMT+7  (Asia/Ho_Chi_Minh)"),
        ]
        for row, (k, v) in enumerate(info_lines):
            lbl_k = QLabel(k + ":", sec3)
            lbl_k.setStyleSheet("color: #475569; font-size: 11px; background: transparent; border: none;")
            lbl_k.setGeometry(16, 36 + row * 22, 220, 18)
            lbl_v = QLabel(v, sec3)
            lbl_v.setStyleSheet("color: #94a3b8; font-size: 11px; background: transparent; border: none;")
            lbl_v.setGeometry(240, 36 + row * 22, 560, 18)

        return page

    # ─────────────────────────────────────────────────────────────────────
    # SETTINGS CALLBACKS
    # ─────────────────────────────────────────────────────────────────────
    def _on_charge_limit_changed(self, value):
        # Snap to nearest multiple of 5
        snapped = round(value / 5) * 5
        if snapped != value:
            self.slider_charge_limit.blockSignals(True)
            self.slider_charge_limit.setValue(snapped)
            self.slider_charge_limit.blockSignals(False)
            value = snapped
        self.charge_limit = value
        self.lbl_charge_limit_val.setText(f"{value}%")
        color = "#22c55e" if value <= 80 else "#f59e0b" if value < 100 else "#94a3b8"
        tip   = "Tốt cho tuổi thọ pin" if value <= 80 else "Bình thường" if value < 100 else "Sạc đầy 100%"
        self.lbl_limit_status.setText(f"{value}%  – {tip}")
        self.lbl_limit_status.setStyleSheet(
            "color: " + color + "; font-size: 11px; background: transparent; border: none;"
        )

    def _on_theme_toggled(self, is_dark: bool):
        """Called by ToggleSwitch.toggled signal – apply theme immediately."""
        self.is_dark_mode = is_dark
        if is_dark:
            self.lbl_theme_status.setText("🌙  Dark Mode")
            self.lbl_theme_status.setStyleSheet(
                "color: #00e5ff; font-size: 14px; font-weight: bold;"
                "background: transparent; border: none;"
            )
        else:
            self.lbl_theme_status.setText("☀️  Light Mode")
            self.lbl_theme_status.setStyleSheet(
                "color: #f59e0b; font-size: 14px; font-weight: bold;"
                "background: transparent; border: none;"
            )
        QApplication.instance().setStyleSheet(DARK_QSS if is_dark else LIGHT_QSS)
        self._log_event(
            "Chuyển giao diện → " + ("Dark Mode" if is_dark else "Light Mode"),
            "#94a3b8"
        )


    # ═════════════════════════════════════════════════════════════════════
    # NAVIGATION
    # ═════════════════════════════════════════════════════════════════════
    def _connect_nav_buttons(self):
        """
        Sidebar button mapping:
          pushButton   → 0 Tổng quan
          pushButton_2 → 1 Pin
          pushButton_3 → 2 Cell
          pushButton_4 → 3 Cảnh báo
          pushButton_5 → 4 Lịch sử
          pushButton_6 → 5 Cài đặt
        """
        nav_map = [
            (self.ui.pushButton,   0),
            (self.ui.pushButton_2, 1),
            (self.ui.pushButton_3, 2),
            (self.ui.pushButton_4, 3),
            (self.ui.pushButton_5, 4),
            (self.ui.pushButton_6, 5),
        ]
        for btn, idx in nav_map:
            btn.clicked.connect(lambda _, i=idx: self._navigate_to(i))

    def _navigate_to(self, index: int):
        self.stacked.setCurrentIndex(index)
        nav_buttons = [
            self.ui.pushButton,
            self.ui.pushButton_2,
            self.ui.pushButton_3,
            self.ui.pushButton_4,
            self.ui.pushButton_5,
            self.ui.pushButton_6,
        ]
        for i, btn in enumerate(nav_buttons):
            btn.setChecked(i == index)

    # ═════════════════════════════════════════════════════════════════════
    # PERSIST DATA
    # ═════════════════════════════════════════════════════════════════════
    # ═════════════════════════════════════════════════════════════════════
    # FIX AUTO-GENERATED FONT SIZES  (ui_main.py uses setPointSize(-1))
    # ═════════════════════════════════════════════════════════════════════

    @staticmethod
    def _fix_ui_font_sizes(root_widget):
        """
        Recursively walk all child widgets and clamp QFont pointSize to >= 1.
        Qt Designer uses pointSize = -1 as the sentinel meaning 'inherit
        system default', but certain embedded platform plugins (linuxfb,
        eglfs) treat it as invalid and spam the console with:
            QFont::setPointSize: Point size <= 0 (-1), must be greater than 0
        Clamping to max(1, ...) silences those warnings without altering
        the visual appearance on platforms that handle -1 correctly.
        """
        for widget in root_widget.findChildren(QWidget):
            font = widget.font()
            if font.pointSize() < 1:
                # Prefer pixel-size if the widget already has one set;
                # otherwise fall back to a safe 9 pt default.
                px = font.pixelSize()
                safe_pt = max(1, int(px * 72 / 96)) if px > 0 else 9
                # Use QFont constructor to avoid any monkey-patch side-effects
                # on setPointSize that may still be active during this call.
                new_font = QFont(font.family(), safe_pt,
                                 font.weight(), font.italic())
                widget.setFont(new_font)

    def load_data(self):

        try:
            with open(self.data_file, 'r') as f:
                data = json.load(f)
                self.soc          = data.get("soc", 100.0)
                self.soh          = data.get("soh", 93.2)
                self.charge_limit = data.get("charge_limit", 100)
        except Exception:
            self.save_data()

    def save_data(self):
        try:
            with open(self.data_file, 'w') as f:
                json.dump({
                    "soc": self.soc,
                    "soh": self.soh,
                    "charge_limit": self.charge_limit,
                }, f)
        except Exception:
            pass

    # ═════════════════════════════════════════════════════════════════════
    # CELL PAGE UPDATE  (helper called from both display_ slots)
    # ═════════════════════════════════════════════════════════════════════
    def _update_cell_page(self):
        for i, v in enumerate(self.cell_volts):
            color = _get_cell_color(v)
            self.cell_bars[i].setValue(int(v * 100))
            self.cell_bars[i].setStyleSheet(
                "QProgressBar { background-color: #1a2436; border-radius: 8px; border: none; }"
                "QProgressBar::chunk { background-color: " + color + "; border-radius: 8px; }"
            )
            self.cell_labels[i].setText(f"{v:.3f} V")
            self.cell_labels[i].setStyleSheet(
                "color: " + color + "; font-size: 22px; font-weight: bold;"
                "background: transparent; border: none;"
            )
            pct = int(max(0, min(100, (v - 3.0) / 1.2 * 100)))
            self.cell_pct_labels[i].setText(f"{pct}%")

        avg_v = sum(self.cell_volts) / len(self.cell_volts)
        self.lbl_delta_v.setText(f"{avg_v:.3f}  V")
        if avg_v >= 3.7:
            dv_txt, dv_col = "● Tốt", "#22c55e"
        elif avg_v >= 3.2:
            dv_txt, dv_col = "⚠ Trung bình", "#f59e0b"
        else:
            dv_txt, dv_col = "🔴 Thấp – Cần sạc!", "#ef4444"
        self.lbl_dv_status.setText(dv_txt)
        self.lbl_dv_status.setStyleSheet(
            "color: " + dv_col + "; font-size: 12px; background: transparent; border: none;"
        )

    # ═════════════════════════════════════════════════════════════════════
    # CAN DATA SLOTS
    # ═════════════════════════════════════════════════════════════════════

    def display_cells_1_2(self, c1: float, c2: float):
        self.cell_volts[0] = c1
        self.cell_volts[1] = c2

        # Page 0 mini-cards (ui_main labels)
        self.ui.txt_volt_cell1.setText(
            f"<span style='font-size:16px;font-weight:bold;color:white'>{c1:.3f}</span>"
            "<span style='font-size:10px;color:#a0aabf'> V</span>"
        )
        self.ui.txt_volt_cell2.setText(
            f"<span style='font-size:16px;font-weight:bold;color:white'>{c2:.3f}</span>"
            "<span style='font-size:10px;color:#a0aabf'> V</span>"
        )
        self.ui.bar_soc_cell1.setValue(int(max(0, min(100, (c1 - 3.0) / 1.2 * 100))))
        self.ui.bar_soc_cell2.setValue(int(max(0, min(100, (c2 - 3.0) / 1.2 * 100))))

        # Page 2 cell bars
        self._update_cell_page()

        # ── Active-alert: under-voltage ───────────────────────────────────
        for i, v in [(1, c1), (2, c2)]:
            self._set_alert(
                f"undervolt_c{i}", v < 3.0,
                f"Cell {i}: Điện áp thấp ({v:.3f} V < 3.0 V)"
            )

    def display_cells_3_4_etc(self, c3: float, c4: float, temp: float, fault: int, speed: int):
        self.cell_volts[2] = c3
        self.cell_volts[3] = c4
        self.current_speed = speed
        self.temp_live     = temp

        self.ui.txt_volt_cell3.setText(
            f"<span style='font-size:16px;font-weight:bold;color:white'>{c3:.3f}</span>"
            "<span style='font-size:10px;color:#a0aabf'> V</span>"
        )
        self.ui.txt_volt_cell4.setText(
            f"<span style='font-size:16px;font-weight:bold;color:white'>{c4:.3f}</span>"
            "<span style='font-size:10px;color:#a0aabf'> V</span>"
        )
        self.ui.bar_soc_cell3.setValue(int(max(0, min(100, (c3 - 3.0) / 1.2 * 100))))
        self.ui.bar_soc_cell4.setValue(int(max(0, min(100, (c4 - 3.0) / 1.2 * 100))))

        self.ui.bar_temperature.setValue(int(max(0, min(100, temp))))
        self.ui.txt_temperature.setText(
            f"<span style='font-size:14px;font-weight:bold;color:white'>{temp:.1f}</span>"
            "<span style='font-size:10px;color:#a0aabf'> °C</span>"
        )

        # Page 2 bars
        self._update_cell_page()

        # ── Active-alerts: cell under-voltage
        for i, v in [(3, c3), (4, c4)]:
            self._set_alert(
                f"undervolt_c{i}", v < 3.0,
                f"Cell {i}: Điện áp thấp ({v:.3f} V < 3.0 V)"
            )

        # ── Active-alert: over-temperature
        self._set_alert(
            "overtemp", temp > 45.0,
            f"Nhiệt độ quá cao ({temp:.1f} °C > 45 °C)", "#f97316"
        )

        # ── Floating alert banner: kích hoạt theo Fault_Code (req. 4) ────────
        # fault là byte nguyên từ CAN 0x104; 0 = không lỗi.
        if fault != 0:
            self.float_alert.show_fault(fault)
        else:
            self.float_alert.hide_fault()

    def display_pack_info(self, t_vol_can: float, t_cur: float):
        # ── Moving-average filter on current (req. 3) ──────────────────
        self._cur_buf.append(t_cur)
        t_cur_avg = sum(self._cur_buf) / len(self._cur_buf)

        # Use the smoothed value for everything below
        t_cur           = t_cur_avg
        self.t_cur_live = t_cur
        real_total_volt = sum(self.cell_volts)

        # ── pyqtgraph – voltage trend (Page 0) ──────────────────────────
        self.ptr += 1
        self.time_data.append(self.ptr)
        self.volt_data.append(real_total_volt)
        if len(self.time_data) > 60:
            self.time_data = self.time_data[1:]
            self.volt_data = self.volt_data[1:]
        self.data_line.setData(self.time_data, self.volt_data)

        # ── Coulomb counting + OCV (chống tụt áp ảo Surface Charge) ────
        current_time = time.time()
        dt = (current_time - self.last_time) / 3600.0
        self.last_time = current_time

        is_charging_now = t_cur < -0.5
        is_discharging  = t_cur > 0.5
        is_idle         = not is_charging_now and not is_discharging

        if is_charging_now:
            # ── ĐANG SẠC: Chỉ dùng Coulomb counting, KHÔNG dùng OCV
            # Tránh Surface Charge khiến điện áp cao ảo → SOC nhảy 100%
            self.soc -= (t_cur * dt) / self.capacity_ah * 100.0
            self.soc  = max(0.0, min(100.0, self.soc))
            self._is_charging     = True
            self._idle_start_time = None  # reset idle timer

        elif is_idle:
            # ── IDLE: Chờ điện áp ổn định ≥30s rồi mới dùng OCV
            if self._idle_start_time is None:
                self._idle_start_time = current_time
            idle_duration = current_time - self._idle_start_time

            if idle_duration >= 30.0:
                # Điện áp đã settle – dùng OCV lookup để hiệu chuẩn SOC
                ocv_soc = max(0.0, min(100.0,
                    (real_total_volt - 12.0) / 4.8 * 100.0))
                # Blend nhẹ để tránh nhảy đột ngột
                self.soc = self.soc * 0.9 + ocv_soc * 0.1
                self.soc = max(0.0, min(100.0, self.soc))
            # Nếu chưa đủ 30s → giữ nguyên SOC, không cập nhật
            self._is_charging = False

        else:
            # ── ĐANG XẢ: Coulomb counting + OCV khi dòng thấp
            self.soc -= (t_cur * dt) / self.capacity_ah * 100.0
            self.soc  = max(0.0, min(100.0, self.soc))
            self._is_charging     = False
            self._idle_start_time = None

        if int(current_time) % 10 == 0:
            self.save_data()

        # ── Fault-code floating alert (req. 4) ─────────────────────────
        # This is driven here because display_pack_info is where fault arrives.
        # (fault comes from display_cells_3_4_etc via the instance variable)
        # We store fault in that slot; check it here for the floating banner.

        # ── Active-alert: over-temperature
        # (already handled in display_cells_3_4_etc; banner is separate logic)

        # ── Charge limit enforcement ───────────────────────────────────────────
        if t_cur < -0.5 and self.soc >= self.charge_limit:
            # Simulate cut-off: zero the current (logic-level only)
            t_cur = 0.0
            self._set_alert(
                "charge_limit_hit", True,
                f"Đã đạt giới hạn sạc {self.charge_limit}% – dừng sạc", "#f59e0b"
            )
            self._log_event(
                f"Đã ngắt sạc theo cài đặt (Giới hạn {self.charge_limit}%)", "#f59e0b"
            )
        else:
            self._set_alert("charge_limit_hit", False,
                            f"Đã đạt giới hạn sạc {self.charge_limit}%")

        # ── Charging-started event log (debounced) ────────────────────────
        is_charging = t_cur < -0.5
        if is_charging and not self._charging_started_logged:
            self._charging_started_logged = True
            self._log_event("Bắt đầu sạc", "#34d399")
        elif not is_charging:
            self._charging_started_logged = False

        # ── Full-charge event ────────────────────────────────────────────
        if self.soc >= 100.0 and is_charging:
            self._log_event("Pin đã sạc đầy 100%", "#22c55e")

        # ── Peak current ─────────────────────────────────────────────────
        if abs(t_cur) > abs(self.peak_current):
            self.peak_current = t_cur

        # ── Range estimate ───────────────────────────────────────────────
        base_range     = (self.soc / 100.0) * 312.0
        penalty_factor = max(0.0, 1.0 - (self.current_speed / 160.0))
        instant_range  = base_range * penalty_factor
        self.smooth_range = self.smooth_range * 0.98 + instant_range * 0.02

        degradation = 100.0 - self.soh

        # ── SOH trend (Page 1) ───────────────────────────────────────────
        self.soh_data.append(self.soh)
        if len(self.soh_data) > 60:
            self.soh_data = self.soh_data[1:]
        self.soh_line.setData(list(range(len(self.soh_data))), self.soh_data)

        # ── Charging info (Page 0 Charging card) ─────────────────────────
        if is_charging:
            chg_kw = abs(t_cur) * real_total_volt / 1000.0
            soc_needed = self.charge_limit - self.soc
            if soc_needed > 0 and abs(t_cur) > 0.1:
                ah_needed   = soc_needed / 100.0 * self.capacity_ah
                hours_left  = ah_needed / abs(t_cur)
                h = int(hours_left)
                m = int((hours_left - h) * 60)
                self.lbl_time_to_full.setText(f"{h:02d} giờ {m:02d} phút")
            else:
                self.lbl_time_to_full.setText("Đã đầy")
            self.lbl_charge_power.setText(f"{chg_kw:.2f} kW")
            self.lbl_chg_status.setText("⚡ Đang sạc ...")
            self.lbl_chg_status.setStyleSheet(
                "color: #34d399; font-size: 11px; background: transparent; border: none;"
            )
        else:
            self.lbl_charge_power.setText("--")
            self.lbl_time_to_full.setText("--")
            self.lbl_chg_status.setText("● Không sạc")
            self.lbl_chg_status.setStyleSheet(
                "color: #475569; font-size: 11px; background: transparent; border: none;"
            )

        # ── Labels – Page 0 ──────────────────────────────────────────────
        self.ui.txt_total_volt.setText(
            f"<span style='font-size:16px;font-weight:bold;color:white'>"
            f"{real_total_volt:.1f}</span>"
            "<span style='font-size:10px;color:#a0aabf'> V</span>"
        )
        display_cur = max(0.0, t_cur)  # Không hiển thị dòng âm trên UI
        self.ui.txt_current.setText(
            f"<span style='font-size:16px;font-weight:bold;color:white'>"
            f"{display_cur:.1f}</span>"
            "<span style='font-size:10px;color:#a0aabf'> A</span>"
        )
        self.ui.txt_soc_total.setText(
            f"<span style='font-size:18px;font-weight:bold;color:white'>"
            f"{int(self.soc)}%</span>"
        )
        try:
            self.ui.txt_distance.setText(
                f"<span style='font-size:16px;font-weight:bold;color:#00e5ff'>"
                f"{int(self.smooth_range)}</span>"
                "<span style='font-size:10px;color:white'> km</span>"
            )
        except Exception:
            pass

        # ── Labels – Page 1 ──────────────────────────────────────────────
        self.ui.txt_soh_total.setText(
            f"<span style='font-size:14px;font-weight:bold;color:#00ff00'>"
            f"{self.soh:.1f}%</span>"
        )
        self.ui.bar_soh_total.setValue(int(self.soh))
        self.ui.txt_degradation.setText(
            f"<span style='font-size:14px;font-weight:bold;color:#00ff00'>"
            f"{degradation:.1f}%</span>"
        )
        # (Nội trở đã loại bỏ khỏi giao diện)
        self.lbl_peak_cur.setText(f"{abs(self.peak_current):.0f}")

        # ── Active-alert: over-current ────────────────────────────────────
        self._set_alert(
            "overcurrent", abs(t_cur) > 100.0,
            f"Dòng quá cao ({t_cur:.1f} A > 100 A)", "#ef4444"
        )



# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Set env vars BEFORE QApplication so the platform plugin reads them.
    os.environ.setdefault("QT_FONT_DPI", "80")
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "0")
    os.environ.setdefault("QT_SCALE_FACTOR", "1")

    app    = QApplication(sys.argv)
    window = MainWindow()   # pyqtgraph + bms_resources_rc imported here
    window.showFullScreen()
    sys.exit(app.exec_())