from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def remove_connected_light_background(source: Image.Image) -> Image.Image:
    """Remove only the light background connected to the four canvas corners."""
    rgb = np.asarray(source.convert("RGB"), dtype=np.float32)
    luminance = rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114

    # The supplied icon has a near-black outer shape. A low threshold includes
    # its antialiased white edge while the dark icon remains a closed barrier.
    eligible = Image.fromarray(
        np.where(luminance > 32, 255, 0).astype(np.uint8)
    ).copy()
    for corner in (
        (0, 0),
        (eligible.width - 1, 0),
        (0, eligible.height - 1),
        (eligible.width - 1, eligible.height - 1),
    ):
        ImageDraw.floodfill(eligible, corner, 128, thresh=0)
    outside = np.asarray(eligible) == 128

    alpha = np.full(luminance.shape, 255.0, dtype=np.float32)
    # Recover smooth alpha from the original white-matted edge.
    alpha[outside] = np.clip((253.0 - luminance[outside]) / 221.0 * 255.0, 0, 255)

    # Replace the white-matted fringe with the icon's dark navy edge color so
    # resampling cannot amplify colored compression specks around the corners.
    normalized_alpha = alpha / 255.0
    output_rgb = rgb.copy()
    output_rgb[outside] = (1, 12, 30)
    output_rgb[outside & (normalized_alpha <= 0.01)] = 0

    rgba = np.dstack((output_rgb.astype(np.uint8), alpha.astype(np.uint8)))
    return Image.fromarray(rgba)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepara los iconos de 3D Enhancer.")
    parser.add_argument("source", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()

    args.output_directory.mkdir(parents=True, exist_ok=True)
    icon = remove_connected_light_background(Image.open(args.source))
    icon = icon.resize((1024, 1024), Image.Resampling.LANCZOS)
    icon.save(args.output_directory / "app_icon.png", optimize=True)
    icon.save(
        args.output_directory / "app_icon.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    icon.save(
        args.output_directory / "app_icon.icns",
        sizes=[(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)],
    )


if __name__ == "__main__":
    main()
