# VoxMux recipe: level 4

Levels 1 to 3 were built and tested with one family of models, Qwen3.5, and one MCP server, the demo one you wrote. Level 4 is what came of trying everything else: seven other models and four MCP servers written by other people. Each item below fixes something that turned up that way, or something level 3 listed under "Known rough edges":

- **Saved conversations.** Each conversation is written to a file of its own after every reply. An Open chat button brings one back, and the one you had open returns when the app starts.
- **Switching models.** Loading a model no longer clears the conversation, so a second model can carry on where the first left off. The first model is let go before the second loads; until now the two had to fit in memory together, and a second Load could fail for that reason alone.
- **Models that are not Qwen.** A system prompt now works with a model whose chat template refuses a system message. A model whose template has no place for tools is noticed, and the status line says so. A tool call written as bare JSON, the way Llama 3.2 writes one, is read and run. The start-of-text token is no longer sent twice.
- **Memory.** A load no longer asks for a model's whole trained context. Newer models claim far more than a graphics card can hold, and on Windows such a load does not fail the way level 1 counted on.
- **A reply that fails** no longer leaves a question without an answer in the conversation.
- **Servers that will not stop.** A server started through `npx` or `uvx` is now ended together with its launcher.

Like the first three levels, this is a description in words, with no finished code. The finished code is in [`answer_key_level4/`](answer_key_level4/).

Start this only after level 3 works. Level 4 changes four of level 3's files and adds none.

## How the tags work in level 4

The steps continue level 3's numbering: steps 18 to 23. Search the level 4 answer key for `[22.8]` to land on the code step 22.8 describes.

As before, a block that level 4 *changes* gets a new tag that names the tag it replaces: `[22.9] (level 3: [16.6])` or `[19.8] (level 1: [3.3.4])`. The tag in the brackets is the one that block carries in your own file right now. Find the block by that tag, rewrite it as described, and change its tag to the new one followed by the note. If the block's tag already had a note of its own, such as `[7.5] (level 1: [3.2.2])`, the old note goes: the new tag is `[19.2] (level 2: [7.5])`, naming only the tag it replaces.

A longer tag can push a docstring's first line past 88 characters, the width the answer keys keep to. Shorten the wording after the tag. Only the tag has to match the answer key.

New docstrings follow the pattern of the ones you already have: the tag and one line saying what the block is for, a blank line, then a paragraph that starts "How it works:". The steps say what to put in that paragraph, and the wording is yours. Unless a step says otherwise, leave no blank lines inside a method's body.

"Set the status text" still means the call from step 4.5: `.config` on `self.status` with `text` set to the message.

| Steps | File | What happens |
| --- | --- | --- |
| 18 | | Set up: copy your level 3 folder. |
| 19 | `backends.py` | Changed: the system prompt for templates that refuse one, a way to ask whether a template describes tools, a limit on the context, one start-of-text token, and giving a model's memory back. |
| 20 | `tools.py` | Changed: tool calls written as bare JSON are read. |
| 21 | `mcp_client.py` | Changed: a server that will not stop is ended with everything it started. |
| 22 | `app.py` | Changed: saved conversations, Open chat, unloading, tools only where the template has them, and taking back a question that failed. |
| 23 | | Run it. |

`demo_mcp_server.py`, `mcp_servers.json` and `install.py` stay exactly as they are.

## What differs from one model family to the next

Every model file carries its own chat template, the small program that turns a list of messages into the one string of text the model was trained on. Levels 1 to 3 handed every template the same things and trusted it to cope. Running seven models from other families through the level 3 app showed five places where templates differ.

1. **The system message.** Most templates accept a first message with the role `"system"`. Mistral 7B's does not: it raises an error, "Conversation roles must alternate user/assistant/user/assistant/...", and in level 3 that error was all you got for any message sent with a system prompt or with Thinking mode on. Gemma 3's template has no system role either, but moves the text into the first user message by itself. Level 4 does the same for a template that will not.
2. **Tools.** A template is handed the list of tools and is free to ignore it. Of the eight model files tried, only two write the tools into the prompt: Qwen3.5 and Llama 3.2. With the other six the model is never told that tools exist. It does not fail; it just answers "17 * 23 = 391" from memory while the status line promises five tools. Level 4 asks each template and tells you.
3. **How a call is written.** Qwen3.5 opens a call with `<tool_call>`. Llama 3.2 uses no mark at all: the call is the whole reply, written as JSON, such as `{"name": "calculate", "parameters": {"expression": "17 * 23"}}`, with `;` between two calls. Note `"parameters"` where level 2's reader expected `"arguments"`. Level 3 showed that JSON to you as the answer and ran nothing.
4. **The start-of-text token.** Most models expect one special token before everything else. llama.cpp adds it to any prompt it is given as text. The templates of Llama 3.2, Gemma 3, Mistral 7B and DeepSeek R1 write it too, so those models were being shown two, and llama.cpp printed a warning in the terminal that this "will likely reduce response quality". Qwen3.5 has no such token, which is why levels 1 to 3 never met the problem.
5. **Thinking.** `enable_thinking` is a setting Qwen's template reads. Other templates ignore it. With those, Thinking mode still adds your thinking instructions to the system prompt, and the model thinks aloud in its answer if it follows them. DeepSeek R1 is the opposite case: its template starts every reply with thinking, whether the box is ticked or not. The app shows that thinking and marks its end, as it does for Qwen.

One more difference has nothing to do with templates: **how much context a model claims.** Step 3.3.1 starts each load at the longest context the model was trained for and halves it if the load fails. Mistral 7B was trained for 32,768 tokens. Llama 3.2, Gemma 3, Phi-4-mini and DeepSeek R1 all claim 131,072, and Qwen3.5 claims 262,144. llama.cpp sets memory aside for the whole context when it loads, and at those sizes it is far more than the card has: for Phi-4-mini, llama.cpp reports 4 GB for a context of 32,768 tokens, which makes 16 GB for 131,072, on a card with 11. So the load should fail and be halved until it fits. On Windows it does not fail. A current NVIDIA driver lets a program that has used up the card's memory carry on into the computer's ordinary memory, which the card reaches far more slowly. The load succeeds, with the full number in the status line, and if the ordinary memory runs short as well, llama.cpp stops the whole app with "CUDA error" in the terminal. That happened here with Phi-4-mini. Level 4 never asks for more than 32,768 tokens, and leaves the rest to compaction.

The table in "How this was checked" lists what each model did.

## How a conversation is saved

A conversation is two things: `self.messages`, which is what the model is shown, and the text in the chat log, which is what you see. They are not the same. The log has the model's thinking and a line for every tool call. And once level 2's compaction has run, the messages hold a summary of the early part where the log still has every word.

So both are saved, as one JSON object with the keys `"messages"` and `"log"`, in a file in a folder named `chats` next to `app.py`. The file is named after the moment the conversation's first reply finished, such as `2026-11-16 14.03.22.json`, and it is rewritten after every reply, so a crash loses nothing but the reply in progress. New chat does not delete anything: it only makes the app forget the file's name, so the next conversation gets a new file.

Opening a chat is the reverse: clear the window, put the messages back, write the log text back. The name of the open file is saved in `settings.json` with the other settings, which is how the app finds the conversation again when it starts.

## Python syntax you will meet

