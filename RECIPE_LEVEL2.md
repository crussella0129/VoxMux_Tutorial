# VoxMux recipe: level 2

Level 2 turns your finished level 1 app into one that can **use tools** and **remember long conversations**:

- **Compaction.** When a conversation outgrows the context, level 1 forgets the oldest messages. Level 2 asks the model to summarise them instead, so the facts survive.
- **Tool calling.** The model can ask the app to run a Python function, such as an exact calculator, read the result, and then answer.
- **MCP.** The Model Context Protocol lets separate programs offer tools to any chat app that speaks it. You will write a small MCP *client* into VoxMux, and a small MCP *server* to test it with.

Like level 1, this is a description in words, with no finished code. The finished code is in [`answer_key_level2/`](answer_key_level2/).

Start this only after level 1 works. Level 2 changes level 1's files, so it assumes you know them.

## How the tags work in level 2

The steps here continue level 1's numbering: steps 7 to 12. Tags work the same way: search the level 2 answer key for `[8.6]` to land on the code step 8.6 describes.

Most of `answer_key_level2/backends.py` and `answer_key_level2/app.py` is level 1 code, unchanged, with its level 1 tags. A block that level 2 *changes* gets a new tag and names the tag it replaces, such as `[7.5] (level 1: [3.2.2])`. When a step here says "change", find the block by its level 1 tag in your own file and rewrite it as described, then change its tag (in the docstring, or in the comment for a block such as the settings row) to the new one followed by `(level 1: [...])`.

| Steps | File | What happens |
| --- | --- | --- |
| 7 | `backends.py` | Changed: tools are passed through to the chat template, and compaction comes before forgetting. |
| 8 | `tools.py` | New: built-in tools, reading tool calls out of a reply, and a toolbox that runs any tool. |
| 9 | `mcp_client.py` | New: starts MCP servers and talks to them. |
| 10 | `demo_mcp_server.py` | New: a small MCP server with three tools, to test the client with. |
| 11 | `mcp_servers.json` | New: the list of MCP servers to start. |
| 12 | `app.py` | Changed: a Use tools switch, the tool-calling loop, and starting and stopping servers. |

## How tool calling works

The model never runs anything itself. It only writes text. Tool calling is an agreement about what that text looks like:

1. The app tells the model which tools exist. Each tool is described as a small piece of JSON, called a **schema**: its name, what it is for, and what arguments it takes. The chat template writes these into the prompt, along with instructions for asking to use one.
2. When the model wants a tool, it writes a **tool call** instead of an answer. Your Qwen3.5 models write it like this, inside `<tool_call>` and `</tool_call>` markers: a `<function=calculate>` line, then one `<parameter=expression>` block per argument. Other model families write JSON between the same markers.
3. The app reads the call out of the reply, runs the tool, and adds two messages to the conversation: the model's turn (with the call attached as `tool_calls`), then a message with the role `"tool"` holding the result.
4. The app asks the model again. Now it can see the result, and usually answers in plain text. If it asks for another tool, the loop goes round again, up to a limit.

## How MCP works

An MCP server is just a program. The client starts it and they talk over the server's standard input and output (the same pipes `input()` and `print()` use), one line of JSON per message, in a format called **JSON-RPC 2.0**:

- A **request** has a `"method"` (what to do), `"params"`, and an `"id"` number. The other side must send back a **response** with the same `"id"`, holding either a `"result"` or an `"error"`.
- A **notification** has a `"method"` but no `"id"`, and gets no answer.

Every conversation opens the same way. The client sends the request `initialize`, then the notification `notifications/initialized`, then the request `tools/list` to learn the server's tools. After that, `tools/call` runs one. Either side may also send requests of its own, such as `ping`.

## Python syntax you will meet

- **Decorators.** Writing `@tool` on the line above `def calculate(...)` is short for writing `calculate = tool(calculate)` after it. A decorator is a function that receives a function, and here it records it in a dictionary.
- **Type hints.** `def calculate(expression: str) -> str:` notes that `expression` should be a string and the function returns one. Python does not enforce them, but code can read them with the `inspect` module. That is how a tool's schema gets written for you.
- **Recursion.** A function that calls itself, on a smaller piece of the problem each time.
- **`isinstance(value, SomeType)`** asks whether a value is of a type. `type(value)` gives the exact type.
- **Regular expressions** (the `re` module) describe text patterns. `(.*?)` captures as little text as possible, `[^>\s]+` means one or more characters that are not `>` or a space, and `re.DOTALL` lets `.` match newlines too. `findall` returns every match.
- **JSON.** `json.dumps(data)` turns Python dictionaries and lists into JSON text; `json.loads(text)` turns it back.
- **Slice assignment.** `items[:3] = [a, b]` replaces the first three items with two new ones, shrinking the list in place.
- **`continue`** skips the rest of a loop's block and goes round again.
- **`callable(thing)`** is `True` if `thing` can be called like a function.
- **`subprocess.Popen`** starts another program. With `stdin=subprocess.PIPE` and `stdout=subprocess.PIPE`, your program can write to it and read from it.
- **`pathlib.Path`** is a file path as an object: `path.parent` is its folder, `path.exists()` says whether it is there, `path / "name"` adds to it, and `Path(__file__)` is the file the code is in.

## Step 6: set up

1. Copy your whole working level 1 folder, `my_build`, to a new folder next to it named `my_build_level2`. In PowerShell:

   ```bash
   Copy-Item -Recurse my_build my_build_level2
   ```

2. Move into `my_build_level2`. Every change below is made there, so your level 1 copy stays as it is.
3. Level 2 needs one more small package, `tzdata`. Windows has no time zone database of its own, and the demo server's time tool (step 10.3) needs one. Open `install.py` and add a fourth list to the end of `STEPS`, holding just the string `"tzdata"`. Put a comment above it starting with `[6.1]` that says why it is there. Then run the script again:

   ```bash
   python install.py
   ```

   The first three libraries print "Requirement already satisfied", `tzdata` installs, and the check passes as before. Everything else in level 2 uses only Python's own modules.
4. Use the 4B model from step 1.4, `Qwen3.5-4B-Q8_0.gguf`, for most of your testing. The 0.8B and 2B models can call tools too, but they also call them when they should not.

## Step 7: `backends.py`, changed

### 7.1 Top of the file

*Answer key: `[3.1]` (module docstring, extended) and `[7.1]` (new constant).*

1. Add "(Level 2 version.)" to the docstring's first line, and a paragraph saying what level 2 adds here: the tool list is handed through to the chat template, and when the conversation no longer fits, the older half is summarised by the model instead of being forgotten. Change the last line to say the numbers match RECIPE.md (3.x) and RECIPE_LEVEL2.md (7.x).
2. Under the two existing constants, leave a blank line, then a comment starting with `[7.1]` saying this is what the model is told when it summarises old messages. Under it define `SUMMARY_INSTRUCTIONS`, a string asking the model to summarise the conversation below so it can be continued later, to keep every name, number, fact, decision and open question, and to write plain sentences of no more than about 200 words. Write it as several shorter strings inside parentheses, one per line: Python joins strings that sit next to each other.

### 7.2 New function `find_user`

*Answer key: `[7.2]`.*

In level 1 the newest message is always the user's, so a loop that walks forward looking for a user message always finds one. In level 2 that stops being true: during a round of tool calls, the newest messages are the model's call and the tool's result. This small function does the looking safely.

