#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# ChangePilot Studio · first-time installer (macOS / Linux)
#
#   Run once after cloning the project:
#
#       chmod +x setup.sh
#       ./setup.sh            # standard setup
#       ./setup.sh --seed     # also seed the demo database
#       ./setup.sh --no-node  # skip npm install (backend only)
#
# What it does:
#   1. Checks that Python 3.11+ is available (prompts to install via pyenv if not)
#   2. Checks that Node 18+ is available  (prompts to install via nvm if not)
#   3. Creates backend/.venv and installs all Python deps
#   4. Runs npm install in frontend/
#   5. Creates backend/.env from .env.example (if absent)
#   6. Optionally seeds the demo database
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Colour helpers ────────────────────────────────────────────
CYAN='\033[0;36m' GREEN='\033[0;32m' YELLOW='\033[1;33m'
RED='\033[0;31m' GRAY='\033[0;90m' RESET='\033[0m'
banner()  { echo; echo -e "${CYAN}=== $* ===${RESET}"; }
ok()      { echo -e "${GREEN}  [OK]  ${RESET}$*"; }
info()    { echo -e "${CYAN}   >   ${RESET}$*"; }
warn()    { echo -e "${YELLOW}  [!]  ${RESET}$*"; }
fail()    { echo -e "${RED}  [X]  ${RESET}$*"; exit 1; }
gray()    { echo -e "${GRAY}        $*${RESET}"; }

# ── Args ─────────────────────────────────────────────────────
DO_SEED=false
SKIP_NODE=false
for arg in "$@"; do
  case "$arg" in
    --seed)    DO_SEED=true ;;
    --no-node) SKIP_NODE=true ;;
    -h|--help)
      echo "Usage: ./setup.sh [--seed] [--no-node]"
      echo "  --seed     Seed the demo database after setup"
      echo "  --no-node  Skip Node.js / npm install (backend only)"
      exit 0 ;;
  esac
done

# ── Paths ─────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"
VENV_PY="$VENV_DIR/bin/python"
ENV_FILE="$BACKEND_DIR/.env"
ENV_EXAMPLE="$BACKEND_DIR/.env.example"

banner "ChangePilot Studio · first-time setup (macOS / Linux)"
gray "Project root: $SCRIPT_DIR"

# ─────────────────────────────────────────────────────────────
# STEP 1 · Python 3.11+
# ─────────────────────────────────────────────────────────────
banner "Step 1/4 · Verify Python 3.11+"

PYTHON_CMD=""
for candidate in python3.13 python3.12 python3.11 python3 python; do
  if command -v "$candidate" &>/dev/null; then
    ver=$("$candidate" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
    major=$(echo "$ver" | cut -d. -f1)
    minor=$(echo "$ver" | cut -d. -f2)
    if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
      PYTHON_CMD="$candidate"
      ok "Using $candidate (Python $ver)"
      break
    fi
  fi
done

if [ -z "$PYTHON_CMD" ]; then
  fail "Python 3.11+ not found. Fix options:
  • Homebrew:  brew install python@3.12
  • pyenv:     pyenv install 3.12.4 && pyenv global 3.12.4
  • Official:  https://www.python.org/downloads/macos/"
fi

# ─────────────────────────────────────────────────────────────
# STEP 2 · Virtual environment + Python deps
# ─────────────────────────────────────────────────────────────
banner "Step 2/4 · Create Python virtual environment"

if [ -d "$VENV_DIR" ]; then
  gray "venv already exists at $VENV_DIR · keeping"
else
  info "Creating venv at $VENV_DIR ..."
  "$PYTHON_CMD" -m venv "$VENV_DIR"
  ok "venv created"
fi

info "Upgrading pip..."
"$VENV_PY" -m pip install --upgrade pip --quiet

info "Installing project dependencies (first run: ~3-5 min) ..."
pushd "$BACKEND_DIR" > /dev/null
"$VENV_PY" -m pip install -e ".[dev]" --quiet
popd > /dev/null
ok "Python deps installed"

# ─────────────────────────────────────────────────────────────
# STEP 3 · Node.js check
# ─────────────────────────────────────────────────────────────
banner "Step 3/4 · Verify Node.js 18+"

NODE_OK=false
if ! $SKIP_NODE; then
  # Load nvm if present but not on PATH yet
  NVM_SH="${NVM_DIR:-$HOME/.nvm}/nvm.sh"
  [ -s "$NVM_SH" ] && source "$NVM_SH"

  if command -v node &>/dev/null; then
    NODE_VER=$(node --version | grep -oE '[0-9]+' | head -1)
    if [ "$NODE_VER" -ge 18 ]; then
      ok "Node $(node --version) found"
      NODE_OK=true
    else
      warn "Node $(node --version) is too old (need 18+). The React UI will be skipped."
      warn "Install via nvm:  nvm install 20 && nvm use 20"
    fi
  else
    warn "Node.js not found. The React UI will be skipped."
    warn "Install options:"
    warn "  • nvm (recommended): curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash"
    warn "                       source ~/.nvm/nvm.sh && nvm install 20 && nvm use 20"
    warn "  • Homebrew:          brew install node@20"
    warn "  • Official:          https://nodejs.org/en/download"
  fi
fi

# ─────────────────────────────────────────────────────────────
# STEP 4 · npm install
# ─────────────────────────────────────────────────────────────
if $NODE_OK && ! $SKIP_NODE; then
  banner "Step 4/4 · Install frontend dependencies (npm install)"
  pushd "$FRONTEND_DIR" > /dev/null
  if [ -d "node_modules" ]; then
    gray "node_modules exists · running npm install (will update if needed)"
  else
    info "Installing fresh (~1-2 min) ..."
  fi
  npm install --silent
  ok "npm deps installed"
  popd > /dev/null
else
  banner "Step 4/4 · Skipped (no Node or --no-node flag)"
fi

# ─────────────────────────────────────────────────────────────
# .env bootstrap
# ─────────────────────────────────────────────────────────────
banner "Environment file"
if [ -f "$ENV_FILE" ]; then
  ok ".env already exists · leaving untouched"
else
  if [ -f "$ENV_EXAMPLE" ]; then
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    ok ".env created from .env.example"
    warn "Edit backend/.env to fill in your credentials before starting:"
    gray "  DATABRICKS_HOST    → your Azure Databricks workspace URL"
    gray "  DATABRICKS_TOKEN   → dapi-... personal access token"
    gray "  GITHUB_TOKEN       → ghp_... for PR comment posting"
  else
    warn ".env.example not found · you'll need to create backend/.env manually"
  fi
fi

# ─────────────────────────────────────────────────────────────
# Optional seed
# ─────────────────────────────────────────────────────────────
if $DO_SEED; then
  banner "Bonus · Seeding demo data"
  "$VENV_PY" "$BACKEND_DIR/scripts/seed_demo.py"
  ok "Demo data seeded"
fi

# ─────────────────────────────────────────────────────────────
# Done
# ─────────────────────────────────────────────────────────────
banner "Setup complete"
echo ""
echo -e "${GREEN}Next steps:${RESET}"
echo "  1. Edit backend/.env with your Databricks + GitHub credentials"
echo "  2. Start the app:        ./start.sh"
echo "  3. Open the UI:          http://127.0.0.1:5173"
echo "  4. Open the API docs:    http://127.0.0.1:8000/docs"
echo ""
echo -e "${GRAY}Verify the content layer:${RESET}"
echo "  $VENV_PY Tests/consistency/consistency_tests.py"
echo ""
