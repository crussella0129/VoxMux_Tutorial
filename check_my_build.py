"""check_my_build.py: test your own copy of VoxMux against the recipe.

    python check_my_build.py my_build
    python check_my_build.py my_build_level2
    python check_my_build.py my_build_level3 --level 3

It runs the same tests the answer keys are checked with, on the folder you
name. No model and no graphics card are needed: a scripted stand-in plays
the model, and your real window is opened and driven by the tests (you will
see small windows flash up). A file you have not written yet is skipped, so
you can run this after each step.

Each test's line ends with the recipe steps it checks. When one fails, read
the message at the bottom, then compare that step with your code.

The level is worked out from the files in the folder. Pass --level if it
guesses wrong.
"""

import argparse
import os
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
TESTS = ROOT / "tests"


def guess_level(folder):
    """Work out which level a folder holds from what is in it."""
    app = folder / "app.py"
    if app.exists() and "def new_chat" in app.read_text(encoding="utf-8"):
        return 3
    backends = folder / "backends.py"
    if (folder / "tools.py").exists():
        return 2
    if backends.exists() and "def compact" in backends.read_text(encoding="utf-8"):
        return 2
    return 1


def syntax_errors(folder):
    """Return one message for each .py file in folder that Python cannot read."""
    messages = []
    for path in sorted(folder.glob("*.py")):
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError as error:
            messages.append(
                f"{path.name}, line {error.lineno}: {error.msg}\n"
                f"    {(error.text or '').strip()[:100]}"
            )
    return messages


def main():
    """Run one level's tests on the folder named on the command line."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("folder", type=pathlib.Path, help="the folder with your files")
    parser.add_argument("--level", type=int, choices=[1, 2, 3])
    options = parser.parse_args()

    folder = options.folder.resolve()
    if not folder.is_dir():
        print(f"There is no folder at {folder}")
        return 2
    level = options.level or guess_level(folder)
    print(f"Checking {folder} against level {level}\n")

    problems = syntax_errors(folder)
    if problems:
        print("Python cannot read these files yet. Fix them first:\n")
        print("\n".join(problems))
        print('\nRECIPE.md\'s "When it does not work" table covers the common causes.')
        return 1

    # The tests read this to know which folder to load instead of an answer key.
    os.environ["VOXMUX_BUILD"] = str(folder)
    sys.path.insert(0, str(TESTS))
    suite = unittest.defaultTestLoader.loadTestsFromName(f"test_level{level}")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.wasSuccessful():
        print(f"\nEverything that could be checked in level {level} passed.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
