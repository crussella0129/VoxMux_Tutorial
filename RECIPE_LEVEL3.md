# VoxMux recipe: level 3

Level 3 is the finishing touches. Each one fixes something that level 1 or level 2 listed under "Known rough edges":

- **A Stop button.** A model in thinking mode can write for minutes. Now you can cut it short and keep what arrived.
- **A New chat button.** It clears the conversation without loading the model again. Loading a model now clears the screen too.
- **Saved settings.** The backend, the model path, the temperature, thinking mode and its instructions, the system prompt and the Use tools switch are written to `settings.json` when the window closes, and read back the next time.
- **Tool approval.** A tool that comes from an MCP server is another program, running with your permissions. The app now asks before it runs one: Allow once, Always allow, or Deny.
- **No more waiting for ever.** If the PyTorch model fails in the middle of a reply, the error now reaches the status line. In levels 1 and 2 the app waits indefinitely.

Like the first two levels, this is a description in words, with no finished code. The finished code is in [`answer_key_level3/`](answer_key_level3/).

Start this only after level 2 works. Level 3 changes two of level 2's files and adds none.

## How the tags work in level 3

The steps continue level 2's numbering: steps 14 to 17. Search the level 3 answer key for `[16.7]` to land on the code step 16.7 describes.

As in level 2, a block that level 3 *changes* gets a new tag that names the tag it replaces: `[16.6] (level 2: [12.4])` or `[16.14] (level 1: [4.15])`. The tag in the brackets is the one that block carries in your own file right now. Find the block by that tag, rewrite it as described, and change its tag to the new one followed by the note.

A longer tag can push a docstring's first line or a comment past the edge of your editor. Shorten the wording after the tag, or let a comment run onto one more line. The same goes for a line of code that grows too long once it is indented further: break it inside its brackets. Only the tag has to match the answer key.

Wherever a step says "a short comment after it", that means on the same line, after the code. Wherever a step says "set the status text", that is the call from step 4.5: `.config` on `self.status` with `text` set to the message.

| Steps | File | What happens |
| --- | --- | --- |
| 14 | | Set up: copy your level 2 folder. |
| 15 | `backends.py` | Changed: the PyTorch backend stops writing when nobody is listening, and passes a failure on. |
| 16 | `app.py` | Changed: Stop, New chat, saved settings, and asking before an MCP tool runs. |
| 17 | | Run it. |

`tools.py`, `mcp_client.py`, `demo_mcp_server.py`, `mcp_servers.json` and `install.py` stay exactly as they are.

## How stopping works

A reply reaches the window through a chain of generators: `stream_reply` loops over `chat`, which hands on what `stream` yields. A generator only runs while someone asks it for its next piece. So the way to stop a reply is to **stop asking**, and then end the generator by calling its `close()` method.

What happens next depends on the backend:

- **llama.cpp** works out one more token each time it is asked for one. Once nobody asks, it does no more work. Level 1's `LlamaCppBackend.stream` needs no change.
- **PyTorch** is different. `generate()` runs on its own thread and writes the whole reply into the streamer whether or not anyone reads it. Left alone, it would keep the graphics card busy for up to `MAX_NEW_TOKENS` tokens after you clicked Stop. So `TransformersBackend.stream` has to notice that it was closed and tell `generate()` to stop. Step 15 does that.

The window's side is a flag. The Stop button raises it. The worker thread reads it before it uses each piece, and leaves its loop when the flag is up. A thread cannot be stopped from outside in Python; it has to check and stop itself.

Stop takes effect at the next piece of text. While the model is still reading a long prompt, summarising, or waiting for a tool, there is no piece yet, so the click is acted on as soon as the first one arrives.

## How a worker thread asks you a question

The tool loop runs on the worker thread. Asking "may this tool run?" means showing a window, and only the main thread may touch the window. Level 1's queue already carries results from the worker to the main thread. Level 3 adds a second queue going the other way:

1. The worker puts an `"ask"` result in `self.results`, then calls `get()` on the new queue, `self.answers`. `get()` on an empty queue waits until something is put in it, so the worker thread sleeps there.
2. `poll_results`, on the main thread, sees the `"ask"` and opens a small window with three buttons.
3. Clicking a button puts the answer in `self.answers`. That wakes the worker, which runs the tool or tells the model it was refused.

