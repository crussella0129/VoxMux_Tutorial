"""Level 2: compaction, tools, the MCP client and server, and the tool loop."""

import json
import pathlib
import random
import shutil
import tempfile
import time
import unittest
import zoneinfo

import support
import test_level1

BUILD = support.load_build(support.folder_for(2))


class Install(test_level1.Install):
    """Step 6: level 1's install.py with one more package."""

    build = BUILD

    def test_tzdata_added(self):
        """tzdata is the last entry in STEPS (step 6)."""
        self.assertEqual(self.build.install.STEPS[-1], ["tzdata"])


class Compaction(support.Case):
    """Step 7: making room by summarising, then by forgetting."""

    build = BUILD

    needs = ["backends"]

    def conversation(self, turns):
        messages = []
        for number in range(turns):
            messages.append({"role": "user", "content": f"fact {number} " * 5})
            messages.append({"role": "assistant", "content": "noted"})
        messages.append({"role": "user", "content": "the newest question"})
        return messages

    def test_find_user(self):
        """find_user gives the next user message, or None (7.2)."""
        find_user = self.build.backends.find_user
        messages = [{"role": "user"}, {"role": "assistant"}, {"role": "tool"}]
        self.assertEqual(find_user(messages, 0), 0)
        self.assertIsNone(find_user(messages, 1))
        self.assertIsNone(find_user(messages, 9))

    def test_tools_reach_the_template(self):
        """chat() hands the tool list through to build_prompt (7.4, 7.5)."""
        backend = support.make_backend(self.build)
        tools = [{"type": "function"}]
        list(backend.chat([{"role": "user", "content": "hi"}], "", 0.7, False, tools))
        self.assertIs(backend.tools_seen[-1], tools)

    def test_older_half_becomes_a_summary(self):
        """Too long: the older half is replaced by a summary pair (7.6)."""
        backend = support.make_backend(self.build, context_size=200)
        backend.replies = ["thinking aloud</think>The user listed facts 0 to 4."]
        alerts = []
        backend.on_compact = lambda: alerts.append("compacting")
        messages = self.conversation(8)
        newest = messages[-1]
        list(backend.chat(messages, "", 0.7, False))
        self.assertEqual(alerts, ["compacting"])
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(
            messages[0]["content"],
            "Summary of our conversation so far:\nThe user listed facts 0 to 4.",
        )
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[2]["role"], "user")
        self.assertIs(messages[-1], newest)
        self.assertLess(len(messages), 17)
        summary_request = backend.prompts[0]
        self.assertIn(self.build.backends.SUMMARY_INSTRUCTIONS, summary_request)
        self.assertIn("user: fact 0", summary_request)

    def test_forgets_when_it_cannot_summarise(self):
        """With nothing to cut cleanly, old messages are forgotten (7.5)."""
        backend = support.make_backend(self.build, context_size=40)
        messages = [
            {"role": "user", "content": "word " * 30},
            {"role": "assistant", "content": "noted"},
            {"role": "user", "content": "the newest question"},
        ]
        list(backend.chat(messages, "", 0.7, False))
        self.assertEqual(messages, [{"role": "user", "content": "the newest question"}])

    def test_one_long_message_is_still_sent(self):
        """A single message that is too long is used as it is (7.5)."""
        backend = support.make_backend(self.build, context_size=10)
        messages = [{"role": "user", "content": "word " * 50}]
        self.assertEqual(list(backend.chat(messages, "", 0.7, False)), ["ok"])
        self.assertEqual(len(messages), 1)

    def test_random_conversations(self):
        """Making room never crashes or loses the newest question (7.5, 7.6)."""
        chooser = random.Random(7)
        for _ in range(300):
            messages = []
            for _ in range(chooser.randint(1, 30)):
                role = chooser.choice(["user", "assistant", "tool"])
                if not messages:
                    role = "user"
                message = {"role": role, "content": "word " * chooser.randint(0, 40)}
                if role == "tool":
                    message["name"] = "calculate"
                messages.append(message)
            last_user = max(
                index for index, m in enumerate(messages) if m["role"] == "user"
            )
            tail = messages[last_user:]
            backend = support.make_backend(
                self.build, context_size=chooser.randint(8, 400)
            )
            list(backend.chat(messages, "Be brief.", 0, False, None))
            self.assertEqual(messages[0]["role"], "user")
            self.assertEqual(messages[-len(tail) :], tail)


