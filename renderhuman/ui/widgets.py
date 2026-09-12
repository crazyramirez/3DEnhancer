from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QImageReader, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QLabel

from renderhuman.i18n import render_text, tr


class ImagePreview(QLabel):
    activated = pyqtSignal()

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
        reader = QImageReader(str(candidate))
        reader.setAutoTransform(True)
        pixmap = QPixmap.fromImage(reader.read())
        if pixmap.isNull():
            self._load_failed = True
            self._source_pixmap = QPixmap()
            self._path = None
            self.setText(tr("No se pudo cargar la previsualización"))
            self._refresh_interaction()
            return
        self._path = candidate
        self._load_failed = False
        self._source_pixmap = pixmap
        self.setToolTip(str(candidate))
        self._refresh_interaction()
        self._render_scaled()

    def clear_image(self) -> None:
        self._load_failed = False
        self._path = None
        self._source_pixmap = QPixmap()
        self.setToolTip("")
        self._refresh_interaction()
        self.retranslate()

    def retranslate(self) -> None:
        self._refresh_interaction()
        if self._source_pixmap.isNull():
            self.setText(tr("No se pudo cargar la previsualización") if self._load_failed
                         else render_text(self._empty_text))
        self.update()

    def _refresh_interaction(self) -> None:
        interactive = self._path is not None
        self.setCursor(Qt.PointingHandCursor if interactive else Qt.ArrowCursor)
        self.setFocusPolicy(Qt.StrongFocus if interactive else Qt.NoFocus)
        self.setAccessibleName(tr("Abrir comparador antes y después") if interactive else render_text(self._empty_text))
        if interactive:
            self.setToolTip(tr("Haz clic para comparar, ampliar y explorar la imagen."))
        else:
            self.setToolTip("")
        if self.property("interactive") != interactive:
            self.setProperty("interactive", interactive)
            self.style().unpolish(self)
            self.style().polish(self)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self._path and self.rect().contains(event.pos()):
            self.activated.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if self._path and event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.activated.emit()
            event.accept()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        if not self._path:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        text = tr("Abrir visor")
        width = painter.fontMetrics().horizontalAdvance(text) + 44
        pill = QRectF(self.width() - width - 16, self.height() - 48, width, 32)
        painter.setBrush(QColor(15, 27, 32, 235))
        painter.setPen(QPen(QColor("#438677"), 1))
        painter.drawRoundedRect(pill, 8, 8)
        painter.setPen(QColor("#B7F4E3"))
        painter.drawText(pill.adjusted(29, 0, -8, 0), Qt.AlignVCenter | Qt.AlignLeft, text)
        x, y = pill.left() + 11, pill.top() + 10
        painter.drawLine(int(x), int(y + 5), int(x), int(y))
        painter.drawLine(int(x), int(y), int(x + 5), int(y))
        painter.drawLine(int(x + 12), int(y + 7), int(x + 12), int(y + 12))
        painter.drawLine(int(x + 12), int(y + 12), int(x + 7), int(y + 12))

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

