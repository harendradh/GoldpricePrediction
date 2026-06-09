#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# ChangePilot Studio · one-command launcher (macOS / Linux)
#
#   ./start.sh                 start backend + React UI
#   ./start.sh --backend       backend only
#   ./start.sh --frontend      React UI only (backend must already be running)
#   ./start.sh --install       install python + npm deps then exit
#   ./start.sh --test          run pytest then exit
#   ./start.sh --stop          stop running servers
#   ./start.sh --clean         drop .venv + node_modules + atlas.db
#   ./start.sh --backend-port 9000   override backend port (default 8000)
#   ./start.sh --frontend-port 3000  override frontend port (default 5173)
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Colour helpers ────────────────────────────────────────────
CYAN='\033[0;36m' GREEN='\033[0;32m' YELLOW='\033[1;33m'
RED='\033[0;31m' GRAY='\033[0;90m' RESET='\033[0m'
banner() { echo; echo -e "${GRAY}--- $* ---${RESET}"; }
ok()     { echo -e "${GREEN}  [OK]  ${RESET}$*"; }
info()   { echo -e "${CYAN}   >   ${RESET}$*"; }
warn()   { echo -e "${YELLOW}  [!]  ${RESET}$*"; }
fail()   { echo -e "${RED}  [X]  ${RESET}$*"; exit 1; }

# ── Paths ─────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"
VENV_PY="$VENV_DIR/bin/python"
ENV_FILE="$BACKEND_DIR/.env"
ENV_EXAMPLE="$BACKEND_DIR/.env.example"
PID_FILE="$SCRIPT_DIR/.changepilot.pids"

# ── Default options ───────────────────────────────────────────
DO_BACKEND=false
DO_FRONTEND=false
DO_INSTALL=false
DO_TEST=false
DO_STOP=false
DO_CLEAN=false
BACKEND_PORT=8000
FRONTEND_PORT=5173

# ── Arg parse ─────────────────────────────────────────────────
i=1
while [ $i -le $# ]; do
  arg="${!i}"
  case "$arg" in
    --backend)       DO_BACKEND=true ;;
    --frontend)      DO_FRONTEND=true ;;
    --install)       DO_INSTALL=true ;;
    --test)          DO_TEST=true ;;
    --stop)          DO_STOP=true ;;
    --clean)         DO_CLEAN=true ;;
    --backend-port)  i=$((i+1)); BACKEND_PORT="${!i}" ;;
    --frontend-port) i=$((i+1)); FRONTEND_PORT="${!i}" ;;
    -h|--help)
      head -20 "$0" | grep "^#"
      exit 0 ;;
  esac
  i=$((i+1))
done

# If neither --backend nor --frontend is given, start both
if ! $DO_BACKEND && ! $DO_FRONTEND; then
  DO_BACKEND=true
  DO_FRONTEND=true
fi

# ─────────────────────────────────────────────────────────────
# STOP
# ─────────────────────────────────────────────────────────────
stop_servers() {
  banner "Stopping ChangePilot Studio"
  if [ -f "$PID_FILE" ]; then
    while IFS= read -r pid; do
      if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null && info "stopped PID $pid"
      fi
    done < "$PID_FILE"
    rm -f "$PID_FILE"
    ok "done"
  else
    # Fallback: grep for uvicorn + vite processes owned by this user
    FOUND=0
    for pid in $(pgrep -f "uvicorn app.main" 2>/dev/null || true); do
      kill "$pid" 2>/dev/null && info "stopped uvicorn PID $pid" && FOUND=$((FOUND+1))
    done
    for pid in $(pgrep -f "vite.*$FRONTEND_PORT" 2>/dev/null || true); do
      kill "$pid" 2>/dev/null && info "stopped vite PID $pid" && FOUND=$((FOUND+1))
    done
    if [ $FOUND -eq 0 ]; then info "no running ChangePilot processes found"; else ok "$FOUND process(es) stopped"; fi
  fi
}

if $DO_STOP; then stop_servers; exit 0; fi

