from __future__ import annotations

import math
from pathlib import Path

from PyQt5.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QImageReader, QKeySequence, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QButtonGroup, QDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QShortcut, QSlider, QToolButton, QVBoxLayout, QWidget,
)

from renderhuman.i18n import render_text, tr
from renderhuman.ui.styles import apply_windows_dark_title_bar


class ComparisonCanvas(QWidget):
    """One image coordinate system for both sources, with a viewport reveal."""

    split_changed = pyqtSignal(float)
    zoom_changed = pyqtSignal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(280, 200)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.original = QPixmap()
        self.result = QPixmap()
        self.mode = "original"
        self.split = 0.5
        self.scale = 1.0
        self.pan = QPointF()
        self.fitting = True
        self._drag = None
        self._last_position = QPointF()
        self._space_down = False
        self.empty_message = tr("Cargando imágenes…")

    @property
    def has_result(self) -> bool:
        return not self.result.isNull()

    @property
    def ready(self) -> bool:
        return not self.original.isNull()

    def set_original(self, image: QPixmap) -> None:
        self.original = image
        self.fit()

    def set_result(self, image: QPixmap) -> None:
        self.result = image
        self.update()

    def set_mode(self, mode: str) -> None:
        self.mode = mode if self.has_result else "original"
        self.update()

    def set_split(self, fraction: float) -> None:
        self.split = max(0.0, min(1.0, fraction))
        self.split_changed.emit(self.split)
        self.update()

    def fit_scale(self) -> float:
        if not self.ready:
            return 1.0
        return min(max(1, self.width() - 64) / self.original.width(),
                   max(1, self.height() - 64) / self.original.height(), 1.0)

    def fit(self) -> None:
        self.fitting = True
        self.scale = self.fit_scale()
        self.pan = QPointF()
        self.zoom_changed.emit(self.scale)
        self.update()

    def image_rect(self) -> QRectF:
        width = self.original.width() * self.scale
        height = self.original.height() * self.scale
        center = QPointF(self.width() / 2, self.height() / 2) + self.pan
        return QRectF(center.x() - width / 2, center.y() - height / 2, width, height)

    def visible_image_rect(self) -> QRectF:
        return self.image_rect().intersected(QRectF(self.rect()))

    def divider_x(self) -> float:
        visible = self.visible_image_rect()
        return visible.left() + visible.width() * self.split

    def image_point(self, position: QPointF) -> QPointF:
        return (position - self.image_rect().topLeft()) / self.scale

    def _clamp_pan(self) -> None:
        horizontal = max(0, (self.original.width() * self.scale - (self.width() - 64)) / 2)
        vertical = max(0, (self.original.height() * self.scale - (self.height() - 64)) / 2)
        self.pan = QPointF(max(-horizontal, min(horizontal, self.pan.x())),
                           max(-vertical, min(vertical, self.pan.y())))

    def zoom_to(self, scale: float, anchor: QPointF | None = None) -> None:
        if not self.ready:
            return
        anchor = anchor if anchor is not None else QPointF(self.width() / 2, self.height() / 2)
        center = QPointF(self.width() / 2, self.height() / 2)
        relative = (anchor - center - self.pan) / self.scale
        self.scale = max(min(0.05, self.fit_scale()), min(8.0, scale))
        self.pan = anchor - center - relative * self.scale
        self._clamp_pan()
        self.fitting = False
        self.zoom_changed.emit(self.scale)
        self.update()

    def _over_divider(self, position: QPointF) -> bool:
        return (self.ready and self.has_result and self.mode == "compare"
                and self.visible_image_rect().adjusted(-14, 0, 14, 0).contains(position)
                and abs(position.x() - self.divider_x()) <= 16)

    def _move_divider(self, position: QPointF) -> None:
        visible = self.visible_image_rect()
        if visible.width() > 0:
            self.set_split((position.x() - visible.left()) / visible.width())

    def _update_cursor(self, position: QPointF) -> None:
        if self._drag == "pan":
            self.setCursor(Qt.ClosedHandCursor)
        elif self._over_divider(position) and not self._space_down:
            self.setCursor(Qt.SplitHCursor)
        elif self.ready:
            self.setCursor(Qt.OpenHandCursor)
        else:
            self.unsetCursor()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self.ready and event.button() in (Qt.LeftButton, Qt.MiddleButton):
            self.setFocus(Qt.MouseFocusReason)
            self._last_position = event.localPos()
            self._drag = ("split" if event.button() == Qt.LeftButton and not self._space_down
                          and self._over_divider(event.localPos()) else "pan")
            self._update_cursor(event.localPos())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag == "split":
            self._move_divider(event.localPos())
        elif self._drag == "pan":
            self.pan += event.localPos() - self._last_position
            self._clamp_pan()
            self.update()
        self._last_position = event.localPos()
        self._update_cursor(event.localPos())

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._drag == "split":
            self._move_divider(event.localPos())
        self._drag = None
        self._update_cursor(event.localPos())
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self.ready:
            self._drag = None
            if abs(self.scale - 1.0) < 0.01:
                self.fit()
            else:
                self.zoom_to(1.0, event.localPos())
            event.accept()

    def wheelEvent(self, event) -> None:  # noqa: N802
        if not self.ready:
            event.ignore()
            return
        delta = event.angleDelta().y() or event.pixelDelta().y()
        self.zoom_to(self.scale * math.pow(1.0015, delta), event.posF())
        event.accept()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Space:
            self._space_down = True
            self.setCursor(Qt.OpenHandCursor)
            event.accept()
        elif event.key() in (Qt.Key_Left, Qt.Key_Right) and self.mode == "compare":
            self.set_split(self.split + (-0.01 if event.key() == Qt.Key_Left else 0.01))
            event.accept()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Space:
            self._space_down = False
        super().keyReleaseEvent(event)

    def focusOutEvent(self, event) -> None:  # noqa: N802
        self._space_down = False
        self._drag = None
        super().focusOutEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self.fitting:
            self.fit()
        else:
            self._clamp_pan()

    def _badge(self, painter: QPainter, text: str, right: bool = False) -> None:
        font = QFont(self.font())
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        width = painter.fontMetrics().horizontalAdvance(text) + 26
        rect = QRectF(self.width() - width - 20 if right else 20, 18, width, 30)
        painter.setPen(QPen(QColor("#35424C"), 1))
        painter.setBrush(QColor(13, 19, 25, 228))
        painter.drawRoundedRect(rect, 7, 7)
        painter.setPen(QColor("#80E9CF") if right else QColor("#EFF5F7"))
        painter.drawText(rect, Qt.AlignCenter, text)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#080C11"))
        painter.setPen(QColor("#111820"))
        for x in range(0, self.width(), 32):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 32):
            painter.drawLine(0, y, self.width(), y)
        if not self.ready:
            painter.setPen(QColor("#A0AEBB"))
            painter.drawText(self.rect().adjusted(32, 32, -32, -32),
                             Qt.AlignCenter | Qt.TextWordWrap, render_text(self.empty_message))
            return
        target = self.image_rect()
        painter.fillRect(target.adjusted(-5, -5, 5, 5), QColor(0, 0, 0, 90))
        painter.setRenderHint(QPainter.SmoothPixmapTransform, self.scale < 1.0)
        base = self.result if self.mode == "result" and self.has_result else self.original
        painter.drawPixmap(target, base, QRectF(base.rect()))
        if self.mode == "compare" and self.has_result:
            split_x = self.divider_x()
            painter.save()
            painter.setClipRect(QRectF(split_x, 0, self.width() - split_x, self.height()))
            painter.drawPixmap(target, self.result, QRectF(self.result.rect()))
            painter.restore()
            visible = self.visible_image_rect()
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(QColor(0, 0, 0, 90), 5))
            painter.drawLine(QPointF(split_x, visible.top()), QPointF(split_x, visible.bottom()))
            painter.setPen(QPen(QColor("#F4FAFC"), 2))
            painter.drawLine(QPointF(split_x, visible.top()), QPointF(split_x, visible.bottom()))
            center = QPointF(split_x, visible.center().y())
            handle = QRectF(center.x() - 20, center.y() - 26, 40, 52)
            painter.setBrush(QColor("#F3FAF8"))
            painter.setPen(QPen(QColor("#FFFFFF"), 1))
            painter.drawRoundedRect(handle, 19, 19)
            painter.setPen(QPen(QColor("#12372F"), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            for direction in (-1, 1):
                tip = center + QPointF(direction * 10, 0)
                painter.drawLine(tip, center + QPointF(direction * 5, -5))
                painter.drawLine(tip, center + QPointF(direction * 5, 5))
        painter.setRenderHint(QPainter.Antialiasing)
        if self.mode != "result":
            self._badge(painter, tr("ANTES · ORIGINAL"))
        if self.mode != "original" and self.has_result:
            self._badge(painter, tr("DESPUÉS · RESULTADO"), right=True)


class ComparisonViewer(QDialog):
    def __init__(self, source_path: Path, result_path: Path | None = None, parent=None) -> None:
        super().__init__(parent)
        self.source_path = Path(source_path)
        self.result_path = Path(result_path) if result_path else None
        self._result_load_failed = False
        self._loading = True
        self._was_maximized = False
        self.setObjectName("ComparisonViewer")
        self.setWindowModality(Qt.WindowModal)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)
        screen = parent.screen() if parent else QApplication.primaryScreen()
        available = screen.availableGeometry()
        self.setMinimumSize(min(800, available.width()), min(560, available.height()))
        self.resize(min(1600, int(available.width() * .93)), min(1080, int(available.height() * .92)))
        self._build_ui()
        self._shortcuts = []
        for key, action in (("+", self.zoom_in), ("=", self.zoom_in), ("-", self.zoom_out),
                            ("0", self.canvas.fit), ("1", lambda: self.canvas.zoom_to(1.0)),
                            ("F", self.toggle_fullscreen)):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(action)
            self._shortcuts.append(shortcut)
        self.retranslate()
        self._load_timer = QTimer(self)
        self._load_timer.setSingleShot(True)
        self._load_timer.timeout.connect(self._load_images)
        self._load_timer.start(0)

    def _tool(self, text: str, action) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(action)
        button.setAutoRaise(False)
        return button

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(14)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        self.eyebrow = QLabel()
        self.eyebrow.setObjectName("ViewerEyebrow")
        self.filename_label = QLabel(self.source_path.name)
        self.filename_label.setObjectName("ViewerFilename")
        self.filename_label.setTextFormat(Qt.PlainText)
        self.filename_label.setWordWrap(True)
        self.filename_label.setToolTip(str(self.source_path))
        titles.addWidget(self.eyebrow)
        titles.addWidget(self.filename_label)
        header.addLayout(titles, 1)
        self.close_button = QPushButton()
        self.close_button.setObjectName("ViewerClose")
        self.close_button.setAutoDefault(False)
        self.close_button.clicked.connect(lambda: self.done(QDialog.Accepted))
        header.addWidget(self.close_button, 0, Qt.AlignTop)
        layout.addLayout(header)

        mode_row = QHBoxLayout()
        self.modes = QButtonGroup(self)
        self.mode_buttons = {}
        for mode in ("original", "compare", "result"):
            button = self._tool("", lambda checked=False, mode=mode: self.set_mode(mode))
            button.setObjectName("ViewerMode")
            button.setCheckable(True)
            self.modes.addButton(button)
            self.mode_buttons[mode] = button
            mode_row.addWidget(button)
        self.mode_buttons["original"].setChecked(True)
        mode_row.addStretch(1)
        self.dimensions_label = QLabel()
        self.dimensions_label.setObjectName("ViewerMuted")
        self.dimensions_label.setMinimumWidth(160)
        self.dimensions_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        mode_row.addWidget(self.dimensions_label)
        layout.addLayout(mode_row)

        self.notice = QLabel()
        self.notice.setObjectName("ViewerNotice")
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        frame = QFrame()
        frame.setObjectName("ComparisonFrame")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(1, 1, 1, 1)
        self.canvas = ComparisonCanvas()
        frame_layout.addWidget(self.canvas)
        layout.addWidget(frame, 1)

        reveal_row = QHBoxLayout()
        reveal_row.setSpacing(14)
        self.before_label = QLabel()
        self.before_label.setObjectName("ViewerMuted")
        self.after_label = QLabel()
        self.after_label.setObjectName("ViewerAccent")
        self.reveal_slider = QSlider(Qt.Horizontal)
        self.reveal_slider.setObjectName("RevealSlider")
        self.reveal_slider.setMinimumHeight(28)
        self.reveal_slider.setRange(0, 1000)
        self.reveal_slider.setValue(500)
        self.reveal_slider.setSingleStep(10)
        self.reveal_slider.setPageStep(100)
        self.reveal_slider.valueChanged.connect(lambda value: self.canvas.set_split(value / 1000))
        self.canvas.split_changed.connect(self._update_split)
        self.center_button = self._tool("50 / 50", lambda: self.canvas.set_split(.5))
        reveal_row.addWidget(self.before_label)
        reveal_row.addWidget(self.reveal_slider, 1)
        reveal_row.addWidget(self.after_label)
        reveal_row.addWidget(self.center_button)
        layout.addLayout(reveal_row)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        self.minus_button = self._tool("−", self.zoom_out)
        self.zoom_label = QLabel("100%")
        self.zoom_label.setObjectName("ViewerZoom")
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.zoom_label.setFixedWidth(66)
        self.plus_button = self._tool("+", self.zoom_in)
        self.fit_button = self._tool("", self.canvas.fit)
        self.actual_button = self._tool("100%", lambda: self.canvas.zoom_to(1.0))
        self.fullscreen_button = self._tool("", self.toggle_fullscreen)
        controls.addWidget(self.minus_button)
        controls.addWidget(self.zoom_label)
        controls.addWidget(self.plus_button)
        controls.addSpacing(12)
        controls.addWidget(self.fit_button)
        controls.addWidget(self.actual_button)
        controls.addStretch(1)
        controls.addWidget(self.fullscreen_button)
        layout.addLayout(controls)
        self.hint = QLabel()
        self.hint.setObjectName("ViewerHint")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self.canvas.zoom_changed.connect(self._update_zoom)

    @staticmethod
    def _read_pixmap(path: Path) -> QPixmap:
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        return QPixmap.fromImage(reader.read())

    def _load_images(self) -> None:
        self.canvas.set_original(self._read_pixmap(self.source_path))
        self._loading = False
        if not self.canvas.ready:
            self.canvas.empty_message = tr("No se pudo abrir la imagen original.")
        if self.result_path:
            self.set_result_path(self.result_path)
        self._refresh_controls()
        self.canvas.setFocus(Qt.OtherFocusReason)

    def set_result_path(self, path: Path) -> None:
        if self.result_path == Path(path) and self.canvas.has_result:
            return
        had_result = self.canvas.has_result
        self.result_path = Path(path)
        self.canvas.set_result(self._read_pixmap(self.result_path))
        self._result_load_failed = not self.canvas.has_result
        if not had_result and self.canvas.has_result:
            self.set_mode("compare")
        elif not self.canvas.has_result:
            self.set_mode("original")
        self._refresh_controls()

    def set_mode(self, mode: str) -> None:
        self.canvas.set_mode(mode)
        self.mode_buttons[self.canvas.mode].setChecked(True)
        self._refresh_controls()

    def _refresh_controls(self) -> None:
        ready = self.canvas.ready
        compare = ready and self.canvas.has_result
        self.mode_buttons["original"].setEnabled(ready)
        self.mode_buttons["compare"].setEnabled(compare)
        self.mode_buttons["result"].setEnabled(compare)
        self.reveal_slider.setEnabled(compare and self.canvas.mode == "compare")
        self.center_button.setEnabled(self.reveal_slider.isEnabled())
        for button in (self.minus_button, self.plus_button, self.fit_button, self.actual_button):
            button.setEnabled(ready)
        if ready:
            self.dimensions_label.setText(f"{self.canvas.original.width():,} × {self.canvas.original.height():,} px".replace(",", " "))
        self.notice.setVisible(not compare)
        if self._loading:
            self.notice.setText(tr("Cargando imágenes…"))
        elif not ready:
            self.notice.setText(tr("No se pudo abrir la imagen original."))
        elif self._result_load_failed:
            self.notice.setText(tr("No se pudo abrir el resultado. Puedes explorar el original."))
        else:
            self.notice.setText(tr("Resultado pendiente. Puedes explorar el original; la comparación aparecerá cuando esté listo."))
        self._update_zoom(self.canvas.scale)
        self.layout().activate()

    def _update_split(self, fraction: float) -> None:
        self.reveal_slider.blockSignals(True)
        self.reveal_slider.setValue(round(fraction * 1000))
        self.reveal_slider.blockSignals(False)

    def _update_zoom(self, scale: float) -> None:
        self.zoom_label.setText(f"{scale * 100:.0f}%")
        self.plus_button.setEnabled(self.canvas.ready and scale < 8.0 - .001)
        self.minus_button.setEnabled(self.canvas.ready and scale > min(.05, self.canvas.fit_scale()) + .001)

    def zoom_in(self) -> None:
        self.canvas.zoom_to(self.canvas.scale * 1.25)

    def zoom_out(self) -> None:
        self.canvas.zoom_to(self.canvas.scale / 1.25)

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showMaximized() if self._was_maximized else self.showNormal()
        else:
            self._was_maximized = self.isMaximized()
            self.showFullScreen()
        self.retranslate()

    def reject(self) -> None:
        if self.isFullScreen():
            self.toggle_fullscreen()
        else:
            super().reject()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        apply_windows_dark_title_bar(self)

    def retranslate(self) -> None:
        self.setWindowTitle(tr("Comparador antes y después"))
        self.eyebrow.setText(tr("ESTUDIO DE COMPARACIÓN"))
        self.close_button.setText(tr("Cerrar · Esc"))
        self.mode_buttons["original"].setText("Original")
        self.mode_buttons["compare"].setText(tr("Comparar"))
        self.mode_buttons["result"].setText(tr("Resultado"))
        self.before_label.setText(tr("Antes"))
        self.after_label.setText(tr("Después"))
        self.fit_button.setText(tr("Ajustar"))
        self.fit_button.setToolTip(tr("Ajustar la imagen al visor · 0"))
        self.actual_button.setToolTip(tr("Ver al 100% · 1"))
        self.plus_button.setToolTip(tr("Acercar · +"))
        self.minus_button.setToolTip(tr("Alejar · −"))
        self.center_button.setToolTip(tr("Centrar la comparación"))
        self.fullscreen_button.setText(tr("Salir de pantalla completa") if self.isFullScreen() else tr("Pantalla completa"))
        self.fullscreen_button.setToolTip(tr("Alternar pantalla completa · F"))
        self.hint.setText(tr("Rueda para ampliar · Arrastra para desplazarte · Doble clic para alternar 100% y ajustar"))
        self.reveal_slider.setAccessibleName(tr("Deslizador antes y después"))
        self.reveal_slider.setToolTip(tr("Arrastra para comparar; usa las flechas para ajustar con precisión."))
        self.canvas.setAccessibleName(tr("Comparador antes y después"))
        self._refresh_controls()
        self.canvas.update()
