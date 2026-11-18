# VoxMux

The Local AI Multiplexer: a desktop chat app for running local models through llama.cpp (GGUF files) or PyTorch (safetensors folders), without a browser.

Want to build it yourself, line by line? See the step-by-step tutorial at [VoxMux_Tutorial](https://github.com/crussella0129/VoxMux_Tutorial). This repository is the finished app.

**Written for Qwen3.5 models** (0.8B, 2B and 4B, on an RTX 2080 Ti), and also run with Llama 3.2, Mistral 7B, Gemma 3, Phi-4-mini, Hermes 3, DeepSeek R1 and SmolLM2. Chatting, the system prompt, Stop, saved conversations and compaction worked with all of them. Tool calling needs a model whose chat template describes tools: of these, Qwen3.5 and Llama 3.2. With any other model the status line says "This model's template has no place for tools." and the model simply answers. Thinking mode can only be switched on and off for Qwen; other models think aloud if your thinking instructions persuade them to, and DeepSeek R1 always thinks.

## Features

- **Two backends:** llama.cpp for a `.gguf` file, or PyTorch (Hugging Face transformers) for a folder of `.safetensors` weights.
- **Streaming replies,** shown as the model writes them, with a **Stop** button to cut one short.
- **System prompt and temperature** controls.
- **Thinking mode,** with your own thinking instructions. Reasoning is marked off from the answer.
- **A context sized to your graphics card.** The app asks for the model's full trained context, up to 32,768 tokens, and halves it until the model loads and leaves the card some room to work in.
- **Compaction.** When a conversation outgrows the context, older messages are summarised by the model rather than dropped.
- **Tool calling.** The model gets an exact calculator and a random-number tool. Calls are read in Qwen's `<tool_call>` style and in the bare JSON style of Llama 3.2.
- **An MCP client.** Any [Model Context Protocol](https://modelcontextprotocol.io) server listed in `mcp_servers.json` adds its tools. A small demo server, with a clock and a notes file, is included.
- **You approve MCP tools.** The first time the model wants to run a tool from an MCP server, the app asks: Allow once, Always allow, or Deny.
- **Conversations are saved.** Each one is written to a file in the `chats` folder after every reply. **Open chat** brings one back, and the one you had open returns when the app starts.
- **Switch models in the middle of a chat.** Loading another model keeps the conversation, and the first model is unloaded before the second loads, so the two need not fit in memory together.
- **Settings are remembered.** The backend, model path, temperature, thinking mode, system prompt and allowed tools are saved in `settings.json` when you close the window.

## Requirements

- Windows
- An NVIDIA graphics card with a current driver
- Python 3.13

## Install

```bash
python install.py
```

This installs the CUDA builds of PyTorch and llama-cpp-python, transformers and tzdata into the Python you ran it with, then copies three CUDA runtime files that llama.cpp needs. It ends by checking that both libraries can see the graphics card. You should see `cuda: True llama gpu: True`. It is safe to run again.

There is no `requirements.txt`. A plain `pip install` of these libraries on Windows fetches the CPU-only PyTorch and tries to compile llama-cpp-python from source, so `install.py` is the one place the dependencies are listed.

## Run

```bash
python app.py
```

1. Pick **llama.cpp** or **PyTorch**.
2. Click **Browse** to choose a `.gguf` file or a model folder.
3. Click **Load**, and wait for the status line to say **Ready**.
4. Type a message and press Enter. **Stop** cuts the reply short, **New chat** starts again, and **Open chat** brings back a saved conversation.

## MCP servers

`mcp_servers.json` uses the same `mcpServers` layout as other MCP clients:

```json
{
  "mcpServers": {
    "demo": {"command": "python", "args": ["demo_mcp_server.py"]}
  }
}
```

Servers start when the first model loads and stop when the window closes. Each server's error output goes to `mcp-<name>.log`. An MCP server runs with your permissions and is given your environment variables, so only add servers you trust.

Besides the included demo server, the client has been run with four official servers: `mcp-server-time` (through `uvx`), and `@modelcontextprotocol/server-filesystem`, `server-memory` and `server-everything` (through `npx`). For example:

```json
{
  "mcpServers": {
    "time": {"command": "uvx", "args": ["mcp-server-time"]}
  }
}
```

## Files

| File | What it is |
| --- | --- |
| `app.py` | The window, the worker threads and the tool-calling loop. |
| `backends.py` | The llama.cpp and PyTorch backends, plus context trimming and compaction. |
| `tools.py` | The built-in tools, tool-call parsing, and the toolbox. |
| `mcp_client.py` | Starts MCP servers and talks JSON-RPC to them. |
| `demo_mcp_server.py` | The demo MCP server. |
| `install.py` | Installs the dependencies. |
| `SOURCE` | The tutorial commit these files were made from. |

## This repository is generated

Nothing here is edited by hand. Every file is written by [`tools/make_app.py`](https://github.com/crussella0129/VoxMux_Tutorial/blob/@@COMMIT@@/tools/make_app.py) in the tutorial repository, from the tutorial's [`answer_key_level4/`](https://github.com/crussella0129/VoxMux_Tutorial/tree/@@COMMIT@@/answer_key_level4) with the teaching text removed. `SOURCE` names the exact tutorial commit, and a check on every push rebuilds the files from that commit and fails if anything differs.

To change the app, change the tutorial, then run this from the tutorial folder:

```bash
python tools/make_app.py ../VoxMux
```

To check a copy yourself, check out the tutorial at the commit in `SOURCE` and run:

```bash
python tools/make_app.py --check ../VoxMux
```

## License

MIT
