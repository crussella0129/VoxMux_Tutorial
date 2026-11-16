"""Level 1: install.py, trimming in backends.py, and the chat window."""

import pathlib
import subprocess
import sys
import sysconfig
import tempfile
import unittest
from unittest import mock

import support

BUILD = support.load_build(support.folder_for(1))


class Install(support.Case):
    """Step 1.2: install.py, without installing anything."""

    build = BUILD

    needs = ["install"]

    def test_commands(self):
        """Every pip command starts with this Python and is a list of strings (1.2.1)."""
        install = self.build.install
        self.assertEqual(install.PIP, [sys.executable, "-m", "pip", "install"])
        self.assertGreaterEqual(len(install.STEPS), 3)
        for step in install.STEPS:
            self.assertIsInstance(step, list)
            for item in step:
                self.assertIsInstance(item, str)
        self.assertEqual(install.STEPS[0][0], "torch")
        self.assertIn("transformers>=5", install.STEPS[1])
        self.assertIn("llama-cpp-python==0.3.36", install.STEPS[2])
        self.assertIn("--only-binary=llama-cpp-python", install.STEPS[2])

    def test_check_is_python(self):
        """CHECK is one valid line of Python (1.2.1)."""
        check = self.build.install.CHECK
        compile(check, "<CHECK>", "exec")
        self.assertIn("'cuda:', torch.cuda.is_available()", check)
        self.assertIn("'llama gpu:', llama_cpp.llama_supports_gpu_offload()", check)

    def test_install_libraries(self):
        """One pip run per entry in STEPS, each with check=True (1.2.2)."""
        install = self.build.install
        with mock.patch.object(subprocess, "run") as run:
            install.install_libraries()
        self.assertEqual(run.call_count, len(install.STEPS))
        for call, step in zip(run.call_args_list, install.STEPS):
            self.assertEqual(call.args[0], install.PIP + step)
            self.assertEqual(call.kwargs, {"check": True})

    def test_copy_cuda_files(self):
        """The three files go from torch/lib to llama_cpp/lib (1.2.3)."""
        install = self.build.install
        with tempfile.TemporaryDirectory() as folder:
            site = pathlib.Path(folder)
            (site / "torch" / "lib").mkdir(parents=True)
            (site / "llama_cpp" / "lib").mkdir(parents=True)
            for name in install.CUDA_FILES:
                (site / "torch" / "lib" / name).write_text(name)
            paths = {"purelib": str(site)}
            with mock.patch.object(sysconfig, "get_paths", return_value=paths):
                install.copy_cuda_files()
                install.copy_cuda_files()  # a second run must be harmless
            for name in install.CUDA_FILES:
                copied = site / "llama_cpp" / "lib" / name
                self.assertEqual(copied.read_text(), name)
        self.assertEqual(len(install.CUDA_FILES), 3)

    def test_check_runs_a_fresh_python(self):
        """check() runs CHECK in a new Python with check=True (1.2.4)."""
        install = self.build.install
        with mock.patch.object(subprocess, "run") as run:
            install.check()
        run.assert_called_once_with([sys.executable, "-c", install.CHECK], check=True)


class Trimming(support.Case):
    """Step 3.2: Backend.chat and fit_to_context, with a stand-in model."""

    build = BUILD

    needs = ["backends"]

    def conversation(self, turns):
        messages = []
        for number in range(turns):
            messages.append({"role": "user", "content": f"question {number} " * 5})
            messages.append({"role": "assistant", "content": f"answer {number} " * 5})
        messages.append({"role": "user", "content": "the newest question"})
        return messages

    def test_chat_streams_pieces(self):
        """chat() is a generator that passes on every piece (3.2.1)."""
        backend = support.make_backend(self.build)
        backend.replies = ["one two three"]
        messages = [{"role": "user", "content": "hi"}]
        pieces = list(backend.chat(messages, "", 0.7, False))
        self.assertEqual(pieces, ["one ", "two ", "three"])

    def test_system_prompt_goes_first(self):
        """The system prompt leads the prompt but is not added to messages (3.2.2)."""
        backend = support.make_backend(self.build)
        messages = [{"role": "user", "content": "hi"}]
        list(backend.chat(messages, "Be brief.", 0.7, False))
        self.assertTrue(backend.prompts[0].startswith("system: Be brief."))
        self.assertEqual(messages, [{"role": "user", "content": "hi"}])

    def test_everything_kept_when_it_fits(self):
        """Nothing is forgotten while the conversation fits (3.2.2)."""
        backend = support.make_backend(self.build)
        messages = self.conversation(4)
        list(backend.chat(messages, "", 0.7, False))
        self.assertEqual(len(messages), 9)

    def test_oldest_forgotten_first(self):
        """Too long: the oldest go, and it still starts with the user (3.2.2)."""
        backend = support.make_backend(self.build, context_size=120)
        messages = self.conversation(8)
        newest = messages[-1]
        list(backend.chat(messages, "", 0.7, False))
        self.assertLess(len(messages), 17)
        self.assertEqual(messages[0]["role"], "user")
        self.assertIs(messages[-1], newest)
        self.assertLessEqual(backend.count_tokens(backend.prompts[-1]), 60)

    def test_newest_message_never_deleted(self):
        """A single message that is too long is still sent (3.2.2)."""
        backend = support.make_backend(self.build, context_size=10)
        messages = [{"role": "user", "content": "word " * 50}]
        list(backend.chat(messages, "", 0.7, False))
        self.assertEqual(len(messages), 1)

    def test_load_backend_refuses_unknown_kind(self):
        """load_backend raises ValueError for a kind it does not know (3.5)."""
        with self.assertRaises(ValueError):
            self.build.backends.load_backend("nonsense", "nowhere")


