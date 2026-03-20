import sys
import time
from PySide6.QtWidgets import (QWidget, QPushButton, QLabel, QHBoxLayout, 
                               QVBoxLayout, QFrame, QGraphicsDropShadowEffect,
                               QSizePolicy)
from PySide6.QtCore import Qt, QPropertyAnimation, QRect, QEasingCurve, Signal, Property, QPoint, QSize
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QLinearGradient
from stylesheet import SURFACE_3, BORDER, ACCENT, TEXT_PRIMARY, TEXT_SECONDARY, SUCCESS, SURFACE_2, SURFACE_1

class ToggleSwitch(QWidget):
    clicked = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 18)
        self._checked = False
        self._knob_pos = 2
        self.animation = QPropertyAnimation(self, b"knob_pos")
        self.animation.setDuration(150)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)

    @Property(int)
    def knob_pos(self):
        return self._knob_pos

    @knob_pos.setter
    def knob_pos(self, pos):
        self._knob_pos = pos
        self.update()

    def setChecked(self, checked):
        if self._checked == checked: return
        self._checked = checked
        self.animation.stop()
        self.animation.setEndValue(20 if checked else 2)
        self.animation.start()
        self.update()

    def isChecked(self):
        return self._checked

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)
            self.clicked.emit(self._checked)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        # Track
        color = QColor(ACCENT) if self._checked else QColor(SURFACE_3)
        p.setBrush(color)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, self.width(), self.height(), 9, 9)
        
        # Knob
        p.setBrush(QColor("white"))
        p.drawEllipse(self._knob_pos, 2, 14, 14)

class ChipWidget(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setFixedHeight(28)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)
        self.update_style()
        self.toggled.connect(self.update_style)

    def update_style(self):
        if self.isChecked():
            self.setStyleSheet(f"""
                ChipWidget {{
                    background-color: #7a2a1f;
                    border: 1px solid {ACCENT};
                    color: {ACCENT};
                    border-radius: 14px;
                    padding: 0 12px;
                    font-weight: bold;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                ChipWidget {{
                    background-color: {SURFACE_3};
                    border: 1px solid {BORDER};
                    color: {TEXT_SECONDARY};
                    border-radius: 14px;
                    padding: 0 12px;
                }}
                ChipWidget:hover {{
                    background-color: {SURFACE_2};
                }}
            """)

class DownloadButton(QPushButton):
    def __init__(self, text="Download Selected", parent=None):
        super().__init__(text, parent)
        self.setFixedHeight(48)
        self._progress = 0
        self._is_downloading = False
        self._status_text = text
        self.setCursor(Qt.PointingHandCursor)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(46, 204, 113, 85)) # SUCCESS with alpha
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

    def setProgress(self, current, total):
        self._is_downloading = True
        self._progress = (current / total) if total > 0 else 0
        self._status_text = f"Downloading... {current} / {total} chapters"
        self.update()

    def reset(self):
        self._is_downloading = False
        self._progress = 0
        self._status_text = "Download Selected"
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        radius = 8
        
        if not self.isEnabled():
            p.setBrush(QColor(SURFACE_3))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(rect, radius, radius)
            p.setPen(QColor("#55556a"))
            p.drawText(rect, Qt.AlignCenter, self._status_text)
            return

        # Background Gradient
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0, QColor("#2ecc71"))
        grad.setColorAt(1, QColor("#27ae60"))
        
        p.setBrush(grad)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(rect, radius, radius)
        
        if self._is_downloading:
            # Progress Overlay
            p.setBrush(QColor(0, 0, 0, 40))
            p.drawRoundedRect(0, 0, int(self.width() * self._progress), self.height(), radius, radius)
            
        p.setPen(QColor("white"))
        font = p.font()
        font.setBold(True)
        font.setPixelSize(15)
        p.setFont(font)
        p.drawText(rect, Qt.AlignCenter, self._status_text)