Put it after the constants and before `class Backend`, at zero indentation. Parameters: `messages` and `start`.

**Docstring:** start with `[7.2]`. Say that it returns the index of the first user message at or after `start`, or `None` if there is none, and why: during tool calls the newest messages are not the user's.

1. A `for` loop over `range(start, len(messages))`, with the loop variable `index`. `range(a, b)` counts from `a` up to, but not including, `b`.
2. Inside it, `if` the role of `messages[index]` equals `"user"`, `return index`.
3. After the loop, `return None`.

### 7.3 Change the `Backend` class docstring, and add a class attribute

*Answer key: `[7.3] (level 1: [3.2])`.*

Compaction runs on the worker thread, but the window should say "Summarising...". The backend cannot touch the window, so the app will hand it a function to call instead.

1. Re-tag the class docstring as `[7.3] (level 1: [3.2])`, and change "forgets the oldest messages" to say it makes room by summarising or forgetting old messages.
2. After the docstring and before `chat`, add a comment starting with `[7.3]` explaining that the app sets this to a function to call when compaction starts, and that `None` means "tell nobody".
3. Under the comment, write `on_compact = None`. A variable written directly inside a class, not inside a method, is a **class attribute**: every object of the class starts with it.

### 7.4 Change `chat`

*Answer key: `[7.4] (level 1: [3.2.1])`.*

1. Add a fifth parameter, `tools`, with a default of `None`.
2. Pass `tools` on to `self.fit_to_context` as its fourth argument.
3. In the docstring, say that `tools` is a list of tool descriptions for the template, or `None` for no tools.

### 7.5 Change `fit_to_context`

*Answer key: `[7.5] (level 1: [3.2.2])`.*

1. Add a fourth parameter, `tools` (no default).
2. Pass `tools` to `self.build_prompt` as its third argument.
3. The `if` that returns the prompt now has only one condition: the token count is less than or equal to `room`. Drop the `or len(messages) == 1` part; items 6 and 7 below take over that job.
4. Replace the level 1 deletion lines at the bottom of the loop (`del messages[0]` and the inner `while` loop under it) with this:
   - Store `len(messages)` as `before`.
   - Call `self.compact` with `messages` and `room`.
   - `if len(messages) < before:` (compaction made the list shorter), `continue`, to go round and measure again.
5. Still inside the loop, after that `if`: compacting freed nothing, so fall back to level 1's forgetting. Set `second_user` to `find_user(messages, 1)`, the first user message after the very first message.
6. `if second_user is None:` `return prompt`. There is only one user message, the newest question, and nothing before it may go, so the prompt is used as it is.
7. Otherwise, `del messages[:second_user]`: delete everything before the second user message in one go. A slice in a `del` deletes every item it covers.
8. Rewrite the docstring: while the prompt is too long, `compact` folds the older half into a summary; if that frees nothing, everything before the second user message is forgotten, as in level 1; if there is no second user message, the prompt is used as it is; either way the change is made to `messages` itself.

### 7.6 New method `compact`

*Answer key: `[7.6]`.*

Add it to `Backend`, after `fit_to_context`. Parameters: `self`, `messages` and `room`.

**Docstring:** start with `[7.6]`. Say that it replaces the older half of `messages` with a short summary. Explain that the older half is at least three messages, so an earlier summary (two messages) is folded into the new one rather than summarised on its own, and that the cut moves forward to the next user message, so the recent half starts with something the user said. Say that the model summarises at temperature 0, and that the summary goes back in as a pair of messages because many chat templates expect user and model turns to alternate. Add that nothing changes if no user message comes after the cut, or if the older half is too long to summarise in one go.

1. Set `cut` to `find_user(messages, max(len(messages) // 2, 3))`: the first user message at or after the middle, or after the third message, whichever is later.
2. `if cut is None:` then `return`. There is nothing that can be cut cleanly.
3. Store `messages[:cut]` (everything before `cut`) as `older`.
4. Leave a blank line. Turn `older` into a plain transcript:
   - Start an empty list named `lines`.
   - Loop over `older` with the loop variable `message`. Inside: `if message.get("content"):` (tool-call messages may have none), append an f-string made of the message's `"role"`, a colon and a space, then its `"content"`. Inside an f-string that uses double quotes, write the keys with single quotes: `message['role']`.
5. Build the request: a list of two dictionaries, stored as `request`. The first has `"role"` set to `"system"` and `"content"` set to `SUMMARY_INSTRUCTIONS`. The second has `"role"` set to `"user"` and `"content"` set to two newline escapes joined onto the lines: `"\n\n".join(lines)`, which puts a blank line between each.
6. Call `self.build_prompt` with `request`, `False` (no thinking) and `None` (no tools), and store it as `prompt`.
7. `if self.count_tokens(prompt) > room:` then `return`. The older half is too big to summarise in one go.
8. Leave a blank line. `if self.on_compact:` then call `self.on_compact()`.
9. Get the summary in one go: call `self.stream` with `prompt` and `0`, and join every piece it yields into one string with `"".join(...)`. Then split it on `"</think>"`, take the last part with `[-1]`, and `.strip()` it. Store the result as `summary`.
10. Replace the older half with a pair of messages, using slice assignment: `messages[:cut] =` a list of two dictionaries. The first has `"role"` set to `"user"` and `"content"` set to `"Summary of our conversation so far:\n"` plus `summary`. The second has `"role"` set to `"assistant"` and `"content"` set to `"Thanks, I have that summary."`.

### 7.7 Change `LlamaCppBackend.build_prompt`

*Answer key: `[7.7] (level 1: [3.3.2])`.*

1. Add a third parameter, `tools`, with a default of `None`.
2. Pass `tools=tools` to `self.formatter` as well. Store what the formatter returns as `response`, then on the next line `return response.prompt`.
3. In the docstring, add that the template writes the tool descriptions into the prompt, along with instructions on how to call them.

### 7.8 Change `TransformersBackend.build_prompt`

*Answer key: `[7.8] (level 1: [3.4.2])`.*

1. Add a third parameter, `tools`, with a default of `None`.
2. Pass `tools=tools` to `apply_chat_template` as the first keyword argument, straight after `messages`.
3. In the docstring, add that the tool descriptions are handed to the template too.

## Step 8: `tools.py`, new

### 8.1 Top of the file

*Answer key: `[8.1]` (on the module docstring and three comments).*

1. A module docstring starting with `[8.1]`. Say that a tool is an ordinary Python function, the `@tool` decorator registers it, `schema_for` describes it from its name, docstring and type hints, `parse_tool_calls` reads the model's calls out of a reply, and a `Toolbox` puts built-in and MCP tools behind one `run` method. End it with a line saying the numbers in square brackets match the step numbers in RECIPE_LEVEL2.md.
2. Imports, each on its own line: `ast`, `inspect`, `json`, `operator`, `random`, `re`.
3. A comment starting with `[8.1]` saying these are the registry and the JSON names for Python types. Under it:
   - `TOOLS`, an empty dictionary, with a short comment: tool name to function, filled in by `@tool`.
   - `TYPE_NAMES`, a dictionary from Python types to JSON type names: `str` to `"string"`, `int` to `"integer"`, `float` to `"number"`, `bool` to `"boolean"`. The keys are the types themselves, with no quotes.