# ─────────────────────────────────────────────────────────────
# CLEAN
# ─────────────────────────────────────────────────────────────
if $DO_CLEAN; then
  stop_servers
  banner "Cleaning .venv + node_modules + atlas.db"
  [ -d "$VENV_DIR" ] && rm -rf "$VENV_DIR" && ok ".venv removed"
  [ -d "$FRONTEND_DIR/node_modules" ] && rm -rf "$FRONTEND_DIR/node_modules" && ok "node_modules removed"
  [ -f "$BACKEND_DIR/atlas.db" ] && rm -f "$BACKEND_DIR/atlas.db" && ok "atlas.db removed"
  exit 0
fi

# ─────────────────────────────────────────────────────────────
# Python check
# ─────────────────────────────────────────────────────────────
banner "ChangePilot Studio launcher"

PYTHON_CMD=""
for candidate in python3.13 python3.12 python3.11 python3 python; do
  if command -v "$candidate" &>/dev/null; then
    ver=$("$candidate" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
    major=$(echo "$ver" | cut -d. -f1)
    minor=$(echo "$ver" | cut -d. -f2)
    if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
      PYTHON_CMD="$candidate"
      break
    fi
  fi
done
[ -z "$PYTHON_CMD" ] && fail "Python 3.11+ not found. Run ./setup.sh first."
info "Python: $($PYTHON_CMD --version 2>&1)"

# ─────────────────────────────────────────────────────────────
# .env bootstrap
# ─────────────────────────────────────────────────────────────
if [ ! -f "$ENV_FILE" ]; then
  if [ -f "$ENV_EXAMPLE" ]; then
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    ok ".env created from .env.example"
    warn "Edit backend/.env — fill in DATABRICKS_HOST, DATABRICKS_TOKEN, GITHUB_TOKEN"
  else
    fail ".env.example missing · run ./setup.sh first"
  fi
else
  ok ".env present"
fi

# ─────────────────────────────────────────────────────────────
# venv + Python deps
# ─────────────────────────────────────────────────────────────
if [ ! -f "$VENV_PY" ]; then
  banner "Creating virtual environment"
  "$PYTHON_CMD" -m venv "$VENV_DIR"
  ok ".venv created"
fi

check_py_deps() {
  "$VENV_PY" -c "import fastapi, sqlalchemy, yaml, structlog, httpx; print('ok')" 2>/dev/null | grep -q "^ok$"
}

if $DO_INSTALL || ! check_py_deps; then
  banner "Installing backend dependencies (~3-5 min first run)"
  pushd "$BACKEND_DIR" > /dev/null
  "$VENV_PY" -m pip install --upgrade pip --quiet
  "$VENV_PY" -m pip install -e ".[dev]" --quiet
  popd > /dev/null
  check_py_deps && ok "Python deps installed" || fail "Dependency install failed — run: cd backend && $VENV_PY -m pip install -e .[dev]"
fi

# ─────────────────────────────────────────────────────────────
# Node + npm
# ─────────────────────────────────────────────────────────────
# Load nvm if present but not on PATH
NVM_SH="${NVM_DIR:-$HOME/.nvm}/nvm.sh"
[ -s "$NVM_SH" ] && source "$NVM_SH"

NODE_OK=false
if command -v node &>/dev/null; then
  NODE_VER=$(node --version | grep -oE '[0-9]+' | head -1)
  if [ "$NODE_VER" -ge 18 ]; then
    info "Node $(node --version) / npm $(npm --version)"
    NODE_OK=true
  else
    warn "Node $(node --version) is too old (need 18+) — UI will be skipped"
  fi
else
  warn "Node not found — UI will be skipped. Run ./setup.sh to install."
fi

if $NODE_OK && [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  banner "Installing frontend dependencies"
  pushd "$FRONTEND_DIR" > /dev/null
  npm install --silent
  ok "npm deps installed"
  popd > /dev/null
fi

if $DO_INSTALL; then
  ok "Install complete"; exit 0
fi

# ─────────────────────────────────────────────────────────────
# TESTS
# ─────────────────────────────────────────────────────────────
if $DO_TEST; then
  banner "Running pytest"
  pushd "$BACKEND_DIR" > /dev/null
  "$VENV_PY" -m pytest -v
  popd > /dev/null
  exit 0
fi

# ─────────────────────────────────────────────────────────────
# Start helpers
# ─────────────────────────────────────────────────────────────
rm -f "$PID_FILE"

wait_for_http() {
  local url="$1" label="$2" max="${3:-90}"
  for i in $(seq 1 $max); do
    if curl -sf "$url" -o /dev/null --connect-timeout 1 --max-time 2 2>/dev/null; then
      ok "$label is up (${i}s)"
      return 0
    fi
    sleep 1
    # On first-run, 17 skills load ~8-10s — let user know it's normal
    if [ "$i" -eq 15 ]; then info "still starting... (skill registry loading — normal on first boot)"; fi
  done
  warn "$label did not respond after ${max}s — check logs: tail -50 $SCRIPT_DIR/backend.log"
}

# ─────────────────────────────────────────────────────────────
# BACKEND
# ─────────────────────────────────────────────────────────────
if $DO_BACKEND; then
  banner "Starting backend on http://127.0.0.1:$BACKEND_PORT"
  LOG_FILE="$SCRIPT_DIR/backend.log"
  export PYTHONPATH="$SCRIPT_DIR"
  pushd "$BACKEND_DIR" > /dev/null
  "$VENV_PY" -m uvicorn app.main:app \
    --host 127.0.0.1 --port "$BACKEND_PORT" --reload \
    >> "$LOG_FILE" 2>&1 &
  BACKEND_PID=$!
  echo "$BACKEND_PID" >> "$PID_FILE"
  info "backend PID $BACKEND_PID  (logs → $LOG_FILE)"
  popd > /dev/null
  wait_for_http "http://127.0.0.1:$BACKEND_PORT/health" "Backend"
fi

# ─────────────────────────────────────────────────────────────
# FRONTEND
# ─────────────────────────────────────────────────────────────
if $DO_FRONTEND; then
  if ! $NODE_OK; then
    warn "Skipping frontend: Node not available"
  else
    banner "Starting React frontend on http://127.0.0.1:$FRONTEND_PORT"
    LOG_FILE="$SCRIPT_DIR/frontend.log"
    pushd "$FRONTEND_DIR" > /dev/null
    npm run dev -- --port "$FRONTEND_PORT" --host 127.0.0.1 \
      >> "$LOG_FILE" 2>&1 &
    FRONTEND_PID=$!
    echo "$FRONTEND_PID" >> "$PID_FILE"
    info "frontend PID $FRONTEND_PID  (logs → $LOG_FILE)"
    popd > /dev/null
    wait_for_http "http://127.0.0.1:$FRONTEND_PORT" "React UI" 60
  fi
fi

# ─────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────
banner "ChangePilot Studio is running"
echo ""
if $DO_BACKEND; then
  echo -e "  ${GREEN}Backend API${RESET}  →  http://127.0.0.1:$BACKEND_PORT/docs   (Swagger)"
fi
if $DO_FRONTEND && $NODE_OK; then
  echo -e "  ${GREEN}React UI   ${RESET}  →  http://127.0.0.1:$FRONTEND_PORT/"
fi
echo ""
echo -e "  Stop:       ${CYAN}./start.sh --stop${RESET}"
echo -e "  Tests:      ${CYAN}./start.sh --test${RESET}"
echo -e "  Clean:      ${CYAN}./start.sh --clean${RESET}"
echo -e "  Backend log:  tail -f backend.log"
echo -e "  Frontend log: tail -f frontend.log"
echo ""

# ─────────────────────────────────────────────────────────────
# Keep alive (Ctrl-C to stop)
# ─────────────────────────────────────────────────────────────
cleanup() {
  echo ""
  banner "Shutting down (Ctrl-C received)"
  stop_servers
}
trap cleanup INT TERM

info "Press Ctrl-C to stop all servers"
wait