class StatusBadge(QLabel):
    def __init__(self, text, status_type="info", parent=None):
        super().__init__(text.upper(), parent)
        self.setFixedHeight(22)
        self.setContentsMargins(10, 0, 10, 0)
        self.setObjectName("Badge")
        
        colors = {
            "ongoing": ("#7a5a10", "#f39c12"),
            "completed": ("#1e5a2d", "#2ecc71"),
            "hiatus": ("#1a4a6e", "#3498db"),
            "info": ("#252535", "#8a8aa0")
        }
        
        bg, fg = colors.get(status_type.lower(), colors["info"])
        self.setStyleSheet(f"background-color: {bg}; color: {fg}; border-radius: 11px; font-size: 11px; font-weight: bold;")

class SegmentedControl(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ControlsBar")
        self.setFixedHeight(32)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.setStyleSheet(f"background-color: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 6px;")

    def addButton(self, text):
        btn = QPushButton(text)
        btn.setFixedHeight(30)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-right: 1px solid {BORDER};
                border-radius: 0px;
                color: {TEXT_PRIMARY};
                font-size: 12px;
            }}
            QPushButton:hover {{ background-color: {SURFACE_3}; }}
        """)
        self.layout.addWidget(btn)
        return btn

class SkeletonWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self._gradient_pos = 0
        self.animation = QPropertyAnimation(self, b"gradient_pos")
        self.animation.setDuration(1500)
        self.animation.setStartValue(0)
        self.animation.setEndValue(100)
        self.animation.setLoopCount(-1)
        self.animation.start()

    @Property(int)
    def gradient_pos(self):
        return self._gradient_pos

    @gradient_pos.setter
    def gradient_pos(self, pos):
        self._gradient_pos = pos
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        grad = QLinearGradient(0, 0, self.width(), 0)
        pos = self._gradient_pos / 100.0
        
        grad.setColorAt(max(0, pos - 0.2), QColor(SURFACE_2))
        grad.setColorAt(pos, QColor(SURFACE_3))
        grad.setColorAt(min(1, pos + 0.2), QColor(SURFACE_2))
        
        p.setBrush(grad)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(self.rect(), 4, 4)

class WelcomeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)

        # Icon or Large Text
        self.icon_label = QLabel("📚")
        self.icon_label.setStyleSheet("font-size: 64px;")
        self.icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.icon_label)

        self.title = QLabel("Welcome to MultiMangaScraper")
        self.title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {TEXT_PRIMARY};")
        self.title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title)

        self.subtitle = QLabel("Search for a manga or select one from your library to begin.")
        self.subtitle.setStyleSheet(f"font-size: 14px; color: {TEXT_SECONDARY};")
        self.subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.subtitle)

        # Some quick stats or tips
        tips_layout = QHBoxLayout()
        tips_layout.setAlignment(Qt.AlignCenter)
        tips_layout.setSpacing(30)
        
        tips = [
            ("🔍", "Global Search"),
            ("⚡", "Fast Downloads"),
            ("📁", "Library Sync")
        ]
        
        for icon, text in tips:
            tip_v = QVBoxLayout()
            t_icon = QLabel(icon)
            t_icon.setStyleSheet("font-size: 24px;")
            t_icon.setAlignment(Qt.AlignCenter)
            t_text = QLabel(text)
            t_text.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {TEXT_SECONDARY}; text-transform: uppercase;")
            t_text.setAlignment(Qt.AlignCenter)
            tip_v.addWidget(t_icon)
            tip_v.addWidget(t_text)
            tips_layout.addLayout(tip_v)
            
        layout.addSpacing(20)
        layout.addLayout(tips_layout)

class LoadingPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        
        self.loading_label = QLabel("Searching...")
        self.loading_label.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {ACCENT};")
        self.loading_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.loading_label)
        
        # Header skeleton
        header = QHBoxLayout()
        cover = SkeletonWidget()
        cover.setFixedSize(160, 228)
        header.addWidget(cover)
        
        info = QVBoxLayout()
        title = SkeletonWidget()
        title.setFixedHeight(32)
        desc1 = SkeletonWidget()
        desc1.setFixedHeight(16)
        desc2 = SkeletonWidget()
        desc2.setFixedHeight(16)
        info.addWidget(title)
        info.addWidget(desc1)
        info.addWidget(desc2)
        info.addStretch()
        header.addLayout(info)
        layout.addLayout(header)
        
        # Chapter list skeleton
        for _ in range(5):
            item = SkeletonWidget()
            item.setFixedHeight(40)
            layout.addWidget(item)
            
        layout.addStretch()