4. A comment starting with `[8.1]` saying these are the patterns for reading tool calls, and what `(.*?)` and `re.DOTALL` mean. Under it, three compiled patterns, each built with `re.compile(pattern, re.DOTALL)`. Write each pattern as a **raw string**, with an `r` before the opening quote, so backslashes are left alone:
   - `CALL_PATTERN`: `<tool_call>`, then a capture group of as little as possible, `(.*?)`, then a non-capturing group of two alternatives: `</tool_call>` or the end of the text. A non-capturing group is `(?:...)`, alternatives are separated by `|`, and `$` means the end. The end is allowed so that a call cut off mid-way is still read.
   - `FUNCTION_PATTERN`: `<function=`, a capture group of one or more characters that are not `>` or whitespace (`([^>\s]+)`), `>`, a capture group of as little as possible, then a non-capturing group of `</function>` or the end.
   - `PARAMETER_PATTERN`: `<parameter=`, the same name capture as above, `>`, a capture of as little as possible, then `</parameter>`.
5. A comment starting with `[8.1]` saying these are the calculator's allowed arithmetic and its limits on powers, so that neither `9 ** 9 ** 9` nor `(2 ** 1000) ** 1000` can freeze the app: the exponent may be at most `LARGEST_POWER`, and the answer at most `LARGEST_RESULT_BITS` binary digits long. Under it:
   - `OPERATORS`, a dictionary from `ast` operator classes to the `operator` module's functions, one pair per line: `ast.Add` to `operator.add`, `ast.Sub` to `operator.sub`, `ast.Mult` to `operator.mul`, `ast.Div` to `operator.truediv`, `ast.FloorDiv` to `operator.floordiv`, `ast.Mod` to `operator.mod`, `ast.Pow` to `operator.pow`, `ast.USub` to `operator.neg`, and `ast.UAdd` to `operator.pos`.
   - `LARGEST_POWER`, set to `1000`.
   - `LARGEST_RESULT_BITS`, set to `100_000`, with a comment: underscores in a number are only there to make it easier to read.

### 8.2 The function `tool`

*Answer key: `[8.2]`.*

Parameters: `function`.

**Docstring:** start with `[8.2]`. Say that it is a decorator, that writing `@tool` above a `def` is the same as `function = tool(function)` after it, and that it records the function in `TOOLS` under its own name and hands it back unchanged.

1. Store `function` in `TOOLS` under the key `function.__name__` (every function knows its own name).
2. `return function`.

### 8.3 The function `evaluate`

*Answer key: `[8.3]`.*

Parameters: `node`. This is the calculator's engine, and it is recursive.

**Docstring:** start with `[8.3]`. Say that `ast.parse` turns text like `2 * (3 + 4)` into a tree of nodes, and that a number is a leaf while an operation has one or two children. Say that the function handles a node by first handling its children, calling itself (recursion), and then applying the operator. Add that anything that is not a number or an allowed operator is refused, and that this is what makes it safe: unlike `eval()`, it can never run code. Add that a power is checked before it is worked out: a whole number's `bit_length()` is how many binary digits it has, and a power has about that many times the exponent.

Four `if` checks, each returning, then a `raise`:

1. `if isinstance(node, ast.Expression):` return `evaluate(node.body)`. This is the tree's outer wrapper.
2. `if isinstance(node, ast.Constant) and type(node.value) in (int, float):` return `node.value`. A plain number.
3. `if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:` (an operation with two sides):
   - Store `evaluate(node.left)` as `left` and `evaluate(node.right)` as `right`.
   - `if isinstance(node.op, ast.Pow):` then, inside it, work out roughly how many binary digits the answer would have: `abs(int(left)).bit_length()` times `abs(right)`, stored as `result_bits`. Then `if` `abs(right)` is greater than `LARGEST_POWER` **or** `result_bits` is greater than `LARGEST_RESULT_BITS`, `raise` a `ValueError` saying `"that power is too large"`.
   - `return` the result of looking up `type(node.op)` in `OPERATORS` and calling what you find with `left` and `right`.
4. `if isinstance(node, ast.UnaryOp) and type(node.op) in OPERATORS:` (a minus or plus sign in front of one value), `return` the operator from `OPERATORS` called with `evaluate(node.operand)`.
5. Anything else: `raise ValueError("only numbers, brackets and + - * / // % ** are allowed")`.

### 8.4 The built-in tools

*Answer key: `[8.4]` (a comment, because these docstrings must not carry tags).*

Above the first one, a two-line comment starting with `[8.4]` saying these are the built-in tools, and that their docstrings are what the model reads to decide when to use them, so they carry no tag.

1. `@tool` on its own line, then `def calculate(expression: str) -> str:`. Its docstring, on one line: `Work out an arithmetic expression exactly, for example (17 * 23) + 4 / 2. Use it for any sum you are not certain of.` Its body is one line: return `str(...)` of `evaluate` called on `ast.parse(expression, mode="eval")`.
2. `@tool`, then `def random_number(low: int, high: int) -> str:`. Docstring: `Pick a random whole number between low and high, including both ends. Use it for dice rolls and random choices.` Body: return `str(random.randint(low, high))`.

### 8.5 The function `schema_for`

*Answer key: `[8.5]`.*

Parameters: `function`.

**Docstring:** start with `[8.5]`. Say that `inspect.signature` lists the parameters with their type hints, that each becomes a property with a JSON type name, that parameters without a default are required, and that the docstring becomes the description the model reads, so it should say when to use the tool.

1. Start an empty dictionary `properties` and an empty list `required`.
2. Loop over `inspect.signature(function).parameters.items()` with two loop variables, `name` and `parameter` (each item is a pair). Inside:
   - Set `properties[name]` to a dictionary with one key, `"type"`, whose value is `TYPE_NAMES.get(parameter.annotation, "string")`. `.get` with a second argument gives that fallback when the key is missing.
   - `if parameter.default is inspect.Parameter.empty:` (no default was given), append `name` to `required`.
3. `return` this nested dictionary, laid out one key per line:
   - `"type"`: `"function"`.
   - `"function"`: a dictionary with `"name"` set to `function.__name__`, `"description"` set to `inspect.getdoc(function)`, and `"parameters"` set to a dictionary with `"type"` set to `"object"`, `"properties"` set to `properties`, and `"required"` set to `required`.

### 8.6 The function `parse_tool_calls`

*Answer key: `[8.6]`.*

Parameters: `text`. It returns two things at once, as a tuple: the text before any call, and a list of calls.

**Docstring:** start with `[8.6]`. Say that models mark a call with `<tool_call>` markers, that inside some models write `<function=...>` with `<parameter=...>` blocks and others write JSON, that both are read into the same shape (a dictionary with `"name"` and `"arguments"`), that unreadable calls are skipped, and that parameter values are left as strings for `Toolbox.run` to convert.

1. Split `text` on `"<tool_call>"`, take the first part with `[0]`, `.strip()` it, and store it as `before`.
2. Start an empty list named `calls`.
3. Loop over `CALL_PATTERN.findall(text)` with the loop variable `body`. Inside:
   - Strip `body` and store it back in `body`.
   - **JSON style.** `if body.startswith("{"):`
     - A `try:` block holding three things: set `data` to `json.loads(body)`; set `arguments` to `data.get("arguments", {})`; and, because some models write the arguments as a JSON string inside the JSON, `if isinstance(arguments, str):` set `arguments` to `json.loads(arguments)`.
     - `except (ValueError, AttributeError):` then `continue`. A tuple of exception types catches any of them: `ValueError` if the text is not JSON, `AttributeError` if it is JSON but not a dictionary (a list has no `.get`).
     - Append to `calls` a dictionary with `"name"` set to `data.get("name", "")` and `"arguments"` set to `arguments`.
     - `continue`.
   - **Function style.** Set `match` to `FUNCTION_PATTERN.search(body)`. `if match:`
     - Start an empty dictionary `arguments`.
     - Loop over `PARAMETER_PATTERN.findall(match.group(2))` with two loop variables, `key` and `value`. `match.group(2)` is the text the second capture group caught: everything inside the function block. Inside the loop, set `arguments[key]` to `value.strip("\n")`, which strips only newlines, so spaces inside a value survive.
     - Append to `calls` a dictionary with `"name"` set to `match.group(1)` and `"arguments"` set to `arguments`.
