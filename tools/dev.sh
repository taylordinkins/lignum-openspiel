#!/usr/bin/env bash
# Run the API (reload, dev mode) on :8000 and the Vite dev server on :5173. Ctrl-C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."
trap 'kill 0' EXIT INT TERM
LIGNUM_DEV=1 uv run uvicorn server.app:app --reload --port 8000 &
(cd web && npm run dev) &
wait
