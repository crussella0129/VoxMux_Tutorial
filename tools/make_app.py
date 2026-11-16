"""make_app.py: build the VoxMux app repository from this tutorial.

The app at github.com/crussella0129/VoxMux is never edited by hand. It is
this tutorial's last answer key with the teaching text taken out, and this
script is the only thing that writes it. The same input always gives the
same output, byte for byte, so anyone can check that the app matches the
tutorial commit named in its SOURCE file.

    python tools/make_app.py OUT_DIR           write the app into OUT_DIR
    python tools/make_app.py --draft OUT_DIR   the same, from uncommitted work
    python tools/make_app.py --check APP_DIR   say whether APP_DIR is up to date

What it does to each .py file in the answer key:

- A docstring that starts with a step tag such as [3.2.1] is cut down to
  its first paragraph, with the tag and any "(level 1: [...])" note
  removed. That leaves one line saying what the function is for.
- A docstring with no tag is kept as it is. Those are the descriptions the
  model reads when it chooses a tool, so they are part of the program.
- Every comment is removed.

Nothing else changes: the script compares the syntax trees before and after
and stops if anything but a docstring differs.

Everything else in the app repository comes from tools/app_extras/ (copied
as it is), the tutorial's LICENSE, and the SOURCE stamp written here.
"""

import argparse
import ast
import io
import pathlib
import re
import subprocess
import sys
import tokenize

ROOT = pathlib.Path(__file__).resolve().parent.parent
ANSWER_KEY = ROOT / "answer_key_level3"
EXTRAS = ROOT / "tools" / "app_extras"
TUTORIAL = "crussella0129/VoxMux_Tutorial"
INPUTS = ["answer_key_level3", "tools", "LICENSE"]

TAG = re.compile(r"\[\d+(?:\.\d+)*\]")
NOTES = [
    re.compile(r"\(level \d+: (?:inside )?\[\d+(?:\.\d+)*\]\)"),
    re.compile(r"\(Level \d+ version\.\)"),
    TAG,
]
DEFINITIONS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def docstring_node(node):
    """Return the statement holding node's docstring, or None."""
    body = node.body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        return body[0]
    return None


def summary(docstring):
    """Return a tagged docstring's one-line summary, or None if it has no tag."""
    text = docstring.strip()
    if not TAG.match(text):
        return None
    line = " ".join(text.split("\n\n")[0].split())
    for pattern in NOTES:
        line = pattern.sub("", line)
    line = " ".join(line.split())
    if not line or "\\" in line or '"""' in line or line.endswith('"'):
        raise ValueError(f"cannot turn this into a one-line docstring: {line!r}")
    return line


def strip(source):
    """Return source with tagged docstrings shortened and comments removed."""
    lines = source.splitlines()
    dropped = set()  # line numbers that go
    replaced = {}  # line number -> the line that takes its place
    cut = {}  # line number -> column where a trailing comment starts

    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, DEFINITIONS):
            continue
        statement = docstring_node(node)
        if statement is None:
            continue
        short = summary(statement.value.value)
        if short is None:
            continue
        indent = " " * statement.col_offset
        replaced[statement.lineno] = f'{indent}"""{short}"""'
        dropped.update(range(statement.lineno + 1, statement.end_lineno + 1))

    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT:
            continue
        row, column = token.start
        if lines[row - 1][:column].strip():
            cut[row] = column
        else:
            dropped.add(row)

    # Rebuild the file. Where removing lines leaves two runs of blank lines
    # touching, keep the longer of the two rather than their sum, and leave
    # no blank line straight after a line that opens a block.
    result = []
    blank = 0  # blank lines waiting to be written
    run = 0  # length of the current unbroken run of blank lines
    for number, line in enumerate(lines, start=1):
        if number in dropped:
            run = 0
            continue
        if number in replaced:
            line = replaced[number]
        elif number in cut:
            line = line[: cut[number]].rstrip()
        if not line.strip():
            run += 1
            blank = max(blank, run)
            continue
        if result and not result[-1].endswith(":"):
            result.extend([""] * blank)
        result.append(line)
        blank = 0
        run = 0
    stripped = "\n".join(result) + "\n"

    if outline(stripped) != outline(source):
        raise ValueError("stripping changed the code, not just the docstrings")
    return stripped


