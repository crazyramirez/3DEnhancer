from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from renderhuman.config import ProcessingOptions
from renderhuman.services.pipeline import PipelineItemResult
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


if __name__ == "__main__":
    unittest.main()