4. After the loop, `return before, calls`.

### 8.7 The function `convert`

*Answer key: `[8.7]`.*

Parameters: `value` and `type_name`.

**Docstring:** start with `[8.7]`. Say that a value read from a `<parameter>` is always a string, but a tool may want a whole number, a decimal or true/false, and that values already of the right kind, or whose wanted type is unknown, pass through.

1. `if not isinstance(value, str):` return `value`.
2. `if type_name == "integer":` return `int(value)`.
3. `if type_name == "number":` return `float(value)`.
4. `if type_name == "boolean":` return whether `value.strip().lower()` equals `"true"`.
5. `if type_name in ("array", "object"):` return `json.loads(value)`.
6. Otherwise return `value`.

### 8.8 The class `Toolbox`

*Answer key: `[8.8]`.*

**Docstring:** start with `[8.8]`. Say that it holds one list of schemas for the chat template and remembers who owns each tool (a Python function from `TOOLS`, or an MCP server), and that if two tools share a name the first one wins.

#### 8.8.1 Method `__init__`

Parameters: `self` and `servers`, a list of connected MCP servers (possibly empty).

**Docstring:** start with `[8.8.1]`. Say that it gathers the built-in tools, then each server's tools, and that each server already holds its tools' schemas.

1. Store `servers` as `self.servers`.
2. Three attributes, each with a short comment after it: `self.schemas`, an empty list (what the chat template is given); `self.owners`, an empty dictionary (tool name to its function or server); and `self.properties`, an empty dictionary (tool name to what each argument should be).
3. Loop over `TOOLS.values()` with the loop variable `function`, and call `self.add` with `schema_for(function)` and `function`.
4. Loop over `servers` with the loop variable `server`, and inside it loop over `server.schemas` with the loop variable `schema`, calling `self.add` with `schema` and `server`.

#### 8.8.2 Method `add`

Parameters: `self`, `schema` and `owner`. One-line docstring starting with `[8.8.2]`: add one tool, unless a tool with that name is already in.

1. Read the name: `schema["function"]["name"]`, stored as `name`.
2. `if name in self.owners:` then `return`.
3. Append `schema` to `self.schemas`, and set `self.owners[name]` to `owner`.
4. Set `parameters` to `schema["function"].get("parameters", {})`, then set `self.properties[name]` to `parameters.get("properties", {})`.

#### 8.8.3 Method `run`

Parameters: `self`, `name` and `arguments`.

**Docstring:** start with `[8.8.3]`. Say that each argument is converted to the type its schema asks for. Say that a built-in tool is called with the arguments unpacked as keywords (`**arguments`) and a server is asked to run its tool. Add that any error comes back as text starting `Error:`, because the model can read that and try again, while an exception would end the whole reply.

1. `if name not in self.owners:` return an f-string: `Error: there is no tool called `, then `name` in braces, then a full stop.
2. A `try:` block. Inside:
   - Set `wanted` to `self.properties[name]`.
   - Start an empty dictionary `converted`. Loop over `arguments.items()` with `key` and `value`. Inside, set `type_name` to `wanted.get(key, {}).get("type")`, then set `converted[key]` to `convert(value, type_name)`.
   - Set `owner` to `self.owners[name]`.
   - `if callable(owner):` return `str(owner(**converted))`.
   - Otherwise return `owner.call_tool(name, converted)`.
3. `except Exception as error:` return an f-string: `Error: `, then `error` in braces.

## Step 9: `mcp_client.py`, new

### 9.1 Top of the file

*Answer key: `[9.1]` (module docstring and one comment).*

1. A module docstring starting with `[9.1]`: what an MCP server is, that the client starts each server from `mcp_servers.json` as a child process and talks over its stdin and stdout, one line of JSON-RPC 2.0 per message, the difference between a request and a notification, and the opening sequence (`initialize`, `notifications/initialized`, `tools/list`, then `tools/call`). End it with the line about the numbers matching RECIPE_LEVEL2.md.
2. Imports, each on its own line: `json`, `os`, `pathlib`, `queue`, `shutil`, `subprocess`, `sys`, `threading`.
3. A comment starting with `[9.1]` saying these are the protocol version this client speaks and how long to wait for a server. Under it: `PROTOCOL_VERSION` set to the string `"2025-06-18"`, and `TIMEOUT_SECONDS` set to `60`.

### 9.2 The class `MCPServer`

*Answer key: `[9.2]`.*

**Docstring:** start with `[9.2]`. Say that it is one running server and its tools. Explain that reading from a pipe waits until a line arrives, possibly for ever, so a small background thread only reads the server's output into a queue. That lets `request` wait on the queue with a time limit: the same queue idea as the app's.

#### 9.2.1 Method `__init__`

Parameters: `self`, `name`, `command`, `args`, `folder`, and `env` with a default of `None`.

**Docstring:** start with `[9.2.1]`. Say that it starts the server, introduces the client, and lists the tools. Say that the command `"python"` is replaced by `sys.executable`, the Python running the app, so a Python server gets the same libraries; that any other command is found by `shutil.which` the way a terminal would; that the server's error output goes to `mcp-<name>.log` in the config's folder; and that if the opening exchange fails, the server is stopped before the error is passed on.

