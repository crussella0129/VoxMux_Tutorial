"""[4.1] app.py: the VoxMux window, a tiny desktop chat for local models.
(Level 3 version.)

How it works: one class, ChatApp, builds the window and holds the state
(which model is loaded, the conversation so far, the thinking-mode
instructions, the tools). Loading a model and generating a reply are slow,
so they run on a second thread and report back through a queue. A reply is
reported a few characters at a time, which is what makes it appear word by
word. The main thread checks that queue twenty times a second and is the
only thread that ever touches the window.

Level 2 adds tool calling. When the model answers with a tool call instead
of text, the worker runs the tool, adds the result to the conversation and
asks the model again, until it gives a plain answer.

Level 3 adds the finishing touches. A Stop button cuts a reply short, and a
New chat button starts a fresh conversation. The settings are saved in
settings.json when the window closes and read back the next time. A tool
that comes from an MCP server only runs after the user has allowed it.

Run it with:  python app.py

The numbers in square brackets match the step numbers in RECIPE.md (4.x),
RECIPE_LEVEL2.md (12.x) and RECIPE_LEVEL3.md (16.x).
"""

import json
import pathlib
import queue
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext

from backends import load_backend
from mcp_client import start_servers
from tools import Toolbox, parse_tool_calls

# [4.1] Constants: timing and the starting values of the settings.
POLL_INTERVAL_MS = 50  # how often the main thread checks the queue
DEFAULT_TEMPERATURE = 0.7  # 0 is predictable, 2 is very random
DEFAULT_THINKING_INSTRUCTIONS = (
    "Think through the question step by step before you answer."
)

# [12.1] Constants: where the MCP server list lives (next to this file), and
# how many rounds of tool calls one reply may take.
MCP_CONFIG = pathlib.Path(__file__).with_name("mcp_servers.json")
MAX_TOOL_ROUNDS = 5

# [16.1] Constants: where the settings are kept between runs (next to this
# file), and what the model is told when the user refuses a tool.
SETTINGS_FILE = pathlib.Path(__file__).with_name("settings.json")
DENIED = "Error: the user did not allow this tool call."


