"""VoxMux: a tiny desktop chat window for local models.

Run it with:  python app.py
"""

import queue
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext

from backends import load_backend

POLL_INTERVAL_MS = 100


class ChatApp:
    def __init__(self, root):
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
        # Top row: pick a backend, pick a model, load it.
        top = tk.Frame(self.root)
        top.pack(fill="x", padx=8, pady=8)

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

        # Status line.
        self.status = tk.Label(self.root, text="No model loaded.", anchor="w")
        self.status.pack(fill="x", padx=8)

        # Bottom row: type a message, send it. Packed before the chat log so
        # it keeps its place at the bottom when the window is resized.
        bottom = tk.Frame(self.root)
        bottom.pack(side="bottom", fill="x", padx=8, pady=8)

        self.entry = tk.Entry(bottom)
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", self.send)

        self.send_button = tk.Button(bottom, text="Send", command=self.send)
        self.send_button.pack(side="left", padx=(8, 0))

        # Chat log fills whatever space is left.
        self.chat_log = scrolledtext.ScrolledText(
            self.root, wrap="word", state="disabled"
        )
        self.chat_log.pack(fill="both", expand=True, padx=8, pady=8)

    def browse(self):
        # A GGUF model is one file; a safetensors model is a whole folder.
        if self.backend_kind.get() == "llama_cpp":
            path = filedialog.askopenfilename(filetypes=[("GGUF model", "*.gguf")])
        else:
            path = filedialog.askdirectory()

        if path:
            self.model_path = path
            self.status.config(text=f"Selected: {path}")

    def load_model(self):
        if not self.model_path:
            self.status.config(text="Pick a model with Browse first.")
            return

        self.set_busy(True)
        self.status.config(text="Loading model...")
        self.start_worker(self.load_worker, self.backend_kind.get(), self.model_path)

    def send(self, event=None):
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
        # Slow work runs on its own thread so the window does not freeze.
        thread = threading.Thread(target=target, args=args, daemon=True)
        thread.start()

    def load_worker(self, kind, model_path):
        try:
            backend = load_backend(kind, model_path)
            self.results.put(("loaded", backend))
        except Exception as error:
            self.results.put(("error", str(error)))

    def reply_worker(self):
        try:
            reply = self.backend.chat(self.messages)
            self.results.put(("reply", reply))
        except Exception as error:
            self.results.put(("error", str(error)))

    def poll_results(self):
        # Worker threads must not touch widgets, so they drop results in a
        # queue and this method, running on the main thread, picks them up.
        while not self.results.empty():
            kind, value = self.results.get()

            if kind == "loaded":
                self.backend = value
                self.messages = []
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
        self.chat_log.config(state="normal")
        self.chat_log.insert("end", f"{speaker}: {text}\n\n")
        self.chat_log.config(state="disabled")
        self.chat_log.see("end")

    def set_busy(self, busy):
        self.busy = busy
        if busy:
            state = "disabled"
        else:
            state = "normal"
        self.load_button.config(state=state)
        self.send_button.config(state=state)


def main():
    root = tk.Tk()
    ChatApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
