"""Level 4: other model families, stubborn MCP servers, and saved chats."""

import json
import os
import subprocess
import sys
import threading
import time
import types
import unittest
from unittest import mock

import support
import test_level3

BUILD = support.load_build(support.folder_for(4))

# What a Llama 3.2 model really wrote when it was offered tools.
LLAMA_ONE_CALL = '{"name": "calculate", "parameters": {"expression": "6 * 7"}}'
LLAMA_THREE_CALLS = (
    '{"name": "calculate", "parameters": {"expression": "12 * 12"}}; '
    '{"name": "calculate", "parameters": {"expression": "99 + 1"}}; '
    '{"name": "save_note", "parameters": {"text": "hello"}}'
)
LLAMA_ODD_CALL = (
    '{"type": "function", "function": "calculate", '
    '"parameters": {"expression": "17 * 23"}}'
)


class Install(test_level3.Install):
    build = BUILD


class Compaction(test_level3.Compaction):
    build = BUILD


class Tools(test_level3.Tools):
    build = BUILD


class Mcp(test_level3.Mcp):
    """Level 2's client tests, and step 21: a server that will not stop."""

    build = BUILD

    def alive(self, pid):
        if sys.platform == "win32":
            listing = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True,
                text=True,
            ).stdout
            return str(pid) in listing
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def kill(self, pid):
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        elif self.alive(pid):
            os.kill(pid, 9)

    def test_a_launcher_and_its_server_are_both_stopped(self):
        """close() ends a stubborn server that a launcher started (21.3, 21.4)."""
        # A server that goes on running after its input has closed...
        (self.tmp / "stubborn.py").write_text(
            "import os\n"
            "import sys\n"
            "import time\n"
            "sys.path.insert(0, '.')\n"
            "import demo_mcp_server\n"
            "with open('server.pid', 'w') as file:\n"
            "    file.write(str(os.getpid()))\n"
            "demo_mcp_server.main()\n"
            "time.sleep(600)\n"
        )
        # ...started by a launcher, the way npx and uvx start theirs.
        (self.tmp / "launcher.py").write_text(
            "import subprocess\n"
            "import sys\n"
            "subprocess.run([sys.executable, 'stubborn.py'])\n"
        )
        support.shutil.copy(self.build.folder / "demo_mcp_server.py", self.tmp)
        servers, problems = self.start(
            {"wrapped": {"command": "python", "args": ["launcher.py"]}}
        )
        self.assertEqual(problems, [])
        server = servers[0]
        self.assertEqual(len(server.schemas), 3)
        server_pid = int((self.tmp / "server.pid").read_text())
        self.addCleanup(self.kill, server_pid)
        self.assertNotEqual(server_pid, server.process.pid)
        self.assertTrue(self.alive(server_pid))

        start = time.time()
        server.close()
        self.assertLess(time.time() - start, 15)
        self.assertIsNotNone(server.process.poll())
        for _ in range(50):
            if not self.alive(server_pid):
                break
            time.sleep(0.1)
        self.assertFalse(self.alive(server_pid), "the real server was left running")
        self.assertFalse(server.reader.is_alive())
        self.assertTrue(server.process.stdout.closed)
        self.assertTrue(server.log.closed)


class Chat(test_level3.Chat):
    """Level 1's window tests must still pass in level 4."""

    build = BUILD


class ToolLoop(test_level3.ToolLoop):
    """Level 2's tool loop must still work, with one change."""

    build = BUILD

    def test_tools_off(self):
        """With Use tools off, a call the model writes is only text (22.10, 22.11)."""
        self.load()
        self.app.use_tools.set(False)
        written = "Sure.\n" + support.call_text("calculate", expression="1 + 1")
        self.backend.replies = [written]
        shown = self.send("hi")
        self.assertIsNone(self.backend.tools_seen[-1])
        self.assertEqual(self.roles(), ["user", "assistant"])
        self.assertEqual(self.app.messages[-1]["content"], written)
        self.assertIn("<tool_call>", shown)
        self.assertNotIn("[calculate", shown)


class Stop(test_level3.Stop):
    build = BUILD


