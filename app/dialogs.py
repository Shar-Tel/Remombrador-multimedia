"""
Diálogos auxiliares: selección de series en TVmaze y confirmación de renombrado.
"""

import os
from typing import List, Dict, Any, Optional

from app.qt_compat import QtWidgets, QtCore, QtGui
from app.tvmaze_client import TVmazeClient


class ConfirmRenameDialog(QtWidgets.QDialog):
    """
    Diálogo para confirmar explícitamente el cambio de nombre de uno o varios archivos,
    garantizando que nada se renombre sin consentimiento expreso.
    """

    def __init__(
        self,
        rename_pairs: List[tuple],  # [(file_path, new_filename), ...]
        parent: Optional[QtWidgets.QWidget] = None
    ):
        super().__init__(parent)
        self.rename_pairs = rename_pairs
        self.setWindowTitle("Confirmar Cambio de Nombre")
        self.resize(720, 430)
        self.setModal(True)

        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)

        # Encabezado
        title_label = QtWidgets.QLabel(
            f"<b>¿Deseas renombrar {len(self.rename_pairs)} archivo(s)?</b>"
        )
        title_label.setStyleSheet("font-size: 15px; color: #0f172a;")
        layout.addWidget(title_label)

        sub_label = QtWidgets.QLabel(
            "Revisa los cambios antes de confirmar. Ningún archivo será modificado sin tu aprobación."
        )
        sub_label.setStyleSheet("color: #475569; font-size: 12px;")
        layout.addWidget(sub_label)

        # Tabla de previsualización
        table = QtWidgets.QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Nombre Actual", "→", "Nuevo Nombre"])
        table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        table.setRowCount(len(self.rename_pairs))
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)

        dark_text_brush = QtGui.QBrush(QtGui.QColor("#0f172a"))
        arrow_brush = QtGui.QBrush(QtGui.QColor("#64748b"))

        has_conflicts = False

        for i, (old_path, new_name) in enumerate(self.rename_pairs):
            old_name = os.path.basename(old_path)
            item_old = QtWidgets.QTableWidgetItem(old_name)
            item_old.setForeground(dark_text_brush)

            item_arrow = QtWidgets.QTableWidgetItem("➔")
            item_arrow.setForeground(arrow_brush)
            item_arrow.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

            item_new = QtWidgets.QTableWidgetItem(new_name)
            item_new.setForeground(dark_text_brush)

            # Comprobar si el archivo destino ya existe y es diferente
            dest_path = os.path.join(os.path.dirname(old_path), new_name)
            if os.path.exists(dest_path) and os.path.abspath(old_path) != os.path.abspath(dest_path):
                has_conflicts = True
                item_new.setBackground(QtGui.QColor("#fee2e2"))
                item_new.setForeground(QtGui.QBrush(QtGui.QColor("#b91c1c")))
                item_new.setToolTip("¡ATENCIÓN! Ya existe un archivo con este nombre de destino.")

            table.setItem(i, 0, item_old)
            table.setItem(i, 1, item_arrow)
            table.setItem(i, 2, item_new)

        layout.addWidget(table)

        if has_conflicts:
            warn = QtWidgets.QLabel("⚠️ Advertencia: Algunos archivos de destino ya existen (marcados en rojo).")
            warn.setStyleSheet("color: #b91c1c; font-weight: bold;")
            layout.addWidget(warn)

        # Botones de acción
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QtWidgets.QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_accept = QtWidgets.QPushButton(f"Aceptar y Renombrar ({len(self.rename_pairs)})")
        btn_accept.setStyleSheet(
            "background-color: #10b981; color: #ffffff !important; font-weight: bold; padding: 6px 14px; border: 1px solid #059669;"
        )
        btn_accept.clicked.connect(self.accept)
        btn_layout.addWidget(btn_accept)

        layout.addLayout(btn_layout)