- **`text.rpartition(mark)`** splits a string at the *last* place `mark` appears and gives back three strings: what came before, the mark itself, and what came after. If the mark is not there, the first two are empty and the third is the whole string.
- **`a, b, c = ...`** takes apart something that holds exactly three values, as `kind, value = ...` did for two in step 4.12.
- **`text[:1]`** is the first character of a string, or an empty string if there is none. `text[0]` would raise an error on an empty string.
- **`items[:n]`** is the first `n` items of a list, or all of them if there are fewer. `items[:0]` is an empty list.
- **`b""`** is an empty value of the `bytes` kind, which is what `.encode("utf-8")` turns a string into.
- **`dict(d)`** makes a copy of a dictionary. Changing the copy leaves the original alone.
- **`items.pop()`** removes the last item of a list and gives it back.
- **`x and y`** gives `y` if `x` counts as true, and `x` otherwise. With two true-or-false values it is plain "both".
- **A method that replaces another.** If a class and the class it is built on both define a method with the same name, an object of the first class uses its own. That is how each backend can have its own `unload` while the code that calls it does not care which it has.
- **A body that is only a docstring.** A docstring is a statement, so a function whose body is nothing but its docstring is complete, and does nothing when called. It needs no `pass`.
- **`decoder.raw_decode(text, position)`**, on a `json.JSONDecoder()`, reads one JSON value that starts at `position` in `text`. It gives back two things, the value and the position just after it, and raises `ValueError` if no JSON value starts there. `json.loads` is stricter: it refuses a string with anything after the value.
- **`time.strftime(pattern)`** writes the current date and time as text. In the pattern, `%Y` is the year, `%m` the month, `%d` the day, `%H` the hour, `%M` the minute and `%S` the second.
- **`path.mkdir(exist_ok=True)`** makes a folder, and does nothing if it is already there. **`path.exists()`** says whether a file or folder is there.
- **`sys.platform`** is a string naming the kind of system Python is running on. On Windows it is `"win32"`.

## Step 18: set up

1. Copy your working level 3 folder to a new folder next to it named `my_build_level4`. In PowerShell:

   ```bash
   Copy-Item -Recurse my_build_level3 my_build_level4
   ```

2. Move into `my_build_level4`. Every change below is made there. There is nothing new to install.
3. Delete `settings.json` from the new folder if it was copied along, so that this level starts with a clean slate. (Level 4 reads a level 3 settings file without trouble; this just keeps the checks in step 23 simple.)

## Step 19: `backends.py`, changed

### 19.1 Top of the file

*Answer key: `[3.1]` (module docstring, extended).*

In the module docstring, change "(Level 3 version.)" to "(Level 4 version.)". After the paragraph on level 3, add one saying that level 4 makes room for models other than Qwen, whose chat templates differ in three ways that matter here: some refuse a system message, so the system prompt is then folded into the first user message; many say nothing about tools, so there is now a way to ask whether a template describes them; and many write the start-of-text token themselves, which llama.cpp would otherwise add a second time. End the paragraph with two more things: each backend can also give its memory back, so that one model can make way for the next; and a load no longer asks for a model's whole trained context, which for newer models is far more than a graphics card can hold. Then change the docstring's last sentence, the one about the numbers in square brackets, to name RECIPE_LEVEL4.md (19.x) as well.

Then add a constant. Below the two constants from step 3.1, after a blank line, write a comment line starting `# [19.1]` that says this is the most context a load will ever ask for, in tokens. Under it, set `LARGEST_CONTEXT` to the integer `32768`, and leave a blank line before the `# [7.1]` comment as there was before. That is about 25,000 words. If your card has memory to spare and you want longer conversations before compaction starts, this is the number to raise.

### 19.2 Change `Backend.fit_to_context`

*Answer key: `[19.2] (level 2: [7.5])`.*

Inside the `while True:` loop, the first four lines build the prompt: the line that sets `full` to `messages`, the `if system_prompt:` with the line under it, and the line that sets `prompt`. Replace all four with one line: set `prompt` to `self.build_with_system(messages, system_prompt, thinking, tools)`. The rest of the loop stays as it is.

Re-tag the docstring and add a last sentence: putting the system prompt in is now the job of `build_with_system`.

### 19.3 New method `build_with_system`

*Answer key: `[19.3]`.*

Parameters: `self`, `messages`, `system_prompt`, `thinking` and `tools`. Put it in the class `Backend`, after `fit_to_context` and before `compact`.

