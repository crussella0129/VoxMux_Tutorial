# VoxMux
The Local AI Multiplexer - chat with a model via llama.cpp or pytorch (directly from safetensor or gguf), without a browser

## Layout

- [`RECIPE.md`](RECIPE.md): level 1, step-by-step instructions in words for writing the app by hand as a Python exercise: streaming chat, system prompt, temperature, thinking mode, and maximum context with trimming.
- [`answer_key/`](answer_key/): the finished level 1 app to compare against. Install with Step 1 of the recipe, then `python answer_key/app.py`.
- [`RECIPE_LEVEL2.md`](RECIPE_LEVEL2.md): level 2, built on top of level 1: compaction, tool calling, and an MCP client and server.
- [`answer_key_level2/`](answer_key_level2/): the finished level 2 app.