def outline(source):
    """Return source's syntax tree as text, with every docstring left out."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, DEFINITIONS) and docstring_node(node) is not None:
            node.body = node.body[1:] or [ast.Pass()]
    return ast.dump(tree)


def read_text(path):
    """Read a text file with its line endings turned into plain newlines."""
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def build(commit):
    """Return the whole app repository as {path: bytes}, stamped with commit."""
    files = {}
    for path in sorted(ANSWER_KEY.glob("*.py")):
        files[path.name] = strip(read_text(path))
    files["mcp_servers.json"] = read_text(ANSWER_KEY / "mcp_servers.json")
    files["LICENSE"] = read_text(ROOT / "LICENSE")
    for path in sorted(EXTRAS.rglob("*")):
        if path.is_file():
            name = path.relative_to(EXTRAS).as_posix()
            files[name] = read_text(path).replace("@@COMMIT@@", commit)
    files["SOURCE"] = f"{TUTORIAL}@{commit}\n"
    return {name: text.encode("utf-8") for name, text in files.items()}


def git(folder, *arguments):
    """Run git in folder and return what it printed, or None if it failed."""
    try:
        done = subprocess.run(
            ["git", "-C", str(folder), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError:
        return None
    if done.returncode != 0:
        return None
    return done.stdout


def tracked(folder):
    """Return the files git tracks in folder, or None if it is not a repository."""
    if not (folder / ".git").exists():
        return None
    listing = git(folder, "ls-files")
    if listing is None:
        return None
    return set(listing.split("\n")) - {""}


def write(folder, draft):
    """Write the app into folder. Returns the exit code."""
    commit = git(ROOT, "rev-parse", "HEAD")
    changes = git(ROOT, "status", "--porcelain", "--", *INPUTS)
    if commit is None or changes is None:
        print("This needs git, run from a checkout of the tutorial.")
        return 1
    commit = commit.strip()
    if draft:
        commit = "uncommitted"
    elif changes.strip():
        print("These have changes that are not committed yet:")
        print(changes.rstrip())
        print("Commit them first, so the SOURCE stamp names a real commit,")
        print("or pass --draft to write an unstamped copy to look at.")
        return 1

    files = build(commit)
    stale = (tracked(folder) or set()) - set(files)
    for name in sorted(stale):
        (folder / name).unlink(missing_ok=True)
        print(f"removed  {name}")
    for name, data in files.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_bytes() != data:
            path.write_bytes(data)
            print(f"wrote    {name}")
    print(f"{folder} now matches {TUTORIAL}@{commit}")
    if not draft and not git(ROOT, "branch", "-r", "--contains", commit):
        print("That commit is not on GitHub yet. Push the tutorial before")
        print("you push the app, or the app's check will not find it.")
    return 0


def check(folder):
    """Compare folder with what would be written. Returns the exit code."""
    stamp = folder / "SOURCE"
    if not stamp.exists():
        print(f"{folder} has no SOURCE file, so it was not made by this script.")
        return 1
    commit = stamp.read_text(encoding="utf-8").strip().rpartition("@")[2]
    here = (git(ROOT, "rev-parse", "HEAD") or "").strip()
    if commit != here:
        print(f"{folder} was made from tutorial commit {commit},")
        print(f"but this checkout of the tutorial is at {here or 'an unknown commit'}.")
        print("Check out that commit to check the app, or write the app again.")
        return 1

    files = build(commit)
    present = tracked(folder)
    problems = []
    for name, data in files.items():
        path = folder / name
        if not path.exists():
            problems.append(f"missing  {name}")
        elif path.read_bytes().replace(b"\r\n", b"\n") != data:
            problems.append(f"differs  {name}")
    for name in sorted((present or set()) - set(files)):
        problems.append(f"extra    {name}")
    if problems:
        print("\n".join(problems))
        print(f"{folder} does not match {TUTORIAL}@{commit}")
        return 1
    print(f"{folder} matches {TUTORIAL}@{commit} ({len(files)} files)")
    return 0


def main():
    """Read the command line and write or check."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("folder", type=pathlib.Path, help="the app repository")
    parser.add_argument("--check", action="store_true", help="compare, write nothing")
    parser.add_argument("--draft", action="store_true", help="allow uncommitted work")
    options = parser.parse_args()
    folder = options.folder.resolve()
    if options.check:
        return check(folder)
    folder.mkdir(parents=True, exist_ok=True)
    return write(folder, options.draft)


if __name__ == "__main__":
    sys.exit(main())
