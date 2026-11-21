"""
collectors/base.py
==================
Shared data models for collectors and embed builders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional

try:
    import zoneinfo
    IST = zoneinfo.ZoneInfo("Asia/Kolkata")
except Exception:
    import pytz
    IST = pytz.timezone("Asia/Kolkata")


@dataclass
class ServiceHealth:
    name: str
    status: str  # "active", "inactive", "failed", "waiting", "unknown"
    sub_state: str = ""
    uptime: str = ""
    description: str = ""

    @property
    def is_running(self) -> bool:
        return self.status.lower() in ("active", "running")


@dataclass
class PositionItem:
    symbol: str
    side: str            # "BUY", "SELL", "LONG", "SHORT"
    quantity: float
    entry_price: float
    current_price: float
    pnl: float
    pnl_pct: float = 0.0
    exchange: str = "NSE" # "NSE" or "DELTA"
    product_type: str = "" # "OPTIONS", "FUTURES", "CNC", "MIS"


@dataclass
class ZerodhaData:
    is_authenticated: bool = False
    service_status: ServiceHealth = field(default_factory=lambda: ServiceHealth("Zerodha Services", "unknown"))
    nifty_strike_status: ServiceHealth = field(default_factory=lambda: ServiceHealth("Nifty Strike Engine", "unknown"))
    nifty_portfolio_status: ServiceHealth = field(default_factory=lambda: ServiceHealth("Nifty Portfolio", "unknown"))
    open_positions: List[PositionItem] = field(default_factory=list)
    intraday_pnl: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    available_margin: float = 0.0
    portfolio_slots_used: int = 0
    portfolio_max_slots: int = 10
    portfolio_unrealized_pnl: float = 0.0
    trades_today_count: int = 0
    error: Optional[str] = None


@dataclass
class DeltaAccountData:
    account_label: str   # "Delta Futures" or "Delta Short Straddle"
    is_authenticated: bool = False
    service_status: ServiceHealth = field(default_factory=lambda: ServiceHealth("Delta Service", "unknown"))
    open_positions: List[PositionItem] = field(default_factory=list)
    unrealized_pnl: float = 0.0
    realized_pnl_today: float = 0.0
    wallet_equity: float = 0.0
    available_balance: float = 0.0
    is_testnet: bool = False
    error: Optional[str] = None


@dataclass
class SystemMetrics:
    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0
    disk_percent: float = 0.0
    temperature_c: Optional[float] = None
    boot_time: str = ""


@dataclass
class DashboardSnapshot:
    timestamp: datetime = field(default_factory=lambda: datetime.now(IST))
    system: SystemMetrics = field(default_factory=SystemMetrics)
    zerodha: ZerodhaData = field(default_factory=ZerodhaData)
    delta_futures: DeltaAccountData = field(default_factory=lambda: DeltaAccountData("Delta Futures"))
    delta_options: DeltaAccountData = field(default_factory=lambda: DeltaAccountData("Delta Short Straddle"))
    overall_status: str = "GREEN"  # "GREEN", "AMBER", "RED"
