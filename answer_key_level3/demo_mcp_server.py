"""[10.1] demo_mcp_server.py: a tiny MCP server with three tools.

How it works: the client starts this file as a child process. It reads one
JSON-RPC message per line from stdin and writes each response as one line
to stdout. Because stdout is the channel to the client, nothing else may be
printed there; anything meant for a person goes to stderr instead. It
offers three tools: the time in any time zone, and saving and listing notes
kept in notes.json next to this file.

The numbers in square brackets match the step numbers in RECIPE_LEVEL2.md.
"""

import datetime
import json
import pathlib
import sys
import zoneinfo

# [10.1] Constants: where notes are kept, and what this server calls itself.
NOTES_FILE = pathlib.Path(__file__).with_name("notes.json")
SERVER_INFO = {"name": "voxmux-demo", "version": "1.0"}

# [10.2] The tools, described the MCP way: a name, a description, and an
# inputSchema saying what arguments each one takes.
TOOLS = [
    {
        "name": "get_current_time",
        "description": "Get the current date and time in a time zone, such as Europe/London or Asia/Tokyo.",
        "inputSchema": {
            "type": "object",
            "properties": {"timezone": {"type": "string"}},
            "required": ["timezone"],
        },
    },
    {
        "name": "save_note",
        "description": "Save a short note so it can be read back later, even after the app is closed.",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "list_notes",
        "description": "List every note saved so far.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def get_current_time(timezone):
    """[10.3] The tools themselves: ordinary functions that return text."""
    now = datetime.datetime.now(zoneinfo.ZoneInfo(timezone))
    return now.strftime(f"%A %d %B %Y, %H:%M in {timezone}")


def load_notes():
    """[10.3] Read the saved notes, or an empty list if there are none yet."""
    if NOTES_FILE.exists():
        return json.loads(NOTES_FILE.read_text(encoding="utf-8"))
    return []


def save_note(text):
    """[10.3] Add one note to the file."""
    notes = load_notes()
    notes.append(text)
    NOTES_FILE.write_text(json.dumps(notes, indent=2), encoding="utf-8")
    return f"Saved. There are now {len(notes)} notes."


def list_notes():
    """[10.3] Return every note, one per line, numbered."""
    notes = load_notes()
    if not notes:
        return "There are no notes yet."
    lines = []
    for number, note in enumerate(notes, start=1):
        lines.append(f"{number}. {note}")
    return "\n".join(lines)


# [10.3] Tool name -> the function that runs it.
HANDLERS = {
    "get_current_time": get_current_time,
    "save_note": save_note,
    "list_notes": list_notes,
}


def handle(message):
    """[10.4] Work out the response to one message, or None for a notification.

    How it works: the method name decides what to do. A failing tool is not
    a protocol error: its message goes back as the tool's result, marked
    with isError, so the model can read it.
    """
    method = message.get("method")
    if "id" not in message:
        return None

    if method == "initialize":
        version = message.get("params", {}).get("protocolVersion", "2025-06-18")
        result = {
            "protocolVersion": version,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = message.get("params", {})
        handler = HANDLERS.get(params.get("name"))
        try:
            if handler is None:
                raise ValueError(f"unknown tool {params.get('name')}")
            text = handler(**params.get("arguments", {}))
            result = {"content": [{"type": "text", "text": text}], "isError": False}
        except Exception as error:
            result = {
                "content": [{"type": "text", "text": str(error)}],
                "isError": True,
            }
    else:
        error = {"code": -32601, "message": f"Method not found: {method}"}
        return {"jsonrpc": "2.0", "id": message["id"], "error": error}

    return {"jsonrpc": "2.0", "id": message["id"], "result": result}


def main():
    """[10.5] Answer messages, one line at a time, until the client goes away.

    How it works: the pipes are switched to UTF-8 so any language survives
    the trip. Looping over sys.stdin ends when the client closes it. A line
    that is not JSON is skipped rather than crashing the server.
    """
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except ValueError:
            continue
        response = handle(message)
        if response is not None:
            print(json.dumps(response), flush=True)


# [10.6] Start the server only when this file is run directly.
if __name__ == "__main__":
    main()
