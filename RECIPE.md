# VoxMux recipe: build it by hand

This is a description, in words, of every file in [`answer_key/`](answer_key/). Follow it top to bottom, type every line yourself, and you will end up with the same app: a desktop window where you pick llama.cpp (a `.gguf` file) or PyTorch (a folder of `.safetensors` weights), load a model, and chat with it.

There is no finished code in this document. The finished code is in `answer_key/`, and the two are tied together by **reference tags**.

## How the reference tags work

Every step below has a number, such as **3.2.1**. The same number appears in square brackets in the answer key, in the docstring or comment sitting on the matching block of code:

- Step **3.2.1** in this file describes `LlamaCppBackend.__init__`.
- In [`answer_key/backends.py`](answer_key/backends.py), that method's docstring starts with `[3.2.1]`.

So when you are stuck on a step, search the answer key for its tag (Ctrl+F, then type `[3.2.1]`) and you land on exactly the lines that step describes. Tags starting with 3 are in `backends.py`. Tags starting with 4 are in `app.py`.

Each tagged block in the answer key also carries a short "How it works" description. Every step here asks you to write your own docstring for the block, **starting with the same tag**. That way your file and the answer key can be compared block by block.

## What you are building

Three files, in a new folder called `my_build/` at the top of the repo:

| Step | File | What it is |
| --- | --- | --- |
| 2 | `requirements.txt` | The list of libraries the app uses. |
| 3 | `backends.py` | Two classes that each know how to run one kind of model, plus one function that picks between them. No UI code. |
| 4 | `app.py` | The window: one class for the UI, one `main` function, and the line that starts it. |

The idea that holds it together: both backend classes have **the same two methods with the same parameters**. You build one by giving it a model path, and you call `chat` on it with the conversation so far to get back a reply string. Because the two look identical from the outside, the window never has to care which one it is holding.

## Python syntax you will meet

Read this once now and come back to it as needed.

- **Indentation is the syntax.** Python has no braces. A line ending in a colon (`def ...:`, `class ...:`, `if ...:`, `while ...:`, `try:`) opens a block, and everything indented four spaces under it is inside that block. Use four spaces, never tabs.
- **Functions** are written `def name(parameter, other_parameter):`. The names in the parentheses are *parameters*. When you call the function, the values you pass are *arguments*.
- **Positional vs keyword arguments.** `f(a, b)` passes by position. `f(width=3, height=4)` passes by name. Library calls with many options are almost always written with keyword arguments, often one per line inside the parentheses with a trailing comma after the last one.
- **Default parameter values.** `def send(self, event=None):` means `event` is optional and is `None` if the caller leaves it out.
- **Classes** are written `class Name:`. Functions defined inside are *methods*. Every method's first parameter is `self`, which is the object the method was called on. You never pass `self` yourself: calling `thing.chat(messages)` fills in `self` with `thing`.
- **`__init__`** (two underscores each side) is the method Python runs when you build an object. Writing `Name(x)` calls `__init__(self, x)`.
- **Attributes.** `self.something = value` stores a value on the object so other methods can read it later as `self.something`.
- **Strings** use double quotes. An **f-string** starts with `f` before the opening quote and lets you drop values in with braces: `f"Ready: {path}"`.
- **Lists** use square brackets, **dictionaries** use braces with `key: value` pairs, **tuples** use parentheses. You read from all three with square brackets: `thing[0]`, `thing["name"]`.
- **Docstrings.** A string in triple double quotes as the first thing in a file, class, or function is its documentation. It goes on the line directly under the `def` or `class` line, indented like the rest of the body.
- **Comments** start with `#`.
- **Constants** are ordinary variables written in `ALL_CAPS` near the top of a file. Python does not enforce it; it is a naming habit.
- **Passing a function vs calling it.** `self.browse` (no parentheses) is the function itself, which you hand to something that will call it later. `self.browse()` calls it right now. Buttons want the first form.
- **Blank lines.** One blank line between methods inside a class. Two blank lines between top-level classes and functions.

## Step 1: install

You need Python 3.13 and an NVIDIA graphics card with its normal driver. Everything else is below. Run the commands in order. Each one is safe to run again; if a library is already there, pip says "Requirement already satisfied" and moves on.

### 1.1 PyTorch

