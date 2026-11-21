"""
config/settings.py
==================
Centralized configuration manager for Algo Dashboard.
ALWAYS reads exchange credentials directly from each respective project directory:
- Delta Futures: delta-exchange-alog/config/.env
- Delta Options: opt-algo/config/.env
- Zerodha Kite: nifty-strike-engine/.env
- Nifty Portfolio: nifty-portfolio/data/portfolio_state.json
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any

from dotenv import dotenv_values, load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _resolve_candidate_path(env_var_name: str, linux_default: str, windows_default: str) -> Path:
    """Resolve path checking custom env override, linux default, then windows fallback."""
    custom = os.getenv(env_var_name)
    if custom and Path(custom).exists():
        return Path(custom)

    p_linux = Path(linux_default)
    if p_linux.exists():
        return p_linux

    p_win = Path(windows_default)
    if p_win.exists():
        return p_win

    if custom:
        return Path(custom)
    return p_win if sys.platform.startswith("win") else p_linux


@dataclass
class DashboardConfig:
    # Discord
    bot_token: str = field(default_factory=lambda: os.getenv("DISCORD_BOT_TOKEN", "").strip())
    channel_id: int = field(default_factory=lambda: int(os.getenv("DISCORD_CHANNEL_ID", "0") or "0"))
    refresh_interval: int = field(default_factory=lambda: int(os.getenv("REFRESH_INTERVAL_SECONDS", "20")))

    # Project directories
    nifty_strike_env_path: Path = field(
        default_factory=lambda: _resolve_candidate_path(
            "NIFTY_STRIKE_ENV_PATH",
            "/home/pi/nifty-strike-engine/.env",
            "D:/Workspace/nifty-strike-engine/.env",
        )
    )
    nifty_portfolio_dir: Path = field(
        default_factory=lambda: _resolve_candidate_path(
            "NIFTY_PORTFOLIO_DIR",
            "/home/pi/nifty-portfolio",
            "D:/Workspace/nifty-portfolio",
        )
    )
    delta_futures_env_path: Path = field(
        default_factory=lambda: _resolve_candidate_path(
            "DELTA_FUTURES_ENV_PATH",
            "/home/pi/delta-exchange-alog/config/.env",
            "D:/Workspace/delta-exchange-alog/config/.env",
        )
    )
    delta_options_env_path: Path = field(
        default_factory=lambda: _resolve_candidate_path(
            "DELTA_OPTIONS_ENV_PATH",
            "/home/pi/opt-algo/config/.env",
            "D:/Workspace/opt-algo/config/.env",
        )
    )

    state_file: Path = field(default_factory=lambda: BASE_DIR / "data" / "dashboard_state.json")

    # Service names on Linux
    services: Dict[str, str] = field(
        default_factory=lambda: {
            "nifty_strike": "nifty-strike-engine.service",
            "nifty_portfolio": "nifty-portfolio.timer",
            "delta_futures": "delta-bot.service",
            "delta_options": "options-bot.service",
        }
    )

    def get_zerodha_creds(self) -> Dict[str, str]:
        """ALWAYS fetch Kite credentials directly from nifty-strike-engine/.env."""
        api_key = ""
        access_token = ""

        if self.nifty_strike_env_path.exists():
            values = dotenv_values(self.nifty_strike_env_path)
            api_key = str(values.get("KITE_API_KEY", "")).strip()
            access_token = str(values.get("KITE_ACCESS_TOKEN", "")).strip()

        # Fallback to local env only if project env had none
        api_key = api_key or os.getenv("KITE_API_KEY", "").strip()
        access_token = access_token or os.getenv("KITE_ACCESS_TOKEN", "").strip()

        return {
            "api_key": api_key,
            "access_token": access_token,
        }

    def get_delta_futures_creds(self) -> Dict[str, str]:
        """ALWAYS fetch Delta Futures credentials directly from delta-exchange-alog/config/.env."""
        api_key = ""
        api_secret = ""
        base_url = "https://api.india.delta.exchange"

        if self.delta_futures_env_path.exists():
            values = dotenv_values(self.delta_futures_env_path)
            api_key = str(values.get("DELTA_FUTURES_API_KEY") or values.get("DELTA_API_KEY", "")).strip()
            api_secret = str(values.get("DELTA_FUTURES_API_SECRET") or values.get("DELTA_API_SECRET", "")).strip()
            base_url = str(values.get("DELTA_BASE_URL", "https://api.india.delta.exchange")).strip()

        # Fallback to local env only if not in project env
        api_key = api_key or os.getenv("DELTA_FUTURES_API_KEY", "").strip()
        api_secret = api_secret or os.getenv("DELTA_FUTURES_API_SECRET", "").strip()

        return {
            "api_key": api_key,
            "api_secret": api_secret,
            "base_url": base_url,
        }

    def get_delta_options_creds(self) -> Dict[str, str]:
        """ALWAYS fetch Delta Options credentials directly from opt-algo/config/.env."""
        api_key = ""
        api_secret = ""
        base_url = "https://api.india.delta.exchange"

        if self.delta_options_env_path.exists():
            values = dotenv_values(self.delta_options_env_path)
            api_key = str(values.get("DELTA_OPTIONS_API_KEY") or values.get("DELTA_API_KEY", "")).strip()
            api_secret = str(values.get("DELTA_OPTIONS_API_SECRET") or values.get("DELTA_API_SECRET", "")).strip()
            base_url = str(values.get("DELTA_BASE_URL", "https://api.india.delta.exchange")).strip()

        # Fallback to local env only if not in project env
        api_key = api_key or os.getenv("DELTA_OPTIONS_API_KEY", "").strip()
        api_secret = api_secret or os.getenv("DELTA_OPTIONS_API_SECRET", "").strip()

        return {
            "api_key": api_key,
            "api_secret": api_secret,
            "base_url": base_url,
        }


# Singleton config instance
config = DashboardConfig()