1. Store `name` as `self.name`.
2. `if command == "python":` set `program` to `sys.executable`. `else:` set `program` to `shutil.which(command)`, or, if that gives `None`, to `command` itself. Write that in one line with `or`: `a or b` gives `a` unless `a` counts as false.
3. Copy the current environment variables: set `environment` to `dict(os.environ)`. Then `if env:` call `environment.update(env)` to add the server's own.
4. Build the log file's path: `pathlib.Path(folder)` divided by (`/`) an f-string `mcp-` then `name` in braces then `.log`. Store it as `log_path`.
5. Open it for writing and keep it: set `self.log` to `open(log_path, "w", encoding="utf-8")`.
6. Start the server: set `self.process` to `subprocess.Popen(...)` with one positional argument and seven keyword arguments, one per line:
   - The command line: a list with `program` in it, plus `list(args)`.
   - `cwd` set to `folder` (the server starts in the config's folder).
   - `env` set to `environment`.
   - `stdin` set to `subprocess.PIPE`, and `stdout` set to `subprocess.PIPE`.
   - `stderr` set to `self.log`.
   - `text` set to `True` (send and receive strings, not bytes), and `encoding` set to `"utf-8"`.
7. Set `self.lines` to a new `queue.Queue()`, and `self.next_id` to `1`.
8. Create a `threading.Thread` with `target` set to `self.read_lines` and `daemon` set to `True`, store it as `reader`, and start it.
9. Leave a blank line. Open a `try:` block for the opening exchange. Inside it:
   - Call `self.request` with `"initialize"` and a dictionary, laid out one key per line: `"protocolVersion"` set to `PROTOCOL_VERSION`, `"capabilities"` set to an empty dictionary, and `"clientInfo"` set to a dictionary with `"name"` set to `"voxmux"` and `"version"` set to `"1.0"`.
   - Call `self.notify` with `"notifications/initialized"`.
   - Set `self.schemas` to `self.list_tools()`.
10. `except Exception:` call `self.close()`, then a bare `raise`. A server that never got going is stopped instead of being left running in the background, and the error still reaches `start_servers`.

#### 9.2.2 Method `read_lines`

Parameters: just `self`. Runs on the reader thread.

**Docstring:** start with `[9.2.2]`. Say that looping over a pipe gives one line at a time and ends when the server closes it, and that `None` is then put in the queue to mean "no more lines".

1. Loop over `self.process.stdout` with the loop variable `line`, and put each `line` into `self.lines`.
2. After the loop, put `None` into `self.lines`.

#### 9.2.3 Method `send`

Parameters: `self` and `message`. One-line docstring starting with `[9.2.3]`: write one message to the server as a single line of JSON.

1. Call `self.process.stdin.write` with `json.dumps(message)` plus `"\n"`.
2. Call `self.process.stdin.flush()`, so it is sent now rather than when a buffer fills.

#### 9.2.4 Method `notify`

Parameters: `self`, `method`, and `params` with a default of `None`. One-line docstring starting with `[9.2.4]`: send a notification, a message that gets no answer.

1. Set `message` to a dictionary with `"jsonrpc"` set to `"2.0"` and `"method"` set to `method`.
2. `if params is not None:` set `message["params"]` to `params`.
3. Call `self.send` with `message`.

#### 9.2.5 Method `request`

Parameters: `self`, `method` and `params`.

**Docstring:** start with `[9.2.5]`. Say that each request gets the next id number and lines are read until the matching response arrives. On the way, the server's notifications are ignored, its requests are answered by `answer_server_request`, and lines that are not a JSON object are skipped. A response holding `"error"` becomes an exception.

1. Store `self.next_id` as `request_id`, then add 1 to `self.next_id`.
2. Call `self.send` with a dictionary: `"jsonrpc"` set to `"2.0"`, `"id"` set to `request_id`, `"method"` set to `method`, and `"params"` set to `params`.
3. Leave a blank line. A `while True:` loop. Inside it:
   - A `try:` block that sets `line` to `self.lines.get(timeout=TIMEOUT_SECONDS)`. In `except queue.Empty:` (nothing arrived in time), `raise` a `TimeoutError` whose message is an f-string: `MCP server `, `self.name` in braces, ` did not answer `, `method` in braces.
   - `if line is None:` `raise` a `ConnectionError` with an f-string: `MCP server `, `self.name` in braces, ` stopped`.
   - A second `try:` that sets `message` to `json.loads(line)`, with `except ValueError:` then `continue`.
   - `if not isinstance(message, dict):` then `continue`. A stray line such as `42` is valid JSON but not a message.
   - `if "method" in message:` (the server is sending us something): inside, `if "id" in message:` call `self.answer_server_request(message)`; then, back at the first `if`'s level inside it, `continue`.
   - `if message.get("id") == request_id:` inside, first `if "error" in message:` `raise` a `RuntimeError` with `message["error"].get("message", "unknown error")`; then `return message.get("result", {})`.

#### 9.2.6 Method `answer_server_request`

Parameters: `self` and `message`.

**Docstring:** start with `[9.2.6]`. Say that servers may ask a client things such as `ping`, that this client answers `ping` and refuses everything else with JSON-RPC's standard "method not found" error.

1. `if message["method"] == "ping":` call `self.send` with a dictionary: `"jsonrpc"` set to `"2.0"`, `"id"` set to `message["id"]`, and `"result"` set to an empty dictionary.
2. `else:` set `error` to a dictionary with `"code"` set to `-32601` and `"message"` set to `"Method not found"`, then send a dictionary with `"jsonrpc"`, the same `"id"`, and `"error"` set to `error`.

#### 9.2.7 Method `list_tools`

Parameters: just `self`.

**Docstring:** start with `[9.2.7]`. Say that a server may hand its list over in pages, and that while a response carries a `"nextCursor"`, that cursor is sent back to get the next page. Add that MCP's `"inputSchema"` is exactly what a chat template calls `"parameters"`.

1. Start an empty list `schemas`, and set `cursor` to `None`.
2. A `while True:` loop. Inside:
   - Set `params` to an empty dictionary. `if cursor:` set `params["cursor"]` to `cursor`.
   - Set `result` to `self.request("tools/list", params)`.
   - Loop over `result.get("tools", [])` with the loop variable `item`. Append to `schemas` a dictionary with `"type"` set to `"function"` and `"function"` set to a dictionary of `"name"` (`item["name"]`), `"description"` (`item.get("description", "")`) and `"parameters"` (`item.get("inputSchema", {"type": "object"})`).
   - Set `cursor` to `result.get("nextCursor")`. `if not cursor:` return `schemas`.

#### 9.2.8 Method `call_tool`

Parameters: `self`, `name` and `arguments`.

**Docstring:** start with `[9.2.8]`. Say that a result's `"content"` is a list of parts, that text parts are joined while other kinds (such as images) are only noted, and that a failed tool (`"isError"`) comes back starting `Error:`.

1. Set `result` to `self.request` called with `"tools/call"` and a dictionary with `"name"` set to `name` and `"arguments"` set to `arguments`.
2. Start an empty list `parts`. Loop over `result.get("content", [])` with `part`. Inside: `if part.get("type") == "text":` append `part["text"]`; `else:` append an f-string: `[`, then `part.get('type')` in braces, then ` content not shown]`.
3. Set `text` to `"\n".join(parts)`.
4. `if result.get("isError"):` return `"Error: "` plus `text`.
5. `return text`.

#### 9.2.9 Method `close`

Parameters: just `self`.

**Docstring:** start with `[9.2.9]`. Say that MCP's way to end a conversation over stdin is to close the server's stdin, that a well-behaved server then exits on its own, that it gets five seconds, and that one still running after that is killed.

1. A `try:` block: call `self.process.stdin.close()`, then `self.process.wait(timeout=5)`.
2. `except Exception:` call `self.process.kill()`. `wait` raises an exception if the time runs out.
3. After that, call `self.log.close()`.

### 9.3 The function `start_servers`

*Answer key: `[9.3]`.*

Back at zero indentation. Parameters: `config_path`. It returns a tuple: the started servers, and a list of problems.

**Docstring:** start with `[9.3]`. Say that the config file uses the same layout as other MCP clients: an `"mcpServers"` object whose keys are server names, each with a `"command"`, optional `"args"` and optional `"env"`. Add that a server that fails to start is reported in `problems` instead of stopping the others, and that no file means no servers.

1. Set `path` to `pathlib.Path(config_path)`. Start two empty lists, `servers` and `problems`.
2. `if not path.exists():` return `servers, problems`.
3. Set `config` to `json.loads(path.read_text(encoding="utf-8"))`.
4. Loop over `config.get("mcpServers", {}).items()` with `name` and `settings`. Inside, a `try:` block:
   - Set `server` to an `MCPServer` built with five arguments, one per line: `name`, `settings["command"]`, `settings.get("args", [])`, `path.parent`, and `settings.get("env")`.
   - Append `server` to `servers`.
   - In `except Exception as error:` append an f-string to `problems`: `name` in braces, a colon and a space, `error` in braces.
5. After the loop, return `servers, problems`.

## Step 10: `demo_mcp_server.py`, new

This is an MCP server, the other end of step 9. The client starts it; you never run it yourself.

### 10.1 Top of the file

*Answer key: `[10.1]`.*

1. A module docstring starting with `[10.1]`. Say that it reads one JSON-RPC message per line from stdin and writes each response as one line to stdout. Add that, because stdout is the channel to the client, nothing else may be printed there, so anything meant for a person goes to stderr. List the three tools: the time in any time zone, and saving and listing notes kept in `notes.json`. End it with the line about the numbers matching RECIPE_LEVEL2.md.
2. Imports, each on its own line: `datetime`, `json`, `pathlib`, `sys`, `zoneinfo`.
3. A comment starting with `[10.1]`, then two constants:
   - `NOTES_FILE`, set to `pathlib.Path(__file__).with_name("notes.json")`: a file named `notes.json` in this file's folder.
   - `SERVER_INFO`, a dictionary with `"name"` set to `"voxmux-demo"` and `"version"` set to `"1.0"`.

### 10.2 The tool descriptions

*Answer key: `[10.2]`.*

A two-line comment starting with `[10.2]` saying these describe the tools the MCP way. Then `TOOLS`, a list of three dictionaries, each with `"name"`, `"description"` and `"inputSchema"`:

1. `"get_current_time"`, described as getting the current date and time in a time zone, such as Europe/London or Asia/Tokyo. Its input schema: `"type"` set to `"object"`, `"properties"` set to a dictionary whose one key `"timezone"` maps to `{"type": "string"}`, and `"required"` set to a list holding `"timezone"`.
2. `"save_note"`, described as saving a short note so it can be read back later, even after the app is closed. Same shape, with one required string property, `"text"`.
3. `"list_notes"`, described as listing every note saved so far. Its schema is `"type"` set to `"object"` and an empty `"properties"`.

### 10.3 The tools themselves

*Answer key: `[10.3]` (on each function and on `HANDLERS`).*

Four short functions, each with a one-line docstring starting with `[10.3]`:

1. `get_current_time(timezone)`: `zoneinfo.ZoneInfo` needs the `tzdata` package from step 6 on Windows. Set `now` to `datetime.datetime.now(zoneinfo.ZoneInfo(timezone))`, then return `now.strftime(...)` with an f-string as the format: `%A %d %B %Y, %H:%M in `, then `timezone` in braces. The `%` codes are the weekday, day, month name, year, hours and minutes.
2. `load_notes()`: `if NOTES_FILE.exists():` return `json.loads(NOTES_FILE.read_text(encoding="utf-8"))`. Otherwise return an empty list.
3. `save_note(text)`: set `notes` to `load_notes()`, append `text`, write the list back with `NOTES_FILE.write_text(json.dumps(notes, indent=2), encoding="utf-8")`, and return an f-string: `Saved. There are now `, `len(notes)` in braces, ` notes.`.
4. `list_notes()`: set `notes` to `load_notes()`. `if not notes:` return `"There are no notes yet."`. Otherwise start an empty list `lines`, loop over `enumerate(notes, start=1)` with `number` and `note` (`enumerate` counts as it goes), append an f-string of `number`, a full stop and a space, then `note`, and return `"\n".join(lines)`.

Then a comment starting with `[10.3]` and the dictionary `HANDLERS`, from each tool's name to its function: `"get_current_time"` to `get_current_time`, and the same for `save_note` and `list_notes`.

### 10.4 The function `handle`

*Answer key: `[10.4]`.*

Parameters: `message`. It returns the response to send, or `None` for a notification.

**Docstring:** start with `[10.4]`. Say that the method name decides what to do, and that a failing tool is not a protocol error: its message goes back as the tool's result, marked with `isError`, so the model can read it.

1. Set `method` to `message.get("method")`.
2. `if "id" not in message:` return `None`.
3. Leave a blank line. An `if` / `elif` chain on `method`, each branch setting `result`:
   - `"initialize"`: set `version` to `message.get("params", {}).get("protocolVersion", "2025-06-18")`, then set `result` to a dictionary with `"protocolVersion"` set to `version`, `"capabilities"` set to `{"tools": {}}`, and `"serverInfo"` set to `SERVER_INFO`.
   - `"ping"`: `result` is an empty dictionary.
   - `"tools/list"`: `result` is `{"tools": TOOLS}`.
   - `"tools/call"`: set `params` to `message.get("params", {})` and `handler` to `HANDLERS.get(params.get("name"))`. Then a `try:` block: `if handler is None:` raise a `ValueError` with an f-string `unknown tool ` and `params.get('name')` in braces; set `text` to `handler(**params.get("arguments", {}))`; set `result` to a dictionary with `"content"` set to a list holding `{"type": "text", "text": text}` and `"isError"` set to `False`. In `except Exception as error:`, set `result` to the same shape with `str(error)` as the text and `"isError"` set to `True`.
   - `else:` set `error` to `{"code": -32601, "message": ...}` where the message is an f-string `Method not found: ` and `method` in braces, and return a dictionary with `"jsonrpc"` set to `"2.0"`, `"id"` set to `message["id"]`, and `"error"` set to `error`.
4. After the chain, return a dictionary with `"jsonrpc"` set to `"2.0"`, `"id"` set to `message["id"]`, and `"result"` set to `result`.

### 10.5 The function `main`

*Answer key: `[10.5]`.*

**Docstring:** start with `[10.5]`. Say that the pipes are switched to UTF-8 so any language survives the trip, that looping over `sys.stdin` ends when the client closes it, and that a line that is not JSON is skipped.

1. Call `sys.stdin.reconfigure(encoding="utf-8")` and the same on `sys.stdout`.
2. Loop over `sys.stdin` with `line`. Inside: `if not line.strip():` then `continue`. A `try:` that sets `message` to `json.loads(line)`, with `except ValueError:` then `continue`, so a stray line cannot crash the server. Set `response` to `handle(message)`. `if response is not None:` print `json.dumps(response)` with `flush` set to `True`.

### 10.6 The last two lines

*Answer key: `[10.6]`.*

The same `if __name__ == "__main__":` ending as `app.py`, calling `main()`, with a comment above it starting with `[10.6]`.

## Step 11: `mcp_servers.json`, new

A JSON file, so no tags and no comments (JSON does not allow them). It holds one object with one key, `"mcpServers"`. That key's value is an object with one key, `"demo"`, whose value is an object with two keys:

- `"command"`: the string `"python"`.
- `"args"`: a list holding one string, `"demo_mcp_server.py"`.

JSON is strict: double quotes only, and no comma after the last item in an object or list.

## Step 12: `app.py`, changed

### 12.1 Top of the file

*Answer key: `[4.1]` (docstring, extended) and `[12.1]` (new constants).*

1. In the module docstring: add "(Level 2 version.)" to the first line, add "the tools" to the list of state the class holds, and add a paragraph: when the model answers with a tool call instead of text, the worker runs the tool, adds the result to the conversation and asks the model again, until it gives a plain answer. Change the last line to say the numbers match RECIPE.md (4.x) and RECIPE_LEVEL2.md (12.x).
2. Add `import pathlib` as the first import (imports are kept in alphabetical order).
3. Under `from backends import load_backend`, add `from mcp_client import start_servers` and `from tools import Toolbox, parse_tool_calls`.
4. Under the level 1 constants, leave a blank line, then a two-line comment starting with `[12.1]`, then two constants:
   - `MCP_CONFIG`, set to `pathlib.Path(__file__).with_name("mcp_servers.json")`. Using the app file's own folder means it is found however the app is started.
   - `MAX_TOOL_ROUNDS`, set to `5`.

### 12.2 Change `__init__`

*Answer key: `[12.2] (level 1: [4.3])`.*

1. After the `geometry` line, call `self.root.protocol` with `"WM_DELETE_WINDOW"` and `self.close`. This sets what happens when the window's X button is clicked.
2. After `self.thinking_instructions`, add `self.toolbox = None`, with a comment: the tools, once the first model is loaded.
3. Update the docstring to mention both.

Also update the class docstring (it keeps its tag, `[4.2]`): the small helpers are now `start_worker`, `stream_reply`, `append_chat`, `set_busy` and `close`.

### 12.3 Change the settings row

*Answer key: `[12.3] (level 1: [4.4.2])`.*

At the end of the settings row block in `build_widgets`, add:

1. A `tk.BooleanVar` with `value` set to `True`, stored as `self.use_tools`.
2. A `tk.Checkbutton` with parent `settings`, `text` set to `"Use tools"`, and `variable` set to `self.use_tools`, packed with `side` set to `"left"` and `padx` set to `(8, 0)`.

Change the block's comment to say temperature, thinking and tools.

### 12.4 Change `send`

*Answer key: `[12.4] (level 1: [4.9])`.*

1. With the other settings, read `self.use_tools.get()` into `use_tools`.
2. Pass `use_tools` to `self.start_worker` as its last argument, after `thinking`.
3. Re-tag the docstring and add that the Use tools setting is read here too.

### 12.5 Change `load_worker`

*Answer key: `[12.5] (level 1: [4.11])`.*

The first time a model loads, the MCP servers are started too.

1. Inside the `try`, after `backend` is loaded: set `toolbox` to `self.toolbox`, and `problems` to an empty list.
2. `if toolbox is None:` set `servers, problems` (two names on the left, unpacking the tuple) to `start_servers(MCP_CONFIG)`, then set `toolbox` to `Toolbox(servers)`.
3. Change the `put` so that the value is a tuple of three: `("loaded", (backend, toolbox, problems))`.
4. Update the docstring to explain both.

### 12.6 Change `reply_worker`

*Answer key: `[12.6] (level 1: [4.12])`.*

Its streaming loop moves out into a new method (12.7), and this method becomes the tool loop. Add a fourth parameter, `use_tools`.

**Docstring:** each round streams one reply. With no tool call in it, that is the answer. Otherwise the reply and its calls join the conversation as an assistant message, each tool runs, its result is shown and added as a `"tool"` message, and the model is asked again. `MAX_TOOL_ROUNDS` stops a model that never stops calling, and the note saying so is shown in the log. With Use tools off, no tools are offered, and a call the model writes anyway is not run.

Inside the `try:`

1. Set `tools` to `None`. `if use_tools:` set `tools` to `self.toolbox.schemas`.
2. Loop `for round_number in range(MAX_TOOL_ROUNDS):` (`range(5)` counts 0 to 4). Inside:
   - Set `answer` to `self.stream_reply` called with `system_prompt`, `temperature`, `thinking` and `tools`.
   - Set `text, calls` to `parse_tool_calls(answer)`.
   - `if not calls or not use_tools:` put `("reply", text)` in the queue, then `return`. Put a comment above it: there is no call to run, or tools are off so a call is never run, and only the text before any `<tool_call>` is kept, as it is all the log showed. Keeping `text` rather than `answer` also stops a broken call the reader could not understand from sitting in the conversation.
   - Leave a blank line. Build the call list for the conversation: an empty list `tool_calls`; loop over `calls` with `call`, appending a dictionary with `"type"` set to `"function"` and `"function"` set to `call`.
   - Append to `self.messages` a dictionary with `"role"` set to `"assistant"`, `"content"` set to `text`, and `"tool_calls"` set to `tool_calls`.
   - Loop over `calls` with `call`. Inside: put `("status", ...)` in the queue with an f-string `Running tool `, `call['name']` in braces, `...`; set `result` to `self.toolbox.run(call["name"], call["arguments"])`; put `("piece", ...)` in the queue with an f-string made of a newline, `[`, `call['name']` in braces, a space, `call['arguments']` in braces, ` -> `, `result` in braces, `]` and a newline; and append to `self.messages` a dictionary with `"role"` set to `"tool"`, `"name"` set to `call["name"]`, and `"content"` set to `result`.
   - After that inner loop, put `("status", "Writing a reply...")` in the queue.
3. After the `for` loop (all rounds used up), set `note` to `"(Stopped: too many tool calls in a row.)"`, then put `("piece", note)` and then `("reply", note)` in the queue. The piece is what makes it show in the log; the reply finishes the work and adds it to the conversation.

The `except` stays as it was.

### 12.7 New method `stream_reply`

*Answer key: `[12.7] (level 1: inside [4.12])`.*

Parameters: `self`, `system_prompt`, `temperature`, `thinking` and `tools`. Put it right after `reply_worker`.

**Docstring:** this is level 1's streaming loop, moved into its own method because a reply that uses tools needs several rounds of it. Anything from `<tool_call>` onwards is kept out of the log, since it is meant for the app, not the reader. It returns the reply with any thinking removed.

It is level 1's `reply_worker` body without the `try`, with three differences:

1. The call to `self.backend.chat` gets `tools` as a fifth argument.
2. `visible` is made in two lines: first `reply.split("<tool_call>")[0]`, then on the next line `.replace("</think>", "\n[end of thinking]").strip()` applied to that.
3. At the end, instead of putting a `"reply"` in the queue, it returns `reply.split("</think>")[-1].strip()`.

### 12.8 Change `poll_results`

*Answer key: `[12.8] (level 1: [4.13])`.*

1. Add a branch after `"piece"`: `elif kind == "status":` set the status text to `value`. Like a piece, it leaves the buttons alone.
2. Change the `"loaded"` branch:
   - First unpack the three parts: `backend, toolbox, problems = value`.
   - Set `self.backend` to `backend` and `self.toolbox` to `toolbox`, and reset `self.messages` as before.
   - Give the backend its compaction alert: set `backend.on_compact` to a `lambda` with no parameters that puts `("status", "Summarising older messages to make room...")` in `self.results`. A lambda is needed because the alert runs later, on the worker thread, and it may only use the queue.
   - Build the status text in a variable `text`: an f-string with `Ready: `, `self.model_path`, a space, then in round brackets `backend.context_size` followed by ` tokens of context, ` and `len(toolbox.schemas)` followed by ` tools`.
   - `if problems:` set `text` to `text` plus `" MCP problems: "` plus `"; ".join(problems)`.
   - Set the status text to `text`, and call `self.set_busy(False)`.
3. Update the docstring: a `"status"` only changes the status line, and when a model loads it is given the compaction alert.

### 12.9 New method `close`

*Answer key: `[12.9]`.*

Parameters: just `self`. Put it after `set_busy`. One-line docstring starting with `[12.9]`: window closed, stop every MCP server, then close the window.

1. `if self.toolbox is not None:` loop over `self.toolbox.servers` with `server` and call `server.close()` on each.
2. Call `self.root.destroy()`.

## Step 13: run it

From inside `my_build_level2`:

```bash
python app.py
```

Load the 4B model. The status line should end with `(262144 tokens of context, 5 tools)`: two built-in tools and three from the demo server. Then check:

1. "What is 1234 * 5678? Use the calculator." The log shows a line like `[calculate {'expression': '1234 * 5678'} -> 7006652]`, then the answer.
2. "What time is it in Tokyo right now?" The model calls `get_current_time` with `Asia/Tokyo`, and "Running tool get_current_time..." flashes in the status line.
3. "Save a note that says: buy oat milk." A file named `notes.json` appears in the folder. Close the app, open it again, load the model, and ask "What notes have I saved?" The note is still there.
4. Untick Use tools and ask something. The model answers without calling anything.
5. Compaction is hard to see with 262,144 tokens of context. To try it, temporarily add a line at the end of `LlamaCppBackend.__init__` that sets `self.context_size` to `2200`. Half of that is set aside for the reply and about 570 tokens go on the tool descriptions, so the conversation fills up after about a dozen short messages. Then tell the model fifteen facts about yourself, one per message. The status line shows "Summarising older messages to make room...", and afterwards the model still knows the first fact. Put the line back when you are done.
6. A file named `mcp-demo.log` appears next to the config. It is empty unless the server printed an error.

## Adding other MCP servers

Any MCP server that talks over stdin and stdout can go in `mcp_servers.json`, as one more entry next to `"demo"`. Two official ones to try:

- **Time:** command `"uvx"`, args `["mcp-server-time"]`. Needs `uv`.
- **Files:** command `"npx"`, args `["-y", "@modelcontextprotocol/server-filesystem", "C:\\Users\\you\\Documents"]`, with a folder of your own. Needs Node.js. In JSON, a backslash must be written twice.

Each one is downloaded the first time it starts, so the first Load takes longer. If that download takes more than `TIMEOUT_SECONDS` (60), the status line says the server "did not answer initialize"; restart the app to try again once the download has finished. Restart the app after editing the file; servers start only on the first Load. If a server does not start, the status line says so after "MCP problems:", and its `mcp-<name>.log` says why. The time server's tools include its own `get_current_time`; since the demo server's tool has the same name and comes first, the model gets the demo one. Remove `"demo"` to use the official one.

An MCP server runs with your permissions and can do anything you can, so only add servers you trust.

## When it does not work

| What you see | Likely cause | Look at |
| --- | --- | --- |
| Status ends with `2 tools` | `mcp_servers.json` is missing or in another folder, or the demo server failed to start. Look after "MCP problems:" in the status line. | step 11, `[12.1]` |
| Status ends with `0 tools`, or fewer than you expect | A built-in tool is not registered: check the `@tool` line above each one, `tool` itself, and the loop over `TOOLS.values()`. | `[8.2]`, `[8.4]`, `[8.8.1]` |
| "MCP problems: demo: MCP server demo stopped" | The server crashed while starting. `mcp-demo.log` has its traceback. | `mcp-demo.log`, step 10 |
| "MCP problems: demo: MCP server demo did not answer initialize" after a minute | The server never sent its reply. Most often `print` is missing `flush=True`, so the reply sits in a buffer. | `[10.5]` |
| After the model loads, the status shows "Error: Expecting property name enclosed in double quotes", "Error: Illegal trailing comma" or another "Error: Expecting ..." | `mcp_servers.json` is not valid JSON: often single quotes, or a comma after the last item. | step 11 |
| The raw `<tool_call>` text shows in the log | `stream_reply` is not cutting `visible` at `<tool_call>`. | `[12.7]` |
| A tool line shows, then "(Stopped: too many tool calls in a row.)" | The tool's result is not being added as a `"tool"` message, so the model asks again; or the model is too small to stop. | `[12.6]` |
| `[calculate ... -> Error: ...]` | The model wrote something the calculator refuses. It can usually read the error and try again. | `[8.3]` |
| "Error: ...fit_to_context() missing 1 required positional argument: 'tools'" | `chat` does not pass `tools` on to `fit_to_context`. | `[7.4]` |
| "Error: ...build_prompt() takes 3 positional arguments but 4 were given" | A `build_prompt` is missing its new `tools=None` parameter. | `[7.7]`, `[7.8]` |
| The status counts the tools, but the model never calls one | `fit_to_context` does not pass `tools` to `build_prompt`, or `build_prompt` does not pass it to the template. | `[7.5]`, `[7.7]`, `[7.8]` |
| "Error: list index out of range" during a long conversation with tools | A loop looks for a user message without checking for the end of the list. Use `find_user`. | `[7.2]`, `[7.5]`, `[7.6]` |
| The model forgets an early fact even after "Summarising..." | The model is small and wrote a poor summary, or `compact` replaced the wrong part. Check what the conversation starts with. | `[7.6]` |

## How this was checked

- **The answer key** was driven through its real window with the 0.8B GGUF, a Q8 build of the 4B GGUF and the 2B PyTorch model. All three called the calculator and the demo server's three tools correctly from plain questions, and answered without tools when Use tools was off. The note survived between calls.
- **Compaction** was tested with the context shrunk on purpose. All three models summarised the older half when it filled. The 4B model's summary kept every early fact, and it then answered a question about the first one correctly.
- **The tool-call reader** was tested on both the `<function=...>` and the JSON style, and on broken calls, which are skipped. The calculator was tested on huge powers, including `(2 ** 1000) ** 1000`, and on code it must refuse. The MCP client was tested on errors, unknown tools, non-English text, a server that prints stray lines and never answers (it is stopped, not left running), and a polite shutdown.
- **Making room** was tested on 2,000 random conversations mixing user, model and tool messages, with random context sizes. None crashed, the newest user message and everything after it were always kept, and the conversation always started with a user message.
- **Troubleshooting table:** each row that describes a coding mistake was checked by making that mistake in a copy of the answer key and running it.
- **Independent review:** reviewers who had not written the code checked this recipe against the answer key line by line, and copies of level 2 were written from this recipe alone.
- **Not tested here:** third-party MCP servers. The machine this was written on was not allowed to download and run them, so the "Adding other MCP servers" section is untested. The client follows the published protocol.

## Known rough edges

- **The quality depends on the model.** Small models call tools when they should not: the 0.8B saved the word "noted" as a note over and over until `MAX_TOOL_ROUNDS` stopped it. They also write poor summaries: the 0.8B's summary dropped the cat's name, and the 2B kept it but then answered wrongly anyway. Use the biggest model that fits.
- Every tool description is sent with every message, about 500 tokens for the five tools here, even when no tool is needed.
- Servers start on the first Load only. After editing `mcp_servers.json`, restart the app.
- A server that hangs makes a tool call wait 60 seconds (`TIMEOUT_SECONDS`) before giving up.
- Tool results are not shortened, so a tool that returns a whole file can fill the context in one go.
- Text a tool returns goes straight to the model, which may treat instructions inside it as if you had written them. Be careful with tools that read web pages or other people's files.
- If the window is closed while the first Load is still starting the servers, they are not stopped by the app; they stop on their own when their input closes as the app exits.
- Compaction runs only when the context is completely full. With the maximum context, that may take a very long conversation, and summarising that much at once takes a while.

Everything in level 1's "Known rough edges" still applies, except that old messages are now summarised rather than simply forgotten.
