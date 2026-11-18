# VoxMux recipe: build it by hand (level 1)

This is a description, in words, of every file in [`answer_key/`](answer_key/). Follow it top to bottom, type every line yourself, and you will end up with the same app: a desktop window where you pick llama.cpp (a `.gguf` file) or PyTorch (a folder of `.safetensors` weights), load a model, and chat with it. Replies appear word by word as the model writes them. You can give the model a system prompt, set its temperature, and switch on thinking mode with your own instructions. The app always loads the biggest context the model and your graphics card allow, and quietly forgets the oldest messages when a conversation outgrows it.

There is no finished code in this document. The finished code is in `answer_key/`, and the two are tied together by **reference tags**.

When this works, [RECIPE_LEVEL2.md](RECIPE_LEVEL2.md) is level 2: summarising old messages instead of forgetting them, tool calling, and MCP servers. [RECIPE_LEVEL3.md](RECIPE_LEVEL3.md) is level 3: a Stop button, a New chat button, saved settings, and asking before a tool runs.

## How the reference tags work

Every step below has a number, such as **3.3.1**. The same number appears in square brackets in the answer key, in the docstring or comment sitting on the matching block of code:

- Step **3.3.1** in this file describes `LlamaCppBackend.__init__`.
- In [`answer_key/backends.py`](answer_key/backends.py), that method's docstring starts with `[3.3.1]`.

So when you are stuck on a step, search the answer key for its tag (Ctrl+F, then type `[3.3.1]`) and you land on exactly the lines that step describes. Tags starting with 1 are in `install.py`. Tags starting with 3 are in `backends.py`. Tags starting with 4 are in `app.py`.

Each tagged docstring in the answer key also carries a short "How it works" description. Wherever a step asks for a docstring, write your own, **starting with the same tag**. A few blocks get a comment instead of a docstring; those steps say so, and that comment starts with the tag too. Any other comment the recipe asks for, such as a note above an import or at the end of a line, has no tag. That way your file and the answer key can be compared block by block.

## What you are building

Three files, in a new folder called `my_build/` at the top of the repo:

| Step | File | What it is |
| --- | --- | --- |
| 1 | `install.py` | A short script that installs the libraries and checks they work. Not part of the app itself. |
| 3 | `backends.py` | A shared base class, two classes that each know how to run one kind of model, and one function that picks between them. No UI code. |
| 4 | `app.py` | The window: one class for the UI, one `main` function, and the line that starts it. |

Step 2 writes no file: it downloads the models you will test with. Step 5 runs the finished app.

The libraries the app depends on are listed in one place only, `install.py`. There is no `requirements.txt`, because `pip install -r requirements.txt` would do the wrong thing on Windows: it fetches the CPU-only PyTorch and tries to compile llama-cpp-python from source.

**You can check your work at any point** without a model or a graphics card. From the repo root:

```bash
python check_my_build.py my_build
```

This runs the same tests the answer key is checked with on your folder. A file you have not written yet is skipped. Each line it prints ends with the step numbers it checks, so a failure tells you which step to read again.

The idea that holds it together: both backend classes have **the same methods with the same parameters**. You build one by giving it a model path, and you loop over `chat` with the conversation so far to receive the reply a few characters at a time. Because the two look identical from the outside, the window never has to care which one it is holding.

## Python syntax you will meet

Read this once now and come back to it as needed.

- **Indentation is the syntax.** Python does not use braces to mark blocks. A line ending in a colon (`def ...:`, `class ...:`, `if ...:`, `while ...:`, `try:`) opens a block, and everything indented four spaces under it is inside that block. Use four spaces, never tabs.
- **Functions** are written `def name(parameter, other_parameter):`. The names in the parentheses are *parameters*. When you call the function, the values you pass are *arguments*.
- **Positional vs keyword arguments.** `f(a, b)` passes by position. `f(width=3, height=4)` passes by name. Library calls with many options are almost always written with keyword arguments, often one per line inside the parentheses with a trailing comma after the last one.
- **Default parameter values.** `def send(self, event=None):` means `event` is optional and is `None` if the caller leaves it out.
- **Classes** are written `class Name:`. Functions defined inside are *methods*. Every method's first parameter is `self`, which is the object the method was called on. You never pass `self` yourself: calling `thing.chat(messages)` fills in `self` with `thing`.
- **Inheritance.** `class Child(Parent):` makes a class that starts with every method of `Parent`. Inside `Parent`'s methods, `self` is still the child object, so a parent's method can call methods that only the child defines. That is how one `chat` method can serve two different backends.
- **`__init__`** (two underscores each side) is the method Python runs when you build an object. Writing `Name(x)` calls `__init__(self, x)`.
- **Attributes.** `self.something = value` stores a value on the object so other methods can read it later as `self.something`.
- **Strings** go in quotes. Python accepts single or double quotes; this app uses double quotes throughout. An **f-string** starts with `f` before the opening quote and lets you drop values in with braces: `f"Ready: {path}"`.
- **Lists** use square brackets, **dictionaries** use braces with `key: value` pairs, **tuples** use parentheses. You read from all three with square brackets: `thing[0]`, `thing["name"]`. `del things[0]` removes the first item of a list. `[a] + things` makes a new list with `a` in front.
- **Booleans** are `True` and `False`. Empty things (`""`, `[]`, `None`, `0`) count as false in an `if`.
- **Docstrings.** A string in triple double quotes as the first thing in a file, class, or function is its documentation. It goes on the line directly under the `def` or `class` line, indented like the rest of the body.
- **Comments** start with `#`.
- **Constants** are ordinary variables written in `ALL_CAPS` near the top of a file. Python does not enforce it; it is a naming habit.
- **Passing a function vs calling it.** `self.browse` (no parentheses) is the function itself, which you hand to something that will call it later. `self.browse()` calls it right now. Buttons want the first form.
- **`lambda`** writes a tiny function in place: `lambda: self.save(window, box)` is a function that, when it is called later, calls `self.save(window, box)`. Use it when a button must call a method *with* arguments.
- **Loops.** `for item in things:` runs its block once for each item. `while condition:` runs its block for as long as the condition is true. `while True:` runs until a `break` or `return` inside it.
- **Errors.** `try:` runs a block; if something in it fails, the matching `except SomeError as error:` block runs instead, with the failure in `error`. A bare `raise` inside `except` passes the same failure on unchanged.
- **Generators and `yield`.** A function that contains the word `yield` is a *generator*. Calling it does not run it; it hands back an object you can put in a `for` loop. Each trip round the loop runs the function up to its next `yield` and gives you the value written after that word. When the function ends, the loop ends. `yield from other()` hands on every value that the generator `other()` yields. This is how a reply can be handed over in pieces while the model is still writing it.
- **Blank lines.** One blank line between methods inside a class. Two blank lines between top-level classes and functions.

## Step 1: install

You need Python 3.13 and an NVIDIA graphics card with its normal driver. Everything else gets installed by a short script that you write yourself, `install.py`. It is your first Python file, so it doubles as a warm-up for steps 3 and 4.

### 1.1 Make your folder

In the repo root, make a folder named `my_build` and move into it in your terminal. Every file from here on goes there.

### 1.2 `install.py`

**What the script has to do, in order:**

1. Install **PyTorch**. The build on PyPI is CPU-only on Windows, so this one comes from PyTorch's own index, the `cu124` (CUDA 12.4) build.
2. Install **transformers**, Hugging Face's library that loads safetensors models and tokenizers on top of PyTorch. It must be version 5 or newer. The app was checked with 5.12 and 5.23.
3. Install **llama-cpp-python**, the Python wrapper around llama.cpp, for GGUF files. PyPI only has source code for Windows, which pip would try to compile. `--only-binary` forbids that, and an extra index supplies a ready-made GPU build. It is pinned to version 0.3.36.
4. Copy three **NVIDIA runtime files** that the GPU build of llama.cpp needs but does not include. PyTorch includes the same three.
5. **Check** that everything imports and that both libraries can see the graphics card.

`tkinter`, the window toolkit, comes with Python, so there is nothing to install for it.

**The modules it imports, and why each one:**

- **`subprocess`** runs another program from inside your script and waits for it to finish. The script uses it to run pip, and later to run a fresh Python for the check.
- **`sys`** gives you `sys.executable`, the full path of the `python.exe` running this script. Each pip command is run as "this Python, `-m pip`", so the libraries go into the same Python that will later run `app.py`. A bare `pip` command could belong to a different Python installed on the same machine.
- **`sysconfig`** says where this Python keeps its installed libraries: its `site-packages` folder.
- **`pathlib`** treats a file path as an object. You join path pieces with `/`.
- **`shutil`** copies files.

**Why each command is a list, not one string.** `subprocess.run` accepts a command in two shapes:

- **A list of strings.** Each string is one argument, handed straight to the program. This is the shape `install.py` uses.
- **One string with `shell=True`.** The whole line goes to Windows' command shell, `cmd.exe`, which splits it up the way a terminal would. That brings back all of the terminal's rules. A path with spaces needs quotes. `transformers>=5` must be quoted, or `cmd` reads the `>` as "send the output to a file named `=5`". Commands chain with `&&`.

The list has no shell in the way, so nothing needs quoting. Each library gets its own `subprocess.run` call. The keyword argument `check=True` stops the script at the first failure, the job `&&` did in the one-string shape.

**Now type it.**

#### 1.2.1 Top of the file and constants

