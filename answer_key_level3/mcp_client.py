"""[9.1] mcp_client.py: a small Model Context Protocol (MCP) client.

How it works: an MCP server is a separate program that offers tools. This
client starts each server listed in mcp_servers.json as a child process and
talks to it over the child's stdin and stdout. Every message is one line of
JSON in the JSON-RPC 2.0 format: a request carries an "id" and gets back a
response with the same "id"; a notification has no "id" and gets no answer.
The conversation always opens the same way: "initialize", then the
"notifications/initialized" notification, then "tools/list" to learn what
the server offers. After that, "tools/call" runs a tool.

The numbers in square brackets match the step numbers in RECIPE_LEVEL2.md.
"""

import json
import os
import pathlib
import queue
import shutil
import subprocess
import sys
import threading

# [9.1] Constants: the protocol version this client speaks, and how long to
# wait for a server before giving up.
PROTOCOL_VERSION = "2025-06-18"
TIMEOUT_SECONDS = 60


class MCPServer:
    """[9.2] One running MCP server and the tools it offers.

    How it works: reading from a pipe waits until a line arrives, possibly
    for ever. So a small background thread does nothing but read the
    server's output and put each line in a queue. request() can then wait
    on the queue with a time limit, the same queue idea the app uses for its
    own threads.
    """

    def __init__(self, name, command, args, folder, env=None):
        """[9.2.1] Start the server, introduce ourselves, and list its tools.

        How it works: the command "python" is replaced by sys.executable,
        the Python running this app, so a server written in Python gets the
        same libraries the app has. Any other command is found the way a
        terminal would find it, by shutil.which. The server's own error
        output goes to a log file, mcp-<name>.log in the config's folder, so
        a server that will not start can be looked into. If the program
        cannot be started at all, the log file is closed before the error is
        passed on. If the opening exchange fails, the server is stopped
        before the error is passed on, so it is not left running in the
        background.
        """
        self.name = name
        if command == "python":
            program = sys.executable
        else:
            program = shutil.which(command) or command
        environment = dict(os.environ)
        if env:
            environment.update(env)
        log_path = pathlib.Path(folder) / f"mcp-{name}.log"
        self.log = open(log_path, "w", encoding="utf-8")
        try:
            self.process = subprocess.Popen(
                [program] + list(args),
                cwd=folder,
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self.log,
                text=True,
                encoding="utf-8",
            )
        except OSError:
            self.log.close()
            raise
        self.lines = queue.Queue()
        self.next_id = 1
        self.reader = threading.Thread(target=self.read_lines, daemon=True)
        self.reader.start()

        try:
            self.request(
                "initialize",
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "voxmux", "version": "1.0"},
                },
            )
            self.notify("notifications/initialized")
            self.schemas = self.list_tools()
        except Exception:
            self.close()
            raise

    def read_lines(self):
        """[9.2.2] Background thread: copy each line the server writes into the queue.

        How it works: looping over a pipe gives one line at a time and ends
        when the server closes it. None is then put in the queue as a
        signal that no more lines will ever come.
        """
        for line in self.process.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def send(self, message):
        """[9.2.3] Write one message to the server as a single line of JSON."""
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def notify(self, method, params=None):
        """[9.2.4] Send a notification: a message that gets no answer."""
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self.send(message)

    def request(self, method, params):
        """[9.2.5] Send a request and wait for the response with the same id.

        How it works: each request gets the next id number. Lines are read
        from the queue until the matching response arrives. On the way, the
        server may send its own notifications (ignored) or its own requests
        (answered by answer_server_request), and lines that are not a JSON
        object are skipped. A response holding "error" becomes an exception.
        """
        request_id = self.next_id
        self.next_id = self.next_id + 1
        self.send(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        )

        while True:
            try:
                line = self.lines.get(timeout=TIMEOUT_SECONDS)
            except queue.Empty:
                raise TimeoutError(f"MCP server {self.name} did not answer {method}")
            if line is None:
                raise ConnectionError(f"MCP server {self.name} stopped")
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if not isinstance(message, dict):
                continue
            if "method" in message:
                if "id" in message:
                    self.answer_server_request(message)
                continue
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(message["error"].get("message", "unknown error"))
                return message.get("result", {})

    def answer_server_request(self, message):
        """[9.2.6] Answer a request the server sent us.

        How it works: servers may ask a client things, such as "ping" (are
        you still there?). This client answers ping and politely refuses
        everything else with JSON-RPC's standard "method not found" error.
        """
        if message["method"] == "ping":
            self.send({"jsonrpc": "2.0", "id": message["id"], "result": {}})
        else:
            error = {"code": -32601, "message": "Method not found"}
            self.send({"jsonrpc": "2.0", "id": message["id"], "error": error})

    def list_tools(self):
        """[9.2.7] Ask for every tool and turn each into a chat-template schema.

        How it works: a server may hand its list over in pages; while a
        response carries a "nextCursor", that cursor is sent back to get the
        next page. MCP describes a tool's arguments as "inputSchema", which
        is exactly what a chat template calls "parameters".
        """
        schemas = []
        cursor = None
        while True:
            params = {}
            if cursor:
                params["cursor"] = cursor
            result = self.request("tools/list", params)
            for item in result.get("tools", []):
                schemas.append(
                    {
                        "type": "function",
                        "function": {
                            "name": item["name"],
                            "description": item.get("description", ""),
                            "parameters": item.get("inputSchema", {"type": "object"}),
                        },
                    }
                )
            cursor = result.get("nextCursor")
            if not cursor:
                return schemas

    def call_tool(self, name, arguments):
        """[9.2.8] Run one of this server's tools and return its result as text.

        How it works: a result's "content" is a list of parts. The text parts
        are joined together; other kinds, such as images, are noted but not
        shown. If the server says the tool failed ("isError"), the text is
        returned starting "Error:".
        """
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        parts = []
        for part in result.get("content", []):
            if part.get("type") == "text":
                parts.append(part["text"])
            else:
                parts.append(f"[{part.get('type')} content not shown]")
        text = "\n".join(parts)
        if result.get("isError"):
            return "Error: " + text
        return text

    def close(self):
        """[9.2.9] Stop the server politely, then close its pipe and its log file.

        How it works: MCP's way to end a conversation over stdin is to close
        the server's stdin. A well-behaved server notices the end of its
        input and exits on its own. It gets five seconds to do that; if it is
        still running after that, it is killed. When the server has gone its
        output ends, so the reader thread finishes, and only then is the
        output pipe closed: closing a pipe while another thread is waiting
        to read from it can hang. The reader gets five seconds too. If it is
        still reading after that, some other program is holding the pipe
        open, and the pipe is left alone.
        """
        try:
            self.process.stdin.close()
            self.process.wait(timeout=5)
        except Exception:
            self.process.kill()
            self.process.wait()
        self.reader.join(timeout=5)
        if not self.reader.is_alive():
            self.process.stdout.close()
        self.log.close()


def start_servers(config_path):
    """[9.3] Start every server listed in the config file.

    How it works: the file uses the same layout as other MCP clients: an
    "mcpServers" object whose keys are server names, each with a "command",
    optional "args" and optional "env". A server that fails to start is
    reported in problems instead of stopping the others. No file means no
    servers.
    """
    path = pathlib.Path(config_path)
    servers = []
    problems = []
    if not path.exists():
        return servers, problems
    config = json.loads(path.read_text(encoding="utf-8"))
    for name, settings in config.get("mcpServers", {}).items():
        try:
            server = MCPServer(
                name,
                settings["command"],
                settings.get("args", []),
                path.parent,
                settings.get("env"),
            )
            servers.append(server)
        except Exception as error:
            problems.append(f"{name}: {error}")
    return servers, problems
