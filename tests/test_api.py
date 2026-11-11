"""
Pruebas para el cliente TVmaze (con mocks y consulta real si hay red).
"""

import unittest
from unittest.mock import patch, MagicMock
from app.media_parser import MediaFileInfo
from app.tvmaze_client import TVmazeClient

class TestTVmazeClient(unittest.TestCase):

    def setUp(self):
        self.client = TVmazeClient()

    @patch.object(TVmazeClient, "_http_get_json")
    def test_mock_search_and_episode(self, mock_get):
        # Configurar retorno para búsqueda
        mock_search_data = [
            {"show": {"id": 123, "name": "Breaking Bad", "premiered": "2008-01-20"}}
        ]
        # Configurar retorno para episodios
        mock_episodes_data = [
            {"season": 1, "number": 1, "name": "Pilot"},
            {"season": 1, "number": 2, "name": "Cat's in the Bag..."}
        ]

        def side_effect(url):
            if "search/shows" in url:
                return mock_search_data
            elif "episodes" in url:
                return mock_episodes_data
            return []

        mock_get.side_effect = side_effect

        info = MediaFileInfo(
            file_path="C:/series/breaking.bad.s01e01.mkv",
            directory="C:/series",
            original_filename="breaking.bad.s01e01.mkv",
            base_name="breaking.bad.s01e01",
            extension=".mkv",
            media_type="series",
            parsed_title="Breaking Bad",
            season=1,
            episode=1
        )

        res = self.client.process_file_info(info)
        self.assertEqual(res.status, "ready")
        self.assertEqual(res.tvmaze_show_name, "Breaking Bad")
        self.assertEqual(res.tvmaze_episode_name, "Pilot")
        self.assertEqual(res.suggested_filename, "Breaking Bad - S01E01 - Pilot.mkv")

    @patch.object(TVmazeClient, "_http_get_json")
    def test_search_ignores_trailing_year(self, mock_get):
        flash = {"id": 13, "name": "The Flash", "premiered": "2014-10-07"}

        def side_effect(url):
            if "The%20Flash%202014" in url:
                return []
            if "search/shows" in url:
                return [{"show": flash, "score": 1.18}]
            if "episodes" in url:
                return [{"season": 1, "number": 1, "name": "Pilot"}]
            return []

        mock_get.side_effect = side_effect

        info = MediaFileInfo(
            file_path="C:/series/The.Flash.2014.S01E01.mkv",
            directory="C:/series",
            original_filename="The.Flash.2014.S01E01.mkv",
            base_name="The.Flash.2014.S01E01",
            extension=".mkv",
            media_type="series",
            parsed_title="The Flash",
            season=1,
            episode=1,
            year=2014,
        )

        res = self.client.process_file_info(info)
        self.assertEqual(res.tvmaze_show_name, "The Flash")
        self.assertEqual(res.suggested_filename, "The Flash - S01E01 - Pilot.mkv")

    @patch.object(TVmazeClient, "_http_get_json")
    def test_rejects_weak_single_word_match(self, mock_get):
        regular_show = {
            "id": 868,
            "name": "Regular Show",
            "premiered": "2010-09-06",
        }
        mock_get.return_value = [{"show": regular_show, "score": 0.68}]

        info = MediaFileInfo(
            file_path="C:/series/Show.S01E01.mkv",
            directory="C:/series",
            original_filename="Show.S01E01.mkv",
            base_name="Show.S01E01",
            extension=".mkv",
            media_type="series",
            parsed_title="Show",
            season=1,
            episode=1,
        )

        res = self.client.process_file_info(info)
        self.assertIsNone(res.tvmaze_show_name)
        self.assertEqual(res.suggested_filename, "Show - S01E01 - Episodio 1.mkv")

    @patch.object(TVmazeClient, "_http_get_json")
    def test_uses_alternative_names(self, mock_get):
        korea = {
            "id": 59307,
            "name": "Money Heist: Korea - Joint Economic Area",
            "premiered": "2022-06-24",
        }
        casa = {"id": 27436, "name": "La Casa de Papel", "premiered": "2017-05-02"}

        def side_effect(url):
            if "search/shows" in url:
                return [
                    {"show": korea, "score": 0.734},
                    {"show": casa, "score": 0.531},
                ]
            if "27436/akas" in url:
                return [{"name": "Money Heist"}, {"name": "Haus des Geldes"}]
            if "59307/akas" in url:
                return [{"name": "Money Heist: Korea"}]
            if "episodes" in url:
                return [{"season": 1, "number": 1, "name": "Efectuar lo acordado"}]
            return []

        mock_get.side_effect = side_effect

        info = MediaFileInfo(
            file_path="C:/series/Money.Heist.S01E01.mkv",
            directory="C:/series",
            original_filename="Money.Heist.S01E01.mkv",
            base_name="Money.Heist.S01E01",
            extension=".mkv",
            media_type="series",
            parsed_title="Money Heist",
            season=1,
            episode=1,
        )

        res = self.client.process_file_info(info)
        self.assertEqual(res.tvmaze_show_name, "La Casa de Papel")
        self.assertEqual(
            res.suggested_filename,
            "La Casa de Papel - S01E01 - Efectuar lo acordado.mkv",
        )

if __name__ == "__main__":
    unittest.main()

