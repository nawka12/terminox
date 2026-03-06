#!/usr/bin/env bash
# terminox updater — pulls latest llama.cpp and rebuilds, updates Python deps
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

# ── llama.cpp ─────────────────────────────────────────────────────────────────

if [[ ! -d "$LLAMA_DIR" ]]; then
    die "llama.cpp not found at $LLAMA_DIR — run install.sh first"
fi

info "Updating llama.cpp..."
BEFORE=$(git -C "$LLAMA_DIR" rev-parse HEAD)
git -C "$LLAMA_DIR" pull --ff-only
AFTER=$(git -C "$LLAMA_DIR" rev-parse HEAD)

if [[ "$BEFORE" == "$AFTER" ]]; then
    success "llama.cpp already up to date"
else
    success "llama.cpp updated ($(git -C "$LLAMA_DIR" log --oneline "$BEFORE..$AFTER" | wc -l) new commits)"

    if command -v nvcc &>/dev/null; then
        CMAKE_CUDA="-DGGML_CUDA=ON"
    else
        warn "nvcc not found — building CPU-only"
        CMAKE_CUDA=""
    fi

    info "Rebuilding llama-server..."
    cmake -B "$LLAMA_DIR/build" -S "$LLAMA_DIR" $CMAKE_CUDA -DCMAKE_BUILD_TYPE=Release
    cmake --build "$LLAMA_DIR/build" --config Release -j"$(nproc)" --target llama-server
    cp "$LLAMA_DIR/build/bin/llama-server" "$LLAMA_DIR/llama-server"
    success "llama-server rebuilt"
fi

# ── Python deps ───────────────────────────────────────────────────────────────

[[ -d "$VENV" ]] || die "venv not found at $VENV — run install.sh first"

info "Updating Python dependencies..."
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet --upgrade -r "$DIR/requirements.txt"
success "Python dependencies updated"

# ── done ──────────────────────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}Update complete!${RESET}"
echo ""