class NewChat(test_level3.NewChat):
    """Level 3's New chat must still work; loading now keeps the chat."""

    build = BUILD

    # Replaced by SavedChats.test_loading_a_model_keeps_the_chat.
    test_loading_a_model_clears_the_log = None


class Settings(test_level3.Settings):
    """Level 3's settings must still work, with one more key."""

    build = BUILD

    def test_saved_on_close(self):
        """Closing the window writes every setting as JSON (22.15)."""
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
                "chat_file": "",
            },
        )


class Approval(test_level3.Approval):
    build = BUILD


class PyTorchSafetyNets(test_level3.PyTorchSafetyNets):
    build = BUILD


class Templates(support.Case):
    """Step 19: chat templates that are not like Qwen's."""

    build = BUILD

    needs = ["backends"]

    def ask(self, backend, system_prompt, messages=None):
        if messages is None:
            messages = [{"role": "user", "content": "hi"}]
        list(backend.chat(messages, system_prompt, 0.7, False))
        return backend.prompts[-1]

    def test_system_prompt_is_a_message_of_its_own(self):
        """Most templates get the system prompt as a system message (19.3)."""
        backend = support.make_backend(self.build)
        self.assertEqual(self.ask(backend, "Be brief."), "system: Be brief.\nuser: hi")
        self.assertEqual(self.ask(backend, ""), "user: hi")

    def test_system_prompt_is_folded_in_when_refused(self):
        """A template with no system role gets it in the first message (19.3)."""
        backend = support.make_backend(self.build)
        backend.refuses_system = True
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "again"},
        ]
        prompt = self.ask(backend, "Be brief.", messages)
        self.assertEqual(prompt, "user: Be brief.\n\nhi\nassistant: hello\nuser: again")
        self.assertEqual(messages[0], {"role": "user", "content": "hi"})
        self.assertEqual(len(messages), 3)

    def test_other_template_errors_are_passed_on(self):
        """An error that is not about the system role still surfaces (19.3)."""
        backend = support.make_backend(self.build)

        def refuse(messages, thinking, tools=None):
            raise ValueError("this template is broken")

        backend.build_prompt = refuse
        with self.assertRaisesRegex(ValueError, "this template is broken"):
            self.ask(backend, "Be brief.")
        with self.assertRaisesRegex(ValueError, "this template is broken"):
            self.ask(backend, "")

    def test_summary_request_is_folded_in_too(self):
        """Compaction works with a template that refuses a system message (19.4)."""
        backend = support.make_backend(self.build, context_size=200)
        backend.refuses_system = True
        backend.replies = ["The user listed facts 0 to 4."]
        messages = []
        for number in range(8):
            messages.append({"role": "user", "content": f"fact {number} " * 5})
            messages.append({"role": "assistant", "content": "noted"})
        messages.append({"role": "user", "content": "the newest question"})
        list(backend.chat(messages, "", 0.7, False))
        self.assertEqual(
            messages[0]["content"],
            "Summary of our conversation so far:\nThe user listed facts 0 to 4.",
        )
        request = backend.prompts[0]
        instructions = self.build.backends.SUMMARY_INSTRUCTIONS
        self.assertTrue(
            request.startswith("user: " + instructions + "\n\nuser: fact 0")
        )

    def test_offers_tools(self):
        """A template that writes nothing about tools is found out (19.5)."""
        tools = [{"type": "function", "function": {"name": "calculate"}}]
        backend = support.make_backend(self.build)
        self.assertIs(backend.offers_tools(tools), True)
        backend.knows_tools = False
        self.assertIs(backend.offers_tools(tools), False)

    def load_gguf(self, trained, fits):
        """Load a pretend .gguf file; return the backend and the sizes tried."""
        tried = []

        class Llama:
            def __init__(self, model_path, vocab_only=False, verbose=True, **more):
                self.metadata = {
                    "general.architecture": "pretend",
                    "pretend.context_length": str(trained),
                    "tokenizer.chat_template": "a template",
                }
                if not vocab_only:
                    tried.append(more["n_ctx"])
                    if more["n_ctx"] > fits:
                        raise ValueError("Failed to create llama_context")

            def token_eos(self):
                return 2

            def token_bos(self):
                return 1

            def detokenize(self, tokens, special=False):
                return b"<mark>"

        class Formatter:
            def __init__(self, template, eos_token, bos_token):
                pass

        library = types.ModuleType("llama_cpp")
        library.Llama = Llama
        formats = types.ModuleType("llama_cpp.llama_chat_format")
        formats.Jinja2ChatFormatter = Formatter
        library.llama_chat_format = formats
        pretend = {"llama_cpp": library, "llama_cpp.llama_chat_format": formats}
        with mock.patch.dict(sys.modules, pretend):
            backend = self.build.backends.LlamaCppBackend("C:/models/pretend.gguf")
        return backend, tried

    def test_a_load_never_asks_for_more_than_the_limit(self):
        """A model trained for a huge context is loaded with less (19.1, 19.7)."""
        limit = self.build.backends.LARGEST_CONTEXT
        self.assertEqual(limit, 32768)
        backend, tried = self.load_gguf(trained=262144, fits=10**9)
        self.assertEqual(tried, [limit])
        self.assertEqual(backend.context_size, limit)

    def test_a_small_model_keeps_its_own_context(self):
        """A model trained for less than the limit keeps its own context (19.7)."""
        backend, tried = self.load_gguf(trained=8192, fits=10**9)
        self.assertEqual(tried, [8192])
        self.assertEqual(backend.context_size, 8192)

    def test_a_context_that_does_not_fit_is_still_halved(self):
        """Below the limit, level 1's halving goes on as before (19.7)."""
        backend, tried = self.load_gguf(trained=131072, fits=10000)
        self.assertEqual(tried, [32768, 16384, 8192])
        self.assertEqual(backend.context_size, 8192)
        with self.assertRaisesRegex(ValueError, "llama_context"):
            self.load_gguf(trained=131072, fits=100)

    def test_start_token_is_sent_once(self):
        """llama.cpp is handed tokens with one start-of-text token (19.8)."""
        outer = self

        class Llm:
            def __init__(self, tokens, start):
                self.tokens = tokens
                self.start = start
                self.sent = None

            def tokenize(self, text, add_bos, special=False):
                if text == b"":
                    outer.assertIs(add_bos, True)
                    return list(self.start)
                outer.assertEqual(text, "the prompt".encode("utf-8"))
                outer.assertIs(add_bos, False)
                outer.assertIs(special, True)
                return list(self.tokens)

            def create_completion(self, prompt, max_tokens, temperature, stream):
                outer.assertIs(stream, True)
                outer.assertEqual(temperature, 0.5)
                self.sent = prompt
                for text in ["Hel", "", "lo"]:
                    yield {"choices": [{"text": text}]}

        cases = [
            ([1, 7, 8], [1], [1, 7, 8]),  # the template wrote it
            ([7, 8], [1], [1, 7, 8]),  # the template did not
            ([7, 8], [], [7, 8]),  # a model that wants none
            ([1, 1, 7], [1], [1, 1, 7]),  # what the template wrote is kept
        ]
        for tokens, start, expected in cases:
            backend = object.__new__(self.build.backends.LlamaCppBackend)
            backend.llm = Llm(tokens, start)
            self.assertEqual(list(backend.stream("the prompt", 0.5)), ["Hel", "lo"])
            self.assertEqual(backend.llm.sent, expected)

    def test_unload_does_nothing_by_default(self):
        """The shared class holds no memory, so unload() is harmless (19.6)."""
        backend = support.make_backend(self.build)
        self.assertIsNone(backend.unload())

    def test_unload_closes_llama_cpp(self):
        """llama.cpp is told to free its memory (19.9)."""

        class Llm:
            closed = False

            def close(self):
                self.closed = True

        backend = object.__new__(self.build.backends.LlamaCppBackend)
        backend.llm = Llm()
        backend.unload()
        self.assertTrue(backend.llm.closed)


