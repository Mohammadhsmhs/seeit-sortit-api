#!/usr/bin/env bash
# start_services.sh — Start all SeeIt SortIt services in a persistent tmux session.
# Services survive SSH disconnection. Reconnect with: tmux attach -t seeit-sortit
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
TMUX_SESSION="seeit-sortit"
CONTAINER_NAME="seeit-sortit-nim"
NIM_IMAGE="nvcr.io/nim/nvidia/nemotron-nano-12b-v2-vl:latest"
NIM_PORT=8888
API_PORT=8000
LT_SUBDOMAIN="fixmy-council-seeit-sortit"

echo "=== SeeIt SortIt Service Manager ==="

# ── 1. Kill orphaned processes ─────────────────────────────────────────────────
echo "[1/4] Cleaning up orphaned processes..."
kill -9 $(lsof -t -i :${API_PORT} 2>/dev/null) 2>/dev/null || true
pkill -9 -f localtunnel 2>/dev/null || true

# ── 2. Start Docker NIM container (detached, auto-restart) ─────────────────────
echo "[2/4] Starting NIM container (${CONTAINER_NAME})..."
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "  ✓ Container '${CONTAINER_NAME}' is already running."
else
    # Remove stopped container with same name if it exists
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true

    LOCAL_NIM_CACHE="${HOME}/.cache/nim"
    mkdir -p "${LOCAL_NIM_CACHE}"

    docker run -d \
        --name "${CONTAINER_NAME}" \
        --gpus all \
        --shm-size=16GB \
        --ipc=host \
        --privileged \
        --restart unless-stopped \
        -e NGC_API_KEY="${NGC_API_KEY}" \
        -v "${LOCAL_NIM_CACHE}:/opt/nim/.cache" \
        -p ${NIM_PORT}:8000 \
        "${NIM_IMAGE}"

    echo "  ✓ Container started. Logs: docker logs -f ${CONTAINER_NAME}"
fi

# ── 3. Kill existing tmux session if it exists ─────────────────────────────────
tmux kill-session -t "${TMUX_SESSION}" 2>/dev/null || true

# ── 4. Create tmux session with uvicorn + localtunnel ──────────────────────────
echo "[3/4] Creating tmux session '${TMUX_SESSION}'..."

# Window 0: uvicorn
tmux new-session -d -s "${TMUX_SESSION}" -n "api" \
    "cd ${PROJECT_DIR} && conda run --no-banner -n seeit-sortit uvicorn main:app --host 0.0.0.0 --port ${API_PORT} --reload; bash"

# Window 1: localtunnel
sleep 2  # Give uvicorn a moment to bind
tmux new-window -t "${TMUX_SESSION}" -n "tunnel" \
    "cd ${PROJECT_DIR} && npx localtunnel --port ${API_PORT} --subdomain ${LT_SUBDOMAIN}; bash"

# Window 2: docker logs (for monitoring)
tmux new-window -t "${TMUX_SESSION}" -n "nim-logs" \
    "docker logs -f ${CONTAINER_NAME}; bash"

echo "[4/4] All services started!"
echo ""
echo "  ┌──────────────────────────────────────────────────────────┐"
echo "  │  Services are running in tmux session: ${TMUX_SESSION}  │"
echo "  │                                                          │"
echo "  │  API:    http://localhost:${API_PORT}/docs               │"
echo "  │  Tunnel: https://${LT_SUBDOMAIN}.loca.lt                │"
echo "  │  NIM:    http://localhost:${NIM_PORT}/v1                 │"
echo "  │                                                          │"
echo "  │  Reconnect after SSH disconnect:                         │"
echo "  │    tmux attach -t ${TMUX_SESSION}                        │"
echo "  │                                                          │"
echo "  │  Switch windows: Ctrl+B then 0/1/2                      │"
echo "  │    0 = API server                                        │"
echo "  │    1 = Localtunnel                                       │"
echo "  │    2 = NIM container logs                                │"
echo "  └──────────────────────────────────────────────────────────┘"