class ChatApp:
    """[4.2] The whole window: its widgets, its state, and its behaviour.

    How it works: apart from setup (__init__, build_widgets) and the small
    helpers (start_worker, stream_reply, may_run, append_chat, set_busy,
    load_settings, save_settings, close), the methods fall into three
    groups. Button handlers (browse, open_thinking_window,
    save_thinking_instructions, load_model, new_chat, send, stop,
    answer_tool) run on the main thread when the user does something.
    Workers (load_worker, reply_worker) run on a second thread and do the
    slow part. poll_results runs on the main thread on a timer and carries
    the workers' results back into the window; open_approval_window is the
    one result that needs a window of its own.
    """

    def __init__(self, root):
        """[16.2] (level 2: [12.2]) Set up the window, state, and queue check.

        How it works: root is the main window object made in main(). Every
        attribute the other methods rely on exists by the time this method
        finishes: the state is created here, and the widgets are created in
        build_widgets, which this calls. protocol("WM_DELETE_WINDOW", ...)
        sets what happens when the window's X button is clicked: close()
        saves the settings and stops the MCP servers before the window goes.
        The saved settings are read back after the widgets are built,
        because most of them are written into widgets.
        """
        self.root = root
        self.root.title("VoxMux")
        self.root.geometry("800x600")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.backend = None  # the loaded model, once there is one
        self.model_path = ""  # what the user picked with Browse
        self.messages = []  # the whole conversation so far
        self.busy = False  # True while a worker thread is running
        self.results = queue.Queue()  # how worker threads report back
        self.thinking_instructions = DEFAULT_THINKING_INSTRUCTIONS
        self.toolbox = None  # the tools, once the first model is loaded
        self.stop_requested = threading.Event()  # raised by the Stop button
        self.answers = queue.Queue()  # the user's answers about tools
        self.allowed_tools = []  # MCP tools the user chose "Always allow" for

        self.build_widgets()
        self.load_settings()
        self.poll_results()

    def build_widgets(self):
        """[4.4] Create every widget and place it in the window.

        How it works: each widget is created with its parent as the first
        argument, then placed with .pack(). tkinter hands out space in the
        order widgets are packed, so the order of the six blocks below is
        the layout.
        """
        # [16.3] (level 1: [4.4.1]) Top row: pick a backend, pick a model,
        # load it, or start a new chat.
        top = tk.Frame(self.root)
        top.pack(fill="x", padx=8, pady=8)

        # Both radio buttons share this one variable. Selecting a button
        # writes that button's value into it.
        self.backend_kind = tk.StringVar(value="llama_cpp")
        tk.Radiobutton(
            top,
            text="llama.cpp (GGUF)",
            variable=self.backend_kind,
            value="llama_cpp",
        ).pack(side="left")
        tk.Radiobutton(
            top,
            text="PyTorch (safetensors)",
            variable=self.backend_kind,
            value="pytorch",
        ).pack(side="left")

        tk.Button(top, text="Browse...", command=self.browse).pack(side="left", padx=8)
        self.load_button = tk.Button(top, text="Load", command=self.load_model)
        self.load_button.pack(side="left")
        self.new_chat_button = tk.Button(top, text="New chat", command=self.new_chat)
        self.new_chat_button.pack(side="right")

        # [12.3] (level 1: [4.4.2]) Settings row: temperature, thinking, tools.
        settings = tk.Frame(self.root)
        settings.pack(fill="x", padx=8)

        tk.Label(settings, text="Temperature").pack(side="left")
        self.temperature = tk.DoubleVar(value=DEFAULT_TEMPERATURE)
        tk.Scale(
            settings,
            variable=self.temperature,
            from_=0,
            to=2,
            resolution=0.1,
            orient="horizontal",
            length=160,
        ).pack(side="left", padx=(4, 16))

        self.thinking = tk.BooleanVar(value=False)
        tk.Checkbutton(settings, text="Thinking mode", variable=self.thinking).pack(
            side="left"
        )
        tk.Button(
            settings,
            text="Thinking instructions...",
            command=self.open_thinking_window,
        ).pack(side="left", padx=8)

        self.use_tools = tk.BooleanVar(value=True)
        tk.Checkbutton(settings, text="Use tools", variable=self.use_tools).pack(
            side="left", padx=(8, 0)
        )

        # [4.4.3] System prompt: standing instructions sent with every message.
        tk.Label(self.root, text="System prompt:", anchor="w").pack(
            fill="x", padx=8, pady=(8, 0)
        )
        self.system_box = tk.Text(self.root, height=3, wrap="word")
        self.system_box.pack(fill="x", padx=8)

        # [4.4.4] Status line: one row of text that says what is going on.
        self.status = tk.Label(self.root, text="No model loaded.", anchor="w")
        self.status.pack(fill="x", padx=8, pady=(8, 0))

        # [16.4] (level 1: [4.4.5]) Bottom row: type a message, send it, or
        # stop the reply. Packed before the chat log so it keeps its place at
        # the bottom when the window is resized.
        bottom = tk.Frame(self.root)
        bottom.pack(side="bottom", fill="x", padx=8, pady=8)

        self.entry = tk.Entry(bottom)
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", self.send)  # pressing Enter sends too

        self.send_button = tk.Button(bottom, text="Send", command=self.send)
        self.send_button.pack(side="left", padx=(8, 0))
        self.stop_button = tk.Button(
            bottom, text="Stop", command=self.stop, state="disabled"
        )
        self.stop_button.pack(side="left", padx=(8, 0))

        # [4.4.6] Chat log: read-only, and fills whatever space is left.
        self.chat_log = scrolledtext.ScrolledText(
            self.root, wrap="word", state="disabled"
        )
        self.chat_log.pack(fill="both", expand=True, padx=8, pady=8)

    def browse(self):
        """[4.5] Browse button: let the user pick a model, remember the path.

        How it works: a GGUF model is one file and a safetensors model is a
        whole folder, so the selected radio button decides which kind of
        picker opens. Both pickers give back something empty on Cancel.
        """
        if self.backend_kind.get() == "llama_cpp":
            path = filedialog.askopenfilename(filetypes=[("GGUF model", "*.gguf")])
        else:
            path = filedialog.askdirectory()

        if path:
            self.model_path = path
            self.status.config(text=f"Selected: {path}")

    def open_thinking_window(self):
        """[4.6] Thinking instructions button: open a small editing window.

        How it works: a Toplevel is a second window that belongs to the main
        one. It holds a text box filled with the current instructions and a
        Save button. The button needs to tell save_thinking_instructions
        which window and which box to use, so its command is a lambda: a
        tiny function, written in place, that makes that call when clicked.
        """
        window = tk.Toplevel(self.root)
        window.title("Thinking mode instructions")

        tk.Label(
            window,
            text="Added to the system prompt whenever Thinking mode is on:",
            anchor="w",
        ).pack(fill="x", padx=8, pady=(8, 0))
        box = tk.Text(window, width=60, height=8, wrap="word")
        box.pack(fill="both", expand=True, padx=8, pady=8)
        box.insert("1.0", self.thinking_instructions)

        tk.Button(
            window,
            text="Save",
            command=lambda: self.save_thinking_instructions(window, box),
        ).pack(pady=(0, 8))

    def save_thinking_instructions(self, window, box):
        """[4.7] Save button: keep the edited instructions, close the window.

        How it works: a Text widget's contents run from "1.0" (line 1,
        character 0) to "end". Tk always adds a newline at the end, so the
        text is stripped before it is kept.
        """
        self.thinking_instructions = box.get("1.0", "end").strip()
        window.destroy()

    def load_model(self):
        """[4.8] Load button: start loading the picked model in the background.

        How it works: this method only starts the work. It greys out the
        buttons, updates the status, hands load_worker to a new thread, and
        returns at once so the window stays responsive.
        """
        if not self.model_path:
            self.status.config(text="Pick a model with Browse first.")
            return

        self.set_busy(True)
        self.status.config(text="Loading model...")
        self.start_worker(self.load_worker, self.backend_kind.get(), self.model_path)

    def new_chat(self):
        """[16.5] New chat button: forget the conversation and clear the log.

        How it works: the model only knows what is in self.messages, so an
        empty list is a fresh start. The log is read-only, so it is unlocked,
        emptied from its first character ("1.0") to its end, and locked
        again. The button is greyed out while a worker is running, so this
        never pulls the conversation out from under a reply.
        """
        self.messages = []
        self.chat_log.config(state="normal")
        self.chat_log.delete("1.0", "end")
        self.chat_log.config(state="disabled")

    def send(self, event=None):
        """[16.6] (level 2: [12.4]) Send button or Enter: add the message, ask.

        How it works: the button calls this with no arguments and the Enter
        key calls it with one (an event object), so event defaults to None
        and is never used. Every setting is read from its widget here, on
        the main thread, and handed to the worker as plain values, because
        only the main thread may touch widgets. The user's message joins
        self.messages and the chat log straight away, followed by the label
        "Model: " with nothing after it yet. The stop flag is lowered, in
        case it is still up from the last reply, and the Stop button is
        brought to life for this one.
        """
        text = self.entry.get().strip()
        if not text or self.backend is None or self.busy:
            return

        system_prompt = self.system_box.get("1.0", "end").strip()
        temperature = self.temperature.get()
        thinking = self.thinking.get()
        use_tools = self.use_tools.get()
        if thinking and self.thinking_instructions:
            system_prompt = system_prompt + "\n\n" + self.thinking_instructions
            system_prompt = system_prompt.strip()

        self.entry.delete(0, "end")
        self.messages.append({"role": "user", "content": text})
        self.append_chat(f"You: {text}\n\nModel: ")

        self.set_busy(True)
        self.stop_requested.clear()
        self.stop_button.config(state="normal")
        self.status.config(text="Writing a reply...")
        self.start_worker(
            self.reply_worker, system_prompt, temperature, thinking, use_tools
        )

    def stop(self):
        """[16.7] Stop button: ask the worker to cut the reply short.

        How it works: a worker thread cannot be stopped from outside; it has
        to stop itself. So this only raises a flag. A threading.Event is a
        flag that is safe to share between threads: set() raises it,
        clear() lowers it and is_set() reads it. stream_reply reads it
        before it uses each piece of the reply. The button greys itself out
        so it cannot be clicked twice.
        """
        self.stop_requested.set()
        self.stop_button.config(state="disabled")
        self.status.config(text="Stopping...")

    def start_worker(self, target, *args):
        """[4.10] Run target(*args) on a new background thread.

        How it works: slow work on the main thread would freeze the window,
        so it gets a thread of its own. daemon=True means the thread is
        dropped when the window closes instead of keeping the program alive.
        """
        thread = threading.Thread(target=target, args=args, daemon=True)
        thread.start()

    def load_worker(self, kind, model_path):
        """[12.5] (level 1: [4.11]) Background thread: load a model and tools.

        How it works: worker threads must not touch widgets, so this method
        reports by putting a (label, value) pair in the queue. The first
        time a model loads, the MCP servers are started too and gathered,
        with the built-in tools, into a Toolbox; later loads reuse it. All
        three results travel together as one tuple. Any error is caught and
        reported the same way; otherwise the window would never hear about
        it and would stay busy for good.
        """
        try:
            backend = load_backend(kind, model_path)
            toolbox = self.toolbox
            problems = []
            if toolbox is None:
                servers, problems = start_servers(MCP_CONFIG)
                toolbox = Toolbox(servers)
            self.results.put(("loaded", (backend, toolbox, problems)))
        except Exception as error:
            self.results.put(("error", str(error)))

    def reply_worker(self, system_prompt, temperature, thinking, use_tools):
        """[16.8] (level 2: [12.6]) Background thread: reply, using tools.

        How it works: each round streams one reply. If it contains no tool
        call, that is the answer and the work is done. Otherwise the reply
        and its calls are added to the conversation as an assistant message,
        each tool is run, its result is shown in the log and added as a
        "tool" message, and the model is asked again with those results in
        front of it. MAX_TOOL_ROUNDS stops a model that never stops calling;
        the note saying so is sent as a piece too, so it shows in the log.
        With Use tools off, no tools are offered, and a call the model writes
        anyway is not run. A reply the user stopped ends the work the same
        way a plain answer does: what had arrived is kept, marked in the log
        with [stopped], and no tool is run. A tool the user refuses is not
        run either; the model is told so in place of a result.
        """
        try:
            tools = None
            if use_tools:
                tools = self.toolbox.schemas
            for round_number in range(MAX_TOOL_ROUNDS):
                answer = self.stream_reply(system_prompt, temperature, thinking, tools)
                text, calls = parse_tool_calls(answer)
                stopped = self.stop_requested.is_set()
                if stopped or not calls or not use_tools:
                    # No call to run (or the reply was stopped, or tools are
                    # off, so a call is never run). Only the text before any
                    # <tool_call> is kept, as it is all the log showed.
                    if stopped:
                        self.results.put(("piece", " [stopped]"))
                    self.results.put(("reply", text))
                    return

                tool_calls = []
                for call in calls:
                    tool_calls.append({"type": "function", "function": call})
                self.messages.append(
                    {"role": "assistant", "content": text, "tool_calls": tool_calls}
                )
                for call in calls:
                    if self.may_run(call):
                        self.results.put(("status", f"Running tool {call['name']}..."))
                        result = self.toolbox.run(call["name"], call["arguments"])
                    else:
                        result = DENIED
                    self.results.put(
                        (
                            "piece",
                            f"\n[{call['name']} {call['arguments']} -> {result}]\n",
                        )
                    )
                    self.messages.append(
                        {"role": "tool", "name": call["name"], "content": result}
                    )
                self.results.put(("status", "Writing a reply..."))
            note = "(Stopped: too many tool calls in a row.)"
            self.results.put(("piece", note))
            self.results.put(("reply", note))
        except Exception as error:
            self.results.put(("error", str(error)))

    def stream_reply(self, system_prompt, temperature, thinking, tools):
        """[16.9] (level 2: [12.7]) Stream one reply into the queue.

        How it works: this is level 1's streaming loop, moved into its own
        method because a reply that uses tools needs several rounds of it.
        Anything from <tool_call> onwards is kept out of the log, since it
        is meant for the app, not the reader. It returns the reply with any
        thinking removed, ready for parse_tool_calls. The stop flag is read
        before each piece is used. After the loop, close() ends the
        generator if the loop was left early, which is what tells the
        backend that nobody is listening. Python would end it by itself
        once nothing refers to it any more, but close() does it here and
        now, where the reader can see it.
        """
        reply = ""  # everything the model has written this round
        shown = ""  # the part already sent to the window
        pieces = self.backend.chat(
            self.messages, system_prompt, temperature, thinking, tools
        )
        for piece in pieces:
            if self.stop_requested.is_set():
                break
            reply = reply + piece
            visible = reply.split("<tool_call>")[0]
            visible = visible.replace("</think>", "\n[end of thinking]").strip()
            start = len(shown)  # where the not-yet-shown part begins
            new_text = visible[start:]
            if new_text:
                self.results.put(("piece", new_text))
                shown = visible
        pieces.close()
        return reply.split("</think>")[-1].strip()

    def may_run(self, call):
        """[16.10] Background thread: is this tool call allowed to run?

        How it works: a built-in tool is a function in tools.py that you can
        read, so it always runs. A tool from an MCP server is another
        program, which may do anything that you can, so the user is asked
        first, unless they already chose "Always allow" for it. Asking means
        showing a window, and only the main thread may do that. So the
        worker puts a status message and an "ask" in the results queue and
        then waits on a second queue, self.answers, for the main thread to
        put the user's choice in it: get() on an empty queue waits until
        something arrives. A tool nobody owns is let through, because
        Toolbox.run answers that with an error the model can read.
        """
        name = call["name"]
        owner = self.toolbox.owners.get(name)
        if owner is None or callable(owner) or name in self.allowed_tools:
            return True
        self.results.put(("status", f"Waiting for your answer about {name}..."))
        self.results.put(("ask", call))
        return self.answers.get() != "deny"

    def poll_results(self):
        """[16.11] (level 2: [12.8]) Main thread, on a timer: apply results.

        How it works: empty the queue, updating the window for each result,
        then ask tkinter to call this same method again in POLL_INTERVAL_MS
        milliseconds. A "piece" means more is coming, so the buttons stay
        greyed out; so does a "status", which only changes the status line,
        and an "ask", which opens the window that asks about a tool. The
        other three results mean the work is over. When a model loads, the
        old conversation is cleared from the log as well as from memory, and
        the model is given a function to call when compaction starts: a
        lambda that puts a status message in the queue, since compaction
        happens on the worker thread.
        """
        while not self.results.empty():
            kind, value = self.results.get()

            if kind == "piece":
                self.append_chat(value)
            elif kind == "status":
                self.status.config(text=value)
            elif kind == "ask":
                self.open_approval_window(value)
            elif kind == "reply":
                self.messages.append({"role": "assistant", "content": value})
                self.append_chat("\n\n")  # blank line before the next message
                self.status.config(text=f"Ready: {self.model_path}")
                self.set_busy(False)
            elif kind == "loaded":
                backend, toolbox, problems = value
                self.backend = backend
                self.toolbox = toolbox
                self.new_chat()  # a new model starts a new conversation
                backend.on_compact = lambda: self.results.put(
                    ("status", "Summarising older messages to make room...")
                )
                text = (
                    f"Ready: {self.model_path} ({backend.context_size} tokens of "
                    f"context, {len(toolbox.schemas)} tools)"
                )
                if problems:
                    text = text + " MCP problems: " + "; ".join(problems)
                self.status.config(text=text)
                self.set_busy(False)
            elif kind == "error":
                self.status.config(text=f"Error: {value}")
                self.set_busy(False)

        self.root.after(POLL_INTERVAL_MS, self.poll_results)

    def open_approval_window(self, call):
        """[16.12] Main thread: ask whether one MCP tool call may run.

        How it works: a small window shows the tool's name and arguments
        above three buttons. Each button's command is a lambda, because it
        must hand answer_tool the window, the tool's name and its own
        answer. Closing the window with its X button counts as Deny;
        otherwise the worker would wait for an answer for ever.
        """
        name = call["name"]
        window = tk.Toplevel(self.root)
        window.title("Allow this tool?")
        window.protocol(
            "WM_DELETE_WINDOW", lambda: self.answer_tool(window, name, "deny")
        )

        tk.Label(
            window,
            text=f"The model wants to run {name} with:\n{call['arguments']}",
            justify="left",
            wraplength=420,
        ).pack(padx=8, pady=8)

        buttons = tk.Frame(window)
        buttons.pack(padx=8, pady=(0, 8))
        tk.Button(
            buttons,
            text="Allow once",
            command=lambda: self.answer_tool(window, name, "once"),
        ).pack(side="left")
        tk.Button(
            buttons,
            text="Always allow",
            command=lambda: self.answer_tool(window, name, "always"),
        ).pack(side="left", padx=8)
        tk.Button(
            buttons,
            text="Deny",
            command=lambda: self.answer_tool(window, name, "deny"),
        ).pack(side="left")

    def answer_tool(self, window, name, answer):
        """[16.13] A button in the approval window: pass the answer on.

        How it works: answer is "once", "always" or "deny". "Always allow"
        adds the tool's name to self.allowed_tools, which is saved with the
        settings, so the question is not asked again. Putting the answer in
        self.answers is what wakes the worker waiting in may_run.
        """
        if answer == "always":
            self.allowed_tools.append(name)
        self.answers.put(answer)
        window.destroy()

    def append_chat(self, text):
        """[4.14] Add text to the end of the chat log, exactly as given.

        How it works: the log is kept read-only so the user cannot type into
        the history. That also blocks the program, so it is unlocked, written
        to, locked again, and then scrolled to the bottom. The caller decides
        on labels and line breaks, so the same method serves a whole message
        and a single streamed word.
        """
        self.chat_log.config(state="normal")
        self.chat_log.insert("end", text)
        self.chat_log.config(state="disabled")
        self.chat_log.see("end")

    def set_busy(self, busy):
        """[16.14] (level 1: [4.15]) Grey out the buttons while work is running.

        How it works: busy is True or False. It is saved on self.busy so
        send() can check it, and it is turned into the "disabled" or "normal"
        state string that tkinter buttons understand. Load, Send and New
        chat follow it. Stop is the odd one out: it is only useful while a
        reply is being written, so send() brings it to life and this method
        only ever greys it out, when the work is over.
        """
        self.busy = busy
        if busy:
            state = "disabled"
        else:
            state = "normal"
        self.load_button.config(state=state)
        self.send_button.config(state=state)
        self.new_chat_button.config(state=state)
        if not busy:
            self.stop_button.config(state="disabled")

    def load_settings(self):
        """[16.15] Read settings.json, if there is one, back into the window.

        How it works: the file holds one JSON object, written by
        save_settings. Each value goes back where it came from: into a
        tkinter variable with set(), into the system prompt box with
        insert(), or onto self. The first run has no file. A file that
        cannot be read, is not JSON, or is missing a key is not worth
        crashing over: the settings read before the problem are kept and
        the rest stay at their starting values.
        """
        if not SETTINGS_FILE.exists():
            return
        try:
            saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            self.backend_kind.set(saved["backend_kind"])
            self.model_path = saved["model_path"]
            self.temperature.set(saved["temperature"])
            self.thinking.set(saved["thinking"])
            self.thinking_instructions = saved["thinking_instructions"]
            self.use_tools.set(saved["use_tools"])
            self.system_box.insert("1.0", saved["system_prompt"])
            self.allowed_tools = saved["allowed_tools"]
        except (OSError, ValueError, KeyError, TypeError):
            pass
        if self.model_path:
            self.status.config(text=f"Selected: {self.model_path}")

    def save_settings(self):
        """[16.16] Write the current settings to settings.json.

        How it works: every setting is gathered into one dictionary, with
        the same keys load_settings reads, and json.dumps turns it into
        text. indent=2 spreads it over several lines so a person can read
        it.
        """
        saved = {
            "backend_kind": self.backend_kind.get(),
            "model_path": self.model_path,
            "temperature": self.temperature.get(),
            "thinking": self.thinking.get(),
            "thinking_instructions": self.thinking_instructions,
            "use_tools": self.use_tools.get(),
            "system_prompt": self.system_box.get("1.0", "end").strip(),
            "allowed_tools": self.allowed_tools,
        }
        SETTINGS_FILE.write_text(json.dumps(saved, indent=2), encoding="utf-8")

    def close(self):
        """[16.17] (level 2: [12.9]) Window closed: save, stop servers, close.

        How it works: the settings are saved first. If the file cannot be
        written, for example because the folder is read-only, the error is
        swallowed: losing the settings is better than a window that will
        not close.
        """
        try:
            self.save_settings()
        except OSError:
            pass
        if self.toolbox is not None:
            for server in self.toolbox.servers:
                server.close()
        self.root.destroy()


def main():
    """[4.16] Create the window, attach the app to it, and run until closed.

    How it works: mainloop() is tkinter's event loop. It waits for clicks,
    keypresses and timers, calls the matching method for each, and does not
    return until the window is closed.
    """
    root = tk.Tk()
    ChatApp(root)
    root.mainloop()


# [4.17] Start the app only when this file is run directly (python app.py),
# not when another file imports it.
if __name__ == "__main__":
    main()
