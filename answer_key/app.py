"""[4.1] app.py: the VoxMux window, a tiny desktop chat for local models.

How it works: one class, ChatApp, builds the window and holds the state
(which model is loaded, the conversation so far). Loading a model and
generating a reply are slow, so they run on a second thread and report back
through a queue. The main thread checks that queue ten times a second and
is the only thread that ever touches the window.

Run it with:  python app.py

The numbers in square brackets match the step numbers in RECIPE.md.
"""

import queue
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext

from backends import load_backend

# [4.1] Constant: how often the main thread checks the queue, in milliseconds.
POLL_INTERVAL_MS = 100


class ChatApp:
    """[4.2] The whole window: its widgets, its state, and its behaviour.

    How it works: the methods fall into three groups. Button handlers
    (browse, load_model, send) run on the main thread when the user does
    something. Workers (load_worker, reply_worker) run on a second thread and
    do the slow part. poll_results runs on the main thread on a timer and
    carries the workers' results back into the window.
    """

    def __init__(self, root):
        """[4.3] Set up the window, the starting state, and the queue check.

        How it works: root is the main window object made in main(). Every
        attribute the other methods rely on is created here first, so no
        method can ever meet one that does not exist yet.
        """
        self.root = root
        self.root.title("VoxMux")
        self.root.geometry("700x500")

        self.backend = None  # the loaded model, once there is one
        self.model_path = ""  # what the user picked with Browse
        self.messages = []  # the whole conversation so far
        self.busy = False  # True while a worker thread is running
        self.results = queue.Queue()  # how worker threads report back

        self.build_widgets()
        self.poll_results()

    def build_widgets(self):
        """[4.4] Create every widget and place it in the window.

        How it works: each widget is created with its parent as the first
        argument, then placed with .pack(). tkinter hands out space in the
        order widgets are packed, so the order of the four blocks below is
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

        # [4.4.2] Status line: one row of text that says what is going on.
        self.status = tk.Label(self.root, text="No model loaded.", anchor="w")
        self.status.pack(fill="x", padx=8)

        # [4.4.3] Bottom row: type a message, send it. Packed before the chat
        # log so it keeps its place at the bottom when the window is resized.
        bottom = tk.Frame(self.root)
        bottom.pack(side="bottom", fill="x", padx=8, pady=8)

        self.entry = tk.Entry(bottom)
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", self.send)  # pressing Enter sends too

        self.send_button = tk.Button(bottom, text="Send", command=self.send)
        self.send_button.pack(side="left", padx=(8, 0))

        # [4.4.4] Chat log: read-only, and fills whatever space is left.
        self.chat_log = scrolledtext.ScrolledText(
            self.root, wrap="word", state="disabled"
        )
        self.chat_log.pack(fill="both", expand=True, padx=8, pady=8)

    def browse(self):
        """[4.5] Browse button: let the user pick a model, remember the path.

        How it works: a GGUF model is one file and a safetensors model is a
        whole folder, so the selected radio button decides which kind of
        picker opens. Both pickers return an empty string on Cancel.
        """
        if self.backend_kind.get() == "llama_cpp":
            path = filedialog.askopenfilename(filetypes=[("GGUF model", "*.gguf")])
        else:
            path = filedialog.askdirectory()

        if path:
            self.model_path = path
            self.status.config(text=f"Selected: {path}")

    def load_model(self):
        """[4.6] Load button: start loading the picked model in the background.

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
        """[4.7] Send button or Enter key: add the message, ask for a reply.

        How it works: the button calls this with no arguments and the Enter
        key calls it with one (an event object), so event defaults to None
        and is never used. The user's message joins self.messages and the
        chat log straight away; the reply arrives later through the queue.
        """
        text = self.entry.get().strip()
        if not text or self.backend is None or self.busy:
            return

        self.entry.delete(0, "end")
        self.messages.append({"role": "user", "content": text})
        self.append_chat("You", text)

        self.set_busy(True)
        self.status.config(text="Thinking...")
        self.start_worker(self.reply_worker)

    def start_worker(self, target, *args):
        """[4.8] Run target(*args) on a new background thread.

        How it works: slow work on the main thread would freeze the window,
        so it gets a thread of its own. daemon=True means the thread is
        dropped when the window closes instead of keeping the program alive.
        """
        thread = threading.Thread(target=target, args=args, daemon=True)
        thread.start()

    def load_worker(self, kind, model_path):
        """[4.9] Background thread: load a model, put the result in the queue.

        How it works: worker threads must not touch widgets, so this method
        reports by putting a (label, value) pair in the queue. Any error is
        caught and reported the same way; otherwise it would vanish silently.
        """
        try:
            backend = load_backend(kind, model_path)
            self.results.put(("loaded", backend))
        except Exception as error:
            self.results.put(("error", str(error)))

    def reply_worker(self):
        """[4.10] Background thread: get a reply, put the result in the queue.

        How it works: the same pattern as load_worker. The whole conversation
        is sent every time, which is how the model remembers earlier turns.
        """
        try:
            reply = self.backend.chat(self.messages)
            self.results.put(("reply", reply))
        except Exception as error:
            self.results.put(("error", str(error)))

    def poll_results(self):
        """[4.11] Main thread, on a timer: apply whatever the workers reported.

        How it works: empty the queue, updating the window for each result,
        then ask tkinter to call this same method again in POLL_INTERVAL_MS
        milliseconds. That last line is what keeps the checking going for as
        long as the window is open.
        """
        while not self.results.empty():
            kind, value = self.results.get()

            if kind == "loaded":
                self.backend = value
                self.messages = []  # a new model starts a new conversation
                self.status.config(text=f"Ready: {self.model_path}")
            elif kind == "reply":
                self.messages.append({"role": "assistant", "content": value})
                self.append_chat("Model", value)
                self.status.config(text=f"Ready: {self.model_path}")
            elif kind == "error":
                self.status.config(text=f"Error: {value}")

            self.set_busy(False)

        self.root.after(POLL_INTERVAL_MS, self.poll_results)

    def append_chat(self, speaker, text):
        """[4.12] Add one "Speaker: text" entry to the chat log.

        How it works: the log is kept read-only so the user cannot type into
        the history. That also blocks the program, so it is unlocked, written
        to, locked again, and then scrolled to the bottom.
        """
        self.chat_log.config(state="normal")
        self.chat_log.insert("end", f"{speaker}: {text}\n\n")
        self.chat_log.config(state="disabled")
        self.chat_log.see("end")

    def set_busy(self, busy):
        """[4.13] Grey out Load and Send while work is running, or bring them back.

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


def main():
    """[4.14] Create the window, attach the app to it, and run until closed.

    How it works: mainloop() is tkinter's event loop. It waits for clicks,
    keypresses and timers, calls the matching method for each, and does not
    return until the window is closed.
    """
    root = tk.Tk()
    ChatApp(root)
    root.mainloop()


# [4.15] Start the app only when this file is run directly (python app.py),
# not when another file imports it.
if __name__ == "__main__":
    main()
