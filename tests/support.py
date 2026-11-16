"""Shared helpers for the tests.

None of these tests needs a graphics card or a real model. A build's files
are imported fresh from its folder, and a scripted stand-in plays the part
of the model.
"""

import gc
import importlib
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile
import time
import tkinter as tk
import types
import unittest
import warnings

ROOT = pathlib.Path(__file__).resolve().parent.parent
ANSWER_KEYS = {1: "answer_key", 2: "answer_key_level2", 3: "answer_key_level3"}
NAMES = ["install", "backends", "tools", "mcp_client", "demo_mcp_server", "app"]


def folder_for(level):
    """Return the folder under test: VOXMUX_BUILD if set, else an answer key."""
    override = os.environ.get("VOXMUX_BUILD")
    if override:
        return pathlib.Path(override).resolve()
    return ROOT / ANSWER_KEYS[level]


def load_build(folder):
    """Import every VoxMux file in folder and return them as one object.

    The files import each other by plain name (app.py says "from backends
    import ..."), so the folder goes on sys.path while they load. The names
    are then taken out of sys.modules again, so that another level's files
    with the same names can be loaded in the same test run.
    """
    folder = pathlib.Path(folder)
    for name in NAMES:
        sys.modules.pop(name, None)
    sys.path.insert(0, str(folder))
    try:
        modules = {"folder": folder, "broken": {}}
        for name in NAMES:
            if (folder / f"{name}.py").exists():
                try:
                    modules[name] = importlib.import_module(name)
                except Exception as error:
                    # A file that will not even load is reported by the tests
                    # that need it, instead of stopping every test here.
                    modules["broken"][name] = error
    finally:
        sys.path.remove(str(folder))
        for name in NAMES:
            sys.modules.pop(name, None)
    return types.SimpleNamespace(**modules)


def need(build, name):
    """Skip the calling test class if the build has no such file yet.

    A file that is there but could not be loaded is an error, not a skip.
    """
    if name in build.broken:
        error = build.broken[name]
        raise RuntimeError(
            f"{name}.py could not be loaded: {type(error).__name__}: {error}"
        )
    if not hasattr(build, name):
        raise unittest.SkipTest(f"{name}.py is not in {build.folder} yet")


def make_backend(build, context_size=100_000):
    """Return a stand-in backend built on the build's own Backend class.

    One word counts as one token. Each reply comes from .replies, a list the
    test fills in: a string is handed out a word at a time, anything else is
    looped over as it is, and when the list is empty the reply is "ok".
    """

    class FakeBackend(build.backends.Backend):
        def __init__(self):
            self.context_size = context_size
            self.replies = []
            self.prompts = []
            self.tools_seen = []
            self.closed_early = False

        def build_prompt(self, messages, thinking, tools=None):
            self.tools_seen.append(tools)
            lines = [f"{m['role']}: {m.get('content') or ''}" for m in messages]
            if thinking:
                lines.append("(thinking on)")
            return "\n".join(lines)

        def count_tokens(self, prompt):
            return len(prompt.split())

        def stream(self, prompt, temperature):
            self.prompts.append(prompt)
            reply = self.replies.pop(0) if self.replies else "ok"
            if isinstance(reply, Exception):
                raise reply
            if isinstance(reply, str):
                reply = re.findall(r"\S+\s*", reply)
            try:
                yield from reply
            except GeneratorExit:
                self.closed_early = True
                raise

    return FakeBackend()


def endless(first=""):
    """A reply that never ends by itself: first, then "word " for ever."""
    if first:
        yield first
    while True:
        time.sleep(0.005)
        yield "word "


def call_text(name, **arguments):
    """Write a tool call the way a Qwen model does."""
    lines = ["<tool_call>", f"<function={name}>"]
    for key, value in arguments.items():
        lines += [f"<parameter={key}>", str(value), "</parameter>"]
    lines += ["</function>", "</tool_call>"]
    return "\n".join(lines)