The main thread never waits on a queue. If it did, the window would freeze.

## Python syntax you will meet

- **`threading.Event`** is a flag that is safe to share between threads. `event.set()` raises it, `event.clear()` lowers it, and `event.is_set()` gives `True` or `False`.
- **A function inside a function.** A `def` written inside another function's body makes a function that exists only there. It can read the outer function's variables, even after it has been handed to something else to call later. Level 1's `lambda` is the one-line form of the same idea.
- **`**extra` in a parameter list** means "collect any further keyword arguments into a dictionary named `extra`". It is the keyword version of `*args` from step 4.10. A function that must accept arguments it does not care about uses it to swallow them.
- **`try:` with `finally:`.** The `finally:` block runs when the `try:` block is left, however it is left: by finishing, by an error, by `return`, or by a generator being closed while it waits at a `yield`.
- **`generator.close()`** ends a generator early. Python raises a `GeneratorExit` error inside it at the `yield` where it was waiting, which runs any `finally:` blocks on the way out. Closing a generator that has already finished does nothing.
- **`thread.join()`** waits until that thread has finished.
- **`pass`** is a statement that does nothing. It is for a block that has to be there but has nothing to do.
- **`dictionary[key]` on a missing key** raises `KeyError`. Level 2 used `.get()` to avoid that; here the error is wanted, and caught.

## Step 14: set up

1. Copy your working level 2 folder to a new folder next to it named `my_build_level3`. In PowerShell:

   ```bash
   Copy-Item -Recurse my_build_level2 my_build_level3
   ```

2. Move into `my_build_level3`. Every change below is made there. There is nothing new to install.

## Step 15: `backends.py`, changed

### 15.1 Top of the file

*Answer key: `[3.1]` (module docstring, extended).*

In the module docstring, change "(Level 2 version.)" to "(Level 3 version.)". After the paragraph on what level 2 adds, add one saying what level 3 changes here: one method, `TransformersBackend.stream`. A reply can be cut short by whoever is looping over `chat`, simply by stopping and closing the generator, and the PyTorch backend then tells its model to stop writing. A failure in the middle of a PyTorch reply is passed on, where it used to leave the app waiting. Change the last sentence to say the numbers match RECIPE.md (3.x), RECIPE_LEVEL2.md (7.x) and RECIPE_LEVEL3.md (15.x).

### 15.2 Change `TransformersBackend.stream`

*Answer key: `[15.2] (level 1: [3.4.4])`.*

This is the method with the four stages. Stages 1 and 2 stay as they are. Stage 3 gains two small functions written inside the method, and stage 4 gains a `finally:`.

**Docstring:** re-tag it. Keep the four stages, and add a paragraph on the two safety nets. `should_stop` is handed to `generate()`, which calls it after every token and stops writing once it returns `True`. It returns the state of `stop`, a flag that the `finally:` block sets when the loop in stage 4 ends for any reason, including the caller closing this generator early. `run` wraps `generate()`: if it fails, the error is kept and the streamer is told the reply is over, so the loop in stage 4 ends and the error can be raised on the thread that is listening.

1. Change the import at the top of the method so that it brings in two names from `transformers` on one line: `StoppingCriteriaList` and `TextIteratorStreamer`.
2. **Stage 3.** Under the stage's comment and before the line that creates `settings`, add two variables, each with a short comment after it:
   - `stop`, set to a new `threading.Event()`. It is raised when nobody is listening any more.
   - `failures`, an empty list. It will hold the error if `generate()` fails. A list is used because the function in item 6 can add to a list it did not create.
