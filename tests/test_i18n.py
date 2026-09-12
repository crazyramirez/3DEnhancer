from __future__ import annotations

import ast
import os
from pathlib import Path
from string import Formatter
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QCoreApplication, QSettings
from PyQt5.QtWidgets import QApplication

from renderhuman.config import DEFAULT_PROMPT, ProcessingOptions
from renderhuman.i18n import ENGLISH, apply_language, get_language, install_qt_translations, tr
from renderhuman.ui.main_window import MainWindow
from renderhuman.ui.worker import ProcessingWorker


class LanguageDetectionTests(unittest.TestCase):
    def tearDown(self) -> None:
        get_language.cache_clear()

    def test_primary_ui_language_takes_precedence_over_region(self) -> None:
        cases = [
            (["es-ES", "en-US"], "en_US", "es"),
            (["es-MX"], "en_US", "es"),
            (["es_Argentina"], "en_US", "es"),
            (["en-US", "es-ES"], "es_ES", "en"),
            (["fr-FR", "es-ES"], "es_ES", "en"),
            ([], "es_ES", "es"),
            ([], "C", "en"),
        ]
        for languages, region, expected in cases:
            with self.subTest(languages=languages, region=region):
                get_language.cache_clear()
                locale = Mock()
                locale.uiLanguages.return_value = languages
                locale.name.return_value = region
                with patch("renderhuman.i18n.QLocale.system", return_value=locale):
                    self.assertEqual(get_language(), expected)

    def test_catalog_preserves_placeholders_and_covers_all_calls(self) -> None:
        formatter = Formatter()
        for source, english in ENGLISH.items():
            with self.subTest(source=source):
                fields = lambda text: {field for _, field, _, _ in formatter.parse(text) if field}
                self.assertEqual(fields(source), fields(english))
        root = Path(__file__).resolve().parents[1] / "renderhuman"
        for path in root.rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tr":
                    self.assertTrue(node.args)
                    value = node.args[0]
                    keys = [value.body, value.orelse] if isinstance(value, ast.IfExp) else [value]
                    for key in keys:
                        self.assertIsInstance(key, ast.Constant, f"{path}:{node.lineno}")
                        self.assertIn(key.value, ENGLISH, f"{path}:{node.lineno}")

    def test_formatting_preserves_user_paths(self) -> None:
        path = "C:/Renders/{cliente}/escena española.png"
        with patch("renderhuman.i18n.get_language", return_value="en"):
            self.assertEqual(tr("Ya no existe el archivo:\n{path}", path=path),
                             f"The file no longer exists:\n{path}")


class LocalizedInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_ui_dialogs_and_worker_messages_in_both_languages(self) -> None:
        cases = [
            ("es", "Procesar imágenes", "Guardar junto a cada imagen de entrada",
             "Introduce una clave de OpenAI.", "Iniciando:", "Error en", "1 imagen", "2 imágenes"),
            ("en", "Process images", "Save next to each input image",
             "Enter an OpenAI key.", "Starting:", "Error in", "1 image", "2 images"),
        ]
        for language, process, output, missing_key, starting, failed, singular, plural in cases:
            with self.subTest(language=language), tempfile.TemporaryDirectory() as directory:
                settings = QSettings(str(Path(directory) / "settings.ini"), QSettings.IniFormat)
                with patch("renderhuman.i18n.get_language", return_value=language), \
                     patch("renderhuman.ui.main_window.QSettings", return_value=settings), \
                     patch("renderhuman.ui.main_window.has_openai_api_key", return_value=False):
                    window = MainWindow()
                    try:
                        self.assertEqual(window.process_button.text(), process)
                        self.assertEqual(window.source_output_check.text(), output)
                        self.assertEqual(window.prompt_edit.toPlainText(), DEFAULT_PROMPT)
                        with patch("renderhuman.ui.main_window.QMessageBox") as dialog:
                            window._store_api_key(show_confirmation=False)
                            self.assertEqual(dialog.information.call_args.args[2], missing_key)
                        window.files = [Path(directory) / "one.png"]
                        window._rebuild_table()
                        self.assertEqual(window.selection_count.text(), singular)
                        window.files.append(Path(directory) / "two.png")
                        window._rebuild_table()
                        self.assertEqual(window.selection_count.text(), plural)
                        window._on_batch_finished(False, 2, 0, 0)
                        self.assertEqual(window.stage_label.text(), tr("Lote completado"))
                        worker = ProcessingWorker(window.files[:1], Path(directory), ProcessingOptions(parallel_jobs=1))
                        messages = []
                        worker.log_message.connect(messages.append)
                        with patch("renderhuman.ui.worker.RenderPipeline") as pipeline:
                            pipeline.return_value.process_one.side_effect = RuntimeError("API detail")
                            worker.run()
                        self.assertTrue(messages[0].startswith(starting))
                        self.assertTrue(messages[1].startswith(failed))
                        self.assertIn("API detail", messages[1])
                    finally:
                        window.close()

    def test_standard_qt_buttons_are_translated(self) -> None:
        apply_language("en", self.app)
        self.addCleanup(lambda: apply_language("system", self.app))
        with patch("renderhuman.i18n.get_language", return_value="es"):
            translator = install_qt_translations(self.app)
            self.assertIsNotNone(translator)
            try:
                self.assertEqual(QCoreApplication.translate("QPlatformTheme", "Cancel"), "Cancelar")
            finally:
                self.app.removeTranslator(translator)
        with patch("renderhuman.i18n.get_language", return_value="en"):
            self.assertIsNone(install_qt_translations(self.app))
            self.assertEqual(QCoreApplication.translate("QPlatformTheme", "Cancel"), "Cancel")


if __name__ == "__main__":
    unittest.main()
