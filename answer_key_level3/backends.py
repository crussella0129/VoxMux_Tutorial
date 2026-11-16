"""[3.1] backends.py: the two ways VoxMux can run a model. (Level 3 version.)

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

Level 2 adds two things here. Tools: the list of tools the model may call is
handed through to the chat template, which describes them to the model.
Compaction: when the conversation no longer fits, the older half is
summarised by the model itself instead of being forgotten.

Level 3 changes one method, TransformersBackend.stream. A reply can now be
cut short: whoever is looping over .chat() simply stops looping and closes
the generator, and the PyTorch backend then tells its model to stop writing.
A failure in the middle of a PyTorch reply is also passed on, where it used
to leave the app waiting for ever.

The numbers in square brackets match the step numbers in RECIPE.md (3.x),
RECIPE_LEVEL2.md (7.x) and RECIPE_LEVEL3.md (15.x).
"""

import threading

# [3.1] Constants: the settings the backends use.
MAX_NEW_TOKENS = 4096  # the longest reply a model may write, in tokens
SMALLEST_CONTEXT = 4096  # give up loading if not even this much context fits

# [7.1] Constant: what the model is told when it summarises old messages.
SUMMARY_INSTRUCTIONS = (
    "Summarise the conversation below so it can be continued later. Keep "
    "every name, number, fact, decision and open question. Write plain "
    "sentences, no more than about 200 words."
)


def find_user(messages, start):
    """[7.2] Return the index of the first user message at or after start.

    How it works: it checks each position from start to the end of the
    list and returns the first whose role is "user". If there is none, it
    returns None. During a round of tool calls the newest messages are the
    model's call and the tool's result, not the user's, so code that looks
    for a user message must be ready for there to be none.
    """
    for index in range(start, len(messages)):
        if messages[index]["role"] == "user":
            return index
    return None


