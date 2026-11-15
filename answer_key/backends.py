"""[3.1] backends.py: the two ways VoxMux can run a model.

How it works: this file holds a shared base class, two backend classes built
on it, and one function that picks between them. There is no UI code here.
Each backend wraps one library. From the outside both look the same: build
one with a path to a model, then loop over .chat(...) to receive the reply a
few characters at a time. That is why the window in app.py never needs to
know which one it is holding.

Both chat methods are generators. A function that contains the word "yield"
does not run when it is called; it hands back an object you can loop over,
and each trip round the loop runs the function up to its next yield. That is
what lets the window show words while the model is still writing.

The numbers in square brackets match the step numbers in RECIPE.md.
"""

import threading

# [3.1] Constants: the settings the backends use.
MAX_NEW_TOKENS = 4096  # the longest reply a model may write, in tokens
SMALLEST_CONTEXT = 4096  # give up loading if not even this much context fits


class Backend:
    """[3.2] What every backend shares: fit the conversation, then stream.

    How it works: a model can only read a limited number of tokens at once,
    its context size. chat() first builds the prompt and, while it is too
    long, forgets the oldest messages; only then does it stream the reply.
    This class never runs a model itself. Each subclass below supplies the
    four model-specific parts it relies on: the context_size attribute and
    the build_prompt(), count_tokens() and stream() methods.
    """

    def chat(self, messages, system_prompt, temperature, thinking):
        """[3.2.1] Fit the conversation into the context, then stream a reply.

        How it works: messages is the conversation so far, a list of
        dictionaries with a "role" and a "content". system_prompt is the
        text from the System prompt box, temperature is the slider's value,
        and thinking is True or False. "yield from" passes on every piece
        that stream() yields, which makes this method a generator too.
        """
        prompt = self.fit_to_context(messages, system_prompt, thinking)
        yield from self.stream(prompt, temperature)

    def fit_to_context(self, messages, system_prompt, thinking):
        """[3.2.2] Build the prompt, forgetting old messages until it fits.

        How it works: room for the reply is set aside first: MAX_NEW_TOKENS,
        or half the context if the model's context is small. While the
        prompt is too long for the rest, the oldest message is deleted from
        messages itself, so it stays forgotten and is never counted again. A
        conversation has to start with something the user said, so any
        replies left at the front go too. The newest message is never
        deleted, even if it is too long on its own; llama.cpp then reports
        an error if the prompt fills the whole context, and PyTorch tries
        anyway.
        """
        reserve = min(MAX_NEW_TOKENS, self.context_size // 2)
        room = self.context_size - reserve
        while True:
            full = messages
            if system_prompt:
                full = [{"role": "system", "content": system_prompt}] + messages
            prompt = self.build_prompt(full, thinking)
            if self.count_tokens(prompt) <= room or len(messages) == 1:
                return prompt
            del messages[0]
            while messages[0]["role"] != "user":
                del messages[0]


class LlamaCppBackend(Backend):
    """[3.3] Runs a single .gguf file through llama.cpp.

    How it works: a .gguf file carries the model's weights, its chat
    template and the longest context it was trained for. This class loads
    the weights with as much context as the graphics card can hold, uses
    the template to turn messages into one prompt string, and streams the
    text llama.cpp writes after that prompt.
    """

    def __init__(self, model_path):
        """[3.3.1] Load the .gguf file with as much context as will fit.

        How it works: a quick first load reads only the file's information.
        The real load then starts at the longest context the model was
        trained for. llama.cpp sets aside memory for the whole context up
        front, so if the card is too small that load fails; the size is
        halved and the load tried again, as long as half is not below
        SMALLEST_CONTEXT. Any other kind of failure, such as a file that is
        not a model, is passed straight on.
        """
        # Imported here, not at the top of the file, so the app still starts
        # if only one of the two libraries is installed.
        from llama_cpp import Llama
        from llama_cpp.llama_chat_format import Jinja2ChatFormatter

        info = Llama(model_path=model_path, vocab_only=True, verbose=False)
        architecture = info.metadata["general.architecture"]
        size = int(info.metadata[f"{architecture}.context_length"])

        while True:
            try:
                self.llm = Llama(
                    model_path=model_path,
                    n_ctx=size,
                    n_gpu_layers=-1,  # -1 means "put every layer on the GPU"
                    verbose=False,  # do not print pages of loading logs
                )
                break
            except ValueError as error:
                if "llama_context" not in str(error) or size // 2 < SMALLEST_CONTEXT:
                    raise
                size = size // 2
        self.context_size = size

        end_token = info.detokenize([info.token_eos()], special=True)
        start_token = info.detokenize([info.token_bos()], special=True)
        self.formatter = Jinja2ChatFormatter(
            template=info.metadata["tokenizer.chat_template"],
            eos_token=end_token.decode("utf-8", errors="ignore"),
            bos_token=start_token.decode("utf-8", errors="ignore"),
        )

    def build_prompt(self, messages, thinking):
        """[3.3.2] Turn messages into the one prompt string the model reads.

        How it works: the formatter fills in the model's own chat template.
        enable_thinking is a setting many templates (Qwen's among them) read
        to decide whether the model thinks before it answers. Templates that
        do not know it simply ignore it.
        """
        return self.formatter(messages=messages, enable_thinking=thinking).prompt

    def count_tokens(self, prompt):
        """[3.3.3] Count how many tokens a prompt string takes up.

        How it works: tokenize() needs bytes, not a string, so the text is
        encoded first. special=True makes markers such as <|im_start|> count
        as the single tokens they really are.
        """
        tokens = self.llm.tokenize(prompt.encode("utf-8"), add_bos=False, special=True)
        return len(tokens)

    def stream(self, prompt, temperature):
        """[3.3.4] Yield the text the model writes after prompt, piece by piece.

        How it works: with stream=True, create_completion hands back a series
        of small chunks instead of one finished answer. Each chunk's new text
        sits under "choices", then index 0, then "text". Empty pieces are
        skipped.
        """
        chunks = self.llm.create_completion(
            prompt,
            max_tokens=MAX_NEW_TOKENS,
            temperature=temperature,
            stream=True,
        )
        for chunk in chunks:
            text = chunk["choices"][0]["text"]
            if text:
                yield text


class TransformersBackend(Backend):
    """[3.4] Runs a folder of safetensors weights through PyTorch.

    How it works: here the steps llama.cpp hides are done by hand. A
    tokenizer turns text into numbers (tokens), the model predicts more
    numbers, and the tokenizer turns those back into text. The model and the
    tokenizer are two separate objects loaded from the same folder.
    """

    def __init__(self, model_path):
        """[3.4.1] Load the tokenizer and the model from the folder model_path.

        How it works: from_pretrained reads config.json in the folder to find
        out what kind of model it is, then loads the matching weights. The
        model is moved to the graphics card if there is one, because
        generating on a CPU is far slower. The longest context the model was
        trained for is read from the same config.
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

        text_config = self.model.config.get_text_config()
        self.context_size = text_config.max_position_embeddings

    def build_prompt(self, messages, thinking):
        """[3.4.2] Turn messages into the one prompt string the model reads.

        How it works: apply_chat_template fills in the model's chat template.
        tokenize=False asks for the text rather than token numbers, and
        add_generation_prompt adds the marker that means "your turn". Extra
        settings such as enable_thinking are handed to the template.
        """
        return self.tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=False,
            enable_thinking=thinking,
        )

    def count_tokens(self, prompt):
        """[3.4.3] Count how many tokens a prompt string takes up.

        How it works: calling the tokenizer on text gives back a dictionary
        whose "input_ids" are the token numbers. add_special_tokens=False
        stops it adding markers the template has already written.
        """
        tokens = self.tokenizer(prompt, add_special_tokens=False)
        return len(tokens["input_ids"])

    def stream(self, prompt, temperature):
        """[3.4.4] Yield the text the model writes after prompt, piece by piece.

        How it works, in four stages: (1) the prompt is turned into token
        numbers on the model's device, (2) a streamer is made to catch the
        words as they are produced, (3) generate() is started on its own
        thread, because it does not return until the whole reply is written,
        and (4) this method loops over the streamer and passes each piece on.
        """
        from transformers import TextIteratorStreamer

        # Stage 1: prompt -> token numbers, on the same device as the model.
        inputs = self.tokenizer(prompt, add_special_tokens=False, return_tensors="pt")
        inputs = inputs.to(self.device)

        # Stage 2: the streamer. generate() pushes tokens into it, and it
        # hands them back out as readable text.
        streamer = TextIteratorStreamer(
            self.tokenizer,
            skip_prompt=True,  # do not repeat the conversation back
            skip_special_tokens=True,  # leave out markers like end-of-turn
        )

        # Stage 3: run generate() in the background, writing into the streamer.
        # A temperature of 0 means "always pick the likeliest word" (no
        # sampling); anything higher samples, more randomly as it rises.
        settings = dict(inputs)
        settings["max_new_tokens"] = MAX_NEW_TOKENS
        settings["streamer"] = streamer
        if temperature > 0:
            settings["do_sample"] = True
            settings["temperature"] = temperature
        else:
            settings["do_sample"] = False
        thread = threading.Thread(
            target=self.model.generate, kwargs=settings, daemon=True
        )
        thread.start()

        # Stage 4: pass each piece on as it arrives. Some pieces are empty.
        for text in streamer:
            if text:
                yield text


def load_backend(kind, model_path):
    """[3.5] Build and return the backend named by kind.

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
