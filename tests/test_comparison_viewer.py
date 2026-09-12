from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PyQt5.QtCore import QPoint, QPointF, QSettings, Qt
from PyQt5.QtGui import QColor, QMouseEvent, QPixmap, QWheelEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QDialog

from renderhuman.i18n import apply_language
from renderhuman.services.pipeline import PipelineItemResult
from renderhuman.ui.comparison_viewer import ComparisonCanvas, ComparisonViewer
from renderhuman.ui.main_window import MainWindow
from renderhuman.ui.widgets import ImagePreview


class ComparisonViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / "original.png"
        self.result = self.root / "original_humanized.png"
        Image.new("RGB", (1000, 800), "red").save(self.source)
        Image.new("RGB", (1000, 800), "blue").save(self.result)
        apply_language("es", self.app)
        self.addCleanup(lambda: apply_language("system", self.app))

    def canvas(self) -> ComparisonCanvas:
        canvas = ComparisonCanvas()
        canvas.resize(800, 600)
        canvas.set_original(QPixmap(str(self.source)))
        canvas.set_result(QPixmap(str(self.result)))
        canvas.set_mode("compare")
        canvas.show()
        self.app.processEvents()
        self.addCleanup(canvas.close)
        return canvas

    def viewer(self, result: Path | None = None) -> ComparisonViewer:
        viewer = ComparisonViewer(self.source, result)
        # Tests own the object until cleanup; production deletes on close.
        viewer.setAttribute(Qt.WA_DeleteOnClose, False)
        viewer.resize(1000, 760)
        viewer.show()
        self.app.processEvents()
        self.app.processEvents()
        self.addCleanup(viewer.close)
        return viewer

    def test_reveal_and_modes_show_the_correct_pixels(self) -> None:
        canvas = self.canvas()
        for split, left, right in ((.5, "red", "blue"), (0, "blue", "blue"), (1, "red", "red")):
            with self.subTest(split=split):
                canvas.set_split(split)
                painted = canvas.grab().toImage()
                self.assertEqual(painted.pixelColor(200, 250), QColor(left))
                self.assertEqual(painted.pixelColor(600, 250), QColor(right))
        canvas.set_mode("original")
        self.assertEqual(canvas.grab().toImage().pixelColor(600, 250), QColor("red"))
        canvas.set_mode("result")
        self.assertEqual(canvas.grab().toImage().pixelColor(200, 250), QColor("blue"))

    def test_zoom_keeps_cursor_anchor_and_clamps_panning(self) -> None:
        canvas = self.canvas()
        canvas.zoom_to(1.0)
        anchor = QPointF(470, 340)
        before = canvas.image_point(anchor)
        canvas.zoom_to(2.0, anchor)
        after = canvas.image_point(anchor)
        self.assertAlmostEqual(before.x(), after.x())
        self.assertAlmostEqual(before.y(), after.y())
        canvas.pan = QPointF(100000, -100000)
        canvas._clamp_pan()
        self.assertTrue(canvas.image_rect().contains(QPointF(400, 300)))
        canvas.zoom_to(100)
        self.assertEqual(canvas.scale, 8.0)
        canvas.fit()
        self.assertEqual(canvas.pan, QPointF())
        self.assertTrue(canvas.fitting)

    def test_dragging_divider_and_keyboard_slider_stay_in_sync(self) -> None:
        viewer = self.viewer(self.result)
        canvas = viewer.canvas
        start = QPoint(round(canvas.divider_x()), round(canvas.visible_image_rect().center().y()))
        target = QPointF(canvas.visible_image_rect().left() + .75 * canvas.visible_image_rect().width(), start.y())
        QTest.mousePress(canvas, Qt.LeftButton, pos=start)
        QApplication.sendEvent(canvas, QMouseEvent(QMouseEvent.MouseMove, target, Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
        QApplication.sendEvent(canvas, QMouseEvent(QMouseEvent.MouseButtonRelease, target, Qt.LeftButton, Qt.NoButton, Qt.NoModifier))
        self.assertAlmostEqual(canvas.split, .75, places=2)
        self.assertAlmostEqual(viewer.reveal_slider.value(), 750, delta=1)
        viewer.reveal_slider.setFocus()
        QTest.keyClick(viewer.reveal_slider, Qt.Key_Home)
        self.assertEqual(canvas.split, 0)
        QTest.keyClick(viewer.reveal_slider, Qt.Key_End)
        self.assertEqual(canvas.split, 1)
        viewer.center_button.click()
        self.assertEqual(canvas.split, .5)

    def test_pending_result_arrives_without_resetting_zoom(self) -> None:
        viewer = self.viewer()
        self.assertEqual(viewer.canvas.mode, "original")
        self.assertFalse(viewer.reveal_slider.isEnabled())
        self.assertTrue(viewer.notice.isVisible())
        viewer.canvas.zoom_to(2.0)
        viewer.canvas.pan = QPointF(50, 30)
        viewer.set_result_path(self.result)
        self.assertEqual(viewer.canvas.mode, "compare")
        self.assertEqual(viewer.canvas.scale, 2.0)
        self.assertEqual(viewer.canvas.pan, QPointF(50, 30))
        self.assertTrue(viewer.reveal_slider.isEnabled())
        self.assertFalse(viewer.notice.isVisible())
        apply_language("en", self.app)
        viewer.retranslate()
        self.assertEqual(viewer.mode_buttons["compare"].text(), "Compare")
        self.assertEqual(viewer.canvas.scale, 2.0)

    def test_wheel_double_click_and_fullscreen_escape(self) -> None:
        viewer = self.viewer(self.result)
        canvas = viewer.canvas
        initial = canvas.scale
        center = QPointF(canvas.width() / 2, canvas.height() / 2)
        QApplication.sendEvent(canvas, QWheelEvent(
            center, center, QPoint(), QPoint(0, 120), Qt.NoButton,
            Qt.NoModifier, Qt.NoScrollPhase, False,
        ))
        self.assertGreater(canvas.scale, initial)
        QTest.mouseDClick(canvas, Qt.LeftButton, pos=center.toPoint())
        self.assertEqual(canvas.scale, 1.0)
        QTest.mouseDClick(canvas, Qt.LeftButton, pos=center.toPoint())
        self.assertTrue(canvas.fitting)
        viewer.toggle_fullscreen()
        self.assertTrue(viewer.isFullScreen())
        viewer.reject()
        self.assertFalse(viewer.isFullScreen())
        self.assertTrue(viewer.isVisible())
        viewer.reject()
        self.assertFalse(viewer.isVisible())

    def test_unreadable_files_disable_comparison_without_crashing(self) -> None:
        viewer = self.viewer(self.root / "missing.png")
        self.assertFalse(viewer.reveal_slider.isEnabled())
        self.assertIn("No se pudo abrir el resultado", viewer.notice.text())
        viewer.source_path = self.root / "missing-original.png"
        viewer._load_images()
        self.assertFalse(viewer.canvas.ready)
        self.assertFalse(viewer.plus_button.isEnabled())

    def test_orientation_matches_in_thumbnail_and_full_view(self) -> None:
        source = self.root / "rotated.jpg"
        image = Image.new("RGB", (100, 60), "red")
        exif = image.getexif()
        exif[274] = 6
        image.save(source, exif=exif)
        preview = ImagePreview("empty")
        self.addCleanup(preview.close)
        preview.set_image(source)
        full = ComparisonViewer._read_pixmap(source)
        self.assertEqual((full.width(), full.height()), (60, 100))
        self.assertEqual(preview._source_pixmap.size(), full.size())
        activated = []
        preview.activated.connect(lambda: activated.append(True))
        QTest.keyClick(preview, Qt.Key_Return)
        self.assertEqual(activated, [True])
        preview.clear_image()
        QTest.keyClick(preview, Qt.Key_Return)
        self.assertEqual(activated, [True])

    def test_main_window_opens_the_clicked_pair_and_only_updates_that_result(self) -> None:
        settings = QSettings(str(self.root / "settings.ini"), QSettings.IniFormat)
        with patch("renderhuman.ui.main_window.QSettings", return_value=settings), \
             patch("renderhuman.ui.main_window.has_openai_api_key", return_value=False):
            window = MainWindow()
            self.addCleanup(window.close)
            window._add_paths([self.source])
            window.original_preview.activated.emit()
            viewer = window._comparison_viewer
            self.assertIsNotNone(viewer)
            self.app.processEvents()
            self.assertEqual(viewer.source_path, self.source)
            self.assertFalse(viewer.canvas.has_result)
            other = self.root / "other.png"
            Image.new("RGB", (1000, 800), "green").save(other)
            window._add_paths([other])
            window._on_item_finished(1, PipelineItemResult(other, "completed", "done", self.result))
            self.assertFalse(viewer.canvas.has_result)
            self.assertEqual(viewer.source_path, self.source)
            result = PipelineItemResult(self.source, "completed", "done", self.result)
            window._on_item_finished(0, result)
            self.assertTrue(viewer.canvas.has_result)
            self.assertEqual(viewer.result_path, self.result)
            viewer.done(QDialog.Accepted)
            self.assertIsNone(window._comparison_viewer)


if __name__ == "__main__":
    unittest.main()
