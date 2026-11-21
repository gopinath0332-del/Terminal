# 📊 Algo Production Monitor — Live Discord Dashboard

A centralized, live-updating Discord dashboard for monitoring all your algorithmic trading applications running on your **Raspberry Pi 5** production server:

1. **Nifty Strike Engine** (Zerodha Kite — Intraday 5m Options Buying)
2. **Nifty 500 Portfolio Engine** (Zerodha Kite — Daily Breakout Swing)
3. **Delta Short Straddle Bot** (Delta Exchange — Daily BTC 17:00 IST Options)
4. **Delta Crypto Futures** (Delta Exchange — Multi-Strategy Futures)

Instead of logging into 2 different broker web portals (Zerodha & Delta Exchange) or checking separate logs over SSH, the bot maintains a **single pinned master embed message** in a private Discord channel and edits it in-place every 20 seconds.

---

## 📸 Dashboard Overview

```
┌─────────────────────────────────────────────────────────────┐
│ 🟢 ALGO TRADING PRODUCTION MONITOR           [16:20:00 IST] │
│ Node: Raspberry Pi 5 • Date: 21 Nov 2026                    │
│ CPU: 12.4% | RAM: 1.8/4.0 GB (42%) | Temp: 43.5°C | Disk: 24%│
├─────────────────────────────────────────────────────────────┤
│ 1️⃣ Nifty Strike Engine (Zerodha)            ● ACTIVE        │
│    • Service: nifty-strike-engine.service                   │
│    • 1x NIFTY 24200 CE (Entry: ₹142.50 ➔ LTP: ₹160.00)      │
│    • Intraday MTM: +₹1,137.50                               │
│                                                             │
│ 2️⃣ Nifty 500 Breakout Portfolio (Zerodha)   ● WAITING       │
│    • Schedule: Daily at 15:45 IST (nifty-portfolio.timer)   │
│    • Active Slots: 10/10 stocks | Portfolio P&L: +₹8,450    │
│    • Available Margin: ₹12,400.00                           │
│                                                             │
│ 3️⃣ Delta Short Straddle (⚡ LIVE)            ● WAITING       │
│    • Service: options-bot.service (Scheduled @ 17:00 IST)   │
│    • Today's Options P&L: $0.00 | Wallet Equity: $850.00    │
│                                                             │
│ 4️⃣ Delta Crypto Futures (⚡ LIVE)            ● ACTIVE        │
│    • Service: delta-bot.service                             │
│    • BTCUSD LONG (+$24.50), SOLUSD SHORT (-$3.20)           │
│    • Futures MTM: +$21.30 | Wallet Equity: $1,420.00        │
├─────────────────────────────────────────────────────────────┤
│ 💰 COMBINED TOTAL P&L TODAY                                 │
│ 🇮🇳 Indian Markets (NSE):   +₹9,587.50                       │
│ 🌐 Crypto Markets (Delta): +$21.30                          │
└─────────────────────────────────────────────────────────────┘
  [ 🔄 Refresh Now ]   [ 📋 View All Positions ]   [ 🩺 Pi Health ]
```

---

## ✨ Features

- **In-Place Live Refresh:** Edits the exact same pinned message every 20 seconds — zero channel message spam.
- **Separate Delta API Keys:** Independently queries your Futures account (`delta-exchange-alog`) and Options account (`opt-algo`).
- **Zero-Touch Kite Token Discovery:** Automatically reads the active `KITE_ACCESS_TOKEN` updated daily by your automated login script.
- **Interactive UI Buttons:**
  - `[ 🔄 Refresh Now ]`: Forces immediate data sync and updates the dashboard.
  - `[ 📋 View All Positions ]`: Sends an ephemeral breakdown of all open contracts, CMP, and P&L visible only to you.
  - `[ 🩺 Pi Health ]`: Displays CPU, RAM, Disk, SoC temperature, and systemd service states.
- **Production Ready:** Includes systemd service definition and auto-restart on boot.

---

## 🛠️ Step-by-Step Setup

### 1. Create Your Discord Bot (2 Minutes)

1. Go to the **[Discord Developer Portal](https://discord.com/developers/applications)**.
2. Click **New Application** $\rightarrow$ Name it `Algo Monitor`.
3. In the left menu, click **Bot**:
   - Click **Reset Token** and copy the **Bot Token**.
   - Under **Privileged Gateway Intents**, turn ON **Message Content Intent**.
4. In the left menu, click **Installation** (or OAuth2 $\rightarrow$ URL Generator):
   - Select Scope: `bot`
   - Permissions: `Send Messages`, `Embed Links`, `Manage Messages` (needed to pin), `Read Message History`.
   - Open the generated URL in a browser and invite the bot to your Discord server.
5. In Discord, create a channel (e.g. `#algo-dashboard`) and copy its **Channel ID** (Right-click channel $\rightarrow$ *Copy Channel ID*).

---

### 2. Configure `.env`

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` and fill in:
```env
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_CHANNEL_ID=your_channel_id_here
```

All other credentials (Zerodha and Delta Exchange) are automatically discovered from your existing project directories (`/home/pi/...` on the Pi or `D:\Workspace\...` on Windows).

---

### 3. Deploy to Raspberry Pi 5

Copy this directory to your Raspberry Pi at `/home/pi/algo-dashboard`, then run:

```bash
cd /home/pi/algo-dashboard
chmod +x deploy/setup_pi.sh
bash deploy/setup_pi.sh
```

Start the background service:
```bash
sudo systemctl start algo-dashboard
```

Check live logs:
```bash
journalctl -u algo-dashboard -f
```

---

### 4. Running Locally for Testing (Windows)

You can also run it on your Windows machine right now:

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```
