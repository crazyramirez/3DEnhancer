from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QCoreApplication, QSettings, Qt
from PyQt5.QtWidgets import QApplication

from renderhuman.config import OPENAI_IMAGE_MODEL
from renderhuman.i18n import apply_language, tr
from renderhuman.ui.main_window import MainWindow
from renderhuman.ui.worker import ProcessingWorker


class MainWindowSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.addCleanup(lambda: apply_language("system", self.app))
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings = QSettings(
            str(Path(self.directory.name) / "settings.ini"), QSettings.IniFormat
        )
        settings_patch = patch("renderhuman.ui.main_window.QSettings", return_value=self.settings)
        settings_patch.start()
        self.addCleanup(settings_patch.stop)
        key_patch = patch("renderhuman.ui.main_window.has_openai_api_key", return_value=False)
        key_patch.start()
        self.addCleanup(key_patch.stop)

    def window(self) -> MainWindow:
        window = MainWindow()
        self.addCleanup(window.close)
        return window

    def test_selection_is_saved_restored_and_used_for_processing(self) -> None:
        window = self.window()
        self.assertEqual(window.model_combo.currentData(), OPENAI_IMAGE_MODEL)
        self.assertEqual(window.model_combo.count(), 2)
        model = "gpt-image-2.5-sunburst"
        window.model_combo.setCurrentIndex(window.model_combo.findData(model))
        self.assertEqual(window._processing_options().image_model, model)
        window._save_settings()

        restored = self.window()
        self.assertEqual(restored.model_combo.currentData(), model)
        restored._set_controls_enabled(False)
        self.assertFalse(restored.model_combo.isEnabled())
        restored._set_controls_enabled(True)
        self.assertTrue(restored.model_combo.isEnabled())

    def test_unknown_saved_model_falls_back_to_default(self) -> None:
        self.settings.setValue("image_model", "removed-model")
        window = self.window()
        self.assertEqual(window._processing_options().image_model, OPENAI_IMAGE_MODEL)

    def test_source_output_preference_preserves_shared_directory(self) -> None:
        window = self.window()
        shared = str(Path(self.directory.name) / "shared")
        window.output_edit.setText(shared)
        window.source_output_check.setChecked(True)
        self.assertTrue(window._processing_options().use_source_directory)
        self.assertFalse(window.output_edit.isEnabled())
        self.assertFalse(window.output_button.isEnabled())
        self.assertFalse(window.open_output_button.isEnabled())
        window._save_settings()
        restored = self.window()
        self.assertTrue(restored.source_output_check.isChecked())
        restored.source_output_check.setChecked(False)
        self.assertTrue(restored.output_edit.isEnabled())
        self.assertEqual(restored.output_edit.text(), shared)
        restored._set_controls_enabled(False)
        self.assertFalse(restored.source_output_check.isEnabled())
        self.assertFalse(restored.output_edit.isEnabled())
        restored._set_controls_enabled(True)
        self.assertTrue(restored.source_output_check.isEnabled())

    def test_source_output_checks_existing_results_in_each_folder(self) -> None:
        window = self.window()
        sources = []
        for folder in ("A", "B"):
            parent = Path(self.directory.name) / folder
            parent.mkdir()
            source = parent / "render.png"
            Image.new("RGB", (100, 60), "blue").save(source)
            Image.new("RGB", (100, 60), "red").save(parent / "render_humanized.png")
            sources.append(source)
        window._add_paths(sources)
        window.output_edit.clear()
        window.source_output_check.setChecked(True)
        with patch("renderhuman.ui.main_window.QMessageBox") as message_box:
            reprocess, skip, cancel = object(), object(), object()
            dialog = message_box.return_value
            dialog.addButton.side_effect = [reprocess, skip, cancel]
            dialog.clickedButton.return_value = skip
            window._start_processing()
            message_box.warning.assert_not_called()
        self.assertEqual(len(window.results), 2)
        for source in sources:
            result = window.results[window._key(source)]
            self.assertEqual(result.status, "skipped")
            self.assertEqual(result.output_path.parent, source.parent)
        self.assertFalse(window.processing)

    def test_live_language_change_preserves_processing_state_and_translates_history(self) -> None:
        window = self.window()
        window.language_combo.setCurrentIndex(window.language_combo.findData("es"))
        source = Path(self.directory.name) / "Resultado.png"
        Image.new("RGB", (100, 60), "blue").save(source)
        window._add_paths([source])
        prompt = "Procesar imágenes {custom prompt}"
        window.prompt_edit.setPlainText(prompt)
        window.api_key_input.setText("sk-test-not-saved")
        window.model_combo.setCurrentIndex(1)
        window.source_output_check.setChecked(True)
        table = window.file_table
        pixmap_key = window.original_preview._source_pixmap.cacheKey()
        window.processing = True
        window._set_controls_enabled(False)
        window._set_localized_text(window.process_button, tr("Procesando…"))
        window._on_item_stage(0, tr("Editando imagen completa"), tr("Aplicando instrucciones"), 4)
        window._append_log(tr("Iniciando: {path}", path=source))
        window.total_progress.setRange(0, 5)
        window.total_progress.setValue(2)

        # Messages can already be queued when the user selects another language.
        worker = ProcessingWorker([source], None, window._processing_options())
        worker.log_message.connect(window._append_log, Qt.QueuedConnection)
        worker.log_message.emit(tr("Salida: carpeta de cada imagen de entrada"))
        try:
            self.assertTrue(window.language_combo.isEnabled())
            window.language_combo.setCurrentIndex(window.language_combo.findData("en"))
            self.app.processEvents()
            self.assertEqual(window.process_button.text(), "Processing…")
            self.assertEqual(window.file_table.item(0, 2).text(), "Editing complete image")
            self.assertEqual(window.stage_label.text(), "Editing complete image · Resultado.png")
            self.assertIn("Starting:", window.log_view.toPlainText())
            self.assertIn("Output: each input image's folder", window.log_view.toPlainText())
            self.assertEqual(QCoreApplication.translate("QPlatformTheme", "Cancel"), "Cancel")
            self.assertEqual(self.settings.value("language"), "en")
            self.assertIs(window.file_table, table)
            self.assertEqual(window.prompt_edit.toPlainText(), prompt)
            self.assertEqual(window.api_key_input.text(), "sk-test-not-saved")
            self.assertEqual(window.original_preview.path, source)
            self.assertEqual(window.original_preview._source_pixmap.cacheKey(), pixmap_key)
            self.assertEqual(window.total_progress.value(), 2)
            self.assertEqual(window.model_combo.currentIndex(), 1)
            self.assertTrue(window.source_output_check.isChecked())
            self.assertFalse(window.model_combo.isEnabled())
            window.language_combo.setCurrentIndex(window.language_combo.findData("es"))
            self.assertEqual(window.process_button.text(), "Procesando…")
            self.assertIn("Iniciando:", window.log_view.toPlainText())
            self.assertEqual(QCoreApplication.translate("QPlatformTheme", "Cancel"), "Cancelar")
        finally:
            window.processing = False

    def test_language_preference_is_restored_and_system_mode_can_be_reselected(self) -> None:
        window = self.window()
        window.language_combo.setCurrentIndex(window.language_combo.findData("en"))
        restored = self.window()
        self.assertEqual(restored.language_combo.currentData(), "en")
        self.assertEqual(restored.process_button.text(), "Process images")
        with patch("renderhuman.i18n.QLocale.system") as system:
            system.return_value.uiLanguages.return_value = ["es-MX"]
            restored.language_combo.setCurrentIndex(0)
            self.assertEqual(restored.process_button.text(), "Procesar imágenes")
            self.assertEqual(restored.language_combo.currentData(), "system")


if __name__ == "__main__":
    unittest.main()
