#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Launch both PaperPulse services inside the OpenShell sandbox:
#   - FastAPI backend  (python run.py)      -> :${PORT:-8000}
#   - Next.js frontend (standalone server)  -> :3000
# Writable state lives under /sandbox; /app is read-only.

set -euo pipefail

export PORT="${PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
export CMBAGENT_DEFAULT_WORK_DIR="${CMBAGENT_DEFAULT_WORK_DIR:-/sandbox/cmbdir}"
mkdir -p "${CMBAGENT_DEFAULT_WORK_DIR}"

echo "[paperpulse] backend  -> http://0.0.0.0:${PORT}  (docs at /docs)"
( cd /app/backend && exec python run.py ) &
backend_pid=$!

echo "[paperpulse] frontend -> http://0.0.0.0:${FRONTEND_PORT}"
( cd /app/frontend/.next/standalone && exec env PORT="${FRONTEND_PORT}" HOSTNAME=0.0.0.0 node server.js ) &
frontend_pid=$!

# If either service exits, tear the whole thing down so the sandbox doesn't
# linger half-alive.
wait -n "${backend_pid}" "${frontend_pid}"
echo "[paperpulse] a service exited — shutting down the other"
kill "${backend_pid}" "${frontend_pid}" 2>/dev/null || true
wait || true
