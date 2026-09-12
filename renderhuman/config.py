from __future__ import annotations

from dataclasses import dataclass


APP_NAME = "3D Enhancer"
OPENAI_IMAGE_MODEL = "gpt-image-2"

SUPPORTED_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".tif",
    ".tiff",
    ".bmp",
}

DEFAULT_PROMPT = """Edit this exact finished architectural render as a tightly constrained photorealism conversion.

ONLY ALLOWED CHANGE:
Replace every existing CGI/3D human character with one believable photographed real person. Make the minimum visual change necessary to remove the CGI look. This is a one-to-one replacement, not a redesign or a new scene.

CHARACTER LOCK:
Keep the exact same number of people. For every person preserve the exact position, scale, full-body silhouette, pose, gesture, viewing direction, depth, occlusion, crop, clothing type, clothing colors, footwear, accessories and contact shadow. Do not add, remove, move, merge, duplicate or regroup anyone.

ANATOMY AND SCALE:
Use ordinary natural human anatomy. Preserve the original head-to-body ratio: never enlarge a head, face or hairstyle. Keep hair within the source head silhouette and close to the skull, preserving its original length, direction and color. Do not invent long, dense or voluminous hair. Bald people stay bald and hats stay unchanged. Faces must be natural but restrained at their actual pixel size; distant, profile, hidden and backward-facing people must remain that way, without invented close-up detail.

IMMUTABLE SCENE — DO NOT EDIT:
Preserve the architecture, geometry, booths, furniture, objects, floor, ceiling, materials, signage, logos, all text, lighting, exposure, shadows, reflections, background, empty areas, camera, perspective, framing, resolution, depth of field, grain and color grade exactly as in the input. Do not alter any non-human pixel intentionally. Do not beautify, restyle, relight, clean up or regenerate the scene.

Return the same complete composition. The result should look like the original render with only its existing CGI people made realistically photographic."""


@dataclass(frozen=True)
class ProcessingOptions:
    parallel_jobs: int = 5
    prompt: str = DEFAULT_PROMPT

    def validate(self) -> None:
        if not self.prompt.strip():
            raise ValueError("El prompt no puede estar vacío.")
        if not 1 <= self.parallel_jobs <= 5:
            raise ValueError("El procesado paralelo debe estar entre 1 y 5 imágenes.")
