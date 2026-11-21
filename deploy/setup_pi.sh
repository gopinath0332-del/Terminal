#!/usr/bin/env bash
# ==============================================================================
# deploy/setup_pi.sh
# Automated Deployment Script for Algo Dashboard on Raspberry Pi 5
# ==============================================================================

set -eu

# Auto-detect project root directory (works in both sh and bash)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVICE_NAME="algo-dashboard"
USER_NAME="$(whoami)"

echo "=========================================================="
echo "🚀 Deploying Algo Dashboard on Raspberry Pi 5"
echo "   User: ${USER_NAME} | Path: ${APP_DIR}"
echo "=========================================================="

mkdir -p "${APP_DIR}/data"

# 1. Ensure Python 3 virtual environment
if [ ! -d "${APP_DIR}/venv" ]; then
    echo "📦 Creating Python virtual environment in ${APP_DIR}/venv..."
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

# Adapt paths and user in the installed service file
sudo sed -i "s|/home/pi/algo-dashboard|${APP_DIR}|g" "/etc/systemd/system/${SERVICE_NAME}.service"
sudo sed -i "s|User=pi|User=${USER_NAME}|g" "/etc/systemd/system/${SERVICE_NAME}.service"

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}.service"

echo ""
echo "=========================================================="
echo "✅ Deployment Complete!"
echo "   1. Ensure ${APP_DIR}/.env has your DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID."
echo "   2. Start the service:"
echo "      sudo systemctl start ${SERVICE_NAME}"
echo "   3. View live logs:"
echo "      journalctl -u ${SERVICE_NAME} -f"
echo "=========================================================="
