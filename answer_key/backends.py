"""[3.1] backends.py: the two ways VoxMux can run a model.

How it works: this file holds two classes and one function, and no UI code.
Each class wraps one library. Both classes have the same two methods with
the same parameters: build one with a path to a model, then loop over
.chat(messages) to receive the model's reply a few characters at a time.
Because they look identical from the outside, the window in app.py never
needs to know which one it is holding.

Both chat methods are generators. A function that contains the word "yield"
does not run when it is called; it hands back an object you can loop over,
and each trip round the loop runs the function up to its next yield. That is
what lets the window show words while the model is still writing.

The numbers in square brackets match the step numbers in RECIPE.md.
"""

import threading

# [3.1] Constants: the settings the backends use.
MAX_NEW_TOKENS = 512  # the longest reply a model may write, in tokens
CONTEXT_SIZE = 4096  # the most tokens llama.cpp can hold: conversation plus reply


class LlamaCppBackend:
    """[3.2] Runs a single .gguf file through llama.cpp.

    How it works: llama.cpp does everything itself. It reads the chat
    template stored inside the .gguf file, turns the messages into a prompt,
    generates, and hands back text. This class only has to pass the messages
    in and dig the text out of each chunk that comes back.
    """

    def __init__(self, model_path):
        """[3.2.1] Load the .gguf file at model_path into memory.

        How it works: building a Llama object reads the whole model file,
        which is the slow part. The object is kept on self.llm so chat() can
        reuse it for every message instead of loading again.
        """
        # Imported here, not at the top of the file, so the app still starts
        # if only one of the two libraries is installed.
        from llama_cpp import Llama

        self.llm = Llama(
            model_path=model_path,
            n_ctx=CONTEXT_SIZE,
            n_gpu_layers=-1,  # -1 means "put every layer on the GPU"
            verbose=False,  # do not print pages of loading logs
        )

    def chat(self, messages):
        """[3.2.2] Send the whole conversation, yield the reply piece by piece.

        How it works: messages is a list of dictionaries, each with a "role"
        ("user" or "assistant") and a "content" string. With stream=True,
        llama.cpp hands back a series of small chunks instead of one finished
        answer. Each chunk is a nested dictionary whose "delta" holds the few
        characters that were just written. The first and last chunks carry no
        text, so those are skipped.
        """
        stream = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=MAX_NEW_TOKENS,
            stream=True,
        )
        for chunk in stream:
            delta = chunk["choices"][0]["delta"]
            text = delta.get("content")
            if text:
                yield text


class TransformersBackend:
    """[3.3] Runs a folder of safetensors weights through PyTorch.

    How it works: here the steps llama.cpp hides are done by hand. A
    tokenizer turns text into numbers (tokens), the model predicts more
    numbers, and the tokenizer turns those back into text. The model and the
    tokenizer are two separate objects loaded from the same folder.
    """

    def __init__(self, model_path):
        """[3.3.1] Load the tokenizer and the model from the folder model_path.

        How it works: from_pretrained reads config.json in the folder to find
        out what kind of model it is, then loads the matching weights. The
        model is then moved to the graphics card if there is one, because
        generating on a CPU is far slower.
        """
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if torch.cuda.is_available():
            self.device = "cuda"
        else:
            self.device = "cpu"

        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForCausalLM.from_pretrained(model_path, dtype="auto")
        self.model.to(self.device)

    def chat(self, messages):
        """[3.3.2] Send the whole conversation, yield the reply piece by piece.

        How it works, in four stages: (1) the tokenizer's chat template turns
        the messages into token numbers, (2) a streamer is made to catch the
        words as they are produced, (3) generate() is started on its own
        thread, because it does not return until the whole reply is written,
        and (4) this method loops over the streamer and passes each piece on.
        """
        from transformers import TextIteratorStreamer

        # Stage 1: messages -> token numbers, on the same device as the model.
        inputs = self.tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,  # add the "your turn" marker at the end
            return_tensors="pt",  # give back PyTorch tensors
            return_dict=True,  # give back input_ids and attention_mask together
        )
        inputs = inputs.to(self.device)

        # Stage 2: the streamer. generate() pushes tokens into it, and it
        # hands them back out as readable text.
        streamer = TextIteratorStreamer(
            self.tokenizer,
            skip_prompt=True,  # do not repeat the conversation back
            skip_special_tokens=True,  # leave out markers like end-of-turn
        )

        # Stage 3: run generate() in the background, writing into the streamer.
        settings = dict(inputs)
        settings["max_new_tokens"] = MAX_NEW_TOKENS
        settings["streamer"] = streamer
        thread = threading.Thread(
            target=self.model.generate, kwargs=settings, daemon=True
        )
        thread.start()

        # Stage 4: pass each piece on as it arrives. Some pieces are empty.
        for text in streamer:
            if text:
                yield text


def load_backend(kind, model_path):
    """[3.4] Build and return the backend named by kind.

    How it works: kind is the string "llama_cpp" or "pytorch", the same two
    values the radio buttons in app.py hold. This is the only place that
    knows both classes exist; everything else just loops over .chat() on
    whatever comes back.
    """
    if kind == "llama_cpp":
        return LlamaCppBackend(model_path)
    if kind == "pytorch":
        return TransformersBackend(model_path)
    raise ValueError(f"Unknown backend: {kind}")
