"""
Pruebas de las operaciones de renombrado transaccionales.
"""

import os
import shutil
import tempfile
import unittest

from app.file_ops import (
    DuplicateDestinationError,
    ExistingDestinationError,
    RenameGroup,
    RenameTransactionError,
    execute_rename_groups,
)


class TestFileOps(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="media_file_ops_test_")

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)

    def _create(self, name, content="x"):
        path = os.path.join(self.directory, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return path

    def _read(self, path):
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()

    def test_basic_rename_returns_record(self):
        src = self._create("old.mkv", "video")
        dst = os.path.join(self.directory, "new.mkv")

        records = execute_rename_groups([RenameGroup(src, dst)])

        self.assertFalse(os.path.exists(src))
        self.assertTrue(os.path.exists(dst))
        self.assertEqual(self._read(dst), "video")
        self.assertIsNotNone(records[0])
        self.assertEqual(records[0].video_old, src)
        self.assertEqual(records[0].video_new, dst)

    def test_existing_destination_requires_explicit_overwrite(self):
        src = self._create("old.mkv", "old")
        dst = self._create("new.mkv", "existing")

        with self.assertRaises(ExistingDestinationError):
            execute_rename_groups([RenameGroup(src, dst)])

        self.assertTrue(os.path.exists(src))
        self.assertEqual(self._read(dst), "existing")

        records = execute_rename_groups([RenameGroup(src, dst)], overwrite=True)
        self.assertFalse(os.path.exists(src))
        self.assertEqual(self._read(dst), "old")
        self.assertIsNotNone(records[0])

    def test_duplicate_destinations_are_rejected(self):
        src_a = self._create("a.mkv")
        src_b = self._create("b.mkv")
        dst = os.path.join(self.directory, "same.mkv")

        with self.assertRaises(DuplicateDestinationError):
            execute_rename_groups([
                RenameGroup(src_a, dst),
                RenameGroup(src_b, dst),
            ])

        self.assertTrue(os.path.exists(src_a))
        self.assertTrue(os.path.exists(src_b))
        self.assertFalse(os.path.exists(dst))

    def test_swap_names_works(self):
        a = self._create("a.mkv", "content-a")
        b = self._create("b.mkv", "content-b")

        execute_rename_groups([
            RenameGroup(a, b),
            RenameGroup(b, a),
        ])

        self.assertEqual(self._read(a), "content-b")
        self.assertEqual(self._read(b), "content-a")

    def test_video_and_subtitles_are_renamed_and_reversible(self):
        video = self._create("Movie.mkv", "video")
        sub_es = self._create("Movie.es.srt", "sub-es")
        sub_en = self._create("Movie.en.forced.srt", "sub-en")

        new_video = os.path.join(self.directory, "Movie (2020).mkv")
        new_sub_es = os.path.join(self.directory, "Movie (2020).es.srt")
        new_sub_en = os.path.join(self.directory, "Movie (2020).en.forced.srt")

        records = execute_rename_groups([
            RenameGroup(video, new_video, [(sub_es, new_sub_es), (sub_en, new_sub_en)])
        ])
        record = records[0]

        self.assertIsNotNone(record)
        self.assertTrue(os.path.exists(new_video))
        self.assertTrue(os.path.exists(new_sub_es))
        self.assertTrue(os.path.exists(new_sub_en))
        self.assertFalse(os.path.exists(sub_es))
        self.assertFalse(os.path.exists(sub_en))

        execute_rename_groups([record.reversed_group()])

        self.assertTrue(os.path.exists(video))
        self.assertTrue(os.path.exists(sub_es))
        self.assertTrue(os.path.exists(sub_en))
        self.assertEqual(self._read(video), "video")
        self.assertEqual(self._read(sub_es), "sub-es")
        self.assertEqual(self._read(sub_en), "sub-en")

    def test_failure_rolls_back_chained_renames(self):
        a = self._create("a.mkv", "content-a")
        b = self._create("b.mkv", "content-b")
        c = self._create("c.mkv", "content-c")
        blocked = os.path.join(self.directory, "d.mkv")
        os.mkdir(blocked)

        with self.assertRaises(RenameTransactionError):
            execute_rename_groups(
                [
                    RenameGroup(a, b),
                    RenameGroup(b, c),
                    RenameGroup(c, blocked),
                ],
                overwrite=True,
            )

        self.assertEqual(self._read(a), "content-a")
        self.assertEqual(self._read(b), "content-b")
        self.assertEqual(self._read(c), "content-c")

    def test_failure_rolls_back_video_and_subtitles(self):
        video = self._create("Movie.mkv", "video")
        sub = self._create("Movie.es.srt", "sub")

        new_video = os.path.join(self.directory, "Movie (2020).mkv")
        blocked_sub = os.path.join(self.directory, "Movie (2020).es.srt")
        # Un directorio en la ruta del subtítulo hace fallar la fase final.
        os.mkdir(blocked_sub)

        with self.assertRaises(RenameTransactionError):
            execute_rename_groups(
                [RenameGroup(video, new_video, [(sub, blocked_sub)])],
                overwrite=True,
            )

        # El video y el subtítulo deben conservar sus nombres originales.
        self.assertTrue(os.path.exists(video))
        self.assertTrue(os.path.exists(sub))
        self.assertFalse(os.path.exists(new_video))
        self.assertEqual(self._read(video), "video")
        self.assertEqual(self._read(sub), "sub")


if __name__ == "__main__":
    unittest.main()
