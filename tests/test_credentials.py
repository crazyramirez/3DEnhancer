from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PyQt5.QtCore import QSettings

from renderhuman.services.credentials import CredentialStore, SecureStorageError


class CredentialStoreTests(unittest.TestCase):
    def _store(self, directory: str) -> tuple[CredentialStore, QSettings]:
        settings = QSettings(str(Path(directory) / "settings.ini"), QSettings.IniFormat)
        settings.clear()
        return CredentialStore(settings), settings

    def test_api_key_is_encrypted_and_round_trips_for_current_user(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, settings = self._store(directory)
            api_key = "sk-test-123456789012345678901234"

            store.save_api_key(api_key)

            stored_value = str(settings.value(store.SETTINGS_KEY))
            self.assertNotIn(api_key, stored_value)
            self.assertEqual(store.load_api_key(), api_key)
            self.assertTrue(store.has_api_key())

    def test_delete_removes_saved_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, _settings = self._store(directory)
            store.save_api_key("sk-test-123456789012345678901234")

            store.delete_api_key()

            self.assertIsNone(store.load_api_key())
            self.assertFalse(store.has_api_key())

    def test_corrupt_value_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, settings = self._store(directory)
            settings.setValue(store.SETTINGS_KEY, "not-base64")

            with self.assertRaises(SecureStorageError):
                store.load_api_key()


if __name__ == "__main__":
    unittest.main()
