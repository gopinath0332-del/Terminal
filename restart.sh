#!/usr/bin/env bash
# ==============================================================================
# restart.sh
# Safely restarts the Algo Dashboard daemon on Raspberry Pi and displays status
# ==============================================================================

SERVICE_NAME="algo-dashboard"

echo "=========================================================="
echo "🔄 Restarting ${SERVICE_NAME} service..."
echo "=========================================================="

if systemctl list-unit-files | grep -q "^${SERVICE_NAME}.service"; then
    sudo systemctl restart "${SERVICE_NAME}"
    echo "✅ Service restarted."
else
    echo "⚠️  ${SERVICE_NAME}.service not found in systemd."
    echo "   Please run 'bash deploy/setup_pi.sh' first."
    exit 1
fi

sleep 2

echo ""
echo "📊 Current Status:"
sudo systemctl status "${SERVICE_NAME}" --no-pager || true

echo ""
echo "📜 Recent Logs:"
sudo journalctl -u "${SERVICE_NAME}" -n 20 --no-pager