3. Leave a blank line, then define a function **inside the method**, indented like the lines around it: `should_stop`, with three parameters, `input_ids`, `scores` and `**extra`. Its body is one line: return `stop.is_set()`. `generate()` calls each stopping check with the tokens so far and their scores, and sometimes more keyword arguments. This check ignores all of them and only reports the flag. It is two lines long and needs no docstring. Leave a blank line after it.
4. After the line that sets `settings["streamer"]`, add one more: set `settings["stopping_criteria"]` to `StoppingCriteriaList(...)` called with a list holding `should_stop` (no parentheses after the name: you are handing the function over).
5. The `if temperature > 0:` block stays as it is.
6. After it, leave a blank line and define a second function inside the method: `run`, with no parameters. Its body is a `try:` holding one line, a call to `self.model.generate` with `**settings`, which unpacks the dictionary into keyword arguments. Then `except Exception as error:` with two lines: append `error` to `failures`, and call `streamer.end()`. `end()` is what `generate()` itself calls when it finishes normally; it makes the loop in stage 4 stop. Without it, a failed `generate()` would leave that loop waiting for words that never come. This function needs no docstring either. Leave a blank line after it.
7. Change the thread. Its `target` is now `run`, and the `kwargs` argument is gone, because `run` passes the settings itself. `daemon=True` stays, and the whole call now fits on one line. `thread.start()` stays.
8. **Stage 4.** Extend the stage's comment to say that `finally` runs however the loop ends, so `generate()` is always told to stop and given time to do so before anything else uses the model. Then put the existing `for` loop inside a `try:` block (indent it one level), and after it add `finally:` with two lines: `stop.set()`, then `thread.join()`.
9. After the `finally:` block, back at the `try`'s own indentation: `if failures:` then `raise failures[0]`. This line is only reached when the loop ended by itself. If the caller closed the generator, the method ends in the `finally:` block.

`LlamaCppBackend.stream` is not changed. "How stopping works" above says why.

### 15.3 Checkpoint: test it without a window

From inside `my_build_level3/`, start the Python prompt and load the PyTorch model as in step 3.6. Then:

1. Make the conversation list as in step 3.6, with a question that needs a long answer, such as asking for a 300 word story.
2. Call `.chat` on your backend with the list, an empty string, `0.7` and `False`, and store what comes back in a variable. Nothing runs yet.
3. Write a `for` loop over `enumerate(...)` of that variable, with two loop variables, a number and a piece. Print the piece as in step 3.6. `if` the number reaches `20`, `break`.
4. After the loop, call `.close()` on the variable.

The prompt should come back straight after the twentieth piece. In Task Manager's Performance tab, the graphics card's load should fall back to idle at that moment. With level 2's `stream`, it would stay busy until the whole story had been written into a streamer nobody was reading.

## Step 16: `app.py`, changed

### 16.1 Top of the file

*Answer key: `[4.1]` (docstring, extended) and `[16.1]` (new constants).*

1. In the module docstring: change "(Level 2 version.)" to "(Level 3 version.)", and after the paragraph on level 2 add one on what level 3 adds: a Stop button that cuts a reply short, a New chat button, settings saved in `settings.json` when the window closes and read back the next time, and MCP tools that only run after the user has allowed them. Change the last sentence to name RECIPE_LEVEL3.md (16.x) as well.
2. Add `import json` as the first import, above `import pathlib`.
3. Under the level 2 constants, leave a blank line, then a two-line comment starting with `[16.1]` that says these are where the settings are kept between runs, and what the model is told when the user refuses a tool. Then two constants:
   - `SETTINGS_FILE`, set to `pathlib.Path(__file__).with_name("settings.json")`, the same way `MCP_CONFIG` is made.
   - `DENIED`, set to the string `"Error: the user did not allow this tool call."`. This is what the model is told in place of a result. It starts with `Error:` like every other tool failure, so the model treats it as one.

### 16.2 Change `__init__`

*Answer key: `[16.2] (level 2: [12.2])`.*

1. After `self.toolbox = None`, add three attributes, each with a short comment after it:
   - `self.stop_requested`, set to a new `threading.Event()`. The Stop button raises it.
   - `self.answers`, set to a new `queue.Queue()`. It carries the user's answers about tools to the worker.
   - `self.allowed_tools`, an empty list. It holds the names of the MCP tools the user chose "Always allow" for.
2. Between `self.build_widgets()` and `self.poll_results()`, add a call to `self.load_settings()`. It must come after `build_widgets`, because most settings are written into widgets, and those have to exist first.
3. Re-tag the docstring and add both points: `close()` now saves the settings as well as stopping the servers, and the saved settings are read back after the widgets are built.

Also update the class docstring (it keeps its tag, `[4.2]`). The small helpers are now `start_worker`, `stream_reply`, `may_run`, `append_chat`, `set_busy`, `load_settings`, `save_settings` and `close`. The button handlers gain `new_chat`, `stop` and `answer_tool`. `open_approval_window` belongs with `poll_results`: it is the one result that needs a window of its own, so add that to the sentence about `poll_results`.

### 16.3 Change the top row