1. A docstring, starting with the tag `[1.2]`. Say what the file is for and how it works: pip commands run through `subprocess` with `sys.executable`, then the copy, then the check.
2. Five imports, one per line, in alphabetical order: `pathlib`, `shutil`, `subprocess`, `sys`, `sysconfig`. Each is `import` followed by the module name.
3. A blank line, then a comment starting with `[1.2.1]` that says what the constants are. Then four constants:
   - `PIP`: a list of four items, the start of every install command. The first item is `sys.executable` (no quotes: it is a value, not text), then the strings `"-m"`, `"pip"`, `"install"`. `-m pip` means "run the pip module with this Python".
   - `STEPS`: a list of three lists, written across several lines with one inner list per line and a trailing comma after each. Each inner list is the rest of one pip command:
     - First, all on one line: `"torch"`, `"--index-url"`, `"https://download.pytorch.org/whl/cu124"`. `--index-url` replaces PyPI with PyTorch's index.
     - Second: just `"transformers>=5"`. Inside a Python string the `>` is only a character, so no extra quoting is needed.
     - Third: four strings, too long for one line. Open the bracket, put one string per line indented one more level, each followed by a comma, then close the bracket on its own line followed by a comma. The strings are `"--only-binary=llama-cpp-python"`, `"llama-cpp-python==0.3.36"`, `"--extra-index-url"`, and `"https://abetlen.github.io/llama-cpp-python/whl/cu124"`. `--extra-index-url` adds this index alongside PyPI rather than replacing it. `==0.3.36` pins that exact version: it is the one the app was tested with, and the next one, 0.3.37, crashed on the test machine's processor (see "When it does not work").
   - `CUDA_FILES`: a list of three strings, `"cudart64_12.dll"`, `"cublas64_12.dll"`, `"cublasLt64_12.dll"`.
   - `CHECK`: a string of Python code that step 1.2.4 runs as its own small program. It is too long for one line, so open a parenthesis after the `=`, put one piece of string per line, and close the parenthesis on its own line. Put no commas between the pieces: Python joins strings that sit next to each other into one. The whole string, once joined, must read `import tkinter, llama_cpp, torch, transformers; print(llama_cpp.__version__, torch.__version__, transformers.__version__, 'cuda:', torch.cuda.is_available(), 'llama gpu:', llama_cpp.llama_supports_gpu_offload())`. Break it after the `; `, after `transformers.__version__, ` and after `torch.cuda.is_available(), `. Keep each piece's trailing space, or the words run together when the pieces are joined. The labels inside it, `'cuda:'` and `'llama gpu:'`, use single quotes because the pieces themselves are in double quotes. A double quote there would end the string early.

#### 1.2.2 `install_libraries()`

Two blank lines after the constants, then a function named `install_libraries` with no parameters. Its docstring starts with `[1.2.2]`. Explain that `PIP + step` joins two lists into one complete command, and that `check=True` stops the script on a failed install.

The body is a `for` loop over `STEPS`, with `step` as the loop variable. Inside it is one line: call `subprocess.run` with two arguments. The first, positional, is `PIP + step`. The second is the keyword argument `check=True`. `+` on two lists makes a new list with the second one's items after the first one's.

#### 1.2.3 `copy_cuda_files()`

Two blank lines, then `copy_cuda_files` with no parameters. Its docstring starts with `[1.2.3]`. Explain that both libraries live in `site-packages`, so both folders are built from that one path.

1. Set `site_packages` to `pathlib.Path(...)` with one argument: `sysconfig.get_paths()["purelib"]`. `get_paths()` returns a dictionary of this Python's folders. The key `"purelib"` is the one where pip puts libraries.
2. Set `source` to `site_packages / "torch" / "lib"`.
3. Set `target` to `site_packages / "llama_cpp" / "lib"`.
4. A `for` loop over `CUDA_FILES` with the loop variable `name`. Inside it, call `shutil.copy` with two arguments: `source / name`, then `target`. Copying into a folder keeps the file's name. A file that is already there is overwritten, so running the script again is safe.

#### 1.2.4 `check()`

Two blank lines, then `check` with no parameters. Its docstring starts with `[1.2.4]`. Explain that the check runs in a new process, the way `app.py` will.

One line: call `subprocess.run` with a list of three items, `sys.executable`, `"-c"` and `CHECK`, then `check=True` as a keyword argument. `python -c "some code"` runs the code text as a program. Running it in a fresh Python proves the libraries load from scratch, rather than relying on anything this script has already done.

#### 1.2.5 `main()`

Two blank lines, then `main` with no parameters. Its docstring starts with `[1.2.5]` and says "Install, copy, then check." The body is three lines, each calling one of the functions above in that order, with empty parentheses.

#### 1.2.6 The start line

Two blank lines, then a comment starting with `[1.2.6]` that says main runs only when this file is run directly. Under it goes `if __name__ == "__main__":` with one indented line that calls `main()`. Python sets `__name__` to `"__main__"` only in the file you ran. If another file imported this one, nothing would install. `app.py` ends with the same line in step 4.

### 1.3 Run it

```bash
python install.py
```

Use the same `python` command you will use later to run `app.py`, because that is the Python the libraries go into. The first run downloads about 3 GB and takes several minutes. Later runs only print "Requirement already satisfied" and finish in seconds.

It ends with a few `ggml_cuda_init` lines naming your graphics card, then three version numbers followed by `cuda: True llama gpu: True`. If it stops early with `CalledProcessError`, scroll up: pip's own message just above says what went wrong.

## Step 2: models to test with

Download one model of each kind from Hugging Face. `install.py` has already installed the `hf` download command, which comes with transformers. None of these models needs an account. Keep models outside the repo; these commands put them in `C:\models`, and any folder works.

A small GGUF file for llama.cpp:

```bash
hf download unsloth/Qwen3.5-0.8B-GGUF Qwen3.5-0.8B-Q8_0.gguf --local-dir C:\models
```

A folder of safetensors weights for PyTorch:

```bash
hf download Qwen/Qwen3.5-2B --local-dir C:\models\Qwen3.5-2B
```

A larger GGUF file, for thinking mode and later for tools:

```bash
hf download unsloth/Qwen3.5-4B-GGUF Qwen3.5-4B-Q8_0.gguf --local-dir C:\models
```

| Backend | Path | Size |
| --- | --- | --- |
| llama.cpp | `C:\models\Qwen3.5-0.8B-Q8_0.gguf` (a file) | 0.8 GB |
| PyTorch | `C:\models\Qwen3.5-2B` (a folder) | 4.5 GB |
| llama.cpp | `C:\models\Qwen3.5-4B-Q8_0.gguf` (a file) | 4.5 GB |

The two small models are fine for chatting but tend to think for ever without answering. Use the 4B model whenever a step asks for it.

These models fit an 11 GB graphics card. The first two are the exact files this recipe was tested with. The 4B tests for levels 1 to 3 used a different Q8 build of Qwen3.5 4B. The file above was run with level 4, and passed every check there.

## Step 3: `backends.py`

This file has no UI in it at all. You can finish it and test it from a terminal before you write a single line of window code.

Its shape: a base class, `Backend`, holds what both backends share. It knows how to fit a conversation into the model's context and then stream a reply, but it cannot run a model itself. Two classes inherit from it, `LlamaCppBackend` and `TransformersBackend`, and each fills in the four things the base class needs from a real model:

- `context_size`: how many tokens the model can read at once.
- `build_prompt(messages, thinking)`: turn the conversation into the one string the model reads.
- `count_tokens(prompt)`: how many tokens that string takes up.
- `stream(prompt, temperature)`: yield the model's reply to that string, piece by piece.

### 3.1 Top of the file

*Answer key: `[3.1]` in `backends.py` (it appears twice, on the module docstring and on the constants).*

1. Start with a **module docstring** on the very first line. Begin it with the tag `[3.1]`, then say in your own words what the file is and how it works: a base class, two backends built on it that look the same from outside, so the window never needs to know which one it has. Add that both `chat` methods are generators, and what that means.
2. Leave a blank line, then one import: `threading`. It is part of Python itself, and step 3.4.4 uses it.
3. Leave a blank line, then a comment line starting with the tag `[3.1]` that says these are the settings the backends use. Under it define two constants, each with a short comment after it on the same line:
   - `MAX_NEW_TOKENS`, set to the integer `4096`. This caps how long a reply can be. Thinking mode needs plenty of room, which is why it is this large.
   - `SMALLEST_CONTEXT`, set to the integer `4096`. If not even this much context fits on the graphics card, loading gives up.
4. The model libraries (`llama_cpp`, `torch`, `transformers`) are **not imported at the top of this file**. That is deliberate, and 3.3.1 explains why.

### 3.2 The class `Backend`

*Answer key: `[3.2]`.*

Define a class named `Backend`. It takes nothing in parentheses after its name.

**Docstring:** start with `[3.2]`. Say that a model can only read a limited number of tokens at once (its context size), that `chat` first builds the prompt and forgets the oldest messages while it is too long, then streams the reply, and that this class never runs a model itself: each subclass supplies `context_size`, `build_prompt`, `count_tokens` and `stream`.

It has two methods.

#### 3.2.1 Method `chat`

*Answer key: `[3.2.1]`.*

Parameters: `self`, `messages`, `system_prompt`, `temperature` and `thinking`.

`messages` is a list of dictionaries. Each dictionary has two keys, `"role"` and `"content"`, both with string values. The role is `"user"` or `"assistant"`. This is the same shape every chat API uses. `system_prompt` is a string (possibly empty), `temperature` is a number, and `thinking` is `True` or `False`.

