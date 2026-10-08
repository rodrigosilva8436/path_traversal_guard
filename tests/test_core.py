import os
import tempfile
import unittest
from pathlib import Path

from path_traversal_guard import PathGuard, PathTraversalError


class TestPathGuardConstruction(unittest.TestCase):
    def test_rejects_nonexistent_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = os.path.join(tmp, "does-not-exist")
            with self.assertRaises(FileNotFoundError):
                PathGuard(missing)

    def test_rejects_file_as_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, "afile")
            Path(f).touch()
            with self.assertRaises(NotADirectoryError):
                PathGuard(f)

    def test_base_directory_property_is_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Create a symlink to the real dir so we can confirm resolve().
            real = Path(tmp) / "real"
            real.mkdir()
            link = Path(tmp) / "link"
            link.symlink_to(real, target_is_directory=True)
            guard = PathGuard(link)
            self.assertEqual(guard.base_directory, real.resolve())


class TestPathGuardContainment(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name) / "base"
        self.base.mkdir()
        self.guard = PathGuard(self.base)

    def tearDown(self):
        self._tmp.cleanup()

    def test_relative_path_inside_base_is_safe(self):
        resolved = self.guard.resolve_safe("subdir/file.txt")
        self.assertEqual(resolved, (self.base / "subdir" / "file.txt").resolve())

    def test_absolute_path_inside_base_is_safe(self):
        target = self.base / "inside.txt"
        resolved = self.guard.resolve_safe(str(target))
        self.assertEqual(resolved, target.resolve())

    def test_base_directory_itself_is_safe(self):
        resolved = self.guard.resolve_safe(".")
        self.assertEqual(resolved, self.base.resolve())

    def test_dotdot_escape_is_rejected(self):
        with self.assertRaises(PathTraversalError):
            self.guard.resolve_safe("../../../etc/passwd")

    def test_absolute_path_outside_base_is_rejected(self):
        with self.assertRaises(PathTraversalError):
            self.guard.resolve_safe("/etc/passwd")

    def test_is_safe_true_inside(self):
        self.assertTrue(self.guard.is_safe("ok.txt"))

    def test_is_safe_false_outside(self):
        self.assertFalse(self.guard.is_safe("../../etc/passwd"))

    def test_nonexistent_path_inside_is_allowed(self):
        # strict=False lets us validate files that will be written.
        resolved = self.guard.resolve_safe("not-yet-created.bin")
        self.assertEqual(resolved, (self.base / "not-yet-created.bin").resolve())
        self.assertFalse(resolved.exists())


class TestPathGuardSymlinks(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.base = self.root / "base"
        self.base.mkdir()
        self.outside = self.root / "outside"
        self.outside.mkdir()
        self.guard = PathGuard(self.base)

    def tearDown(self):
        self._tmp.cleanup()

    def test_symlink_pointing_inside_is_allowed(self):
        target = self.base / "real_target"
        target.mkdir()
        link = self.base / "good_link"
        link.symlink_to(target, target_is_directory=True)
        resolved = self.guard.resolve_safe("good_link")
        self.assertEqual(resolved, target.resolve())

    def test_symlink_pointing_outside_is_rejected(self):
        link = self.base / "bad_link"
        link.symlink_to(self.outside, target_is_directory=True)
        with self.assertRaises(PathTraversalError):
            self.guard.resolve_safe("bad_link")


class TestPathGuardEdgeCases(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name) / "base"
        self.base.mkdir()
        self.guard = PathGuard(self.base)

    def tearDown(self):
        self._tmp.cleanup()

    def test_pathlike_input_accepted(self):
        resolved = self.guard.resolve_safe(Path("subdir") / "file")
        self.assertEqual(resolved, (self.base / "subdir" / "file").resolve())

    def test_base_subdir_name_prefix_not_confused_with_base(self):
        # A directory named "base_extra" must not be treated as inside "base".
        sibling = self.base.parent / "base_extra"
        sibling.mkdir()
        try:
            with self.assertRaises(PathTraversalError):
                self.guard.resolve_safe(str(sibling / "file.txt"))
        finally:
            sibling.rmdir()

    def test_trailing_components_after_escape_still_rejected(self):
        with self.assertRaises(PathTraversalError):
            self.guard.resolve_safe("../outside/deeply/nested")


if __name__ == "__main__":
    unittest.main()
