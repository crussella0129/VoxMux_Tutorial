"""The two ways VoxMux can run a model.

Both classes have the same shape: build one with a path to a model, then
call .chat(messages) to get the model's reply as a string. Because they
look identical from the outside, the UI never needs to know which one it has.
"""

MAX_NEW_TOKENS = 512
CONTEXT_SIZE = 4096


class LlamaCppBackend:
    """Runs a single .gguf file through llama.cpp."""

    def __init__(self, model_path):
        # Imported here, not at the top of the file, so the app still starts
        # if only one of the two libraries is installed.
        from llama_cpp import Llama

        self.llm = Llama(
            model_path=model_path,
            n_ctx=CONTEXT_SIZE,
            n_gpu_layers=-1,
            verbose=False,
        )

    def chat(self, messages):
        response = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=MAX_NEW_TOKENS,
        )
        reply = response["choices"][0]["message"]["content"]
        return reply.strip()


class TransformersBackend:
    """Runs a folder of safetensors weights through PyTorch."""

    def __init__(self, model_path):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if torch.cuda.is_available():
            self.device = "cuda"
        else:
            self.device = "cpu"

        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForCausalLM.from_pretrained(model_path, dtype="auto")
        self.model.to(self.device)

    def chat(self, messages):
        inputs = self.tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
        )
        inputs = inputs.to(self.device)

        output = self.model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS)

        # generate() returns the prompt followed by the reply, so slice the
        # prompt off the front and decode only what the model added.
        prompt_length = inputs["input_ids"].shape[1]
        new_tokens = output[0][prompt_length:]
        reply = self.tokenizer.decode(new_tokens, skip_special_tokens=True)
        return reply.strip()


def load_backend(kind, model_path):
    """Build the backend named by kind ("llama_cpp" or "pytorch")."""
    if kind == "llama_cpp":
        return LlamaCppBackend(model_path)
    if kind == "pytorch":
        return TransformersBackend(model_path)
    raise ValueError(f"Unknown backend: {kind}")