**Docstring:** start with `[19.3]`. Say that it builds the prompt with the system prompt in it, one way or another. Explain that most chat templates take the system prompt as a message of its own with the role "system", placed first; that some (Mistral's among them) have no such role and raise an error when they meet it; and that for those the system prompt is written at the start of the first user message instead, where the model reads it just the same. Add that this is done on a copy of the message, made with `dict()`, so the conversation itself is not changed, and that if the second attempt fails too, the template was objecting to something else, and that error is passed on.

1. `if not system_prompt:` return `self.build_prompt(messages, thinking, tools)`. With no system prompt there is nothing to place.
2. Set `system` to a dictionary with `"role"` set to `"system"` and `"content"` set to `system_prompt`.
3. A `try:` block with one line: return `self.build_prompt(...)` called with `[system] + messages`, `thinking` and `tools`. This is what level 2 did.
4. `except Exception:` with three lines:
   - Set `first` to `dict(messages[0])`, a copy of the first message.
   - Set `first["content"]` to `system_prompt`, plus `"\n\n"`, plus `first["content"]`.
   - Return `self.build_prompt(...)` called with `[first] + messages[1:]`, `thinking` and `tools`. `messages[1:]` is every message but the first.

The first message is always the user's: level 2's way of making room never leaves a conversation starting with anything else. The `except` cannot tell why the template complained, so it simply tries the other layout. If the complaint was about something else, the second call raises it again, and this time nothing catches it.

### 19.4 Change `compact`

*Answer key: `[19.4] (level 2: [7.6])`.*

The request for a summary used to be built as two messages, the first with the role `"system"`. A template that refuses that role would refuse this too, so the request now goes the same way as everything else.

1. Replace the `request` list of two dictionaries with a list of one: a dictionary with `"role"` set to `"user"` and `"content"` set to `"\n\n".join(lines)`. It now fits on one line.
2. Replace the line that sets `prompt` with a call to `self.build_with_system` with four arguments: `request`, `SUMMARY_INSTRUCTIONS`, `False` and `None`.

Re-tag the docstring. Its first line no longer fits with the longer tag, so shorten it to say that it replaces the older half with a short summary. Where the docstring says the model is asked to summarise the transcript at temperature 0, add that the request goes through `build_with_system`, because the instructions for the summary are a system prompt like any other.

### 19.5 New method `offers_tools`

*Answer key: `[19.5]`.*

Parameters: `self` and `tools`. Put it in the class `Backend`, after `compact`. It returns `True` or `False`.

**Docstring:** start with `[19.5]`. Say that it says whether this model's chat template describes tools. Explain that a template is free to ignore the tools it is handed, and many do, so that the model never learns there are any; and that the test is to build the same one-message prompt twice, once with the tools and once without: if both come out the same, the template wrote nothing about them.

1. Set `sample` to a list holding one dictionary: `"role"` set to `"user"`, `"content"` set to `"Hello"`.
2. Set `with_tools` to `self.build_prompt(sample, False, tools)`.
3. Return whether `with_tools` is not equal to (`!=`) `self.build_prompt(sample, False, None)`.

### 19.6 New method `Backend.unload`

*Answer key: `[19.6]`.*

Parameters: just `self`. Put it in the class `Backend`, after `offers_tools`. Its body is its docstring and nothing else.

**Docstring:** start with `[19.6]`. Say that it gives back the memory the model takes up; that the app calls it on the old model before it loads a new one, because a graphics card rarely has room for two; and that nothing is held by this base class, so there is nothing to do here, and each backend below replaces this method with its own.

### 19.7 Change `LlamaCppBackend.__init__`

*Answer key: `[19.7] (level 1: [3.3.1])`.*

One new line. After the line that reads the trained context into `size`, and before the `while True:` loop, set `size` to the smaller of `size` and `LARGEST_CONTEXT`, with `min(...)`. A model trained for less than the limit keeps its own number, and the loop below still halves a context that will not fit.

Re-tag the docstring. Its first line no longer fits with the longer tag, so shorten it to say that it loads the .gguf file with a context that fits. In the "How it works" paragraph, where it says the real load starts at the longest context the model was trained for, add "or at `LARGEST_CONTEXT` if that is less". Then add a paragraph for level 4: newer models are trained for contexts of 131,072 tokens and more, which no ordinary graphics card can hold; such a load ought to fail and be halved, but on Windows a current NVIDIA driver lets a program that has used up the card carry on into ordinary memory; the load then succeeds with a context the card cannot hold, and if the ordinary memory runs short as well, llama.cpp stops the whole app; starting no higher than `LARGEST_CONTEXT` avoids that, and compaction (step 7) deals with a conversation that outgrows it.

The class docstring just above, `[3.3]`, says the class loads the weights with as much context as the graphics card can hold. Add "up to LARGEST_CONTEXT" there. Its tag stays as it is.

`TransformersBackend` is left alone. PyTorch sets no memory aside for the context when it loads, so there is nothing to limit there.

### 19.8 Change `LlamaCppBackend.stream`

*Answer key: `[19.8] (level 1: [3.3.4])`.*

1. Make the first line of the method's body, above the call to `create_completion`: set `tokens` to `self.llm.tokenize(...)` called with `prompt.encode("utf-8")`, `add_bos=False` and `special=True`. This is the call `count_tokens` makes in step 3.3.3: the prompt as it stands, with nothing added.
2. Set `start` to `self.llm.tokenize(b"", add_bos=True)`. `b""` is an empty piece of text, as bytes. Tokenizing nothing, while asking for the start-of-text token to be added, gives a list holding just that token, or an empty list for a model that wants none.
3. `if tokens[: len(start)] != start:` set `tokens` to `start + tokens`. `tokens[: len(start)]` is as many tokens from the front of the prompt as `start` holds. If they are not the same as `start`, the template did not write the token, so it is put in front. For a model that wants none, both sides are empty lists, and nothing happens.
4. In the call to `create_completion`, change the first argument from `prompt` to `tokens`. Handed a list of tokens instead of text, llama.cpp adds nothing of its own.

Re-tag the docstring, shortening its first line to say that it yields the text the model writes after prompt. Keep the paragraph about chunks, then add a paragraph for level 4: the prompt is turned into tokens here, not left to `create_completion`; most models expect one start-of-text token before everything else; llama.cpp adds it to a prompt given as text, but many chat templates write it too, and a model that is shown two answers worse; so the prompt is tokenized as it stands, `tokenize()` is then asked for the tokens of nothing at all with `add_bos=True`, which gives a list holding the start-of-text token (or an empty list for a model that wants none), and if the prompt does not already begin with that list, it is put in front; and `create_completion` adds nothing to a list of tokens.

### 19.9 New method `LlamaCppBackend.unload`

*Answer key: `[19.9]`.*

Parameters: just `self`. Put it at the end of the class `LlamaCppBackend`, after `stream`.

**Docstring:** start with `[19.9]`. Say that it gives the model's memory back to the graphics card, and that llama.cpp keeps the weights and the context in memory of its own, outside Python's reach, and `close()` is how it is told to free them.

1. Call `self.llm.close()`.

### 19.10 New method `TransformersBackend.unload`

*Answer key: `[19.10]`.*

Parameters: just `self`. Put it at the end of the class `TransformersBackend`, after `stream`.

**Docstring:** start with `[19.10]`. Say that it gives the model's memory back to the graphics card. Explain that Python frees an object once nothing refers to it, so letting go of the model is enough to free its weights; and that PyTorch keeps the freed graphics memory for itself, ready for its next use, so `empty_cache()` hands it back, and llama.cpp can have it if a GGUF model is loaded next.

1. `import torch`, inside the method like this class's other imports, followed by a blank line.
2. Set `self.model` to `None`.
3. Call `torch.cuda.empty_cache()`. On a machine with no graphics card it does nothing.

### 19.11 Checkpoint: test it without a window

From inside `my_build_level4/`, start the Python prompt and load a GGUF model as in step 3.6, keeping the backend in a variable. Then:

1. Import `Toolbox` from `tools`, make one with an empty list of servers, and call `.offers_tools(...)` on your backend with the toolbox's `.schemas`. A Qwen3.5 model gives `True`.
2. Open Task Manager's Performance tab and watch the graphics card's dedicated memory. Call `.unload()` on your backend. The memory falls back to where it was before you loaded the model.

## Step 20: `tools.py`, changed

### 20.1 Top of the file

*Answer key: `[8.1]` (module docstring, extended).*

In the module docstring, add "(Level 4 version.)" on a line of its own under the first line. After the paragraph that ends with the app not caring where a tool lives, add one on level 4: it reads a second way of writing a call; models in the Llama 3.2 family use no `<tool_call>` mark, and the call is the whole reply, written as JSON; so a reply that starts like JSON is now treated as a possible call, and only counted as ordinary text once it is clear that it is not one. Rewrite the last sentence, which named only RECIPE_LEVEL2.md, to say the numbers match RECIPE_LEVEL2.md (8.x) and RECIPE_LEVEL4.md (20.x).

### 20.2 New function `text_before_call`

*Answer key: `[20.2]`.*

Parameters: `text`. Put it after `schema_for` and before `parse_tool_calls`.

**Docstring:** start with `[20.2]`. Say that it returns the part of a reply that comes before any tool call. Explain that Qwen-style models open a call with `<tool_call>`, so the text before that mark is ordinary text; that Llama 3.2-style models use no mark, so the call is the whole reply, written as JSON, and starts with `{` (one call) or `[` (a list of them); that while such a reply is still arriving there is no telling whether it will turn out to be a call, so it is treated as one, which means none of it is ordinary text yet; and that `parse_tool_calls` gives the final word once the reply is complete.

1. `if text.lstrip()[:1] in ("{", "["):` return an empty string. `lstrip()` removes spaces and line breaks from the start, and `[:1]` is the first character of what is left.
2. Otherwise return `text.split("<tool_call>")[0]`, which is what level 2 did.

### 20.3 New function `json_calls`

*Answer key: `[20.3]`.*

Parameters: `text`. Put it after `text_before_call`. It returns a list of calls, each a dictionary with `"name"` and `"arguments"`, the same shape level 2 used.

**Docstring:** start with `[20.3]`. Say that it reads every tool call that is written as JSON somewhere in text. Explain `raw_decode`: it reads one JSON value starting at a given position and reports where it ended, so whatever stands around the values (a closing tag, a `;` between two calls) does not matter. Say that every `{` and `[` in the text is tried as the start of a value and the ones that are not JSON are stepped over; that a value on its own is handled as a list of one; and that an item counts as a call if it is an object with a name and arguments. End with the keys: models do not agree on them, so the name is under `"name"` or, now and then, `"function"`, and the arguments are under `"arguments"` or `"parameters"`, sometimes as JSON inside a string.

1. Set `decoder` to a new `json.JSONDecoder()`, `calls` to an empty list, and `position` to `0`.
2. A `while` loop that runs as long as `position` is less than `len(text)`. Inside it:
   - `if text[position] not in "{[":` add 1 to `position` and `continue`. Only those two characters can start a call.
   - A `try:` block that sets `value, position` to `decoder.raw_decode(text, position)`. On success `position` jumps to just after the value. In `except ValueError:` add 1 to `position` and `continue`.
   - `if isinstance(value, dict):` set `value` to a list holding `value`.
   - Loop over `value` with the loop variable `item`. Inside that loop:
     - `if not isinstance(item, dict):` then `continue`.
     - Set `name` to `item.get("name") or item.get("function")`.
     - Set `arguments` to `item.get("arguments", item.get("parameters"))`: the first key if it is there, otherwise the second, otherwise `None`.
     - `if isinstance(arguments, str):` a `try:` that sets `arguments` to `json.loads(arguments)`, with `except ValueError:` then `continue`.
     - `if isinstance(name, str) and isinstance(arguments, dict):` append to `calls` a dictionary with `"name"` set to `name` and `"arguments"` set to `arguments`.
3. After the `while` loop, return `calls`.

The last `if` is what keeps ordinary JSON from being taken for a call. `{"name": "Biscuit"}` has no arguments, so `arguments` is `None`, which is not a dictionary, and nothing is appended.

### 20.4 Change `parse_tool_calls`

*Answer key: `[20.4] (level 2: [8.6])`.*

The function keeps its name and what it returns, a tuple of text and calls, but its body is rewritten around the two new functions.

1. Set `before` to `text_before_call(text)`.
2. Set `rest` to `text[len(before) :]`: everything from where `before` ends.
3. Start an empty list `calls`.
4. Loop over `CALL_PATTERN.findall(rest)` with the loop variable `body`. Inside, keep only the `<function=...>` reading from level 2: set `match` to `FUNCTION_PATTERN.search(body)`, and `if match:` build `arguments` from `PARAMETER_PATTERN` and append the call, exactly as before. The lines that came first in the old loop go: the `body.strip()` line, and the whole `if body.startswith("{"):` block with its `continue`.
5. After the loop, `if not calls:` set `calls` to `json_calls(rest)`. This reads JSON calls with `<tool_call>` around them, which the deleted block used to do, and bare ones.
6. `if not calls:` return `text.strip(), []`.
7. Return `before.strip(), calls`.

Item 6 is new behaviour. In level 2 a reply with an unreadable call lost everything from `<tool_call>` on. Now a reply in which no call can be read is ordinary text, all of it, however it began.

Re-tag the docstring, shortening its first line to say that it splits a reply into its text and its tool calls, and rewrite the rest for the new order: `text_before_call` says where a call may start; in the rest of the reply, calls in Qwen3.5's style are looked for first, and if there are none, `json_calls` looks for calls written as JSON, with or without `<tool_call>` around them; both kinds are read into the same shape; values read from parameters are left as strings for `Toolbox.run()` to convert; and if no call can be read, the reply was ordinary text after all, so all of it is returned as text.

### 20.5 Checkpoint: test it without a window

From inside `my_build_level4/`, start the Python prompt, import `parse_tool_calls` from `tools`, and call it on three strings. Wrap each in single quotes, since they contain double quotes.

1. `{"name": "calculate", "parameters": {"expression": "6 * 7"}}` gives an empty string and a list of one call, named `calculate`, with the arguments in a dictionary.
2. `{"colour": "blue"}` gives the same string back, and an empty list.
3. `Sure.<tool_call>{"name": "calculate", "arguments": {"expression": "1+1"}}</tool_call>` gives `'Sure.'` and one call, as it did in level 2.

## Step 21: `mcp_client.py`, changed

A server from someone else is rarely started directly. The config says `npx` or `uvx`, which is a small launcher: it downloads the server if need be and then starts it as a program of its own. So the program this client started, and can kill, is the launcher. The official servers all stop when asked politely, and for them nothing changes. But kill the launcher of a server that ignores the request, and the server itself is left running with nobody to talk to. This was checked: after `kill()` alone, the real server was still there in both cases.

### 21.1 Top of the file

*Answer key: `[9.1]` (module docstring, extended).*

1. In the module docstring, add "(Level 4 version.)" on a line of its own under the first line. After the "How it works" paragraph, add one on level 4: it changes how a server that will not stop is dealt with; servers from other people are usually started through a launcher such as npx or uvx, so the program this client starts is not the server itself; killing only the launcher would leave the real server running, so the launcher is now ended together with everything it started. Rewrite the last sentence, which named only RECIPE_LEVEL2.md, to say the numbers match RECIPE_LEVEL2.md (9.x) and RECIPE_LEVEL4.md (21.x).
2. Add `import signal` to the imports, between `import shutil` and `import subprocess`.

### 21.2 Change `__init__`

*Answer key: `[21.2] (level 2: [9.2.1])`.*

1. Add an eighth keyword argument at the end of the `subprocess.Popen(...)` call: `start_new_session` set to `True`. On Linux and macOS this starts the server as the head of its own group of processes, and everything the server starts joins that group. Windows has no such groups and ignores the setting.

Re-tag the docstring, shortening its first line to say that it starts the server and lists its tools. Add at the end that `start_new_session=True` puts the server, and anything it starts, in a group of its own, which `stop_tree` relies on, and that Windows has no such groups and ignores the setting.

### 21.3 Change `close`

*Answer key: `[21.3] (level 2: [9.2.9])`.*

1. In the `except Exception:` block, replace both lines (`self.process.kill()` and `self.process.wait()`) with one call: `self.stop_tree()`.

Re-tag the docstring, shortening its first line to say that it stops the server and closes its pipe and its log. Where it said that a server still running after five seconds is killed, say instead that `stop_tree` ends it by force, along with everything it started.

### 21.4 New method `stop_tree`

*Answer key: `[21.4]`.*

Parameters: just `self`. Put it in the class `MCPServer`, after `close`.

**Docstring:** start with `[21.4]`. Say that it ends the server by force, with every program it started. Explain the launcher as above: a server started through npx or uvx is not this client's child; the child is a small launcher and the server is a program the launcher started, so `kill()` would end only the launcher. Then the two ways: on Windows the `taskkill` command does the whole job, where `/T` means "and everything it started" and `/F` means "by force", and its output is captured so that it does not appear in the terminal; elsewhere the server was started as the head of its own group of processes (see `__init__`), and `killpg` sends the whole group the signal that cannot be refused; if the group has already gone, there is nothing to do. End by saying that `wait()` then collects the launcher's exit code, so that Python knows it has ended.

1. `if sys.platform == "win32":` call `subprocess.run(...)` with two arguments, each on its own line: a list of five strings, `"taskkill"`, `"/F"`, `"/T"`, `"/PID"` and `str(self.process.pid)`; and `capture_output` set to `True`.
2. `else:` a `try:` block with one line, `os.killpg(self.process.pid, signal.SIGKILL)`, then `except OSError:` with `pass`.
3. After the `if` and `else`, back at their level: call `self.process.wait()`.

## Step 22: `app.py`, changed

### 22.1 Top of the file

*Answer key: `[4.1]` (docstring, extended) and `[22.1]` (new constant).*

1. In the module docstring: change "(Level 3 version.)" to "(Level 4 version.)". After the paragraph on level 3, and before the line that says how to run the app, add one on level 4. Say that it saves conversations: each one is written to a file of its own in the chats folder after every reply, can be opened again, and is brought back when the app starts. Say that loading a model no longer clears the conversation, so a second model can carry on where the first left off, and that the first model is let go before the second is loaded, so the two need not fit in memory together. Say that the app also copes with models other than Qwen: it notices a model whose chat template has no place for tools, shows a tool call written as bare JSON as a call and not as text, and takes a question that ended in an error back out of the conversation. Change the last sentence, the one about the numbers in square brackets, to name RECIPE_LEVEL4.md (22.x) as well.
2. Add `import time` to the imports, between `import threading` and `import tkinter as tk`.
3. Change the last import so that it brings in three names from `tools`: `Toolbox`, `parse_tool_calls` and `text_before_call`.
4. Under the level 3 constants, leave a blank line, then a comment line starting `# [22.1]` that says this constant is the folder conversations are saved in, next to this file. Then the constant: `CHATS_FOLDER`, set to `pathlib.Path(__file__).with_name("chats")`, the same way `SETTINGS_FILE` is made.

### 22.2 Change `__init__`

*Answer key: `[22.2] (level 3: [16.2])`.*

1. After `self.allowed_tools`, add two attributes, each with a short comment after it:
   - `self.chat_file`, set to `None`. It is where this conversation is saved, once it has been.
   - `self.offer_tools`, set to `False`. It becomes `True` if the loaded model's template describes tools.
2. Re-tag the docstring and add to its last sentence that the conversation that was open last time comes back with the settings.

Also update the class docstring (it keeps its tag, `[4.2]`). The small helpers now start with `read_chat` and `save_chat`, before `start_worker`. The button handlers gain `open_chat`, after `new_chat`.

### 22.3 Change the top row

*Answer key: `[22.3] (level 3: [16.3])`.*

At the end of the top row block in `build_widgets`, after the New chat button is packed:

1. Create a `tk.Button` with parent `top`, `text` set to `"Open chat..."`, and `command` set to `self.open_chat`. Store it as `self.open_chat_button`. The call is too long for one line, so put its three arguments on a line of their own inside the parentheses.
2. Pack it with `side` set to `"right"` and `padx` set to `8`. Things packed on the right fill in from the right-hand edge, so it lands to the left of New chat.

Change the block's comment: re-tag it, and make its end read "load it, start a new chat, or open a saved one".

### 22.4 Change `load_model`

*Answer key: `[22.4] (level 1: [4.8])`.*

In levels 1 to 3, the old model was only let go when the new one arrived in `poll_results` and took its place in `self.backend`. For a moment both were in memory. With a model that fills the graphics card, the second never fitted, and Load failed with "Failed to load model from file" until you restarted the app.

1. Straight after the call to `self.set_busy(True)`, add: `if self.backend is not None:` with two lines inside, a call to `self.backend.unload()` and then `self.backend = None`.

Re-tag the docstring, shortening its first line to say that the Load button starts loading the picked model. Add that a model that is already loaded is let go first, since a graphics card rarely has room for two, and that this means a load that fails leaves no model loaded.

### 22.5 Change `new_chat`

*Answer key: `[22.5] (level 3: [16.5])`.*

1. After the line that sets `self.messages` to an empty list, add one that sets `self.chat_file` to `None`.

Re-tag the docstring, shortening its first line to say that the New chat button starts a fresh conversation. Add that the conversation that was open stays in its file, and that forgetting the file's name here is what makes `save_chat` start a new file for the next one.

### 22.6 New method `open_chat`

*Answer key: `[22.6]`.*

Parameters: just `self`. Put it after `new_chat`.

**Docstring:** start with `[22.6]`. Say that the Open chat button lets the user pick a saved conversation and shows it; that this is the same file picker Browse uses, opened in the chats folder; that if that folder does not exist yet, the picker opens wherever it likes; and that Cancel gives back an empty string.

1. Set `path` to `filedialog.askopenfilename(...)` with two keyword arguments on a line of their own: `initialdir` set to `CHATS_FOLDER`, and `filetypes` set to a list holding one tuple, `("Saved chat", "*.json")`.
2. `if path:` call `self.read_chat(path)`.

### 22.7 New method `read_chat`

*Answer key: `[22.7]`.*

Parameters: `self` and `path`. Put it after `open_chat`. Two things call it: `open_chat`, and `load_settings` when the app starts.

**Docstring:** start with `[22.7]`. Say that it brings one saved conversation back into the window. Explain that a chat file holds one JSON object with two keys, as written by `save_chat`; that both are read before anything in the window is touched, so a file that is missing, is not JSON, or lacks a key leaves the conversation on screen as it was and only changes the status line; and that the window is then cleared, the messages and the log text are put back, and the file is remembered so that later replies are saved to it.

1. A `try:` block with three lines:
   - Set `saved` to `json.loads(...)` of `pathlib.Path(path).read_text(encoding="utf-8")`.
   - Set `messages` to `saved["messages"]`.
   - Set `log` to `saved["log"]`.
2. `except (OSError, ValueError, KeyError, TypeError):` with two lines: set the status text to an f-string reading `Could not open the chat in `, then `path` in braces; then `return`. These are the same four errors `load_settings` catches in step 16.15, for the same reasons.
3. Leave the `try` and call `self.new_chat()`.
4. Set `self.messages` to `messages`.
5. Call `self.append_chat(log)`.
6. Set `self.chat_file` to `pathlib.Path(path)`.

The order of the last four lines matters. `new_chat` empties the list, clears the log and forgets the file, so it must come first, and the file is remembered last.

### 22.8 New method `save_chat`

*Answer key: `[22.8]`.*

Parameters: just `self`. Put it after `read_chat` and before `send`. It runs on the main thread, called from `poll_results`.

**Docstring:** start with `[22.8]`. Say that it writes this conversation to its file in the chats folder. Explain that the first time a conversation is saved it is given a file named after the date and time, and the chats folder is made if it is not there yet (`exist_ok=True` means "no error if it is"); that if a file of that name is already there, from a chat begun in the same second, a number in brackets is added, counting up until the name is free, because otherwise the older chat would be overwritten; and that after that the same file is rewritten each time. Say what is saved: "messages" is what the model is shown, which is the summary once old messages have been summarised, and "log" is the text on screen, which still has every word. Add that `ensure_ascii=False` keeps letters such as "é" as they are, instead of as codes, and that if the file cannot be written, the status line says so and the chat carries on.

The whole body is one `try:` block and its `except`.

1. Inside the `try:`, first `if self.chat_file is None:` with these lines inside it:
   - Call `CHATS_FOLDER.mkdir(exist_ok=True)`.
   - Set `name` to `time.strftime("%Y-%m-%d %H.%M.%S")`. Full stops separate the time's parts because Windows does not allow a colon in a file name.
   - Set `self.chat_file` to `CHATS_FOLDER` divided by (`/`) an f-string: `name` in braces, then `.json`.
   - Set `number` to `2`.
   - `while self.chat_file.exists():` with two lines inside: set `self.chat_file` to `CHATS_FOLDER` divided by an f-string reading `name` in braces, a space, `(`, `number` in braces, `)`, then `.json`; and add 1 to `number`.
2. Still inside the `try:`, set `saved` to a dictionary laid out one key per line: `"messages"` set to `self.messages`, and `"log"` set to `self.chat_log.get("1.0", "end-1c")`. `"end-1c"` means "the end, less one character": it leaves off the newline that Tk always adds.
3. Set `text` to `json.dumps(saved, indent=2, ensure_ascii=False)`.
4. Call `self.chat_file.write_text(text, encoding="utf-8")`.
5. `except OSError as error:` set the status text to an f-string reading `Could not save this chat: `, then `error` in braces.

The `except` matters more than it looks. This method is called from `poll_results`. An error that escaped there would stop `poll_results` before it asks to be called again, and the window would never hear from a worker again.

### 22.9 Change `send`

*Answer key: `[22.9] (level 3: [16.6])`.*

1. Change the line that sets `use_tools` so that it reads `self.use_tools.get() and self.offer_tools`. Tools are used only if the box is ticked and the template has a place for them.

Re-tag the docstring and add that as its last sentence.

### 22.10 Change `reply_worker`

*Answer key: `[22.10] (level 3: [16.8])`.*

Reading the calls out of a reply moves into `stream_reply`, which needs to know about them while the reply is still arriving. Three changes:

1. Replace the two lines that set `answer` and then `text, calls` with one statement: set `text, calls` to `self.stream_reply(...)`, called with the same four arguments as before. It is too long for one line, so put the arguments on a line of their own inside the parentheses.
2. The `if` under the line that sets `stopped` loses its third condition. It now reads `if stopped or not calls:`. With tools off, `stream_reply` finds no calls, so `not use_tools` has nothing left to do. Reword the comment inside the `if` to say: no call to run, or the reply was stopped; the text is kept as the answer, and a call in a stopped reply is not run.
3. In the `except Exception as error:` at the end, change the label that is put in the queue from `"error"` to `"failed"`. `load_worker` keeps `"error"`.

Re-tag the docstring. Replace the sentence about Use tools being off with: with tools off, no tools are offered and `stream_reply` does not look for calls, so whatever the model writes is its answer. Add at the end that an error is reported as "failed", not as "error", so that `poll_results` can tell a reply that went wrong from a model that would not load.

### 22.11 Change `stream_reply`

*Answer key: `[22.11] (level 3: [16.9])`.*

The method now returns two things, the reply's text and its calls, and it decides what part of a reply may be shown while it arrives.

1. Inside the loop, replace the line that sets `visible` to `reply.split("<tool_call>")[0]` with four lines:
   - Set `thoughts, end_mark, answer` to `reply.rpartition("</think>")`.
   - `if tools:` and, on the line under it, set `answer` to `text_before_call(answer)`.
   - Set `visible` to `thoughts` plus `end_mark` plus `answer`.

   The line after them, which replaces `</think>` in `visible` and strips it, stays, and so does the rest of the loop.
2. After `pieces.close()`, leave a blank line and replace the `return` with the following.
   - Set `answer` to `reply.split("</think>")[-1].strip()`. This is what the old `return` returned.
   - `if not tools:` return `answer, []`.
   - Set `text, calls` to `parse_tool_calls(answer)`.
   - `if not calls:` with four lines inside: set `whole` to `reply.replace("</think>", "\n[end of thinking]").strip()`; set `held_back` to `whole[len(shown) :]`; then `if held_back:` put `("piece", held_back)` in `self.results`.
   - Return `text, calls`.

While a reply that starts with `{` is arriving, `text_before_call` lets none of it through, so nothing is shown. If it turns out to be a call, nothing ever is, apart from the line `reply_worker` writes about the tool. If it turns out to be an answer that merely began with a bracket, `whole` is everything that should be on screen, `shown` is what already is, and the difference is put up in one go.

Re-tag the docstring, changing its first line to say that it streams one reply and returns its text and calls. Take out the sentences saying that anything from `<tool_call>` onwards is kept out of the log and that it returns the reply ready for `parse_tool_calls`. Add a second paragraph: a tool call is meant for the app, not the reader, so it is kept out of the log; `rpartition` splits the reply at its last `</think>` into the thinking, the mark itself and the answer (with no mark, all of it is the answer); when tools are in use, only the part of the answer that `text_before_call` lets through is shown; once the reply is complete, `parse_tool_calls` reads the calls, and if there turn out to be none, anything that was held back because it looked like the start of a call is shown after all; and with tools off the reply is never searched for calls.

### 22.12 Change `poll_results`

*Answer key: `[22.12] (level 3: [16.11])`.*

1. **Save after every reply.** In the `"reply"` branch, between the line that sets the status text to `Ready: ...` and the call to `self.set_busy(False)`, add a call to `self.save_chat()`. It comes after the status line is set, so that a "Could not save" message is not overwritten.
2. **Keep the conversation.** In the `"loaded"` branch, delete the line that calls `self.new_chat()`, comment and all.
3. **Ask the template about tools.** In its place, set `self.offer_tools` to `backend.offers_tools(toolbox.schemas)`.
4. **Say so.** After the statement that builds `text` and before `if problems:`, add: `if not self.offer_tools:` set `text` to `text` plus the string `" This model's template has no place for tools."`. The string starts with a space.
5. **A reply that failed.** Add a branch between `"loaded"` and `"error"`: `elif kind == "failed":` with five lines inside.
   - A `while` loop whose condition is `self.messages and self.messages.pop()["role"] != "user"`, and whose body is `pass`. Each trip round removes the last message; the loop ends once the message it removed was the user's, or the list is empty.
   - Call `self.append_chat` with `" [failed]\n\n"`. Like level 3's `[stopped]`, the mark starts with a space, so that it is set off from any words that had arrived.
   - Set the status text to an f-string reading `Error: `, then `value` in braces, and call `self.set_busy(False)`, as the `"error"` branch does.

Why take the question back? A reply can fail after the user's message has joined the conversation, and after a tool call and its result have too. Left there, they would be followed by the next question, and a template like Mistral's refuses two user messages in a row: one error would lead to another on every Send until New chat. The loop removes everything from the failed turn, back to and including the question. A model that would not load asked nothing, which is why it needs a label of its own.

Re-tag the docstring. Say that the other *four* results mean the work is over. Replace the sentence about the old conversation being cleared with: a finished reply is saved with the rest of its conversation; when a model loads, the conversation is kept, the model's template is asked whether it describes tools, and the model is given a function to call when compaction starts (keep the explanation of the lambda). Add at the end: when a reply fails, the log is marked with [failed] and the question that got no answer is taken back out of the conversation; `pop()` removes the last message and hands it back, and the loop goes on until the one it removed was the user's; left in, it would be followed by the next question, and some chat templates refuse two user messages in a row.

### 22.13 Change `set_busy`

*Answer key: `[22.13] (level 3: [16.14])`.*

1. After the line that sets the state of `self.new_chat_button`, add one that does the same for `self.open_chat_button`.

Re-tag the docstring and add Open chat to the buttons that follow `busy`.

### 22.14 Change `load_settings`

*Answer key: `[22.14] (level 3: [16.15])`.*

1. Inside the `try:` block, after the line that reads `"allowed_tools"`, add: `if saved["chat_file"]:` call `self.read_chat(saved["chat_file"])`.

It is the last thing read on purpose. A settings file written by level 3 has no `"chat_file"`, so that line raises `KeyError`, which the `except` already catches, and every setting read before it is kept.

Re-tag the docstring, shortening its first line to say that it reads settings.json back into the window. Add that the conversation that was open when the app closed is read last, so a settings file from level 3, which has no "chat_file", still gives back everything else.

### 22.15 Change `save_settings`

*Answer key: `[22.15] (level 3: [16.16])`.*

1. Before the `saved` dictionary, add three lines: set `chat_file` to an empty string; then `if self.chat_file is not None:` set `chat_file` to `str(self.chat_file)`.
2. Add a ninth entry at the end of the dictionary: `"chat_file"` set to `chat_file`.

Re-tag the docstring and add that the open conversation's file is saved as text, because JSON has no way to write a Path, and as an empty string if there is none.

`close` is not changed. The conversation was saved when its last reply finished.

## Step 23: run it

First, without a model. From the repo root:

```bash
python check_my_build.py my_build_level4
```

It works out that the folder holds level 4 from the `save_chat` method in your `app.py`. One test, for step 21, starts a small server that refuses to stop and takes about five seconds to deal with it. Fix anything that fails before you go on.

Then, from inside `my_build_level4`, with a real model:

```bash
python app.py
```

Load the 4B model. The status line says `32768 tokens of context`, where level 3 said `262144`. Then check:

1. **Saving.** Tell the model your name. When the reply finishes, a folder named `chats` appears next to `app.py`, with one file in it named after the date and time. Open the file and read it: your message and the reply are under `"messages"`, and the text on screen is under `"log"`.
2. **A new file for a new chat.** Click New chat and say something else. A second file appears, and the first is untouched.
3. **Open chat.** Click Open chat..., pick the first file, and ask "What is my name?" The log shows the first conversation, and the model knows.
4. **Coming back.** Close the app and start it again. The conversation is on screen before you load anything. Load the model and carry on.
5. **Switching models.** With the conversation still on screen, click Load again. In levels 1 to 3 this failed with "Failed to load model from file" for a model that fills the card. Now it loads, and the conversation is still there. Then pick the 2B PyTorch model and load that: it answers a question about the same conversation.
6. **Tools as before.** "What is 1234 * 5678? Use the calculator." and "Save a note that says: buy oat milk." behave as in level 3.

If you have a model from another family, load it and check:

7. **No tools.** With a model whose status line ends "This model's template has no place for tools.", ask "What is 17 * 23? Use the calculator." The model answers by itself; no tool line appears.
8. **A system prompt everywhere.** Type a system prompt, such as "Answer in French.", and send a message. With Mistral 7B, level 3 answered every such message with "Error: Conversation roles must alternate..."; now it answers in French.
9. **Bare JSON.** With a Llama 3.2 model, ask the calculator question. The log shows the `[calculate ... -> ...]` line and not the JSON.

Step 2 of [RECIPE.md](RECIPE.md) has the download command; these are the files that were used here:

| Model | Repository on Hugging Face | File | Size |
| --- | --- | --- | --- |
| Llama 3.2 3B | `unsloth/Llama-3.2-3B-Instruct-GGUF` | `Llama-3.2-3B-Instruct-Q4_K_M.gguf` | 2.0 GB |
| Mistral 7B v0.3 | `bartowski/Mistral-7B-Instruct-v0.3-GGUF` | `Mistral-7B-Instruct-v0.3-Q4_K_M.gguf` | 4.4 GB |
| DeepSeek R1 1.5B | `unsloth/DeepSeek-R1-Distill-Qwen-1.5B-GGUF` | `DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf` | 1.1 GB |

## When it does not work

| What you see | Likely cause | Look at |
| --- | --- | --- |
| The status line ends "This model's template has no place for tools." for every model, Qwen included, and no tool is ever called | `offers_tools` builds both of its prompts the same way, so they never differ. Or `poll_results` never sets `self.offer_tools`, which then keeps its starting value of `False`. | `[19.5]`, `[22.12]` |
| With Mistral 7B and a system prompt, every message gets "Error: Conversation roles must alternate..." | `fit_to_context` still puts the system message in front itself instead of calling `build_with_system`. | `[19.2]` |
| In a chat file saved with Mistral 7B, the first message begins with the system prompt, repeated once for every reply so far | `build_with_system` changes the conversation's own first message. `dict(...)` is missing, so `first` is the real message and not a copy. | `[19.3]` |
| With Llama 3.2, a tool call appears in the log as JSON, such as `{"name": "calculate", "parameters": ...}`, and nothing is run | One of three things in `tools.py`. `parse_tool_calls` does not call `json_calls` when it found no `<tool_call>`. Or `text_before_call` lacks its check for `{` and `[`. Or `json_calls` looks for the arguments under `"arguments"` only, and Llama writes `"parameters"`. | `[20.4]`, `[20.2]`, `[20.3]` |
| With tools on, an answer that is itself JSON leaves an empty `Model:` line, though the chat file holds the answer | `stream_reply` does not put the text it held back into the queue when it turns out not to be a call. | `[22.11]` |
| With tools on, every reply appears twice | `held_back` is the whole reply and not only the part after what was already shown: the slice `[len(shown) :]` is missing. | `[22.11]` |
| Every reply ends with `[failed]`, and the status shows `Error: 'tuple' object has no attribute 'lstrip'` | `reply_worker` still passes what `stream_reply` returns to `parse_tool_calls`. It is now a pair, already parsed. | `[22.10]` |
| With tools on, every reply ends with `[failed]`, and the status shows `Error: too many values to unpack (expected 2)` | `stream_reply` returns only the text at its end, not the text and the calls. | `[22.11]` |
| After an error there is no `[failed]` in the log, and the chat file later shows the unanswered question followed by the next one | `reply_worker` still reports `"error"` and not `"failed"`. Or, if `[failed]` is there, the `while` loop that takes the messages back is missing from the `"failed"` branch. | `[22.10]`, `[22.12]` |
| A model that will not load takes the last question and its answer out of the conversation, and the log gets a `[failed]` | `load_worker` reports `"failed"`. Only `reply_worker` should: `load_worker` keeps `"error"`. | `[22.10]` |
| No `chats` folder ever appears | `poll_results` does not call `save_chat()` in its `"reply"` branch. | `[22.12]` |
| After the first reply Send stays grey, and the terminal shows `AttributeError: 'NoneType' object has no attribute 'write_text'` | `save_chat` put the new file name in a variable called `chat_file` and not in `self.chat_file`. | `[22.8]` |
| After New chat, the new conversation is written over the old one's file | `new_chat` does not set `self.chat_file` back to `None`. | `[22.5]` |
| Open chat... leaves an empty window, with no error | `read_chat` calls `new_chat()` after filling the window in, not before. | `[22.7]` |
| Open chat... adds the saved conversation below the one already on screen | `read_chat` does not call `new_chat()` at all. | `[22.7]` |
| The window will not close, and the terminal shows `TypeError: Object of type WindowsPath is not JSON serializable` (`PosixPath` on Linux and macOS) | `save_settings` puts `self.chat_file` in the dictionary as it is, without `str(...)`. | `[22.15]` |
| The first time level 4 starts with a `settings.json` from level 3, none of the settings come back | `load_settings` reads `"chat_file"` before the other keys. A level 3 file has no such key, so reading stops there. It must be read last. | `[22.14]` |
| The last conversation is not on screen when the app starts, though `settings.json` names its file under `"chat_file"` | `load_settings` does not read `"chat_file"`. | `[22.14]` |
| Loading a model empties the screen, as it did in level 3 | The `"loaded"` branch of `poll_results` still calls `new_chat()`. | `[22.12]` |
| A second Load of a large model still fails with "Error: Failed to load model from file" | `load_model` does not call `unload()` on the model it is replacing. | `[22.4]` |
| Open chat... can be clicked while a reply is being written | `set_busy` does not set the new button's state. | `[22.13]` |
| When a chat cannot be saved, for example because the `chats` folder cannot be made, Send stays grey after the reply and the terminal shows the error, such as `FileNotFoundError` | The `try:` in `save_chat` is missing, or its `except` names something other than `OSError`. | `[22.8]` |
| With Llama 3.2, Gemma 3, Mistral 7B or DeepSeek R1, the terminal shows `RuntimeWarning: Detected duplicate leading "<bos>"` (or the model's own start mark) once per reply | `stream` still hands `create_completion` the prompt as text. It must be the list of tokens. | `[19.8]` |
| With the same models, the terminal shows `check_double_bos_eos: Added a BOS token to the prompt...` once per reply | The prompt is tokenized with `add_bos=True`. Only the empty text is. | `[19.8]` |
| `check_my_build.py` fails on "a launcher and its server are both stopped" | `close` still calls `self.process.kill()` where it should call `self.stop_tree()`. | `[21.3]` |
| On Linux, the same test never finishes, and the app hangs on closing when a server will not stop | `Popen` was not given `start_new_session=True`. The server then has no group of its own for `os.killpg` to end, and `close` waits for it for good. | `[21.2]` |
| With Llama 3.2 or Phi-4-mini the status line says `131072 tokens of context`, and with Phi-4-mini the app may vanish, leaving `CUDA error` in the terminal | `__init__` does not hold `size` down to `LARGEST_CONTEXT`: the `min(...)` line is missing. | `[19.7]` |

## How this was checked

- **Automatic tests.** Everything in this level is covered by [`tests/test_level4.py`](tests/test_level4.py): 117 tests, which include all of the earlier levels' tests run against the level 4 answer key. The new ones use real replies that Llama 3.2 wrote, a stand-in for a template that refuses a system message, a stand-in for llama.cpp that records what context each load asked for, and a server that ignores every polite request to stop, started through a launcher the way `npx` starts one. `python check_my_build.py` runs the same tests on your copy.
- **Real models.** The answer key was driven through its real window by [`tests/real_model.py`](tests/real_model.py) with each model below, on Windows 11 with an 11 GB RTX 2080 Ti. The script stops a long reply, saves and reopens a chat, loads the model a second time in the middle of a conversation, uses the calculator and the demo server's tools where the template offers tools, shrinks the context to force a summary, and restarts the app to see the conversation come back. Every model passed every check that does not depend on what the model chooses to say. "Memory" is what the card gave up when the model loaded with a context of 32,768 tokens.

  | Model | File | Tools in its template | Memory | What it did |
  | --- | --- | --- | --- | --- |
  | Qwen3.5 4B | `Qwen3.5-4B-Q8_0.gguf` from `unsloth/Qwen3.5-4B-GGUF`, the file in step 2 | yes | 6.3 GB | Everything asked of it, tools included. |
  | Qwen3.5 0.8B | `Qwen3.5-0.8B-Q8_0.gguf` | yes | 1.7 GB | Used every tool correctly. Could not recall a name from the summarised part of a conversation. |
  | Qwen3.5 2B | `Qwen/Qwen3.5-2B`, PyTorch | yes | not set aside | As the 0.8B. |
  | Llama 3.2 3B | `Llama-3.2-3B-Instruct-Q4_K_M.gguf` from `unsloth/Llama-3.2-3B-Instruct-GGUF` | yes | 7.0 GB | Wrote its calls as bare JSON; all were read and run. Calls tools far more often than it is asked to. |
  | Hermes 3 (Llama 3.2 3B) | `Hermes-3-Llama-3.2-3B.Q4_K_M.gguf` from `NousResearch/Hermes-3-Llama-3.2-3B-GGUF` | no | 7.0 GB | Chatted and summarised well, with no tools. |
  | Phi-4-mini | `Phi-4-mini-instruct-Q4_K_M.gguf` from `unsloth/Phi-4-mini-instruct-GGUF` | no | 7.9 GB | As Hermes 3. Before the context limit, this is the model that stopped the app with "CUDA error". |
  | Gemma 3 4B | `gemma-3-4b-it-Q4_K_M.gguf` from `unsloth/gemma-3-4b-it-GGUF` | no | 7.2 GB | As Hermes 3. Its template puts the system prompt into the first message by itself. |
  | Mistral 7B v0.3 | `Mistral-7B-Instruct-v0.3-Q4_K_M.gguf` from `bartowski/Mistral-7B-Instruct-v0.3-GGUF` | no | 9.1 GB | As Hermes 3, now with a system prompt. With level 3's code every message sent with a system prompt was refused. |
  | DeepSeek R1 1.5B | `DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf` from `unsloth/DeepSeek-R1-Distill-Qwen-1.5B-GGUF` | no | 2.6 GB | Thinks before every answer. Its summaries tend to come out longer than what they replace, and the app then drops them again. |
  | SmolLM2 360M | `HuggingFaceTB/SmolLM2-360M-Instruct`, PyTorch | no | not set aside | Chatted. Its summary did not survive either, and it could not recall a name from early in the conversation. |

  The 4B checks were also run with the different Q8 build of Qwen3.5 4B that levels 1 to 3 were tested with, with the same result. With the four models that used to be sent two start-of-text tokens, llama.cpp printed no warning about it in any run.
- **One thing that was not explained.** In the full pass, the two PyTorch models each ended once with a segmentation fault while their weights were loading, before the app had been asked for anything. Both passed when run again, and nine further loads of the 2B model did not repeat it. The cause was not found.
- **Switching models** was run through the window with the 4B GGUF and the 2B PyTorch model: GGUF, the same GGUF again, PyTorch, GGUF, PyTorch, PyTorch. Every load worked, and each model answered a question about something said to the one before. The card's memory in use went from 7.1 GB with the GGUF model loaded to 4.4 GB with the PyTorch model loaded in its place, so the first had been let go.
- **MCP servers written by other people.** The client was run directly against four official servers: `mcp-server-time` through `uvx`, and `@modelcontextprotocol/server-filesystem`, `server-memory` and `server-everything` through `npx`. All four started, listed their tools (44 between them) and answered calls. The app was then run with the time and filesystem servers and the 4B model: the status line showed 21 tools, the model looked up the time in Tokyo, wrote a file and listed a folder, each after the approval window, and a request for a file outside the server's folder was refused by the server. Nine programs were running behind those two servers. After the window closed, none was left.
- **A server that will not stop** is in the automatic tests on Windows. The same test was run by hand on Linux, under WSL: level 4 ended the launcher and its server, and level 3's `close` left the server running.
- **This document.** Twice, a copy of level 4 was written from this recipe alone, starting from the level 3 answer key and without sight of the level 4 answer key or the tests. The second time was after the last change to the steps. Apart from docstrings and comments its code was identical to the answer key. The places where each writer had to make a choice were then spelled out.
- **Troubleshooting table:** each row was checked by making that mistake in a copy of the answer key and running it. `check_my_build.py` failed on every one of them, apart from the Linux row, where it waits for ever.

## Known rough edges

- **Tools need a template that describes them.** Of the eight model files tried, only Qwen3.5's and Llama 3.2's do. A model family that can call tools may still come in a file whose template says nothing about them: that was the case for the Hermes 3, Mistral 7B and Phi-4-mini files here. The app can only go by the template in the file.
- **Only two ways of writing a call are read:** Qwen's `<tool_call>` mark, and bare JSON at the very start of a reply. A call written after some other text with no mark is shown as text and not run. Other marks, such as Mistral's `[TOOL_CALLS]`, are not handled, because no file tried here used one.
- With tools on, a reply that starts with `{` or `[` is not shown word by word. It appears all at once when it is complete.
- With tools on, an answer that is itself JSON with a `"name"` and `"arguments"` (or `"parameters"`) is taken for a tool call.
- Llama 3.2 3B calls tools eagerly. Asked only to say hello, it called a tool named `hello` that does not exist, and it often calls the same tool again when it already has the answer. `MAX_TOOL_ROUNDS` is what stops it, and the approval window is what stops it writing notes nobody asked for.
- Thinking mode can only be switched on and off for Qwen. DeepSeek R1 always thinks, and a small model that thinks can take minutes over a summary, during which Stop does nothing (see level 3's list).
- Chats are only ever added. There is no way to delete or rename one from the app; use File Explorer. A chat is named by its date and time, not by what it was about.
- A chat file is trusted in the same way as `settings.json`. One that has been edited by hand into the wrong shape may fail later, not when it is opened.
- If the chat that was open last time has been deleted, the app starts with an empty window. The "Could not open the chat" message is written to the status line but replaced at once by "Selected: ..." if a model path was saved, so you do not see it.
- A conversation in which tools were used cannot always be carried on with a model whose template has no place for tools. Gemma 3's template refuses the tool messages already in such a conversation. The reply then fails, and the question is taken back.
- A reply that fails is marked in the log, but the chat file is not rewritten until the next reply that works.
- A load that fails now leaves no model loaded, where levels 1 to 3 kept the old one.
- **The context limit is one number for every card.** With `LARGEST_CONTEXT` at 32,768, the largest load here, Mistral 7B, took 9.1 GB of the card's 11. On a smaller card, or with a larger model, 32,768 tokens can still be too much. On Linux such a load fails and is halved, as step 3.3.1 intends. On Windows with a current NVIDIA driver it succeeds and spills into ordinary memory, as described above. If the status line shows the full 32,768 and Task Manager shows the card's "Shared GPU memory" in use, lower `LARGEST_CONTEXT`. NVIDIA Control Panel also has a setting for this, "CUDA - Sysmem Fallback Policy"; it was not tried here.
- `TransformersBackend` has no limit of this kind. It still takes the model's whole trained context as its size, as level 1's list says.
- `stop_tree`'s branch for Linux and macOS was run on Linux only, under WSL.
- Everything in the earlier levels' lists still applies, except the items this level fixes: conversations are saved, a second model can be loaded without restarting, a message that got no answer does not stay in the conversation, and other people's models and MCP servers have been tried.

## Where to go next

The app you have built is the one in [crussella0129/VoxMux](https://github.com/crussella0129/VoxMux). That repository is this answer key with the teaching text removed, made by [`tools/make_app.py`](tools/make_app.py).

Good next exercises, in rough order of size: say why Send did nothing when no model is loaded; add a way to take back "Always allow" from the window; show the model's thinking in a different colour; give each saved chat a title from its first message; and choose the context size from the graphics card's free memory instead of from one fixed number.