**Docstring:** start with `[3.2.1]`. Describe the parameters, and say that `yield from` passes on every piece `stream` yields, which makes this method a generator too.

1. Call `self.fit_to_context` with `messages`, `system_prompt` and `thinking`, and store the result as `prompt`.
2. On the next line write `yield from`, then a call to `self.stream` with `prompt` and `temperature`.

#### 3.2.2 Method `fit_to_context`

*Answer key: `[3.2.2]`.*

Parameters: `self`, `messages`, `system_prompt` and `thinking`.

This is the trimming. It builds the prompt and checks its size. If it is too big, it deletes the oldest message from `messages` *itself* (not a copy), so the deleted message stays gone and is never counted again. Room for the reply is set aside first.

**Docstring:** start with `[3.2.2]`. Say what it does, that deletions are made to `messages` itself so they last, and that a conversation must start with something the user said, so leftover replies at the front go too. Add that the newest message is never deleted, even if it is too long on its own: llama.cpp then reports an error if the prompt fills the whole context, and PyTorch tries anyway.

1. Work out how much to set aside for the reply: the smaller of `MAX_NEW_TOKENS` and half the context (`self.context_size // 2`), using `min(...)`. Store it as `reserve`. Without the half, a model with a small context would have no room left at all. Then set `room` to `self.context_size` minus `reserve`.
2. Start a `while True:` loop. Everything below is inside it.
3. Set a variable named `full` to `messages`.
4. `if system_prompt:` (that is, if it is not empty), set `full` to a new list: a list holding one dictionary, with `"role"` set to `"system"` and `"content"` set to `system_prompt`, plus `messages`. Use `+` to join the two lists.
5. Call `self.build_prompt` with `full` and `thinking`, and store the result as `prompt`.
6. Write an `if` with two conditions joined by `or`: the result of `self.count_tokens(prompt)` is less than or equal to (`<=`) `room`, **or** the length of `messages` (`len(messages)`) equals `1`. Inside it, `return prompt`. The second condition is the safety catch: the newest message alone is never deleted.
7. After that `if` (still inside the loop), delete the oldest message with `del messages[0]`.
8. Then a second, inner `while` loop: as long as the role of `messages[0]` is not equal to (`!=`) `"user"`, `del messages[0]` again. This removes replies left at the front.

The loop then goes round and checks again.

### 3.3 The class `LlamaCppBackend`

*Answer key: `[3.3]`.*

Define a class named `LlamaCppBackend` that inherits from `Backend`: put `Backend` in parentheses after the name.

**Docstring:** start with `[3.3]`. Say that it runs a single `.gguf` file through llama.cpp, and what the file carries: the weights, the chat template, and the longest context the model was trained for. Say that it loads with as much context as the card can hold, uses the template to build one prompt string, and streams what llama.cpp writes after it.

It has four methods.

#### 3.3.1 Method `__init__`

*Answer key: `[3.3.1]`.*

Parameters: `self` and `model_path`.

**Docstring:** start with `[3.3.1]`. Say that a quick first load reads only the file's information, that the real load starts at the longest trained context, that llama.cpp sets aside memory for the whole context up front so a too-large context fails to load and is halved and tried again (as long as half is not below `SMALLEST_CONTEXT`), and that any other kind of failure is passed straight on.

1. Straight after the docstring come two imports, with a comment above them: from the module `llama_cpp`, import `Llama`; and from `llama_cpp.llama_chat_format`, import `Jinja2ChatFormatter`. Putting imports inside the method instead of at the top of the file means they only run when someone actually builds this backend, so the app still starts if `llama-cpp-python` is not installed. The comment should say so.
2. Leave a blank line. Build a `Llama` with three keyword arguments, `model_path` set to `model_path`, `vocab_only` set to `True` and `verbose` set to `False`, and store it as `info`. `vocab_only` reads the file's information and vocabulary without the weights, so it is quick. It prints one harmless line about `n_ctx_train` to the terminal.
3. `info.metadata` is a dictionary of everything the file says about itself. Read the key `"general.architecture"` from it and store it as `architecture`.
4. The trained context is stored under a key named after the architecture, such as `qwen35.context_length`. Build that key with an f-string (`architecture` in braces, then `.context_length`), read it from `info.metadata`, turn the result into a whole number with `int(...)`, and store it as `size`.
5. Leave a blank line. Start a `while True:` loop. Inside it, a `try:` block. Inside the `try`:
   - Build a `Llama` and store it as `self.llm`. Pass four keyword arguments, one per line, each with a short comment where helpful: `model_path` set to `model_path`, `n_ctx` set to `size`, `n_gpu_layers` set to `-1` (which means "put every layer on the GPU"), and `verbose` set to `False`.
   - Then `break`, to leave the loop.
6. After the `try` block, `except ValueError as error:`. Inside it:
   - An `if` with two conditions joined by `or`: the text `"llama_context"` is not in `str(error)` (write `not in`), **or** half the size (`size // 2`) is less than `SMALLEST_CONTEXT`. Inside it, a bare `raise`. A context that will not fit fails with the message "Failed to create llama_context"; anything else is a different problem, so it is passed on. Checking half the size, not the size itself, means the loop never tries a context below `SMALLEST_CONTEXT`, whatever number it started from.
   - After that `if`, halve the size: set `size` to `size // 2`. Two slashes divide and drop any fraction.
7. After the loop (back at the method's own indentation), store `size` as `self.context_size`.
8. Leave a blank line. The chat template needs the text of the model's end and start markers. Call `info.detokenize` with a list containing `info.token_eos()` and the keyword argument `special` set to `True`, and store it as `end_token`. Do the same with `info.token_bos()` and store it as `start_token`. These come back as bytes, not strings.
9. Build a `Jinja2ChatFormatter` and store it as `self.formatter`. Three keyword arguments, one per line:
   - `template` set to `info.metadata` read with the key `"tokenizer.chat_template"`.
   - `eos_token` set to `end_token.decode("utf-8", errors="ignore")`, which turns the bytes into a string.
   - `bos_token` set to the same, made from `start_token`.

#### 3.3.2 Method `build_prompt`

*Answer key: `[3.3.2]`.*

Parameters: `self`, `messages` and `thinking`.

**Docstring:** start with `[3.3.2]`. Say that the formatter fills in the model's own chat template, that `enable_thinking` is a setting many templates (Qwen's among them) read to decide whether the model thinks first, and that templates that do not know it ignore it.

1. Call `self.formatter` as if it were a function, with two keyword arguments: `messages` set to `messages` and `enable_thinking` set to `thinking`. It hands back an object whose `.prompt` attribute is the finished string. `return` that attribute, in one line.

#### 3.3.3 Method `count_tokens`

*Answer key: `[3.3.3]`.*

Parameters: `self` and `prompt`.

**Docstring:** start with `[3.3.3]`. Say that `tokenize` needs bytes, so the text is encoded first, and that `special=True` counts markers such as `<|im_start|>` as the single tokens they really are.

1. Call `self.llm.tokenize` with `prompt.encode("utf-8")` as its positional argument and two keyword arguments, `add_bos` set to `False` and `special` set to `True`. Store the result, a list of token numbers, as `tokens`.
2. `return` the length of `tokens`.

#### 3.3.4 Method `stream`

*Answer key: `[3.3.4]`.*

Parameters: `self`, `prompt` and `temperature`. This method is a **generator**.

**Docstring:** start with `[3.3.4]`. Say that with `stream=True`, `create_completion` hands back a series of small chunks instead of one finished answer, where each chunk's new text sits, and that empty pieces are skipped.

1. Call `self.llm.create_completion` and store what comes back as `chunks`. One positional argument, `prompt`, then three keyword arguments, one per line: `max_tokens` set to `MAX_NEW_TOKENS`, `temperature` set to `temperature`, and `stream` set to `True`.
2. Write a `for` loop over `chunks`, naming the loop variable `chunk`. Inside it:
   - The new text lives under key `"choices"`, then index `0`, then key `"text"`. Chain three sets of square brackets to reach it and store it as `text`.
   - `if text:` then `yield text`.

There is no `return` line. The generator ends when the loop ends.

### 3.4 The class `TransformersBackend`

*Answer key: `[3.4]`.*

Define a class named `TransformersBackend` that also inherits from `Backend`. Same four methods, same parameters, different insides.

**Docstring:** start with `[3.4]`. Say that it runs a folder of safetensors weights through PyTorch, and how: a tokenizer turns text into numbers, the model predicts more numbers, and the tokenizer turns them back into text.

#### 3.4.1 Method `__init__`

*Answer key: `[3.4.1]`.*

Parameters: `self` and `model_path`.

Here `model_path` is a **folder**, not a file. The folder holds `config.json`, the tokenizer files, and one or more `.safetensors` weight files.

**Docstring:** start with `[3.4.1]`. Say that it loads the tokenizer and the model from the folder, moves the model to the graphics card if there is one, and reads the longest trained context from the model's config.

