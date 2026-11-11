"""
Hilo de trabajo (QThread) para escanear carpetas y consultar la API en segundo plano
sin bloquear la interfaz gráfica.
"""

import os
from typing import List, Optional

from app.qt_compat import QtCore, Signal
from app.media_parser import parse_filename, MediaFileInfo, MEDIA_EXTENSIONS
from app.tvmaze_client import TVmazeClient


class ScanAndQueryWorker(QtCore.QThread):
    """
    Worker que escanea el sistema de archivos y consulta TVmaze
    emitiendo señales de progreso a la interfaz principal.
    """

    # Señales Qt
    scan_started = Signal(int)                     # Total de archivos encontrados
    progress_updated = Signal(int, int, str)       # actual, total, nombre_archivo
    file_processed = Signal(object)                # MediaFileInfo
    scan_finished = Signal(int, int)               # procesados, total
    error_occurred = Signal(str)                   # mensaje de error

    def __init__(
        self,
        directory: str,
        include_subdirs: bool = False,
        format_pattern: str = "{show} - S{season:02d}E{episode:02d} - {title}{ext}",
        parent: Optional[QtCore.QObject] = None
    ):
        super().__init__(parent)
        self.directory = directory
        self.include_subdirs = include_subdirs
        self.format_pattern = format_pattern
        self.tvmaze_client = TVmazeClient()
        self._is_cancelled = False

    def cancel(self):
        """Solicita la cancelación del proceso."""
        self._is_cancelled = True
        self.requestInterruption()

    def run(self):
        try:
            if not os.path.exists(self.directory) or not os.path.isdir(self.directory):
                self.error_occurred.emit(f"El directorio no existe: {self.directory}")
                return

            # Recolectar archivos multimedia
            media_files: List[str] = []

            if self.include_subdirs:
                for root, _, files in os.walk(self.directory):
                    if self._is_cancelled or self.isInterruptionRequested():
                        return
                    for f in files:
                        ext = os.path.splitext(f)[1].lower()
                        if ext in MEDIA_EXTENSIONS:
                            media_files.append(os.path.join(root, f))
            else:
                try:
                    for f in os.listdir(self.directory):
                        full_p = os.path.join(self.directory, f)
                        if os.path.isfile(full_p):
                            ext = os.path.splitext(f)[1].lower()
                            if ext in MEDIA_EXTENSIONS:
                                media_files.append(full_p)
                except Exception as e:
                    self.error_occurred.emit(f"Error al listar archivos: {e}")
                    return

            total_files = len(media_files)
            self.scan_started.emit(total_files)

            if total_files == 0:
                self.scan_finished.emit(0, 0)
                return

            processed_count = 0

            for index, file_path in enumerate(media_files, start=1):
                if self._is_cancelled or self.isInterruptionRequested():
                    break

                filename = os.path.basename(file_path)
                self.progress_updated.emit(index, total_files, filename)

                # Analizar el archivo
                info = parse_filename(file_path)
                if not info:
                    continue

                # Consultar TVmaze
                processed_info = self.tvmaze_client.process_file_info(
                    info,
                    format_pattern=self.format_pattern
                )

                self.file_processed.emit(processed_info)
                processed_count += 1

            self.scan_finished.emit(processed_count, total_files)

        except Exception as e:
            self.error_occurred.emit(f"Error inesperado durante el escaneo: {e}")

