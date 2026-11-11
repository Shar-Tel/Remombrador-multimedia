"""
Pruebas de inicialización de la interfaz gráfica (PyQt/PySide).
"""

import os
import tempfile
import unittest

from app.qt_compat import QtWidgets, QtCore
from app.main_window import MainWindow

class TestMainWindowUI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Iniciar una instancia de QApplication para pruebas en modo offscreen
        if not QtWidgets.QApplication.instance():
            cls.app = QtWidgets.QApplication(["--platform", "offscreen"])
        else:
            cls.app = QtWidgets.QApplication.instance()

    def test_window_creation(self):
        window = MainWindow()
        self.assertIsNotNone(window)
        self.assertEqual(window.table.columnCount(), 6)
        self.assertFalse(window.btn_stop.isEnabled())
        self.assertTrue(window.btn_scan.isEnabled())
        self.assertTrue(window.chk_confirm_each.isChecked())

    def test_start_scan_is_ignored_while_worker_runs(self):
        directory = tempfile.mkdtemp(prefix="media_scan_guard_test_")
        try:
            window = MainWindow()
            window.dir_input.setText(directory)

            class RunningWorker:
                def isRunning(self):
                    return True

            running_worker = RunningWorker()
            window.worker = running_worker

            # No debe reemplazar el worker ni vaciar la tabla.
            window._start_scan()
            self.assertIs(window.worker, running_worker)
        finally:
            os.rmdir(directory)


if __name__ == "__main__":
    unittest.main()