1. Two imports inside the method: import `torch`, and from `transformers` import two names on one line, `AutoModelForCausalLM` and `AutoTokenizer`.
2. Decide which device to use. Write an `if` / `else`: if `torch.cuda.is_available()` returns true, set `self.device` to the string `"cuda"`; otherwise set it to `"cpu"`.
3. Load the tokenizer: call `AutoTokenizer.from_pretrained` with `model_path` as its one positional argument, and store the result as `self.tokenizer`. Note there is no `()` after `AutoTokenizer`. `from_pretrained` is a method you call on the class itself, and it builds the object for you.
4. Load the model the same way: call `AutoModelForCausalLM.from_pretrained` with `model_path` as the positional argument and one keyword argument, `dtype` set to the string `"auto"`. That means "keep the number format the weights were saved in", usually 16-bit, rather than 32-bit, which would take twice the memory. Store it as `self.model`. In transformers 5, `"auto"` is already the default, so writing it out only makes the choice visible; older versions loaded 32-bit unless told otherwise.
5. Move the model onto the device: call `.to` on `self.model`, passing `self.device`. You do not need to store the result.
6. Leave a blank line. Some models keep their text settings in a section of their config. Call `self.model.config.get_text_config()` and store the result as `text_config`. Then set `self.context_size` to `text_config.max_position_embeddings`, the longest context the model was trained for.

#### 3.4.2 Method `build_prompt`

*Answer key: `[3.4.2]`.*

Parameters: `self`, `messages` and `thinking`.

**Docstring:** start with `[3.4.2]`. Say that `apply_chat_template` fills in the chat template, that `tokenize=False` asks for text rather than token numbers, that `add_generation_prompt` adds the "your turn" marker, and that extra settings such as `enable_thinking` are handed to the template.

1. `return` the result of calling `self.tokenizer.apply_chat_template` with `messages` as the positional argument and three keyword arguments, one per line: `add_generation_prompt` set to `True`, `tokenize` set to `False`, and `enable_thinking` set to `thinking`.

#### 3.4.3 Method `count_tokens`

*Answer key: `[3.4.3]`.*

Parameters: `self` and `prompt`.

**Docstring:** start with `[3.4.3]`. Say that calling the tokenizer on text gives back a dictionary whose `"input_ids"` are the token numbers, and that `add_special_tokens=False` stops it adding markers the template has already written.

1. Call `self.tokenizer` as a function with `prompt` and the keyword argument `add_special_tokens` set to `False`. Store the result as `tokens`.
2. `return` the length of `tokens` read with the key `"input_ids"`.

#### 3.4.4 Method `stream`

*Answer key: `[3.4.4]`.*

Parameters: `self`, `prompt` and `temperature`. This is a generator too.

The difficulty here is that the model's `generate` method does not return until the whole reply is written. To get words out while it is still working, you give it a **streamer** to write into, run `generate` on its own thread, and read from the streamer on this one.

**Docstring:** start with `[3.4.4]`. Name the four stages: turn the prompt into token numbers, make a streamer, start `generate` on its own thread, pass each piece on. Then put a one-line comment above each stage in the body, starting `Stage 1:`, `Stage 2:` and so on (no tag needed on these).

1. The first line after the docstring is an import: from `transformers`, import `TextIteratorStreamer`.
2. **Stage 1.** Call `self.tokenizer` as a function with `prompt` and two keyword arguments, `add_special_tokens` set to `False` and `return_tensors` set to the string `"pt"` (PyTorch tensors). Store the result as `inputs`.
3. Still Stage 1: reassign `inputs` to the result of calling `.to` on it with `self.device`. For this particular object, `.to` moves the data where it sits and hands back the same object, so storing the result changes nothing here. Store it anyway, because that is the safe habit: on a plain PyTorch tensor, `.to` leaves the original where it is and hands back a moved copy.
4. **Stage 2.** Build a `TextIteratorStreamer` and store it as `streamer`. One positional argument, `self.tokenizer`, then two keyword arguments, each with a short comment:
   - `skip_prompt` set to `True`, so it does not repeat the conversation back to you.
   - `skip_special_tokens` set to `True`, so markers like end-of-turn are left out.
5. **Stage 3.** Put a second comment line under the Stage 3 comment saying that a temperature of 0 means "always pick the likeliest word" and anything higher samples. Then collect the arguments for `generate` in a dictionary:
   - Create a variable named `settings` by calling `dict` on `inputs`. That copies everything in `inputs` into an ordinary dictionary.
   - Add a key to it: `settings`, square brackets around the string `"max_new_tokens"`, set equal to `MAX_NEW_TOKENS`.
   - Add another the same way: the key `"streamer"`, set to `streamer`.
   - `if temperature > 0:` set the key `"do_sample"` to `True` and the key `"temperature"` to `temperature`. `else:` set `"do_sample"` to `False`.
6. Still Stage 3: create a `threading.Thread` with three keyword arguments: `target` set to `self.model.generate` (no parentheses, you are handing over the method), `kwargs` set to `settings`, and `daemon` set to `True`. Store it as `thread`. `kwargs` means "call the target with these as keyword arguments". Then call `.start()` on `thread`.
7. **Stage 4.** Write a `for` loop over `streamer`, naming the loop variable `text`. Inside it, write `if text:` and inside that, `yield text`. Some pieces arrive empty, and the `if` skips them. The loop ends on its own when `generate` finishes.

### 3.5 The function `load_backend`

*Answer key: `[3.5]`.*

Back at zero indentation (outside all three classes), define a function named `load_backend` with two parameters: `kind` and `model_path`.

**Docstring:** start with `[3.5]`. Say that it builds and returns the backend named by `kind`, and that this is the only place that knows both classes exist; everything else just loops over `chat`.

1. If `kind` equals the string `"llama_cpp"` (equality is two equals signs), `return` a new `LlamaCppBackend` built with `model_path`.
2. If `kind` equals the string `"pytorch"`, `return` a new `TransformersBackend` built with `model_path`.
3. If neither matched, `raise` a `ValueError` whose message is an f-string reading `Unknown backend: ` followed by `kind` in braces. Because each branch above returns, you can write plain `if`s with no `else`: reaching this line already means nothing matched.

### 3.6 Checkpoint: test it without a window

From inside `my_build/`, start the Python prompt by running `python` with no arguments. Then, one line at a time:

1. From `backends`, import `load_backend`.
2. Call it with two arguments, the kind string and the full path to a model from step 2, and store the result in a variable. The kind is `"llama_cpp"` for the `.gguf` file and `"pytorch"` for the folder. Put an `r` before the opening quote of a Windows path so the backslashes are taken literally.
3. Print the variable's `context_size` attribute. For the test models it should be `262144`.
4. Make a list containing one dictionary, with `"role"` set to `"user"` and `"content"` set to a question, and store it in a variable.
5. Write a `for` loop over a call to `.chat` on your backend variable. Pass four arguments: your list, an empty string for the system prompt, `0.7` for the temperature, and `False` for thinking. Inside the loop, call `print` with the loop variable and two keyword arguments: `end` set to an empty string (so each piece continues on the same line) and `flush` set to `True` (so it shows at once). At the Python prompt, press Enter on an empty line to run the loop.

If a sentence types itself out a few characters at a time, this file is done. Do it once for each kind.

Both backends print some harmless lines to the terminal. llama.cpp prints one line ending `possible training context overflow` during the quick first load. The PyTorch backend prints a "fast path is not available" notice, some `[ERROR] ... not documented` lines, and "Setting `pad_token_id`" (plus a note about generation flags when the temperature is 0). Loading the PyTorch model takes about 25 seconds; the GGUF takes about 2. The answer key prints all of these too.

## Step 4: `app.py`

The window is built with `tkinter`, which comes with Python.

Before you start, understand the one hard idea in this file. Loading a model and generating a reply are slow. If you do slow work directly inside a button's function, the window freezes until it finishes. So slow work runs on a second **thread**. But tkinter is built around the main thread, the one that created the window. Python can pass widget calls over to it from other threads, but that is fragile, so this app follows a strict rule: only the main thread ever touches a widget. The bridge between the two is a **queue**: the worker thread puts its results into the queue, and the main thread checks the queue twenty times a second and updates the window. Steps 4.10 to 4.13 exist only to do that.

Streaming rides on the same queue. Instead of one result per reply, the worker puts in one small result per piece of text, and a last one to say the reply is finished.

The same rule decides where settings are read. The system prompt, the temperature and the thinking switch all live in widgets, so `send` reads them on the main thread and hands the worker plain values.

### Run it as you go

Step 4 is about 300 lines. Do not type all of them before the first run: a mistake is far easier to find in the twenty lines you just typed than in three hundred. Three checkpoints below, after steps 4.4, 4.8 and 4.11, say when to run `python app.py` and what you should see. They rely on two tricks.

**Type the ending early.** At the first checkpoint you skip ahead and type steps 4.16 and 4.17, `main` and the last two lines, at the bottom of the file. They stay at the bottom. Every method you type afterwards goes above them, inside the class.

**Stand-ins.** `build_widgets` hands `self.browse`, `self.load_model` and other methods to buttons, and Python looks each one up at that moment. A method that does not exist yet stops the window from opening. So until you reach a method's own step, give it a stand-in: its `def` line with the right parameters, and a body of one word, `pass`, which does nothing. When you reach the method's step, replace the stand-in with the real thing. Each checkpoint says which stand-ins it needs.

### 4.1 Top of the file

*Answer key: `[4.1]` in `app.py` (it appears twice, on the module docstring and on the constants).*

1. A module docstring. Start with `[4.1]`, then say what the file is, how it works (one class for the window, slow work on a second thread, results coming back through a queue, replies arriving a few characters at a time), and how to run it.
2. Imports, in this order:
   - `queue`
   - `threading`
   - `tkinter`, renamed to `tk` with the `as` keyword, so you can write `tk.Button` instead of `tkinter.Button`.
   - From `tkinter`, import two submodules on one line: `filedialog` and `scrolledtext`.
   - A blank line, then from your own `backends` file, import `load_backend`. No `.py` in the name.
