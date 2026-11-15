"""[4.1] app.py: the VoxMux window, a tiny desktop chat for local models.
(Level 2 version.)

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

Run it with:  python app.py

The numbers in square brackets match the step numbers in RECIPE.md (4.x)
and RECIPE_LEVEL2.md (12.x).
"""

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


class ChatApp:
    """[4.2] The whole window: its widgets, its state, and its behaviour.

    How it works: apart from setup (__init__, build_widgets) and the small
    helpers (start_worker, stream_reply, append_chat, set_busy, close), the
    methods fall into three groups. Button handlers (browse,
    open_thinking_window, save_thinking_instructions, load_model, send) run
    on the main thread when the user does something. Workers (load_worker,
    reply_worker) run on a second thread and do the slow part. poll_results
    runs on the main thread on a timer and carries the workers' results back
    into the window.
    """

    def __init__(self, root):
        """[12.2] (level 1: [4.3]) Set up the window, state, and queue check.

        How it works: root is the main window object made in main(). Every
        attribute the other methods rely on exists by the time this method
        finishes: the state is created here, and the widgets are created in
        build_widgets, which this calls. protocol("WM_DELETE_WINDOW", ...)
        sets what happens when the window's X button is clicked: close()
        stops the MCP servers before the window goes.
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

        self.build_widgets()
        self.poll_results()

    def build_widgets(self):
        """[4.4] Create every widget and place it in the window.

        How it works: each widget is created with its parent as the first
        argument, then placed with .pack(). tkinter hands out space in the
        order widgets are packed, so the order of the six blocks below is
        the layout.
        """
        # [4.4.1] Top row: pick a backend, pick a model, load it.
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

        # [4.4.5] Bottom row: type a message, send it. Packed before the chat
        # log so it keeps its place at the bottom when the window is resized.
        bottom = tk.Frame(self.root)
        bottom.pack(side="bottom", fill="x", padx=8, pady=8)

        self.entry = tk.Entry(bottom)
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", self.send)  # pressing Enter sends too

        self.send_button = tk.Button(bottom, text="Send", command=self.send)
        self.send_button.pack(side="left", padx=(8, 0))

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

    def send(self, event=None):
        """[12.4] (level 1: [4.9]) Send button or Enter: add the message, ask.

        How it works: the button calls this with no arguments and the Enter
        key calls it with one (an event object), so event defaults to None
        and is never used. Every setting is read from its widget here, on
        the main thread, and handed to the worker as plain values, because
        only the main thread may touch widgets. The user's message joins
        self.messages and the chat log straight away, followed by the label
        "Model: " with nothing after it yet.
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
        self.status.config(text="Writing a reply...")
        self.start_worker(
            self.reply_worker, system_prompt, temperature, thinking, use_tools
        )

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
        """[12.6] (level 1: [4.12]) Background thread: reply, using tools.

        How it works: each round streams one reply. If it contains no tool
        call, that is the answer and the work is done. Otherwise the reply
        and its calls are added to the conversation as an assistant message,
        each tool is run, its result is shown in the log and added as a
        "tool" message, and the model is asked again with those results in
        front of it. MAX_TOOL_ROUNDS stops a model that never stops calling;
        the note saying so is sent as a piece too, so it shows in the log.
        With Use tools off, no tools are offered, and a call the model writes
        anyway is not run.
        """
        try:
            tools = None
            if use_tools:
                tools = self.toolbox.schemas
            for round_number in range(MAX_TOOL_ROUNDS):
                answer = self.stream_reply(system_prompt, temperature, thinking, tools)
                text, calls = parse_tool_calls(answer)
                if not calls or not use_tools:
                    # No call to run (or tools are off, so a call is never
                    # run). Only the text before any <tool_call> is kept, as
                    # it is all the log showed.
                    self.results.put(("reply", text))
                    return

                tool_calls = []
                for call in calls:
                    tool_calls.append({"type": "function", "function": call})
                self.messages.append(
                    {"role": "assistant", "content": text, "tool_calls": tool_calls}
                )
                for call in calls:
                    self.results.put(("status", f"Running tool {call['name']}..."))
                    result = self.toolbox.run(call["name"], call["arguments"])
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
        """[12.7] (level 1: inside [4.12]) Stream one reply into the queue.

        How it works: this is level 1's streaming loop, moved into its own
        method because a reply that uses tools needs several rounds of it.
        Anything from <tool_call> onwards is kept out of the log, since it
        is meant for the app, not the reader. It returns the reply with any
        thinking removed, ready for parse_tool_calls.
        """
        reply = ""  # everything the model has written this round
        shown = ""  # the part already sent to the window
        for piece in self.backend.chat(
            self.messages, system_prompt, temperature, thinking, tools
        ):
            reply = reply + piece
            visible = reply.split("<tool_call>")[0]
            visible = visible.replace("</think>", "\n[end of thinking]").strip()
            start = len(shown)  # where the not-yet-shown part begins
            new_text = visible[start:]
            if new_text:
                self.results.put(("piece", new_text))
                shown = visible
        return reply.split("</think>")[-1].strip()

    def poll_results(self):
        """[12.8] (level 1: [4.13]) Main thread, on a timer: apply results.

        How it works: empty the queue, updating the window for each result,
        then ask tkinter to call this same method again in POLL_INTERVAL_MS
        milliseconds. A "piece" means more is coming, so the buttons stay
        greyed out; so does a "status", which only changes the status line.
        The other three results mean the work is over. When a model loads,
        it is given a function to call when compaction starts: a lambda
        that puts a status message in the queue, since compaction happens on
        the worker thread.
        """
        while not self.results.empty():
            kind, value = self.results.get()

            if kind == "piece":
                self.append_chat(value)
            elif kind == "status":
                self.status.config(text=value)
            elif kind == "reply":
                self.messages.append({"role": "assistant", "content": value})
                self.append_chat("\n\n")  # blank line before the next message
                self.status.config(text=f"Ready: {self.model_path}")
                self.set_busy(False)
            elif kind == "loaded":
                backend, toolbox, problems = value
                self.backend = backend
                self.toolbox = toolbox
                self.messages = []  # a new model starts a new conversation
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
        """[4.15] Grey out Load and Send while work is running, or bring them back.

        How it works: busy is True or False. It is saved on self.busy so
        send() can check it, and it is turned into the "disabled" or "normal"
        state string that tkinter buttons understand.
        """
        self.busy = busy
        if busy:
            state = "disabled"
        else:
            state = "normal"
        self.load_button.config(state=state)
        self.send_button.config(state=state)

    def close(self):
        """[12.9] Window closed: stop every MCP server, then close the window."""
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