class Chat(support.AppCase):
    """Step 4: the window, driven the way a person would."""

    build = BUILD

    def test_load_needs_a_model(self):
        """Load before Browse only shows a message (4.8)."""
        self.open()
        self.app.model_path = ""
        self.app.load_button.invoke()
        self.assertEqual(self.status(), "Pick a model with Browse first.")
        self.assertFalse(self.app.busy)

    def test_load(self):
        """Load ends with Ready and the context size in the status line (4.13)."""
        self.load("C:/models/test.gguf")
        self.assertIs(self.app.backend, self.backend)
        self.assertIn(
            "Ready: C:/models/test.gguf (100000 tokens of context", self.status()
        )
        self.assertEqual(self.state(self.app.send_button), "normal")

    def test_load_error(self):
        """A model that fails to load shows Error and frees the buttons (4.11)."""

        def broken(kind, path):
            raise RuntimeError("not a model")

        self.patch("load_backend", broken)
        self.load()
        self.assertEqual(self.status(), "Error: not a model")
        self.assertEqual(self.state(self.app.load_button), "normal")

    def test_send_before_load_does_nothing(self):
        """Send with no model loaded is ignored (4.9)."""
        self.open()
        self.app.entry.insert(0, "hello")
        self.app.send_button.invoke()
        self.assertEqual(self.log(), "")
        self.assertEqual(self.app.messages, [])

    def test_reply(self):
        """A message and its reply reach the log and the conversation (4.9, 4.12)."""
        self.load()
        self.backend.replies = ["Hello there, friend."]
        shown = self.send("hi")
        self.assertEqual(shown, "You: hi\n\nModel: Hello there, friend.\n\n")
        self.assertEqual(self.roles(), ["user", "assistant"])
        self.assertEqual(self.app.messages[1]["content"], "Hello there, friend.")
        self.assertEqual(self.app.entry.get(), "")
        self.assertIn("Ready:", self.status())

    def test_enter_sends(self):
        """Pressing Enter in the entry box sends too (4.4.5)."""
        self.load()
        self.app.entry.insert(0, "hi")
        self.app.send(event=object())
        self.idle()
        self.assertEqual(self.roles(), ["user", "assistant"])

    def test_model_remembers(self):
        """The whole conversation is sent every time (4.12)."""
        self.load()
        self.send("My name is Sam.")
        self.send("What is my name?")
        self.assertIn("user: My name is Sam.", self.backend.prompts[-1])
        self.assertEqual(self.roles(), ["user", "assistant", "user", "assistant"])

    def test_system_prompt_and_thinking_instructions(self):
        """Both are read from the window and sent ahead of the messages (4.9)."""
        self.load()
        self.app.system_box.insert("1.0", "Always answer in French.")
        self.app.thinking.set(True)
        self.app.thinking_instructions = "Think first."
        self.send("hi")
        prompt = self.backend.prompts[-1]
        self.assertTrue(
            prompt.startswith("system: Always answer in French.\n\nThink first.")
        )
        self.assertIn("(thinking on)", prompt)

    def test_thinking_is_shown_but_not_kept(self):
        """The log marks the end of thinking; only the answer is kept (4.12)."""
        self.load()
        self.backend.replies = ["Let me see.</think>It is 391."]
        shown = self.send("17 * 23?")
        self.assertIn("Let me see.\n[end of thinking]It is 391.", shown)
        self.assertEqual(self.app.messages[-1]["content"], "It is 391.")

    def test_buttons_grey_out_while_writing(self):
        """Load and Send stay greyed out until the reply is finished (4.13, 4.15)."""
        self.load()
        self.backend.replies = [support.endless()]
        self.send("hi", wait=False)
        self.pump(lambda: "word" in self.log(), what="the first words")
        self.assertEqual(self.state(self.app.send_button), "disabled")
        self.assertEqual(self.state(self.app.load_button), "disabled")
        self.assertEqual(self.status(), "Writing a reply...")

    def test_reply_error(self):
        """A reply that fails shows Error and frees the buttons (4.12)."""
        self.load()
        self.backend.replies = [RuntimeError("out of memory")]
        self.send("hi")
        self.assertEqual(self.status(), "Error: out of memory")
        self.assertEqual(self.state(self.app.send_button), "normal")

    def test_thinking_instructions_window(self):
        """The instructions window shows the text and Save keeps the edit (4.6, 4.7)."""
        self.open()
        self.app.open_thinking_window()
        (window,) = self.windows()
        (box,) = [w for w in window.winfo_children() if w.winfo_class() == "Text"]
        self.assertEqual(
            box.get("1.0", "end").strip(), self.module.DEFAULT_THINKING_INSTRUCTIONS
        )
        box.delete("1.0", "end")
        box.insert("1.0", "Check your work.\n")
        self.click(window, "Save")
        self.assertEqual(self.app.thinking_instructions, "Check your work.")
        self.assertEqual(self.windows(), [])


if __name__ == "__main__":
    unittest.main()
