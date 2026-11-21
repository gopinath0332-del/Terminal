#!/usr/bin/env bash
# ==============================================================================
# deploy/setup_pi.sh
# Automated Deployment Script for Algo Dashboard on Raspberry Pi 5
# ==============================================================================

set -euo pipefail

APP_DIR="${HOME}/algo-dashboard"
SERVICE_NAME="algo-dashboard"
USER_NAME="$(whoami)"

echo "=========================================================="
echo "🚀 Deploying Algo Dashboard on Raspberry Pi 5"
echo "   User: ${USER_NAME} | Path: ${APP_DIR}"
echo "=========================================================="

mkdir -p "${APP_DIR}/data"

# 1. Ensure Python 3 virtual environment
if [ ! -d "${APP_DIR}/venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv "${APP_DIR}/venv"
fi

echo "📦 Installing / Upgrading Python dependencies..."
"${APP_DIR}/venv/bin/pip" install --upgrade pip
"${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

# 2. Check if .env exists
if [ ! -f "${APP_DIR}/.env" ]; then
    echo "⚠️  No .env file found. Copying .env.example..."
    cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
    echo "❗ IMPORTANT: Please edit ${APP_DIR}/.env and paste your DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID."
fi

# 3. Install Systemd Service
echo "⚙️  Installing systemd service /etc/systemd/system/${SERVICE_NAME}.service..."
sudo cp "${APP_DIR}/deploy/${SERVICE_NAME}.service" "/etc/systemd/system/"

if [ "${USER_NAME}" != "pi" ]; then
    sudo sed -i "s|User=pi|User=${USER_NAME}|g" "/etc/systemd/system/${SERVICE_NAME}.service"
    sudo sed -i "s|/home/pi|${HOME}|g" "/etc/systemd/system/${SERVICE_NAME}.service"
fi

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}.service"

echo ""
echo "=========================================================="
echo "✅ Deployment Complete!"
echo "   To start the service:"
echo "     sudo systemctl start ${SERVICE_NAME}"
echo "   To view live logs:"
echo "     journalctl -u ${SERVICE_NAME} -f"
echo "=========================================================="
