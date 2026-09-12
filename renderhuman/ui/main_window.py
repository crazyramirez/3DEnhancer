from __future__ import annotations

import os
from collections import deque
from pathlib import Path

from PyQt5.QtCore import QSettings, QThread, QTimer, QUrl, Qt
from PyQt5.QtGui import QBrush, QColor, QDesktopServices, QImageReader
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from renderhuman.i18n import apply_language, render_text, tr
from renderhuman.config import (
    APP_NAME,
    DEFAULT_PROMPT,
    OPENAI_IMAGE_MODEL,
    OPENAI_IMAGE_MODELS,
    ProcessingOptions,
    SUPPORTED_IMAGE_EXTENSIONS,
)
from renderhuman.core.images import existing_result_paths
from renderhuman.services.credentials import CredentialStore, SecureStorageError
from renderhuman.services.openai_editor import has_openai_api_key, project_root
from renderhuman.services.pipeline import PipelineItemResult, RenderPipeline
from renderhuman.ui.widgets import ImagePreview
from renderhuman.ui.worker import ProcessingWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.files: list[Path] = []
        self.results: dict[str, PipelineItemResult] = {}
        self.settings = QSettings("3DEnhancer", APP_NAME)
        self.language_preference = str(self.settings.value("language", "system"))
        if self.language_preference not in {"system", "es", "en"}:
            self.language_preference = "system"
        apply_language(self.language_preference, QApplication.instance())
        self._language_bindings = []
        self._dynamic_text = {}
        self._row_messages = {}
        self._log_messages = deque(maxlen=500)
        self.credential_store = CredentialStore(self.settings)
        self.thread: QThread | None = None
        self.worker: ProcessingWorker | None = None
        self.processing = False
        self._close_after_cancel = False

        self.setWindowTitle(f"{APP_NAME} · Real People")
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        initial_width = (
            min(1720, max(1360, int(available.width() * 0.90)))
            if available
            else 1600
        )
        initial_height = (
            min(1120, max(880, int(available.height() * 0.95)))
            if available
            else 1020
        )
        self.resize(initial_width, initial_height)
        self.setMinimumSize(1200, 780)
        self.setAcceptDrops(True)
        self._build_ui()
        self._load_settings()
        self._rebuild_table()
        self._refresh_api_controls()

    @staticmethod
    def _key(path: Path) -> str:
        return os.path.normcase(str(path.resolve()))

    def _translated(self, widget, message: str, setter: str = "setText", *, uppercase: bool = False):
        self._language_bindings.append((widget, setter, message, uppercase))
        text = render_text(message)
        getattr(widget, setter)(text.upper() if uppercase else text)
        return widget

    def _section_label(self, text: str) -> QLabel:
        label = self._translated(QLabel(), text, uppercase=True)
        label.setObjectName("SectionTitle")
        return label

    @staticmethod
    def _card() -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(11)
        return card, layout

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("AppRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(22, 18, 22, 20)
        root_layout.setSpacing(14)
        self.setCentralWidget(root)

        header = QHBoxLayout()
        title_column = QVBoxLayout()
        title_column.setSpacing(1)
        title = QLabel("3D Enhancer")
        title.setObjectName("AppTitle")
        subtitle = self._translated(QLabel(), tr('Convierte personajes de renders 3D en personas fotorrealistas'))
        subtitle.setObjectName("AppSubtitle")
        title_column.addWidget(title)
        title_column.addWidget(subtitle)
        header.addLayout(title_column)
        header.addStretch(1)
        language_column = QVBoxLayout()
        self.language_label = self._translated(QLabel(), tr('Idioma'))
        self.language_combo = QComboBox()
        self.language_combo.setMinimumWidth(135)
        self.language_combo.addItem(tr("Sistema"), "system")
        self.language_combo.addItem("Español", "es")
        self.language_combo.addItem("English", "en")
        self._translated(self.language_combo, tr('Cambiar el idioma de la interfaz sin reiniciar la aplicación.'), "setToolTip")
        self.language_combo.setCurrentIndex(self.language_combo.findData(self.language_preference))
        self.language_combo.currentIndexChanged.connect(self._change_language)
        language_column.addWidget(self.language_label)
        language_column.addWidget(self.language_combo)
        header.addLayout(language_column)
        api_column = QVBoxLayout()
        api_column.setSpacing(5)
        self.api_key_input = QLineEdit()
        self.api_key_input.setObjectName("ApiKeyInput")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setClearButtonEnabled(True)
        self._translated(self.api_key_input, tr('La clave se guarda en el almacén seguro de credenciales de tu sistema.'), "setToolTip")
        self.api_key_input.returnPressed.connect(self._save_api_key)
        self.api_key_button = QPushButton()
        self.api_key_button.setObjectName("ApiKeyButton")
        self.api_key_button.clicked.connect(self._save_api_key)
        api_column.addWidget(self.api_key_input)
        api_column.addWidget(self.api_key_button)
        header.addLayout(api_column)
        root_layout.addLayout(header)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(18)
        root_layout.addWidget(splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        splitter.addWidget(left)

        source_card, source_layout = self._card()
        left_layout.addWidget(source_card, 1)
        source_title_row = QHBoxLayout()
        source_title_row.addWidget(self._section_label(tr("Imágenes de entrada")))
        source_title_row.addStretch(1)
        self.selection_count = self._translated(QLabel(), tr('0 imágenes'))
        self.selection_count.setObjectName("Muted")
        source_title_row.addWidget(self.selection_count)
        source_layout.addLayout(source_title_row)

        self.drop_hint = self._translated(QLabel(), tr('Arrastra aquí imágenes o carpetas. También puedes usar los botones inferiores.'))
        self.drop_hint.setObjectName("DropHint")
        self.drop_hint.setAlignment(Qt.AlignCenter)
        self.drop_hint.setWordWrap(True)
        source_layout.addWidget(self.drop_hint)

        source_buttons = QHBoxLayout()
        self.add_files_button = self._translated(QPushButton(), tr('Añadir imágenes'))
        self.add_folder_button = self._translated(QPushButton(), tr('Añadir carpeta'))
        self.remove_button = self._translated(QPushButton(), tr('Quitar selección'))
        self.clear_button = self._translated(QPushButton(), tr('Limpiar'))
        self.add_files_button.clicked.connect(self._choose_files)
        self.add_folder_button.clicked.connect(self._choose_folder)
        self.remove_button.clicked.connect(self._remove_selected)
        self.clear_button.clicked.connect(self._clear_files)
        source_buttons.addWidget(self.add_files_button)
        source_buttons.addWidget(self.add_folder_button)
        source_buttons.addStretch(1)
        source_buttons.addWidget(self.remove_button)
        source_buttons.addWidget(self.clear_button)
        source_layout.addLayout(source_buttons)

        self.file_table = QTableWidget(0, 4)
        self.file_table.setHorizontalHeaderLabels([tr("ARCHIVO"), tr("TAMAÑO"), tr("ESTADO"), tr("DETALLE")])
        self.file_table.setAlternatingRowColors(True)
        self.file_table.setShowGrid(False)
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.file_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.file_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.verticalHeader().setDefaultSectionSize(43)
        table_header = self.file_table.horizontalHeader()
        table_header.setSectionResizeMode(0, QHeaderView.Stretch)
        table_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        table_header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.file_table.itemSelectionChanged.connect(self._update_preview_from_selection)
        source_layout.addWidget(self.file_table, 1)

        source_layout.addWidget(self._section_label(tr("Directorio de salida")))
        output_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self._translated(self.output_edit, tr('Selecciona dónde guardar los resultados'), "setPlaceholderText")
        self.output_edit.textChanged.connect(self._persist_output_directory)
        self.output_button = self._translated(QPushButton(), tr('Seleccionar'))
        self.open_output_button = self._translated(QPushButton(), tr('Abrir'))
        self.output_button.clicked.connect(self._choose_output)
        self.open_output_button.clicked.connect(self._open_output)
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(self.output_button)
        output_row.addWidget(self.open_output_button)
        source_layout.addLayout(output_row)

        self.source_output_check = self._translated(QCheckBox(), tr('Guardar junto a cada imagen de entrada'))
        self._translated(self.source_output_check, tr('Cada resultado se guarda en la carpeta de su original, aunque las imágenes del lote estén en carpetas distintas.'), "setToolTip")
        self.source_output_check.toggled.connect(self._refresh_output_controls)
        source_layout.addWidget(self.source_output_check)

        model_row = QHBoxLayout()
        model_label = self._translated(QLabel(), tr('Modelo de imagen'))
        model_row.addWidget(model_label)
        self.model_combo = QComboBox()
        for model_id, label in OPENAI_IMAGE_MODELS.items():
            self.model_combo.addItem(label, model_id)
        self._translated(self.model_combo, tr('Modelo utilizado para editar todas las imágenes del lote.'), "setToolTip")
        model_row.addWidget(self.model_combo, 1)
        source_layout.addLayout(model_row)

        self.settings_toggle = QToolButton()
        self._translated(self.settings_toggle, tr('Ajustes avanzados'), "setText")
        self.settings_toggle.setCheckable(True)
        self.settings_toggle.setChecked(False)
        self.settings_toggle.setArrowType(Qt.RightArrow)
        self.settings_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.settings_toggle.toggled.connect(self._toggle_settings)
        left_layout.addWidget(self.settings_toggle)

        self.settings_panel = QFrame()
        self.settings_panel.setObjectName("SettingsPanel")
        self.settings_panel.setMinimumHeight(330)
        settings_layout = QVBoxLayout(self.settings_panel)
        settings_layout.setContentsMargins(15, 13, 15, 14)
        settings_layout.setSpacing(10)

        options_grid = QGridLayout()
        options_grid.setHorizontalSpacing(10)
        options_grid.setVerticalSpacing(8)
        self.parallel_spin = QSpinBox()
        self.parallel_spin.setRange(1, 5)
        self._translated(self.parallel_spin, tr(' imágenes'), "setSuffix")
        self._translated(self.parallel_spin, tr('Número de renders enviados simultáneamente al modelo seleccionado.'), "setToolTip")

        parallel_label = self._translated(QLabel(), tr('Imágenes simultáneas'))
        options_grid.addWidget(parallel_label, 0, 0)
        options_grid.addWidget(self.parallel_spin, 0, 1)
        processing_note = self._translated(QLabel(), tr('Cada render se envía completo al modelo seleccionado en una sola llamada. No se ejecutan detectores ni se generan máscaras.'))
        processing_note.setObjectName("Muted")
        processing_note.setWordWrap(True)
        options_grid.addWidget(processing_note, 1, 0, 1, 4)
        settings_layout.addLayout(options_grid)

        prompt_header = QHBoxLayout()
        prompt_header.addWidget(self._section_label(tr("Prompt de edición · calidad alta")))
        prompt_header.addStretch(1)
        reset_prompt_button = self._translated(QPushButton(), tr('Restaurar prompt'))
        reset_prompt_button.clicked.connect(lambda: self.prompt_edit.setPlainText(DEFAULT_PROMPT))
        prompt_header.addWidget(reset_prompt_button)
        settings_layout.addLayout(prompt_header)
        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setMinimumHeight(150)
        self.prompt_edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        settings_layout.addWidget(self.prompt_edit)
        self.settings_scroll = QScrollArea()
        self.settings_scroll.setObjectName("SettingsScroll")
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setFrameShape(QFrame.NoFrame)
        self.settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.settings_scroll.setMinimumHeight(290)
        self.settings_scroll.setWidget(self.settings_panel)
        self.settings_scroll.setVisible(False)
        left_layout.addWidget(self.settings_scroll)

        action_row = QHBoxLayout()
        self.cancel_button = self._translated(QPushButton(), tr('Cancelar'))
        self.cancel_button.setObjectName("DangerButton")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel_processing)
        self.process_button = self._translated(QPushButton(), tr('Procesar imágenes'))
        self.process_button.setObjectName("PrimaryButton")
        self.process_button.clicked.connect(self._start_processing)
        action_row.addWidget(self.cancel_button)
        action_row.addStretch(1)
        action_row.addWidget(self.process_button)
        left_layout.addLayout(action_row)

        right_card, right_layout = self._card()
        right_card.setMinimumWidth(410)
        splitter.addWidget(right_card)
        splitter.setSizes([820, 500])

        preview_header = QHBoxLayout()
        preview_header.addWidget(self._section_label(tr("Previsualización")))
        preview_header.addStretch(1)
        self.preview_name = self._translated(QLabel(), tr('Selecciona una imagen'))
        self.preview_name.setObjectName("Muted")
        preview_header.addWidget(self.preview_name)
        right_layout.addLayout(preview_header)

        self.preview_tabs = QTabWidget()
        self.preview_tabs.tabBar().setExpanding(True)
        self.preview_tabs.tabBar().setUsesScrollButtons(False)
        self.original_preview = ImagePreview(tr("Selecciona una imagen de la cola"))
        self.result_preview = ImagePreview(tr("El resultado aparecerá al completar la edición"))
        self.preview_tabs.addTab(self.original_preview, "Original")
        self.preview_tabs.addTab(self.result_preview, tr("Resultado"))
        right_layout.addWidget(self.preview_tabs, 1)

        status_card = QFrame()
        status_card.setObjectName("StatusCard")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(14, 12, 14, 13)
        status_layout.setSpacing(7)
        status_layout.addWidget(self._section_label(tr("Estado actual")))
        self.stage_label = self._translated(QLabel(), tr('Listo para procesar'))
        self.stage_label.setObjectName("StageLabel")
        self.stage_detail = self._translated(QLabel(), tr('Añade uno o varios renders para comenzar.'))
        self.stage_detail.setObjectName("DetailLabel")
        self.stage_detail.setWordWrap(True)
        status_layout.addWidget(self.stage_label)
        status_layout.addWidget(self.stage_detail)

        current_progress_row = QHBoxLayout()
        current_label = self._translated(QLabel(), tr('Imagen'))
        current_label.setObjectName("Muted")
        self.current_progress = QProgressBar()
        self.current_progress.setRange(0, RenderPipeline.STAGE_COUNT)
        self.current_progress.setValue(0)
        self.current_progress.setTextVisible(False)
        current_progress_row.addWidget(current_label)
        current_progress_row.addWidget(self.current_progress, 1)
        status_layout.addLayout(current_progress_row)

        total_progress_row = QHBoxLayout()
        total_label = self._translated(QLabel(), tr('Lote'))
        total_label.setObjectName("Muted")
        self.total_progress = QProgressBar()
        self.total_progress.setRange(0, 1)
        self.total_progress.setValue(0)
        self.total_progress.setFormat("%v / %m")
        total_progress_row.addWidget(total_label)
        total_progress_row.addWidget(self.total_progress, 1)
        status_layout.addLayout(total_progress_row)

        log_header = QHBoxLayout()
        self.log_toggle = QToolButton()
        self._set_localized_text(self.log_toggle, tr('Ver registro'))
        self.log_toggle.setCheckable(True)
        self.log_toggle.toggled.connect(self._toggle_log)
        log_header.addStretch(1)
        log_header.addWidget(self.log_toggle)
        status_layout.addLayout(log_header)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(125)
        self.log_view.document().setMaximumBlockCount(500)
        self.log_view.setVisible(False)
        status_layout.addWidget(self.log_view)
        right_layout.addWidget(status_card)


    def _set_localized_text(self, widget, message: str) -> None:
        self._dynamic_text[widget] = message
        widget.setText(render_text(message))

    def _change_language(self) -> None:
        preference = self.language_combo.currentData()
        if preference == self.language_preference:
            return
        self.language_preference = preference
        apply_language(preference, QApplication.instance())
        self.settings.setValue("language", preference)
        self.settings.sync()
        self._retranslate_ui()

    def _retranslate_ui(self) -> None:
        for widget, setter, message, uppercase in self._language_bindings:
            text = render_text(message)
            getattr(widget, setter)(text.upper() if uppercase else text)
        for widget, message in self._dynamic_text.items():
            widget.setText(render_text(message))
        self.language_combo.setItemText(0, tr("Sistema"))
        self.file_table.setHorizontalHeaderLabels([tr("ARCHIVO"), tr("TAMAÑO"), tr("ESTADO"), tr("DETALLE")])
        self.preview_tabs.setTabText(1, tr("Resultado"))
        for row, (status, detail) in self._row_messages.items():
            if row < self.file_table.rowCount():
                self.file_table.item(row, 2).setText(render_text(status))
                self.file_table.item(row, 3).setText(render_text(detail))
                self.file_table.item(row, 3).setToolTip(render_text(detail))
        scrollbar = self.log_view.verticalScrollBar()
        position = scrollbar.value()
        at_bottom = position == scrollbar.maximum()
        self.log_view.setPlainText("\n".join(render_text(message) for message in self._log_messages))
        scrollbar.setValue(scrollbar.maximum() if at_bottom else position)
        self.original_preview.retranslate()
        self.result_preview.retranslate()
        self._refresh_api_controls()

    def _load_settings(self) -> None:
        settings_version = int(self.settings.value("settings_version", 0))
        if settings_version < 7:
            for obsolete_key in (
                "yolo_model",
                "processing_mode",
                "confidence",
                "inference_size",
                "device",
                "mask_margin",
                "edge_feather",
                "detailed_detection",
                "retry_invalid_regions",
                "save_masks",
                "copy_when_empty",
            ):
                self.settings.remove(obsolete_key)
            self.settings.setValue("settings_version", 7)

        default_output = str(project_root() / "output")
        self.output_edit.setText(str(self.settings.value("output_dir", default_output)))
        self.source_output_check.setChecked(
            self.settings.value("use_source_directory", False, type=bool)
        )
        self._refresh_output_controls()

        self.parallel_spin.setValue(int(self.settings.value("parallel_jobs", 5)))
        model_index = self.model_combo.findData(
            self.settings.value("image_model", OPENAI_IMAGE_MODEL)
        )
        self.model_combo.setCurrentIndex(max(0, model_index))
        self.prompt_edit.setPlainText(str(self.settings.value("prompt", DEFAULT_PROMPT)))

    def _save_settings(self) -> None:
        self.settings.setValue("language", self.language_preference)
        self.settings.setValue("output_dir", self.output_edit.text().strip())
        self.settings.setValue("use_source_directory", self.source_output_check.isChecked())
        self.settings.setValue("parallel_jobs", self.parallel_spin.value())
        self.settings.setValue("image_model", self.model_combo.currentData())
        self.settings.setValue("prompt", self.prompt_edit.toPlainText())
        self.settings.sync()

    def _persist_output_directory(self, value: str) -> None:
        self.settings.setValue("output_dir", value.strip())

    def _refresh_api_controls(self) -> None:
        ready = has_openai_api_key(self.credential_store)
        self.api_key_input.setPlaceholderText(
            tr("Clave guardada de forma segura")
            if ready
            else tr("Introduce tu clave de OpenAI (sk-…)")
        )
        self.api_key_button.setText(
            tr("API configurada · Guardar cambios") if ready else tr("Guardar API key")
        )
        self.api_key_button.setProperty("ready", ready)
        self.api_key_button.style().unpolish(self.api_key_button)
        self.api_key_button.style().polish(self.api_key_button)

    def _store_api_key(self, *, show_confirmation: bool) -> bool:
        api_key = self.api_key_input.text().strip()
        if not api_key:
            message = (
                tr("La clave ya está guardada. Introduce una nueva clave para sustituirla.")
                if has_openai_api_key(self.credential_store)
                else tr("Introduce una clave de OpenAI.")
            )
            QMessageBox.information(self, APP_NAME, message)
            return False
        if not api_key.startswith("sk-") or len(api_key) < 20:
            QMessageBox.warning(self, APP_NAME, tr("La clave de OpenAI no parece válida."))
            return False
        try:
            self.credential_store.save_api_key(api_key)
        except (SecureStorageError, ValueError) as error:
            QMessageBox.critical(self, APP_NAME, str(error))
            return False
        self.api_key_input.clear()
        self._refresh_api_controls()
        if show_confirmation:
            QMessageBox.information(
                self,
                APP_NAME,
                tr("Clave guardada localmente en el almacén seguro de tu sistema."),
            )
        return True

    def _save_api_key(self) -> None:
        self._store_api_key(show_confirmation=True)

    def _toggle_settings(self, visible: bool) -> None:
        self.settings_toggle.setArrowType(Qt.DownArrow if visible else Qt.RightArrow)
        self.settings_scroll.setVisible(visible)

    def _toggle_log(self, visible: bool) -> None:
        self._set_localized_text(self.log_toggle, tr('Ocultar registro') if visible else tr('Ver registro'))
        self.log_view.setVisible(visible)

    def _choose_files(self) -> None:
        start = str(self.settings.value("last_input_dir", str(project_root())))
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            tr("Seleccionar renders"),
            start,
            tr("Imágenes (*.png *.jpg *.jpeg *.webp *.tif *.tiff *.bmp)"),
        )
        if paths:
            self.settings.setValue("last_input_dir", str(Path(paths[0]).parent))
            self._add_paths([Path(path) for path in paths])

    def _choose_folder(self) -> None:
        start = str(self.settings.value("last_input_dir", str(project_root())))
        chosen = QFileDialog.getExistingDirectory(self, tr("Seleccionar carpeta de renders"), start)
        if not chosen:
            return
        directory = Path(chosen)
        self.settings.setValue("last_input_dir", str(directory))
        discovered = sorted(
            (
                path
                for path in directory.rglob("*")
                if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
            ),
            key=lambda path: str(path).lower(),
        )
        if not discovered:
            QMessageBox.information(self, APP_NAME, tr("No se encontraron imágenes compatibles en la carpeta."))
            return
        self._add_paths(discovered)

    def _choose_output(self) -> None:
        start = self.output_edit.text().strip() or str(project_root())
        chosen = QFileDialog.getExistingDirectory(self, tr("Seleccionar directorio de salida"), start)
        if chosen:
            self.output_edit.setText(chosen)

    def _open_output(self) -> None:
        value = self.output_edit.text().strip()
        if not value:
            return
        output = Path(value)
        output.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(output.resolve())))

    def _refresh_output_controls(self) -> None:
        enabled = self.source_output_check.isEnabled() and not self.processing
        shared_output = enabled and not self.source_output_check.isChecked()
        self.output_edit.setEnabled(shared_output)
        self.output_button.setEnabled(shared_output)
        self.open_output_button.setEnabled(shared_output)

    def _add_paths(self, candidates: list[Path]) -> None:
        if self.processing:
            return
        existing = {self._key(path) for path in self.files}
        added = 0
        for candidate in candidates:
            if candidate.is_dir():
                nested = [
                    path
                    for path in candidate.rglob("*")
                    if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
                ]
                self._add_paths(nested)
                continue
            if not candidate.is_file() or candidate.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
                continue
            resolved = candidate.resolve()
            key = self._key(resolved)
            if key in existing:
                continue
            self.files.append(resolved)
            existing.add(key)
            added += 1
        if added:
            self._rebuild_table()
            if self.file_table.rowCount() and not self.file_table.selectedItems():
                self.file_table.selectRow(0)

    def _remove_selected(self) -> None:
        rows = sorted({index.row() for index in self.file_table.selectionModel().selectedRows()}, reverse=True)
        for row in rows:
            if 0 <= row < len(self.files):
                removed = self.files.pop(row)
                self.results.pop(self._key(removed), None)
        self._rebuild_table()

    def _clear_files(self) -> None:
        if self.processing:
            return
        self.files.clear()
        self.results.clear()
        self._rebuild_table()
        self.original_preview.clear_image()
        self.result_preview.clear_image()
        self._set_localized_text(self.preview_name, tr('Selecciona una imagen'))

    @staticmethod
    def _image_dimensions(path: Path) -> str:
        reader = QImageReader(str(path))
        size = reader.size()
        if not size.isValid():
            return "—"
        return f"{size.width()} × {size.height()}"

    def _rebuild_table(self) -> None:
        self._row_messages.clear()
        self.file_table.setRowCount(len(self.files))
        for row, path in enumerate(self.files):
            name_item = QTableWidgetItem(path.name)
            name_item.setToolTip(str(path))
            name_item.setData(Qt.UserRole, str(path))
            size_item = QTableWidgetItem(self._image_dimensions(path))
            status_item = QTableWidgetItem(tr("Pendiente"))
            self._row_messages[row] = (tr("Pendiente"), "")
            detail_item = QTableWidgetItem("")
            self.file_table.setItem(row, 0, name_item)
            self.file_table.setItem(row, 1, size_item)
            self.file_table.setItem(row, 2, status_item)
            self.file_table.setItem(row, 3, detail_item)
            result = self.results.get(self._key(path))
            if result:
                state = "success" if result.status == "completed" else "skipped"
                status = tr("Completada") if result.status == "completed" else tr("Omitida")
                self._set_row_status(row, status, result.message, state)
        count = len(self.files)
        self._set_localized_text(self.selection_count, tr('{count} imagen' if count == 1 else '{count} imágenes', count=count))
        self.process_button.setEnabled(bool(self.files) and not self.processing)
        self.remove_button.setEnabled(bool(self.files) and not self.processing)
        self.clear_button.setEnabled(bool(self.files) and not self.processing)

    def _set_row_status(self, row: int, status: str, detail: str, state: str) -> None:
        if not 0 <= row < self.file_table.rowCount():
            return
        self._row_messages[row] = (status, detail)
        colors = {
            "working": "#72E2C3",
            "success": "#6FE0A4",
            "skipped": "#E7C66A",
            "error": "#FF8F85",
            "pending": "#A7B1BA",
        }
        status_item = self.file_table.item(row, 2)
        detail_item = self.file_table.item(row, 3)
        status_item.setText(render_text(status))
        status_item.setForeground(QBrush(QColor(colors.get(state, colors["pending"]))))
        detail_item.setText(render_text(detail))
        detail_item.setToolTip(render_text(detail))

    def _selected_row(self) -> int | None:
        rows = self.file_table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    def _update_preview_from_selection(self) -> None:
        row = self._selected_row()
        if row is None or not 0 <= row < len(self.files):
            return
        path = self.files[row]
        self._set_localized_text(self.preview_name, path.name)
        self.preview_name.setToolTip(str(path))
        self.original_preview.set_image(path)
        result = self.results.get(self._key(path))
        if result:
            self.result_preview.set_image(result.output_path)
        else:
            self.result_preview.clear_image()

    def _processing_options(self) -> ProcessingOptions:
        return ProcessingOptions(
            parallel_jobs=self.parallel_spin.value(),
            prompt=self.prompt_edit.toPlainText().strip(),
            image_model=self.model_combo.currentData(),
            use_source_directory=self.source_output_check.isChecked(),
        )

    def _start_processing(self) -> None:
        if self.processing or not self.files:
            return
        missing = [path for path in self.files if not path.is_file()]
        if missing:
            QMessageBox.warning(self, APP_NAME, tr("Ya no existe el archivo:\n{path}", path=missing[0]))
            return
        output_value = self.output_edit.text().strip()
        if not output_value and not self.source_output_check.isChecked():
            QMessageBox.warning(self, APP_NAME, tr("Selecciona un directorio de salida."))
            return
        try:
            options = self._processing_options()
            options.validate()
            output_dir = None
            if not options.use_source_directory:
                output_dir = Path(output_value).expanduser().resolve()
                output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as error:
            QMessageBox.warning(self, APP_NAME, str(error))
            return

        self._save_settings()
        existing_by_row = {
            row: paths
            for row, source_path in enumerate(self.files)
            if (paths := existing_result_paths(
                options.output_directory_for(source_path, output_dir), source_path.stem
            ))
        }
        skip_existing = False
        if existing_by_row:
            dialog = QMessageBox(self)
            dialog.setIcon(QMessageBox.Question)
            dialog.setWindowTitle(APP_NAME)
            dialog.setText(
                tr("Ya existen resultados para {existing} de {total} imagen(es).",
                   existing=len(existing_by_row), total=len(self.files))
            )
            dialog.setInformativeText(
                tr("¿Quieres volver a procesarlas? Los resultados anteriores se conservarán y "
                "los nuevos se guardarán con un sufijo como _2 o _3.")
            )
            reprocess_button = dialog.addButton(
                tr("Reprocesar y renombrar"),
                QMessageBox.AcceptRole,
            )
            skip_button = dialog.addButton(
                tr("Omitir las procesadas"),
                QMessageBox.ActionRole,
            )
            cancel_button = dialog.addButton(QMessageBox.Cancel)
            dialog.setDefaultButton(skip_button)
            dialog.setEscapeButton(cancel_button)
            dialog.exec_()
            if dialog.clickedButton() is cancel_button:
                return
            skip_existing = dialog.clickedButton() is skip_button

        self.results.clear()
        pending: list[tuple[int, Path]] = []
        for row, source_path in enumerate(self.files):
            if skip_existing and row in existing_by_row:
                existing_output = existing_by_row[row][-1]
                message = tr("Ya procesada: se conserva {filename}.", filename=existing_output.name)
                self.results[self._key(source_path)] = PipelineItemResult(
                    source_path=source_path,
                    status="skipped",
                    message=message,
                    output_path=existing_output,
                )
                self._set_row_status(row, tr("Ya procesada"), message, "skipped")
            else:
                pending.append((row, source_path))
                self._set_row_status(row, tr("En cola"), "", "pending")

        if not pending:
            self.total_progress.setRange(0, len(self.files))
            self.total_progress.setValue(len(self.files))
            self._set_localized_text(self.stage_label, tr('No hay imágenes pendientes'))
            self._set_localized_text(self.stage_detail, tr('Todos los resultados existentes se han conservado sin consumir la API.'))
            self._update_preview_from_selection()
            return

        if self.api_key_input.text().strip() and not self._store_api_key(show_confirmation=False):
            return
        self._refresh_api_controls()
        if not has_openai_api_key(self.credential_store):
            QMessageBox.warning(
                self,
                APP_NAME,
                tr("Introduce y guarda una clave de OpenAI antes de procesar."),
            )
            self._rebuild_table()
            self._update_preview_from_selection()
            return

        skipped_existing = len(self.files) - len(pending)

        self.processing = True
        self._set_controls_enabled(False)
        self.cancel_button.setEnabled(True)
        self._set_localized_text(self.process_button, tr('Procesando…'))
        self.current_progress.setValue(0)
        self.total_progress.setRange(0, len(self.files))
        self.total_progress.setValue(skipped_existing)
        self._set_localized_text(self.stage_label, tr('Preparando el lote'))
        self._set_localized_text(self.stage_detail, tr('{count} imagen(es) en cola · hasta {parallel} simultáneas · {model}', count=len(pending), parallel=options.parallel_jobs, model=OPENAI_IMAGE_MODELS[options.image_model]))
        self.log_view.clear()
        self._log_messages.clear()
        self._append_log(tr("Modelo del lote: {model} · calidad alta", model=options.image_model))
        self._append_log(
            tr("Salida: carpeta de cada imagen de entrada")
            if options.use_source_directory else tr("Salida: {directory}", directory=output_dir)
        )

        thread = QThread(self)
        worker = ProcessingWorker(
            [source_path for _row, source_path in pending],
            output_dir,
            options,
            row_indices=[row for row, _source_path in pending],
            initial_skipped=skipped_existing,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.item_stage.connect(self._on_item_stage)
        worker.item_finished.connect(self._on_item_finished)
        worker.item_failed.connect(self._on_item_failed)
        worker.batch_progress.connect(self._on_batch_progress)
        worker.log_message.connect(self._append_log)
        worker.finished.connect(self._on_batch_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_thread_stopped)
        thread.finished.connect(thread.deleteLater)
        self.thread = thread
        self.worker = worker
        thread.start()

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.api_key_input.setEnabled(enabled)
        self.api_key_button.setEnabled(enabled)
        self.add_files_button.setEnabled(enabled)
        self.add_folder_button.setEnabled(enabled)
        self.source_output_check.setEnabled(enabled)
        self._refresh_output_controls()
        self.model_combo.setEnabled(enabled)
        self.settings_toggle.setEnabled(enabled)
        self.settings_panel.setEnabled(enabled)
        self.file_table.setDragEnabled(False)
        self.remove_button.setEnabled(enabled and bool(self.files))
        self.clear_button.setEnabled(enabled and bool(self.files))
        self.process_button.setEnabled(enabled and bool(self.files))

    def _on_item_stage(self, row: int, title: str, detail: str, step: int) -> None:
        filename = self.files[row].name if 0 <= row < len(self.files) else tr("Imagen")
        self._set_localized_text(self.stage_label, tr('{title} · {filename}', title=title, filename=filename))
        self._set_localized_text(self.stage_detail, detail)
        if step in {2, 4}:
            self.current_progress.setRange(0, 0)
        else:
            self.current_progress.setRange(0, RenderPipeline.STAGE_COUNT)
            self.current_progress.setValue(step)
        self._set_row_status(row, title, detail, "working")
        if self._selected_row() != row:
            self.file_table.selectRow(row)
        QApplication.processEvents()

    def _on_item_finished(self, row: int, result: PipelineItemResult) -> None:
        self.results[self._key(result.source_path)] = result
        if result.status == "completed":
            status, state = tr("Completada"), "success"
        else:
            status, state = tr("Omitida"), "skipped"
        self._set_row_status(row, status, result.message, state)
        if self._selected_row() == row:
            self._update_preview_from_selection()
            if result.output_path:
                self.preview_tabs.setCurrentWidget(self.result_preview)

    def _on_item_failed(self, row: int, message: str) -> None:
        self._set_row_status(row, "Error", message, "error")
        self._set_localized_text(self.stage_label, tr('Error de procesado'))
        self._set_localized_text(self.stage_detail, message)
        self.log_toggle.setChecked(True)

    def _on_batch_progress(self, completed: int, total: int) -> None:
        self.total_progress.setRange(0, max(1, total))
        self.total_progress.setValue(completed)

    def _append_log(self, message: str) -> None:
        self._log_messages.append(message)
        self.log_view.appendPlainText(render_text(message))

    def _on_batch_finished(self, cancelled: bool, succeeded: int, failed: int, skipped: int) -> None:
        self.cancel_button.setEnabled(False)
        processed = succeeded + failed + skipped
        self.current_progress.setRange(0, RenderPipeline.STAGE_COUNT)
        self.total_progress.setValue(processed)
        if cancelled:
            self._set_localized_text(self.stage_label, tr('Procesado cancelado'))
            self._set_localized_text(self.stage_detail, tr('Completadas: {succeeded} · Sin procesar/omitidas: {skipped} · Errores: {failed}', succeeded=succeeded, skipped=skipped, failed=failed))
        elif failed:
            self._set_localized_text(self.stage_label, tr('Lote terminado con incidencias'))
            self._set_localized_text(self.stage_detail, tr('Completadas: {succeeded} · Omitidas/copias: {skipped} · Errores: {failed}', succeeded=succeeded, skipped=skipped, failed=failed))
        else:
            self._set_localized_text(self.stage_label, tr('Lote completado'))
            self._set_localized_text(self.stage_detail, tr('Completadas con IA: {succeeded} · Omitidas: {skipped}', succeeded=succeeded, skipped=skipped))
            self.current_progress.setValue(RenderPipeline.STAGE_COUNT)

    def _on_thread_stopped(self) -> None:
        self.processing = False
        self.worker = None
        self.thread = None
        self._set_localized_text(self.process_button, tr('Procesar imágenes'))
        self._set_controls_enabled(True)
        if self._close_after_cancel:
            self._close_after_cancel = False
            QTimer.singleShot(0, self.close)

    def _cancel_processing(self) -> None:
        if not self.worker:
            return
        self.worker.request_cancel()
        self.cancel_button.setEnabled(False)
        self._set_localized_text(self.stage_label, tr('Cancelando…'))
        self._set_localized_text(self.stage_detail, tr('La cancelación se aplicará al terminar la operación activa. Una llamada a la API no puede interrumpirse a mitad.'))

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self.processing or not event.mimeData().hasUrls():
            event.ignore()
            return
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        if any(path.is_dir() or path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS for path in paths):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt API
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        self._add_paths(paths)
        event.acceptProposedAction()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self.processing:
            answer = QMessageBox.question(
                self,
                APP_NAME,
                tr("Hay un lote en proceso. ¿Quieres cancelarlo y cerrar cuando termine la operación activa?"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                self._close_after_cancel = True
                self._cancel_processing()
            event.ignore()
            return
        self._save_settings()
        event.accept()
