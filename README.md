# terminox

A terminal chat interface for local LLMs via [llama.cpp](https://github.com/ggerganov/llama.cpp)'s `llama-server`.

Features streaming responses, thinking block rendering, markdown output, session persistence, web/filesystem tools, and auto-compaction when context fills up.

> **Note:** This project is experimental and a personal side project. It is not intended for daily use or production environments. Expect rough edges.

---

## Requirements

- Linux (tested on CachyOS/Arch)
- Python 3.12+
- NVIDIA GPU with CUDA (for llama.cpp CUDA build)
- `cmake`, `gcc`/`g++`, `curl`
- A GGUF model file

---

## Installation

### 1. Clone terminox

```bash
git clone https://github.com/nawka12/terminox terminox
cd terminox
```

### 2. Run the install script

The script builds llama.cpp and sets up the Python environment:

```bash
bash install.sh
```

This will:
- Build `llama-server` from source at `llama.cpp/` (inside terminox)
- Create a `.venv` and install Python dependencies

> Skip the script and see [Manual Installation](#manual-installation) if you prefer.

### 3. Configure

Edit `config.sh` to point at your model and adjust inference parameters:

```bash
# Model
MODEL_ALIAS="my-model"
MODEL_PATH="/path/to/your/model.gguf"

# Network
HOST="127.0.0.1"
PORT=8002

# Inference
CTX_SIZE=8192
TEMP=1.0

# Optional: custom Jinja2 chat template
# TEMPLATE_PATH="/path/to/template.jinja"

# Optional: thinking-model flags (Qwen3, QwQ, DeepSeek-R1, etc.)
# REASONING_BUDGET=-1
# CHAT_TEMPLATE_KWARGS='{"enable_thinking":true}'
```

---

## Usage

### Start the server

```bash
bash start-terminox-server.sh          # start
bash start-terminox-server.sh stop     # stop
bash start-terminox-server.sh restart  # restart
bash start-terminox-server.sh status   # check status + VRAM usage
bash start-terminox-server.sh logs     # tail the log
```

### Start chatting

```bash
source .venv/bin/activate
python chat.py                   # new conversation
python chat.py --resume          # pick up a previous session
```

---

## Chat commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/system <text>` | Set or replace the system prompt |
| `/clear` | Clear history (keeps system prompt) |
| `/resume` | Load a previous session |
| `/think` | Toggle thinking block visibility |
| `/compact` | Manually summarise context |
| `/exit` | Save session and quit |
| `Ctrl+C` | Save session and quit |
| `Alt+Enter` | Insert newline (multi-line input) |

---

## Tools

The model can call these tools automatically:

| Tool | Description |
|------|-------------|
| `get_current_time` | Current local date and time |
| `search` | Web search via SearXNG |
| `scrape` | Fetch and extract text from a URL |
| `fetch_json` | Fetch a URL and return JSON |
| `read_file` | Read a local file (50 KB cap) |
| `write_file` | Write content to a local file |
| `list_dir` | List directory contents |
| `run_shell` | Run a shell command (blocklisted + confirmation required) |

### SearXNG

`search` requires a running [SearXNG](https://github.com/searxng/searxng) instance. Set the URL via environment variable (default: `http://localhost:8080`):

```bash
export TERMINOX_SEARXNG="http://localhost:8080"
```

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TERMINOX_HOST` | `127.0.0.1` | llama-server host |
| `TERMINOX_PORT` | `8002` | llama-server port |
| `TERMINOX_MODEL` | `qwen35-9b-ft` | Model alias sent in API requests |
| `TERMINOX_SEARXNG` | `http://localhost:8080` | SearXNG base URL |

---

## Sessions

Conversations are saved automatically on exit to:

```
~/.local/share/terminox/sessions/
```

Resume with `python chat.py --resume` to see a numbered menu of recent sessions.

---

## Running tests

```bash
source .venv/bin/activate
pytest
```

---

## Manual Installation

### llama.cpp

```bash
git clone https://github.com/ggerganov/llama.cpp llama.cpp
cd llama.cpp
cmake -B build -DGGML_CUDA=ON
cmake --build build --config Release -j$(nproc) --target llama-server
cp build/bin/llama-server .
cd ..
```

> Remove `-DGGML_CUDA=ON` for CPU-only inference (slow).

### Python environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```
