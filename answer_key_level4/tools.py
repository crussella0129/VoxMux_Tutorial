"""[8.1] tools.py: the tools a model may call, and reading its calls back.
(Level 4 version.)

How it works: a tool is an ordinary Python function. The @tool decorator
puts it in the TOOLS dictionary, and schema_for() describes it the way chat
templates expect, using the function's name, docstring and type hints. When
the model wants a tool it writes a <tool_call> block in its reply;
parse_tool_calls() finds those blocks and reads out the tool's name and
arguments. A Toolbox gathers the built-in tools and the tools offered by
MCP servers behind one run() method, so the app does not care where a tool
lives.

Level 4 reads a second way of writing a call. Models in the Llama 3.2 family
use no <tool_call> mark: the call is the whole reply, written as JSON. So a
reply that starts like JSON is now treated as a possible call, and only
counted as ordinary text once it is clear that it is not one.

The numbers in square brackets match the step numbers in RECIPE_LEVEL2.md
(8.x) and RECIPE_LEVEL4.md (20.x).
"""

import ast
import inspect
import json
import operator
import random
import re

# [8.1] The registry, and what Python type hints are called in a schema.
TOOLS = {}  # tool name -> the function that runs it, filled in by @tool
TYPE_NAMES = {str: "string", int: "integer", float: "number", bool: "boolean"}

# [8.1] Patterns for reading tool calls out of a reply. (.*?) means "as
# little text as possible", and re.DOTALL lets "." match newlines too.
CALL_PATTERN = re.compile(r"<tool_call>(.*?)(?:</tool_call>|$)", re.DOTALL)
FUNCTION_PATTERN = re.compile(r"<function=([^>\s]+)>(.*?)(?:</function>|$)", re.DOTALL)
PARAMETER_PATTERN = re.compile(r"<parameter=([^>\s]+)>(.*?)</parameter>", re.DOTALL)

# [8.1] The arithmetic the calculator allows, and limits on powers, so that
# neither 9 ** 9 ** 9 nor (2 ** 1000) ** 1000 can freeze the app: the
# exponent may be at most LARGEST_POWER, and the answer at most
# LARGEST_RESULT_BITS binary digits long.
OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}
LARGEST_POWER = 1000
LARGEST_RESULT_BITS = 100_000  # underscores in a number are just for reading


def tool(function):
    """[8.2] Decorator: register function as a tool the model may call.

    How it works: writing @tool on the line above a def is the same as
    writing function = tool(function) after it. This puts the function in
    TOOLS under its own name and hands it back unchanged.
    """
    TOOLS[function.__name__] = function
    return function


def evaluate(node):
    """[8.3] Work out the value of one piece of a parsed arithmetic expression.

    How it works: ast.parse turns text like "2 * (3 + 4)" into a tree of
    nodes. A number is a leaf; an operation has one or two children. This
    function handles a node by first handling its children, calling itself
    (recursion), then applying the operator. Anything that is not a number
    or an allowed operator is refused, which is what makes it safe: unlike
    eval(), it can never run code. A power is checked before it is worked
    out: a whole number's bit_length() is how many binary digits it has,
    and a power has about that many times the exponent.
    """
    if isinstance(node, ast.Expression):
        return evaluate(node.body)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
        left = evaluate(node.left)
        right = evaluate(node.right)
        if isinstance(node.op, ast.Pow):
            result_bits = abs(int(left)).bit_length() * abs(right)
            if abs(right) > LARGEST_POWER or result_bits > LARGEST_RESULT_BITS:
                raise ValueError("that power is too large")
        return OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPERATORS:
        return OPERATORS[type(node.op)](evaluate(node.operand))
    raise ValueError("only numbers, brackets and + - * / // % ** are allowed")


# [8.4] The built-in tools. Their docstrings are what the model reads to
# decide when to use them, so these two carry no tag.
@tool
def calculate(expression: str) -> str:
    """Work out an arithmetic expression exactly, for example (17 * 23) + 4 / 2. Use it for any sum you are not certain of."""
    return str(evaluate(ast.parse(expression, mode="eval")))


@tool
def random_number(low: int, high: int) -> str:
    """Pick a random whole number between low and high, including both ends. Use it for dice rolls and random choices."""
    return str(random.randint(low, high))


