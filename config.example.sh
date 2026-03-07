# terminox configuration
# Edit this file to change model, paths, and inference parameters.

# Network
HOST="127.0.0.1"
PORT=8002

# Model
MODEL_ALIAS="my-model"
MODEL_PATH="/path/to/your/model.gguf"

# Paths (relative to script directory)
SERVER_PATH="llama.cpp/llama-server"
TEMPLATE_PATH=""   # optional: path to a custom Jinja2 chat template

# Inference parameters
CTX_SIZE=8192
TEMP=1.0
TOP_P=0.95
TOP_K=40
MIN_P=0.0
PRESENCE_PENALTY=0.0
FLASH_ATTN=on
CACHE_TYPE_K=f16
CACHE_TYPE_V=f16

# Thinking-model options (uncomment for models like Qwen3, QwQ, DeepSeek-R1)
# REASONING_BUDGET=-1
# CHAT_TEMPLATE_KWARGS='{"enable_thinking":true}'

# Startup wait: STARTUP_ITERS * STARTUP_SLEEP seconds = max wait
STARTUP_ITERS=90
STARTUP_SLEEP=2
