from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt5.QtCore import QSettings

from renderhuman.services.credentials import CredentialStore, SecureStorageError


@unittest.skipUnless(sys.platform == "win32", "Requires Windows DPAPI")
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


class MacOSCredentialStoreTests(unittest.TestCase):
    """Exercise Keychain routing without touching the user's real credentials."""

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.settings = QSettings(str(Path(directory.name) / "settings.ini"), QSettings.IniFormat)
        self.store = CredentialStore(self.settings)
        platform = patch("renderhuman.services.credentials.sys.platform", "darwin")
        platform.start()
        self.addCleanup(platform.stop)
        security = patch.object(CredentialStore, "_run_security")
        self.security = security.start()
        self.addCleanup(security.stop)

    def test_save_uses_keychain_without_storing_key_in_settings(self) -> None:
        self.security.return_value = subprocess.CompletedProcess([], 0, "", "")
        self.store.save_api_key("  sk-test-macos  ")
        self.security.assert_called_once_with(
            "add-generic-password", "-a", self.store._keychain_account(),
            "-s", self.store.KEYCHAIN_SERVICE, "-w", "sk-test-macos", "-U",
        )
        self.assertEqual(self.settings.allKeys(), [])

    def test_load_reads_keychain(self) -> None:
        self.security.return_value = subprocess.CompletedProcess([], 0, "sk-test-macos\n", "")
        self.assertEqual(self.store.load_api_key(), "sk-test-macos")
        self.security.assert_called_once_with(
            "find-generic-password", "-a", self.store._keychain_account(),
            "-s", self.store.KEYCHAIN_SERVICE, "-w",
        )

    def test_missing_key_returns_none(self) -> None:
        self.security.return_value = subprocess.CompletedProcess([], 44, "", "")
        self.assertIsNone(self.store.load_api_key())

    def test_delete_uses_keychain(self) -> None:
        self.security.return_value = subprocess.CompletedProcess([], 0, "", "")
        self.store.delete_api_key()
        self.security.assert_called_once_with(
            "delete-generic-password", "-a", self.store._keychain_account(),
            "-s", self.store.KEYCHAIN_SERVICE,
        )

    def test_keychain_errors_are_reported(self) -> None:
        self.security.return_value = subprocess.CompletedProcess([], 1, "", "Access denied")
        for operation in (lambda: self.store.save_api_key("sk-test"),
                          self.store.load_api_key, self.store.delete_api_key):
            with self.subTest(operation=operation):
                with self.assertRaises(SecureStorageError):
                    operation()


if __name__ == "__main__":
    unittest.main()
