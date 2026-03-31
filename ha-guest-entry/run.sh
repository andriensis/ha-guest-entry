#!/usr/bin/with-contenv bashio

export PORT="${PORT:-7979}"
export DATA_DIR="${DATA_DIR:-/data}"
export CONFIG_DIR="${CONFIG_DIR:-/config}"
export OPTIONS_FILE="${OPTIONS_FILE:-/data/options.json}"
export HA_BASE_URL="${HA_BASE_URL:-http://supervisor/core/api}"
export HA_WS_URL="${HA_WS_URL:-ws://supervisor/core/websocket}"
export SUPERVISOR_TOKEN="${SUPERVISOR_TOKEN}"

exec python -m backend.main
