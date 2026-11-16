"""Level 3: Stop, New chat, saved settings, tool approval, PyTorch safety nets."""

import importlib.util
import json
import threading
import time
import tkinter as tk
import unittest
from unittest import mock

import support
import test_level1
import test_level2

BUILD = support.load_build(support.folder_for(3))
TINY_MODEL = support.ROOT / "tests" / "tiny_model"


class Install(test_level2.Install):
    build = BUILD


class Compaction(test_level2.Compaction):
    build = BUILD


class Tools(test_level2.Tools):
    build = BUILD


class Mcp(test_level2.Mcp):
    build = BUILD


class Chat(test_level1.Chat):
    """Level 1's window tests must still pass in level 3."""

    build = BUILD


class ToolLoop(test_level2.ToolLoop):
    """Level 2's tool loop must still work for built-in tools."""

    build = BUILD


class Stop(support.AppCase):
    """Steps 16.4 to 16.9: cutting a reply short."""

    build = BUILD

    def test_stop_is_only_live_during_a_reply(self):
        """Stop is greyed out when idle and while a model loads (16.4, 16.14)."""
        self.open()
        self.assertEqual(self.state(self.app.stop_button), "disabled")
        self.app.model_path = "C:/models/test.gguf"
        self.app.load_button.invoke()
        self.assertEqual(self.state(self.app.stop_button), "disabled")
        self.idle()
        self.assertEqual(self.state(self.app.stop_button), "disabled")

    def test_stop_cuts_the_reply_short(self):
        """Stop ends the reply, keeps what arrived, and closes the generator (16.7 to 16.9)."""
        self.load()
        self.backend.replies = [support.endless()]
        self.send("Tell me a long story.", wait=False)
        self.pump(lambda: self.log().count("word") >= 3, what="the first words")
        self.assertEqual(self.state(self.app.stop_button), "normal")
        self.app.stop_button.invoke()
        self.assertEqual(self.status(), "Stopping...")
        self.assertEqual(self.state(self.app.stop_button), "disabled")
        self.idle()
        self.assertTrue(self.backend.closed_early)
        self.assertTrue(self.log().endswith("word [stopped]\n\n"))
        self.assertEqual(self.roles(), ["user", "assistant"])
        kept = self.app.messages[-1]["content"]
        self.assertTrue(kept.startswith("word word word"))
        self.assertEqual(self.log().count("word"), kept.count("word"))
        self.assertIn("Ready:", self.status())
        self.assertEqual(self.state(self.app.send_button), "normal")
        self.assertEqual(self.state(self.app.stop_button), "disabled")

    def test_next_reply_is_not_stopped(self):
        """The stop flag is lowered again by the next Send (16.6)."""
        self.load()
        self.backend.replies = [support.endless(), "A whole answer."]
        self.send("first", wait=False)
        self.pump(lambda: "word" in self.log(), what="the first words")
        self.app.stop_button.invoke()
        self.idle()
        shown = self.send("second")
        self.assertEqual(shown, "You: second\n\nModel: A whole answer.\n\n")

    def test_stopped_reply_runs_no_tool(self):
        """A tool call in a reply that was stopped is not run (16.8)."""
        self.load()
        call = support.call_text("calculate", expression="1 + 1")
        self.backend.replies = [support.endless("Let me check. " + call)]
        self.send("hi", wait=False)
        self.pump(lambda: "Let me check." in self.log(), what="the first words")
        self.app.stop_button.invoke()
        self.idle()
        self.assertEqual(self.roles(), ["user", "assistant"])
        self.assertEqual(self.app.messages[-1]["content"], "Let me check.")
        self.assertNotIn("[calculate", self.log())


class NewChat(support.AppCase):
    """Steps 16.3, 16.5 and 16.11: starting again."""

    build = BUILD

    def test_new_chat_clears_everything(self):
        """New chat empties the conversation and the log (16.5)."""
        self.load()
        self.send("My name is Sam.")
        self.app.new_chat_button.invoke()
        self.assertEqual(self.app.messages, [])
        self.assertEqual(self.log(), "")
        self.send("What is my name?")
        self.assertNotIn("Sam", self.backend.prompts[-1])
        self.assertEqual(str(self.app.chat_log.cget("state")), "disabled")

    def test_new_chat_waits_for_the_reply(self):
        """New chat is greyed out while a reply is being written (16.14)."""
        self.load()
        self.backend.replies = [support.endless()]
        self.send("hi", wait=False)
        self.pump(lambda: "word" in self.log(), what="the first words")
        self.assertEqual(self.state(self.app.new_chat_button), "disabled")
        self.app.stop_button.invoke()
        self.idle()
        self.assertEqual(self.state(self.app.new_chat_button), "normal")

    def test_loading_a_model_clears_the_log(self):
        """A newly loaded model starts with an empty log (16.11)."""
        self.load()
        self.send("hi")
        self.load()
        self.assertEqual(self.app.messages, [])
        self.assertEqual(self.log(), "")


