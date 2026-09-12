from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps


MIN_API_PIXELS = 655_360
MAX_API_PIXELS = 8_294_400
MAX_API_EDGE = 3_840
MAX_API_RATIO = 3.0
API_SIZE_MULTIPLE = 16


def load_render_image(path: Path) -> Image.Image:
    """Load an image with EXIF orientation applied and return an opaque RGB image."""
    with Image.open(path) as opened:
        image = ImageOps.exif_transpose(opened)
        if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            image = Image.alpha_composite(background, rgba)
        return image.convert("RGB").copy()


def _round_up(value: float, multiple: int = API_SIZE_MULTIPLE) -> int:
    return int(math.ceil(value / multiple) * multiple)


@dataclass(frozen=True)
class CanvasTransform:
    original_size: tuple[int, int]
    content_size: tuple[int, int]
    canvas_size: tuple[int, int]
    offset: tuple[int, int]

    @classmethod
    def for_image(cls, size: tuple[int, int]) -> "CanvasTransform":
        width, height = size
        if width <= 0 or height <= 0:
            raise ValueError("La imagen tiene dimensiones no válidas.")

        # Add protected padding only when needed to satisfy the API's 3:1 ratio.
        base_width = max(float(width), float(height) / MAX_API_RATIO)
        base_height = max(float(height), float(width) / MAX_API_RATIO)
        base_pixels = base_width * base_height

        min_scale = math.sqrt(MIN_API_PIXELS / base_pixels)
        max_scale = min(
            MAX_API_EDGE / max(base_width, base_height),
            math.sqrt(MAX_API_PIXELS / base_pixels),
        )
        scale = min(1.0, max_scale)
        if scale < min_scale:
            scale = min_scale
        scale = min(scale, max_scale)

        def dimensions(at_scale: float) -> tuple[int, int, int, int]:
            content_width = max(1, int(round(width * at_scale)))
            content_height = max(1, int(round(height * at_scale)))
            logical_width = max(content_width, math.ceil(content_height / MAX_API_RATIO))
            logical_height = max(content_height, math.ceil(content_width / MAX_API_RATIO))
            return (
                content_width,
                content_height,
                _round_up(logical_width),
                _round_up(logical_height),
            )

        content_width, content_height, canvas_width, canvas_height = dimensions(scale)
        for _ in range(100):
            pixels = canvas_width * canvas_height
            ratio = max(canvas_width / canvas_height, canvas_height / canvas_width)
            if (
                canvas_width <= MAX_API_EDGE
                and canvas_height <= MAX_API_EDGE
                and pixels <= MAX_API_PIXELS
                and ratio <= MAX_API_RATIO
            ):
                break
            scale *= 0.99
            content_width, content_height, canvas_width, canvas_height = dimensions(scale)
        else:
            raise ValueError("No se pudo adaptar la imagen a un tamaño admitido por GPT Image 2.")

        if canvas_width * canvas_height < MIN_API_PIXELS:
            raise ValueError("No se pudo alcanzar el tamaño mínimo requerido por GPT Image 2.")

        offset_x = (canvas_width - content_width) // 2
        offset_y = (canvas_height - content_height) // 2
        return cls(
            original_size=size,
            content_size=(content_width, content_height),
            canvas_size=(canvas_width, canvas_height),
            offset=(offset_x, offset_y),
        )

    @property
    def api_size(self) -> str:
        return f"{self.canvas_size[0]}x{self.canvas_size[1]}"

    def prepare_source(self, image: Image.Image) -> Image.Image:
        resized = image.convert("RGB").resize(self.content_size, Image.Resampling.LANCZOS)
        array = np.asarray(resized)
        offset_x, offset_y = self.offset
        right = self.canvas_size[0] - self.content_size[0] - offset_x
        bottom = self.canvas_size[1] - self.content_size[1] - offset_y
        padded = np.pad(
            array,
            ((offset_y, bottom), (offset_x, right), (0, 0)),
            mode="edge",
        )
        return Image.fromarray(padded)

    def restore_output(self, generated: Image.Image) -> Image.Image:
        generated = generated.convert("RGB")
        if generated.size != self.canvas_size:
            generated = generated.resize(self.canvas_size, Image.Resampling.LANCZOS)
        offset_x, offset_y = self.offset
        content_width, content_height = self.content_size
        cropped = generated.crop(
            (
                offset_x,
                offset_y,
                offset_x + content_width,
                offset_y + content_height,
            )
        )
        return cropped.resize(self.original_size, Image.Resampling.LANCZOS)


def sanitize_stem(stem: str) -> str:
    cleaned = re.sub(r"[<>:\"/\\|?*\x00-\x1F]", "_", stem).strip(" .")
    return cleaned or "render"


def existing_result_paths(output_dir: Path, source_stem: str) -> list[Path]:
    """Return completed outputs for a source, including numbered reprocessings."""
    if not output_dir.is_dir():
        return []
    safe_stem = sanitize_stem(source_stem)
    result_name = re.compile(
        rf"^{re.escape(safe_stem)}_humanized(?:_\d+)?\.png$",
        re.IGNORECASE,
    )
    matches = [
        path
        for path in output_dir.iterdir()
        if path.is_file() and result_name.match(path.name)
    ]

    def reprocessing_index(path: Path) -> int:
        match = re.search(r"_(\d+)\.png$", path.name, re.IGNORECASE)
        return int(match.group(1)) if match else 1

    return sorted(matches, key=reprocessing_index)


def unique_output_path(
    output_dir: Path,
    source_stem: str,
    reserved_paths: set[Path] | None = None,
) -> Path:
    safe_stem = sanitize_stem(source_stem)
    reserved = reserved_paths or set()
    index = 1
    while True:
        suffix = "" if index == 1 else f"_{index}"
        base = f"{safe_stem}_humanized{suffix}"
        result = output_dir / f"{base}.png"
        if not result.exists() and result not in reserved:
            return result
        index += 1


def save_image_atomic(image: Image.Image, path: Path, *, image_format: str = "PNG") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.stem}.{uuid.uuid4().hex}.tmp{path.suffix}")
    save_kwargs: dict[str, object] = {}
    if image_format.upper() == "PNG":
        save_kwargs["optimize"] = True
    elif image_format.upper() == "JPEG":
        save_kwargs.update({"quality": 92, "optimize": True})
    try:
        image.save(temporary, format=image_format, **save_kwargs)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
