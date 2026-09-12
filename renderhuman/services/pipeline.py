from __future__ import annotations

import tempfile
import threading
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Callable, Literal

from PIL import Image

from renderhuman.config import ProcessingOptions
from renderhuman.core.images import (
    CanvasTransform,
    load_render_image,
    save_image_atomic,
    unique_output_path,
)
from renderhuman.services.openai_editor import OpenAIImageEditor


StageCallback = Callable[[str, str, int], None]


class ProcessingCancelled(RuntimeError):
    pass


@dataclass(frozen=True)
class PipelineItemResult:
    source_path: Path
    status: Literal["completed", "skipped"]
    message: str
    output_path: Path | None = None


class RenderPipeline:
    STAGE_COUNT = 6

    def __init__(
        self,
        options: ProcessingOptions,
        *,
        editor: OpenAIImageEditor | None = None,
    ) -> None:
        options.validate()
        self.options = options
        self.editor = editor or OpenAIImageEditor()

    @staticmethod
    def _notify(callback: StageCallback | None, title: str, detail: str, step: int) -> None:
        if callback:
            callback(title, detail, step)

    @staticmethod
    def _check_cancelled(cancel_event: threading.Event | None) -> None:
        if cancel_event and cancel_event.is_set():
            raise ProcessingCancelled("Procesado cancelado.")

    def _edit_complete_image(
        self,
        original: Image.Image,
        *,
        stage_callback: StageCallback | None,
        cancel_event: threading.Event | None,
    ) -> Image.Image:
        transform = CanvasTransform.for_image(original.size)
        with tempfile.TemporaryDirectory(prefix="3d_enhancer_") as temp_directory:
            source_path = Path(temp_directory) / "source.png"
            transform.prepare_source(original).save(source_path, format="PNG", optimize=True)
            self._check_cancelled(cancel_event)
            self._notify(
                stage_callback,
                "Editando imagen completa",
                f"GPT Image 2 · calidad alta · lienzo {transform.api_size}",
                4,
            )
            generated_bytes = self.editor.edit(
                source_path,
                self.options.prompt,
                transform.api_size,
            )
        with Image.open(BytesIO(generated_bytes)) as generated_file:
            return transform.restore_output(generated_file)

    def process_one(
        self,
        source_path: Path,
        output_dir: Path,
        *,
        output_path: Path | None = None,
        stage_callback: StageCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> PipelineItemResult:
        source_path = Path(source_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_path or unique_output_path(output_dir, source_path.stem)

        self._notify(stage_callback, "Preparando", "Leyendo y normalizando el render", 1)
        original = load_render_image(source_path)
        self._check_cancelled(cancel_event)
        self._notify(
            stage_callback,
            "Preparando edición completa",
            "Conservando el render completo como referencia visual",
            2,
        )
        self._notify(
            stage_callback,
            "Aplicando instrucciones",
            "Una llamada; solo deben cambiar los personajes 3D",
            3,
        )
        result_image = self._edit_complete_image(
            original,
            stage_callback=stage_callback,
            cancel_event=cancel_event,
        )
        self._check_cancelled(cancel_event)
        self._notify(
            stage_callback,
            "Restaurando resolución",
            f"Recuperando el tamaño original de {original.width} × {original.height} px",
            5,
        )
        self._notify(stage_callback, "Guardando", output_path.name, 6)
        save_image_atomic(result_image, output_path)
        return PipelineItemResult(
            source_path=source_path,
            status="completed",
            message="Completada en una llamada de imagen completa.",
            output_path=output_path,
        )