def schema_for(function):
    """[8.5] Describe a function the way chat templates expect a tool described.

    How it works: inspect.signature lists the function's parameters with
    their type hints (the ": str" and ": int" after each name). Each becomes
    a property with a JSON type name. Parameters without a default value are
    required. The docstring becomes the description the model reads, so it
    should say when to use the tool.
    """
    properties = {}
    required = []
    for name, parameter in inspect.signature(function).parameters.items():
        properties[name] = {"type": TYPE_NAMES.get(parameter.annotation, "string")}
        if parameter.default is inspect.Parameter.empty:
            required.append(name)
    return {
        "type": "function",
        "function": {
            "name": function.__name__,
            "description": inspect.getdoc(function),
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def text_before_call(text):
    """[20.2] Return the part of a reply that comes before any tool call.

    How it works: Qwen-style models open a call with <tool_call>, so the
    text before that mark is ordinary text. Llama 3.2-style models use no
    mark: the call is the whole reply, written as JSON, so it starts with {
    (one call) or [ (a list of them). While such a reply is still arriving
    there is no telling whether it will turn out to be a call. It is
    treated as one, which means none of it is ordinary text yet;
    parse_tool_calls gives the final word once the reply is complete.
    """
    if text.lstrip()[:1] in ("{", "["):
        return ""
    return text.split("<tool_call>")[0]


def json_calls(text):
    """[20.3] Read every tool call that is written as JSON somewhere in text.

    How it works: a JSONDecoder's raw_decode reads one JSON value starting
    at a given position and reports where it ended, so whatever stands
    around the values (a closing tag, a ";" between two calls) does not
    matter. Every { and [ in the text is tried as the start of a value, and
    the ones that are not JSON are stepped over. A value on its own is
    handled as a list of one. An item counts as a call if it is an object
    with a name and arguments. Models do not agree on the keys: the name
    is under "name" or, now and then, "function", and the arguments are
    under "arguments" or "parameters", sometimes as JSON inside a string.
    """
    decoder = json.JSONDecoder()
    calls = []
    position = 0
    while position < len(text):
        if text[position] not in "{[":
            position = position + 1
            continue
        try:
            value, position = decoder.raw_decode(text, position)
        except ValueError:
            position = position + 1
            continue
        if isinstance(value, dict):
            value = [value]
        for item in value:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("function")
            arguments = item.get("arguments", item.get("parameters"))
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except ValueError:
                    continue
            if isinstance(name, str) and isinstance(arguments, dict):
                calls.append({"name": name, "arguments": arguments})
    return calls


def parse_tool_calls(text):
    """[20.4] (level 2: [8.6]) Split a reply into its text and its tool calls.

    How it works: text_before_call says where a call may start. In the rest
    of the reply, calls in Qwen3.5's style are looked for first: inside
    <tool_call>, a <function=name> with one <parameter=key>value</parameter>
    per argument. If there are none, json_calls looks for calls written as
    JSON, with or without <tool_call> around them. Both kinds are read into
    the same shape: a dictionary with "name" and "arguments". Values read
    from parameters are left as strings; Toolbox.run() converts them to the
    types the tool asks for. If no call can be read, the reply was ordinary
    text after all, however it began, so all of it is returned as text.
    """
    before = text_before_call(text)
    rest = text[len(before) :]
    calls = []
    for body in CALL_PATTERN.findall(rest):
        match = FUNCTION_PATTERN.search(body)
        if match:
            arguments = {}
            for key, value in PARAMETER_PATTERN.findall(match.group(2)):
                arguments[key] = value.strip("\n")
            calls.append({"name": match.group(1), "arguments": arguments})
    if not calls:
        calls = json_calls(rest)
    if not calls:
        return text.strip(), []
    return before.strip(), calls


def convert(value, type_name):
    """[8.7] Turn a value the model wrote into the type a tool asked for.

    How it works: a value read from <parameter=...> is always a string, but
    a tool may want a whole number, a decimal or true/false. Values that are
    already the right kind, or whose wanted type is unknown, pass through.
    """
    if not isinstance(value, str):
        return value
    if type_name == "integer":
        return int(value)
    if type_name == "number":
        return float(value)
    if type_name == "boolean":
        return value.strip().lower() == "true"
    if type_name in ("array", "object"):
        return json.loads(value)
    return value


class Toolbox:
    """[8.8] Every tool the model may call, built-in or from an MCP server.

    How it works: the toolbox keeps one list of tool descriptions (schemas)
    to hand to the chat template, and remembers who owns each tool: a Python
    function from TOOLS, or an MCP server. If two tools share a name, the
    first one wins and the second is left out, so the model is never offered
    two tools with the same name.
    """

    def __init__(self, servers):
        """[8.8.1] Gather the built-in tools, then each server's tools.

        How it works: servers is a list of connected MCP servers (it may be
        empty). Each one already holds the schemas of the tools it offers.
        """
        self.servers = servers
        self.schemas = []  # what the chat template is given
        self.owners = {}  # tool name -> its function or its server
        self.properties = {}  # tool name -> what each argument should be
        for function in TOOLS.values():
            self.add(schema_for(function), function)
        for server in servers:
            for schema in server.schemas:
                self.add(schema, server)

    def add(self, schema, owner):
        """[8.8.2] Add one tool, unless a tool with that name is already in."""
        name = schema["function"]["name"]
        if name in self.owners:
            return
        self.schemas.append(schema)
        self.owners[name] = owner
        parameters = schema["function"].get("parameters", {})
        self.properties[name] = parameters.get("properties", {})

    def run(self, name, arguments):
        """[8.8.3] Run the tool called name and return its result as text.

        How it works: each argument is converted to the type the tool's
        schema asks for. A built-in tool is a function, so it is called with
        the arguments unpacked as keywords (**arguments); a server is asked
        to run the tool. Any error is returned as text starting "Error:",
        because the model can read that and try again, while an exception
        would end the whole reply.
        """
        if name not in self.owners:
            return f"Error: there is no tool called {name}."
        try:
            wanted = self.properties[name]
            converted = {}
            for key, value in arguments.items():
                type_name = wanted.get(key, {}).get("type")
                converted[key] = convert(value, type_name)
            owner = self.owners[name]
            if callable(owner):
                return str(owner(**converted))
            return owner.call_tool(name, converted)
        except Exception as error:
            return f"Error: {error}"
