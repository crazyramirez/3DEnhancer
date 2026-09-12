from __future__ import annotations

import sys

from PyQt5.QtCore import QEvent, QObject, QTimer
from PyQt5.QtWidgets import QDialog


def apply_windows_dark_title_bar(window) -> bool:
    """Use a dark native caption while keeping the normal Windows frame."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        set_attribute = ctypes.WinDLL("dwmapi").DwmSetWindowAttribute
        set_attribute.argtypes = (
            wintypes.HWND,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
        )
        set_attribute.restype = ctypes.c_long  # HRESULT
        handle = wintypes.HWND(int(window.winId()))

        enabled = ctypes.c_int(1)
        immersive_result = set_attribute(
            handle,
            20,  # DWMWA_USE_IMMERSIVE_DARK_MODE on current Windows versions.
            ctypes.byref(enabled),
            ctypes.sizeof(enabled),
        )
        if immersive_result != 0:
            immersive_result = set_attribute(
                handle,
                19,  # Compatibility value used by older Windows 10 builds.
                ctypes.byref(enabled),
                ctypes.sizeof(enabled),
            )

        # Windows 11 supports explicit caption, border and text colors. Older
        # versions simply ignore these attributes and retain immersive dark mode.
        for attribute, color in (
            (35, 0x0017110D),  # DWMWA_CAPTION_COLOR, RGB #0D1117 as COLORREF.
            (34, 0x003D3127),  # DWMWA_BORDER_COLOR, RGB #27313D as COLORREF.
            (36, 0x00FAF8F5),  # DWMWA_TEXT_COLOR, RGB #F5F8FA as COLORREF.
        ):
            value = wintypes.DWORD(color)
            set_attribute(handle, attribute, ctypes.byref(value), ctypes.sizeof(value))
        return immersive_result == 0
    except (AttributeError, OSError, TypeError, ValueError):
        return False


class DarkDialogEventFilter(QObject):
    """Apply the dark native frame to every Qt modal dialog when it opens."""

    def eventFilter(self, watched, event):  # noqa: N802 - Qt API
        if event.type() == QEvent.Show and isinstance(watched, QDialog):
            apply_windows_dark_title_bar(watched)
            QTimer.singleShot(0, lambda dialog=watched: apply_windows_dark_title_bar(dialog))
        return super().eventFilter(watched, event)


DARK_STYLESHEET = r"""
* {
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 10pt;
    color: #E7ECEF;
}

QMainWindow, QWidget#AppRoot {
    background: #0D1117;
}

QDialog, QMessageBox {
    background: #151B23;
}

QMessageBox QLabel {
    color: #E7ECEF;
    background: transparent;
}

QMessageBox QPushButton {
    min-width: 86px;
}

QFrame#Card, QFrame#StatusCard, QFrame#SettingsPanel {
    background: #151B23;
    border: 1px solid #27313D;
    border-radius: 12px;
}

QScrollArea#SettingsScroll, QScrollArea#SettingsScroll > QWidget {
    background: transparent;
    border: 0;
}

QLabel#AppTitle {
    font-size: 22pt;
    font-weight: 700;
    color: #F5F8FA;
}

QLabel#AppSubtitle, QLabel#Muted, QLabel#DetailLabel {
    color: #8F9BA8;
}

QLabel#SectionTitle {
    color: #99A6B3;
    font-size: 8pt;
    font-weight: 700;
}

QLabel#StageLabel {
    font-size: 13pt;
    font-weight: 650;
    color: #F5F8FA;
}

QLineEdit#ApiKeyInput {
    min-width: 285px;
    padding: 6px 9px;
}

QPushButton#ApiKeyButton {
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 9pt;
    font-weight: 650;
}

QPushButton#ApiKeyButton[ready="true"] {
    color: #72E2C3;
    background: #12372F;
    border: 1px solid #225B4D;
}

QPushButton#ApiKeyButton[ready="false"] {
    color: #FFB4A8;
    background: #3A211F;
    border: 1px solid #6B3631;
}

QPushButton#ApiKeyButton[ready="true"]:hover {
    background: #19483D;
    border-color: #31806B;
}

QPushButton#ApiKeyButton[ready="false"]:hover {
    background: #4A2926;
    border-color: #87463F;
}

QLabel#DropHint {
    background: #10161D;
    color: #92A0AD;
    border: 1px dashed #3A4A59;
    border-radius: 9px;
    padding: 12px;
}

QLabel#ImagePreview {
    background: #0A0E13;
    color: #778492;
    border: 1px solid #26313C;
    border-radius: 9px;
    padding: 4px;
}

QLabel#ImagePreview[interactive="true"]:hover,
QLabel#ImagePreview[interactive="true"]:focus {
    border: 1px solid #53B69F;
}

QDialog#ComparisonViewer {
    background: #10161D;
}

QLabel#ViewerEyebrow {
    color: #73DCC2;
    font-size: 8pt;
    font-weight: 700;
}

QLabel#ViewerFilename {
    color: #F1F6F8;
    font-size: 18pt;
    font-weight: 650;
}

QLabel#ViewerMuted, QLabel#ViewerHint {
    color: #8B9BAA;
    font-size: 9pt;
}

QLabel#ViewerAccent {
    color: #80E9CF;
    font-size: 9pt;
}

QLabel#ViewerZoom {
    color: #ECF5F4;
    font-size: 10pt;
    font-weight: 650;
}

QLabel#ViewerNotice {
    color: #D4C6A4;
    background: #25251F;
    border: 1px solid #3B3B2F;
    border-radius: 8px;
    padding: 10px 14px;
}