class ShowSearchDialog(QtWidgets.QDialog):
    """
    Diálogo para buscar manualmente una serie en TVmaze cuando la detección
    automática requiera ajuste o elección de otra serie.
    """

    def __init__(
        self,
        initial_title: str,
        client: TVmazeClient,
        parent: Optional[QtWidgets.QWidget] = None
    ):
        super().__init__(parent)
        self.client = client
        self.selected_show: Optional[Dict[str, Any]] = None

        self.setWindowTitle("Buscar Serie en TVmaze")
        self.resize(580, 420)
        self.setModal(True)

        self._build_ui(initial_title)
        if initial_title.strip():
            self._do_search()

    def _build_ui(self, initial_title: str):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)

        # Barra de búsqueda
        search_layout = QtWidgets.QHBoxLayout()
        self.search_input = QtWidgets.QLineEdit(initial_title)
        self.search_input.setPlaceholderText("Nombre de la serie...")
        self.search_input.returnPressed.connect(self._do_search)
        search_layout.addWidget(self.search_input)

        btn_search = QtWidgets.QPushButton("Buscar")
        btn_search.clicked.connect(self._do_search)
        search_layout.addWidget(btn_search)
        layout.addLayout(search_layout)

        # Lista de resultados
        self.results_list = QtWidgets.QListWidget()
        self.results_list.itemDoubleClicked.connect(self._on_item_chosen)
        layout.addWidget(self.results_list)

        # Resumen / detalles
        self.detail_label = QtWidgets.QLabel("Selecciona una serie para ver sus detalles.")
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet("color: #334155; font-size: 12px;")
        self.results_list.currentRowChanged.connect(self._on_selection_changed)
        layout.addWidget(self.detail_label)

        # Botones
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QtWidgets.QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        self.btn_select = QtWidgets.QPushButton("Seleccionar esta Serie")
        self.btn_select.setEnabled(False)
        self.btn_select.setStyleSheet(
            "background-color: #2563eb; color: #ffffff !important; font-weight: bold; padding: 6px 14px; border: 1px solid #1d4ed8;"
        )
        self.btn_select.clicked.connect(self._on_accepted)
        btn_layout.addWidget(self.btn_select)

        layout.addLayout(btn_layout)

    def _do_search(self):
        query = self.search_input.text().strip()
        if not query:
            return

        self.results_list.clear()
        self.btn_select.setEnabled(False)
        self.detail_label.setText("Buscando en TVmaze...")

        shows = self.client.search_shows(query)
        self.current_shows = shows

        if not shows:
            self.detail_label.setText("No se encontraron series para esta búsqueda.")
            return

        dark_text_brush = QtGui.QBrush(QtGui.QColor("#0f172a"))

        for show in shows:
            name = show.get("name", "Desconocido")
            prem = show.get("premiered", "")
            year = f" ({prem[:4]})" if prem else ""
            network = ""
            if show.get("network"):
                network = f" - {show['network'].get('name', '')}"
            elif show.get("webChannel"):
                network = f" - {show['webChannel'].get('name', '')}"

            item = QtWidgets.QListWidgetItem(f"{name}{year}{network}")
            item.setForeground(dark_text_brush)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, show)
            self.results_list.addItem(item)

        if self.results_list.count() > 0:
            self.results_list.setCurrentRow(0)

    def _on_selection_changed(self, row: int):
        if row < 0 or row >= len(getattr(self, "current_shows", [])):
            self.btn_select.setEnabled(False)
            return

        show = self.current_shows[row]
        self.selected_show = show
        self.btn_select.setEnabled(True)

        genres = ", ".join(show.get("genres", [])) or "N/A"
        status = show.get("status", "N/A")
        prem = show.get("premiered", "N/A")

        summary_raw = show.get("summary", "") or ""
        import re
        clean_summary = re.sub(r"<[^>]+>", "", summary_raw).strip()
        if len(clean_summary) > 200:
            clean_summary = clean_summary[:200] + "..."

        self.detail_label.setText(
            f"<b>Estreno:</b> {prem} | <b>Estado:</b> {status} | <b>Géneros:</b> {genres}<br>"
            f"<i>{clean_summary}</i>"
        )

    def _on_item_chosen(self, item: QtWidgets.QListWidgetItem):
        self._on_accepted()

    def _on_accepted(self):
        row = self.results_list.currentRow()
        if row >= 0 and row < len(getattr(self, "current_shows", [])):
            self.selected_show = self.current_shows[row]
            self.accept()
