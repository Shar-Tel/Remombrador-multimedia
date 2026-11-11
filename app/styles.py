"""
Estilos y temas para la aplicación Renombrador Multimedia.
Garantiza un contraste óptimo y legible independientemente de si el sistema
operativo está configurado en Modo Oscuro o Modo Claro.
"""

MODERN_STYLE = """
/* Reseteo global de texto para evitar texto blanco de temas oscuros del sistema */
QWidget {
    color: #1e293b;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif;
    font-size: 13px;
}

/* Ventanas principales y diálogos */
QMainWindow, QDialog {
    background-color: #f8fafc;
    color: #1e293b;
}

/* Etiquetas y Textos */
QLabel {
    color: #1e293b;
    background-color: transparent;
}

/* Grupos y paneles */
QGroupBox {
    font-weight: bold;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 14px;
    background-color: #ffffff;
    color: #0f172a;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: #0f172a;
    background-color: #ffffff;
}

/* Casillas de verificación (CheckBox) */
QCheckBox {
    color: #1e293b;
    spacing: 6px;
    background-color: transparent;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #94a3b8;
    border-radius: 4px;
    background-color: #ffffff;
}

QCheckBox::indicator:checked {
    background-color: #2563eb;
    border-color: #2563eb;
    image: none;
}

/* Campos de entrada de texto */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #38bdf8;
    selection-color: #0f172a;
}

QLineEdit:focus, QTextEdit:focus {
    border: 1.5px solid #2563eb;
    background-color: #ffffff;
    color: #0f172a;
}

QLineEdit:disabled {
    background-color: #f1f5f9;
    color: #94a3b8;
}

/* Menús desplegables (ComboBox) */
QComboBox {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 5px 10px;
    min-height: 22px;
}

QComboBox:focus {
    border: 1.5px solid #2563eb;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid #cbd5e1;
    background-color: #f8fafc;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    selection-background-color: #e0f2fe;
    selection-color: #0369a1;
    padding: 4px;
    outline: none;
}

/* Botones estándar */
QPushButton {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #f1f5f9;
    border-color: #94a3b8;
    color: #0f172a;
}

QPushButton:pressed {
    background-color: #e2e8f0;
}

QPushButton:disabled {
    background-color: #f8fafc;
    color: #94a3b8;
    border-color: #e2e8f0;
}

/* Botón primario de escaneo */
QPushButton#btn_scan {
    background-color: #2563eb;
    color: #ffffff !important;
    font-weight: bold;
    border: 1px solid #1d4ed8;
}

QPushButton#btn_scan:hover {
    background-color: #1d4ed8;
}

QPushButton#btn_scan:pressed {
    background-color: #1e40af;
}

/* Botón de detener */
QPushButton#btn_stop {
    background-color: #ef4444;
    color: #ffffff !important;
    border: 1px solid #dc2626;
    font-weight: bold;
}

QPushButton#btn_stop:hover {
    background-color: #dc2626;
}

QPushButton#btn_stop:disabled {
    background-color: #fca5a5;
    color: #ffffff !important;
    border-color: #fca5a5;
}

/* Botón de renombrar individual en la tabla */
QPushButton.btn-rename-row {
    background-color: #10b981;
    color: #ffffff !important;
    font-weight: bold;
    border-radius: 4px;
    padding: 4px 10px;
    border: 1px solid #059669;
}

QPushButton.btn-rename-row:hover {
    background-color: #059669;
}

QPushButton.btn-rename-row:disabled {
    background-color: #cbd5e1;
    color: #64748b !important;
    border-color: #cbd5e1;
}

/* Tablas y Listas */
QTableWidget, QTableView, QListWidget, QListView {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    gridline-color: #f1f5f9;
    selection-background-color: #e0f2fe;
    selection-color: #0369a1;
}

QTableWidget::item, QListWidget::item {
    color: #0f172a;
    padding: 6px 8px;
    border-bottom: 1px solid #f1f5f9;
}

QTableWidget::item:selected, QListWidget::item:selected {
    background-color: #e0f2fe;
    color: #0369a1;
}

/* Cabecera de la tabla */
QHeaderView::section {
    background-color: #f1f5f9;
    color: #334155;
    font-weight: bold;
    border: none;
    border-bottom: 2px solid #cbd5e1;
    border-right: 1px solid #e2e8f0;
    padding: 8px;
}

/* Barra de progreso */
QProgressBar {
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    text-align: center;
    background-color: #f1f5f9;
    color: #0f172a;
    font-weight: bold;
    height: 18px;
}

QProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 5px;
}

/* Barra de estado */
QStatusBar {
    background-color: #ffffff;
    border-top: 1px solid #cbd5e1;
    color: #334155;
}

QStatusBar QLabel {
    color: #334155;
}

/* Menú Contextual (Clic derecho) */
QMenu {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    color: #0f172a;
    padding: 6px 24px 6px 10px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #e0f2fe;
    color: #0369a1;
}

QMenu::separator {
    height: 1px;
    background-color: #e2e8f0;
    margin: 4px 6px;
}

/* Tooltips */
QToolTip {
    background-color: #0f172a;
    color: #ffffff;
    border: 1px solid #334155;
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 12px;
}
"""
