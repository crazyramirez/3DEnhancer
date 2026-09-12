from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QLabel

from renderhuman.i18n import render_text, tr


class ImagePreview(QLabel):
    def __init__(self, empty_text: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ImagePreview")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(360, 300)
        self._empty_text = empty_text
        self._source_pixmap = QPixmap()
        self._path: Path | None = None
        self._load_failed = False
        self.clear_image()

    @property
    def path(self) -> Path | None:
        return self._path

    def set_image(self, path: Path | str | None) -> None:
        if not path:
            self.clear_image()
            return
        candidate = Path(path)
        pixmap = QPixmap(str(candidate))
        if pixmap.isNull():
            self._load_failed = True
            self._source_pixmap = QPixmap()
            self._path = None
            self.setText(tr("No se pudo cargar la previsualización"))
            return
        self._path = candidate
        self._load_failed = False
        self._source_pixmap = pixmap
        self.setToolTip(str(candidate))
        self._render_scaled()

    def clear_image(self) -> None:
        self._load_failed = False
        self._path = None
        self._source_pixmap = QPixmap()
        self.setToolTip("")
        self.retranslate()

    def retranslate(self) -> None:
        if self._source_pixmap.isNull():
            self.setText(tr("No se pudo cargar la previsualización") if self._load_failed
                         else render_text(self._empty_text))

    def _render_scaled(self) -> None:
        if self._source_pixmap.isNull():
            return
        available = self.contentsRect().size()
        scaled = self._source_pixmap.scaled(
            max(1, available.width() - 12),
            max(1, available.height() - 12),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.setPixmap(scaled)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._render_scaled()