3. A comment line starting with the tag `[4.1]` that says these are timing and the starting values of the settings. Under it, three constants, the first two with a short comment after them on the same line:
   - `POLL_INTERVAL_MS`, set to `50`.
   - `DEFAULT_TEMPERATURE`, set to `0.7`.
   - `DEFAULT_THINKING_INSTRUCTIONS`, set to the string `"Think through the question step by step before you answer."`. A long string can sit inside parentheses on its own line.

### 4.2 The class `ChatApp`

*Answer key: `[4.2]`.*

Define a class named `ChatApp`.

**Docstring:** start with `[4.2]`. Say that it is the whole window. Then, setting aside the setup methods (`__init__`, `build_widgets`) and the three small helpers (`start_worker`, `append_chat`, `set_busy`), describe the three groups the other methods fall into: button handlers that run on the main thread (`browse`, `open_thinking_window`, `save_thinking_instructions`, `load_model`, `send`), workers that run on a second thread (`load_worker`, `reply_worker`), and `poll_results`, which carries the workers' results back.

Steps 4.3 to 4.15 are its methods, in order.

### 4.3 Method `__init__`

*Answer key: `[4.3]`.*

Parameters: `self` and `root`. `root` is the main window object, which `main` will create and pass in.

**Docstring:** start with `[4.3]`. Say that it sets up the window, the starting state, and the queue check, and that every attribute the other methods rely on exists by the time it finishes: the state is created here, and the widgets in `build_widgets`, which it calls.

1. Store `root` as `self.root`.
2. Call `title` on `self.root` with the string `"VoxMux"`.
3. Call `geometry` on `self.root` with the string `"800x600"` (width, a lowercase x, height).
4. Create six attributes that hold the app's state. Put a short comment after each of the first five, on the same line.
   - `self.backend`, set to `None`. It will hold the loaded model.
   - `self.model_path`, set to an empty string. It will hold what the user picked.
   - `self.messages`, set to an empty list. It will hold the whole conversation.
   - `self.busy`, set to `False`. It is `True` while a worker thread is running.
   - `self.results`, set to a new `queue.Queue()`. This is how worker threads report back.
   - `self.thinking_instructions`, set to `DEFAULT_THINKING_INSTRUCTIONS`.
5. Call `self.build_widgets()`.
6. Call `self.poll_results()`. This starts the twenty-times-a-second check, which then keeps itself going.

### 4.4 Method `build_widgets`

*Answer key: `[4.4]`, with one tagged comment per block: `[4.4.1]` to `[4.4.6]`.*

Parameters: just `self`.

**Docstring:** start with `[4.4]`. Say that it creates every widget and places it, and that the order things are packed in is the layout.

Every tkinter widget follows the same two-step pattern. First you **create** it, passing its parent as the first positional argument and options as keyword arguments. Then you **place** it by calling `.pack(...)` on it. If you need to talk to the widget later, store it on `self` first and pack on the next line. If you never need it again, you can create and pack in one chained expression.

Build these six blocks in this order. Put a comment above each block starting with its tag.

#### 4.4.1 The top row

1. Create a `tk.Frame` whose parent is `self.root`. Store it in a local variable named `top` (not on `self`, nothing else needs it). A frame is an invisible box for grouping widgets.
2. Pack `top` with `fill` set to `"x"` (stretch horizontally), and `padx` and `pady` both set to `8`.
3. Create a `tk.StringVar` with the keyword argument `value` set to `"llama_cpp"`, and store it as `self.backend_kind`. A `StringVar` is a little box holding a string that widgets can share. Whichever radio button is selected writes its value into it. Put a two-line comment above it saying so.
4. Create a `tk.Radiobutton` with parent `top` and three keyword arguments: `text` set to `"llama.cpp (GGUF)"`, `variable` set to `self.backend_kind`, and `value` set to `"llama_cpp"`. Chain `.pack` straight onto it with `side` set to `"left"`.
5. Create a second `tk.Radiobutton` the same way: `text` is `"PyTorch (safetensors)"`, same `variable`, and `value` is `"pytorch"`. Pack it to the left too. These two value strings must match the ones `load_backend` checks for, exactly.
6. Create a `tk.Button` with parent `top`, `text` set to `"Browse..."`, and `command` set to `self.browse` (no parentheses: you are handing over the method, not calling it). Chain `.pack` with `side` set to `"left"` and `padx` set to `8`.
7. Create another `tk.Button` with parent `top`, `text` set to `"Load"`, and `command` set to `self.load_model`. This one you need later, so store it as `self.load_button`, then pack it on the next line with `side` set to `"left"`.

#### 4.4.2 The settings row

1. Create a `tk.Frame` with parent `self.root`, stored in a local variable named `settings`, and pack it with `fill` set to `"x"` and `padx` set to `8`.
2. Create a `tk.Label` with parent `settings` and `text` set to `"Temperature"`, and chain `.pack` with `side` set to `"left"`.
3. Create a `tk.DoubleVar` (a box holding a decimal number) with `value` set to `DEFAULT_TEMPERATURE`, and store it as `self.temperature`.
4. Create a `tk.Scale` (a slider) with parent `settings` and six keyword arguments: `variable` set to `self.temperature`, `from_` set to `0` (the trailing underscore is because `from` on its own is a Python keyword), `to` set to `2`, `resolution` set to `0.1`, `orient` set to `"horizontal"`, and `length` set to `160`. Chain `.pack` with `side` set to `"left"` and `padx` set to the tuple `(4, 16)`.
5. Create a `tk.BooleanVar` with `value` set to `False`, and store it as `self.thinking`.
6. Create a `tk.Checkbutton` with parent `settings`, `text` set to `"Thinking mode"`, and `variable` set to `self.thinking`. Chain `.pack` with `side` set to `"left"`. Ticking the box sets the variable to `True`.
7. Create a `tk.Button` with parent `settings`, `text` set to `"Thinking instructions..."`, and `command` set to `self.open_thinking_window`. Chain `.pack` with `side` set to `"left"` and `padx` set to `8`.

#### 4.4.3 The system prompt box

1. Create a `tk.Label` with parent `self.root`, `text` set to `"System prompt:"`, and `anchor` set to `"w"`. Chain `.pack` with `fill` set to `"x"`, `padx` set to `8`, and `pady` set to the tuple `(8, 0)`.
2. Create a `tk.Text` (a box that holds several lines) with parent `self.root`, `height` set to `3` (lines), and `wrap` set to `"word"`. Store it as `self.system_box`.
3. Pack it with `fill` set to `"x"` and `padx` set to `8`.

#### 4.4.4 The status line

1. Create a `tk.Label` with parent `self.root`, `text` set to `"No model loaded."`, and `anchor` set to `"w"` (west, so the text hugs the left edge). Store it as `self.status`.
2. Pack it with `fill` set to `"x"`, `padx` set to `8`, and `pady` set to the tuple `(8, 0)`.

#### 4.4.5 The bottom row

This is built before the chat log on purpose: tkinter gives space to widgets in the order they are packed, so packing this first keeps it visible when the window shrinks. Say so in this block's comment.

1. Create a `tk.Frame` with parent `self.root`, stored in a local variable named `bottom`.
2. Pack it with `side` set to `"bottom"`, `fill` set to `"x"`, and `padx` and `pady` both `8`.
3. Create a `tk.Entry` (a one-line text box) with parent `bottom`. Store it as `self.entry`.
4. Pack it with `side` set to `"left"`, `fill` set to `"x"`, and `expand` set to `True`, so it takes all the width the Send button does not need.
5. Call `bind` on `self.entry` with two positional arguments: the string `"<Return>"` (angle brackets included) and `self.send`. Now pressing Enter in the box calls `send`.
6. Create a `tk.Button` with parent `bottom`, `text` set to `"Send"`, and `command` set to `self.send`. Store it as `self.send_button`.
7. Pack it with `side` set to `"left"` and `padx` set to the tuple `(8, 0)`, meaning 8 pixels of space on its left and none on its right.

#### 4.4.6 The chat log

1. Create a `scrolledtext.ScrolledText` with parent `self.root`, `wrap` set to `"word"` (break lines between words), and `state` set to `"disabled"` (read-only, so the user cannot type into the history). Store it as `self.chat_log`.
2. Pack it with `fill` set to `"both"`, `expand` set to `True`, and `padx` and `pady` both `8`. It takes whatever space is left.

### Checkpoint 1: the window opens

1. Skip ahead and type steps 4.16 and 4.17 now, at the bottom of the file.
2. Inside the class, below `build_widgets`, add five stand-ins:
   - `browse`, `open_thinking_window`, `load_model` and `poll_results`, each with the one parameter `self`.
   - `send`, with the parameters `self` and `event=None`. Step 4.9 explains the default.
3. Run `python app.py` from inside `my_build/`.

The window should open with two radio buttons, Browse and Load; a Temperature slider, a Thinking mode box and a Thinking instructions button; a System prompt box; the status line "No model loaded."; an empty log; and an entry box with Send. Drag the window smaller: the entry box and Send stay visible at the bottom. The buttons do nothing yet.

If no window opens, the last line of the error in the terminal names the problem, and the lines above it name the line of your file. Close the window before you go on.

### 4.5 Method `browse`

*Answer key: `[4.5]`.*

Parameters: just `self`. Runs when the Browse button is clicked.

