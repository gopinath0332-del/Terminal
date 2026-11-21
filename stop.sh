#!/usr/bin/env bash
# ==============================================================================
# stop.sh
# Stops the Algo Dashboard daemon
# ==============================================================================

SERVICE_NAME="algo-dashboard"

echo "🛑 Stopping ${SERVICE_NAME}..."
sudo systemctl stop "${SERVICE_NAME}"
echo "✅ ${SERVICE_NAME} stopped."
