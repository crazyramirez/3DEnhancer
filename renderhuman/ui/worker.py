from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from renderhuman.i18n import describe_error, tr
from renderhuman.config import ProcessingOptions
from renderhuman.core.images import unique_output_path
from renderhuman.services.pipeline import PipelineItemResult, ProcessingCancelled, RenderPipeline


class ProcessingWorker(QObject):
    item_stage = pyqtSignal(int, object, object, int)
    item_finished = pyqtSignal(int, object)
    item_failed = pyqtSignal(int, object)
    batch_progress = pyqtSignal(int, int)
    log_message = pyqtSignal(object)
    finished = pyqtSignal(bool, int, int, int)

    def __init__(
        self,
        files: list[Path],
        output_dir: Path | None,
        options: ProcessingOptions,
        *,
        row_indices: list[int] | None = None,
        initial_skipped: int = 0,
    ) -> None:
        super().__init__()
        self.files = files
        self.output_dir = output_dir
        self.options = options
        self.row_indices = row_indices if row_indices is not None else list(range(len(files)))
        if len(self.row_indices) != len(self.files):
            raise ValueError(tr("El número de filas no coincide con el número de imágenes."))
        self.initial_skipped = initial_skipped
        self._cancel_event = threading.Event()

    def request_cancel(self) -> None:
        self._cancel_event.set()

    def _planned_items(self) -> list[tuple[int, Path, Path]]:
        reserved: set[Path] = set()
        planned = []
        for row, source_path in zip(self.row_indices, self.files):
            output_path = unique_output_path(
                self.options.output_directory_for(source_path, self.output_dir),
                source_path.stem,
                reserved,
            )
            reserved.add(output_path)
            planned.append((row, source_path, output_path))
        return planned

    def _process_item(
        self,
        item: tuple[int, Path, Path],
        pipeline: RenderPipeline | None = None,
    ) -> tuple[str, int, Path, PipelineItemResult | None, str]:
        row, source_path, output_path = item
        self.log_message.emit(tr("Iniciando: {path}", path=source_path))

        def report(title: str, detail: str, step: int) -> None:
            self.item_stage.emit(row, title, detail, step)

        try:
            active_pipeline = pipeline or RenderPipeline(self.options)
            result = active_pipeline.process_one(
                source_path,
                output_path.parent,
                output_path=output_path,
                stage_callback=report,
                cancel_event=self._cancel_event,
            )
        except ProcessingCancelled:
            return "cancelled", row, source_path, None, ""
        except Exception as error:  # Continue the rest of the batch.
            message = describe_error(error)
            return "failed", row, source_path, None, message
        return "finished", row, source_path, result, ""

    def _publish_outcome(
        self,
        outcome: tuple[str, int, Path, PipelineItemResult | None, str],
    ) -> tuple[int, int, int, bool]:
        status, row, source_path, result, message = outcome
        if status == "cancelled":
            return 0, 0, 0, True
        if status == "failed":
            self.item_failed.emit(row, message)
            self.log_message.emit(tr("Error en {filename}: {message}", filename=source_path.name, message=message))
            return 0, 1, 0, False

        if result is None:
            message = tr("El procesado no devolvió ningún resultado.")
            self.item_failed.emit(row, message)
            self.log_message.emit(tr("Error en {filename}: {message}", filename=source_path.name, message=message))
            return 0, 1, 0, False

        self.item_finished.emit(row, result)
        self.log_message.emit(tr("{message} {filename}", message=result.message, filename=source_path.name))
        if result.status == "completed":
            return 1, 0, 0, False
        return 0, 0, 1, False

    @pyqtSlot()
    def run(self) -> None:
        succeeded = 0
        failed = 0
        skipped = self.initial_skipped
        cancelled = False
        completed_jobs = 0
        total_items = len(self.files) + self.initial_skipped
        try:
            planned = self._planned_items()
            if self.initial_skipped:
                self.batch_progress.emit(self.initial_skipped, total_items)

            parallelism = self.options.parallel_jobs
            if parallelism == 1:
                pipeline = RenderPipeline(self.options)
                for item in planned:
                    if self._cancel_event.is_set():
                        cancelled = True
                        break
                    outcome = self._process_item(item, pipeline)
                    added_success, added_failed, added_skipped, item_cancelled = (
                        self._publish_outcome(outcome)
                    )
                    succeeded += added_success
                    failed += added_failed
                    skipped += added_skipped
                    if item_cancelled:
                        cancelled = True
                        break
                    completed_jobs += 1
                    self.batch_progress.emit(
                        self.initial_skipped + completed_jobs,
                        total_items,
                    )
            else:
                for start in range(0, len(planned), parallelism):
                    if self._cancel_event.is_set():
                        cancelled = True
                        break
                    group = planned[start : start + parallelism]
                    with ThreadPoolExecutor(
                        max_workers=len(group),
                        thread_name_prefix="3d-enhancer",
                    ) as executor:
                        futures = [executor.submit(self._process_item, item) for item in group]
                        for future in as_completed(futures):
                            outcome = future.result()
                            added_success, added_failed, added_skipped, item_cancelled = (
                                self._publish_outcome(outcome)
                            )
                            succeeded += added_success
                            failed += added_failed
                            skipped += added_skipped
                            if item_cancelled:
                                cancelled = True
                                continue
                            completed_jobs += 1
                            self.batch_progress.emit(
                                self.initial_skipped + completed_jobs,
                                total_items,
                            )
                    if cancelled or self._cancel_event.is_set():
                        cancelled = True
                        break
        except Exception as error:
            failed += max(0, len(self.files) - completed_jobs)
            message = describe_error(error)
            self.log_message.emit(tr("Error general: {message}", message=message))
            if self.row_indices:
                self.item_failed.emit(self.row_indices[0], message)
        finally:
            self.finished.emit(cancelled, succeeded, failed, skipped)
