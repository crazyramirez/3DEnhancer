from __future__ import annotations

import base64
import ctypes
import getpass
import subprocess
import sys

if sys.platform == "win32":
    from ctypes import wintypes
else:  # Keep the module importable in the macOS application bundle.
    wintypes = None

from PyQt5.QtCore import QSettings

from renderhuman.config import APP_NAME


class SecureStorageError(RuntimeError):
    pass


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_uint32),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


class CredentialStore:
    """Store the API key with DPAPI on Windows or Keychain on macOS."""

    SETTINGS_KEY = "security/openai_api_key_dpapi"
    ENTROPY = b"3DEnhancer/OpenAI/API/v1"
    CRYPTPROTECT_UI_FORBIDDEN = 0x1
    KEYCHAIN_SERVICE = "3D Enhancer OpenAI API"

    def __init__(self, settings: QSettings | None = None) -> None:
        self.settings = settings or QSettings("3DEnhancer", APP_NAME)

    @staticmethod
    def _blob(data: bytes) -> tuple[_DataBlob, ctypes.Array]:
        buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        blob = _DataBlob(
            len(data),
            ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
        )
        return blob, buffer

    @staticmethod
    def _windows_libraries():
        if sys.platform != "win32":
            raise SecureStorageError(
                "El almacenamiento cifrado de la clave requiere Windows."
            )
        assert wintypes is not None

        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        crypt32.CryptProtectData.argtypes = (
            ctypes.POINTER(_DataBlob),
            wintypes.LPCWSTR,
            ctypes.POINTER(_DataBlob),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(_DataBlob),
        )
        crypt32.CryptProtectData.restype = wintypes.BOOL
        crypt32.CryptUnprotectData.argtypes = (
            ctypes.POINTER(_DataBlob),
            ctypes.c_void_p,
            ctypes.POINTER(_DataBlob),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(_DataBlob),
        )
        crypt32.CryptUnprotectData.restype = wintypes.BOOL
        kernel32.LocalFree.argtypes = (ctypes.c_void_p,)
        kernel32.LocalFree.restype = ctypes.c_void_p
        return crypt32, kernel32

    @classmethod
    def _protect(cls, plaintext: bytes) -> bytes:
        crypt32, kernel32 = cls._windows_libraries()
        source, source_buffer = cls._blob(plaintext)
        entropy, entropy_buffer = cls._blob(cls.ENTROPY)
        protected = _DataBlob()
        if not crypt32.CryptProtectData(
            ctypes.byref(source),
            "3D Enhancer OpenAI API key",
            ctypes.byref(entropy),
            None,
            None,
            cls.CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(protected),
        ):
            raise SecureStorageError(
                f"Windows no pudo cifrar la clave: {ctypes.WinError(ctypes.get_last_error())}"
            )
        try:
            return ctypes.string_at(protected.pbData, protected.cbData)
        finally:
            kernel32.LocalFree(protected.pbData)

    @classmethod
    def _unprotect(cls, ciphertext: bytes) -> bytes:
        crypt32, kernel32 = cls._windows_libraries()
        source, source_buffer = cls._blob(ciphertext)
        entropy, entropy_buffer = cls._blob(cls.ENTROPY)
        plaintext = _DataBlob()
        if not crypt32.CryptUnprotectData(
            ctypes.byref(source),
            None,
            ctypes.byref(entropy),
            None,
            None,
            cls.CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(plaintext),
        ):
            raise SecureStorageError(
                "No se pudo descifrar la clave. Vuelve a introducirla en la aplicación."
            )
        try:
            return ctypes.string_at(plaintext.pbData, plaintext.cbData)
        finally:
            kernel32.LocalFree(plaintext.pbData)

    def save_api_key(self, api_key: str) -> None:
        normalized = api_key.strip()
        if not normalized:
            raise ValueError("La clave de OpenAI no puede estar vacía.")
        if sys.platform == "darwin":
            self._save_macos_key(normalized)
            return
        protected = self._protect(normalized.encode("utf-8"))
        self.settings.setValue(
            self.SETTINGS_KEY,
            base64.b64encode(protected).decode("ascii"),
        )
        self.settings.sync()
        if self.settings.status() != QSettings.NoError:
            raise SecureStorageError("No se pudo guardar la clave cifrada localmente.")

    def load_api_key(self) -> str | None:
        if sys.platform == "darwin":
            return self._load_macos_key()
        encoded = str(self.settings.value(self.SETTINGS_KEY, "") or "").strip()
        if not encoded:
            return None
        try:
            ciphertext = base64.b64decode(encoded, validate=True)
            return self._unprotect(ciphertext).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as error:
            raise SecureStorageError(
                "La clave guardada está dañada. Vuelve a introducirla."
            ) from error

    def has_api_key(self) -> bool:
        try:
            return bool(self.load_api_key())
        except SecureStorageError:
            return False

    def delete_api_key(self) -> None:
        if sys.platform == "darwin":
            self._delete_macos_key()
            return
        self.settings.remove(self.SETTINGS_KEY)
        self.settings.sync()

    @classmethod
    def _keychain_account(cls) -> str:
        return getpass.getuser() or "3DEnhancer"

    @classmethod
    def _run_security(cls, *arguments: str) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                ["/usr/bin/security", *arguments],
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise SecureStorageError(
                "No se pudo acceder al Llavero de macOS."
            ) from error

    @classmethod
    def _save_macos_key(cls, api_key: str) -> None:
        result = cls._run_security(
            "add-generic-password",
            "-a",
            cls._keychain_account(),
            "-s",
            cls.KEYCHAIN_SERVICE,
            "-w",
            api_key,
            "-U",
        )
        if result.returncode != 0:
            raise SecureStorageError(
                "macOS no pudo guardar la clave en el Llavero."
            )

    @classmethod
    def _load_macos_key(cls) -> str | None:
        result = cls._run_security(
            "find-generic-password",
            "-a",
            cls._keychain_account(),
            "-s",
            cls.KEYCHAIN_SERVICE,
            "-w",
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
        if result.returncode == 44 or "could not be found" in result.stderr.lower():
            return None
        raise SecureStorageError("No se pudo leer la clave del Llavero de macOS.")

    @classmethod
    def _delete_macos_key(cls) -> None:
        result = cls._run_security(
            "delete-generic-password",
            "-a",
            cls._keychain_account(),
            "-s",
            cls.KEYCHAIN_SERVICE,
        )
        if result.returncode not in (0, 44) and "could not be found" not in result.stderr.lower():
            raise SecureStorageError("No se pudo eliminar la clave del Llavero de macOS.")
