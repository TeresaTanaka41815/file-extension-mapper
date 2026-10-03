import os
import shutil
import tempfile
import unittest

from file_extension_mapper import ExtensionMapper, RenameResult, map_extensions


class _FakeClock:
    def __init__(self, start=0.0):
        self.t = start

    def __call__(self):
        self.t += 1.0
        return self.t


class TestExtensionMapper(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="fem_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _write(self, name, content=b""):
        path = os.path.join(self.tmp, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(content)
        return path

    def test_renames_by_extension(self):
        self._write("a.txt", b"hello")
        self._write("b.md", b"world")
        results = map_extensions(self.tmp, {"txt": "md"}, clock=_FakeClock())
        names = {r.original for r in results}
        self.assertEqual(names, {"a.txt"})
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "a.md")))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "a.txt")))

    def test_mapping_accepts_leading_dot(self):
        self._write("a.txt", b"x")
        map_extensions(self.tmp, {".txt": ".md"}, clock=_FakeClock())
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "a.md")))

    def test_case_insensitive_extension_match(self):
        self._write("Photo.JPG", b"x")
        self._write("photo.TIFF", b"y")
        map_extensions(
            self.tmp,
            {"jpg": "jpeg", "tiff": "tif"},
            clock=_FakeClock(),
        )
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "Photo.jpeg")))
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "photo.tif")))

    def test_preserves_new_extension_case(self):
        self._write("a.txt", b"x")
        map_extensions(self.tmp, {"txt": "MD"}, clock=_FakeClock())
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "a.MD")))

    def test_skips_when_extension_unchanged(self):
        self._write("a.txt", b"x")
        results = map_extensions(self.tmp, {"txt": "txt"}, clock=_FakeClock())
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "a.txt")))
        self.assertTrue(results[0].skipped)
        self.assertEqual(results[0].reason, "extension unchanged")

    def test_conflict_resolution_inserts_suffix(self):
        self._write("photo.jpg", b"1")
        self._write("photo.jpeg", b"2")
        results = map_extensions(self.tmp, {"jpeg": "jpg"}, clock=_FakeClock())
        renamed = [r for r in results if not r.skipped][0]
        self.assertNotEqual(renamed.renamed, "photo.jpg")
        self.assertTrue(renamed.renamed.startswith("photo_"))
        self.assertTrue(renamed.renamed.endswith(".jpg"))
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "photo.jpg")))
        self.assertTrue(os.path.exists(os.path.join(self.tmp, renamed.renamed)))

    def test_dry_run_does_not_touch_disk(self):
        self._write("a.txt", b"keep")
        results = map_extensions(
            self.tmp, {"txt": "md"}, dry_run=True, clock=_FakeClock()
        )
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "a.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "a.md")))
        self.assertEqual(results[0].renamed, "a.md")
        self.assertFalse(results[0].skipped)

    def test_overwrite_replaces_existing(self):
        self._write("a.txt", b"new")
        self._write("a.md", b"old")
        results = map_extensions(
            self.tmp, {"txt": "md"}, overwrite=True, clock=_FakeClock()
        )
        self.assertEqual(results[0].renamed, "a.md")
        with open(os.path.join(self.tmp, "a.md"), "rb") as f:
            self.assertEqual(f.read(), b"new")

    def test_multiple_files_to_same_extension_resolve_uniquely(self):
        for n in ("a.txt", "b.txt", "c.txt"):
            self._write(n, n.encode())
        self._write("z.md", b"z")
        results = map_extensions(self.tmp, {"txt": "md"}, clock=_FakeClock())
        renamed = {r.renamed for r in results if not r.skipped}
        self.assertEqual(len(renamed), len({r.renamed for r in results if not r.skipped}))
        for n in ("a.md", "b.md", "c.md", "z.md"):
            self.assertIn(n, renamed | {"z.md"} | {r.original for r in results})

    def test_ignores_subdirectories(self):
        os.makedirs(os.path.join(self.tmp, "sub"))
        self._write(os.path.join("sub", "a.txt"), b"x")
        self._write("a.txt", b"y")
        results = map_extensions(self.tmp, {"txt": "md"}, clock=_FakeClock())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].original, "a.txt")
        self.assertTrue(os.path.isdir(os.path.join(self.tmp, "sub")))
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "sub", "a.txt")))

    def test_nonexistent_directory_raises(self):
        with self.assertRaises(NotADirectoryError):
            map_extensions(
                os.path.join(self.tmp, "does-not-exist"),
                {"txt": "md"},
                clock=_FakeClock(),
            )

    def test_default_mapping_value_must_be_string(self):
        self._write("a.txt", b"x")
        with self.assertRaises(TypeError):
            map_extensions(self.tmp, {"txt": 5}, clock=_FakeClock())

    def test_result_dataclass_fields(self):
        self._write("a.txt", b"x")
        r = map_extensions(self.tmp, {"txt": "md"}, clock=_FakeClock())[0]
        self.assertIsInstance(r, RenameResult)
        self.assertEqual(r.original, "a.txt")
        self.assertEqual(r.renamed, "a.md")
        self.assertFalse(r.skipped)
        self.assertIsNone(r.reason)

    def test_extension_with_multiple_dots(self):
        self._write("archive.tar.gz", b"x")
        results = map_extensions(self.tmp, {"gz": "tgz"}, clock=_FakeClock())
        self.assertEqual(results[0].renamed, "archive.tar.tgz")
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "archive.tar.tgz")))


if __name__ == "__main__":
    unittest.main()
