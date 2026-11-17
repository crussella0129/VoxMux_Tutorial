# VoxMux
The Local AI Multiplexer - chat with a model via llama.cpp or pytorch (directly from safetensor or gguf), without a browser

This repository is the tutorial: build the app yourself, step by step. The finished app, with minimal comments and ready to use, is at [crussella0129/VoxMux](https://github.com/crussella0129/VoxMux).

## The four levels

Each level is a recipe in words, with no finished code in it, and an answer key to compare against. Numbered tags tie every step of a recipe to the lines of the answer key it describes.

| Level | Recipe | Answer key | What you build |
| --- | --- | --- | --- |
| 1 | [`RECIPE.md`](RECIPE.md) | [`answer_key/`](answer_key/) | Streaming chat, system prompt, temperature, thinking mode, and maximum context with trimming. |
| 2 | [`RECIPE_LEVEL2.md`](RECIPE_LEVEL2.md) | [`answer_key_level2/`](answer_key_level2/) | Compaction, tool calling, and an MCP client and server. |
| 3 | [`RECIPE_LEVEL3.md`](RECIPE_LEVEL3.md) | [`answer_key_level3/`](answer_key_level3/) | A Stop button, a New chat button, saved settings, and asking before an MCP tool runs. |
| 4 | [`RECIPE_LEVEL4.md`](RECIPE_LEVEL4.md) | [`answer_key_level4/`](answer_key_level4/) | Saved conversations, switching models mid-chat, models other than Qwen, and MCP servers that will not stop. |

To run an answer key, install with `python answer_key/install.py` (Step 1 of the recipe), then `python answer_key/app.py`. You need Windows, an NVIDIA graphics card and Python 3.13.

Levels 1 to 3 were written and tested with Qwen3.5 models only. Level 4 was also run with Llama 3.2, Mistral 7B, Gemma 3, Phi-4-mini, Hermes 3, DeepSeek R1 and SmolLM2, and with four MCP servers written by other people; its recipe says what each one did.

## Checking your own copy

```bash
python check_my_build.py my_build
```

This runs the tests below on the folder you are writing. It needs no model and no graphics card, skips files you have not written yet, and names the recipe steps each test checks.

## Tests

```bash
python -m unittest discover -s tests
```

The tests in [`tests/`](tests/) check all four answer keys in about two minutes. They open the real window and drive it with a scripted stand-in for the model, so they need no graphics card, and they run on GitHub on every change. The tests of the PyTorch backend run only where PyTorch is installed; they use an 80 KB random model in `tests/tiny_model/`.

[`tests/real_model.py`](tests/real_model.py) is the one test that needs a real model. Run it by hand: `python tests/real_model.py answer_key_level4 llama_cpp C:\models\Qwen3.5-4B-Q8_0.gguf`. It works with any model: what does not depend on the model is checked strictly, and what does is only reported.

## How the app repository is made

The app repository is generated from this one, never edited by hand:

```bash
python tools/make_app.py ../VoxMux
```

[`tools/make_app.py`](tools/make_app.py) takes `answer_key_level4/`, cuts every tagged docstring down to its first line, removes the comments, and adds the files in [`tools/app_extras/`](tools/app_extras/). It checks that nothing but docstrings and comments changed. It also writes a `SOURCE` file naming the commit of this repository it worked from.

The same input always gives the same bytes. On every push, the app repository checks out the commit named in `SOURCE`, runs `make_app.py --check`, and fails if any file differs. So the app can always be traced to one exact version of the tutorial.

To change the app: change `answer_key_level4/` (and its recipe), commit and push here, run the command above, then commit and push the app.
