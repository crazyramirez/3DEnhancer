from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication

from renderhuman.config import OPENAI_IMAGE_MODEL
from renderhuman.ui.main_window import MainWindow


class ModelSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
