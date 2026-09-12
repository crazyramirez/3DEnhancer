from __future__ import annotations

import sys

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

from renderhuman.config import APP_NAME
from renderhuman.resources import resource_path
from renderhuman.ui.main_window import MainWindow
from renderhuman.ui.styles import (
    DARK_STYLESHEET,
    DarkDialogEventFilter,
    apply_windows_dark_title_bar,
)


def main() -> int:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("3DEnhancer")
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLESHEET)
    app.setWindowIcon(QIcon(str(resource_path("assets/app_icon.png"))))
    app.dark_dialog_filter = DarkDialogEventFilter(app)
    app.installEventFilter(app.dark_dialog_filter)

    window = MainWindow()
    window.show()
    apply_windows_dark_title_bar(window)
    QTimer.singleShot(0, lambda: apply_windows_dark_title_bar(window))
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
