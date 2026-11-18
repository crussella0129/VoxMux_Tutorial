"""[3.1] backends.py: the two ways VoxMux can run a model. (Level 4 version.)

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

Level 4 makes room for models other than Qwen, whose chat templates differ
in three ways that matter here. Some refuse a system message, so the system
prompt is then folded into the first user message. Many say nothing about
tools, so there is now a way to ask whether a template describes them. And
many write the start-of-text token themselves, which llama.cpp would
otherwise add a second time. Each backend can also give its memory back,
so that one model can make way for the next. And a load no longer asks
for a model's whole trained context, which for newer models is far more
than a graphics card can hold. A load that overflows the card all the
same is noticed, and made again with half the context.

The numbers in square brackets match the step numbers in RECIPE.md (3.x),
RECIPE_LEVEL2.md (7.x), RECIPE_LEVEL3.md (15.x) and RECIPE_LEVEL4.md (19.x).
"""

import ctypes
import importlib
import threading

# [3.1] Constants: the settings the backends use.
MAX_NEW_TOKENS = 4096  # the longest reply a model may write, in tokens
SMALLEST_CONTEXT = 4096  # give up loading if not even this much context fits

# [19.1] Constants: the most context a load will ever ask for, in tokens,
# and how much of the graphics card's memory a load must leave free, in
# bytes (512 MB).
LARGEST_CONTEXT = 32768
CARD_RESERVE = 512 * 1024 * 1024

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
        """[19.2] (level 2: [7.5]) Build the prompt, making room until it fits.

        How it works: room for the reply is set aside first, as in level 1.
        While the prompt is too long for the rest, compact() folds the older
        half of the conversation into a summary. If that frees nothing,
        everything before the second user message is forgotten instead, as
        in level 1. If there is no second user message, there is nothing
        left that may go, so the prompt is used as it is. Either way the
        change is made to messages itself, so it lasts. Putting the system
        prompt in is now the job of build_with_system.
        """
        reserve = min(MAX_NEW_TOKENS, self.context_size // 2)
        room = self.context_size - reserve
        while True:
            prompt = self.build_with_system(messages, system_prompt, thinking, tools)
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

    def build_with_system(self, messages, system_prompt, thinking, tools):
        """[19.3] Build the prompt with the system prompt in it, one way or another.

        How it works: most chat templates take the system prompt as a
        message of its own, with the role "system", placed first. Some
        (Mistral's among them) have no such role and raise an error when
        they meet it. For those, the system prompt is written at the start
        of the first user message instead, where the model reads it just the
        same. That is done on a copy of the message, made with dict(), so
        the conversation itself is not changed. If the second attempt fails
        too, the template was objecting to something else, and that error
        is passed on.
        """
        if not system_prompt:
            return self.build_prompt(messages, thinking, tools)
        system = {"role": "system", "content": system_prompt}
        try:
            return self.build_prompt([system] + messages, thinking, tools)
        except Exception:
            first = dict(messages[0])
            first["content"] = system_prompt + "\n\n" + first["content"]
            return self.build_prompt([first] + messages[1:], thinking, tools)

    def compact(self, messages, room):
        """[19.4] (level 2: [7.6]) Replace the older half with a short summary.

        How it works: the older half is at least three messages, so an
        earlier summary (always two messages) gets folded into the new one
        instead of being summarised on its own. The cut is moved forward to
        the next user message, so the recent half starts with something the
        user said. The older half is written out as a plain transcript and
        the model is asked, at temperature 0, to summarise it; the request
        goes through build_with_system, because the instructions for the
        summary are a system prompt like any other. The summary
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
        request = [{"role": "user", "content": "\n\n".join(lines)}]
        prompt = self.build_with_system(request, SUMMARY_INSTRUCTIONS, False, None)
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

    def offers_tools(self, tools):
        """[19.5] Say whether this model's chat template describes tools.

        How it works: a template is free to ignore the tools it is handed,
        and many do; the model then never learns that there are any. The
        test is to build the same one-message prompt twice, once with the
        tools and once without. If both come out the same, the template
        wrote nothing about them.
        """
        sample = [{"role": "user", "content": "Hello"}]
        with_tools = self.build_prompt(sample, False, tools)
        return with_tools != self.build_prompt(sample, False, None)

    def unload(self):
        """[19.6] Give back the memory the model takes up.

        How it works: the app calls this on the old model before it loads a
        new one, because a graphics card rarely has room for two. Nothing
        is held by this base class, so there is nothing to do here; each
        backend below replaces this method with its own.
        """


class LlamaCppBackend(Backend):
    """[3.3] Runs a single .gguf file through llama.cpp.

    How it works: a .gguf file carries the model's weights, its chat
    template and the longest context it was trained for. This class loads
    the weights with as much context as the graphics card can hold, up to
    LARGEST_CONTEXT, uses the template to turn messages into one prompt
    string, and streams the text llama.cpp writes after that prompt.
    """

    def __init__(self, model_path):
        """[19.7] (level 1: [3.3.1]) Load the .gguf file with a context that fits.

        How it works: a quick first load reads only the file's information.
        The real load then starts at the longest context the model was
        trained for, or at LARGEST_CONTEXT if that is less. llama.cpp sets
        aside memory for the whole context up front, so if the card is too
        small that load fails; the size is halved and the load tried again,
        as long as half is not below SMALLEST_CONTEXT. Any other kind of
        failure, such as a file that is not a model, is passed straight on.

        Level 4 adds two things. The first is the upper limit. Newer models
        are trained for contexts of 131,072 tokens and more, which no
        ordinary graphics card can hold. Such a load ought to fail and be
        halved, but on Windows a current NVIDIA driver lets a program that
        has used up the card carry on into ordinary memory. The load then
        succeeds with a context the card cannot hold, and if the ordinary
        memory runs short as well, llama.cpp stops the whole app. Starting
        no higher than LARGEST_CONTEXT keeps most loads clear of that, and
        compaction (step 7) deals with a conversation that outgrows it.

        The second is a check after every load that succeeds. card_free()
        asks llama.cpp how much of the card's memory is left. If that is
        less than CARD_RESERVE, the load took the card to its edge or past
        it, so the model is closed and loaded again with half the context,
        just as if the load had failed. There is no check when the answer
        is None, which means there is no card to ask about, or when half
        the context would be below SMALLEST_CONTEXT: a slow model is
        better than none.
        """
        # Imported here, not at the top of the file, so the app still starts
        # if only one of the two libraries is installed.
        from llama_cpp import Llama
        from llama_cpp.llama_chat_format import Jinja2ChatFormatter

        info = Llama(model_path=model_path, vocab_only=True, verbose=False)
        architecture = info.metadata["general.architecture"]
        size = int(info.metadata[f"{architecture}.context_length"])
        size = min(size, LARGEST_CONTEXT)

        while True:
            try:
                self.llm = Llama(
                    model_path=model_path,
                    n_ctx=size,
                    n_gpu_layers=-1,  # -1 means "put every layer on the GPU"
                    verbose=False,  # do not print pages of loading logs
                )
                free = self.card_free()
                if free is None or free >= CARD_RESERVE:
                    break
                if size // 2 < SMALLEST_CONTEXT:
                    break
                self.llm.close()
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
        """[19.8] (level 1: [3.3.4]) Yield the text the model writes after prompt.

        How it works: with stream=True, create_completion hands back a series
        of small chunks instead of one finished answer. Each chunk's new text
        sits under "choices", then index 0, then "text". Empty pieces are
        skipped.

        Level 4 turns the prompt into tokens here, instead of leaving that
        to create_completion. Most models expect one start-of-text token
        before everything else. Handed a prompt as text, llama.cpp adds that
        token, but many chat templates write it too, and a model that is
        shown two answers worse. So the prompt is tokenized as it stands
        (add_bos=False). Then tokenize() is asked for the tokens of nothing
        at all, with add_bos=True: that gives a list holding the
        start-of-text token, or an empty list for a model that wants none.
        If the prompt does not already begin with that list, it is put in
        front. Handed a list of tokens, create_completion adds nothing of
        its own.
        """
        tokens = self.llm.tokenize(prompt.encode("utf-8"), add_bos=False, special=True)
        start = self.llm.tokenize(b"", add_bos=True)
        if tokens[: len(start)] != start:
            tokens = start + tokens
        chunks = self.llm.create_completion(
            tokens,
            max_tokens=MAX_NEW_TOKENS,
            temperature=temperature,
            stream=True,
        )
        for chunk in chunks:
            text = chunk["choices"][0]["text"]
            if text:
                yield text

    def unload(self):
        """[19.9] Give the model's memory back to the graphics card.

        How it works: llama.cpp keeps the weights and the context in memory
        of its own, outside Python's reach, and close() is how it is told
        to free them.
        """
        self.llm.close()

    def card_free(self):
        """[19.10] Return the graphics card's free memory in bytes, or None.

        How it works: llama.cpp keeps a list of the devices it can run on
        and can say how much memory each has left, but llama_cpp passes on
        neither. So the two libraries that can are called directly, with
        ctypes, Python's way of calling functions written in C. C does not
        say what kind of value it is handed or hands back, so the code has
        to: restype says that the function giving out a device returns an
        address (c_void_p), and every value handed over is wrapped in the
        kind C expects. The memory function gives its two answers by
        writing them into variables it is shown the way to, which is what
        byref() does. Devices of kind 0 are the processor and are skipped.
        With more than one card, the smallest answer is the one that
        matters. If any of this fails, for example because this copy of
        llama_cpp is laid out differently, the answer is None, and the
        caller carries on without the check.
        """
        try:
            from llama_cpp import _ggml
            from llama_cpp._ctypes_extensions import load_shared_library

            devices = _ggml.libggml
            details = load_shared_library("ggml-base", _ggml.libggml_base_path)
            devices.ggml_backend_dev_get.restype = ctypes.c_void_p
            least = None
            for index in range(devices.ggml_backend_dev_count()):
                found = devices.ggml_backend_dev_get(ctypes.c_size_t(index))
                device = ctypes.c_void_p(found)
                if details.ggml_backend_dev_type(device) == 0:
                    continue
                free = ctypes.c_size_t()
                total = ctypes.c_size_t()
                details.ggml_backend_dev_memory(
                    device, ctypes.byref(free), ctypes.byref(total)
                )
                if least is None or free.value < least:
                    least = free.value
            return least
        except Exception:
            return None


class TransformersBackend(Backend):
    """[3.4] Runs a folder of safetensors weights through PyTorch.

    How it works: here the steps llama.cpp hides are done by hand. A
    tokenizer turns text into numbers (tokens), the model predicts more
    numbers, and the tokenizer turns those back into text. The model and the
    tokenizer are two separate objects loaded from the same folder.
    """

    def __init__(self, model_path):
        """[19.11] (level 1: [3.4.1]) Load the tokenizer and the model.

        How it works: from_pretrained reads config.json in the folder to find
        out what kind of model it is, then loads the matching weights. The
        model is moved to the graphics card if there is one, because
        generating on a CPU is far slower. The longest context the model was
        trained for is read from the same config.

        Level 4 holds that number down to LARGEST_CONTEXT, as it does for
        a GGUF model. PyTorch sets no memory aside for the context when it
        loads, so nothing can overflow here; the memory goes as the
        conversation grows. The limit is what makes compaction start
        before a long conversation has used the card up.

        Level 4 also imports pyarrow before anything else, if it is
        installed. The app has no use for it, but transformers loads it
        (by way of pandas) whenever it is there. Windows gives a program
        64 quick slots for per-thread storage, importing torch takes all
        that are left, and version 24 of pyarrow, loaded after that,
        carries on with a slot it cannot use and can stop the whole app
        without a word. Loaded first, it gets a slot that works.
        import_module() is import with the name given as a string; a
        computer without pyarrow raises ImportError, and nothing is lost.
        """
        try:
            importlib.import_module("pyarrow")
        except ImportError:
            pass
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
        self.context_size = min(text_config.max_position_embeddings, LARGEST_CONTEXT)

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

    def unload(self):
        """[19.12] Give the model's memory back to the graphics card.

        How it works: Python frees an object once nothing refers to it, so
        letting go of the model is enough to free its weights. PyTorch
        keeps the freed graphics memory for itself, though, ready for its
        next use; empty_cache() hands it back, so that llama.cpp can have
        it if a GGUF model is loaded next.
        """
        import torch

        self.model = None
        torch.cuda.empty_cache()


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
