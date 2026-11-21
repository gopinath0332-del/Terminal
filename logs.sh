#!/usr/bin/env bash
# ==============================================================================
# logs.sh
# Live-tails the Algo Dashboard systemd logs
# ==============================================================================

SERVICE_NAME="algo-dashboard"

echo "📜 Streaming live logs for ${SERVICE_NAME} (Ctrl+C to exit)..."
sudo journalctl -u "${SERVICE_NAME}" -f
