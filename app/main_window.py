"""
Ventana principal de la aplicación Renombrador Multimedia.
"""

import os
import sys
import logging
from typing import List, Optional, Tuple

from app.qt_compat import QtWidgets, QtCore, QtGui, Signal
from app.media_parser import MediaFileInfo, sanitize_filename, find_associated_subtitles
from app.file_ops import (
    RenameGroup,
    RenameRecord,
    execute_rename_groups,
    ExistingDestinationError,
    DuplicateDestinationError,
    RenameError,
)
from app.tvmaze_client import TVmazeClient
from app.renamer_worker import ScanAndQueryWorker
from app.dialogs import ConfirmRenameDialog, ShowSearchDialog
from app.styles import MODERN_STYLE

logger = logging.getLogger(__name__)


class RenameButton(QtWidgets.QPushButton):
    """Botón personalizado que mantiene una referencia directa a su MediaFileInfo."""
    def __init__(self, file_info: MediaFileInfo, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__("✓ Renombrar", parent)
        self.file_info = file_info
        self.setProperty("class", "btn-rename-row")
        self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))


class MainWindow(QtWidgets.QMainWindow):
    """
    Ventana principal de la aplicación.
    """

    def __init__(self, initial_directory: Optional[str] = None):
        super().__init__()
        self.setWindowTitle("Renombrador Multimedia - Series y Películas con TVmaze")
        self.resize(1260, 760)
        self.setMinimumSize(940, 540)

        # Estado interno
        self.file_items: List[MediaFileInfo] = []
        self.worker: Optional[ScanAndQueryWorker] = None
        self._scan_cancelled = False
        self.tvmaze_client = TVmazeClient()
        # Historial para deshacer: (cambios realizados, archivo asociado).
        self.rename_history: List[Tuple[RenameRecord, MediaFileInfo]] = []

        # Construir Interfaz
        self._init_ui()
        self.setStyleSheet(MODERN_STYLE)

        # Si se pasó directorio inicial (por argumento o configuración)
        if initial_directory and os.path.exists(initial_directory):
            self.dir_input.setText(os.path.abspath(initial_directory))

    def _init_ui(self):
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 12)
        main_layout.setSpacing(12)

        # 1. Cabecera Informativa
        header_layout = QtWidgets.QHBoxLayout()
        title_box = QtWidgets.QVBoxLayout()
        lbl_title = QtWidgets.QLabel("🎬 Renombrador Multimedia")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #0f172a;")
        lbl_desc = QtWidgets.QLabel(
            "Identifica y renombra archivos de series y películas mediante la API de TVmaze de forma segura."
        )
        lbl_desc.setStyleSheet("color: #475569; font-size: 13px;")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_desc)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        # Botón Deshacer en cabecera
        self.btn_undo = QtWidgets.QPushButton("↩ Deshacer Último Renombrado")
        self.btn_undo.setEnabled(False)
        self.btn_undo.setToolTip("Restaura el nombre anterior del último archivo renombrado.")
        self.btn_undo.clicked.connect(self._undo_last_rename)
        header_layout.addWidget(self.btn_undo)

        main_layout.addLayout(header_layout)

        # 2. Panel de Selección de Directorio y Opciones
        panel_group = QtWidgets.QGroupBox("1. Directorio y Configuración de Escaneo")
        panel_layout = QtWidgets.QVBoxLayout(panel_group)
        panel_layout.setSpacing(10)

        # Fila 1: Selector de Directorio
        dir_layout = QtWidgets.QHBoxLayout()
        lbl_dir = QtWidgets.QLabel("Carpeta:")
        lbl_dir.setStyleSheet("font-weight: bold; min-width: 60px; color: #0f172a;")
        dir_layout.addWidget(lbl_dir)

        self.dir_input = QtWidgets.QLineEdit()
        self.dir_input.setPlaceholderText("Selecciona o arrastra una carpeta con series o películas...")
        dir_layout.addWidget(self.dir_input)

        btn_browse = QtWidgets.QPushButton("📁 Examinar...")
        btn_browse.clicked.connect(self._on_browse_directory)
        dir_layout.addWidget(btn_browse)

        self.btn_scan = QtWidgets.QPushButton("🔍 Analizar y Buscar en TVmaze")
        self.btn_scan.setObjectName("btn_scan")
        self.btn_scan.clicked.connect(self._start_scan)
        dir_layout.addWidget(self.btn_scan)

        self.btn_stop = QtWidgets.QPushButton("⏹ Detener")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_scan)
        dir_layout.addWidget(self.btn_stop)

        panel_layout.addLayout(dir_layout)

        # Fila 2: Opciones de formato y subcarpetas
        opts_layout = QtWidgets.QHBoxLayout()
        self.chk_subdirs = QtWidgets.QCheckBox("Escanear subdirectorios")
        self.chk_subdirs.setChecked(False)
        opts_layout.addWidget(self.chk_subdirs)

        opts_layout.addSpacing(15)

        self.chk_subtitles = QtWidgets.QCheckBox("Renombrar subtítulos asociados (.srt, etc.)")
        self.chk_subtitles.setChecked(True)
        self.chk_subtitles.setToolTip("Si existe un archivo de subtítulo con el mismo nombre, se renombrará a la par.")
        opts_layout.addWidget(self.chk_subtitles)

        opts_layout.addSpacing(15)

        lbl_format = QtWidgets.QLabel("Formato:")
        lbl_format.setStyleSheet("font-weight: 500; color: #0f172a;")
        opts_layout.addWidget(lbl_format)

        self.combo_format = QtWidgets.QComboBox()
        self.combo_format.addItem(
            "{show} - S{season:02d}E{episode:02d} - {title}{ext}",
            userData="{show} - S{season:02d}E{episode:02d} - {title}{ext}"
        )
        self.combo_format.addItem(
            "{show} - {season}x{episode:02d} - {title}{ext}",
            userData="{show} - {season}x{episode:02d} - {title}{ext}"
        )
        self.combo_format.addItem(
            "S{season:02d}E{episode:02d} - {title}{ext}",
            userData="S{season:02d}E{episode:02d} - {title}{ext}"
        )
        self.combo_format.addItem(
            "{show} S{season:02d}E{episode:02d}{ext}",
            userData="{show} S{season:02d}E{episode:02d}{ext}"
        )
        opts_layout.addWidget(self.combo_format)

        opts_layout.addSpacing(15)

        self.chk_confirm_each = QtWidgets.QCheckBox("Pedir confirmación para cada archivo")
        self.chk_confirm_each.setChecked(True)
        opts_layout.addWidget(self.chk_confirm_each)

        opts_layout.addStretch()
        panel_layout.addLayout(opts_layout)

        main_layout.addWidget(panel_group)

        # 3. Barra de Acciones y Filtros de la Tabla
        filter_layout = QtWidgets.QHBoxLayout()

        self.search_filter = QtWidgets.QLineEdit()
        self.search_filter.setPlaceholderText("🔍 Filtrar lista de archivos por nombre...")
        self.search_filter.textChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.search_filter, 2)

        self.combo_type_filter = QtWidgets.QComboBox()
        self.combo_type_filter.addItems(["Todos los tipos", "Series", "Películas"])
        self.combo_type_filter.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.combo_type_filter)

        filter_layout.addSpacing(15)

        btn_select_all = QtWidgets.QPushButton("Seleccionar Todos")
        btn_select_all.clicked.connect(lambda: self._set_all_checkboxes(True))
        filter_layout.addWidget(btn_select_all)

        btn_deselect_all = QtWidgets.QPushButton("Deseleccionar")
        btn_deselect_all.clicked.connect(lambda: self._set_all_checkboxes(False))
        filter_layout.addWidget(btn_deselect_all)

        self.btn_bulk_rename = QtWidgets.QPushButton("⚡ Renombrar Seleccionados")
        self.btn_bulk_rename.setStyleSheet(
            "background-color: #0284c7; color: #ffffff !important; font-weight: bold; padding: 6px 14px;"
        )
        self.btn_bulk_rename.clicked.connect(self._on_bulk_rename)
        filter_layout.addWidget(self.btn_bulk_rename)

        main_layout.addLayout(filter_layout)

        # 4. Tabla Principal
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Sel.", "Estado", "Tipo", "Nombre Actual", "Nombre Sugerido (Doble clic para editar)", "Acción"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Stretch)

        # La columna "Acción" necesita ancho suficiente para el texto completo
        # del botón, tanto al mostrar "✓ Renombrar" como "Renombrado ✓".
        self.table.horizontalHeader().setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.Interactive)
        action_font = QtGui.QFont(self.font())
        action_font.setBold(True)
        action_metrics = QtGui.QFontMetrics(action_font)
        action_width = max(
            action_metrics.horizontalAdvance("✓ Renombrar"),
            action_metrics.horizontalAdvance("Renombrado ✓"),
        ) + 44
        self.table.setColumnWidth(5, action_width)

        # Filas un poco más altas para que el botón y el texto respiren.
        self.table.verticalHeader().setDefaultSectionSize(38)

        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        self.table.cellChanged.connect(self._on_cell_edited)

        main_layout.addWidget(self.table, 1)

        # 5. Barra Inferior con Progreso y Resumen
        bottom_layout = QtWidgets.QHBoxLayout()

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimum(0)
        bottom_layout.addWidget(self.progress_bar, 1)

        self.lbl_stats = QtWidgets.QLabel("Listo. Selecciona una carpeta y pulsa 'Analizar'.")
        self.lbl_stats.setStyleSheet("font-weight: 500; color: #334155;")
        bottom_layout.addWidget(self.lbl_stats)

        main_layout.addLayout(bottom_layout)

        # Barra de estado
        self.status_bar = QtWidgets.QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Esperando inicio...")

        # Habilitar Drag & Drop de carpetas
        self.setAcceptDrops(True)

    # ------------------ Drag & Drop ------------------
    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QtGui.QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if os.path.isdir(path):
                self.dir_input.setText(path)
                self._start_scan()
            elif os.path.isfile(path):
                self.dir_input.setText(os.path.dirname(path))
                self._start_scan()

    # ------------------ Selección de Directorio ------------------
    def _on_browse_directory(self):
        curr = self.dir_input.text().strip() or os.path.expanduser("~")
        chosen = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Seleccionar Carpeta con Videos", curr
        )
        if chosen:
            self.dir_input.setText(chosen)

    # ------------------ Escaneo y Proceso en Segundo Plano ------------------
    def _start_scan(self):
        directory = self.dir_input.text().strip()
        if not directory:
            QtWidgets.QMessageBox.warning(
                self, "Aviso", "Por favor selecciona una carpeta para escanear."
            )
            return

        if not os.path.exists(directory) or not os.path.isdir(directory):
            QtWidgets.QMessageBox.critical(
                self, "Error", f"La carpeta seleccionada no existe:\n{directory}"
            )
            return

        # Evitar dos escaneos simultáneos (p. ej. al soltar una carpeta mientras
        # el anterior sigue en marcha). Los dos workers competirían por la tabla.
        if self.worker is not None and self.worker.isRunning():
            self.status_bar.showMessage(
                "Ya hay un escaneo en curso. Deténlo antes de iniciar otro.", 5000
            )
            return

        # Limpiar tabla y estado previo
        self.file_items.clear()
        self.table.setRowCount(0)
        self._scan_cancelled = False
        self.btn_scan.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_stats.setText("Buscando archivos multimedia en la carpeta...")

        pattern = self.combo_format.currentData() or "{show} - S{season:02d}E{episode:02d} - {title}{ext}"
        include_subdirs = self.chk_subdirs.isChecked()

        self.worker = ScanAndQueryWorker(
            directory=directory,
            include_subdirs=include_subdirs,
            format_pattern=pattern,
            parent=self
        )
        self.worker.scan_started.connect(self._on_worker_started)
        self.worker.progress_updated.connect(self._on_worker_progress)
        self.worker.file_processed.connect(self._on_file_processed)
        self.worker.scan_finished.connect(self._on_worker_finished)
        self.worker.error_occurred.connect(self._on_worker_error)
        self.worker.start()

    def _stop_scan(self):
        worker = self.worker
        if worker is not None and worker.isRunning():
            self._scan_cancelled = True
            self.lbl_stats.setText("Deteniendo escaneo...")
            self.btn_stop.setEnabled(False)
            worker.cancel()
            # No se fuerza la habilitación de "Analizar": el worker puede tardar
            # en terminar una petición de red. El handler de finalización será
            # quien restaure la interfaz cuando realmente haya acabado.
            if not worker.wait(3000):
                self.status_bar.showMessage(
                    "El escaneo sigue finalizando; espera un momento...", 5000
                )
        else:
            self.btn_stop.setEnabled(False)
            self.btn_scan.setEnabled(True)
            if self.progress_bar.isVisible():
                self.progress_bar.setVisible(False)

    def _is_current_worker(self) -> bool:
        """Ignora señales tardías de un worker que ya fue reemplazado."""
        sender = self.sender()
        return sender is None or sender is self.worker

    def _on_worker_started(self, total: int):
        if not self._is_current_worker():
            return
        self.progress_bar.setMaximum(total if total > 0 else 1)
        self.lbl_stats.setText(f"Encontrados {total} archivos multimedia. Consultando TVmaze...")

    def _on_worker_progress(self, current: int, total: int, filename: str):
        if not self._is_current_worker():
            return
        self.progress_bar.setValue(current)
        self.status_bar.showMessage(f"Analizando [{current}/{total}]: {filename}")

    def _on_file_processed(self, info: MediaFileInfo):
        if not self._is_current_worker():
            return
        self.file_items.append(info)
        self._add_row_to_table(info)
        self._update_summary_labels()

    def _on_worker_finished(self, processed: int, total: int):
        if not self._is_current_worker():
            return
        cancelled = self._scan_cancelled
        self.worker = None
        self._scan_cancelled = False
        self.btn_scan.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress_bar.setVisible(False)
        if cancelled:
            self.lbl_stats.setText("Escaneo cancelado por el usuario.")
            self.status_bar.showMessage("Escaneo cancelado por el usuario.", 4000)
        else:
            self.status_bar.showMessage(f"Completado: {processed} archivos analizados.")
        self._update_summary_labels()

        if total == 0 and not cancelled:
            QtWidgets.QMessageBox.information(
                self, "Información", "No se encontraron archivos de video compatibles en la carpeta."
            )

    def _on_worker_error(self, message: str):
        if not self._is_current_worker():
            return
        self.worker = None
        self._scan_cancelled = False
        self.btn_scan.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress_bar.setVisible(False)
        QtWidgets.QMessageBox.critical(self, "Error en Escaneo", message)

    def closeEvent(self, event: QtGui.QCloseEvent):
        """Cancela y espera al worker antes de cerrar la ventana."""
        worker = self.worker
        if worker is not None and worker.isRunning():
            worker.cancel()
            # El timeout HTTP del worker es de 8 s; se deja margen suficiente.
            if not worker.wait(10000):
                logger.warning(
                    "El escaneo no terminó a tiempo al cerrar; se fuerza la parada."
                )
                worker.terminate()
                worker.wait(1000)
        self.worker = None
        event.accept()

    # ------------------ Renderizado de la Tabla ------------------
    def _add_row_to_table(self, info: MediaFileInfo):
        self.table.blockSignals(True)
        row = self.table.rowCount()
        self.table.insertRow(row)

        dark_text_brush = QtGui.QBrush(QtGui.QColor("#0f172a"))

        # Col 0: Checkbox
        chk_item = QtWidgets.QTableWidgetItem()
        chk_item.setFlags(QtCore.Qt.ItemFlag.ItemIsUserCheckable | QtCore.Qt.ItemFlag.ItemIsEnabled)
        chk_item.setCheckState(QtCore.Qt.CheckState.Checked)
        chk_item.setData(QtCore.Qt.ItemDataRole.UserRole, info)
        self.table.setItem(row, 0, chk_item)

        # Col 1: Estado (Badge)
        status_widget = self._create_status_badge(info.status)
        self.table.setCellWidget(row, 1, status_widget)

        # Col 2: Tipo
        type_str = "📺 Serie" if info.media_type == "series" else "🎬 Película"
        type_item = QtWidgets.QTableWidgetItem(type_str)
        type_item.setForeground(dark_text_brush)
        type_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable)
        type_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 2, type_item)

        # Col 3: Nombre Actual
        orig_item = QtWidgets.QTableWidgetItem(info.original_filename)
        orig_item.setForeground(dark_text_brush)
        orig_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable)
        orig_item.setToolTip(f"Ruta completa:\n{info.file_path}")
        self.table.setItem(row, 3, orig_item)

        # Col 4: Nombre Sugerido (Editable)
        sugg_text = info.suggested_filename or info.original_filename
        sugg_item = QtWidgets.QTableWidgetItem(sugg_text)
        sugg_item.setForeground(dark_text_brush)
        sugg_item.setFlags(
            QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEditable
        )
        tooltip = "Haz doble clic para editar manualmente el nombre propuesto antes de aceptar."
        if info.error_message:
            tooltip = f"{info.error_message}\n\n{tooltip}"
        sugg_item.setToolTip(tooltip)
        self.table.setItem(row, 4, sugg_item)

        # Col 5: Botón de Acción individual
        btn_action = RenameButton(info)
        btn_action.clicked.connect(lambda: self._on_single_rename_clicked(btn_action))
        self.table.setCellWidget(row, 5, btn_action)

        self.table.blockSignals(False)

    def _create_status_badge(self, status: str) -> QtWidgets.QWidget:
        """Crea una etiqueta estilizada para representar el estado del archivo."""
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        lbl = QtWidgets.QLabel()
        lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        if status == "ready":
            lbl.setText("Listo")
            lbl.setStyleSheet(
                "background-color: #e0f2fe; color: #0369a1 !important; border: 1px solid #bae6fd; border-radius: 4px; padding: 2px 8px; font-weight: bold;"
            )
        elif status == "renamed":
            lbl.setText("Renombrado ✓")
            lbl.setStyleSheet(
                "background-color: #dcfce7; color: #15803d !important; border: 1px solid #bbf7d0; border-radius: 4px; padding: 2px 8px; font-weight: bold;"
            )
        elif status == "error":
            lbl.setText("Error ⚠️")
            lbl.setStyleSheet(
                "background-color: #fee2e2; color: #b91c1c !important; border: 1px solid #fecaca; border-radius: 4px; padding: 2px 8px; font-weight: bold;"
            )
        else:
            lbl.setText("Pendiente")
            lbl.setStyleSheet(
                "background-color: #f1f5f9; color: #475569 !important; border: 1px solid #e2e8f0; border-radius: 4px; padding: 2px 8px;"
            )

        layout.addWidget(lbl)
        return container

    def _update_row_status(self, row: int, status: str):
        status_widget = self._create_status_badge(status)
        self.table.setCellWidget(row, 1, status_widget)

    def _update_summary_labels(self):
        total = len(self.file_items)
        renamed = sum(1 for i in self.file_items if i.status == "renamed")
        ready = sum(1 for i in self.file_items if i.status == "ready")
        self.lbl_stats.setText(
            f"Total: {total} archivos | Listos para renombrar: {ready} | Renombrados: {renamed}"
        )
        self.btn_undo.setEnabled(len(self.rename_history) > 0)

    # ------------------ Edición en Celda de Nombre Sugerido ------------------
    def _on_cell_edited(self, row: int, col: int):
        if col == 4:
            item = self.table.item(row, col)
            chk_item = self.table.item(row, 0)
            if item and chk_item:
                info: MediaFileInfo = chk_item.data(QtCore.Qt.ItemDataRole.UserRole)
                if info:
                    new_val = item.text().strip()
                    if not new_val.lower().endswith(info.extension.lower()):
                        new_val += info.extension
                    info.suggested_filename = sanitize_filename(new_val)
                    if item.text() != info.suggested_filename:
                        self.table.blockSignals(True)
                        item.setText(info.suggested_filename)
                        self.table.blockSignals(False)

    # ------------------ Renombrado Individual (Con Confirmación) ------------------
    def _on_single_rename_clicked(self, button: RenameButton):
        info = button.file_info
        if not info or info.status == "renamed":
            return

        row = self._find_row_for_info(info)
        if row is None:
            return

        sugg_item = self.table.item(row, 4)
        new_filename = sugg_item.text().strip() if sugg_item else info.suggested_filename

        if not new_filename:
            QtWidgets.QMessageBox.warning(self, "Aviso", "No hay un nombre sugerido válido.")
            return

        if new_filename == info.original_filename:
            QtWidgets.QMessageBox.information(
                self, "Sin Cambios", "El nombre sugerido es idéntico al actual."
            )
            return

        # REQUISITO EXPRESO: "Que no cambie ningún nombre de archivo sin preguntar."
        if self.chk_confirm_each.isChecked():
            confirm_dialog = ConfirmRenameDialog([(info.file_path, new_filename)], parent=self)
            if confirm_dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
                return

        self._execute_rename(info, new_filename, row, button)

    def _build_rename_group(self, info: MediaFileInfo, new_filename: str) -> RenameGroup:
        """Prepara el renombrado del video y de sus subtítulos asociados."""
        dest_path = os.path.join(info.directory, new_filename)
        subtitles: List[Tuple[str, str]] = []
        if self.chk_subtitles.isChecked():
            new_base, _ = os.path.splitext(new_filename)
            for sub_old_path, sub_ext in find_associated_subtitles(info.file_path):
                sub_new_path = os.path.join(info.directory, f"{new_base}{sub_ext}")
                subtitles.append((sub_old_path, sub_new_path))
        return RenameGroup(info.file_path, dest_path, subtitles)

    def _run_rename_groups(
        self, groups: List[RenameGroup]
    ) -> Optional[List[Optional[RenameRecord]]]:
        """
        Ejecuta los renombrados y gestiona colisiones con confirmación explícita.
        Devuelve None si el usuario cancela o si hubo un error ya notificado.
        """
        try:
            return execute_rename_groups(groups, overwrite=False)
        except ExistingDestinationError as exc:
            resp = QtWidgets.QMessageBox.warning(
                self,
                "Archivo Existente",
                f"{exc}\n\n¿Deseas sobrescribirlo?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No,
            )
            if resp != QtWidgets.QMessageBox.StandardButton.Yes:
                return None
            try:
                return execute_rename_groups(groups, overwrite=True)
            except (RenameError, OSError) as overwrite_error:
                QtWidgets.QMessageBox.critical(
                    self, "Error al Renombrar", str(overwrite_error)
                )
                return None
        except DuplicateDestinationError as exc:
            QtWidgets.QMessageBox.critical(
                self,
                "Nombres Duplicados",
                f"{exc}\n\nCorrige los nombres sugeridos antes de continuar.",
            )
            return None
        except (RenameError, OSError) as exc:
            QtWidgets.QMessageBox.critical(self, "Error al Renombrar", str(exc))
            return None

    def _apply_rename_record(
        self, info: MediaFileInfo, record: RenameRecord, row: int, button: Optional[RenameButton]
    ):
        """Actualiza el modelo y la fila tras un renombrado correcto."""
        new_path = record.video_new
        new_name = os.path.basename(new_path)
        self.rename_history.append((record, info))

        info.file_path = new_path
        info.original_filename = new_name
        info.status = "renamed"

        self.table.blockSignals(True)
        orig_item = self.table.item(row, 3)
        if orig_item:
            orig_item.setText(new_name)
            orig_item.setToolTip(f"Ruta completa:\n{new_path}")
        self.table.blockSignals(False)

        self._update_row_status(row, "renamed")
        if button:
            button.setText("Renombrado ✓")
            button.setEnabled(False)

        chk_item = self.table.item(row, 0)
        if chk_item:
            chk_item.setCheckState(QtCore.Qt.CheckState.Unchecked)

    def _execute_rename(self, info: MediaFileInfo, new_filename: str, row: int, button: Optional[RenameButton]):
        group = self._build_rename_group(info, new_filename)
        results = self._run_rename_groups([group])
        if not results or results[0] is None:
            return

        self._apply_rename_record(info, results[0], row, button)
        self._update_summary_labels()
        self.status_bar.showMessage(f"Renombrado con éxito: {new_filename}", 4000)

    # ------------------ Renombrado Múltiple Seleccionado (Con Confirmación) ------------------
    def _on_bulk_rename(self):
        targets: List[tuple] = []

        for r in range(self.table.rowCount()):
            chk_item = self.table.item(r, 0)
            if chk_item and chk_item.checkState() == QtCore.Qt.CheckState.Checked:
                info: MediaFileInfo = chk_item.data(QtCore.Qt.ItemDataRole.UserRole)
                if info and info.status != "renamed":
                    sugg_item = self.table.item(r, 4)
                    new_name = sugg_item.text().strip() if sugg_item else info.suggested_filename
                    if new_name and new_name != info.original_filename:
                        btn = self.table.cellWidget(r, 5)
                        targets.append((info, new_name, r, btn))

        if not targets:
            QtWidgets.QMessageBox.information(
                self, "Aviso", "No hay archivos seleccionados con nombres nuevos pendientes de renombrar."
            )
            return

        # REQUISITO EXPRESO: Preguntar confirmación previa de todos los archivos
        pairs = [(t[0].file_path, t[1]) for t in targets]
        dialog = ConfirmRenameDialog(pairs, parent=self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return

        # Un único lote transaccional: si algo falla, no quedan videos y
        # subtítulos con nombres incoherentes. También permite intercambios.
        groups = [self._build_rename_group(info, new_name) for info, new_name, _, _ in targets]
        results = self._run_rename_groups(groups)
        if results is None:
            return

        success_count = 0
        for (info, new_name, r, btn), record in zip(targets, results):
            if record is None:
                continue
            self._apply_rename_record(info, record, r, btn)
            success_count += 1

        self._update_summary_labels()
        QtWidgets.QMessageBox.information(
            self, "Proceso Finalizado", f"Se han renombrado {success_count} de {len(targets)} archivo(s) correctamente."
        )

    # ------------------ Función Deshacer Renombrado ------------------
    def _undo_last_rename(self):
        if not self.rename_history:
            return

        record, info = self.rename_history[-1]
        current_name = os.path.basename(record.video_new)
        old_name = os.path.basename(record.video_old)

        resp = QtWidgets.QMessageBox.question(
            self,
            "Deshacer Renombrado",
            f"¿Deseas restaurar el nombre original?\n\nActual: {current_name}\nOriginal: {old_name}",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.Yes
        )

        if resp != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        results = self._run_rename_groups([record.reversed_group()])
        if results is None:
            return

        # Solo se elimina del historial cuando la restauración fue correcta.
        self.rename_history.pop()
        restored_path = record.video_old
        info.file_path = restored_path
        info.original_filename = old_name
        info.status = "ready"

        row = self._find_row_for_info(info)
        if row is not None:
            self.table.blockSignals(True)
            orig_item = self.table.item(row, 3)
            if orig_item:
                orig_item.setText(old_name)
                orig_item.setToolTip(f"Ruta completa:\n{restored_path}")
            self.table.blockSignals(False)

            self._update_row_status(row, "ready")
            btn = self.table.cellWidget(row, 5)
            if isinstance(btn, RenameButton):
                btn.setText("✓ Renombrar")
                btn.setEnabled(True)

        self._update_summary_labels()
        self.status_bar.showMessage(f"Restaurado nombre original: {old_name}", 4000)

    # ------------------ Utilidades de Selección y Filtro ------------------
    def _set_all_checkboxes(self, state: bool):
        val = QtCore.Qt.CheckState.Checked if state else QtCore.Qt.CheckState.Unchecked
        for r in range(self.table.rowCount()):
            if not self.table.isRowHidden(r):
                chk_item = self.table.item(r, 0)
                if chk_item:
                    chk_item.setCheckState(val)

    def _apply_filter(self):
        text = self.search_filter.text().lower().strip()
        type_idx = self.combo_type_filter.currentIndex()

        for r in range(self.table.rowCount()):
            orig_item = self.table.item(r, 3)
            sugg_item = self.table.item(r, 4)
            type_item = self.table.item(r, 2)

            orig_text = orig_item.text().lower() if orig_item else ""
            sugg_text = sugg_item.text().lower() if sugg_item else ""
            item_type = type_item.text() if type_item else ""

            match_text = (text in orig_text) or (text in sugg_text)

            match_type = True
            if type_idx == 1 and "Serie" not in item_type:
                match_type = False
            elif type_idx == 2 and "Película" not in item_type:
                match_type = False

            self.table.setRowHidden(r, not (match_text and match_type))

    def _find_row_for_info(self, info: MediaFileInfo) -> Optional[int]:
        for r in range(self.table.rowCount()):
            chk_item = self.table.item(r, 0)
            if chk_item and chk_item.data(QtCore.Qt.ItemDataRole.UserRole) == info:
                return r
        return None

    # ------------------ Menú Contextual (Clic Derecho) ------------------
    def _on_context_menu(self, pos: QtCore.QPoint):
        item = self.table.itemAt(pos)
        if not item:
            return

        row = item.row()
        chk_item = self.table.item(row, 0)
        if not chk_item:
            return

        info: MediaFileInfo = chk_item.data(QtCore.Qt.ItemDataRole.UserRole)
        if not info:
            return

        menu = QtWidgets.QMenu(self)

        action_rename = menu.addAction("✓ Aceptar y Renombrar este archivo")
        if info.status == "renamed":
            action_rename.setEnabled(False)

        menu.addSeparator()

        action_search_tvmaze = menu.addAction("🔍 Buscar otra serie en TVmaze...")
        action_open_folder = menu.addAction("📂 Abrir carpeta en el Explorador")

        selected_action = menu.exec(self.table.viewport().mapToGlobal(pos))

        if selected_action == action_rename:
            btn = self.table.cellWidget(row, 5)
            if isinstance(btn, RenameButton):
                self._on_single_rename_clicked(btn)

        elif selected_action == action_search_tvmaze:
            self._manual_tvmaze_search(info, row)

        elif selected_action == action_open_folder:
            import subprocess
            folder = os.path.dirname(info.file_path)
            if sys.platform == "win32":
                subprocess.Popen(f'explorer /select,"{os.path.abspath(info.file_path)}"')
            else:
                QtWidgets.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(folder))

    def _manual_tvmaze_search(self, info: MediaFileInfo, row: int):
        dialog = ShowSearchDialog(info.parsed_title, self.tvmaze_client, parent=self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted and dialog.selected_show:
            show = dialog.selected_show
            pattern = self.combo_format.currentData() or "{show} - S{season:02d}E{episode:02d} - {title}{ext}"

            self.tvmaze_client.apply_show_to_info(info, show, pattern)

            self.table.blockSignals(True)
            sugg_item = self.table.item(row, 4)
            if sugg_item:
                sugg_item.setText(info.suggested_filename or info.original_filename)
                sugg_item.setToolTip(
                    "Haz doble clic para editar manualmente el nombre propuesto antes de aceptar."
                )
            self.table.blockSignals(False)

            self._update_row_status(row, info.status)
            self._update_summary_labels()
            self.status_bar.showMessage(f"Serie actualizada: {show['name']}", 4000)
