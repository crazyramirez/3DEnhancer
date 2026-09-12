from __future__ import annotations

import base64
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from renderhuman.config import OPENAI_IMAGE_MODEL, ProcessingOptions
from renderhuman.services.openai_editor import OpenAIImageEditor
from renderhuman.services.pipeline import RenderPipeline


class FakeEditor:
    def __init__(self) -> None:
        self.calls = 0
        self.last_prompt = ""

    def edit(self, source_path: Path, prompt: str, size: str) -> bytes:
        self.calls += 1
        self.last_prompt = prompt
        with Image.open(source_path) as source:
            assert source.format == "PNG"
            assert size == f"{source.width}x{source.height}"
            output = Image.new("RGB", source.size, (20, 40, 230))
        buffer = BytesIO()
        output.save(buffer, format="PNG")
        return buffer.getvalue()


class PipelineTests(unittest.TestCase):
    def test_pipeline_uses_one_complete_image_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "crowd.png"
            Image.new("RGB", (1200, 700), (80, 90, 100)).save(source_path)
            editor = FakeEditor()
            pipeline = RenderPipeline(ProcessingOptions(), editor=editor)

            result = pipeline.process_one(source_path, root / "out")

            self.assertEqual(result.status, "completed")
            self.assertEqual(editor.calls, 1)
            self.assertIn("ONLY ALLOWED CHANGE", editor.last_prompt)
            self.assertIn("never enlarge a head", editor.last_prompt)
            self.assertIn("IMMUTABLE SCENE", editor.last_prompt)
            self.assertTrue(result.output_path and result.output_path.exists())
            with Image.open(result.output_path) as output:
                self.assertEqual(output.size, (1200, 700))
                self.assertEqual(output.getpixel((10, 10)), (20, 40, 230))


class FakeImagesEndpoint:
    def __init__(self) -> None:
        self.arguments = None

    def edit(self, **kwargs):
        self.arguments = kwargs
        payload = base64.b64encode(b"fake-png-data").decode("ascii")
        return SimpleNamespace(data=[SimpleNamespace(b64_json=payload)])


class OpenAIEditorTests(unittest.TestCase):
    def test_request_uses_gpt_image_2_high_and_has_no_mask(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            Image.new("RGB", (1536, 1024), "white").save(source)
            endpoint = FakeImagesEndpoint()
            client = SimpleNamespace(images=endpoint)

            data = OpenAIImageEditor(client=client).edit(
                source,
                "prompt",
                "1536x1024",
            )

            self.assertEqual(data, b"fake-png-data")
            self.assertEqual(endpoint.arguments["model"], OPENAI_IMAGE_MODEL)
            self.assertEqual(endpoint.arguments["quality"], "high")
            self.assertEqual(endpoint.arguments["size"], "1536x1024")
            self.assertNotIn("mask", endpoint.arguments)
            self.assertNotIn("input_fidelity", endpoint.arguments)
            self.assertNotIn("response_format", endpoint.arguments)


if __name__ == "__main__":
    unittest.main()
