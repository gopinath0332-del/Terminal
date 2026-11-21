"""
collectors/base.py
==================
Shared data models for exchange-wise collectors and embed builders.
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
    status: str  # "active", "inactive", "failed", "waiting", "dev_mode", "unknown"
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
    exchange: str = "NSE"     # "NSE", "BSE", "MCX", "DELTA"
    segment: str = "EQUITY"   # "EQUITY", "OPTIONS", "COMMODITY", "FUTURES"
    product_type: str = ""    # "CNC", "MIS", "NRML"


@dataclass
class HoldingItem:
    symbol: str
    quantity: float
    average_price: float
    last_price: float
    pnl: float
    pnl_pct: float = 0.0
    invested_amount: float = 0.0
    current_value: float = 0.0


@dataclass
class ZerodhaData:
    """Zerodha Exchange Data across Holdings, F&O, and MCX Commodities."""
    is_authenticated: bool = False

    # Holdings (Equity Cash / Swing Portfolio)
    holdings: List[HoldingItem] = field(default_factory=list)
    holdings_total_investment: float = 0.0
    holdings_current_value: float = 0.0
    holdings_total_pnl: float = 0.0
    holdings_day_pnl: float = 0.0

    # Positions categorized
    fno_positions: List[PositionItem] = field(default_factory=list)       # NFO Options & Index Futures
    commodity_positions: List[PositionItem] = field(default_factory=list) # MCX Futures (Gold, Crude, etc.)
    equity_positions: List[PositionItem] = field(default_factory=list)    # Intraday MIS

    # Account Financials
    intraday_mtm: float = 0.0
    realized_pnl: float = 0.0
    total_day_pnl: float = 0.0
    available_margin: float = 0.0
    commodity_margin: float = 0.0

    # Systemd daemons attached
    nifty_strike_status: ServiceHealth = field(default_factory=lambda: ServiceHealth("Nifty Strike Engine", "unknown"))
    nifty_portfolio_status: ServiceHealth = field(default_factory=lambda: ServiceHealth("Nifty Portfolio", "unknown"))

    error: Optional[str] = None


@dataclass
class DeltaAccountData:
    """Delta Exchange Account Data (Futures or Options)."""
    account_label: str   # "Delta Futures Account" or "Delta Options Account"
    account_type: str    # "FUTURES" or "OPTIONS"
    is_authenticated: bool = False
    is_testnet: bool = False

    open_positions: List[PositionItem] = field(default_factory=list)
    unrealized_pnl: float = 0.0
    realized_pnl_today: float = 0.0
    wallet_equity: float = 0.0
    available_balance: float = 0.0

    service_status: ServiceHealth = field(default_factory=lambda: ServiceHealth("Delta Service", "unknown"))
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
    delta_futures: DeltaAccountData = field(default_factory=lambda: DeltaAccountData("Delta Futures Account", "FUTURES"))
    delta_options: DeltaAccountData = field(default_factory=lambda: DeltaAccountData("Delta Options Account", "OPTIONS"))
