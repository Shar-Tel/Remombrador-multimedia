"""
Capa de compatibilidad para soportar tanto PyQt6 como PySide6 de forma transparente.
"""

import sys

QT_LIB = None

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    Signal = QtCore.Signal
    Slot = QtCore.Slot
    QT_LIB = "PySide6"
except ImportError:
    try:
        from PyQt6 import QtCore, QtGui, QtWidgets
        Signal = QtCore.pyqtSignal
        Slot = QtCore.pyqtSlot
        QT_LIB = "PyQt6"
    except ImportError:
        raise ImportError(
            "No se ha encontrado PySide6 ni PyQt6 instalado.\n"
            "Instala uno de ellos ejecutando: pip install PySide6  (o pip install PyQt6)"
        )

__all__ = ["QtCore", "QtGui", "QtWidgets", "Signal", "Slot", "QT_LIB"]