class Calls(support.Case):
    """Step 20: tool calls written as bare JSON."""

    build = BUILD

    needs = ["tools"]

    def test_text_before_call(self):
        """JSON at the start of a reply is not ordinary text (20.2)."""
        before = self.build.tools.text_before_call
        self.assertEqual(before("Sure.\n<tool_call>\n<function=x>"), "Sure.\n")
        self.assertEqual(before("Just an answer."), "Just an answer.")
        self.assertEqual(before(""), "")
        self.assertEqual(before('{"name": "calc'), "")
        self.assertEqual(before('\n [{"name": "calc'), "")
        self.assertEqual(
            before("The set {1, 2} has two members."), "The set {1, 2} has two members."
        )

    def test_json_calls(self):
        """Calls are read whatever keys and separators the model used (20.3)."""
        json_calls = self.build.tools.json_calls
        self.assertEqual(
            json_calls(LLAMA_THREE_CALLS),
            [
                {"name": "calculate", "arguments": {"expression": "12 * 12"}},
                {"name": "calculate", "arguments": {"expression": "99 + 1"}},
                {"name": "save_note", "arguments": {"text": "hello"}},
            ],
        )
        self.assertEqual(
            json_calls(LLAMA_ODD_CALL),
            [{"name": "calculate", "arguments": {"expression": "17 * 23"}}],
        )
        self.assertEqual(
            json_calls(
                '[{"name": "a", "arguments": {}}, {"name": "b", "arguments": "{\\"n\\": 1}"}]'
            ),
            [{"name": "a", "arguments": {}}, {"name": "b", "arguments": {"n": 1}}],
        )

    def test_json_that_is_not_a_call(self):
        """JSON without a name and arguments is not a call (20.3)."""
        json_calls = self.build.tools.json_calls
        for text in [
            '{"name": "Biscuit"}',
            '{"colour": "blue", "arguments": {}}',
            '{"name": 5, "arguments": {}}',
            '{"name": "x", "arguments": "not json"}',
            '{"name": "x", "arguments": [1, 2]}',
            "[1, 2, 3]",
            "{not json at all}",
            "no brackets here",
            "",
        ]:
            self.assertEqual(json_calls(text), [], text)

    def test_parse_bare_json(self):
        """A reply that is a JSON call has no text, only calls (20.4)."""
        parse = self.build.tools.parse_tool_calls
        self.assertEqual(
            parse(LLAMA_ONE_CALL),
            ("", [{"name": "calculate", "arguments": {"expression": "6 * 7"}}]),
        )
        self.assertEqual(len(parse("\n" + LLAMA_THREE_CALLS)[1]), 3)

    def test_parse_gives_text_back_when_there_is_no_call(self):
        """A reply with no readable call is returned whole (20.4)."""
        parse = self.build.tools.parse_tool_calls
        for text in [
            '{"colour": "blue"}',
            "[Verse 1]\nLa la la",
            "Sure.\n<tool_call>{not json}</tool_call>",
            '{"name": "calc',
        ]:
            self.assertEqual(parse(text), (text, []), text)


