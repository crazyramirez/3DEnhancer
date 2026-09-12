from __future__ import annotations

import base64
import sys
from pathlib import Path
from typing import Any

from renderhuman.config import OPENAI_IMAGE_MODEL
from renderhuman.services.credentials import CredentialStore


class MissingAPIKeyError(RuntimeError):
    pass


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path.home() / "Documents" / "3D Enhancer"
    return Path(__file__).resolve().parents[2]


def has_openai_api_key(store: CredentialStore | None = None) -> bool:
    return (store or CredentialStore()).has_api_key()


class OpenAIImageEditor:
    def __init__(
        self,
        *,
        client: Any | None = None,
        credential_store: CredentialStore | None = None,
    ) -> None:
        self._client = client
        self.credential_store = credential_store or CredentialStore()

    def _client_or_create(self) -> Any:
        if self._client is not None:
            return self._client

        api_key = self.credential_store.load_api_key()
        if not api_key:
            raise MissingAPIKeyError(
                "No hay una clave de OpenAI guardada. Introdúcela en la aplicación."
            )

        try:
            from openai import OpenAI
        except ImportError as error:
            raise RuntimeError(
                "No está instalado el SDK de OpenAI. Ejecuta: pip install -r requirements.txt"
            ) from error

        self._client = OpenAI(api_key=api_key, timeout=240.0, max_retries=2)
        return self._client

    def edit(
        self,
        source_path: Path,
        prompt: str,
        size: str,
        *,
        model: str = OPENAI_IMAGE_MODEL,
    ) -> bytes:
        client = self._client_or_create()
        with source_path.open("rb") as source_file:
            response = client.images.edit(
                model=model,
                image=source_file,
                prompt=prompt,
                quality="high",
                size=size,
                output_format="png",
            )

        if not response.data:
            raise RuntimeError(f"{model} no devolvió ninguna imagen.")
        encoded = response.data[0].b64_json
        if not encoded:
            raise RuntimeError(f"{model} devolvió una respuesta sin datos de imagen.")
        return base64.b64decode(encoded)
