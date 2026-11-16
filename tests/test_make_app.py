"""tools/make_app.py: the script that builds the app repository."""

import ast
import importlib.util
import io
import pathlib
import shutil
import subprocess
import sys
import tempfile
import tokenize
import unittest

import support

spec = importlib.util.spec_from_file_location(
    "make_app", support.ROOT / "tools" / "make_app.py"
)
make_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(make_app)

COMMIT = "0123456789abcdef0123456789abcdef01234567"


class Strip(unittest.TestCase):
    """What happens to one Python file."""

    def test_tagged_docstring_becomes_its_first_line(self):
        source = (
            "def send(self):\n"
            '    """[16.6] (level 2: [12.4]) Send button or Enter: add the\n'
            "    message, ask.\n"
            "\n"
            "    How it works: a long explanation.\n"
            '    """\n'
            "    return 1\n"
        )
        self.assertEqual(
            make_app.strip(source),
            "def send(self):\n"
            '    """Send button or Enter: add the message, ask."""\n'
            "    return 1\n",
        )

    def test_notes_are_removed_from_the_summary(self):
        summary = make_app.summary
        self.assertEqual(
            summary("[4.1] app.py: the window.\n(Level 3 version.)"),
            "app.py: the window.",
        )
        self.assertEqual(
            summary("[12.7] (level 1: inside [4.12]) Stream it."), "Stream it."
        )
        self.assertIsNone(summary("Pick a random whole number."))

    def test_untagged_docstring_is_kept(self):
        source = 'def calculate(expression):\n    """Work it out. Use it for sums."""\n    return 1\n'
        self.assertEqual(make_app.strip(source), source)

    def test_comments_go_and_strings_stay(self):
        source = (
            "# a comment at the top\n"
            "import os\n"
            "\n"
            "# [1.1] a tagged comment\n"
            'NAME = "a # inside a string"  # a trailing comment\n'
            "\n"
            "\n"
            "def f():\n"
            "    # the first thing in a block\n"
            "\n"
            "    x = 1\n"
            "\n"
            "    # a comment between two blank lines\n"
            "\n"
            "    return x\n"
        )
        self.assertEqual(
            make_app.strip(source),
            "import os\n"
            "\n"
            'NAME = "a # inside a string"\n'
            "\n"
            "\n"
            "def f():\n"
            "    x = 1\n"
            "\n"
            "    return x\n",
        )

    def test_a_summary_that_cannot_be_one_line_is_refused(self):
        """A summary ending in a quote would run into the closing quotes."""
        with self.assertRaises(ValueError):
            make_app.strip('def f():\n    """[1.1] Say "hi" """\n')


class Build(unittest.TestCase):
    """The whole app repository, built from the files in this checkout."""

    @classmethod
    def setUpClass(cls):
        cls.files = make_app.build(COMMIT)

    def test_same_input_gives_the_same_output(self):
        self.assertEqual(make_app.build(COMMIT), self.files)

    def test_the_files(self):
        self.assertEqual(
            sorted(self.files),
            [
                ".gitattributes",
                ".github/workflows/check.yml",
                ".gitignore",
                "LICENSE",
                "README.md",
                "SOURCE",
                "app.py",
                "backends.py",
                "demo_mcp_server.py",
                "install.py",
                "mcp_client.py",
                "mcp_servers.json",
                "tools.py",
            ],
        )

    def test_the_stamp(self):
        self.assertEqual(
            self.files["SOURCE"].decode(), f"crussella0129/VoxMux_Tutorial@{COMMIT}\n"
        )
        self.assertIn(
            f"/blob/{COMMIT}/tools/make_app.py", self.files["README.md"].decode()
        )
        self.assertNotIn(b"@@COMMIT@@", b"".join(self.files.values()))

    def test_plain_newlines_everywhere(self):
        for name, data in self.files.items():
            self.assertNotIn(b"\r", data, name)
            self.assertTrue(data.endswith(b"\n"), name)

    def test_the_code_is_the_answer_key(self):
        """Apart from docstrings and comments, every .py file is unchanged."""
        for path in sorted(make_app.ANSWER_KEY.glob("*.py")):
            original = path.read_text(encoding="utf-8")
            made = self.files[path.name].decode()
            self.assertEqual(
                make_app.outline(made), make_app.outline(original), path.name
            )

    def test_no_teaching_text_is_left(self):
        """No comments, no step tags, and one-line docstrings only."""
        for name, data in self.files.items():
            if not name.endswith(".py"):
                continue
            text = data.decode()
            self.assertNotIn("How it works", text, name)
            for token in tokenize.generate_tokens(io.StringIO(text).readline):
                self.assertNotEqual(token.type, tokenize.COMMENT, f"{name}: {token}")
            for node in ast.walk(ast.parse(text)):
                if isinstance(node, make_app.DEFINITIONS):
                    docstring = ast.get_docstring(node, clean=False) or ""
                    self.assertNotIn("\n", docstring, name)
                    self.assertIsNone(make_app.TAG.search(docstring), name)

    def test_tool_descriptions_survive(self):
        """The model still reads the same description of each built-in tool."""
        build = support.load_build(make_app.ANSWER_KEY)
        with tempfile.TemporaryDirectory() as folder:
            for name, data in self.files.items():
                path = pathlib.Path(folder) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            made = support.load_build(folder)
            self.assertEqual(
                made.tools.Toolbox([]).schemas, build.tools.Toolbox([]).schemas
            )
            self.assertEqual(made.demo_mcp_server.TOOLS, build.demo_mcp_server.TOOLS)

    @unittest.skipUnless(shutil.which("ruff"), "ruff is not installed here")
    def test_output_is_already_formatted(self):
        """ruff would not change a line of the generated Python."""
        with tempfile.TemporaryDirectory() as folder:
            for name, data in self.files.items():
                if name.endswith(".py"):
                    (pathlib.Path(folder) / name).write_bytes(data)
            for command in (["format", "--check"], ["check"]):
                done = subprocess.run(
                    ["ruff", *command, "--isolated", folder],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


class CommandLine(unittest.TestCase):
    """Writing and checking, through the real command line."""

    def run_script(self, *arguments):
        return subprocess.run(
            [sys.executable, str(support.ROOT / "tools" / "make_app.py"), *arguments],
            capture_output=True,
            text=True,
        )

    def test_draft_then_check(self):
        with tempfile.TemporaryDirectory() as folder:
            done = self.run_script("--draft", folder)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            stamp = (pathlib.Path(folder) / "SOURCE").read_text()
            self.assertEqual(stamp, "crussella0129/VoxMux_Tutorial@uncommitted\n")
            # A draft can never pass the check: it names no commit.
            done = self.run_script("--check", folder)
            self.assertEqual(done.returncode, 1)
            self.assertIn("was made from tutorial commit uncommitted", done.stdout)

    def test_check_refuses_a_folder_with_no_stamp(self):
        with tempfile.TemporaryDirectory() as folder:
            done = self.run_script("--check", folder)
            self.assertEqual(done.returncode, 1)
            self.assertIn("no SOURCE file", done.stdout)


if __name__ == "__main__":
    unittest.main()