**Docstring:** start with `[4.5]`. Say that it lets the user pick a model and remembers the path, and why there are two kinds of picker: a GGUF model is one file, a safetensors model is a whole folder.

1. Read which backend is selected by calling `.get()` on `self.backend_kind`, and compare it to `"llama_cpp"` in an `if`.
2. If it matches, call `filedialog.askopenfilename` with one keyword argument, `filetypes`, set to a list containing one tuple of two strings: a label, `"GGUF model"`, and a pattern, `"*.gguf"`. Store the result in a local variable named `path`.
3. In the `else`, call `filedialog.askdirectory` with no arguments and store the result in `path`.
4. Both dialogs give back something empty if the user cancels (an empty string, on Windows), and anything empty counts as false. So write `if path:` and inside it:
   - Store `path` as `self.model_path`.
   - Update the status label: call `.config` on `self.status` with `text` set to an f-string reading `Selected:`, a space, then `path` in braces.

From here on, "set the status text to X" always means this same call: `.config` on `self.status` with `text` set to X. And wherever a status message has a label like `Ready:` or `Error:`, put one space after the colon.

### 4.6 Method `open_thinking_window`

*Answer key: `[4.6]`.*

Parameters: just `self`. Runs when the Thinking instructions button is clicked.

**Docstring:** start with `[4.6]`. Say that a `Toplevel` is a second window belonging to the main one, that it holds a text box filled with the current instructions and a Save button, and why the button's command is a `lambda`: it has to tell `save_thinking_instructions` which window and which box to use.

1. Create a `tk.Toplevel` with parent `self.root` and store it in a local variable named `window`. Call `title` on it with `"Thinking mode instructions"`.
2. Create a `tk.Label` with parent `window`, `text` set to `"Added to the system prompt whenever Thinking mode is on:"`, and `anchor` set to `"w"`. Chain `.pack` with `fill` set to `"x"`, `padx` set to `8`, and `pady` set to `(8, 0)`.
3. Create a `tk.Text` with parent `window`, `width` set to `60`, `height` set to `8`, and `wrap` set to `"word"`. Store it in a local variable named `box`, and pack it with `fill` set to `"both"`, `expand` set to `True`, and `padx` and `pady` both `8`.
4. Fill the box: call `.insert` on `box` with `"1.0"` (line 1, character 0, the very start) and `self.thinking_instructions`.
5. Create a `tk.Button` with parent `window`, `text` set to `"Save"`, and `command` set to a `lambda` with no parameters that calls `self.save_thinking_instructions` with `window` and `box`. Chain `.pack` with `pady` set to `(0, 8)`.

### 4.7 Method `save_thinking_instructions`

*Answer key: `[4.7]`.*

Parameters: `self`, `window` and `box`. Runs when that Save button is clicked.

**Docstring:** start with `[4.7]`. Say that a `Text` widget's contents run from `"1.0"` to `"end"`, and that Tk always adds a newline at the end, so the text is stripped before it is kept.

1. Call `.get` on `box` with `"1.0"` and `"end"`, chain `.strip()` onto it, and store the result as `self.thinking_instructions`.
2. Call `.destroy()` on `window` to close it.

### 4.8 Method `load_model`

*Answer key: `[4.8]`.*

Parameters: just `self`. Runs when the Load button is clicked.

**Docstring:** start with `[4.8]`. Say that it only *starts* the loading: it greys out the buttons, updates the status, hands the slow part to a thread, and returns at once.

1. Guard first. If `self.model_path` is empty (`if not self.model_path:`), set the status text to `"Pick a model with Browse first."` and then write a bare `return` to leave the method early.
2. Call `self.set_busy` with `True`.
3. Set the status text to `"Loading model..."`.
4. Call `self.start_worker` with three positional arguments: `self.load_worker` (the method itself, no parentheses), the result of `self.backend_kind.get()`, and `self.model_path`.

### Checkpoint 2: Browse, the instructions window, and the Load guard

`browse`, `open_thinking_window` and `load_model` are real now. `send` and `poll_results` are still stand-ins. Run the app and check, in this order:

1. Click Load before anything else. The status line says "Pick a model with Browse first."
2. Click Thinking instructions..., change the text, and click Save. The small window closes. Open it again: your text is there.
3. Click Browse with llama.cpp selected. A file picker opens, filtered to `.gguf`. Pick a model: the status line says `Selected:` and its path. Select PyTorch and click Browse again: this time it is a folder picker.

Do not click Load now that a model is picked. `set_busy` and `start_worker` do not exist yet, so nothing would happen in the window and the terminal would show an `AttributeError`.

### 4.9 Method `send`

*Answer key: `[4.9]`.*

Parameters: `self`, and `event` with a default value of `None`.

Why the default? This method gets called two ways. The Send button calls it with no arguments. The Enter key binding calls it with one argument, an event object describing the keypress. A default lets one method serve both. You never use `event`; it just has to be accepted.

**Docstring:** start with `[4.9]`. Say that it adds the user's message and asks for a reply, explain the `event` parameter, say that every setting is read from its widget here, on the main thread, and handed to the worker as plain values, and note that it writes the label `Model: ` with nothing after it, ready for the reply's words.

1. Read the entry box by calling `.get()` on `self.entry`, chain `.strip()` onto that to remove spaces from both ends, and store the result as `text`.
2. Guard: if `text` is empty, **or** `self.backend` is `None`, **or** `self.busy` is true, `return` early. Use `not text` for the first test, `is None` for the second, and join the three with the word `or`.
3. Leave a blank line. Read the settings:
   - Call `.get` on `self.system_box` with `"1.0"` and `"end"`, chain `.strip()`, and store it as `system_prompt`.
   - Call `.get()` on `self.temperature` and store it as `temperature`.
   - Call `.get()` on `self.thinking` and store it as `thinking`.
4. `if thinking and self.thinking_instructions:` (both true), add the instructions to the system prompt: set `system_prompt` to `system_prompt` plus `"\n\n"` plus `self.thinking_instructions`, then on the next line set `system_prompt` to `system_prompt.strip()` (in case the system prompt box was empty).
5. Leave a blank line. Clear the entry box: call `.delete` on `self.entry` with the integer `0` and the string `"end"`.
6. Add the user's message to the conversation: call `.append` on `self.messages`, passing a dictionary with `"role"` set to `"user"` and `"content"` set to `text`.
7. Show it: call `self.append_chat` with one argument, an f-string made of: `You:`, a space, `text` in braces, two newline escapes (`\n\n`), then `Model:` and a space. Nothing comes after that last space; the reply will be added there piece by piece.
8. Leave a blank line. Call `self.set_busy` with `True`.
9. Set the status text to `"Writing a reply..."`.
10. Call `self.start_worker` with four arguments: `self.reply_worker`, `system_prompt`, `temperature` and `thinking`.

### 4.10 Method `start_worker`

*Answer key: `[4.10]`.*

Parameters: `self`, `target`, and `*args`.

The asterisk is new. `*args` in a parameter list means "collect any further positional arguments into a tuple named `args`". It lets this one helper start a worker that needs two arguments (loading) or three (replying).

**Docstring:** start with `[4.10]`. Say that it runs `target` on a new background thread so the window does not freeze, and what `daemon` means.

1. Create a `threading.Thread` with three keyword arguments: `target` set to `target`, `args` set to `args`, and `daemon` set to `True`. A daemon thread is dropped automatically when you close the window, instead of keeping the program alive. Store it in a local variable named `thread`.
2. Call `.start()` on it.

### 4.11 Method `load_worker`

*Answer key: `[4.11]`.*

Parameters: `self`, `kind`, and `model_path`. **This method runs on the worker thread, so it must not touch any widget.** It only does the slow work and puts a result in the queue.

**Docstring:** start with `[4.11]`. Say that it runs on the background thread, loads a model, and reports through the queue as a pair of a label and a value, including when something goes wrong.

1. Open a `try:` block. Inside it:
   - Call `load_backend` with `kind` and `model_path` and store the result as `backend`.
   - Call `.put` on `self.results` with **one** argument: a tuple of two things, the string `"loaded"` and `backend`. A tuple inside a call means two sets of parentheses, one for the call and one for the tuple.
2. Follow it with `except Exception as error:`. Inside:
   - Put a tuple of the string `"error"` and `str(error)` into `self.results`. `str(...)` converts the exception into its message text.

Catching `Exception` broadly is usually bad style, but here it is right. Without it, an error on the worker thread would only print a traceback in the terminal. The window would never hear about it, so the status would stay on "Loading model..." and Load and Send would stay greyed out for good. Catching it lets the error show in the status line instead.

### Checkpoint 3: loading a model

Loading needs two methods from further down before it works from end to end: `poll_results` (step 4.13), which carries the result back to the window, and `set_busy` (step 4.15). Skip ahead and type those two now, replacing the `poll_results` stand-in. The answer key keeps the methods in step order, so put them where they will end up: `reply_worker` (4.12) will go above `poll_results`, and `append_chat` (4.14) between `poll_results` and `set_busy`.

No stand-ins are left after this. Run the app and check:

1. Browse to a model and click Load. The status line says "Loading model..." and Load and Send grey out. The window still moves and resizes while it loads.
2. The status changes to "Ready:", the model's path, and "(262144 tokens of context)". Load and Send come back.
3. Select PyTorch, Browse to a folder with no model in it, and click Load. The status line shows "Error:" and a message, and the buttons come back.

Do not send a message yet. `send` is real, but the two methods it leads to, `reply_worker` and `append_chat`, are the last two you have to type: steps 4.12 and 4.14. When they are in, check 4.13 and 4.15 against what you typed at this checkpoint, then go to step 5.