class Tools(support.Case):
    """Step 8: tools.py."""

    build = BUILD

    needs = ["tools"]

    def test_calculator(self):
        """calculate does exact arithmetic (8.3, 8.4)."""
        calculate = self.build.tools.calculate
        self.assertEqual(calculate("1234 * 5678"), "7006652")
        self.assertEqual(calculate("(17 * 23) + 4 / 2"), "393.0")
        self.assertEqual(calculate("-2 ** 3 + 7 // 2 + 7 % 3"), "-4")

    def test_calculator_refuses_code(self):
        """Anything that is not arithmetic is refused, not run (8.3)."""
        calculate = self.build.tools.calculate
        for text in ["__import__('os').getcwd()", "len('abc')", "'a' * 3", "x + 1"]:
            with self.assertRaises((ValueError, SyntaxError)):
                calculate(text)

    def test_calculator_refuses_huge_powers(self):
        """Powers that would freeze the app are refused quickly (8.3)."""
        calculate = self.build.tools.calculate
        start = time.time()
        for text in ["9 ** 9 ** 9", "(2 ** 1000) ** 1000", "2 ** 100001"]:
            with self.assertRaises(ValueError):
                calculate(text)
        self.assertLess(time.time() - start, 2)
        self.assertEqual(calculate("2 ** 10"), "1024")

    def test_schema(self):
        """schema_for describes a tool from its name, docstring and hints (8.5)."""
        tools = self.build.tools
        schema = tools.schema_for(tools.random_number)
        function = schema["function"]
        self.assertEqual(schema["type"], "function")
        self.assertEqual(function["name"], "random_number")
        self.assertIn("random whole number", function["description"])
        self.assertNotIn("[", function["description"])
        self.assertEqual(
            function["parameters"],
            {
                "type": "object",
                "properties": {"low": {"type": "integer"}, "high": {"type": "integer"}},
                "required": ["low", "high"],
            },
        )

    def test_parse_function_style(self):
        """A <function=...> call is read, values kept as strings (8.6)."""
        text = "Let me work that out.\n" + support.call_text(
            "calculate", expression="2 + 3"
        )
        before, calls = self.build.tools.parse_tool_calls(text)
        self.assertEqual(before, "Let me work that out.")
        self.assertEqual(
            calls, [{"name": "calculate", "arguments": {"expression": "2 + 3"}}]
        )

    def test_parse_json_style(self):
        """A JSON call is read, with arguments as an object or as a string (8.6)."""
        parse = self.build.tools.parse_tool_calls
        text = '<tool_call>{"name": "random_number", "arguments": {"low": 1, "high": 6}}</tool_call>'
        self.assertEqual(
            parse(text),
            ("", [{"name": "random_number", "arguments": {"low": 1, "high": 6}}]),
        )
        text = '<tool_call>{"name": "calculate", "arguments": "{\\"expression\\": \\"1+1\\"}"}</tool_call>'
        self.assertEqual(parse(text)[1][0]["arguments"], {"expression": "1+1"})

    def test_parse_broken_calls(self):
        """Unreadable calls are skipped; a call cut off mid-way is still read (8.6)."""
        parse = self.build.tools.parse_tool_calls
        self.assertEqual(parse("Just an answer."), ("Just an answer.", []))
        self.assertEqual(parse("<tool_call>{not json}</tool_call>")[1], [])
        self.assertEqual(parse("<tool_call>[1, 2]</tool_call>")[1], [])
        cut_off = "<tool_call>\n<function=calculate>\n<parameter=expression>\n1+1\n</parameter>"
        self.assertEqual(
            parse(cut_off)[1],
            [{"name": "calculate", "arguments": {"expression": "1+1"}}],
        )

    def test_convert(self):
        """convert turns a string into the type the schema asks for (8.7)."""
        convert = self.build.tools.convert
        self.assertEqual(convert("7", "integer"), 7)
        self.assertEqual(convert("2.5", "number"), 2.5)
        self.assertIs(convert(" True ", "boolean"), True)
        self.assertIs(convert("no", "boolean"), False)
        self.assertEqual(convert("[1, 2]", "array"), [1, 2])
        self.assertEqual(convert("text", "string"), "text")
        self.assertEqual(convert("text", None), "text")
        self.assertEqual(convert(7, "integer"), 7)

    def test_toolbox(self):
        """The toolbox runs tools and turns every failure into "Error: ..." (8.8)."""
        toolbox = self.build.tools.Toolbox([])
        names = [schema["function"]["name"] for schema in toolbox.schemas]
        self.assertEqual(names, ["calculate", "random_number"])
        self.assertEqual(toolbox.run("calculate", {"expression": "6 * 7"}), "42")
        self.assertEqual(toolbox.run("random_number", {"low": "3", "high": "3"}), "3")
        self.assertEqual(
            toolbox.run("delete_everything", {}),
            "Error: there is no tool called delete_everything.",
        )
        self.assertTrue(
            toolbox.run("calculate", {"expression": "1 / 0"}).startswith("Error:")
        )
        self.assertTrue(toolbox.run("calculate", {"wrong": "1"}).startswith("Error:"))

    def test_first_tool_with_a_name_wins(self):
        """A server's tool does not replace a tool of the same name (8.8.2)."""

        class Server:
            schemas = [
                {"type": "function", "function": {"name": "calculate"}},
                {"type": "function", "function": {"name": "lookup"}},
            ]

            def call_tool(self, name, arguments):
                return f"{name} from the server"

        toolbox = self.build.tools.Toolbox([Server()])
        self.assertEqual(len(toolbox.schemas), 3)
        self.assertEqual(toolbox.run("calculate", {"expression": "1 + 1"}), "2")
        self.assertEqual(toolbox.run("lookup", {}), "lookup from the server")


