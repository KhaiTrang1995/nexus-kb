#!/usr/bin/env bash
# deploy.sh — Local dev stack deployment for nexus-kb
# Usage: ./scripts/deploy.sh [--no-ui] [--no-migrate] [--api-only]
#
# Flags:
#   --no-ui        Skip web console build
#   --no-migrate   Skip Alembic migrations
#   --api-only     Start API only (skip Docker storage startup)

set -euo pipefail

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; NC='\033[0m'; BOLD='\033[1m'

log_step() { echo -e "\n${CYAN}${BOLD}▶ $1${NC}"; }
log_ok()   { echo -e "${GREEN}✔ $1${NC}"; }
log_warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
log_err()  { echo -e "${RED}✘ $1${NC}"; exit 1; }

# ── Parse flags ───────────────────────────────────────────────────────────────
SKIP_UI=false
SKIP_MIGRATE=false
API_ONLY=false
for arg in "$@"; do
  case "$arg" in
    --no-ui)       SKIP_UI=true ;;
    --no-migrate)  SKIP_MIGRATE=true ;;
    --api-only)    API_ONLY=true ;;
    --help|-h)
      echo "Usage: ./scripts/deploy.sh [--no-ui] [--no-migrate] [--api-only]"
      exit 0
      ;;
    *) log_warn "Unknown flag: $arg" ;;
  esac
done

# ── Repo root detection ────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"
echo -e "${BOLD}nexus-kb deploy${NC} — root: $REPO_ROOT"

# ── Prerequisite checks ───────────────────────────────────────────────────────
log_step "Checking prerequisites"
for cmd in python3 pip docker; do
  if ! command -v "$cmd" &>/dev/null; then
    log_err "$cmd is not installed or not on PATH"
  fi
  log_ok "$cmd found"
done

if ! $SKIP_UI; then
  for cmd in node npm; do
    if ! command -v "$cmd" &>/dev/null; then
      log_warn "$cmd not found — skipping web console build (use --no-ui to suppress this warning)"
      SKIP_UI=true
      break
    fi
  done
fi

# ── .env setup ────────────────────────────────────────────────────────────────
log_step "Environment configuration"
if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    cp .env.example .env
    log_warn ".env not found — copied from .env.example. Edit secrets before production use."
  else
    log_err ".env.example missing — cannot create .env"
  fi
else
  log_ok ".env already exists"
fi

# ── Docker storage ────────────────────────────────────────────────────────────
if ! $API_ONLY; then
  log_step "Starting storage services (PostgreSQL + Qdrant)"
  if ! docker info &>/dev/null 2>&1; then
    log_err "Docker daemon is not running"
  fi

  docker compose up -d
  log_ok "Docker Compose services started"

  # Wait for PostgreSQL to accept connections
  log_step "Waiting for PostgreSQL to be ready"
  TIMEOUT=60
  ELAPSED=0
  until docker compose exec -T postgres pg_isready -U nexus &>/dev/null 2>&1; do
    if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
      log_err "PostgreSQL did not become ready within ${TIMEOUT}s"
    fi
    echo -n "."
    sleep 2
    ELAPSED=$((ELAPSED + 2))
  done
  echo ""
  log_ok "PostgreSQL ready"
fi

# ── Python venv + dependencies ────────────────────────────────────────────────
log_step "Python environment"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  log_ok "Virtual environment created"
fi

# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate 2>/dev/null
pip install -q -r requirements.txt
log_ok "Python dependencies installed"

# ── Alembic migrations ────────────────────────────────────────────────────────
if ! $SKIP_MIGRATE && ! $API_ONLY; then
  log_step "Running Alembic migrations"

  CURRENT=$(alembic -c infrastructure/alembic.ini current 2>&1 || echo "")
  if echo "$CURRENT" | grep -q "(head)"; then
    log_ok "Database already at head — no migration needed"
  else
    # Stamp phase1 if alembic_version table is empty (fresh install from SQL scripts)
    STAMP_CHECK=$(alembic -c infrastructure/alembic.ini current 2>&1 || echo "")
    if echo "$STAMP_CHECK" | grep -q "No migration"; then
      log_warn "Stamping 001_phase1_schema for pre-Alembic database..."
      alembic -c infrastructure/alembic.ini stamp 001_phase1_schema
    fi
    alembic -c infrastructure/alembic.ini upgrade head
    log_ok "Migrations applied to head"
  fi
fi

# ── Web console build ─────────────────────────────────────────────────────────
if ! $SKIP_UI; then
  log_step "Building web console (apps/web-console)"
  pushd apps/web-console > /dev/null
  npm install --silent
  npm run build --silent
  popd > /dev/null
  log_ok "Web console built → apps/web-console/dist/"
fi

# ── Start API ─────────────────────────────────────────────────────────────────
log_step "Starting nexus-api"

export PYTHONPATH="$REPO_ROOT/packages/shared-contracts:$REPO_ROOT/packages/vector-client:$REPO_ROOT/workers/document-parser:$REPO_ROOT/workers/graph-builder:$REPO_ROOT/services/nexus-api:$REPO_ROOT/services/llm-gateway"

echo ""
echo -e "${BOLD}API ready at:${NC} http://127.0.0.1:8000"
echo -e "${BOLD}OpenAPI docs:${NC} http://127.0.0.1:8000/docs"
echo -e "${BOLD}Web console: ${NC} cd apps/web-console && npm run dev  (dev) or serve dist/ (prod)"
echo ""

uvicorn nexus_api.main:app --host 0.0.0.0 --port 8000 --reload