class Case(unittest.TestCase):
    """Base class for every test here. Subclasses set .build.

    The MCP client leaves a server's pipes for Python to close when the
    server object is thrown away. That is harmless, but Python's test runner
    prints a ResourceWarning for each one, so those are switched off.
    """

    build = None
    needs = []

    @classmethod
    def setUpClass(cls):
        warnings.simplefilter("ignore", ResourceWarning)
        for name in cls.needs:
            need(cls.build, name)


class AppCase(Case):
    """Base class: opens the build's real window around a stand-in backend.

    Each test gets its own window, its own temporary folder for settings and
    notes, and no MCP servers unless it calls use_demo_server() before
    load().
    """

    needs = ["backends", "app"]

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="voxmux-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.module = self.build.app
        self.backend = make_backend(self.build)
        self.patch("load_backend", lambda kind, path: self.backend)
        if hasattr(self.module, "MCP_CONFIG"):
            self.patch("MCP_CONFIG", self.tmp / "mcp_servers.json")
        if hasattr(self.module, "SETTINGS_FILE"):
            self.patch("SETTINGS_FILE", self.tmp / "settings.json")
        self.root = None
        self.app = None

    def patch(self, name, value):
        original = getattr(self.module, name)
        setattr(self.module, name, value)
        self.addCleanup(setattr, self.module, name, original)

    def open(self):
        """Open the window. Skips the test where there is no screen."""
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"no screen for tkinter: {error}")
        self.root.withdraw()
        self.app = self.module.ChatApp(self.root)
        self.addCleanup(self.shut)
        return self.app

    def shut(self):
        """Close the window the app's own way, if the test has not already.

        The window's objects are then thrown away here and now. Left to
        Python, that could happen later on some other thread, and tkinter
        objects must be thrown away on the thread that made them.
        """
        if self.root is None:
            return
        for timer in self.root.tk.splitlist(self.root.tk.call("after", "info")):
            self.root.after_cancel(timer)
        try:
            if hasattr(self.app, "close"):
                self.app.close()
            else:
                self.root.destroy()
        except tk.TclError:
            pass
        self.root = None
        self.app = None
        gc.collect()

    def pump(self, done, timeout=20, what="the app to finish"):
        """Keep the window alive until done() is true."""
        end = time.time() + timeout
        while not done():
            self.root.update()
            time.sleep(0.005)
            if time.time() > end:
                self.fail(f"timed out waiting for {what}")
        self.root.update()

    def idle(self):
        self.pump(lambda: not self.app.busy)

    def load(self, path="C:/models/test.gguf"):
        """Pick a model path and click Load."""
        if self.app is None:
            self.open()
        self.app.model_path = path
        self.app.load_button.invoke()
        self.idle()

    def send(self, text, wait=True):
        """Type text and click Send. Returns what was added to the log."""
        before = len(self.log())
        self.app.entry.insert(0, text)
        self.app.send_button.invoke()
        self.root.update()
        if wait:
            self.idle()
        return self.log()[before:]

    def log(self):
        return self.app.chat_log.get("1.0", "end-1c")

    def status(self):
        return self.app.status.cget("text")

    def roles(self):
        return [message["role"] for message in self.app.messages]

    def state(self, button):
        return str(button.cget("state"))

    def use_demo_server(self):
        """Give the app the build's demo MCP server, run from the temp folder."""
        need(self.build, "demo_mcp_server")
        shutil.copy(self.build.folder / "demo_mcp_server.py", self.tmp)
        config = {
            "mcpServers": {
                "demo": {"command": "python", "args": ["demo_mcp_server.py"]}
            }
        }
        (self.tmp / "mcp_servers.json").write_text(json.dumps(config))

    def windows(self):
        """Every extra window that is open right now."""
        return [w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)]

    def click(self, window, label):
        """Click the button with this label somewhere inside window."""
        stack = [window]
        while stack:
            widget = stack.pop()
            if isinstance(widget, tk.Button) and widget.cget("text") == label:
                widget.invoke()
                return
            stack.extend(widget.winfo_children())
        self.fail(f"no button labelled {label!r}")
