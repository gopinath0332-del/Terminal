"""
ui/embed_builder.py
===================
Renders rich, color-coded Discord Embeds for the live algo monitor dashboard.
"""

from __future__ import annotations

from datetime import datetime
from typing import Tuple

import discord

from collectors.base import DashboardSnapshot, PositionItem, ServiceHealth


def _status_dot(health: ServiceHealth) -> str:
    """Return status emoji indicator."""
    status = health.status.lower()
    if status in ("active", "running"):
        return "🟢 `ACTIVE`"
    if status in ("waiting", "dev_mode", "inactive"):
        return "🟡 `WAITING`"
    if status in ("failed", "error", "degraded"):
        return "🔴 `FAILED`"
    return "⚪ `UNKNOWN`"


def _format_currency(val: float, currency_sym: str = "₹") -> str:
    """Format positive/negative currency strings."""
    sign = "+" if val > 0 else ""
    return f"{sign}{currency_sym}{val:,.2f}"


class DashboardEmbedBuilder:
    """Constructs the master live dashboard Discord Embed."""

    @staticmethod
    def build(snapshot: DashboardSnapshot) -> discord.Embed:
        # Determine overall color
        color = 0x00C851  # Emerald Green
        if (
            snapshot.zerodha.error
            or snapshot.delta_futures.error
            or snapshot.delta_options.error
            or snapshot.zerodha.nifty_strike_status.status == "failed"
            or snapshot.delta_futures.service_status.status == "failed"
            or snapshot.delta_options.service_status.status == "failed"
        ):
            color = 0xFF4444  # Red Alert
        elif (
            snapshot.zerodha.intraday_pnl < 0
            or (snapshot.delta_futures.unrealized_pnl + snapshot.delta_options.unrealized_pnl) < 0
        ):
            color = 0xFFBB33  # Amber / Warning

        ist_time_str = snapshot.timestamp.strftime("%H:%M:%S IST")
        date_str = snapshot.timestamp.strftime("%d %b %Y")

        embed = discord.Embed(
            title="📊 ALGO TRADING PRODUCTION MONITOR",
            description=f"**Node:** Raspberry Pi 5 • **Date:** {date_str} • **Live Sync:** {ist_time_str}",
            color=color,
            timestamp=snapshot.timestamp,
        )

        # -------------------------------------------------------------
        # System Hardware Bar
        # -------------------------------------------------------------
        sys = snapshot.system
        temp_str = f"{sys.temperature_c:.1f}°C" if sys.temperature_c is not None else "N/A"
        embed.add_field(
            name="🖥️ System Hardware Telemetry",
            value=(
                f"**CPU:** `{sys.cpu_percent:.1f}%`  |  "
                f"**RAM:** `{sys.ram_used_gb}/{sys.ram_total_gb} GB ({sys.ram_percent}%)`  |  "
                f"**Temp:** `{temp_str}`  |  "
                f"**Disk:** `{sys.disk_percent}%`"
            ),
            inline=False,
        )

        # -------------------------------------------------------------
        # 1. NIFTY STRIKE ENGINE (Zerodha)
        # -------------------------------------------------------------
        z = snapshot.zerodha
        ns_dot = _status_dot(z.nifty_strike_status)
        strike_positions = [
            p for p in z.open_positions if "NIFTY" in p.symbol.upper() and p.product_type != "CNC"
        ]

        if strike_positions:
            pos_lines = []
            for sp in strike_positions:
                pnl_str = _format_currency(sp.pnl, "₹")
                pos_lines.append(
                    f"• **{sp.side} {sp.quantity:.0f}x {sp.symbol}**\n"
                    f"  Entry: ₹{sp.entry_price:,.1f} ➔ LTP: ₹{sp.current_price:,.1f} ({pnl_str})"
                )
            strike_details = "\n".join(pos_lines)
        elif not z.is_authenticated:
            strike_details = f"⚠️ *Auth Pending / Access token not active*"
        else:
            strike_details = "• No open intraday position (Monitoring 5m candles)"

        embed.add_field(
            name=f"1️⃣ Nifty Strike Engine (Zerodha)  {ns_dot}",
            value=(
                f"**Service:** `{z.nifty_strike_status.name}`\n"
                f"{strike_details}\n"
                f"**Intraday MTM:** `{_format_currency(z.intraday_pnl, '₹')}`"
            ),
            inline=False,
        )

        # -------------------------------------------------------------
        # 2. NIFTY 500 PORTFOLIO (Zerodha Swing)
        # -------------------------------------------------------------
        np_dot = _status_dot(z.nifty_portfolio_status)
        embed.add_field(
            name=f"2️⃣ Nifty 500 Breakout Portfolio (Zerodha)  {np_dot}",
            value=(
                f"**Schedule:** Daily at `15:45 IST` (`{z.nifty_portfolio_status.name}`)\n"
                f"**Active Slots:** `{z.portfolio_slots_used}/{z.portfolio_max_slots}` stocks\n"
                f"**Portfolio Unrealized:** `{_format_currency(z.portfolio_unrealized_pnl, '₹')}`  |  "
                f"**Cash:** `₹{z.available_margin:,.2f}`"
            ),
            inline=False,
        )

        # -------------------------------------------------------------
        # 3. DELTA SHORT STRADDLE (Delta Options)
        # -------------------------------------------------------------
        d_opt = snapshot.delta_options
        d_opt_dot = _status_dot(d_opt.service_status)
        mode_badge = "🧪 TESTNET" if d_opt.is_testnet else "⚡ LIVE"

        if d_opt.open_positions:
            opt_lines = []
            for op in d_opt.open_positions:
                pnl_str = _format_currency(op.pnl, "$")
                opt_lines.append(
                    f"• **{op.side} {op.quantity:.0f}x {op.symbol}** ({pnl_str})"
                )
            opt_details = "\n".join(opt_lines)
        elif not d_opt.is_authenticated:
            opt_details = f"⚠️ *Check API keys in {d_opt.account_label}*"
        else:
            opt_details = "• No active straddle (Scheduled entry: 17:00 IST)"

        embed.add_field(
            name=f"3️⃣ Delta Short Straddle ({mode_badge})  {d_opt_dot}",
            value=(
                f"**Service:** `{d_opt.service_status.name}`\n"
                f"{opt_details}\n"
                f"**Options MTM:** `{_format_currency(d_opt.unrealized_pnl, '$')}`  |  "
                f"**Wallet Equity:** `${d_opt.wallet_equity:,.2f}`"
            ),
            inline=False,
        )

        # -------------------------------------------------------------
        # 4. DELTA CRYPTO FUTURES (Delta Multi-Strategy)
        # -------------------------------------------------------------
        d_fut = snapshot.delta_futures
        d_fut_dot = _status_dot(d_fut.service_status)
        fut_mode_badge = "🧪 TESTNET" if d_fut.is_testnet else "⚡ LIVE"

        if d_fut.open_positions:
            fut_lines = []
            for fp in d_fut.open_positions:
                pnl_str = _format_currency(fp.pnl, "$")
                fut_lines.append(
                    f"• **{fp.side} {fp.quantity} {fp.symbol}** ➔ `{pnl_str}`"
                )
            fut_details = "\n".join(fut_lines)
        elif not d_fut.is_authenticated:
            fut_details = f"⚠️ *Check API keys in {d_fut.account_label}*"
        else:
            fut_details = "• No open futures positions (Scanning multi-coins)"

        embed.add_field(
            name=f"4️⃣ Delta Crypto Futures ({fut_mode_badge})  {d_fut_dot}",
            value=(
                f"**Service:** `{d_fut.service_status.name}`\n"
                f"{fut_details}\n"
                f"**Futures MTM:** `{_format_currency(d_fut.unrealized_pnl, '$')}`  |  "
                f"**Wallet Equity:** `${d_fut.wallet_equity:,.2f}`"
            ),
            inline=False,
        )

        # -------------------------------------------------------------
        # 5. Combined Financial Summary Footer
        # -------------------------------------------------------------
        total_inr = z.intraday_pnl + z.portfolio_unrealized_pnl
        total_usd = d_opt.unrealized_pnl + d_fut.unrealized_pnl

        embed.add_field(
            name="💰 COMBINED TOTAL P&L TODAY",
            value=(
                f"🇮🇳 **Indian Markets (NSE):** `{_format_currency(total_inr, '₹')}`\n"
                f"🌐 **Crypto Markets (Delta):** `{_format_currency(total_usd, '$')}`"
            ),
            inline=False,
        )

        embed.set_footer(text="Auto-updating live in-place • Click buttons below for instant action")
        return embed