*Answer key: `[16.3] (level 1: [4.4.1])`.*

At the end of the top row block in `build_widgets`, after the Load button is packed:

1. Create a `tk.Button` with parent `top`, `text` set to `"New chat"`, and `command` set to `self.new_chat`. Store it as `self.new_chat_button`.
2. Pack it with `side` set to `"right"`, which puts it at the far end of the row, away from the model controls.

Change the block's comment: re-tag it and add "or start a new chat".

### 16.4 Change the bottom row

*Answer key: `[16.4] (level 1: [4.4.5])`.*

At the end of the bottom row block, after the Send button is packed:

1. Create a `tk.Button` with parent `bottom` and three keyword arguments: `text` set to `"Stop"`, `command` set to `self.stop`, and `state` set to `"disabled"`. It starts greyed out because there is nothing to stop yet. Store it as `self.stop_button`.
2. Pack it with `side` set to `"left"` and `padx` set to `(8, 0)`, like the Send button.

Change the block's comment: re-tag it and add "or stop the reply".

### 16.5 New method `new_chat`

*Answer key: `[16.5]`.*

Parameters: just `self`. Put it after `load_model` and before `send`.

**Docstring:** start with `[16.5]`. Say that the model only knows what is in `self.messages`, so an empty list is a fresh start; that the log is read-only, so it is unlocked, emptied and locked again; and that the button is greyed out while a worker is running, so this never pulls the conversation out from under a reply.

1. Set `self.messages` to an empty list.
2. Call `.config` on `self.chat_log` with `state` set to `"normal"`.
3. Call `.delete` on `self.chat_log` with `"1.0"` and `"end"`: everything from the first character to the end.
4. Call `.config` again with `state` set to `"disabled"`.

### 16.6 Change `send`

*Answer key: `[16.6] (level 2: [12.4])`.*

Straight after the call to `self.set_busy(True)`, add two lines:

1. Call `.clear()` on `self.stop_requested`. The flag may still be up from the last reply; without this line, every reply after the first Stop would be stopped at once.
2. Call `.config` on `self.stop_button` with `state` set to `"normal"`.

Re-tag the docstring and add that the stop flag is lowered and the Stop button brought to life for this reply.

### 16.7 New method `stop`

*Answer key: `[16.7]`.*

Parameters: just `self`. Put it after `send`.

**Docstring:** start with `[16.7]`. Say that a worker thread cannot be stopped from outside and has to stop itself, so this only raises a flag; what a `threading.Event` is; that `stream_reply` reads the flag before it uses each piece; and that the button greys itself out so it cannot be clicked twice.

1. Call `.set()` on `self.stop_requested`.
2. Call `.config` on `self.stop_button` with `state` set to `"disabled"`.
3. Set the status text to `"Stopping..."`.

### 16.8 Change `reply_worker`

*Answer key: `[16.8] (level 2: [12.6])`.*

Two changes inside the `for` loop.

1. **A stopped reply ends the work.** After the line that sets `text, calls`, add a line that stores `self.stop_requested.is_set()` as `stopped`. Then change the `if` under it so that it has three conditions joined by `or`, with the new one first: `stopped`, `not calls`, `not use_tools`. Inside that `if`, before the existing `put`, add: `if stopped:` put `("piece", " [stopped]")` in the queue. The string starts with a space, so the mark is set off from the last word. Put those two lines under the comment that is already inside the `if`, and reword that comment to mention the stopped reply. A stopped reply is handled like a plain answer: the text that arrived is kept, and a tool call in it is not run.
2. **Ask before running.** In the inner loop that runs each call, the two lines that put the "Running tool" status in the queue and set `result` to `self.toolbox.run(...)` move into an `if`: `if self.may_run(call):` then those two lines, indented one more level. Add an `else:` that sets `result` to `DENIED`. The lines after it, which show the result and add the `"tool"` message, stay as they are. They now run for a refused call too, so the refusal appears in the log and reaches the model.

Re-tag the docstring and add both: a reply the user stopped ends the work the way a plain answer does, with what had arrived kept and marked `[stopped]`; and a tool the user refuses is not run, with the model told so in place of a result.

### 16.9 Change `stream_reply`

*Answer key: `[16.9] (level 2: [12.7])`.*

The `for` loop used to loop directly over the call to `self.backend.chat(...)`. To close a generator you need a name for it.

