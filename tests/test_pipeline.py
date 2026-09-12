from __future__ import annotations

import base64
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from renderhuman.config import OPENAI_IMAGE_MODEL, OPENAI_IMAGE_MODELS, ProcessingOptions
from renderhuman.services.openai_editor import OpenAIImageEditor
from renderhuman.services.pipeline import RenderPipeline


class FakeEditor:
    def __init__(self) -> None:
        self.calls = 0
        self.last_prompt = ""
        self.last_model = ""

    def edit(self, source_path: Path, prompt: str, size: str, *, model: str) -> bytes:
        self.calls += 1
        self.last_prompt = prompt
        self.last_model = model
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
            self.assertEqual(editor.last_model, OPENAI_IMAGE_MODEL)
            self.assertIn("ONLY ALLOWED CHANGE", editor.last_prompt)
            self.assertIn("never enlarge a head", editor.last_prompt)
            self.assertIn("IMMUTABLE SCENE", editor.last_prompt)
            self.assertTrue(result.output_path and result.output_path.exists())
            with Image.open(result.output_path) as output:
                self.assertEqual(output.size, (1200, 700))
                self.assertEqual(output.getpixel((10, 10)), (20, 40, 230))

    def test_selected_model_reaches_api_and_progress(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "render.png"
            Image.new("RGB", (1200, 700), "white").save(source)
            buffer = BytesIO()
            Image.new("RGB", (1536, 1024), "blue").save(buffer, format="PNG")
            payload = base64.b64encode(buffer.getvalue()).decode("ascii")
            from unittest.mock import Mock

            for model, label in OPENAI_IMAGE_MODELS.items():
                with self.subTest(model=model):
                    client = Mock()
                    client.images.edit.return_value = SimpleNamespace(
                        data=[SimpleNamespace(b64_json=payload)]
                    )
                    pipeline = RenderPipeline(
                        ProcessingOptions(image_model=model),
                        editor=OpenAIImageEditor(client=client),
                    )
                    stages = []
                    result = pipeline.process_one(
                        source, root / "out",
                        stage_callback=lambda *stage: stages.append(stage),
                    )
                    arguments = client.images.edit.call_args.kwargs
                    self.assertEqual(arguments["model"], model)
                    self.assertEqual(arguments["quality"], "high")
                    self.assertEqual(arguments["output_format"], "png")
                    self.assertTrue(any(label in detail for _, detail, _ in stages))
                    self.assertEqual(result.status, "completed")
                    with Image.open(result.output_path) as output:
                        self.assertEqual(output.size, (1200, 700))

    def test_unsupported_model_is_rejected_before_processing(self) -> None:
        with self.assertRaisesRegex(ValueError, "modelo de imagen compatible"):
            RenderPipeline(ProcessingOptions(image_model="unknown-model"))


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