QFrame#ComparisonFrame {
    border: 1px solid #30414D;
    border-radius: 3px;
    background: #080C11;
}

QToolButton#ViewerMode {
    min-width: 78px;
    padding: 7px 16px;
    background: #161F29;
    border-color: #293844;
    color: #A4B2BE;
}

QToolButton#ViewerMode:checked {
    background: #173C34;
    border-color: #367F6D;
    color: #9DF2DB;
}

QToolButton#ViewerMode:hover {
    border-color: #62AD98;
}

QToolButton#ViewerMode:disabled {
    color: #596570;
    border-color: #26303A;
    background: #131A22;
}

QSlider#RevealSlider::groove:horizontal {
    height: 4px;
    background: #2B3944;
    border-radius: 2px;
}

QSlider#RevealSlider::sub-page:horizontal {
    background: #49B99E;
    border-radius: 2px;
}

QSlider#RevealSlider::handle:horizontal {
    background: #E9FFF7;
    border: 3px solid #55C6A9;
    width: 16px;
    height: 16px;
    margin: -9px 0;
    border-radius: 10px;
}

QSlider#RevealSlider::handle:horizontal:hover {
    background: #FFFFFF;
    border-color: #99FFE0;
}

QSlider#RevealSlider::handle:horizontal:disabled {
    background: #596973;
    border-color: #374A54;
}

QPushButton, QToolButton {
    background: #202936;
    color: #EAF0F3;
    border: 1px solid #334151;
    border-radius: 7px;
    padding: 7px 12px;
    min-height: 18px;
}

QPushButton:hover, QToolButton:hover {
    background: #293544;
    border-color: #496073;
}

QPushButton:pressed, QToolButton:pressed {
    background: #17202B;
}

QPushButton:disabled, QToolButton:disabled {
    color: #66727E;
    background: #171D25;
    border-color: #252E38;
}

QPushButton#PrimaryButton {
    background: #18A88D;
    color: #071511;
    border: 1px solid #25C3A4;
    font-size: 11pt;
    font-weight: 700;
    min-height: 26px;
    padding: 9px 20px;
}

QPushButton#PrimaryButton:hover {
    background: #27C0A2;
}

QPushButton#DangerButton {
    color: #FFB0A8;
    background: #2D1E20;
    border-color: #5C3034;
}

QPushButton#DangerButton:disabled {
    color: #6E5556;
    background: #1B171A;
    border-color: #332528;
}

QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #0F151C;
    color: #E6EBEF;
    border: 1px solid #303C49;
    border-radius: 7px;
    padding: 7px 9px;
    selection-background-color: #168A75;
}

QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #27B89D;
}

QComboBox::drop-down {
    border: 0;
    width: 25px;
}

QComboBox QAbstractItemView {
    background: #151B23;
    border: 1px solid #334151;
    selection-background-color: #1D6E61;
}

QCheckBox {
    spacing: 7px;
    color: #C8D0D7;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #4A5968;
    background: #0F151C;
}

QCheckBox::indicator:checked {
    background: #1CB397;
    border-color: #35D1B2;
}

QTableWidget {
    background: #10161D;
    alternate-background-color: #131A22;
    border: 1px solid #283440;
    border-radius: 8px;
    gridline-color: transparent;
    selection-background-color: #183E3A;
    selection-color: #F2F7F8;
    outline: 0;
}

QTableWidget::item {
    padding: 7px;
    border-bottom: 1px solid #202A34;
}

QHeaderView::section {
    background: #18212B;
    color: #98A6B4;
    border: 0;
    border-bottom: 1px solid #2D3945;
    padding: 7px;
    font-size: 8pt;
    font-weight: 700;
}

QProgressBar {
    background: #0C1218;
    border: 1px solid #2C3945;
    border-radius: 5px;
    text-align: center;
    color: #C6D0D8;
    min-height: 9px;
}

QProgressBar::chunk {
    background: #1CB397;
    border-radius: 4px;
}

QTabWidget::pane {
    background: transparent;
    border: 0;
    top: -1px;
}

QTabBar::tab {
    background: #121820;
    color: #8997A5;
    border: 1px solid #293540;
    padding: 8px 16px;
    min-width: 70px;
}

QTabBar::tab:selected {
    background: #1B262F;
    color: #75E0C5;
    border-bottom-color: #1CB397;
}

QSplitter::handle:horizontal {
    background: #0D1117;
    width: 18px;
}

QMenu {
    background: #151B23;
    color: #E7ECEF;
    border: 1px solid #354352;
    border-radius: 8px;
    padding: 6px;
}

QMenu::item {
    background: transparent;
    color: #E7ECEF;
    border-radius: 5px;
    padding: 8px 30px 8px 12px;
    margin: 1px 0;
}

QMenu::item:selected {
    background: #1D6E61;
    color: #FFFFFF;
}

QMenu::item:disabled {
    color: #687581;
}

QMenu::separator {
    height: 1px;
    background: #2C3743;
    margin: 5px 8px;
}

QScrollBar:vertical {
    background: #10161D;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #354452;
    min-height: 28px;
    border-radius: 5px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: #10161D;
    height: 10px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background: #354452;
    min-width: 28px;
    border-radius: 5px;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

QScrollBar::add-page, QScrollBar::sub-page {
    background: transparent;
}

QAbstractScrollArea::corner {
    background: #10161D;
}

QToolTip {
    background: #202A34;
    color: #E7ECEF;
    border: 1px solid #40505F;
    padding: 5px;
}
"""