### 4.12 Method `reply_worker`

*Answer key: `[4.12]`.*

Parameters: `self`, `system_prompt`, `temperature` and `thinking`. Also runs on the worker thread.

This is where the streamed pieces are turned into queue results. It keeps two strings: `reply`, everything the model has written so far, and `shown`, the part already sent to the window. After each new piece it works out what is in `reply` but not yet in `shown`, and sends just that. Comparing against a *stripped* copy of the reply means blank space at the very start or end is never shown, because trailing blank space only gets sent once real text follows it.

Thinking mode adds one twist. The model writes its reasoning first and ends it with the marker `</think>`, then writes the answer. The log shows that marker as `[end of thinking]`, and only the answer after it is kept in the conversation, so old reasoning does not eat into the context.

**Docstring:** start with `[4.12]`. Say that it streams a reply into the queue, that the whole conversation is sent every time (which is how the model remembers earlier turns, and the backend forgets the oldest if they no longer fit), how `reply` and `shown` work together, and what happens to `</think>`.

1. Open a `try:` block. Items 2 to 5 are inside it.
2. Create two variables, both set to an empty string, each with a short comment after it on the same line: `reply` and `shown`.
3. Write a `for` loop over a call to `.chat` on `self.backend`, passing four arguments: `self.messages`, `system_prompt`, `temperature` and `thinking`. Name the loop variable `piece`. Inside the loop:
   - Set `reply` to `reply` plus `piece`. The plus sign joins two strings.
   - Call `.replace` on `reply` with `"</think>"` and `"\n[end of thinking]"`, chain `.strip()` onto it, and store the result as `visible`.
   - Find where the new part begins: call `len` on `shown` to get its length in characters, and store that number as `start`, with a short comment.
   - Take the new part: slice `visible` from `start` to the end. A slice is square brackets with a colon: the start value, then a colon, then nothing. Store it as `new_text`.
   - Write `if new_text:` and inside it do two things: put the tuple `("piece", new_text)` into `self.results`, and set `shown` to `visible`.
4. After the loop, keep only the answer: call `.split` on `reply` with `"</think>"`, which gives a list of the parts between markers. Take the last part with index `-1`, chain `.strip()`, and store it as `answer`. With no marker in the reply, the list has one part, the whole reply.
5. Put the tuple `("reply", answer)` into `self.results`. This tells the main thread the reply is finished and hands over the text to keep.
6. In `except Exception as error:`, put the tuple `("error", str(error))` into `self.results`.

### 4.13 Method `poll_results`

*Answer key: `[4.13]`.*

Parameters: just `self`. Runs on the main thread, twenty times a second, for as long as the window is open. This is the other end of the queue.

**Docstring:** start with `[4.13]`. Say that it empties the queue, updates the window for each result, and then schedules itself to run again. Note that a `"piece"` means more is coming, so the buttons stay greyed out, while the other three results mean the work is over.

1. Start a `while` loop that runs as long as the queue is not empty: the condition is `not` followed by a call to `.empty()` on `self.results`.
2. Inside the loop, call `.get()` on `self.results`. It returns one of your two-item tuples. *Unpack* it into two variables on one line by writing both names separated by a comma on the left of the equals sign: `kind` and `value`.
3. Still inside the loop, a chain on `kind` with four branches: one `if` and three `elif`s.
   - If it equals `"piece"`: call `self.append_chat` with `value`. Nothing else. The reply is still coming, so the buttons must stay greyed out.
   - Else if it equals `"reply"`: append a dictionary to `self.messages` with `"role"` set to `"assistant"` and `"content"` set to `value`; call `self.append_chat` with a string of two newline escapes (`"\n\n"`) to leave a blank line before the next message; set the status text to an f-string reading `Ready:`, a space, then `self.model_path` in braces; and call `self.set_busy` with `False`.
   - Else if it equals `"loaded"`: set `self.backend` to `value`; reset `self.messages` to an empty list (a new model starts a new conversation); store `value.context_size` in a local variable named `size`; set the status text to an f-string reading `Ready:`, a space, `self.model_path` in braces, a space, then in round brackets `size` in braces followed by ` tokens of context`; and call `self.set_busy` with `False`.
   - Else if it equals `"error"`: set the status text to an f-string reading `Error:`, a space, then `value` in braces, and call `self.set_busy` with `False`.
