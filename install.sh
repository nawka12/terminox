#!/usr/bin/env bash
# terminox installer — builds llama-server and sets up Python venv
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
LLAMA_DIR="$DIR/llama.cpp"
VENV="$DIR/.venv"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
RESET='\033[0m'

info()    { echo -e "${GREEN}▸ $*${RESET}"; }
warn()    { echo -e "${YELLOW}⚠ $*${RESET}"; }
die()     { echo -e "${RED}✗ $*${RESET}" >&2; exit 1; }
success() { echo -e "${GREEN}✓ $*${RESET}"; }

# ── check dependencies ────────────────────────────────────────────────────────

info "Checking dependencies..."

command -v python3 &>/dev/null || die "python3 not found"
command -v cmake   &>/dev/null || die "cmake not found — install with: sudo pacman -S cmake"
command -v git     &>/dev/null || die "git not found"
command -v curl    &>/dev/null || die "curl not found"

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [[ "$PYTHON_MAJOR" -lt 3 || ("$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -lt 12) ]]; then
    die "Python 3.12+ required (found $PYTHON_VERSION)"
fi
success "Python $PYTHON_VERSION"

# Check for CUDA (optional — warn, don't abort)
if command -v nvcc &>/dev/null; then
    CUDA_VERSION=$(nvcc --version | grep -oP 'release \K[0-9.]+')
    success "CUDA $CUDA_VERSION found — will build with GPU support"
    CMAKE_CUDA="-DGGML_CUDA=ON"
else
    warn "nvcc not found — building CPU-only (slow for large models)"
    CMAKE_CUDA=""
fi

# ── config ────────────────────────────────────────────────────────────────────

if [[ ! -f "$DIR/config.sh" ]]; then
    cp "$DIR/config.example.sh" "$DIR/config.sh"
    warn "Created config.sh from config.example.sh — edit it to set your model path"
fi

# ── llama.cpp ─────────────────────────────────────────────────────────────────

if [[ -f "$LLAMA_DIR/llama-server" ]]; then
    success "llama-server already exists at $LLAMA_DIR/llama-server — skipping build"
else
    if [[ ! -d "$LLAMA_DIR" ]]; then
        info "Cloning llama.cpp to $LLAMA_DIR..."
        git clone https://github.com/ggerganov/llama.cpp "$LLAMA_DIR"
    else
        info "llama.cpp directory exists, updating..."
        git -C "$LLAMA_DIR" pull --ff-only
    fi

    info "Building llama-server (this may take a few minutes)..."
    cmake -B "$LLAMA_DIR/build" -S "$LLAMA_DIR" $CMAKE_CUDA -DCMAKE_BUILD_TYPE=Release
    cmake --build "$LLAMA_DIR/build" --config Release -j"$(nproc)" --target llama-server
    cp "$LLAMA_DIR/build/bin/llama-server" "$LLAMA_DIR/llama-server"
    success "llama-server built"
fi

# ── Python venv ───────────────────────────────────────────────────────────────

if [[ ! -d "$VENV" ]]; then
    info "Creating Python virtual environment..."
    python3 -m venv "$VENV"
fi

info "Installing Python dependencies..."
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$DIR/requirements-dev.txt"
success "Python dependencies installed"

# ── verify ────────────────────────────────────────────────────────────────────

info "Running tests..."
cd "$DIR" && "$VENV/bin/pytest" -q

# ── done ──────────────────────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}Installation complete!${RESET}"
echo ""
echo "  1. Edit config.sh to set your model path"
echo "  2. Start the server:  bash start-terminox-server.sh"
echo "  3. Start chatting:    source .venv/bin/activate && python chat.py"
echo ""