The build on PyPI is CPU-only on Windows, so install the GPU build from PyTorch's own index:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu124
```

### 1.2 Transformers

Hugging Face's library, which loads safetensors models and tokenizers on top of PyTorch:

```bash
pip install transformers
```

### 1.3 llama-cpp-python

The Python wrapper around llama.cpp, for GGUF files. PyPI only has source code for Windows, so install the ready-made GPU build from the project's own index:

```bash
pip install --only-binary=llama-cpp-python llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124
```

### 1.4 NVIDIA runtime files for llama.cpp

The GPU build of llama.cpp needs three NVIDIA files that it does not include. PyTorch includes the same three, so copy them across:

```bash
python -c "import shutil, sysconfig, pathlib; sp = pathlib.Path(sysconfig.get_paths()['purelib']); [shutil.copy(sp / 'torch' / 'lib' / n, sp / 'llama_cpp' / 'lib') for n in ('cudart64_12.dll', 'cublas64_12.dll', 'cublasLt64_12.dll')]"
```

### 1.5 Check that everything imports

```bash
python -c "import tkinter, llama_cpp, torch, transformers; print(llama_cpp.__version__, torch.__version__, transformers.__version__, 'cuda:', torch.cuda.is_available(), 'llama gpu:', llama_cpp.llama_supports_gpu_offload())"
```

You should see three version numbers followed by `cuda: True llama gpu: True`. `tkinter` is the window toolkit; it comes with Python, so there was nothing to install for it.

### 1.6 Two small models to test with

Copy one model of each kind from the NAS into `C:\models`:

```bash
robocopy \\nas\models\gguf C:\models Qwen3.5-0.8B-Q8_0.gguf
```

```bash
robocopy \\nas\models\safetensors\Qwen--Qwen3.5-2B C:\models\Qwen--Qwen3.5-2B /E
```

| Backend | Path | Size |
| --- | --- | --- |
| llama.cpp | `C:\models\Qwen3.5-0.8B-Q8_0.gguf` (a file) | 0.8 GB |
| PyTorch | `C:\models\Qwen--Qwen3.5-2B` (a folder) | 4.3 GB |

### 1.7 Make your folder

In the repo root, make a folder named `my_build` and move into it in your terminal. All three files go there.

## Step 2: `requirements.txt`

Make a file named `requirements.txt`. It is plain text, one library name per line, nothing else:

1. `llama-cpp-python`
2. `torch`
3. `transformers`

This file is the app's record of what it depends on. It has no tags because it has no code.

## Step 3: `backends.py`

This file has no UI in it at all. You can finish it and test it from a terminal before you write a single line of window code.

### 3.1 Top of the file

*Answer key: `[3.1]` in `backends.py` (it appears twice, on the module docstring and on the constants).*

1. Start with a **module docstring** on the very first line. Begin it with the tag `[3.1]`, then say in your own words what the file is and how it works: two classes that each wrap one library, sharing the same two methods, so the window never needs to know which one it has.
2. Leave a blank line, then a comment line starting with the tag `[3.1]` that says these are settings shared by both backends. Under it define two constants, each with a short comment after it on the same line:
   - `MAX_NEW_TOKENS`, set to the integer `512`. This caps how long a reply can be.
   - `CONTEXT_SIZE`, set to the integer `4096`. This is how many tokens of conversation llama.cpp will keep in view.
3. There are **no imports at the top of this file**. That is deliberate, and 3.2.1 explains why.

### 3.2 The class `LlamaCppBackend`

*Answer key: `[3.2]`.*

Define a class named `LlamaCppBackend`. It takes nothing in parentheses after its name.

**Docstring:** start with `[3.2]`. Say that it runs a single `.gguf` file through llama.cpp, and how: llama.cpp reads the chat template stored inside the file, builds the prompt, generates, and returns text, so this class only passes messages in and digs the reply out.

It has two methods.

#### 3.2.1 Method `__init__`

*Answer key: `[3.2.1]`.*

Parameters: `self` and `model_path`.

**Docstring:** start with `[3.2.1]`. Say that it loads the file into memory, that this is the slow part, and that the result is kept on `self` so `chat` can reuse it.

1. The first line after the docstring is an import: from the module `llama_cpp`, import the name `Llama` (capital L, it is a class). Putting the import inside the method instead of at the top of the file means it only runs when someone actually builds this backend, so the app still starts if `llama-cpp-python` is not installed. Leave yourself a comment saying so.
2. Build a `Llama` object and store it on `self` as `self.llm`. Pass four keyword arguments, one per line:
   - `model_path` set to the `model_path` parameter.
   - `n_ctx` set to your `CONTEXT_SIZE` constant.
   - `n_gpu_layers` set to `-1`, which means "put every layer on the GPU".
   - `verbose` set to `False`, which stops llama.cpp printing pages of logs.
3. `__init__` returns nothing. No `return` line.

#### 3.2.2 Method `chat`

*Answer key: `[3.2.2]`.*

Parameters: `self` and `messages`.

`messages` is a list of dictionaries. Each dictionary has two keys, `"role"` and `"content"`, both with string values. The role is `"user"` or `"assistant"`. This is the same shape every chat API uses.

**Docstring:** start with `[3.2.2]`. Say that it sends the whole conversation and returns the reply as a string, and describe the shape of `messages`.

1. Call the method `create_chat_completion` on `self.llm` and store what comes back in a variable named `response`. Pass two keyword arguments: `messages` set to the `messages` parameter, and `max_tokens` set to `MAX_NEW_TOKENS`.
2. `response` is a dictionary nested several levels deep. The reply text lives at: key `"choices"`, then index `0` of that list, then key `"message"`, then key `"content"`. Chain four sets of square brackets to reach it and store it in a variable named `reply`.
3. `return` the result of calling `.strip()` on `reply`. Models often pad their answer with blank lines; `.strip()` removes whitespace from both ends of a string.

### 3.3 The class `TransformersBackend`

*Answer key: `[3.3]`.*

Define a second class named `TransformersBackend`. Same two methods, same parameters, different insides.

**Docstring:** start with `[3.3]`. Say that it runs a folder of safetensors weights through PyTorch, and how: a tokenizer turns text into numbers, the model predicts more numbers, and the tokenizer turns them back into text.

#### 3.3.1 Method `__init__`

*Answer key: `[3.3.1]`.*

Parameters: `self` and `model_path`.

Here `model_path` is a **folder**, not a file. The folder holds `config.json`, the tokenizer files, and one or more `.safetensors` weight files.

**Docstring:** start with `[3.3.1]`. Say that it loads the tokenizer and the model from the folder, and moves the model to the graphics card if there is one.

1. Two imports inside the method: import `torch`, and from `transformers` import two names on one line, `AutoModelForCausalLM` and `AutoTokenizer`.
2. Decide which device to use. Write an `if` / `else`: if `torch.cuda.is_available()` returns true, set `self.device` to the string `"cuda"`; otherwise set it to `"cpu"`.
3. Load the tokenizer: call `AutoTokenizer.from_pretrained` with `model_path` as its one positional argument, and store the result as `self.tokenizer`. Note there is no `()` after `AutoTokenizer`. `from_pretrained` is a method you call on the class itself, and it builds the object for you.
4. Load the model the same way: call `AutoModelForCausalLM.from_pretrained` with `model_path` as the positional argument and one keyword argument, `dtype` set to the string `"auto"` (use the number format the weights were saved in, instead of doubling memory by converting to 32-bit floats). Store it as `self.model`. The `dtype` keyword needs transformers 4.56 or newer, which step 1.2 gives you.
5. Move the model onto the device: call `.to` on `self.model`, passing `self.device`. You do not need to store the result.

#### 3.3.2 Method `chat`

*Answer key: `[3.3.2]`.*

Parameters: `self` and `messages`.

**Docstring:** start with `[3.3.2]`. Name the four stages: turn messages into token numbers, generate, slice off the prompt, turn numbers back into text. Then put a one-line comment above each stage in the body, starting `Stage 1:`, `Stage 2:` and so on (no tag needed on these). Items 1 and 2 below are both Stage 1.

1. **Stage 1.** Call `apply_chat_template` on `self.tokenizer` and store the result as `inputs`. One positional argument, `messages`, then three keyword arguments:
   - `add_generation_prompt` set to `True`. This appends the marker that tells the model "now it is your turn".
   - `return_tensors` set to the string `"pt"`, meaning PyTorch tensors.
   - `return_dict` set to `True`, so you get back a dictionary-like object holding both the token ids and the attention mask.
2. Reassign `inputs` to the result of calling `.to` on it with `self.device`. Unlike the model in `__init__`, this one **does** need the result stored: `.to` on inputs returns a moved copy.
3. **Stage 2.** Call `generate` on `self.model` and store the result as `output`. The first argument is `inputs` with two asterisks in front of it (`**inputs`). The double asterisk *unpacks* a dictionary into keyword arguments, so every key in `inputs` becomes a named argument. Add one more keyword argument, `max_new_tokens`, set to `MAX_NEW_TOKENS`.
4. **Stage 3.** `generate` hands back the prompt *and* the reply as one long sequence of token numbers, so you need to cut the prompt off the front:
   - Get the prompt length: index `inputs` with the key `"input_ids"`, read its `.shape` attribute, and take index `1` of that. (Shape is rows by columns; there is one row, and the column count is the number of prompt tokens.) Store it as `prompt_length`.
   - Take the first (only) row of `output` with index `0`, then *slice* it from `prompt_length` to the end. A slice is square brackets with a colon: a start value, then a colon, then nothing. Store it as `new_tokens`.
5. **Stage 4.** Call `decode` on `self.tokenizer` with `new_tokens` as the positional argument and the keyword argument `skip_special_tokens` set to `True`. Store the result as `reply`.
6. `return` the result of calling `.strip()` on `reply`, same as in the other class.

### 3.4 The function `load_backend`

*Answer key: `[3.4]`.*

Back at zero indentation (outside both classes), define a function named `load_backend` with two parameters: `kind` and `model_path`.

**Docstring:** start with `[3.4]`. Say that it builds and returns the backend named by `kind`, and that this is the only place that knows both classes exist.

1. If `kind` equals the string `"llama_cpp"` (equality is two equals signs), `return` a new `LlamaCppBackend` built with `model_path`.
2. If `kind` equals the string `"pytorch"`, `return` a new `TransformersBackend` built with `model_path`.
3. If neither matched, `raise` a `ValueError` whose message is an f-string reading `Unknown backend: ` followed by `kind` in braces. Because each branch above returns, you can write plain `if`s with no `else`: reaching this line already means nothing matched.

### 3.5 Checkpoint: test it without a window

From inside `my_build/`, start the Python prompt by running `python` with no arguments. Then, one line at a time:

1. From `backends`, import `load_backend`.
2. Call it with the kind string and the full path to a model from step 1.6, and store the result in a variable. Put an `r` before the opening quote of a Windows path so the backslashes are taken literally.
3. Call `.chat` on that variable. The argument is a list containing one dictionary, with `"role"` set to `"user"` and `"content"` set to a question.

If a sentence comes back, this file is done. Do it once for each kind, using the two model paths from step 1.6.

The PyTorch backend prints several lines to the terminal while it loads and generates (a "fast path is not available" notice, some `[ERROR] ... not documented` lines, and "Setting `pad_token_id`"). They come from the transformers library, they are harmless, and the answer key prints them too. Loading the PyTorch model takes about 25 seconds; the GGUF takes about 2.

## Step 4: `app.py`

The window is built with `tkinter`, which comes with Python.

Before you start, understand the one hard idea in this file. Loading a model and generating a reply are slow. If you do slow work directly inside a button's function, the window freezes until it finishes. So slow work runs on a second **thread**. But tkinter widgets may only be touched from the main thread. The bridge between the two is a **queue**: the worker thread puts its result into the queue, and the main thread checks the queue ten times a second and updates the window. Steps 4.8 to 4.11 exist only to do that.

### 4.1 Top of the file

*Answer key: `[4.1]` in `app.py` (it appears twice, on the module docstring and on the constant).*

1. A module docstring. Start with `[4.1]`, then say what the file is, how it works (one class for the window, slow work on a second thread, results coming back through a queue), and how to run it.
2. Imports, in this order, each on its own line:
   - `queue`
   - `threading`
   - `tkinter`, renamed to `tk` with the `as` keyword, so you can write `tk.Button` instead of `tkinter.Button`.
   - From `tkinter`, import two submodules on one line: `filedialog` and `scrolledtext`.
   - A blank line, then from your own `backends` file, import `load_backend`. No `.py` in the name.
3. One constant, with a comment above it that starts with the tag `[4.1]`: `POLL_INTERVAL_MS`, set to `100`.

### 4.2 The class `ChatApp`

*Answer key: `[4.2]`.*

Define a class named `ChatApp`.

**Docstring:** start with `[4.2]`. Say that it is the whole window, and describe the three groups its methods fall into: button handlers that run on the main thread, workers that run on a second thread, and `poll_results`, which carries the workers' results back.

Steps 4.3 to 4.13 are its methods, in order.

### 4.3 Method `__init__`

*Answer key: `[4.3]`.*

Parameters: `self` and `root`. `root` is the main window object, which `main` will create and pass in.

**Docstring:** start with `[4.3]`. Say that it sets up the window, the starting state, and the queue check, and that every attribute is created here so no other method can meet one that does not exist yet.

1. Store `root` as `self.root`.
2. Call `title` on `self.root` with the string `"VoxMux"`.
3. Call `geometry` on `self.root` with the string `"700x500"` (width, a lowercase x, height).
4. Create five attributes that hold the app's state. Put a short comment after each one, on the same line.
   - `self.backend`, set to `None`. It will hold the loaded model.
   - `self.model_path`, set to an empty string. It will hold what the user picked.
   - `self.messages`, set to an empty list. It will hold the whole conversation.
   - `self.busy`, set to `False`. It is `True` while a worker thread is running.
   - `self.results`, set to a new `queue.Queue()`. This is how worker threads report back.
5. Call `self.build_widgets()`.
6. Call `self.poll_results()`. This starts the ten-times-a-second check, which then keeps itself going.

### 4.4 Method `build_widgets`

*Answer key: `[4.4]`, with one tagged comment per block: `[4.4.1]` to `[4.4.4]`.*

Parameters: just `self`.

**Docstring:** start with `[4.4]`. Say that it creates every widget and places it, and that the order things are packed in is the layout.

Every tkinter widget follows the same two-step pattern. First you **create** it, passing its parent as the first positional argument and options as keyword arguments. Then you **place** it by calling `.pack(...)` on it. If you need to talk to the widget later, store it on `self` first and pack on the next line. If you never need it again, you can create and pack in one chained expression.

Build these four blocks in this order. Put a comment above each block starting with its tag.

#### 4.4.1 The top row

1. Create a `tk.Frame` whose parent is `self.root`. Store it in a local variable named `top` (not on `self`, nothing else needs it). A frame is an invisible box for grouping widgets.
2. Pack `top` with `fill` set to `"x"` (stretch horizontally), and `padx` and `pady` both set to `8`.
3. Create a `tk.StringVar` with the keyword argument `value` set to `"llama_cpp"`, and store it as `self.backend_kind`. A `StringVar` is a little box holding a string that widgets can share. Whichever radio button is selected writes its value into it.
4. Create a `tk.Radiobutton` with parent `top` and three keyword arguments: `text` set to `"llama.cpp (GGUF)"`, `variable` set to `self.backend_kind`, and `value` set to `"llama_cpp"`. Chain `.pack` straight onto it with `side` set to `"left"`.
5. Create a second `tk.Radiobutton` the same way: `text` is `"PyTorch (safetensors)"`, same `variable`, and `value` is `"pytorch"`. Pack it to the left too. These two value strings must match the ones `load_backend` checks for, exactly.
6. Create a `tk.Button` with parent `top`, `text` set to `"Browse..."`, and `command` set to `self.browse` (no parentheses: you are handing over the method, not calling it). Chain `.pack` with `side` set to `"left"` and `padx` set to `8`.
7. Create another `tk.Button` with parent `top`, `text` set to `"Load"`, and `command` set to `self.load_model`. This one you need later, so store it as `self.load_button`, then pack it on the next line with `side` set to `"left"`.

#### 4.4.2 The status line

1. Create a `tk.Label` with parent `self.root`, `text` set to `"No model loaded."`, and `anchor` set to `"w"` (west, so the text hugs the left edge). Store it as `self.status`.
2. Pack it with `fill` set to `"x"` and `padx` set to `8`.

#### 4.4.3 The bottom row

This is built before the chat log on purpose: tkinter gives space to widgets in the order they are packed, so packing this first keeps it visible when the window shrinks. Say so in this block's comment.

1. Create a `tk.Frame` with parent `self.root`, stored in a local variable named `bottom`.
2. Pack it with `side` set to `"bottom"`, `fill` set to `"x"`, and `padx` and `pady` both `8`.
3. Create a `tk.Entry` (a one-line text box) with parent `bottom`. Store it as `self.entry`.
4. Pack it with `side` set to `"left"`, `fill` set to `"x"`, and `expand` set to `True`, so it takes all the width the Send button does not need.
5. Call `bind` on `self.entry` with two positional arguments: the string `"<Return>"` (angle brackets included) and `self.send`. Now pressing Enter in the box calls `send`.
6. Create a `tk.Button` with parent `bottom`, `text` set to `"Send"`, and `command` set to `self.send`. Store it as `self.send_button`.
7. Pack it with `side` set to `"left"` and `padx` set to the tuple `(8, 0)`, meaning 8 pixels of space on its left and none on its right.

#### 4.4.4 The chat log

1. Create a `scrolledtext.ScrolledText` with parent `self.root`, `wrap` set to `"word"` (break lines between words), and `state` set to `"disabled"` (read-only, so the user cannot type into the history). Store it as `self.chat_log`.
2. Pack it with `fill` set to `"both"`, `expand` set to `True`, and `padx` and `pady` both `8`. It takes whatever space is left.

### 4.5 Method `browse`

*Answer key: `[4.5]`.*

Parameters: just `self`. Runs when the Browse button is clicked.

**Docstring:** start with `[4.5]`. Say that it lets the user pick a model and remembers the path, and why there are two kinds of picker: a GGUF model is one file, a safetensors model is a whole folder.

1. Read which backend is selected by calling `.get()` on `self.backend_kind`, and compare it to `"llama_cpp"` in an `if`.
2. If it matches, call `filedialog.askopenfilename` with one keyword argument, `filetypes`, set to a list containing one tuple of two strings: a label, `"GGUF model"`, and a pattern, `"*.gguf"`. Store the result in a local variable named `path`.
3. In the `else`, call `filedialog.askdirectory` with no arguments and store the result in `path`.
4. Both dialogs return an empty string if the user cancels. An empty string counts as false, so write `if path:` and inside it:
   - Store `path` as `self.model_path`.
   - Update the status label: call `.config` on `self.status` with `text` set to an f-string reading `Selected:`, a space, then `path` in braces.

From here on, "set the status text to X" always means this same call: `.config` on `self.status` with `text` set to X. And wherever a status message has a label like `Ready:` or `Error:`, put one space after the colon.

### 4.6 Method `load_model`

*Answer key: `[4.6]`.*

Parameters: just `self`. Runs when the Load button is clicked.

**Docstring:** start with `[4.6]`. Say that it only *starts* the loading: it greys out the buttons, updates the status, hands the slow part to a thread, and returns at once.

1. Guard first. If `self.model_path` is empty (`if not self.model_path:`), set the status text to `"Pick a model with Browse first."` and then write a bare `return` to leave the method early.
2. Call `self.set_busy` with `True`.
3. Set the status text to `"Loading model..."`.
4. Call `self.start_worker` with three positional arguments: `self.load_worker` (the method itself, no parentheses), the result of `self.backend_kind.get()`, and `self.model_path`.

### 4.7 Method `send`

*Answer key: `[4.7]`.*

Parameters: `self`, and `event` with a default value of `None`.

Why the default? This method gets called two ways. The Send button calls it with no arguments. The Enter key binding calls it with one argument, an event object describing the keypress. A default lets one method serve both. You never use `event`; it just has to be accepted.

**Docstring:** start with `[4.7]`. Say that it adds the user's message and asks for a reply, explain the `event` parameter, and note that the reply arrives later through the queue.

1. Read the entry box by calling `.get()` on `self.entry`, chain `.strip()` onto that to remove spaces from both ends, and store the result as `text`.
2. Guard: if `text` is empty, **or** `self.backend` is `None`, **or** `self.busy` is true, `return` early. Use `not text` for the first test, `is None` for the second, and join the three with the word `or`.
3. Clear the entry box: call `.delete` on `self.entry` with the integer `0` and the string `"end"`.
4. Add the user's message to the conversation: call `.append` on `self.messages`, passing a dictionary with `"role"` set to `"user"` and `"content"` set to `text`.
5. Show it: call `self.append_chat` with `"You"` and `text`.
6. Call `self.set_busy` with `True`.
7. Set the status text to `"Thinking..."`.
8. Call `self.start_worker` with one argument, `self.reply_worker`.

### 4.8 Method `start_worker`

*Answer key: `[4.8]`.*

Parameters: `self`, `target`, and `*args`.

The asterisk is new. `*args` in a parameter list means "collect any further positional arguments into a tuple named `args`". It lets this one helper start a worker that needs two arguments (loading) or none (replying).

**Docstring:** start with `[4.8]`. Say that it runs `target` on a new background thread so the window does not freeze, and what `daemon` means.

1. Create a `threading.Thread` with three keyword arguments: `target` set to `target`, `args` set to `args`, and `daemon` set to `True`. A daemon thread is dropped automatically when you close the window, instead of keeping the program alive. Store it in a local variable named `thread`.
2. Call `.start()` on it.

### 4.9 Method `load_worker`

*Answer key: `[4.9]`.*

Parameters: `self`, `kind`, and `model_path`. **This method runs on the worker thread, so it must not touch any widget.** It only does the slow work and puts a result in the queue.

**Docstring:** start with `[4.9]`. Say that it runs on the background thread, loads a model, and reports through the queue as a pair of a label and a value, including when something goes wrong.

1. Open a `try:` block. Inside it:
   - Call `load_backend` with `kind` and `model_path` and store the result as `backend`.
   - Call `.put` on `self.results` with **one** argument: a tuple of two things, the string `"loaded"` and `backend`. A tuple inside a call means two sets of parentheses, one for the call and one for the tuple.
2. Follow it with `except Exception as error:`. Inside:
   - Put a tuple of the string `"error"` and `str(error)` into `self.results`. `str(...)` converts the exception into its message text.

Catching `Exception` broadly is usually bad style, but here it is right: anything that goes wrong on a worker thread would otherwise vanish silently, and you want it shown in the status line.

### 4.10 Method `reply_worker`

*Answer key: `[4.10]`.*

Parameters: just `self`. Also runs on the worker thread. Same shape as `load_worker`.

**Docstring:** start with `[4.10]`. Say that it gets a reply on the background thread and reports through the queue, and that the whole conversation is sent every time, which is how the model remembers earlier turns.

1. In a `try:` block, call `.chat` on `self.backend` with `self.messages`, store the result as `reply`, then put the tuple `("reply", reply)` into `self.results`.
2. In `except Exception as error:`, put the tuple `("error", str(error))` into `self.results`.

### 4.11 Method `poll_results`

*Answer key: `[4.11]`.*

Parameters: just `self`. Runs on the main thread, ten times a second, for as long as the window is open. This is the other end of the queue.

**Docstring:** start with `[4.11]`. Say that it empties the queue, updates the window for each result, and then schedules itself to run again.

1. Start a `while` loop that runs as long as the queue is not empty: the condition is `not` followed by a call to `.empty()` on `self.results`.
2. Inside the loop, call `.get()` on `self.results`. It returns one of your two-item tuples. *Unpack* it into two variables on one line by writing both names separated by a comma on the left of the equals sign: `kind` and `value`.
3. Still inside the loop, an `if` / `elif` / `elif` chain on `kind`:
   - If it equals `"loaded"`: set `self.backend` to `value`, reset `self.messages` to an empty list (a new model starts a new conversation), and set the status text to an f-string reading `Ready:`, a space, then `self.model_path` in braces.
   - Else if it equals `"reply"`: append a dictionary to `self.messages` with `"role"` set to `"assistant"` and `"content"` set to `value`; call `self.append_chat` with `"Model"` and `value`; and set the status text to the same `Ready:` f-string.
   - Else if it equals `"error"`: set the status text to an f-string reading `Error:`, a space, then `value` in braces.
4. After the chain but still inside the `while` loop, call `self.set_busy` with `False`. Whatever happened, the work is over.
5. **Outside** the loop (back at the method's indentation), schedule the next check: call `.after` on `self.root` with two arguments, `POLL_INTERVAL_MS` and `self.poll_results` (no parentheses). This says "call this method again in 100 milliseconds". The method re-arms itself every time it runs. If you indent this line into the loop by mistake, the polling stops the first time the queue is empty, and nothing ever shows up.

### 4.12 Method `append_chat`

*Answer key: `[4.12]`.*

Parameters: `self`, `speaker`, and `text`.

**Docstring:** start with `[4.12]`. Say that it adds one entry to the chat log, and why it has to unlock and relock the log: read-only blocks the program as well as the user.

1. Call `.config` on `self.chat_log` with `state` set to `"normal"`.
2. Call `.insert` on `self.chat_log` with two arguments: the string `"end"` (where to insert), and an f-string made of `speaker` in braces, a colon and a space, `text` in braces, and then two newline escapes (`\n\n`) to leave a blank line between messages.
3. Call `.config` again with `state` set to `"disabled"`.
4. Call `.see` on `self.chat_log` with `"end"`, which scrolls to the bottom.

### 4.13 Method `set_busy`

*Answer key: `[4.13]`.*

Parameters: `self` and `busy` (a boolean).

**Docstring:** start with `[4.13]`. Say that it greys out Load and Send while work is running or brings them back, and that it saves the flag so `send` can check it.

1. Store `busy` as `self.busy`.
2. `if busy:` set a local variable `state` to the string `"disabled"`. `else:` set it to `"normal"`.
3. Call `.config` on `self.load_button` with `state` set to `state`.
4. Do the same for `self.send_button`.

### 4.14 The function `main`

*Answer key: `[4.14]`.*

Back at zero indentation, outside the class. Define a function named `main` with no parameters.

**Docstring:** start with `[4.14]`. Say that it creates the window, attaches the app, and runs until the window is closed, and what `mainloop` is: the loop that waits for clicks, keypresses and timers and calls your methods.

1. Create the main window by calling `tk.Tk()` and store it as `root`.
2. Build the app by calling `ChatApp` with `root`. You do not need to store the result.
3. Call `.mainloop()` on `root`. This line does not return until the window is closed.

### 4.15 The last two lines

*Answer key: `[4.15]`.*

The standard ending for a runnable Python file. Put a comment above it starting with `[4.15]`.

Write an `if` that compares the special variable `__name__` to the string `"__main__"` (two underscores on each side of both), and inside it call `main()`. Python sets `__name__` to `"__main__"` only in the file you ran directly, so this means "start the app if I was run, but not if I was imported".

## Step 5: run it

From inside `my_build/`:

```bash
python app.py
```

Check each of these, once per backend, using the two models from step 1.6:

1. The window opens with two radio buttons, Browse, Load, a status line, an empty log, and an entry box with Send.
2. Clicking Load before Browse shows "Pick a model with Browse first."
3. With llama.cpp selected, Browse opens a file picker filtered to `.gguf`. With PyTorch selected, it opens a folder picker.
4. Load shows "Loading model..." and both buttons grey out. The window still moves and resizes while it loads. Then the status changes to "Ready: ...".
5. Typing a message and pressing Enter (or Send) shows your line, then "Thinking...", then the model's line.
6. A second message gets an answer that shows the model remembers the first. Tell it your name in the first message and ask for it in the second.
7. Loading a bad path shows "Error: ..." in the status line instead of crashing.

## When it does not work

| What you see | Likely cause | Look at |
| --- | --- | --- |
| `IndentationError`, or a method "is not defined" | A line is at the wrong depth. Methods are indented four spaces inside the class, their bodies eight. | the step you just typed |
| `TypeError: ... takes 1 positional argument but 2 were given` | You forgot `self` as a method's first parameter, or forgot `event=None` on `send`. | `[4.7]` |
| A button's function runs once at startup and never again | You wrote `command=self.browse()` with parentheses. | `[4.4.1]` |
| The window freezes while loading | You called the worker method directly instead of handing it to `start_worker`. | `[4.6]`, `[4.8]` |
| The model loads but the status stays on "Loading model..." | `poll_results` is not re-arming: the `.after` line is missing or indented into the `while` loop. | `[4.11]` |
| "Error: Unknown backend: ..." | A radio button's `value` does not match the strings in `load_backend`. | `[4.4.1]`, `[3.4]` |
| "Error: Failed to load model from file" | The file is not a chat model (the `mmproj-*.gguf` files are not). | step 1.6 |
| "Error: Failed to load shared library ... llama.dll" | The three NVIDIA runtime files are missing. | step 1.4 |
| Red `[ERROR] ... not documented` lines in the terminal with the PyTorch backend | Harmless noise from transformers. If the status line says "Ready", it worked. | step 3.5 |
| The PyTorch reply repeats your whole prompt back | The slice is missing or starts at the wrong place. | `[3.3.2]` |
| `ModuleNotFoundError: No module named 'backends'` | You ran `python app.py` from a different folder than the one holding both files. | step 5 |

## How this recipe was checked

- **Install steps:** steps 1.1 to 1.5 were run, in order and with nothing else, in an empty Python environment on this machine. The check in 1.5 passed, and the app then ran both models in that environment. Skipping step 1.4 made `import llama_cpp` fail, so that step is required.
- **Answer key:** the finished app was driven through its real window with both models from step 1.6: click Load, send with the Send button, send again with Enter, and confirm the model remembered the first message.
- **This document:** a copy of the app was written from this recipe alone, without sight of the answer key, and put through the same test with both models.

The one thing not exercised is the Browse dialog itself; the tests set the model path directly.

## Known rough edges

This is the most basic version on purpose, so a few things are left undone. The answer key behaves the same way.

- Loading a second model starts a new conversation for the model, but the old messages stay on screen.
- The status line's "Ready: ..." shows whatever path was last picked with Browse, so browsing again without clicking Load makes it name the wrong model.
- If a reply fails with an error, your message stays in the conversation without an answer after it.
- Picking a `.gguf` file and then switching the radio button to PyTorch before Load gives an error, because the path and the backend no longer match.

Each of these is a small fix and a good first change to make on your own.

## Where to go next

Once your copy works, these are good second exercises, in rough order of difficulty: make replies stream in word by word, add a "New chat" button, add a system prompt box, remember the last model path between runs.