class SavedChats(support.AppCase):
    """Steps 22.5 to 22.8 and 22.12 to 22.15: conversations in files."""

    build = BUILD

    def chats(self):
        return sorted((self.tmp / "chats").glob("*.json"))

    def read(self, path):
        return json.loads(path.read_text(encoding="utf-8"))

    def clock(self):
        """Make each new chat's name one second later than the last."""
        names = (f"2026-11-16 10.00.{second:02d}" for second in range(60))
        patcher = mock.patch.object(
            self.module.time, "strftime", side_effect=lambda form: next(names)
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def pick(self, path):
        """Make the file picker answer with path the next time it opens."""
        picker = mock.Mock(return_value=str(path))
        self.patch_picker = mock.patch.object(
            self.module.filedialog, "askopenfilename", picker
        )
        self.patch_picker.start()
        self.addCleanup(self.patch_picker.stop)
        return picker

    def test_nothing_is_saved_before_the_first_reply(self):
        """Opening the window and loading a model write no chat (22.2, 22.8)."""
        self.load()
        self.assertIsNone(self.app.chat_file)
        self.assertEqual(self.chats(), [])

    def test_a_reply_saves_the_chat(self):
        """Each reply rewrites the conversation's one file (22.8, 22.12)."""
        self.load()
        self.backend.replies = ["Hello Sam."]
        self.send("My name is Sam.")
        (path,) = self.chats()
        self.assertRegex(path.name, r"^\d{4}-\d\d-\d\d \d\d\.\d\d\.\d\d\.json$")
        self.assertEqual(self.app.chat_file, path)
        self.assertEqual(
            self.read(path),
            {
                "messages": [
                    {"role": "user", "content": "My name is Sam."},
                    {"role": "assistant", "content": "Hello Sam."},
                ],
                "log": "You: My name is Sam.\n\nModel: Hello Sam.\n\n",
            },
        )
        self.send("And again.")
        self.assertEqual(self.chats(), [path])
        saved = self.read(path)
        self.assertEqual(saved["messages"], self.app.messages)
        self.assertEqual(len(saved["messages"]), 4)
        self.assertEqual(saved["log"], self.log())

    def test_other_alphabets_stay_readable(self):
        """Letters outside ASCII are written as themselves (22.8)."""
        self.load()
        self.backend.replies = ["こんにちは"]
        self.send("Say hello in Japanese, s'il vous plaît.")
        text = self.chats()[0].read_text(encoding="utf-8")
        self.assertIn("こんにちは", text)
        self.assertIn("plaît", text)

    def test_tool_calls_are_saved_too(self):
        """A conversation that used a tool can be written as JSON (22.8)."""
        self.load()
        self.backend.replies = [
            support.call_text("calculate", expression="6 * 7"),
            "It is 42.",
        ]
        self.send("What is 6 * 7?")
        saved = self.read(self.chats()[0])
        self.assertEqual(
            [message["role"] for message in saved["messages"]],
            ["user", "assistant", "tool", "assistant"],
        )
        self.assertIn("[calculate {'expression': '6 * 7'} -> 42]", saved["log"])

    def test_new_chat_starts_a_new_file(self):
        """New chat leaves the old file alone and starts another (22.5)."""
        self.clock()
        self.load()
        self.send("first chat")
        (first,) = self.chats()
        before = first.read_text(encoding="utf-8")
        self.app.new_chat_button.invoke()
        self.assertIsNone(self.app.chat_file)
        self.assertEqual(self.chats(), [first])
        self.send("second chat")
        self.assertEqual(len(self.chats()), 2)
        self.assertEqual(first.read_text(encoding="utf-8"), before)
        second = self.chats()[1]
        self.assertEqual(self.app.chat_file, second)
        self.assertEqual(self.read(second)["messages"][0]["content"], "second chat")

    def test_two_chats_in_one_second_get_two_files(self):
        """A name that is taken is never used again (22.8)."""
        patcher = mock.patch.object(
            self.module.time, "strftime", return_value="2026-11-16 10.00.00"
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.load()
        for number in range(3):
            self.send(f"chat number {number}")
            self.app.new_chat_button.invoke()
        names = [path.name for path in self.chats()]
        self.assertEqual(
            names,
            [
                "2026-11-16 10.00.00 (2).json",
                "2026-11-16 10.00.00 (3).json",
                "2026-11-16 10.00.00.json",
            ],
        )
        first = self.read(self.tmp / "chats" / "2026-11-16 10.00.00.json")
        self.assertEqual(first["messages"][0]["content"], "chat number 0")

    def test_open_chat_brings_a_conversation_back(self):
        """Open chat restores the messages, the log and the file (22.6, 22.7)."""
        self.clock()
        self.load()
        self.backend.replies = ["Hello Sam."]
        self.send("My name is Sam.")
        (first,) = self.chats()
        first_log = self.log()
        self.app.new_chat_button.invoke()
        self.send("Something else entirely.")

        picker = self.pick(first)
        self.app.open_chat_button.invoke()
        self.assertEqual(picker.call_args.kwargs["initialdir"], self.tmp / "chats")
        self.assertEqual(self.roles(), ["user", "assistant"])
        self.assertEqual(self.app.messages[0]["content"], "My name is Sam.")
        self.assertEqual(self.log(), first_log)
        self.assertEqual(self.app.chat_file, first)
        self.assertEqual(str(self.app.chat_log.cget("state")), "disabled")

        self.send("What is my name?")
        self.assertIn("My name is Sam.", self.backend.prompts[-1])
        self.assertNotIn("Something else", self.backend.prompts[-1])
        self.assertEqual(len(self.chats()), 2)
        self.assertEqual(len(self.read(first)["messages"]), 4)

    def test_cancelling_the_picker_changes_nothing(self):
        """Cancel in the file picker leaves the conversation alone (22.6)."""
        self.load()
        self.send("hi")
        log = self.log()
        self.pick("")
        self.app.open_chat_button.invoke()
        self.assertEqual(self.log(), log)
        self.assertEqual(self.roles(), ["user", "assistant"])

    def test_a_file_that_is_not_a_chat_changes_nothing(self):
        """A bad file only changes the status line (22.7)."""
        self.load()
        self.send("hi")
        log = self.log()
        file = self.app.chat_file
        bad = self.tmp / "bad.json"
        for text in ["{not json", "[1, 2, 3]", '{"messages": []}', '{"log": ""}']:
            bad.write_text(text, encoding="utf-8")
            self.app.status.config(text="")
            self.app.read_chat(str(bad))
            self.assertEqual(self.status(), f"Could not open the chat in {bad}", text)
            self.assertEqual(self.log(), log)
            self.assertEqual(self.roles(), ["user", "assistant"])
            self.assertEqual(self.app.chat_file, file)
        self.app.read_chat(str(self.tmp / "no such file.json"))
        self.assertTrue(self.status().startswith("Could not open the chat in"))
        self.assertEqual(self.log(), log)

    def test_open_chat_waits_for_the_reply(self):
        """Open chat is greyed out while a reply is being written (22.13)."""
        self.load()
        self.assertEqual(self.state(self.app.open_chat_button), "normal")
        self.backend.replies = [support.endless()]
        self.send("hi", wait=False)
        self.pump(lambda: "word" in self.log(), what="the first words")
        self.assertEqual(self.state(self.app.open_chat_button), "disabled")
        self.app.stop_button.invoke()
        self.idle()
        self.assertEqual(self.state(self.app.open_chat_button), "normal")

    def test_loading_a_model_keeps_the_chat(self):
        """A second model carries on the same conversation (22.12)."""
        self.load()
        self.send("My name is Sam.")
        log = self.log()
        file = self.app.chat_file
        self.load("C:/models/another.gguf")
        self.assertEqual(self.roles(), ["user", "assistant"])
        self.assertEqual(self.log(), log)
        self.assertEqual(self.app.chat_file, file)
        self.send("What is my name?")
        self.assertIn("My name is Sam.", self.backend.prompts[-1])
        self.assertEqual(len(self.chats()), 1)

    def test_the_last_chat_comes_back_on_start(self):
        """Closing and opening the app restores the conversation (22.14, 22.15)."""
        self.load()
        self.backend.replies = ["Hello Sam."]
        self.send("My name is Sam.")
        log = self.log()
        (path,) = self.chats()
        self.shut()
        saved = self.read(self.tmp / "settings.json")
        self.assertEqual(saved["chat_file"], str(path))

        self.open()
        self.assertEqual(self.log(), log)
        self.assertEqual(self.roles(), ["user", "assistant"])
        self.assertEqual(self.app.chat_file, path)
        self.load()
        self.send("What is my name?")
        self.assertIn("My name is Sam.", self.backend.prompts[-1])
        self.assertEqual(self.chats(), [path])

    def test_a_new_chat_stays_new_on_start(self):
        """After New chat, the next start has no conversation open (22.15)."""
        self.load()
        self.send("hi")
        self.app.new_chat_button.invoke()
        self.shut()
        self.assertEqual(self.read(self.tmp / "settings.json")["chat_file"], "")
        self.open()
        self.assertEqual(self.log(), "")
        self.assertEqual(self.app.messages, [])

    def test_a_level_3_settings_file_still_works(self):
        """Settings saved without "chat_file" are all read back (22.14)."""
        settings = {
            "backend_kind": "pytorch",
            "model_path": "C:/models/Some Model",
            "temperature": 1.3,
            "thinking": True,
            "thinking_instructions": "Check your work.",
            "use_tools": False,
            "system_prompt": "Always answer in French.",
            "allowed_tools": ["save_note"],
        }
        (self.tmp / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        self.open()
        self.assertEqual(self.app.temperature.get(), 1.3)
        self.assertEqual(self.app.allowed_tools, ["save_note"])
        self.assertEqual(self.app.messages, [])
        self.assertEqual(self.status(), "Selected: C:/models/Some Model")

    def test_a_deleted_chat_file_is_not_fatal(self):
        """The app still starts when the last chat's file has gone (22.7, 22.14)."""
        self.load()
        self.send("hi")
        (path,) = self.chats()
        self.shut()
        path.unlink()
        self.open()
        self.assertEqual(self.log(), "")
        self.assertEqual(self.app.messages, [])
        self.assertIsNone(self.app.chat_file)
        self.load()
        self.send("hi again")
        self.assertEqual(len(self.chats()), 1)

    def test_a_chat_that_cannot_be_saved_carries_on(self):
        """A failed save is reported and the chat goes on (22.8)."""
        blocked = self.tmp / "blocked"
        blocked.write_text("a file where the folder should be")
        self.patch("CHATS_FOLDER", blocked / "chats")
        self.load()
        self.send("hi")
        self.assertTrue(self.status().startswith("Could not save this chat: "))
        self.assertEqual(self.roles(), ["user", "assistant"])
        self.assertEqual(self.state(self.app.send_button), "normal")
        self.send("hi again")
        self.assertEqual(self.roles(), ["user", "assistant"] * 2)


class OtherModels(support.AppCase):
    """Steps 22.4 and 22.9 to 22.12: the window with models that are not Qwen."""

    build = BUILD

    def test_a_template_without_tools_is_noticed(self):
        """The status line says so, and no tools are used (22.9, 22.12)."""
        self.backend.knows_tools = False
        self.load()
        self.assertTrue(
            self.status().endswith(
                "2 tools) This model's template has no place for tools."
            )
        )
        self.assertIs(self.app.offer_tools, False)
        self.backend.replies = [LLAMA_ONE_CALL]
        shown = self.send("What is 6 * 7?")
        self.assertIsNone(self.backend.tools_seen[-1])
        self.assertEqual(self.roles(), ["user", "assistant"])
        self.assertEqual(shown, f"You: What is 6 * 7?\n\nModel: {LLAMA_ONE_CALL}\n\n")

    def test_a_template_with_tools_is_not_remarked_on(self):
        """The usual status line is unchanged (22.12)."""
        self.load()
        self.assertTrue(self.status().endswith("2 tools)"))
        self.assertIs(self.app.offer_tools, True)

    def test_the_next_model_is_asked_again(self):
        """Whether tools are offered follows the model that is loaded (22.12)."""
        self.backend.knows_tools = False
        self.load()
        self.assertIs(self.app.offer_tools, False)
        self.backend.knows_tools = True
        self.load()
        self.assertIs(self.app.offer_tools, True)

    def test_a_bare_json_call_is_run_and_not_shown(self):
        """A Llama 3.2-style call runs like any other (20.4, 22.11)."""
        self.load()
        self.backend.replies = [LLAMA_ONE_CALL, "It is 42."]
        shown = self.send("What is 6 * 7?")
        self.assertEqual(
            shown,
            "You: What is 6 * 7?\n\nModel: "
            "\n[calculate {'expression': '6 * 7'} -> 42]\nIt is 42.\n\n",
        )
        self.assertEqual(self.roles(), ["user", "assistant", "tool", "assistant"])
        self.assertEqual(self.app.messages[1]["content"], "")

    def test_several_bare_json_calls(self):
        """Calls separated by ";" all run, in order (20.3, 22.10)."""
        self.load()
        self.backend.replies = [
            '{"name": "calculate", "parameters": {"expression": "12 * 12"}}; '
            '{"name": "calculate", "parameters": {"expression": "99 + 1"}}',
            "144 and 100.",
        ]
        shown = self.send("Two sums, please.")
        self.assertIn("-> 144]", shown)
        self.assertIn("-> 100]", shown)
        self.assertLess(shown.index("-> 144]"), shown.index("-> 100]"))
        self.assertEqual(self.roles().count("tool"), 2)

    def test_json_is_held_back_while_it_arrives(self):
        """Nothing that may be a call is shown until the reply is complete (22.11)."""
        self.load()
        go_on = threading.Event()

        def slowly():
            yield '{"name": "calculate", '
            go_on.wait(10)
            yield '"parameters": {"expression": "6 * 7"}}'

        self.backend.replies = [slowly(), "It is 42."]
        self.send("What is 6 * 7?", wait=False)
        end = time.time() + 0.5
        while time.time() < end:
            self.root.update()
            time.sleep(0.01)
        self.assertTrue(self.log().endswith("Model: "))
        go_on.set()
        self.idle()
        self.assertNotIn('{"name"', self.log())
        self.assertIn("[calculate {'expression': '6 * 7'} -> 42]", self.log())

    def test_json_that_is_an_answer_is_shown_in_the_end(self):
        """A reply that only looked like a call appears once, whole (22.11)."""
        self.load()
        answer = '{"colour": "blue", "hex": "#0000ff"}'
        self.backend.replies = [answer]
        shown = self.send("Give me a colour as JSON.")
        self.assertEqual(
            shown, f"You: Give me a colour as JSON.\n\nModel: {answer}\n\n"
        )
        self.assertEqual(self.app.messages[-1]["content"], answer)

    def test_thinking_is_shown_before_a_bare_json_call(self):
        """Thinking still appears when the answer is a call (22.11)."""
        self.load()
        self.backend.replies = [
            "I should use the calculator.</think>\n\n" + LLAMA_ONE_CALL,
            "It is 42.",
        ]
        shown = self.send("What is 6 * 7?")
        self.assertIn("I should use the calculator.\n[end of thinking]", shown)
        self.assertNotIn('{"name"', shown)
        self.assertIn("-> 42]", shown)

    def test_a_failed_reply_is_taken_back(self):
        """After an error the unanswered question is gone again (22.10, 22.12)."""
        self.load()
        self.send("first")
        self.backend.replies = [RuntimeError("the model fell over")]
        shown = self.send("second")
        self.assertEqual(self.status(), "Error: the model fell over")
        self.assertEqual(shown, "You: second\n\nModel:  [failed]\n\n")
        self.assertEqual(self.roles(), ["user", "assistant"])
        self.assertEqual(self.state(self.app.send_button), "normal")
        shown = self.send("third")
        self.assertEqual(self.roles(), ["user", "assistant"] * 2)
        self.assertNotIn("second", self.backend.prompts[-1])

    def test_a_failure_after_a_tool_call_takes_the_whole_turn_back(self):
        """The call and its result go too, back to the question (22.12)."""
        self.load()
        self.backend.replies = [
            support.call_text("calculate", expression="6 * 7"),
            RuntimeError("the model fell over"),
        ]
        shown = self.send("What is 6 * 7?")
        self.assertEqual(self.app.messages, [])
        self.assertIn("-> 42]", shown)
        self.assertTrue(shown.endswith("-> 42]\n [failed]\n\n"))

    def test_the_old_model_is_let_go_before_the_new_one_loads(self):
        """Load unloads the model it replaces first (22.4)."""
        self.load()
        first = self.backend
        events = []
        first.unload = lambda: events.append("first model unloaded")
        second = support.make_backend(self.build)

        def load_second(kind, path):
            events.append("second model loading")
            return second

        self.patch("load_backend", load_second)
        self.app.load_button.invoke()
        self.assertIsNone(self.app.backend)
        self.idle()
        self.assertEqual(events, ["first model unloaded", "second model loading"])
        self.assertIs(self.app.backend, second)

    def test_a_failed_load_leaves_no_model(self):
        """After a load that fails, Send waits for one that works (22.4)."""
        self.load()

        def refuse(kind, path):
            raise RuntimeError("not a model")

        self.patch("load_backend", refuse)
        self.app.load_button.invoke()
        self.idle()
        self.assertIsNone(self.app.backend)
        self.assertEqual(self.send("hi"), "")
        self.assertEqual(self.app.messages, [])

    def test_a_failed_load_takes_nothing_back(self):
        """A model that will not load leaves the conversation alone (22.12)."""
        self.load()
        self.send("hi")
        log = self.log()

        def refuse(kind, path):
            raise RuntimeError("not a model")

        self.patch("load_backend", refuse)
        self.app.load_button.invoke()
        self.idle()
        self.assertEqual(self.status(), "Error: not a model")
        self.assertEqual(self.roles(), ["user", "assistant"])
        self.assertEqual(self.log(), log)


if __name__ == "__main__":
    unittest.main()
