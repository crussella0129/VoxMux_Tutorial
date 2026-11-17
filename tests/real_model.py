"""real_model.py: drive a finished VoxMux window with a real model.

    python tests/real_model.py FOLDER KIND MODEL_PATH

FOLDER is a level 3 or level 4 build (answer_key_level4, or a copy of the
app), KIND is llama_cpp or pytorch, and MODEL_PATH is a .gguf file or a model
folder. This needs the graphics card and takes a few minutes, so it is run
by hand and not by "python -m unittest" or by GitHub.

It works on a copy of FOLDER in a temporary folder, so the notes, settings
and chats it writes do not touch your files. It prints what the model said
at each step. There are two kinds of check. Things that do not depend on
what the model chooses to say are marked "ok" or "FAIL", and the script
stops at the first FAIL. Things that need the model to cooperate, such as
calling a tool when asked to, are marked "ok" or "MOOD" and never stop the
script. Whether the model's answers are any good is for you to read.

A model whose chat template has no place for tools is noticed by a level 4
build, and the tool steps are then skipped.
"""

import json
import pathlib
import shutil
import sys
import tempfile
import time
import tkinter as tk

# Models write all sorts of characters; a Windows terminal cannot show them all.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
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
level4 = hasattr(window, "save_chat")
statuses = []
asked = []
moods = []


def check(condition, what):
    print(f"    {'ok  ' if condition else 'FAIL'}  {what}")
    if not condition:
        raise SystemExit(1)


def mood(condition, what):
    print(f"    {'ok  ' if condition else 'MOOD'}  {what}")
    if not condition:
        moods.append(what)


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


def status():
    return window.status.cget("text")


def wait(answer="Deny", timeout=900):
    """Keep the window alive until the work is over. Answer any tool question.

    Some models call a tool when nobody asked them to. A question that no
    step expected is therefore answered with Deny, not treated as a fault.
    """
    start = time.time()
    while window.busy:
        root.update()
        text = status()
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


def ask(text, label, answer="Deny", stop_after=None):
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
    if status().startswith("Error"):
        check(False, f"the reply arrived without an error ({status()})")
    return shown


def load():
    window.backend_kind.set(kind)
    window.model_path = model_path
    window.load_button.invoke()
    print(f"[load] {wait():.1f}s  {status()!r}")
    check(window.backend is not None and "Ready:" in status(), "a model is loaded")


load()
check("5 tools)" in status(), "two built-in tools and three from the demo server")
has_tools = getattr(window, "offer_tools", True)
if not has_tools:
    check(
        status().endswith("This model's template has no place for tools."),
        "the status line says the template has no place for tools",
    )
window.temperature.set(0.2)
window.system_box.insert("1.0", "You are a helpful assistant. Keep answers short.")

# Tools are off for this step, so that the reply is certain to be a story.
window.use_tools.set(False)
shown = ask("Write a 300 word story about a lighthouse.", "stop", stop_after=120)
window.use_tools.set(True)
check(shown.endswith("[stopped]"), "the log marks the reply as stopped")
check("Stopping..." in statuses, 'the status line said "Stopping..."')
check(len(window.messages[-1]["content"]) < 1200, "the reply was cut short")
check(str(window.stop_button.cget("state")) == "disabled", "Stop is greyed out again")

shown = ask("Reply with just the word: hello", "after a stop")
check(
    "[stopped]" not in shown and window.messages[-1]["content"],
    "the next reply is whole",
)

first_chat = None
if level4:
    files = sorted((work / "chats").glob("*.json"))
    check(len(files) == 1, "the conversation is in one file in the chats folder")
    first_chat = files[0]
    saved = json.loads(first_chat.read_text(encoding="utf-8"))
    check(saved["messages"] == window.messages, "the file holds the messages")
    check(saved["log"] == log(), "the file holds the log")
    first_log = log()

window.new_chat_button.invoke()
check(
    log() == "" and window.messages == [],
    "New chat cleared the log and the conversation",
)