1. Before the loop, store the result of that same call to `self.backend.chat`, with the same five arguments, in a variable named `pieces`.
2. Change the loop to `for piece in pieces:`.
3. Make the first thing inside the loop a check: `if self.stop_requested.is_set():` then `break`. The rest of the loop body stays as it is, below the check.
4. After the loop and before the `return`, call `pieces.close()`. If the loop ran to its end, this does nothing. If it was left with `break`, this ends the generator, which is what tells the PyTorch backend that nobody is listening. Python would end the generator by itself once nothing refers to it any more, which here is when the method returns. Calling `close()` does it on a line you can see, and does not depend on when Python tidies up.

Re-tag the docstring and add what the last three items do: the flag is read before each piece is used, and `close()` ends the generator if the loop was left early, which tells the backend that nobody is listening.

### 16.10 New method `may_run`

*Answer key: `[16.10]`.*

Parameters: `self` and `call`. Put it after `stream_reply`. It runs on the worker thread and returns `True` or `False`.

**Docstring:** start with `[16.10]`. Say that a built-in tool is a function in `tools.py` that you can read, so it always runs, while a tool from an MCP server is another program, so the user is asked first unless they already chose "Always allow". Explain the two queues as in "How a worker thread asks you a question". Add that a tool nobody owns is let through, because `Toolbox.run` answers that with an error the model can read.

1. Store `call["name"]` as `name`.
2. Look up who owns the tool: `self.toolbox.owners.get(name)`, stored as `owner`. `.get` gives `None` for a name that is not there.
3. An `if` with three conditions joined by `or`: `owner is None`, `callable(owner)`, and `name in self.allowed_tools`. Inside it, `return True`. A built-in tool's owner is a function, which is callable; an MCP tool's owner is a server object, which is not.
4. Put `("status", ...)` in `self.results`, with an f-string reading `Waiting for your answer about `, `name` in braces, `...`.
5. Put `("ask", call)` in `self.results`.
6. `return` whether `self.answers.get()` is not equal to (`!=`) `"deny"`. This is the line where the worker waits.

### 16.11 Change `poll_results`

*Answer key: `[16.11] (level 2: [12.8])`.*

1. Add a branch after `"status"`: `elif kind == "ask":` call `self.open_approval_window` with `value`. Like a piece or a status, it leaves the buttons alone, because the work is not over.
2. In the `"loaded"` branch, replace the line that sets `self.messages` to an empty list with a call to `self.new_chat()`. That empties the list and the log, so the screen no longer shows a conversation the new model knows nothing about. Keep the comment at the end of that line.
3. Re-tag the docstring and add both.

### 16.12 New method `open_approval_window`

*Answer key: `[16.12]`.*

Parameters: `self` and `call`. Put it after `poll_results` and before `append_chat`. It runs on the main thread.

**Docstring:** start with `[16.12]`. Say that a small window shows the tool's name and arguments above three buttons, that each button's command is a `lambda` because it must hand `answer_tool` the window, the tool's name and its own answer, and that closing the window with its X button counts as Deny, because otherwise the worker would wait for an answer for ever.

1. Store `call["name"]` as `name`.
2. Create a `tk.Toplevel` with parent `self.root`, stored as `window`, and call `title` on it with `"Allow this tool?"`.
3. Call `window.protocol` with two arguments: `"WM_DELETE_WINDOW"`, and a `lambda` with no parameters that calls `self.answer_tool` with `window`, `name` and `"deny"`. This is the same call `__init__` makes on the main window in step 12.2. It is too long for one line, so put the two arguments on a line of their own inside the parentheses.
4. Leave a blank line. Create a `tk.Label` with parent `window` and three keyword arguments, one per line: `text` set to an f-string reading `The model wants to run `, `name` in braces, ` with:`, a newline escape, then `call['arguments']` in braces; `justify` set to `"left"`; and `wraplength` set to `420`, which wraps long arguments at 420 pixels. Chain `.pack` with `padx` and `pady` both `8`.
5. Leave a blank line. Create a `tk.Frame` with parent `window`, stored as `buttons`, and pack it with `padx` set to `8` and `pady` set to `(0, 8)`.
6. Three `tk.Button`s with parent `buttons`, each with `text` and `command` on their own lines, and each `command` a `lambda` with no parameters that calls `self.answer_tool` with `window`, `name` and an answer string:
   - `"Allow once"`, answering `"once"`. Chain `.pack` with `side` set to `"left"`.
   - `"Always allow"`, answering `"always"`. Chain `.pack` with `side` set to `"left"` and `padx` set to `8`.
   - `"Deny"`, answering `"deny"`. Chain `.pack` with `side` set to `"left"`.

