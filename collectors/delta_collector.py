"""
collectors/delta_collector.py
=============================
Delta Exchange REST collector supporting distinct API credentials for:
1. Delta Crypto Futures (delta-exchange-alog)
2. Delta Options Short Straddle (opt-algo)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import urllib.parse
from typing import Dict, Any, List, Optional

import requests

from collectors.base import DeltaAccountData, PositionItem

logger = logging.getLogger(__name__)


class DeltaAccountCollector:
    """Queries Delta Exchange REST endpoints using HMAC-SHA256 authentication."""

    def __init__(
        self,
        account_label: str,
        api_key: str,
        api_secret: str,
        base_url: str = "https://api.india.delta.exchange",
    ):
        self.account_label = account_label
        self.api_key = api_key.strip()
        self.api_secret = api_secret.strip()
        self.base_url = base_url.rstrip("/")
        self.is_testnet = "testnet" in self.base_url.lower()

    def update_credentials(self, api_key: str, api_secret: str, base_url: str) -> None:
        self.api_key = api_key.strip()
        self.api_secret = api_secret.strip()
        if base_url:
            self.base_url = base_url.rstrip("/")
            self.is_testnet = "testnet" in self.base_url.lower()

    def _sign_and_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Generate HMAC-SHA256 signature and execute request."""
        timestamp = str(int(time.time()))
        query_string = ""
        url = f"{self.base_url}{endpoint}"

        if params:
            query_string = urllib.parse.urlencode(params)
            url_with_query = f"{url}?{query_string}"
        else:
            url_with_query = url

        path_with_query = endpoint if not query_string else f"{endpoint}?{query_string}"
        payload = json.dumps(data) if data else ""

        message = f"{method}{timestamp}{path_with_query}{payload}"
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "api-key": self.api_key,
            "timestamp": timestamp,
            "signature": signature,
        }

        resp = requests.request(method, url_with_query, headers=headers, data=payload or None, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def collect(self) -> DeltaAccountData:
        """Fetch open positions and wallet equity for this account."""
        data = DeltaAccountData(
            account_label=self.account_label,
            is_testnet=self.is_testnet,
        )

        if not self.api_key or not self.api_secret:
            data.is_authenticated = False
            data.error = f"API credentials missing for {self.account_label}"
            return data

        try:
            # 1. Fetch Wallet Balance
            try:
                wallet_resp = self._sign_and_request("GET", "/v2/wallet/balances")
                balances = wallet_resp.get("result", [])
                total_equity = 0.0
                avail_bal = 0.0

                for b in balances:
                    asset = b.get("asset_symbol", "")
                    # Consider USD, USDT, USDC balances
                    if asset in ("USDT", "USD", "USDC", "DETO"):
                        bal = float(b.get("balance", 0.0) or 0.0)
                        avail = float(b.get("available_balance", 0.0) or 0.0)
                        total_equity += bal
                        avail_bal += avail

                data.wallet_equity = round(total_equity, 2)
                data.available_balance = round(avail_bal, 2)
            except Exception as e:
                logger.warning(f"Failed to fetch {self.account_label} wallet balance: {e}")

            # 2. Fetch Open Positions
            pos_resp = self._sign_and_request("GET", "/v2/positions/margined")
            positions = pos_resp.get("result", [])
            if not positions:
                # Fallback to general positions endpoint if margined returns empty
                try:
                    alt_pos = self._sign_and_request("GET", "/v2/positions")
                    positions = alt_pos.get("result", [])
                except Exception:
                    pass

            open_items: List[PositionItem] = []
            total_unrealized = 0.0
            total_realized_today = 0.0

            for p in positions:
                size = float(p.get("size", 0) or 0)
                if size == 0:
                    continue

                symbol = (
                    p.get("product_symbol")
                    or (p.get("product") or {}).get("symbol")
                    or f"Product-{p.get('product_id')}"
                )
                entry_price = float(p.get("entry_price", 0.0) or 0.0)
                mark_price = float(p.get("mark_price", 0.0) or 0.0)
                unrealized = float(p.get("unrealized_pnl", 0.0) or 0.0)
                realized = float(p.get("realized_pnl", 0.0) or 0.0)

                side = "LONG" if size > 0 else "SHORT"
                total_unrealized += unrealized
                total_realized_today += realized

                cost = abs(size * entry_price)
                pnl_pct = (unrealized / cost * 100.0) if cost > 0 else 0.0

                open_items.append(
                    PositionItem(
                        symbol=symbol,
                        side=side,
                        quantity=abs(size),
                        entry_price=entry_price,
                        current_price=mark_price,
                        pnl=round(unrealized, 2),
                        pnl_pct=round(pnl_pct, 2),
                        exchange="DELTA",
                        product_type="OPTIONS" if ("-C" in symbol or "-P" in symbol) else "FUTURES",
                    )
                )

            data.open_positions = open_items
            data.unrealized_pnl = round(total_unrealized, 2)
            data.realized_pnl_today = round(total_realized_today, 2)
            data.is_authenticated = True

        except Exception as e:
            err_msg = str(e)
            logger.error(f"Error querying {self.account_label}: {err_msg}")
            data.is_authenticated = False
            data.error = err_msg

        return data