4. Notice that `set_busy(False)` is written inside three of the branches and not after the chain. If it ran for every result, the first streamed piece would bring the Send button back while the model was still writing.
5. **Outside** the loop (back at the method's indentation), schedule the next check: call `.after` on `self.root` with two arguments, `POLL_INTERVAL_MS` and `self.poll_results` (no parentheses). This says "call this method again in 50 milliseconds". The method re-arms itself every time it runs. If you indent this line into the loop by mistake, the polling stops the first time the queue is empty, and nothing ever shows up.

### 4.14 Method `append_chat`

*Answer key: `[4.14]`.*

Parameters: `self` and `text`.

**Docstring:** start with `[4.14]`. Say that it adds text to the end of the chat log exactly as given, why it has to unlock and relock the log (read-only blocks the program as well as the user), and that the caller decides on labels and line breaks, so the same method serves a whole message and a single streamed word.

1. Call `.config` on `self.chat_log` with `state` set to `"normal"`.
2. Call `.insert` on `self.chat_log` with two arguments: the string `"end"` (where to insert) and `text`.
3. Call `.config` again with `state` set to `"disabled"`.
4. Call `.see` on `self.chat_log` with `"end"`, which scrolls to the bottom.

### 4.15 Method `set_busy`

*Answer key: `[4.15]`.*

Parameters: `self` and `busy` (a boolean).

**Docstring:** start with `[4.15]`. Say that it greys out Load and Send while work is running or brings them back, and that it saves the flag so `send` can check it.

1. Store `busy` as `self.busy`.
2. `if busy:` set a local variable `state` to the string `"disabled"`. `else:` set it to `"normal"`.
3. Call `.config` on `self.load_button` with `state` set to `state`.
4. Do the same for `self.send_button`.

### 4.16 The function `main`

*Answer key: `[4.16]`.*

Back at zero indentation, outside the class. Define a function named `main` with no parameters.

**Docstring:** start with `[4.16]`. Say that it creates the window, attaches the app, and runs until the window is closed, and what `mainloop` is: the loop that waits for clicks, keypresses and timers and calls your methods.

1. Create the main window by calling `tk.Tk()` and store it as `root`.
2. Build the app by calling `ChatApp` with `root`. You do not need to store the result.
3. Call `.mainloop()` on `root`. This line does not return until the window is closed.

### 4.17 The last two lines

*Answer key: `[4.17]`.*

The standard ending for a runnable Python file. Put a comment above it starting with `[4.17]`.

(If you followed the checkpoints, 4.16 and 4.17 are already at the bottom of your file.)

Write an `if` that compares the special variable `__name__` to the string `"__main__"` (two underscores on each side of both), and inside it call `main()`. Python sets `__name__` to `"__main__"` only in the file you ran directly, so this means "start the app if I was run, but not if I was imported".

## Step 5: run it

First, without a model. From the repo root:

```bash
python check_my_build.py my_build
```

This opens your window with a scripted stand-in for the model and clicks through it in a few seconds. Fix anything that fails before you go on: each line ends with the steps it checks.

Then, from inside `my_build/`, with a real model:

```bash
python app.py
```

Check each of these, once per backend, using the models from step 2:

1. The window opens with two radio buttons, Browse and Load; a Temperature slider, a Thinking mode box and a Thinking instructions button; a System prompt box; a status line; an empty log; and an entry box with Send.
2. Clicking Load before Browse shows "Pick a model with Browse first."
3. With llama.cpp selected, Browse opens a file picker filtered to `.gguf`. With PyTorch selected, it opens a folder picker.
4. Load shows "Loading model..." and the Load and Send buttons grey out. The window still moves and resizes while it loads. Then the status changes to "Ready: ... (262144 tokens of context)".
5. Typing a message and pressing Enter (or Send) shows your line and `Model:` straight away, with "Writing a reply..." in the status. The reply then types itself out a few characters at a time. Send stays greyed out until it is finished.
6. A second message gets an answer that shows the model remembers the first. Tell it your name in the first message and ask for it in the second.
7. Type "Always answer in French." in the System prompt box and ask a question. The answer should come in French (the smallest models do not always obey).
8. Set the temperature to 0 and ask "Name one fruit. Reply with one word." twice, each time after loading the model again. The answer should be the same both times.
9. Click Thinking instructions..., change the text, and click Save; the window closes. Tick Thinking mode and ask "What is 17 * 23?" with the 4B model. You should see its reasoning, then `[end of thinking]`, then the answer.
10. Loading a bad path shows "Error: ..." in the status line instead of crashing.

## When it does not work

| What you see | Likely cause | Look at |
| --- | --- | --- |
| `SyntaxError: unterminated string literal` when running `install.py` | A string is missing its closing quote, or has an extra one at the end of the line. A `"` left over from a `python -c "..."` command pasted from elsewhere does this. | the line the error names |
| `install.py` stops with `CalledProcessError` | One of the commands failed. Pip's own message, just above it, says why: often no internet, or a typing mistake in a package name or index address. | `[1.2.1]`, `[1.2.2]` |
| `install.py` stops with `FileNotFoundError` naming `cudart64_12.dll` | The PyTorch you have is the CPU-only build from PyPI, which was installed before the script ran. Pip saw a `torch` already there and kept it. Add `"--force-reinstall"` to the end of the torch list in `STEPS`, run the script once, then take it out again. | `[1.2.1]` |
| `IndentationError`, `AttributeError: '...' object has no attribute '...'`, or `NameError: name 'self' is not defined` | A line is at the wrong depth. Methods are indented four spaces inside the class, their bodies eight. | the step you just typed |
| `TypeError: ... takes 0 positional arguments but 1 was given` (or 1 but 2, and so on) | You left `self` out of the parameters of the method named in the message. If that method is `send`, `event=None` may be missing instead. | the step for the method named in the message (`[4.9]` for `send`) |
| `TypeError: ... missing 1 required positional argument` in the status line, or "takes 4 positional arguments but 5 were given" | A method is called with a different number of arguments than its definition has: usually `chat`, `stream` or `reply_worker`. Count them against the step. | `[3.2.1]`, `[4.9]`, `[4.12]` |
| The Browse dialog pops up by itself as the app starts, or `AttributeError: 'ChatApp' object has no attribute 'status'` at startup | You put parentheses after a method you were handing over: `command=self.browse()` or `command=self.load_model()`. That calls it on the spot instead of handing it to the button. | `[4.4.1]` |
| Send or Enter does nothing even with a model loaded | The same mistake in the bottom row: `command=self.send()`, or `self.send()` in the `bind` call. | `[4.4.5]` |
| Clicking Thinking instructions... shows no window, and the terminal shows `TclError: bad window path name` | The Save button's `command` calls `self.save_thinking_instructions(window, box)` directly instead of inside a `lambda`, so it runs while the window is being built and closes it before the button can be added. | `[4.6]` |
| The window freezes while loading | You called the worker method directly instead of handing it to `start_worker`. | `[4.8]`, `[4.10]` |
| The model loads but the status stays on "Loading model..." | `poll_results` is not re-arming: the `.after` line is missing or indented into the `while` loop. | `[4.13]` |
| "Error: Unknown backend: ..." | A radio button's `value` does not match the strings in `load_backend`. | `[4.4.1]`, `[3.5]` |
| The model seems to load, but the status stays on "Loading model..." and the terminal shows `AttributeError: '...Backend' object has no attribute 'context_size'` | `__init__` never stores `self.context_size`, so `poll_results` fails when it reads it and stops checking the queue. | `[3.3.1]`, `[3.4.1]`, `[4.13]` |
| "Error: Failed to load model from file" | The file is not a chat model. Files whose names start with `mmproj-` are add-ons for image input, not models. | the file you picked |
| Pressing Send does nothing | No model is loaded yet, or a reply is still being written. | `[4.9]` |
| Loading a `.gguf` file shows "Error: [WinError -1073741795] Windows Error 0xc000001d", or the app closes with no message | That is Windows' "illegal instruction" error: the llama-cpp-python build uses a processor instruction your CPU does not have. 0.3.37 did this on the test machine, and 0.3.36 did not. Check that the llama-cpp-python line in `STEPS` ends in `==0.3.36`, then run `install.py` again. | `[1.2.1]` |
| "Error: Failed to load shared library ... llama.dll" | The three NVIDIA runtime files are missing: `install.py` was not run, or stopped before the copy. | `[1.2.3]`, step 1.3 |
| Lines about `n_ctx_train`, `not documented`, `pad_token_id` or generation flags in the terminal | Harmless noise from llama.cpp and transformers. If the status line says "Ready", it worked. | step 3.6 |
| The PyTorch reply repeats your whole prompt back | `skip_prompt` is missing from the streamer. | `[3.4.4]` |
| The PyTorch reply appears all at once after a pause | `generate` is being called directly instead of on its own thread. | `[3.4.4]` |
| "Error: string indices must be integers, not 'str'" with llama.cpp | `stream=True` is missing, so llama.cpp hands back one finished answer (a dictionary) and the `for` loop walks over its key names instead of chunks. | `[3.3.4]` |
| Send comes back to life after the first word | `set_busy(False)` runs for every result instead of only in the three finishing branches. | `[4.13]` |
| Words in the reply are doubled or run together | The slice in `reply_worker` is wrong, or `shown` is not being updated. | `[4.12]` |
| `<generator object ...>` appears instead of a reply, at the Python prompt or in the log | The result of `chat` is being used as if it were a string: passed straight to `print` in step 3.6, or put straight into the queue in `reply_worker`. A generator has to be looped over. | step 3.6, `[4.12]` |
| `ModuleNotFoundError: No module named 'backends'` | Running `app.py`: `backends.py` is not in the same folder as `app.py`, or was saved under another name (such as `backend.py`, or `backends.py.txt`, which Windows shows as `backends.py` when it hides file extensions). At the Python prompt in step 3.6: you started `python` from a folder other than `my_build/`. | step 1.1, step 3.6 |

## How this recipe was checked

- **Install steps:** the answer key's `install.py` was run in an empty Python environment on the test machine, and again in a Python that already had everything. Both ended with `cuda: True llama gpu: True`, and the empty environment then chatted with the 0.8B GGUF. The first empty-environment run, before the pin, got llama-cpp-python 0.3.37. It passed the import check but crashed with `0xc000001d` as soon as a model loaded, which is why the version is pinned. The same installs, done by hand, were checked earlier by running the app with both models. Without the copy in `[1.2.3]`, `import llama_cpp` failed, so that step is required.
- **Answer key:** the finished app was driven through its real window with the 0.8B GGUF, a Q8 build of the 4B GGUF and the 2B PyTorch model. Each loaded with its full 262,144-token context. Replies streamed in dozens of pieces with the window responsive and Send greyed out until the end. The system prompt changed the answers, temperature 0 gave the same answer twice, the instructions window saved its text, and thinking mode showed reasoning, `[end of thinking]` and the answer (with the 4B model). With the context shrunk on purpose, the oldest messages were forgotten and the conversation always restarted on a user message. Asking for more context than the card holds made llama.cpp's load fail cleanly and the halving find a size that fits.
- **This document:** copies of the app were written from this recipe alone, without sight of the answer key, and put through the same tests.
- **Troubleshooting table:** each row that describes a coding mistake was checked by making that mistake in a copy of the answer key and running it. The symptom in the table is what actually happened.
- **Explanations:** the claims this recipe makes about how Python, tkinter, llama-cpp-python and transformers behave were checked against the installed libraries' source code and small test runs.
- **Automatic tests:** [`tests/test_level1.py`](tests/test_level1.py) checks `install.py` without installing anything, the trimming in `backends.py` with a stand-in model, and the window from Load to a finished reply. The tests need no graphics card and run on GitHub on every change. `check_my_build.py` runs them on your copy.
- **Checkpoints:** the three checkpoints in step 4 were tried by cutting the answer key down to exactly the methods and stand-ins each one describes and running it.

The one thing not exercised is the Browse dialog itself; the tests set the model path directly.

## Known rough edges

Level 1 leaves a few things undone on purpose. The answer key behaves the same way.

- Sending a message before a model is loaded does nothing, with no message to say why.
- Loading a second model starts a new conversation for the model, but the old messages stay on screen.
- The app asks for the biggest context the model supports, so llama.cpp can claim most of the graphics card's memory (about 8 GB for the test models). The first model also stays in memory until the second has finished loading. Close and reopen the app to switch models. Level 4 sets a limit on the context, checks that a load left the card some room, and lets the first model go before it loads the second.
- The PyTorch backend uses the model's full trained context as its limit, but it does not set memory aside up front, so a very long chat can run out of graphics memory before trimming ever starts. Level 4 holds it to the same limit as a GGUF model.
- When the conversation outgrows the context, the oldest messages are forgotten for good. They stay on screen, but the model no longer knows them. Level 2 summarises them instead.
- In thinking mode, small models can keep thinking until they reach `MAX_NEW_TOKENS` without ever answering: the 0.8B and 2B test models did on a simple sum. Their thinking is then kept as the answer.
- Thinking mode works by setting `enable_thinking` in the chat template and adding your instructions to the system prompt. A model whose template ignores `enable_thinking` only thinks if your instructions persuade it, and its reasoning will not be marked with `[end of thinking]`.
- Closing the Thinking instructions window with its X button throws your edits away; only Save keeps them.
- The status line's "Ready: ..." shows whatever path was last picked with Browse, so browsing again without clicking Load makes it name the wrong model.
- If a reply fails with an error, your message stays in the conversation without an answer after it.
- If a reply fails partway through, the words that had already arrived stay on screen and the next message starts on the same line.
- If the PyTorch model fails in the middle of generating, the app waits for more words indefinitely and has to be closed.
- Picking a `.gguf` file and then switching the radio button to PyTorch before Load gives an error, because the path and the backend no longer match.

Each of these is a small fix and a good first change to make on your own. Level 2 deals with the forgotten messages. Level 3 deals with the old messages left on screen after a second Load, and with the PyTorch failure that never ends. Level 4 lets the first model go before the second loads, and takes a message that got no answer back out of the conversation.

## Where to go next

[RECIPE_LEVEL2.md](RECIPE_LEVEL2.md) is level 2: compaction, tool calling and MCP. [RECIPE_LEVEL3.md](RECIPE_LEVEL3.md) is level 3: a Stop button that cuts a reply short, a New chat button, settings that are remembered between runs, and asking before an MCP tool runs. If you would like to try adding those buttons on your own first, do it before you read level 3.
