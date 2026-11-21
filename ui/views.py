"""
ui/views.py
===========
Interactive Discord Buttons attached to the Exchange-Wise live dashboard embed.
Renders clean, polished, human-readable Discord Embeds for detailed positions.
"""

from __future__ import annotations

import logging
from typing import Callable, Coroutine, Any, List

import discord

from collectors.base import DashboardSnapshot, PositionItem, HoldingItem

logger = logging.getLogger(__name__)


def _fmt_curr(val: float, sym: str = "₹") -> str:
    """Format currency with sign before the symbol: +₹500.00 or -₹500.00."""
    sign = "+" if val > 0 else ("-" if val < 0 else "")
    return f"{sign}{sym}{abs(val):,.2f}"


def _fmt_qty(qty: float) -> str:
    """Clean integer or decimal quantity."""
    abs_q = abs(qty)
    return f"{int(abs_q):,}" if abs_q.is_integer() else f"{abs_q:,.2f}"


def _dot(val: float) -> str:
    """Return green/red indicator dot."""
    if val > 0:
        return "🟢"
    elif val < 0:
        return "🔴"
    return "⚪"


class DashboardView(discord.ui.View):
    """View providing interactive buttons below the pinned dashboard message."""

    def __init__(
        self,
        refresh_callback: Callable[[], Coroutine[Any, Any, DashboardSnapshot]],
        get_latest_snapshot: Callable[[], DashboardSnapshot],
    ):
        super().__init__(timeout=None)
        self.refresh_callback = refresh_callback
        self.get_latest_snapshot = get_latest_snapshot

    @discord.ui.button(
        label="Refresh Now",
        style=discord.ButtonStyle.primary,
        emoji="🔄",
        custom_id="btn_refresh_dashboard",
    )
    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            snapshot = await self.refresh_callback()
            await interaction.followup.send(
                f"✅ Dashboard refreshed successfully at `{snapshot.timestamp.strftime('%H:%M:%S IST')}`.",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Error handling manual refresh: {e}")
            await interaction.followup.send(f"❌ Failed to refresh: {e}", ephemeral=True)

    @discord.ui.button(
        label="View All Positions",
        style=discord.ButtonStyle.secondary,
        emoji="📋",
        custom_id="btn_view_positions",
    )
    async def btn_positions(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Send a beautifully formatted, highly legible card of all positions & holdings."""
        snapshot = self.get_latest_snapshot()
        z = snapshot.zerodha
        d_fut = snapshot.delta_futures
        d_opt = snapshot.delta_options

        embed = discord.Embed(
            title="📋 Comprehensive Portfolio & Positions Breakdown",
            description=f"**Node:** Raspberry Pi 5 • **As of:** {snapshot.timestamp.strftime('%H:%M:%S IST')}",
            color=0x33B5E5,
        )

        has_any_data = False

        # -------------------------------------------------------------
        # 1. Zerodha Stock Holdings
        # -------------------------------------------------------------
        if z.holdings:
            has_any_data = True
            h_lines: List[str] = []
            for h in z.holdings[:12]:
                h_lines.append(
                    f"{_dot(h.pnl)} **{h.symbol}** ({_fmt_qty(h.quantity)} shares)\n"
                    f"   Avg: ₹{h.average_price:,.1f} ➔ CMP: ₹{h.last_price:,.1f} • **{_fmt_curr(h.pnl, '₹')}** ({h.pnl_pct:+.1f}%)"
                )
            if len(z.holdings) > 12:
                h_lines.append(f"*... and {len(z.holdings) - 12} more holdings.*")

            total_h_pnl = _fmt_curr(z.holdings_total_pnl, "₹")
            field_name = f"🇮🇳 Zerodha Equity Holdings ({len(z.holdings)} stocks • {total_h_pnl})"
            embed.add_field(name=field_name, value="\n".join(h_lines), inline=False)

        # -------------------------------------------------------------
        # 2. Zerodha MCX Commodities
        # -------------------------------------------------------------
        if z.commodity_positions:
            has_any_data = True
            comm_lines: List[str] = []
            comm_total_pnl = sum(p.pnl for p in z.commodity_positions)
            for p in z.commodity_positions:
                side_label = "BUY" if p.quantity > 0 else "SELL"
                comm_lines.append(
                    f"{_dot(p.pnl)} **{p.symbol}** • `{side_label} {_fmt_qty(p.quantity)}`\n"
                    f"   Entry: ₹{p.entry_price:,.1f} ➔ CMP: ₹{p.current_price:,.1f} • **{_fmt_curr(p.pnl, '₹')}**"
                )
            field_name = f"🪙 Zerodha MCX Commodities ({len(z.commodity_positions)} contracts • {_fmt_curr(comm_total_pnl, '₹')})"
            embed.add_field(name=field_name, value="\n".join(comm_lines), inline=False)

        # -------------------------------------------------------------
        # 3. Zerodha F&O Derivatives (NFO Options/Futures)
        # -------------------------------------------------------------
        if z.fno_positions:
            has_any_data = True
            fno_lines: List[str] = []
            fno_total_pnl = sum(p.pnl for p in z.fno_positions)
            for p in z.fno_positions:
                side_label = "BUY" if p.quantity > 0 else "SELL"
                fno_lines.append(
                    f"{_dot(p.pnl)} **{p.symbol}** • `{side_label} {_fmt_qty(p.quantity)}`\n"
                    f"   Entry: ₹{p.entry_price:,.1f} ➔ LTP: ₹{p.current_price:,.1f} • **{_fmt_curr(p.pnl, '₹')}**"
                )
            field_name = f"📈 Zerodha F&O Derivatives ({len(z.fno_positions)} positions • {_fmt_curr(fno_total_pnl, '₹')})"
            embed.add_field(name=field_name, value="\n".join(fno_lines), inline=False)

        # -------------------------------------------------------------
        # 4. Delta Exchange — Futures Account
        # -------------------------------------------------------------
        if d_fut.open_positions:
            has_any_data = True
            fut_lines: List[str] = []
            fut_total_pnl = sum(p.pnl for p in d_fut.open_positions)
            for p in d_fut.open_positions:
                side_label = p.side.upper()
                fut_lines.append(
                    f"{_dot(p.pnl)} **{p.symbol}** • `{side_label} {_fmt_qty(p.quantity)}`\n"
                    f"   Entry: ${p.entry_price:,.2f} ➔ Mark: ${p.current_price:,.2f} • **{_fmt_curr(p.pnl, '$')}**"
                )
            field_name = f"🌐 Delta Crypto Futures ({len(d_fut.open_positions)} positions • {_fmt_curr(fut_total_pnl, '$')})"
            embed.add_field(name=field_name, value="\n".join(fut_lines), inline=False)

        # -------------------------------------------------------------
        # 5. Delta Exchange — Options Account
        # -------------------------------------------------------------
        if d_opt.open_positions:
            has_any_data = True
            opt_lines: List[str] = []
            opt_total_pnl = sum(p.pnl for p in d_opt.open_positions)
            for p in d_opt.open_positions:
                side_label = p.side.upper()
                opt_lines.append(
                    f"{_dot(p.pnl)} **{p.symbol}** • `{side_label} {_fmt_qty(p.quantity)}`\n"
                    f"   Entry: ${p.entry_price:,.2f} ➔ Mark: ${p.current_price:,.2f} • **{_fmt_curr(p.pnl, '$')}**"
                )
            field_name = f"🌐 Delta Crypto Options ({len(d_opt.open_positions)} positions • {_fmt_curr(opt_total_pnl, '$')})"
            embed.add_field(name=field_name, value="\n".join(opt_lines), inline=False)

        if not has_any_data:
            await interaction.response.send_message(
                "ℹ️ **No active positions or holdings** currently open across Zerodha or Delta Exchange.",
                ephemeral=True,
            )
            return

        embed.set_footer(text="Private view • Only visible to you")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="Pi Health",
        style=discord.ButtonStyle.success,
        emoji="🩺",
        custom_id="btn_pi_health",
    )
    async def btn_health(self, interaction: discord.Interaction, button: discord.ui.Button):
        snapshot = self.get_latest_snapshot()
        sys = snapshot.system

        embed = discord.Embed(
            title="🩺 Raspberry Pi 5 System Diagnostics",
            color=0x33B5E5,
            timestamp=snapshot.timestamp,
        )

        temp_str = f"{sys.temperature_c:.1f}°C" if sys.temperature_c is not None else "N/A"
        embed.add_field(
            name="🖥️ Hardware Utilization",
            value=(
                f"• **CPU Load:** `{sys.cpu_percent:.1f}%`\n"
                f"• **RAM Memory:** `{sys.ram_used_gb} / {sys.ram_total_gb} GB` ({sys.ram_percent}%)\n"
                f"• **Disk Usage:** `{sys.disk_percent}%`\n"
                f"• **SoC Temperature:** `{temp_str}`"
            ),
            inline=False,
        )

        z = snapshot.zerodha
        d_fut = snapshot.delta_futures
        d_opt = snapshot.delta_options

        embed.add_field(
            name="🤖 Algo Daemon Services",
            value=(
                f"• `{z.nifty_strike_status.name}`: `{z.nifty_strike_status.status.upper()}`\n"
                f"• `{z.nifty_portfolio_status.name}`: `{z.nifty_portfolio_status.status.upper()}`\n"
                f"• `{d_fut.service_status.name}`: `{d_fut.service_status.status.upper()}`\n"
                f"• `{d_opt.service_status.name}`: `{d_opt.service_status.status.upper()}`"
            ),
            inline=False,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)