### 16.13 New method `answer_tool`

*Answer key: `[16.13]`.*

Parameters: `self`, `window`, `name` and `answer`. Put it after `open_approval_window`.

**Docstring:** start with `[16.13]`. Say that `answer` is `"once"`, `"always"` or `"deny"`, that "Always allow" adds the tool's name to `self.allowed_tools`, which is saved with the settings, and that putting the answer in `self.answers` is what wakes the worker waiting in `may_run`.

1. `if answer == "always":` append `name` to `self.allowed_tools`.
2. Put `answer` in `self.answers`.
3. Call `.destroy()` on `window`.

### 16.14 Change `set_busy`

*Answer key: `[16.14] (level 1: [4.15])`.*

After the two lines that set the state of the Load and Send buttons, add:

1. The same `.config` call on `self.new_chat_button`.
2. `if not busy:` call `.config` on `self.stop_button` with `state` set to `"disabled"`.

Stop is the odd one out. It is only useful while a reply is being written, not while a model loads, so `send` brings it to life and this method only ever greys it out. Re-tag the docstring, change its first line to say it greys out the buttons while work is running, and add that explanation.

### 16.15 New method `load_settings`

*Answer key: `[16.15]`.*

Parameters: just `self`. Put it after `set_busy`.

**Docstring:** start with `[16.15]`. Say that the file holds one JSON object written by `save_settings`, and that each value goes back where it came from: into a tkinter variable with `set()`, into the system prompt box with `insert()`, or onto `self`. Add that the first run has no file, and that a file which cannot be read, is not JSON, or is missing a key is not worth crashing over: the settings read before the problem are kept and the rest stay at their starting values.

1. `if not SETTINGS_FILE.exists():` then a bare `return`.
2. A `try:` block. Inside it, nine lines:
   - Set `saved` to `json.loads(...)` of `SETTINGS_FILE.read_text(encoding="utf-8")`.
   - Call `.set` on `self.backend_kind` with `saved["backend_kind"]`.
   - Set `self.model_path` to `saved["model_path"]`.
   - Call `.set` on `self.temperature` with `saved["temperature"]`.
   - Call `.set` on `self.thinking` with `saved["thinking"]`.
   - Set `self.thinking_instructions` to `saved["thinking_instructions"]`.
   - Call `.set` on `self.use_tools` with `saved["use_tools"]`.
   - Call `.insert` on `self.system_box` with `"1.0"` and `saved["system_prompt"]`.
   - Set `self.allowed_tools` to `saved["allowed_tools"]`.
3. `except (OSError, ValueError, KeyError, TypeError):` then `pass`. `OSError` is a file that cannot be read, `ValueError` is text that is not JSON, `KeyError` is a missing key, and `TypeError` is JSON that is not an object, such as a list.
4. After the `try`, at the method's own indentation: `if self.model_path:` set the status text to an f-string reading `Selected: ` and `self.model_path` in braces, the same message `browse` shows. The saved model is not loaded for you; that still takes a click on Load.

### 16.16 New method `save_settings`

*Answer key: `[16.16]`.*

Parameters: just `self`. Put it after `load_settings`.

**Docstring:** start with `[16.16]`. Say that every setting is gathered into one dictionary with the same keys `load_settings` reads, that `json.dumps` turns it into text, and that `indent=2` spreads it over several lines so a person can read it.

1. Create a dictionary named `saved`, one key per line, with a trailing comma after the last:
   - `"backend_kind"`: `self.backend_kind.get()`
   - `"model_path"`: `self.model_path`
   - `"temperature"`: `self.temperature.get()`
   - `"thinking"`: `self.thinking.get()`
   - `"thinking_instructions"`: `self.thinking_instructions`
   - `"use_tools"`: `self.use_tools.get()`
   - `"system_prompt"`: `self.system_box.get("1.0", "end").strip()`
   - `"allowed_tools"`: `self.allowed_tools`
