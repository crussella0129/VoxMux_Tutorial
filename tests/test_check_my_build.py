"""check_my_build.py: the self-check a learner runs on their own folder."""

import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import support


class CheckMyBuild(unittest.TestCase):
    def setUp(self):
        self.folder = pathlib.Path(tempfile.mkdtemp(prefix="voxmux-test-"))
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)

    def run_script(self, *arguments):
        return subprocess.run(
            [sys.executable, str(support.ROOT / "check_my_build.py"), *arguments],
            capture_output=True,
            text=True,
        )

    def copy(self, name, level=1):
        shutil.copy(support.ROOT / support.ANSWER_KEYS[level] / name, self.folder)

    def test_a_folder_with_only_step_1_done(self):
        """Files that are not written yet are skipped, not failed."""
        self.copy("install.py")
        done = self.run_script(str(self.folder))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("against level 1", done.stdout)
        self.assertIn("backends.py is not in", done.stderr)
        self.assertIn(
            "Everything that could be checked in level 1 passed.", done.stdout
        )

    def test_a_syntax_error_is_explained(self):
        """A file Python cannot read is named with its line, with no traceback."""
        (self.folder / "install.py").write_text('import sys\nNAME = "torch\n')
        done = self.run_script(str(self.folder))
        self.assertEqual(done.returncode, 1)
        self.assertIn("install.py, line 2: unterminated string literal", done.stdout)
        self.assertNotIn("Traceback", done.stdout + done.stderr)

    def test_a_file_that_fails_to_load_is_an_error(self):
        """A file that is valid Python but crashes on import fails its tests."""
        (self.folder / "install.py").write_text("import no_such_module_anywhere\n")
        done = self.run_script(str(self.folder))
        self.assertEqual(done.returncode, 1)
        self.assertIn(
            "install.py could not be loaded: ModuleNotFoundError", done.stderr
        )

    def test_a_mistake_is_caught(self):
        """A wrong line in the folder fails the test for its step."""
        self.copy("install.py")
        path = self.folder / "install.py"
        text = path.read_text(encoding="utf-8")
        right = "subprocess.run(PIP + step, check=True)"
        self.assertEqual(text.count(right), 1)
        path.write_text(text.replace(right, "subprocess.run(PIP + step)"), "utf-8")
        done = self.run_script(str(self.folder))
        self.assertEqual(done.returncode, 1)
        self.assertIn("(1.2.2)", done.stderr)

    def test_the_level_is_worked_out_from_the_files(self):
        for level in (2, 3, 4):
            folder = support.ROOT / support.ANSWER_KEYS[level]
            done = self.run_script(str(folder), "--help")
            self.assertEqual(done.returncode, 0)
        sys.path.insert(0, str(support.ROOT))
        try:
            import check_my_build
        finally:
            sys.path.remove(str(support.ROOT))
        for level, name in support.ANSWER_KEYS.items():
            self.assertEqual(check_my_build.guess_level(support.ROOT / name), level)
        self.assertEqual(check_my_build.guess_level(self.folder), 1)


if __name__ == "__main__":
    unittest.main()
