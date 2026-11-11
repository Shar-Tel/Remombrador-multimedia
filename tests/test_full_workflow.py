"""
Pruebas de flujo de trabajo completo (end-to-end con archivos reales simulados).
"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from app.media_parser import parse_filename
from app.tvmaze_client import TVmazeClient

class TestFullWorkflow(unittest.TestCase):

    def setUp(self):
        # Crear directorio temporal para pruebas de archivos
        self.test_dir = tempfile.mkdtemp(prefix="media_renamer_test_")
        
        # Archivos de prueba simulados
        self.sample_files = [
            "Breaking.Bad.S01E01.720p.HDTV.mkv",
            "Stranger.Things.S01E02.1080p.WEBRip.mp4",
            "Inception.2010.BluRay.x264.mkv",
            "The.Matrix.1999.1080p.mp4",
            "notas.txt"  # No es archivo multimedia, debe ignorarse
        ]
        
        for name in self.sample_files:
            p = os.path.join(self.test_dir, name)
            with open(p, "w", encoding="utf-8") as f:
                f.write("dummy media content")

    def tearDown(self):
        # Limpiar directorio temporal
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_file_discovery_and_filtering(self):
        client = TVmazeClient()
        found_infos = []
        for fname in os.listdir(self.test_dir):
            full_path = os.path.join(self.test_dir, fname)
            info = parse_filename(full_path)
            if info:
                found_infos.append(info)

        # De los 5 archivos, 4 son multimedia (notas.txt debe ser ignorado)
        self.assertEqual(len(found_infos), 4)

    @patch.object(TVmazeClient, "_http_get_json")
    def test_process_and_rename_file(self, mock_get):
        # Configurar respuestas simuladas de TVmaze
        def mock_tvmaze(url):
            if "search/shows?q=Breaking" in url:
                return [{"show": {"id": 169, "name": "Breaking Bad", "premiered": "2008-01-20"}}]
            elif "169/episodes" in url:
                return [{"season": 1, "number": 1, "name": "Pilot"}]
            return []

        mock_get.side_effect = mock_tvmaze

        client = TVmazeClient()
        file_path = os.path.join(self.test_dir, "Breaking.Bad.S01E01.720p.HDTV.mkv")
        info = parse_filename(file_path)
        self.assertIsNotNone(info)

        processed = client.process_file_info(info)
        self.assertEqual(processed.suggested_filename, "Breaking Bad - S01E01 - Pilot.mkv")

        # Simular acción de renombrado
        dest_path = os.path.join(self.test_dir, processed.suggested_filename)
        self.assertTrue(os.path.exists(file_path))
        self.assertFalse(os.path.exists(dest_path))

        os.rename(file_path, dest_path)

        # Verificar que el archivo antiguo ya no existe y el nuevo sí
        self.assertFalse(os.path.exists(file_path))
        self.assertTrue(os.path.exists(dest_path))

if __name__ == "__main__":
    unittest.main()