class Backend:
    """[7.3] (level 1: [3.2]) What every backend shares: fit, then stream.

    How it works: a model can only read a limited number of tokens at once,
    its context size. chat() first builds the prompt and, while it is too
    long, makes room by summarising or forgetting old messages; only then
    does it stream the reply. This class never runs a model itself. Each
    subclass below supplies the four model-specific parts it relies on: the
    context_size attribute and the build_prompt(), count_tokens() and
    stream() methods.
    """

    # [7.3] Set by the app to a function to call when compaction starts, so
    # the window can say what is happening. None means "tell nobody".
    on_compact = None

    def chat(self, messages, system_prompt, temperature, thinking, tools=None):
        """[7.4] (level 1: [3.2.1]) Fit the conversation, then stream a reply.

        How it works: messages is the conversation so far, a list of
        dictionaries with a "role" and a "content". system_prompt is the
        text from the System prompt box, temperature is the slider's value,
        and thinking is True or False. tools is a list of tool descriptions
        for the template, or None for no tools. "yield from" passes on every
        piece that stream() yields, which makes this method a generator too.
        """
        prompt = self.fit_to_context(messages, system_prompt, thinking, tools)
        yield from self.stream(prompt, temperature)

    def fit_to_context(self, messages, system_prompt, thinking, tools):
        """[7.5] (level 1: [3.2.2]) Build the prompt, making room until it fits.

        How it works: room for the reply is set aside first, as in level 1.
        While the prompt is too long for the rest, compact() folds the older
        half of the conversation into a summary. If that frees nothing,
        everything before the second user message is forgotten instead, as
        in level 1. If there is no second user message, there is nothing
        left that may go, so the prompt is used as it is. Either way the
        change is made to messages itself, so it lasts.
        """
        reserve = min(MAX_NEW_TOKENS, self.context_size // 2)
        room = self.context_size - reserve
        while True:
            full = messages
            if system_prompt:
                full = [{"role": "system", "content": system_prompt}] + messages
            prompt = self.build_prompt(full, thinking, tools)
            if self.count_tokens(prompt) <= room:
                return prompt
            before = len(messages)
            self.compact(messages, room)
            if len(messages) < before:
                continue
            second_user = find_user(messages, 1)
            if second_user is None:
                return prompt
            del messages[:second_user]

    def compact(self, messages, room):
        """[7.6] Replace the older half of messages with a short summary.

        How it works: the older half is at least three messages, so an
        earlier summary (always two messages) gets folded into the new one
        instead of being summarised on its own. The cut is moved forward to
        the next user message, so the recent half starts with something the
        user said. The older half is written out as a plain transcript and
        the model is asked, at temperature 0, to summarise it. The summary
        goes back in as a pair of messages, one from the user carrying it
        and a short reply, because many chat templates expect user and model
        turns to alternate. Nothing is changed if no user message comes
        after the cut, or if the older half is too long to summarise in one
        go; fit_to_context then falls back to forgetting.
        """
        cut = find_user(messages, max(len(messages) // 2, 3))
        if cut is None:
            return
        older = messages[:cut]

        lines = []
        for message in older:
            if message.get("content"):
                lines.append(f"{message['role']}: {message['content']}")
        request = [
            {"role": "system", "content": SUMMARY_INSTRUCTIONS},
            {"role": "user", "content": "\n\n".join(lines)},
        ]
        prompt = self.build_prompt(request, False, None)
        if self.count_tokens(prompt) > room:
            return

        if self.on_compact:
            self.on_compact()
        summary = "".join(self.stream(prompt, 0)).split("</think>")[-1].strip()
        messages[:cut] = [
            {
                "role": "user",
                "content": "Summary of our conversation so far:\n" + summary,
            },
            {"role": "assistant", "content": "Thanks, I have that summary."},
        ]


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

    def build_prompt(self, messages, thinking, tools=None):
        """[7.7] (level 1: [3.3.2]) Turn messages into one prompt string.

        How it works: the formatter fills in the model's own chat template.
        enable_thinking is a setting many templates (Qwen's among them) read
        to decide whether the model thinks before it answers. tools is the
        list of tool descriptions; the template writes them into the prompt
        along with instructions on how to call them. Templates that know
        neither setting simply ignore them.
        """
        response = self.formatter(
            messages=messages, tools=tools, enable_thinking=thinking
        )
        return response.prompt

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

    def build_prompt(self, messages, thinking, tools=None):
        """[7.8] (level 1: [3.4.2]) Turn messages into one prompt string.

        How it works: apply_chat_template fills in the model's chat template.
        tokenize=False asks for the text rather than token numbers, and
        add_generation_prompt adds the marker that means "your turn". The
        tool descriptions and extra settings such as enable_thinking are
        handed to the template.
        """
        return self.tokenizer.apply_chat_template(
            messages,
            tools=tools,
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
        """[15.2] (level 1: [3.4.4]) Yield the text the model writes after prompt.

        How it works, in four stages: (1) the prompt is turned into token
        numbers on the model's device, (2) a streamer is made to catch the
        words as they are produced, (3) generate() is started on its own
        thread, because it does not return until the whole reply is written,
        and (4) this method loops over the streamer and passes each piece on.

        Level 3 adds two safety nets, both built from functions defined
        inside this method so that they can use its variables. should_stop
        is handed to generate(), which calls it after every token and stops
        writing once it returns True. It returns the state of stop, a flag
        that the "finally" block sets when the loop in stage 4 ends for any
        reason, including the caller closing this generator early. run
        wraps generate(): if it fails, the error is kept and the streamer is
        told the reply is over, so the loop in stage 4 ends and the error
        can be raised here, on the thread that is listening.
        """
        from transformers import StoppingCriteriaList, TextIteratorStreamer

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
        stop = threading.Event()  # set when nobody is listening any more
        failures = []  # the error, if generate() fails

        def should_stop(input_ids, scores, **extra):
            return stop.is_set()

        settings = dict(inputs)
        settings["max_new_tokens"] = MAX_NEW_TOKENS
        settings["streamer"] = streamer
        settings["stopping_criteria"] = StoppingCriteriaList([should_stop])
        if temperature > 0:
            settings["do_sample"] = True
            settings["temperature"] = temperature
        else:
            settings["do_sample"] = False

        def run():
            try:
                self.model.generate(**settings)
            except Exception as error:
                failures.append(error)
                streamer.end()

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

        # Stage 4: pass each piece on as it arrives. Some pieces are empty.
        # "finally" runs however the loop ends, so generate() is always told
        # to stop and is given time to do so before anything else uses the
        # model.
        try:
            for text in streamer:
                if text:
                    yield text
        finally:
            stop.set()
            thread.join()
        if failures:
            raise failures[0]


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