class Settings(support.AppCase):
    """Steps 16.15 to 16.17: settings.json."""

    build = BUILD

    def change_everything(self):
        self.app.backend_kind.set("pytorch")
        self.app.model_path = "C:/models/Some Model"
        self.app.temperature.set(1.3)
        self.app.thinking.set(True)
        self.app.thinking_instructions = "Check your work."
        self.app.use_tools.set(False)
        self.app.system_box.insert("1.0", "Always answer in French.")
        self.app.allowed_tools.append("save_note")

    def test_first_run_has_defaults(self):
        """With no settings file the window opens as before (16.15)."""
        self.open()
        self.assertEqual(self.app.backend_kind.get(), "llama_cpp")
        self.assertEqual(self.app.model_path, "")
        self.assertEqual(self.status(), "No model loaded.")
        self.assertEqual(self.app.allowed_tools, [])

    def test_saved_on_close(self):
        """Closing the window writes every setting as JSON (16.16, 16.17)."""
        self.open()
        self.change_everything()
        self.shut()
        saved = json.loads((self.tmp / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(
            saved,
            {
                "backend_kind": "pytorch",
                "model_path": "C:/models/Some Model",
                "temperature": 1.3,
                "thinking": True,
                "thinking_instructions": "Check your work.",
                "use_tools": False,
                "system_prompt": "Always answer in French.",
                "allowed_tools": ["save_note"],
            },
        )

    def test_read_back_on_start(self):
        """The next run starts with the saved settings (16.2, 16.15)."""
        self.open()
        self.change_everything()
        self.shut()
        self.open()
        self.assertEqual(self.app.backend_kind.get(), "pytorch")
        self.assertEqual(self.app.model_path, "C:/models/Some Model")
        self.assertEqual(self.app.temperature.get(), 1.3)
        self.assertIs(self.app.thinking.get(), True)
        self.assertEqual(self.app.thinking_instructions, "Check your work.")
        self.assertIs(self.app.use_tools.get(), False)
        self.assertEqual(
            self.app.system_box.get("1.0", "end").strip(), "Always answer in French."
        )
        self.assertEqual(self.app.allowed_tools, ["save_note"])
        self.assertEqual(self.status(), "Selected: C:/models/Some Model")

    def test_broken_file_is_ignored(self):
        """A settings file that is not JSON, or lacks keys, is not fatal (16.15)."""
        for text in ["{not json", "[1, 2, 3]", '{"backend_kind": "pytorch"}', ""]:
            (self.tmp / "settings.json").write_text(text, encoding="utf-8")
            self.open()
            self.assertEqual(self.app.model_path, "")
            self.assertEqual(
                self.app.temperature.get(), self.module.DEFAULT_TEMPERATURE
            )
            self.shut()

    def test_close_survives_an_unwritable_file(self):
        """The window still closes when the settings cannot be saved (16.17)."""
        root = self.open().root
        with mock.patch.object(self.app, "save_settings", side_effect=OSError("no")):
            self.shut()
        with self.assertRaises(tk.TclError):
            root.winfo_exists()


class Approval(support.AppCase):
    """Steps 16.10 to 16.13: asking before an MCP tool runs."""

    build = BUILD

    def setUp(self):
        super().setUp()
        self.use_demo_server()
        self.load()

    def ask_for_note(self, text="buy oat milk", wait=False):
        self.backend.replies = [support.call_text("save_note", text=text), "Done."]
        return self.send("Save a note.", wait=wait)

    def approval_window(self):
        self.pump(lambda: self.windows(), what="the approval window")
        (window,) = self.windows()
        return window

    def notes(self):
        path = self.tmp / "notes.json"
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def test_built_in_tools_do_not_ask(self):
        """A built-in tool runs without a question (16.10)."""
        self.backend.replies = [
            support.call_text("calculate", expression="2 + 2"),
            "4.",
        ]
        shown = self.send("2 + 2?")
        self.assertIn("-> 4]", shown)
        self.assertEqual(self.windows(), [])

    def test_the_question_names_the_call(self):
        """The window shows the tool's name and arguments, and the tool waits (16.12)."""
        self.ask_for_note()
        window = self.approval_window()
        self.assertEqual(window.title(), "Allow this tool?")
        (label,) = [w for w in window.winfo_children() if w.winfo_class() == "Label"]
        self.assertEqual(
            label.cget("text"),
            "The model wants to run save_note with:\n{'text': 'buy oat milk'}",
        )
        self.assertEqual(self.notes(), [])
        self.assertTrue(self.app.busy)
        self.assertEqual(self.status(), "Waiting for your answer about save_note...")
        self.click(window, "Deny")
        self.idle()

    def test_allow_once(self):
        """Allow once runs this call and asks again next time (16.13)."""
        self.ask_for_note("first")
        self.click(self.approval_window(), "Allow once")
        self.idle()
        self.assertEqual(self.notes(), ["first"])
        self.assertIn("-> Saved. There are now 1 notes.]", self.log())
        self.assertEqual(self.roles(), ["user", "assistant", "tool", "assistant"])
        self.assertEqual(self.app.allowed_tools, [])
        self.assertEqual(self.windows(), [])
        self.ask_for_note("second")
        self.click(self.approval_window(), "Allow once")
        self.idle()
        self.assertEqual(self.notes(), ["first", "second"])

    def test_always_allow(self):
        """Always allow runs the call, is remembered, and is saved (16.13, 16.16)."""
        self.ask_for_note("first")
        self.click(self.approval_window(), "Always allow")
        self.idle()
        self.assertEqual(self.app.allowed_tools, ["save_note"])
        self.ask_for_note("second", wait=True)
        self.assertEqual(self.windows(), [])
        self.assertEqual(self.notes(), ["first", "second"])
        self.shut()
        saved = json.loads((self.tmp / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["allowed_tools"], ["save_note"])

    def test_deny(self):
        """Deny does not run the tool and tells the model so (16.8, 16.13)."""
        self.ask_for_note()
        self.click(self.approval_window(), "Deny")
        self.idle()
        self.assertEqual(self.notes(), [])
        self.assertEqual(self.app.messages[2]["content"], self.module.DENIED)
        self.assertIn(f"-> {self.module.DENIED}]", self.log())
        self.assertIn(self.module.DENIED, self.backend.prompts[-1])
        self.assertEqual(self.roles(), ["user", "assistant", "tool", "assistant"])

    def test_closing_the_window_denies(self):
        """The window's X button counts as Deny (16.12)."""
        self.ask_for_note()
        window = self.approval_window()
        window.tk.call(window.protocol("WM_DELETE_WINDOW"))
        self.idle()
        self.assertEqual(self.notes(), [])
        self.assertEqual(self.app.messages[2]["content"], self.module.DENIED)
        self.assertEqual(self.windows(), [])


@unittest.skipUnless(
    importlib.util.find_spec("torch") and importlib.util.find_spec("transformers"),
    "PyTorch and transformers are not installed here",
)
class PyTorchSafetyNets(support.Case):
    """Step 15.2: TransformersBackend.stream, on a tiny random model.

    The model in tests/tiny_model is 80 KB of random numbers with a
    ten-word vocabulary. It runs on the processor in a moment and writes
    nonsense, which is all these tests need.
    """

    build = BUILD
    needs = ["backends"]

    def setUp(self):
        import torch
        import transformers

        transformers.utils.logging.disable_progress_bar()
        transformers.utils.logging.set_verbosity_error()
        with mock.patch.object(torch.cuda, "is_available", return_value=False):
            self.backend = self.build.backends.TransformersBackend(str(TINY_MODEL))
        self.backend.model.generation_config.eos_token_id = None
        self.prompt = self.backend.build_prompt(
            [{"role": "user", "content": "a b c"}], False
        )
        self.threads = threading.active_count()

    def test_whole_reply_and_failure(self):
        """A failure in generate() is raised here instead of hanging (15.2)."""
        # With no end marker the model writes until it runs past the 1,024
        # positions it has, and then fails inside generate().
        pieces = []
        start = time.time()
        with self.assertRaises(Exception) as caught:
            for piece in self.backend.stream(self.prompt, 0.7):
                pieces.append(piece)
        self.assertGreater(len(pieces), 10)
        self.assertNotIsInstance(caught.exception, (GeneratorExit, StopIteration))
        self.assertLess(time.time() - start, 60)
        self.assertEqual(threading.active_count(), self.threads)

    def test_closing_early_stops_the_model(self):
        """Closing the generator makes generate() stop writing (15.2)."""
        calls = []
        real_generate = self.backend.model.generate

        def counting_generate(**settings):
            result = real_generate(**settings)
            calls.append(result.shape[-1])
            return result

        self.backend.model.generate = counting_generate
        pieces = self.backend.stream(self.prompt, 0)
        for _ in range(3):
            next(pieces)
        pieces.close()
        self.assertEqual(threading.active_count(), self.threads)
        self.assertEqual(len(calls), 1, "generate() should have returned normally")
        self.assertLess(calls[0], 900, "generate() should have stopped early")

    def test_short_reply_still_works(self):
        """A reply that ends by itself is passed on whole (15.2)."""
        self.backend.model.generation_config.max_length = None
        with mock.patch.object(self.build.backends, "MAX_NEW_TOKENS", 20):
            text = "".join(self.backend.stream(self.prompt, 0))
        self.assertTrue(text.strip())
        self.assertEqual(threading.active_count(), self.threads)


if __name__ == "__main__":
    unittest.main()
