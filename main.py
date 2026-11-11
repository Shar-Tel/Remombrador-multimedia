"""
Punto de entrada principal para el Renombrador Multimedia.
"""

import sys
import os
import logging

from app.qt_compat import QtWidgets, QtGui
from app.main_window import MainWindow

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("MediaRenamer")


def apply_light_palette(app: QtWidgets.QApplication):
    """
    Fuerza una paleta clara consistente para evitar que el modo oscuro del sistema
    operativo genere texto blanco sobre fondos claros.
    """
    palette = QtGui.QPalette()
    dark_text = QtGui.QColor("#0f172a")
    secondary_text = QtGui.QColor("#475569")
    white = QtGui.QColor("#ffffff")
    light_bg = QtGui.QColor("#f8fafc")
    border_color = QtGui.QColor("#cbd5e1")
    accent_blue = QtGui.QColor("#2563eb")
    selection_bg = QtGui.QColor("#e0f2fe")
    selection_text = QtGui.QColor("#0369a1")

    # Colores generales de ventana y base
    palette.setColor(QtGui.QPalette.ColorRole.Window, light_bg)
    palette.setColor(QtGui.QPalette.ColorRole.WindowText, dark_text)
    palette.setColor(QtGui.QPalette.ColorRole.Base, white)
    palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor("#f1f5f9"))
    palette.setColor(QtGui.QPalette.ColorRole.Text, dark_text)
    palette.setColor(QtGui.QPalette.ColorRole.Button, white)
    palette.setColor(QtGui.QPalette.ColorRole.ButtonText, dark_text)
    palette.setColor(QtGui.QPalette.ColorRole.BrightText, QtGui.QColor("#ef4444"))
    palette.setColor(QtGui.QPalette.ColorRole.Link, accent_blue)
    palette.setColor(QtGui.QPalette.ColorRole.Highlight, selection_bg)
    palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, selection_text)
    palette.setColor(QtGui.QPalette.ColorRole.PlaceholderText, QtGui.QColor("#94a3b8"))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtGui.QColor("#0f172a"))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, white)

    app.setPalette(palette)


def main():
    # Qt 6 habilita el escalado HiDPI automáticamente. Los atributos
    # AA_EnableHighDpiScaling y AA_UseHighDpiPixmaps están obsoletos en Qt 6
    # y ya no tienen efecto, así que no se establecen para evitar avisos.
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Renombrador Multimedia")
    app.setOrganizationName("MediaTools")

    # Aplicar paleta anti texto blanco
    apply_light_palette(app)

    # Si se pasa una ruta de directorio por línea de comandos
    initial_dir = None
    if len(sys.argv) > 1:
        candidate_dir = sys.argv[1]
        if os.path.exists(candidate_dir):
            initial_dir = candidate_dir

    window = MainWindow(initial_directory=initial_dir)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
