"""
Pruebas unitarias para el analizador de archivos multimedia y sanitizador.
"""

import os
import shutil
import tempfile
import unittest

from app.media_parser import (
    MediaFileInfo,
    build_suggested_filename,
    find_associated_subtitles,
    parse_filename,
    sanitize_filename,
)

class TestMediaParser(unittest.TestCase):

    def test_sanitize_filename(self):
        # Probar caracteres ilegales en Windows
        raw = 'Breaking Bad: S01E01? "Pilot" <1080p> *Director/Cut* | Best.mkv'
        clean = sanitize_filename(raw)
        self.assertNotIn(":", clean)
        self.assertNotIn("?", clean)
        self.assertNotIn('"', clean)
        self.assertNotIn("<", clean)
        self.assertNotIn(">", clean)
        self.assertNotIn("*", clean)
        self.assertNotIn("/", clean)
        self.assertNotIn("|", clean)
        self.assertFalse(clean.endswith("."))
        self.assertFalse(clean.endswith(" "))

    def test_parse_series_standard(self):
        path = "C:/Videos/Breaking.Bad.S01E01.720p.HDTV.x264.mkv"
        info = parse_filename(path)
        self.assertIsNotNone(info)
        self.assertEqual(info.media_type, "series")
        self.assertEqual(info.season, 1)
        self.assertEqual(info.episode, 1)
        self.assertEqual(info.parsed_title, "Breaking Bad")
        self.assertEqual(info.extension, ".mkv")

    def test_parse_series_nxnn(self):
        path = "C:/Videos/Stranger.Things.3x04.1080p.WEBRip.mp4"
        info = parse_filename(path)
        self.assertIsNotNone(info)
        self.assertEqual(info.media_type, "series")
        self.assertEqual(info.season, 3)
        self.assertEqual(info.episode, 4)
        self.assertEqual(info.parsed_title, "Stranger Things")
        self.assertEqual(info.extension, ".mp4")

    def test_parse_series_double_episode(self):
        path = "C:/Videos/Friends.S04E01-E02.720p.mkv"
        info = parse_filename(path)
        self.assertIsNotNone(info)
        self.assertEqual(info.media_type, "series")
        self.assertEqual(info.season, 4)
        self.assertEqual(info.episode, 1)
        self.assertEqual(info.end_episode, 2)

    def test_parse_movie_with_year(self):
        path = "C:/Peliculas/Inception.2010.1080p.BluRay.x264.mkv"
        info = parse_filename(path)
        self.assertIsNotNone(info)
        self.assertEqual(info.media_type, "movie")
        self.assertEqual(info.year, 2010)
        self.assertEqual(info.parsed_title, "Inception")

    def test_parse_movie_parenthesis_year(self):
        path = "C:/Peliculas/The Matrix (1999) [1080p].mp4"
        info = parse_filename(path)
        self.assertIsNotNone(info)
        self.assertEqual(info.media_type, "movie")
        self.assertEqual(info.year, 1999)
        self.assertEqual(info.parsed_title, "The Matrix")

    def test_parse_movie_bracket_year(self):
        info = parse_filename("C:/Peliculas/The Matrix [1999] [1080p].mp4")
        self.assertEqual(info.media_type, "movie")
        self.assertEqual(info.year, 1999)
        self.assertEqual(info.parsed_title, "The Matrix")

    def test_build_suggested_filename(self):
        info = MediaFileInfo(
            file_path="C:/vids/bb.mkv",
            directory="C:/vids",
            original_filename="bb.mkv",
            base_name="bb",
            extension=".mkv",
            media_type="series",
            parsed_title="Breaking Bad",
            season=1,
            episode=1
        )
        suggested = build_suggested_filename(info, show_name="Breaking Bad", episode_title="Pilot")
        self.assertEqual(suggested, "Breaking Bad - S01E01 - Pilot.mkv")

    def test_parse_series_with_year_in_title(self):
        # "Show.Year.SxxExx" es una convención muy habitual y TVmaze no encuentra
        # nada si se busca incluyendo el año.
        info = parse_filename("C:/Videos/The.Flash.2014.S01E01.1080p.mkv")
        self.assertIsNotNone(info)
        self.assertEqual(info.media_type, "series")
        self.assertEqual(info.parsed_title, "The Flash")
        self.assertEqual(info.year, 2014)

    def test_clean_title_keeps_common_words(self):
        # "Real" y "Es"/"En" son palabras legítimas de títulos, no etiquetas.
        self.assertEqual(
            parse_filename("C:/Peliculas/Real.Steel.2011.mkv").parsed_title,
            "Real Steel",
        )
        self.assertEqual(
            parse_filename("C:/Peliculas/Es.por.tu.bien.2017.mkv").parsed_title,
            "Es por tu bien",
        )

    def test_parse_movie_uses_last_year(self):
        info = parse_filename("C:/Peliculas/1917.2019.1080p.mkv")
        self.assertEqual(info.parsed_title, "1917")
        self.assertEqual(info.year, 2019)

    def test_sanitize_preserves_hyphenated_words(self):
        self.assertEqual(
            sanitize_filename("Spider-Man - S01E01-E02 - Pilot.mkv"),
            "Spider-Man - S01E01-E02 - Pilot.mkv",
        )

    def test_movie_keeps_language(self):
        info = parse_filename("C:/Peliculas/El.Cuerpo.2012.1080p.BluRay.Latino.mkv")
        self.assertEqual(info.parsed_title, "El Cuerpo")
        self.assertEqual(info.year, 2012)
        self.assertEqual(info.language, "Latino")
        self.assertEqual(
            build_suggested_filename(info), "El Cuerpo (2012) [Latino].mkv"
        )

    def test_movie_dual_latino_prefers_language(self):
        info = parse_filename("C:/Peliculas/Inception (2010) [1080p] [Dual Latino].mkv")
        self.assertEqual(info.parsed_title, "Inception")
        self.assertEqual(info.language, "Latino")
        self.assertEqual(
            build_suggested_filename(info), "Inception (2010) [Latino].mkv"
        )

    def test_movie_vose_language(self):
        info = parse_filename("C:/Peliculas/Joker.2019.VOSE.1080p.mkv")
        self.assertEqual(info.language, "VOSE")
        self.assertEqual(
            build_suggested_filename(info), "Joker (2019) [VOSE].mkv"
        )

    def test_movie_without_year_strips_release_suffix(self):
        info = parse_filename("C:/Peliculas/Movie.Name.1080p.BluRay.x264.mkv")
        self.assertEqual(info.parsed_title, "Movie Name")
        self.assertIsNone(info.year)
        self.assertEqual(build_suggested_filename(info), "Movie Name.mkv")

    def test_movie_without_year_strips_dvd_rip_and_keeps_language(self):
        info = parse_filename(
            "C:/Peliculas/Dos.Colgaos.Muy.Fumaos.Fuga.De.Guantanamo."
            "(Spanish).DVD-Rip.XviD-AC3.by.D2Group.(zonaquatro.com).avi"
        )
        self.assertEqual(
            info.parsed_title, "Dos Colgaos Muy Fumaos Fuga De Guantanamo"
        )
        self.assertIsNone(info.year)
        self.assertEqual(info.language, "Español")
        self.assertEqual(
            build_suggested_filename(info),
            "Dos Colgaos Muy Fumaos Fuga De Guantanamo [Español].avi",
        )

    def test_movie_preserves_ambiguous_title_words(self):
        # "French", "Spanish", "Dual" y "REC" son palabras legítimas del título.
        self.assertEqual(
            parse_filename("C:/Peliculas/The.French.Dispatch.2021.1080p.mkv").parsed_title,
            "The French Dispatch",
        )
        self.assertEqual(
            parse_filename("C:/Peliculas/The.Spanish.Princess.S01E01.1080p.mkv").parsed_title,
            "The Spanish Princess",
        )
        dual = parse_filename("C:/Peliculas/Dual.2022.1080p.mkv")
        self.assertEqual(dual.parsed_title, "Dual")
        self.assertIsNone(dual.language)
        self.assertEqual(
            build_suggested_filename(dual), "Dual (2022).mkv"
        )
        rec = parse_filename("C:/Peliculas/[REC].2007.1080p.mkv")
        self.assertEqual(rec.parsed_title, "REC")
        self.assertEqual(build_suggested_filename(rec), "REC (2007).mkv")

    def test_movie_strips_punctuated_technical_tags(self):
        for filename in (
            "Movie.H.264.2010.mkv",
            "Movie.AAC2.0.2010.mkv",
            "Movie.HDR10+.2010.mkv",
        ):
            info = parse_filename("C:/Peliculas/" + filename)
            self.assertEqual(info.parsed_title, "Movie", filename)
            self.assertEqual(info.year, 2010, filename)
            self.assertEqual(build_suggested_filename(info), "Movie (2010).mkv", filename)

    def test_language_before_year_is_detected(self):
        info = parse_filename("C:/Peliculas/El.Cuerpo.Latino.2012.1080p.mkv")
        self.assertEqual(info.parsed_title, "El Cuerpo")
        self.assertEqual(info.language, "Latino")
        self.assertEqual(
            build_suggested_filename(info), "El Cuerpo (2012) [Latino].mkv"
        )

    def test_movie_without_year_preserves_language_word_in_title(self):
        info = parse_filename("C:/Peliculas/The.French.Dispatch.mkv")
        self.assertEqual(info.parsed_title, "The French Dispatch")
        self.assertIsNone(info.language)
        self.assertEqual(build_suggested_filename(info), "The French Dispatch.mkv")

    def test_subtitle_association_requires_known_suffix(self):
        directory = tempfile.mkdtemp(prefix="media_subtitle_test_")
        try:
            video = os.path.join(directory, "Movie.mkv")
            valid = os.path.join(directory, "Movie.es.srt")
            valid_flags = os.path.join(directory, "Movie.en.forced.srt")
            invalid = os.path.join(directory, "Movie.2.es.srt")
            for path in (video, valid, valid_flags, invalid):
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write("x")

            found = find_associated_subtitles(video)
            found_paths = {path for path, _ in found}

            self.assertIn(valid, found_paths)
            self.assertIn(valid_flags, found_paths)
            self.assertNotIn(invalid, found_paths)
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_double_episode_uses_format_pattern(self):
        info = MediaFileInfo(
            file_path="C:/vids/friends.mkv",
            directory="C:/vids",
            original_filename="friends.mkv",
            base_name="friends",
            extension=".mkv",
            media_type="series",
            parsed_title="Friends",
            season=4,
            episode=1,
            end_episode=2,
        )
        suggested = build_suggested_filename(
            info, show_name="Friends", episode_title="The One With the Jellyfish"
        )
        self.assertEqual(
            suggested, "Friends - S04E01-E02 - The One With the Jellyfish.mkv"
        )

if __name__ == "__main__":
    unittest.main()

