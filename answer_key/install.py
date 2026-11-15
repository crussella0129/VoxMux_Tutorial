"""[1.2] install.py: install everything VoxMux needs, then check that it worked.

How it works: each install is one pip command, run by subprocess as a
separate program. Every command starts with sys.executable, the Python that
is running this script, so the libraries land exactly where that same
Python will look for them when it runs app.py. After the installs, three
NVIDIA files are copied from PyTorch's folder into llama.cpp's, and a fresh
Python is started to import everything and report whether the graphics card
is usable. Every step is safe to run again.

The numbers in square brackets match the step numbers in RECIPE.md.
"""

import pathlib
import shutil
import subprocess
import sys
import sysconfig

# [1.2.1] Constants. PIP is the start of every install command. STEPS holds
# the rest of each command, one list per library, in the order they install.
PIP = [sys.executable, "-m", "pip", "install"]
STEPS = [
    ["torch", "--index-url", "https://download.pytorch.org/whl/cu124"],
    ["transformers>=5"],
    [
        "--only-binary=llama-cpp-python",
        "llama-cpp-python==0.3.36",
        "--extra-index-url",
        "https://abetlen.github.io/llama-cpp-python/whl/cu124",
    ],
]
CUDA_FILES = ["cudart64_12.dll", "cublas64_12.dll", "cublasLt64_12.dll"]
CHECK = (
    "import tkinter, llama_cpp, torch, transformers; "
    "print(llama_cpp.__version__, torch.__version__, transformers.__version__, "
    "'cuda:', torch.cuda.is_available(), "
    "'llama gpu:', llama_cpp.llama_supports_gpu_offload())"
)


def install_libraries():
    """[1.2.2] Run one pip install per library, stopping at the first failure.

    How it works: PIP + step joins two lists into one, such as
    [python, "-m", "pip", "install", "transformers>=5"]. subprocess.run starts
    that program and waits for it to finish. check=True turns a failed
    install into an error that stops the script, instead of carrying on to
    the next library as if nothing had gone wrong.
    """
    for step in STEPS:
        subprocess.run(PIP + step, check=True)


def copy_cuda_files():
    """[1.2.3] Copy the three NVIDIA files llama.cpp needs from PyTorch.

    How it works: sysconfig says where this Python keeps its installed
    libraries (site-packages). Both libraries live there, each in its own
    folder, so the source and target folders are built from that one path
    with the / operator that pathlib provides.
    """
    site_packages = pathlib.Path(sysconfig.get_paths()["purelib"])
    source = site_packages / "torch" / "lib"
    target = site_packages / "llama_cpp" / "lib"
    for name in CUDA_FILES:
        shutil.copy(source / name, target)


def check():
    """[1.2.4] Import everything in a fresh Python and print what it finds.

    How it works: python -c runs the text in CHECK as a tiny program. It
    runs in a new process, the way app.py will, so it proves the libraries
    load from scratch rather than relying on anything this script did.
    """
    subprocess.run([sys.executable, "-c", CHECK], check=True)


def main():
    """[1.2.5] Install, copy, then check."""
    install_libraries()
    copy_cuda_files()
    check()


# [1.2.6] Run main only when this file is run directly.
if __name__ == "__main__":
    main()