if has_tools:
    asked.clear()
    shown = ask("What is 1234 * 5678? Use the calculator.", "built-in tool")
    mood("-> 7006652]" in shown, "the calculator ran and gave 7006652")
    check(
        not any("calculate" in question for question in asked),
        "no question was asked about a built-in tool",
    )

    asked.clear()
    shown = ask(
        "Save a note that says: buy oat milk.", "MCP tool, denied", answer="Deny"
    )
    mood(len(asked) >= 1 and "save_note" in asked[0], "the app asked about save_note")
    if asked:
        check(app.DENIED in shown, "the model was told the call was refused")
    check(not (work / "notes.json").exists(), "nothing was saved")

    asked.clear()
    shown = ask(
        "Save a note that says: buy oat milk.",
        "MCP tool, always allowed",
        answer="Always allow",
    )
    mood(len(asked) == 1, "the app asked once")
    if asked:
        check("save_note" in window.allowed_tools, "save_note is now always allowed")
        check((work / "notes.json").exists(), "the note was saved")

    asked.clear()
    shown = ask(
        "Save another note that says: call Dana.",
        "MCP tool, no question",
        answer="Deny",
    )
    if "save_note" in window.allowed_tools:
        check(not asked, "no question this time")
    notes = []
    if (work / "notes.json").exists():
        notes = json.loads((work / "notes.json").read_text(encoding="utf-8"))
    mood(len(notes) >= 2, "the second note was saved")

    window.use_tools.set(False)
    shown = ask("Say hello in five words.", "tools off")
    check(
        window.messages[-1]["role"] == "assistant" and "-> " not in shown,
        "a plain answer with no tool",
    )
    window.use_tools.set(True)
else:
    print("[tools] skipped: this model's template has no place for tools")
    shown = ask("What is 12 * 12? Answer with just the number.", "no tools")
    check(
        [message["role"] for message in window.messages] == ["user", "assistant"],
        "a plain answer, with nothing run",
    )

if level4:
    window.read_chat(str(first_chat))
    root.update()
    check(log() == first_log, "opening the first chat brought its log back")
    check(window.chat_file == first_chat, "later replies will go to that file")
    load()
    check(log() == first_log, "loading a model kept the conversation")
    shown = ask("What did I ask you to write a story about?", "after reopening")
    mood("lighthouse" in shown.lower(), "the model still knows the story's subject")

# Compaction: shrink the context so that the older half must be summarised.
# Tools are off, because a round of tool calls in so small a context can
# push the summary itself out, which is allowed but cannot be checked.
window.new_chat_button.invoke()
window.temperature.set(0.0)
window.use_tools.set(False)
one_message = window.backend.build_prompt(
    [{"role": "user", "content": "hi"}], False, None
)
base = window.backend.count_tokens(one_message)
full_size = window.backend.context_size
window.backend.context_size = 2 * (base + 600)  # half is kept for the reply
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
facts = facts + [f"To say it once more: {fact}" for fact in facts]
summarised = False
for number, fact in enumerate(facts, start=1):
    ask(f"{fact} Reply with just: noted.", f"fact {number}")
    summarised = summarised or any(s.startswith("Summarising") for s in statuses)
check(summarised, 'the status line said "Summarising older messages..."')
# A summary that comes out longer than what it replaced is dropped again when
# room is next needed, so whether one is still there depends on the model.
mood(
    window.messages[0]["content"].startswith("Summary of our conversation so far:"),
    "the conversation starts with a summary",
)
print("    first message:", repr(window.messages[0]["content"][:500]))
shown = ask("What is my cat called? Answer in a few words.", "recall")
mood("miso" in shown.lower(), "the model still knows the cat's name")
window.backend.context_size = full_size
window.use_tools.set(True)
last_log = log()
last_messages = list(window.messages)

window.close()
saved = json.loads((work / "settings.json").read_text(encoding="utf-8"))
check(
    saved["model_path"] == model_path and saved["backend_kind"] == kind,
    "the model path and backend were saved",
)
check(
    saved["system_prompt"] == "You are a helpful assistant. Keep answers short.",
    "the system prompt was saved",
)

if level4:
    root = tk.Tk()
    window = app.ChatApp(root)
    root.update()
    check(log() == last_log, "the next start brought the last conversation back")
    check(window.messages == last_messages, "and its messages")
    check(facts[0] in last_log, "the log still shows the first fact word for word")
    window.close()

shutil.rmtree(work, ignore_errors=True)
print("\nAll mechanical checks passed. Read the answers above to judge the model.")
if moods:
    print("These depended on the model, and it did not go along:")
    for what in moods:
        print("  -", what)
