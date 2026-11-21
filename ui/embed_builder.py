"""
ui/embed_builder.py
===================
Renders rich, color-coded Exchange-Wise Discord Embeds:
1. Zerodha (Stock Holdings + F&O Derivatives + MCX Commodities)
2. Delta Exchange - Futures Account
3. Delta Exchange - Options Account
4. Algo Daemons Telemetry (Systemd + Pi Health)
"""

from __future__ import annotations

from datetime import datetime
from typing import List

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
    """Constructs the Exchange-Wise master live dashboard Discord Embed."""

    @staticmethod
    def build(snapshot: DashboardSnapshot) -> discord.Embed:
        z = snapshot.zerodha
        d_fut = snapshot.delta_futures
        d_opt = snapshot.delta_options
        sys = snapshot.system

        # Determine overall color
        color = 0x00C851  # Emerald Green
        if (
            z.error
            or d_fut.error
            or d_opt.error
            or z.nifty_strike_status.status == "failed"
            or d_fut.service_status.status == "failed"
            or d_opt.service_status.status == "failed"
        ):
            color = 0xFF4444  # Red Alert
        elif (z.intraday_mtm < 0) or ((d_fut.unrealized_pnl + d_opt.unrealized_pnl) < 0):
            color = 0xFFBB33  # Amber / Warning

        ist_time_str = snapshot.timestamp.strftime("%H:%M:%S IST")
        date_str = snapshot.timestamp.strftime("%d %b %Y")

        embed = discord.Embed(
            title="📊 LIVE EXCHANGE ALGO MONITOR",
            description=f"**Node:** Raspberry Pi 5 • **Date:** {date_str} • **Live Sync:** {ist_time_str}",
            color=color,
            timestamp=snapshot.timestamp,
        )

        # -------------------------------------------------------------
        # System Hardware Telemetry
        # -------------------------------------------------------------
        temp_str = f"{sys.temperature_c:.1f}°C" if sys.temperature_c is not None else "N/A"
        embed.add_field(
            name="🖥️ Raspberry Pi Telemetry",
            value=(
                f"**CPU:** `{sys.cpu_percent:.1f}%`  |  "
                f"**RAM:** `{sys.ram_used_gb}/{sys.ram_total_gb} GB ({sys.ram_percent}%)`  |  "
                f"**Temp:** `{temp_str}`  |  "
                f"**Disk:** `{sys.disk_percent}%`"
            ),
            inline=False,
        )

        # -------------------------------------------------------------
        # 1. ZERODHA (Holdings + F&O + MCX Commodities)
        # -------------------------------------------------------------
        zerodha_sections: List[str] = []

        if not z.is_authenticated:
            zerodha_sections.append(f"⚠️ *Kite auth pending: {z.error or 'Waiting for token refresh'}*")
        else:
            # 1A. Stock Holdings
            if z.holdings:
                h_pnl_str = _format_currency(z.holdings_total_pnl, "₹")
                h_day_str = _format_currency(z.holdings_day_pnl, "₹")
                zerodha_sections.append(
                    f"📦 **Stock Holdings ({len(z.holdings)} stocks):**\n"
                    f"  Value: `₹{z.holdings_current_value:,.2f}` | P&L: `{h_pnl_str}` (Today: `{h_day_str}`)"
                )
            else:
                zerodha_sections.append("📦 **Stock Holdings:** No active CNC stocks")

            # 1B. F&O Positions (Options & Index Futures)
            if z.fno_positions:
                fno_lines = []
                for p in z.fno_positions:
                    pnl_str = _format_currency(p.pnl, "₹")
                    fno_lines.append(
                        f"  • **{p.side} {p.quantity:.0f}x {p.symbol}** ➔ `{pnl_str}` (LTP: ₹{p.current_price:,.1f})"
                    )
                zerodha_sections.append("📈 **F&O Derivatives:**\n" + "\n".join(fno_lines))
            else:
                zerodha_sections.append("📈 **F&O Derivatives:** None active")

            # 1C. Commodity Positions (MCX Futures - Gold, Crude, Silver)
            if z.commodity_positions:
                comm_lines = []
                for p in z.commodity_positions:
                    pnl_str = _format_currency(p.pnl, "₹")
                    comm_lines.append(
                        f"  • **{p.side} {p.quantity:.0f}x {p.symbol}** ➔ `{pnl_str}` (LTP: ₹{p.current_price:,.1f})"
                    )
                zerodha_sections.append("🪙 **MCX Commodities:**\n" + "\n".join(comm_lines))
            else:
                zerodha_sections.append("🪙 **MCX Commodities:** None active")

            # 1D. Totals & Margins
            mtm_str = _format_currency(z.intraday_mtm, "₹")
            realized_str = _format_currency(z.realized_pnl, "₹")
            zerodha_sections.append(
                f"💵 **Intraday MTM:** `{mtm_str}` | **Realized:** `{realized_str}`\n"
                f"💳 **Available Margin:** Equity: `₹{z.available_margin:,.2f}` | Commodity: `₹{z.commodity_margin:,.2f}`"
            )

        embed.add_field(
            name="🇮🇳 ZERODHA (Equity Holdings • F&O Options • MCX Commodities)",
            value="\n".join(zerodha_sections),
            inline=False,
        )

        # -------------------------------------------------------------
        # 2. DELTA EXCHANGE — FUTURES ACCOUNT
        # -------------------------------------------------------------
        fut_sections: List[str] = []
        fut_mode = "🧪 TESTNET" if d_fut.is_testnet else "⚡ LIVE"

        if not d_fut.is_authenticated:
            fut_sections.append(f"⚠️ *API Error: {d_fut.error or 'Check delta-exchange-alog/.env'}*")
        else:
            if d_fut.open_positions:
                for p in d_fut.open_positions:
                    pnl_str = _format_currency(p.pnl, "$")
                    fut_sections.append(
                        f"• **{p.side} {p.quantity} {p.symbol}** ➔ `{pnl_str}` (Mark: ${p.current_price:,.2f})"
                    )
            else:
                fut_sections.append("• No open futures contracts")

            fut_mtm_str = _format_currency(d_fut.unrealized_pnl, "$")
            fut_sections.append(
                f"**Futures MTM:** `{fut_mtm_str}` | **Wallet Equity:** `${d_fut.wallet_equity:,.2f}` (Avail: `${d_fut.available_balance:,.2f}`)"
            )

        embed.add_field(
            name=f"🌐 DELTA EXCHANGE — FUTURES ACCOUNT ({fut_mode})",
            value="\n".join(fut_sections),
            inline=False,
        )

        # -------------------------------------------------------------
        # 3. DELTA EXCHANGE — OPTIONS ACCOUNT
        # -------------------------------------------------------------
        opt_sections: List[str] = []
        opt_mode = "🧪 TESTNET" if d_opt.is_testnet else "⚡ LIVE"

        if not d_opt.is_authenticated:
            opt_sections.append(f"⚠️ *API Error: {d_opt.error or 'Check opt-algo/.env'}*")
        else:
            if d_opt.open_positions:
                for p in d_opt.open_positions:
                    pnl_str = _format_currency(p.pnl, "$")
                    opt_sections.append(
                        f"• **{p.side} {p.quantity:.0f}x {p.symbol}** ➔ `{pnl_str}`"
                    )
            else:
                opt_sections.append("• No active options positions (Daily Straddle scheduled @ 17:00 IST)")

            opt_mtm_str = _format_currency(d_opt.unrealized_pnl, "$")
            opt_sections.append(
                f"**Options MTM:** `{opt_mtm_str}` | **Wallet Equity:** `${d_opt.wallet_equity:,.2f}` (Avail: `${d_opt.available_balance:,.2f}`)"
            )

        embed.add_field(
            name=f"🌐 DELTA EXCHANGE — OPTIONS ACCOUNT ({opt_mode})",
            value="\n".join(opt_sections),
            inline=False,
        )

        # -------------------------------------------------------------
        # 4. ALGO DAEMONS STATUS
        # -------------------------------------------------------------
        embed.add_field(
            name="🤖 Background Algo Daemons (Systemd)",
            value=(
                f"• **Nifty Strike Engine:** {_status_dot(z.nifty_strike_status)}  |  "
                f"**Nifty Portfolio:** {_status_dot(z.nifty_portfolio_status)}\n"
                f"• **Delta Futures:** {_status_dot(d_fut.service_status)}  |  "
                f"**Delta Options:** {_status_dot(d_opt.service_status)}"
            ),
            inline=False,
        )

        # -------------------------------------------------------------
        # 5. Combined Financial Summary
        # -------------------------------------------------------------
        total_inr_intraday = z.intraday_mtm + z.realized_pnl
        total_usd_mtm = d_fut.unrealized_pnl + d_opt.unrealized_pnl

        embed.add_field(
            name="💰 COMBINED REAL-TIME P&L SUMMARY",
            value=(
                f"🇮🇳 **Zerodha Intraday P&L:** `{_format_currency(total_inr_intraday, '₹')}`  "
                f"*(Holdings Total P&L: {_format_currency(z.holdings_total_pnl, '₹')})*\n"
                f"🌐 **Delta Exchange P&L:** `{_format_currency(total_usd_mtm, '$')}` "
                f"*(Futures: {_format_currency(d_fut.unrealized_pnl, '$')}, Options: {_format_currency(d_opt.unrealized_pnl, '$')})*"
            ),
            inline=False,
        )

        embed.set_footer(text="Exchange-Wise Live Feed • Updates in-place every 20s")
        return embed
