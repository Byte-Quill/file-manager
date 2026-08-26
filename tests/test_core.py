"""Core-layer tests (stdlib unittest — no extra dependencies).

Run with:  python -m unittest discover -s tests
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from filemanager.core.archive import compress_zip, extract_zip
from filemanager.core.cleaner import scan_for_temp_files
from filemanager.core.errors import FileOperationError
from filemanager.core.fileops import (
    bulk_rename,
    create_file,
    create_folder,
    rename_item,
    unique_name,
)
from filemanager.core.info import folder_size
from filemanager.core.models import human_size
from filemanager.core.search import search


class HumanSizeTest(unittest.TestCase):
    def test_bytes(self):
        self.assertEqual(human_size(0), "0 B")
        self.assertEqual(human_size(1023), "1023 B")

    def test_units(self):
        self.assertEqual(human_size(1024), "1.0 KB")
        self.assertEqual(human_size(1536), "1.5 KB")
        self.assertEqual(human_size(1024 ** 3), "1.0 GB")

    def test_petabyte(self):
        self.assertEqual(human_size(1024 ** 5), "1.0 PB")
        self.assertEqual(human_size(2048.0 * 1024 ** 5), "2.0 EB")


class UniqueNameTest(unittest.TestCase):
    def test_no_conflict(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(unique_name(Path(td), "a.txt"), "a.txt")

    def test_conflict_numbers_suffix(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "a.txt").touch()
            self.assertEqual(unique_name(Path(td), "a.txt"), "a (1).txt")
            (Path(td) / "a (1).txt").touch()
            self.assertEqual(unique_name(Path(td), "a.txt"), "a (2).txt")


class NameValidationTest(unittest.TestCase):
    def test_rejects_bad_names(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for bad in ("", "   ", "a/b", ".", ".."):
                with self.assertRaises(FileOperationError):
                    create_folder(root, bad)
                with self.assertRaises(FileOperationError):
                    create_file(root, bad)
            (root / "x").mkdir()
            with self.assertRaises(FileOperationError):
                rename_item(root / "x", "y/z")

    def test_accepts_plain_name(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.assertTrue(create_file(root, "ok.txt").exists())
            self.assertTrue(create_folder(root, "dir").is_dir())


class FolderSizeTest(unittest.TestCase):
    def test_sums_tree(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.txt").write_bytes(b"x" * 10)
            sub = root / "sub"
            sub.mkdir()
            (sub / "b.txt").write_bytes(b"y" * 20)
            self.assertEqual(folder_size(root), 30)

    def test_deep_tree_no_recursion_error(self):
        with tempfile.TemporaryDirectory() as td:
            old_limit = sys.getrecursionlimit()
            sys.setrecursionlimit(200)
            try:
                p = os.path.join(td, "deep")
                os.mkdir(p)
                for _ in range(300):
                    p = os.path.join(p, "d")
                    os.mkdir(p)
                with open(os.path.join(p, "leaf"), "wb") as f:
                    f.write(b"x" * 7)
                self.assertEqual(folder_size(Path(td) / "deep"), 7)
            finally:
                sys.setrecursionlimit(old_limit)


class SearchTest(unittest.TestCase):
    def test_substring_and_glob(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Report.PDF").touch()
            (root / "notes.txt").touch()
            names = {e.name for e in search(root, "report")}
            self.assertEqual(names, {"Report.PDF"})
            names = {e.name for e in search(root, "*.pdf")}
            self.assertEqual(names, {"Report.PDF"})

    def test_max_results(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for i in range(10):
                (root / f"f{i}.tmp").touch()
            self.assertEqual(len(search(root, ".tmp", max_results=3)), 3)


class CleanerTest(unittest.TestCase):
    def _scan(self, root, keys, **kw):
        return {str(m.path.relative_to(root)): m
                for m in scan_for_temp_files(root, keys, **kw)}

    def test_hidden_empty_dirs_not_reported_when_hidden_off(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".hidden_empty").mkdir()
            (root / "visible_empty").mkdir()
            res = self._scan(root, ["empty_dirs"], include_hidden=False)
            self.assertNotIn(".hidden_empty", res)
            self.assertIn("visible_empty", res)

    def test_hidden_empty_dirs_reported_when_hidden_on(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".hidden_empty").mkdir()
            res = self._scan(root, ["empty_dirs"], include_hidden=True)
            self.assertIn(".hidden_empty", res)

    def test_case_insensitive_patterns_and_reason(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "UPPER.TMP").touch()
            (root / "backup.BAK").touch()
            res = self._scan(root, ["temp_files", "backup_files"])
            self.assertEqual(res["UPPER.TMP"].reason, "*.tmp")
            self.assertEqual(res["backup.BAK"].reason, "*.bak")

    def test_matched_dir_pruned(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cache = root / "__pycache__"
            cache.mkdir()
            (cache / "mod.pyc").touch()
            res = self._scan(root, ["python_cache"])
            self.assertEqual(set(res), {"__pycache__"})

    def test_protected_dirs_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            git = root / ".git"
            git.mkdir()
            (git / "HEAD").touch()
            res = self._scan(root, ["temp_files", "empty_dirs"], include_hidden=True)
            self.assertEqual(res, {})


class ArchiveTest(unittest.TestCase):
    def test_roundtrip_files_and_folders(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.txt").write_text("hello")
            sub = root / "sub"
            sub.mkdir()
            (sub / "b.txt").write_text("world")

            archive = compress_zip([root / "a.txt", sub], root / "out.zip")
            self.assertTrue(archive.exists())

            dest = root / "extracted"
            extract_zip(archive, dest)
            self.assertEqual((dest / "a.txt").read_text(), "hello")
            self.assertEqual((dest / "sub" / "b.txt").read_text(), "world")

    def test_bad_zip_raises(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = root / "fake.zip"
            fake.write_text("not a zip")
            with self.assertRaises(FileOperationError):
                extract_zip(fake, root / "out")

    def test_rejects_path_traversal_in_archive_name(self):
        from filemanager.core.archive import compress_zip
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.txt").touch()
            with self.assertRaises(FileOperationError):
                compress_zip([root / "a.txt"], root / "../evil.zip")
            self.assertFalse((root.parent / "evil.zip").exists())

    def test_rejects_existing_archive_overwrite(self):
        from filemanager.core.archive import compress_zip
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.txt").write_text("x")
            (root / "out.zip").write_text("precious")
            with self.assertRaises(FileOperationError):
                compress_zip([root / "a.txt"], root / "out.zip")
            self.assertEqual((root / "out.zip").read_text(), "precious")


class BulkRenameTest(unittest.TestCase):
    def test_simple_and_swap(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            a = root / "a.txt"
            b = root / "b.txt"
            a.write_text("A")
            b.write_text("B")
            # swap names — only works with two-phase rename
            res = bulk_rename([a, b], ["b.txt", "a.txt"])
            self.assertEqual(res[0].read_text(), "A")
            self.assertEqual(res[1].read_text(), "B")
            self.assertEqual((root / "a.txt").read_text(), "B")

    def test_rejects_duplicates_and_bad_names(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            a = root / "a.txt"
            b = root / "b.txt"
            a.touch()
            b.touch()
            with self.assertRaises(FileOperationError):
                bulk_rename([a, b], ["same.txt", "same.txt"])
            with self.assertRaises(FileOperationError):
                bulk_rename([a], ["x/y"])

    def test_rejects_collision_with_outsider(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            a = root / "a.txt"
            outsider = root / "c.txt"
            a.touch()
            outsider.touch()
            with self.assertRaises(FileOperationError):
                bulk_rename([a], ["c.txt"])


class SelfCopyTest(unittest.TestCase):
    def test_copy_folder_into_itself_fails_cleanly(self):
        from filemanager.core.fileops import copy_items
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "src"
            src.mkdir()
            (src / "f.txt").write_text("x")
            with self.assertRaises(FileOperationError) as ctx:
                copy_items([src], src)
            self.assertIn("itself", str(ctx.exception))
            # No runaway nested copies were created.
            self.assertEqual([p.name for p in src.iterdir()], ["f.txt"])

    def test_move_folder_into_descendant_fails_cleanly(self):
        from filemanager.core.fileops import move_items
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "src"
            sub = src / "sub"
            sub.mkdir(parents=True)
            (sub / "keep.txt").write_text("keep")
            with self.assertRaises(FileOperationError):
                move_items([src], sub)
            self.assertTrue((sub / "keep.txt").exists())


class CaseRenameTest(unittest.TestCase):
    def test_case_only_rename_allowed(self):
        from filemanager.core.fileops import rename_item
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            f = root / "A.txt"
            f.write_text("data")
            target = rename_item(f, "a.txt")
            self.assertEqual(target.name, "a.txt")
            self.assertTrue(target.exists())


class PartialFailureTest(unittest.TestCase):
    def test_delete_reports_all_failures(self):
        from filemanager.core.fileops import delete_items
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            gone = root / "gone.txt"
            gone.write_text("x")
            locked = root / "locked" / "sub"  # nonexistent parent fails
            with self.assertRaises(FileOperationError) as ctx:
                delete_items([gone, locked], use_trash=False)
            self.assertFalse(gone.exists())  # deletable item still deleted
            self.assertIn("locked", str(ctx.exception))

    def test_copy_continues_after_failure(self):
        from filemanager.core.fileops import copy_items
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "src"
            src.mkdir()
            (src / "ok.txt").write_text("ok")
            dest = root / "dest"
            dest.mkdir()
            with self.assertRaises(FileOperationError):
                copy_items([root / "missing.txt", src / "ok.txt"], dest)
            self.assertTrue((dest / "ok.txt").exists())


class SettingsTest(unittest.TestCase):
    def test_roundtrip(self):
        from filemanager.core import settings
        with tempfile.TemporaryDirectory() as td:
            fake = Path(td) / "settings.json"
            import unittest.mock as mock
            with mock.patch.object(settings, "settings_path", return_value=fake):
                settings.save({"recent": ["/tmp"], "geometry": "100x100"})
                self.assertEqual(settings.load()["recent"], ["/tmp"])
            with mock.patch.object(settings, "settings_path",
                                   return_value=Path(td) / "missing.json"):
                self.assertEqual(settings.load(), {})


if __name__ == "__main__":
    unittest.main()
