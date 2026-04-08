#!/usr/bin/env bash
set -uo pipefail

# RealityOps pre-submission validator.
# Usage: ./validate-submission.sh <hf_space_url> [repo_dir]

DOCKER_BUILD_TIMEOUT=600

if [ -t 1 ]; then
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  YELLOW='\033[1;33m'
  BOLD='\033[1m'
  NC='\033[0m'
else
  RED='' GREEN='' YELLOW='' BOLD='' NC=''
fi

run_with_timeout() {
  local secs="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then
    timeout "$secs" "$@"
  elif command -v gtimeout >/dev/null 2>&1; then
    gtimeout "$secs" "$@"
  else
    "$@" &
    local pid=$!
    ( sleep "$secs" && kill "$pid" 2>/dev/null ) &
    local watcher=$!
    wait "$pid" 2>/dev/null
    local rc=$?
    kill "$watcher" 2>/dev/null
    wait "$watcher" 2>/dev/null
    return "$rc"
  fi
}

portable_mktemp() {
  local prefix="${1:-validate}"
  mktemp "${TMPDIR:-/tmp}/${prefix}-XXXXXX" 2>/dev/null || mktemp
}

CLEANUP_FILES=()
cleanup() {
  rm -f "${CLEANUP_FILES[@]+"${CLEANUP_FILES[@]}"}"
}
trap cleanup EXIT

HF_SPACE_URL="${1:-}"
REPO_DIR="${2:-.}"

if [ -z "$HF_SPACE_URL" ]; then
  printf "Usage: %s <hf_space_url> [repo_dir]\n" "$0"
  printf "Example: %s https://your-space.hf.space .\n" "$0"
  exit 1
fi

if ! REPO_DIR="$(cd "$REPO_DIR" 2>/dev/null && pwd)"; then
  printf "Error: directory '%s' not found\n" "${2:-.}"
  exit 1
fi

HF_SPACE_URL="${HF_SPACE_URL%/}"
PASS_COUNT=0

log() {
  printf "[%s] %b\n" "$(date -u +%H:%M:%S)" "$*"
}

pass() {
  log "${GREEN}PASSED${NC} -- $1"
  PASS_COUNT=$((PASS_COUNT + 1))
}

fail() {
  log "${RED}FAILED${NC} -- $1"
}

hint() {
  printf "  ${YELLOW}Hint:${NC} %b\n" "$1"
}

stop_at() {
  printf "\n${RED}${BOLD}Validation stopped at %s.${NC}\n" "$1"
  exit 1
}

log "Step 1/3: Checking HF Space availability"

PING_OUTPUT=$(portable_mktemp "validate-ping")
CLEANUP_FILES+=("$PING_OUTPUT")

HTTP_CODE=$(curl -s -o "$PING_OUTPUT" -w "%{http_code}" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{}' \
  "$HF_SPACE_URL/reset" \
  --max-time 30 2>/dev/null || printf "000")

if [ "$HTTP_CODE" = "200" ]; then
  pass "HF Space is reachable and responds to /reset"
else
  if [ "$HTTP_CODE" = "000" ]; then
    fail "HF Space is not reachable"
    hint "Check that your Space URL is correct and deployment is live."
  else
    fail "HF Space /reset returned HTTP $HTTP_CODE"
    hint "Ensure your server exposes POST /reset and is healthy."
  fi
  stop_at "Step 1"
fi

log "Step 2/3: Building Docker image"

if ! command -v docker >/dev/null 2>&1; then
  fail "docker command not found"
  hint "Install Docker and ensure it is available in PATH."
  stop_at "Step 2"
fi

if [ -f "$REPO_DIR/Dockerfile" ]; then
  DOCKER_CONTEXT="$REPO_DIR"
elif [ -f "$REPO_DIR/server/Dockerfile" ]; then
  DOCKER_CONTEXT="$REPO_DIR/server"
else
  fail "No Dockerfile found in repo root or server/"
  stop_at "Step 2"
fi

BUILD_OUTPUT=$(run_with_timeout "$DOCKER_BUILD_TIMEOUT" docker build "$DOCKER_CONTEXT" 2>&1)
BUILD_RC=$?

if [ "$BUILD_RC" -eq 0 ]; then
  pass "Docker build succeeded"
else
  fail "Docker build failed (timeout=${DOCKER_BUILD_TIMEOUT}s)"
  printf "%s\n" "$BUILD_OUTPUT" | tail -20
  hint "Resolve Dockerfile/build errors and retry."
  stop_at "Step 2"
fi

log "Step 3/3: Running openenv validate"

if ! command -v openenv >/dev/null 2>&1; then
  fail "openenv command not found"
  hint "Install with: pip install openenv-core"
  stop_at "Step 3"
fi

VALIDATE_OUTPUT=$(cd "$REPO_DIR" && openenv validate 2>&1)
VALIDATE_RC=$?

if [ "$VALIDATE_RC" -eq 0 ]; then
  pass "openenv validate passed"
else
  fail "openenv validate failed"
  printf "%s\n" "$VALIDATE_OUTPUT"
  hint "Fix schema/contract errors reported by openenv validate."
  stop_at "Step 3"
fi

printf "\n${GREEN}${BOLD}All 3/3 checks passed. Submission is ready.${NC}\n\n"
exit 0