class Mcp(support.Case):
    """Steps 9 to 11: the MCP client talking to the demo server."""

    build = BUILD

    needs = ["mcp_client", "demo_mcp_server"]

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="voxmux-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.servers = []
        self.addCleanup(self.stop_servers)

    def stop_servers(self):
        for server in self.servers:
            server.close()

    def start(self, servers):
        config = self.tmp / "mcp_servers.json"
        config.write_text(json.dumps({"mcpServers": servers}), encoding="utf-8")
        self.servers, problems = self.build.mcp_client.start_servers(config)
        return self.servers, problems

    def demo(self):
        shutil.copy(self.build.folder / "demo_mcp_server.py", self.tmp)
        servers, problems = self.start(
            {"demo": {"command": "python", "args": ["demo_mcp_server.py"]}}
        )
        self.assertEqual(problems, [])
        return servers[0]

    def test_config_in_the_build(self):
        """mcp_servers.json lists the demo server (step 11)."""
        config = json.loads((self.build.folder / "mcp_servers.json").read_text())
        self.assertEqual(
            config,
            {
                "mcpServers": {
                    "demo": {"command": "python", "args": ["demo_mcp_server.py"]}
                }
            },
        )

    def test_no_config_means_no_servers(self):
        """A missing config file is not an error (9.3)."""
        result = self.build.mcp_client.start_servers(self.tmp / "missing.json")
        self.assertEqual(result, ([], []))

    def test_tools_are_listed(self):
        """The demo server's three tools arrive as chat-template schemas (9.2.7)."""
        server = self.demo()
        names = [schema["function"]["name"] for schema in server.schemas]
        self.assertEqual(names, ["get_current_time", "save_note", "list_notes"])
        for schema in server.schemas:
            self.assertEqual(schema["type"], "function")
            self.assertEqual(schema["function"]["parameters"]["type"], "object")
            self.assertTrue(schema["function"]["description"])

    def test_notes_round_trip(self):
        """Notes are saved to a file and read back, in any language (9.2.8, 10.3)."""
        server = self.demo()
        self.assertEqual(server.call_tool("list_notes", {}), "There are no notes yet.")
        self.assertEqual(
            server.call_tool("save_note", {"text": "buy oat milk"}),
            "Saved. There are now 1 notes.",
        )
        server.call_tool("save_note", {"text": "こんにちは"})
        self.assertEqual(
            server.call_tool("list_notes", {}), "1. buy oat milk\n2. こんにちは"
        )
        saved = json.loads((self.tmp / "notes.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, ["buy oat milk", "こんにちは"])

    def test_clock(self):
        """get_current_time names the time zone it was asked for (10.3)."""
        try:
            zoneinfo.ZoneInfo("Asia/Tokyo")
        except zoneinfo.ZoneInfoNotFoundError:
            self.skipTest("no time zone database here: install tzdata")
        server = self.demo()
        self.assertTrue(
            server.call_tool("get_current_time", {"timezone": "Asia/Tokyo"}).endswith(
                " in Asia/Tokyo"
            )
        )

    def test_tool_errors_come_back_as_text(self):
        """A failing or unknown tool gives "Error: ...", not an exception (9.2.8, 10.4)."""
        server = self.demo()
        self.assertTrue(server.call_tool("no_such_tool", {}).startswith("Error:"))
        self.assertTrue(
            server.call_tool("get_current_time", {"timezone": "Not/AZone"}).startswith(
                "Error:"
            )
        )
        self.assertTrue(server.call_tool("save_note", {}).startswith("Error:"))

    def test_unknown_method_is_refused(self):
        """A method the server does not know raises on the client (9.2.5, 10.4)."""
        server = self.demo()
        with self.assertRaises(RuntimeError):
            server.request("no/such/method", {})
        self.assertEqual(server.request("ping", {}), {})

    def test_close_stops_the_server(self):
        """close() ends the server's process, its pipes and its log file (9.2.9)."""
        server = self.demo()
        server.close()
        self.assertIsNotNone(server.process.poll())
        self.assertFalse(server.reader.is_alive())
        self.assertTrue(server.process.stdin.closed)
        self.assertTrue(server.process.stdout.closed)
        self.assertTrue(server.log.closed)
        self.assertTrue((self.tmp / "mcp-demo.log").exists())

    def test_a_server_that_fails_is_reported(self):
        """One bad server becomes a problem; the others still start (9.3)."""
        shutil.copy(self.build.folder / "demo_mcp_server.py", self.tmp)
        (self.tmp / "crash.py").write_text("raise SystemExit(1)\n")
        servers, problems = self.start(
            {
                "crash": {"command": "python", "args": ["crash.py"]},
                "missing": {"command": "no-such-program-here"},
                "demo": {"command": "python", "args": ["demo_mcp_server.py"]},
            }
        )
        self.assertEqual([server.name for server in servers], ["demo"])
        self.assertEqual(len(problems), 2)
        self.assertEqual(problems[0], "crash: MCP server crash stopped")
        self.assertTrue(problems[1].startswith("missing: "))

    def test_stray_lines_are_skipped(self):
        """Lines that are not JSON messages do not confuse the client (9.2.5)."""
        (self.tmp / "noisy.py").write_text(
            "import sys\n"
            "sys.path.insert(0, '.')\n"
            "import demo_mcp_server\n"
            "print('starting up', flush=True)\n"
            "print('42', flush=True)\n"
            "demo_mcp_server.main()\n"
        )
        shutil.copy(self.build.folder / "demo_mcp_server.py", self.tmp)
        servers, problems = self.start(
            {"noisy": {"command": "python", "args": ["noisy.py"]}}
        )
        self.assertEqual(problems, [])
        self.assertEqual(len(servers[0].schemas), 3)


class Chat(test_level1.Chat):
    """Level 1's window tests must still pass in level 2."""

    build = BUILD


class ToolLoop(support.AppCase):
    """Step 12: the window's tool-calling loop."""

    build = BUILD

    def test_tools_are_counted(self):
        """The status line counts the tools after a load (12.8)."""
        self.load()
        self.assertTrue(self.status().endswith("(100000 tokens of context, 2 tools)"))

    def test_server_tools_are_counted_and_stopped(self):
        """MCP servers start with the first load and stop on close (12.5, 12.9)."""
        self.use_demo_server()
        self.load()
        self.assertTrue(self.status().endswith("5 tools)"))
        (server,) = self.app.toolbox.servers
        self.load()
        self.assertEqual(self.app.toolbox.servers, [server])
        self.shut()
        self.assertIsNotNone(server.process.poll())

    def test_server_problems_are_shown(self):
        """A server that will not start is named in the status line (12.8)."""
        config = {"mcpServers": {"broken": {"command": "no-such-program-here"}}}
        (self.tmp / "mcp_servers.json").write_text(json.dumps(config))
        self.load()
        self.assertIn("2 tools) MCP problems: broken: ", self.status())

    def test_tool_call_round_trip(self):
        """A call is run, shown, added to the conversation, and answered (12.6)."""
        self.load()
        self.backend.replies = [
            "One moment.\n" + support.call_text("calculate", expression="1234 * 5678"),
            "It is 7006652.",
        ]
        shown = self.send("What is 1234 * 5678?")
        self.assertIn("[calculate {'expression': '1234 * 5678'} -> 7006652]", shown)
        self.assertNotIn("<tool_call>", shown)
        self.assertTrue(shown.rstrip().endswith("It is 7006652."))
        self.assertEqual(self.roles(), ["user", "assistant", "tool", "assistant"])
        asked, result, answer = self.app.messages[1:]
        self.assertEqual(asked["content"], "One moment.")
        self.assertEqual(
            asked["tool_calls"],
            [
                {
                    "type": "function",
                    "function": {
                        "name": "calculate",
                        "arguments": {"expression": "1234 * 5678"},
                    },
                }
            ],
        )
        self.assertEqual(
            result, {"role": "tool", "name": "calculate", "content": "7006652"}
        )
        self.assertEqual(answer["content"], "It is 7006652.")
        self.assertIn("tool: 7006652", self.backend.prompts[-1])
        self.assertTrue(self.backend.tools_seen[-1])

    def test_tools_off(self):
        """With Use tools off, no tools are offered and no call is run (12.6)."""
        self.load()
        self.app.use_tools.set(False)
        self.backend.replies = [
            "Sure.\n" + support.call_text("calculate", expression="1 + 1")
        ]
        self.send("hi")
        self.assertIsNone(self.backend.tools_seen[-1])
        self.assertEqual(self.roles(), ["user", "assistant"])
        self.assertEqual(self.app.messages[-1]["content"], "Sure.")

    def test_too_many_rounds(self):
        """A model that never stops calling tools is stopped (12.6)."""
        self.load()
        rounds = self.module.MAX_TOOL_ROUNDS
        self.backend.replies = [support.call_text("calculate", expression="1 + 1")] * 9
        shown = self.send("hi")
        note = "(Stopped: too many tool calls in a row.)"
        self.assertTrue(shown.rstrip().endswith(note))
        self.assertEqual(self.roles().count("tool"), rounds)
        self.assertEqual(self.app.messages[-1], {"role": "assistant", "content": note})

    def test_compaction_is_announced(self):
        """The backend's compaction alert reaches the status line (12.8)."""
        self.load()
        self.assertTrue(callable(self.backend.on_compact))
        self.backend.on_compact()
        self.pump(lambda: self.status().startswith("Summarising"), what="the alert")
        self.assertEqual(self.status(), "Summarising older messages to make room...")


if __name__ == "__main__":
    unittest.main()
