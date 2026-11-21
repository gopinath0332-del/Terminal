"""
collectors/zerodha_collector.py
===============================
Fetches live positions, margins, and P&L from Zerodha Kite Connect,
and reads portfolio state from nifty-portfolio engine.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from collectors.base import PositionItem, ServiceHealth, ZerodhaData

logger = logging.getLogger(__name__)


class ZerodhaCollector:
    """Interacts with Zerodha Kite REST API and local state files."""

    def __init__(self, api_key: str, access_token: str, portfolio_dir: Path):
        self.api_key = api_key
        self.access_token = access_token
        self.portfolio_dir = portfolio_dir
        self._kite: Optional[Any] = None
        self._init_client()

    def _init_client(self) -> None:
        if not self.api_key or not self.access_token:
            logger.info("Zerodha credentials missing or access token not generated yet.")
            return

        try:
            from kiteconnect import KiteConnect
            self._kite = KiteConnect(api_key=self.api_key)
            self._kite.set_access_token(self.access_token)
        except Exception as e:
            logger.error(f"Failed to initialize KiteConnect client: {e}")
            self._kite = None

    def update_credentials(self, api_key: str, access_token: str) -> None:
        """Update credentials dynamically (e.g. after daily auto-login refreshes token)."""
        if api_key != self.api_key or access_token != self.access_token:
            self.api_key = api_key
            self.access_token = access_token
            self._init_client()

    def collect(self) -> ZerodhaData:
        """Collect current Zerodha trading status and open positions."""
        data = ZerodhaData()

        # 1. Check local Nifty Portfolio state file
        self._read_portfolio_state(data)

        # 2. Query Kite API if initialized
        if not self._kite:
            data.is_authenticated = False
            data.error = "Kite access token missing or not refreshed yet"
            return data

        try:
            # Query Margins
            try:
                margins = self._kite.margins(segment="equity")
                available_cash = (
                    margins.get("net", 0.0)
                    or margins.get("available", {}).get("live_balance", 0.0)
                    or margins.get("available", {}).get("cash", 0.0)
                )
                data.available_margin = float(available_cash)
            except Exception as e:
                logger.warning(f"Could not fetch Zerodha margins: {e}")

            # Query Positions
            pos_resp = self._kite.positions()
            net_positions = pos_resp.get("net", [])
            day_positions = pos_resp.get("day", [])

            total_unrealized = 0.0
            total_realized = 0.0
            open_items: List[PositionItem] = []

            for p in net_positions:
                qty = float(p.get("quantity", 0))
                pnl = float(p.get("pnl", 0.0))
                m2m = float(p.get("m2m", 0.0))
                realized = float(p.get("realised", 0.0))
                unrealized = float(p.get("unrealised", 0.0))

                total_realized += realized
                total_unrealized += (m2m if qty != 0 else unrealized)

                if qty != 0:
                    symbol = p.get("tradingsymbol", "")
                    buy_price = float(p.get("average_price", 0.0))
                    ltp = float(p.get("last_price", 0.0))
                    side = "BUY" if qty > 0 else "SELL"
                    product = p.get("product", "MIS")

                    cost = abs(qty * buy_price)
                    pnl_pct = (pnl / cost * 100.0) if cost > 0 else 0.0

                    open_items.append(
                        PositionItem(
                            symbol=symbol,
                            side=side,
                            quantity=qty,
                            entry_price=buy_price,
                            current_price=ltp,
                            pnl=pnl,
                            pnl_pct=round(pnl_pct, 2),
                            exchange="NSE",
                            product_type=product,
                        )
                    )

            data.open_positions = open_items
            data.unrealized_pnl = round(total_unrealized, 2)
            data.realized_pnl = round(total_realized, 2)
            data.intraday_pnl = round(total_unrealized + total_realized, 2)
            data.trades_today_count = len(day_positions)
            data.is_authenticated = True

        except Exception as e:
            err_str = str(e)
            logger.error(f"Error querying Zerodha Kite API: {err_str}")
            data.error = err_str
            data.is_authenticated = False

        return data

    def _read_portfolio_state(self, data: ZerodhaData) -> None:
        """Read nifty-portfolio persistent JSON state if present."""
        state_file = self.portfolio_dir / "data" / "portfolio_state.json"
        if not state_file.exists():
            return

        try:
            with open(state_file, "r") as f:
                content = json.load(f)
                holdings = content.get("holdings", {})
                data.portfolio_slots_used = len(holdings)
                data.portfolio_max_slots = content.get("max_slots", 10)

                # Sum unrealized portfolio pnl if recorded
                p_pnl = 0.0
                for _, h in holdings.items():
                    p_pnl += float(h.get("pnl", 0.0) or 0.0)
                data.portfolio_unrealized_pnl = round(p_pnl, 2)
        except Exception as e:
            logger.debug(f"Could not read portfolio_state.json: {e}")