2. Call `SETTINGS_FILE.write_text` with `json.dumps(saved, indent=2)` and the keyword argument `encoding` set to `"utf-8"`.

The key strings must be spelled exactly as in `load_settings`. A key that is saved under one name and read under another makes `load_settings` stop at that line.

### 16.17 Change `close`

*Answer key: `[16.17] (level 2: [12.9])`.*

At the top of the method, before the servers are stopped, add:

1. A `try:` block with one line, a call to `self.save_settings()`.
2. `except OSError:` then `pass`.

The docstring was one line. Re-tag it, change that line to say the window is closed by saving, stopping the servers, then closing, and add a "How it works" paragraph under it on why the error is swallowed: if the file cannot be written, for example because the folder is read-only, losing the settings is better than a window that will not close.

## Step 17: run it

First, without a model. From the repo root:

```bash
python check_my_build.py my_build_level3
```

This opens your window with a scripted stand-in for the model and clicks through everything in this level in under a minute. It works out that the folder holds level 3 from the `new_chat` method in your `app.py`. Each line it prints ends with the steps it checks. Fix anything that fails before you go on.

Then, from inside `my_build_level3`, with a real model:

```bash
python app.py
```

Load the 4B model and check:

1. **Stop.** The Stop button is grey. Ask for a 300 word story. Stop turns live as the reply starts. Click it part-way through: the status shows "Stopping...", the reply ends with `[stopped]`, and Send comes back. Ask "What was the story about?" The model answers from the part it wrote.
2. **Stop, PyTorch.** Do the same with the 2B PyTorch model. The reply must stop just as quickly, and the next reply must start without a long pause.
3. **New chat.** Tell the model your name, click New chat, and ask what your name is. The log is empty after the click, and the model does not know.
4. **Loading clears the screen.** Chat, then click Load again. The old conversation disappears when the model is ready.
5. **Approval, deny.** Ask "Save a note that says: buy oat milk." A window titled "Allow this tool?" shows `save_note` and its arguments, and the status line says "Waiting for your answer about save_note...". Click Deny. The log shows the call with `-> Error: the user did not allow this tool call.`, the model says it could not save the note, and no `notes.json` appears.
6. **Approval, allow.** Ask again and click Allow once. The note is saved. Ask for another note: the window appears again. This time click Always allow. A third request saves the note without asking.
7. **Built-in tools do not ask.** "What is 1234 * 5678? Use the calculator." runs straight away.
8. **Settings.** Set the temperature to 1.2, tick Thinking mode, type a system prompt, and close the window. A file named `settings.json` appears in the folder; open it and read it. Start the app again. Everything is as you left it, the status line says `Selected:` with your model's path, and Load works without Browse. `save_note` is still always allowed.
9. **A broken settings file.** Close the app, open `settings.json`, delete its last line (the closing brace), and save. The app must still start, with its usual starting values. Close it again and the file is rewritten whole.

## When it does not work

