"""
collectors/zerodha_collector.py
===============================
Fetches comprehensive Zerodha Exchange data:
1. Stock Holdings (Equity Cash / Swing Portfolio)
2. F&O Derivatives Positions (Nifty/BankNifty Options & Index Futures)
3. MCX Commodity Futures Positions (Gold, Crude Oil, Silver, etc.)
4. Margins for Equity & Commodity segments
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from collectors.base import HoldingItem, PositionItem, ZerodhaData

logger = logging.getLogger(__name__)

COMMODITY_SYMBOLS = {
    "GOLD", "GOLDPETAL", "GOLDM", "SILVER", "SILVERM", "SILVERMIC",
    "CRUDEOIL", "CRUDEOILM", "NATURALGAS", "NATURALGASM", "COPPER", "ZINC", "LEAD", "ALUMINIUM"
}


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
        if api_key != self.api_key or access_token != self.access_token:
            self.api_key = api_key
            self.access_token = access_token
            self._init_client()

    def collect(self) -> ZerodhaData:
        data = ZerodhaData()

        if not self._kite:
            data.is_authenticated = False
            data.error = "Kite access token missing or not refreshed yet"
            self._read_portfolio_state_fallback(data)
            return data

        try:
            # 1. Fetch Margins (Equity & Commodity)
            try:
                margin_resp = self._kite.margins()
                eq_margin = margin_resp.get("equity", {})
                comm_margin = margin_resp.get("commodity", {})

                data.available_margin = float(
                    eq_margin.get("net", 0.0)
                    or eq_margin.get("available", {}).get("live_balance", 0.0)
                    or 0.0
                )
                data.commodity_margin = float(
                    comm_margin.get("net", 0.0)
                    or comm_margin.get("available", {}).get("live_balance", 0.0)
                    or 0.0
                )
            except Exception as e:
                logger.warning(f"Failed to fetch Zerodha margins: {e}")

            # 2. Fetch Stock Holdings (Equity Cash / Swing Portfolio)
            try:
                holdings_resp = self._kite.holdings()
                total_invested = 0.0
                total_current_val = 0.0
                total_pnl = 0.0
                day_pnl = 0.0
                holding_items: List[HoldingItem] = []

                for h in holdings_resp:
                    qty = float(h.get("quantity", 0) or 0)
                    t1_qty = float(h.get("t1_quantity", 0) or 0)
                    total_qty = qty + t1_qty
                    if total_qty <= 0:
                        continue

                    avg_price = float(h.get("average_price", 0.0) or 0.0)
                    last_price = float(h.get("last_price", 0.0) or 0.0)
                    h_pnl = float(h.get("pnl", 0.0) or 0.0)
                    h_day_change = float(h.get("day_change", 0.0) or 0.0)
                    h_day_pnl = round(h_day_change * total_qty, 2)

                    cost = total_qty * avg_price
                    curr_val = total_qty * last_price
                    pnl_pct = (h_pnl / cost * 100.0) if cost > 0 else 0.0

                    total_invested += cost
                    total_current_val += curr_val
                    total_pnl += h_pnl
                    day_pnl += h_day_pnl

                    holding_items.append(
                        HoldingItem(
                            symbol=h.get("tradingsymbol", ""),
                            quantity=total_qty,
                            average_price=avg_price,
                            last_price=last_price,
                            pnl=round(h_pnl, 2),
                            pnl_pct=round(pnl_pct, 2),
                            invested_amount=round(cost, 2),
                            current_value=round(curr_val, 2),
                        )
                    )

                data.holdings = holding_items
                data.holdings_total_investment = round(total_invested, 2)
                data.holdings_current_value = round(total_current_val, 2)
                data.holdings_total_pnl = round(total_pnl, 2)
                data.holdings_day_pnl = round(day_pnl, 2)

            except Exception as e:
                logger.warning(f"Failed to fetch Zerodha holdings: {e}")
                self._read_portfolio_state_fallback(data)

            # 3. Fetch Positions & Categorize (F&O vs Commodities vs Equity)
            pos_resp = self._kite.positions()
            net_positions = pos_resp.get("net", [])

            total_unrealized = 0.0
            total_realized = 0.0

            for p in net_positions:
                qty = float(p.get("quantity", 0) or 0)
                pnl = float(p.get("pnl", 0.0) or 0.0)
                m2m = float(p.get("m2m", 0.0) or 0.0)
                realized = float(p.get("realised", 0.0) or 0.0)
                unrealized = float(p.get("unrealised", 0.0) or 0.0)

                total_realized += realized
                total_unrealized += (m2m if qty != 0 else unrealized)

                if qty != 0:
                    symbol = p.get("tradingsymbol", "")
                    exchange = p.get("exchange", "NSE")
                    product = p.get("product", "MIS")
                    buy_price = float(p.get("average_price", 0.0) or 0.0)
                    ltp = float(p.get("last_price", 0.0) or 0.0)
                    side = "BUY" if qty > 0 else "SELL"

                    cost = abs(qty * buy_price)
                    pnl_pct = (pnl / cost * 100.0) if cost > 0 else 0.0

                    # Determine segment
                    is_commodity = exchange == "MCX" or any(cs in symbol for cs in COMMODITY_SYMBOLS)
                    is_fno = exchange in ("NFO", "BFO") or symbol.endswith("CE") or symbol.endswith("PE") or "FUT" in symbol

                    segment = "COMMODITY" if is_commodity else ("OPTIONS" if is_fno else "EQUITY")

                    item = PositionItem(
                        symbol=symbol,
                        side=side,
                        quantity=qty,
                        entry_price=buy_price,
                        current_price=ltp,
                        pnl=round(pnl, 2),
                        pnl_pct=round(pnl_pct, 2),
                        exchange=exchange,
                        segment=segment,
                        product_type=product,
                    )

                    if is_commodity:
                        data.commodity_positions.append(item)
                    elif is_fno:
                        data.fno_positions.append(item)
                    else:
                        data.equity_positions.append(item)

            data.intraday_mtm = round(total_unrealized, 2)
            data.realized_pnl = round(total_realized, 2)
            data.total_day_pnl = round(total_unrealized + total_realized, 2)
            data.is_authenticated = True

        except Exception as e:
            err_str = str(e)
            logger.error(f"Error querying Zerodha Kite: {err_str}")
            data.error = err_str
            data.is_authenticated = False
            self._read_portfolio_state_fallback(data)

        return data

    def _read_portfolio_state_fallback(self, data: ZerodhaData) -> None:
        """Fallback reading from local nifty-portfolio persistent JSON state."""
        state_file = self.portfolio_dir / "data" / "portfolio_state.json"
        if not state_file.exists():
            return

        try:
            with open(state_file, "r") as f:
                content = json.load(f)
                holdings = content.get("holdings", {})
                if not data.holdings and holdings:
                    p_pnl = 0.0
                    for sym, h in holdings.items():
                        qty = float(h.get("shares", 0) or 0)
                        entry = float(h.get("entry_price", 0.0) or 0.0)
                        pnl = float(h.get("pnl", 0.0) or 0.0)
                        p_pnl += pnl
                        data.holdings.append(
                            HoldingItem(
                                symbol=sym,
                                quantity=qty,
                                average_price=entry,
                                last_price=entry,
                                pnl=pnl,
                                invested_amount=round(qty * entry, 2),
                                current_value=round(qty * entry + pnl, 2),
                            )
                        )
                    data.holdings_total_pnl = round(p_pnl, 2)
        except Exception as e:
            logger.debug(f"Could not read portfolio_state.json: {e}")
