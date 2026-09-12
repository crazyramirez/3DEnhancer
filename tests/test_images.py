from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from renderhuman.core.images import (
    MAX_API_EDGE,
    MAX_API_PIXELS,
    MAX_API_RATIO,
    MIN_API_PIXELS,
    CanvasTransform,
    existing_result_paths,
    unique_output_path,
)


class CanvasTransformTests(unittest.TestCase):
    def test_common_and_extreme_sizes_fit_api_constraints(self) -> None:
        for size in ((1920, 1080), (800, 600), (4000, 2500), (10_000, 900), (320, 240)):
            with self.subTest(size=size):
                transform = CanvasTransform.for_image(size)
                width, height = transform.canvas_size
                pixels = width * height
                ratio = max(width / height, height / width)
                self.assertEqual(width % 16, 0)
                self.assertEqual(height % 16, 0)
                self.assertLessEqual(max(width, height), MAX_API_EDGE)
                self.assertGreaterEqual(pixels, MIN_API_PIXELS)
                self.assertLessEqual(pixels, MAX_API_PIXELS)
                self.assertLessEqual(ratio, MAX_API_RATIO)

    def test_prepare_and_restore_keeps_original_dimensions(self) -> None:
        original = Image.new("RGB", (1919, 1079), (80, 120, 160))
        transform = CanvasTransform.for_image(original.size)
        prepared = transform.prepare_source(original)
        restored = transform.restore_output(prepared)

        self.assertEqual(prepared.size, transform.canvas_size)
        self.assertEqual(restored.size, original.size)
        self.assertEqual(restored.getpixel((500, 500)), (80, 120, 160))


class OutputNamingTests(unittest.TestCase):
    def test_existing_results_are_found_in_reprocessing_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            for name in (
                "render_humanized_10.png",
                "render_humanized.png",
                "render_humanized_2.png",
                "other_humanized.png",
            ):
                (output_dir / name).touch()

            results = existing_result_paths(output_dir, "render")

            self.assertEqual(
                [path.name for path in results],
                ["render_humanized.png", "render_humanized_2.png", "render_humanized_10.png"],
            )

    def test_reserved_names_prevent_parallel_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            reserved: set[Path] = set()

            first = unique_output_path(output_dir, "render", reserved)
            reserved.add(first)
            second = unique_output_path(output_dir, "render", reserved)

            self.assertEqual(first.name, "render_humanized.png")
            self.assertEqual(second.name, "render_humanized_2.png")


if __name__ == "__main__":
    unittest.main()