| What you see | Likely cause | Look at |
| --- | --- | --- |
| `AttributeError: 'ChatApp' object has no attribute 'backend_kind'` as the app starts | `load_settings()` is called before `build_widgets()`. This only shows once a `settings.json` exists. | `[16.2]` |
| No settings come back, or only the first few | None: `load_settings()` is not called in `__init__`. Some: a key is spelled differently in `load_settings` and `save_settings`, so reading stops at that line and everything after it keeps its starting value. | `[16.2]`, `[16.15]`, `[16.16]` |
| The window will not close, and the terminal shows `TypeError: Object of type DoubleVar is not JSON serializable` (or `BooleanVar`, or `StringVar`) | A tkinter variable was put in the dictionary without `.get()`, such as `self.temperature` on its own. | `[16.16]` |
| Stop stays grey while a reply is being written | `send` does not set the Stop button's state to `"normal"`. | `[16.6]` |
| Stop stays live after the reply has finished | `set_busy` does not grey it out when `busy` is false. | `[16.14]` |
| Clicking Stop shows "Stopping..." but the reply carries on to its end, and only then gets its `[stopped]` mark | `stream_reply` does not check the flag inside its loop. | `[16.9]` |
| After one Stop, every later reply is empty apart from `[stopped]` | `send` does not lower the flag with `clear()`. | `[16.6]` |
| Stop works, but a tool call in the stopped reply still runs | `stopped` is missing from the `if` in `reply_worker`. | `[16.8]` |
| PyTorch only: after Stop, the graphics card stays busy and the next reply is slow to start | `stream` does not tell `generate()` to stop: the `stopping_criteria` line, or `stop.set()` in the `finally:` block, is missing. | `[15.2]` |
| The status stays on "Waiting for your answer about ..." and no window opens | `poll_results` has no `"ask"` branch, so the question is taken out of the queue and dropped. | `[16.11]` |
| No approval window appears, the status stays on "Waiting for your answer about ..." for good, and the terminal shows `TclError: bad window path name` | A button's `command` calls `self.answer_tool(...)` directly instead of inside a `lambda`. That answers the question and closes the window while it is still being built, and the error stops `poll_results` from running again. The tool may have run. | `[16.12]` |
| An MCP tool runs without any question | Its name is already in `"allowed_tools"` in `settings.json`, because you clicked Always allow in an earlier run. If not, `may_run` returns `True` too early: check the three conditions in its `if`. | `[16.10]` |
| The calculator asks for permission | `callable(owner)` is missing from the `if` in `may_run`. | `[16.10]` |
| New chat clears the screen, but the model still remembers | `new_chat` does not set `self.messages` to an empty list. | `[16.5]` |
| New chat leaves the old messages on screen, though the model has forgotten them | The log was not unlocked with `state="normal"` before `.delete`. A read-only log ignores the delete without any error. | `[16.5]` |

## How this was checked

- **Automatic tests.** Everything in this level is covered by [`tests/test_level3.py`](tests/test_level3.py), which drives the real window with a scripted stand-in for the model. It also runs all of level 1's and level 2's tests against the level 3 answer key, to check that nothing earlier broke. `python check_my_build.py` runs the same tests on your copy.
- **The PyTorch changes** were tested on a tiny random model that ships with the tests. Closing the generator early made `generate()` return after a few tokens, and a failure inside `generate()` was raised to the caller. The same failure with level 2's `stream` left the caller waiting until the test gave up.
- **Real models.** The answer key was driven through its real window by [`tests/real_model.py`](tests/real_model.py) with the 0.8B GGUF, a Q8 build of the 4B GGUF and the 2B PyTorch model: stopping a long reply, a whole reply straight afterwards, New chat, the calculator, an MCP tool denied, allowed, and always allowed, tools off, compaction, and the settings file. All three passed every check that does not depend on what the model chooses to say. With PyTorch, the reply after a stopped one started in under a second.
- **This document.** A copy of level 3 was written from this recipe alone, starting from the level 2 answer key and without sight of the level 3 answer key or the tests. It passed all the automatic tests on its first run, and apart from docstrings and comments its code was identical to the answer key. The places where that writer had to make a choice were then spelled out.
- **Troubleshooting table:** each row was checked by making that mistake in a copy of the answer key and running it.

## Known rough edges

- Stop is acted on when the next piece of text arrives. While the model is reading a long prompt, summarising old messages, or waiting for a tool, nothing happens until then.
- A stopped reply stays in the conversation as far as it got. If you stop the model while it is still thinking, that unfinished thinking is what is kept.
- Conversations are not saved. Closing the window or clicking New chat forgets them.
- Settings are saved only when the window is closed normally. If the app crashes, changes made since it started are lost.
- "Always allow" remembers a tool by its name alone. Any server that offers a tool of that name is trusted, with any arguments. To take a permission back, close the app and remove the name from `"allowed_tools"` in `settings.json`.
- `settings.json` is trusted to hold the right kinds of value. If you edit it by hand and put text where a number belongs, the app may fail later. Delete the file to start again.
- The saved model path is selected but not loaded. Loading still takes a click.
- Everything in the earlier levels' lists still applies, except the items this level fixes: there is now a way to start a new chat, loading a model clears the screen, and a PyTorch failure in the middle of a reply shows an error.

## Where to go next

The app you have built is the one in [crussella0129/VoxMux](https://github.com/crussella0129/VoxMux). That repository is this answer key with the teaching text removed, made by [`tools/make_app.py`](tools/make_app.py).

Good next exercises, in rough order of size: say why Send did nothing when no model is loaded; save the conversation as well as the settings; add a way to take back "Always allow" from the window; show the model's thinking in a different colour; and read tool calls written by a model family other than Qwen.
