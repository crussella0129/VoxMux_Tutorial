"""real_model.py: drive a finished VoxMux window with a real model.

    python tests/real_model.py FOLDER KIND MODEL_PATH

FOLDER is a level 3 build (answer_key_level3, or a copy of the app), KIND is
llama_cpp or pytorch, and MODEL_PATH is a .gguf file or a model folder. This
needs the graphics card and takes a few minutes, so it is run by hand and
not by "python -m unittest" or by GitHub.

It works on a copy of FOLDER in a temporary folder, so the notes and
settings it writes do not touch your files. It prints what the model said at
each step. Things that do not depend on the model's mood are checked, and
the script stops at the first one that is wrong. Whether the model's answers
are any good is for you to read.
"""

import json
import pathlib
import shutil
import sys
import tempfile
import time
import tkinter as tk

folder, kind, model_path = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
work = pathlib.Path(tempfile.mkdtemp(prefix="voxmux-real-"))
for path in folder.iterdir():
    if path.suffix in (".py", ".json") and path.name not in (
        "settings.json",
        "notes.json",
    ):
        shutil.copy(path, work)
sys.path.insert(0, str(work))
import app  # noqa: E402

root = tk.Tk()
window = app.ChatApp(root)
statuses = []
asked = []


def check(condition, what):
    print(f"    {'ok  ' if condition else 'FAIL'}  {what}")
    if not condition:
        raise SystemExit(1)


def approvals():
    return [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]


def click(widget, label):
    stack = [widget]
    while stack:
        item = stack.pop()
        if isinstance(item, tk.Button) and item.cget("text") == label:
            item.invoke()
            return
        stack.extend(item.winfo_children())
    raise SystemExit(f"no button labelled {label}")


def wait(answer=None, timeout=900):
    """Keep the window alive until the work is over. Answer any tool question."""
    start = time.time()
    while window.busy:
        root.update()
        text = window.status.cget("text")
        if not statuses or statuses[-1] != text:
            statuses.append(text)
        for question in approvals():
            asked.append(question.winfo_children()[0].cget("text"))
            click(question, answer)
        time.sleep(0.01)
        if time.time() - start > timeout:
            raise SystemExit("TIMEOUT")
    root.update()
    return time.time() - start


def log():
    return window.chat_log.get("1.0", "end-1c")


def ask(text, label, answer=None, stop_after=None):
    """Send text. With stop_after, click Stop once that many characters arrive."""
    statuses.clear()
    before = len(log())
    window.entry.insert(0, text)
    window.send_button.invoke()
    root.update()
    if stop_after is not None:
        marker = before + len(f"You: {text}\n\nModel: ") + stop_after
        while window.busy and len(log()) < marker:
            root.update()
            time.sleep(0.01)
        window.stop_button.invoke()
    took = wait(answer)
    shown = log()[before:].strip()
    print(f"[{label}] {took:.1f}s")
    print("    log:", repr(shown[:400]))
    return shown


window.backend_kind.set(kind)
window.model_path = model_path
window.load_button.invoke()
print(f"[load] {wait():.1f}s  {window.status.cget('text')!r}")
check(window.backend is not None, "a model is loaded")
check(
    window.status.cget("text").endswith("5 tools)"),
    "two built-in tools and three from the demo server",
)
window.temperature.set(0.2)

shown = ask("Write a 300 word story about a lighthouse.", "stop", stop_after=120)
check(shown.endswith("[stopped]"), "the log marks the reply as stopped")
check("Stopping..." in statuses, 'the status line said "Stopping..."')
check(len(window.messages[-1]["content"]) < 1200, "the reply was cut short")
check(str(window.stop_button.cget("state")) == "disabled", "Stop is greyed out again")

shown = ask("Reply with just the word: hello", "after a stop")
check(
    "[stopped]" not in shown and window.messages[-1]["content"],
    "the next reply is whole",
)

window.new_chat_button.invoke()
check(
    log() == "" and window.messages == [],
    "New chat cleared the log and the conversation",
)

shown = ask("What is 1234 * 5678? Use the calculator.", "built-in tool")
check("-> 7006652]" in shown, "the calculator ran and gave 7006652")
check(not asked, "no question was asked about a built-in tool")

shown = ask("Save a note that says: buy oat milk.", "MCP tool, denied", answer="Deny")
check(len(asked) >= 1 and "save_note" in asked[0], "the app asked about save_note")
check(app.DENIED in shown, "the model was told the call was refused")
check(not (work / "notes.json").exists(), "nothing was saved")

asked.clear()
shown = ask(
    "Save a note that says: buy oat milk.",
    "MCP tool, always allowed",
    answer="Always allow",
)
check(len(asked) == 1, "the app asked once")
check("save_note" in window.allowed_tools, "save_note is now always allowed")
check((work / "notes.json").exists(), "the note was saved")

asked.clear()
shown = ask(
    "Save another note that says: call Dana.", "MCP tool, no question", answer="Deny"
)
check(not asked, "no question this time")
check(
    len(json.loads((work / "notes.json").read_text(encoding="utf-8"))) >= 2,
    "the second note was saved",
)

window.use_tools.set(False)
shown = ask("Say hello in five words.", "tools off")
check(
    window.messages[-1]["role"] == "assistant" and "[" not in shown,
    "a plain answer with no tool",
)
window.use_tools.set(True)

# Compaction: shrink the context so that the older half must be summarised.
window.new_chat_button.invoke()
window.temperature.set(0.0)
one_message = window.backend.build_prompt(
    [{"role": "user", "content": "hi"}], False, window.toolbox.schemas
)
base = window.backend.count_tokens(one_message)
full_size = window.backend.context_size
window.backend.context_size = 2 * (base + 200)  # half is kept for the reply
facts = [
    "My name is Sam and my cat is called Miso.",
    "I live in a small town near the sea.",
    "My favourite food is ramen.",
    "I am learning Python by building a chat app.",
    "My sister is called Dana.",
    "I play the cello on weekends.",
    "My first car was a green Volvo estate that I drove for eleven years.",
    "My best friend from school now works as a lighthouse keeper in Norway.",
    "I once cycled from London to Paris over four days in the rain.",
    "My grandmother taught me to bake sourdough bread every Sunday morning.",
    "I keep a collection of old maps of the coast where I grew up.",
    "My favourite book is about a sailor who maps islands nobody has visited.",
]
summarised = False
for number, fact in enumerate(facts, start=1):
    ask(f"{fact} Reply with just: noted.", f"fact {number}", answer="Deny")
    summarised = summarised or any(s.startswith("Summarising") for s in statuses)
check(summarised, 'the status line said "Summarising older messages..."')
check(
    window.messages[0]["content"].startswith("Summary of our conversation so far:"),
    "the conversation starts with a summary",
)
print("    summary:", repr(window.messages[0]["content"][:500]))
ask(
    "What is my cat called? Answer in a few words.",
    "recall after compaction",
    answer="Deny",
)
window.backend.context_size = full_size

window.system_box.insert("1.0", "Be brief.")
window.close()
saved = json.loads((work / "settings.json").read_text(encoding="utf-8"))
check(
    saved["model_path"] == model_path and saved["backend_kind"] == kind,
    "the model path and backend were saved",
)
check(
    saved["allowed_tools"] == ["save_note"] and saved["system_prompt"] == "Be brief.",
    "the allowed tool and system prompt were saved",
)
shutil.rmtree(work, ignore_errors=True)
print("\nAll mechanical checks passed. Read the answers above to judge the model.")
