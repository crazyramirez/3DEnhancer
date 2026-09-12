from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from renderhuman.config import ProcessingOptions
from renderhuman.services.pipeline import PipelineItemResult, RenderPipeline
from renderhuman.ui.worker import ProcessingWorker


class FakeParallelPipeline:
    lock = threading.Lock()
    active = 0
    max_active = 0
    output_names: list[str] = []

    def __init__(self, _options: ProcessingOptions) -> None:
        pass

    def process_one(self, source_path: Path, _output_dir: Path, **kwargs) -> PipelineItemResult:
        output_path = kwargs["output_path"]
        with self.lock:
            type(self).active += 1
            type(self).max_active = max(type(self).max_active, type(self).active)
            type(self).output_names.append(output_path.name)
        time.sleep(0.04)
        with self.lock:
            type(self).active -= 1
        return PipelineItemResult(
            source_path=source_path,
            status="completed",
            message="ok",
            output_path=output_path,
        )


class WorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeParallelPipeline.active = 0
        FakeParallelPipeline.max_active = 0
        FakeParallelPipeline.output_names = []

    def test_complete_mode_processes_groups_of_five_and_reserves_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = [root / f"folder_{index}" / "render.png" for index in range(7)]
            worker = ProcessingWorker(
                files,
                root / "out",
                ProcessingOptions(parallel_jobs=5),
                row_indices=list(range(7)),
            )
            final_stats = []
            worker.finished.connect(lambda *stats: final_stats.append(stats))

            with patch("renderhuman.ui.worker.RenderPipeline", FakeParallelPipeline):
                worker.run()

            self.assertEqual(FakeParallelPipeline.max_active, 5)
            self.assertEqual(len(set(FakeParallelPipeline.output_names)), 7)
            self.assertEqual(final_stats, [(False, 7, 0, 0)])

    def test_source_directories_preserve_originals_and_existing_results(self) -> None:
        for parallel_jobs in (1, 5):
            with self.subTest(parallel_jobs=parallel_jobs), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                files = [root / "A" / "render.png", root / "A" / "render.jpg",
                         root / "B" / "render.png"]
                for source in files:
                    source.parent.mkdir(exist_ok=True)
                    Image.new("RGB", (100, 60), "blue").save(source)
                previous = root / "A" / "render_humanized.png"
                Image.new("RGB", (100, 60), "red").save(previous)
                original_data = {path: path.read_bytes() for path in [*files, previous]}
                options = ProcessingOptions(
                    parallel_jobs=parallel_jobs, use_source_directory=True
                )
                editor = Mock()
                editor.edit.side_effect = lambda source, *_args, **_kwargs: source.read_bytes()
                worker = ProcessingWorker(files, None, options)
                final_stats = []
                worker.finished.connect(lambda *stats: final_stats.append(stats))
                with patch("renderhuman.ui.worker.RenderPipeline",
                           side_effect=lambda opts: RenderPipeline(opts, editor=editor)):
                    worker.run()

                self.assertEqual(final_stats, [(False, 3, 0, 0)])
                for path, data in original_data.items():
                    self.assertEqual(path.read_bytes(), data)
                for output in (root / "A" / "render_humanized_2.png",
                               root / "A" / "render_humanized_3.png",
                               root / "B" / "render_humanized.png"):
                    with Image.open(output) as result:
                        self.assertEqual(result.size, (100, 60))


if __name__ == "__main__":
    unittest.main()
