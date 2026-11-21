"""
ui/views.py
===========
Interactive Discord Buttons attached to the Exchange-Wise live dashboard embed.
"""

from __future__ import annotations

import logging
from typing import Callable, Coroutine, Any

import discord

from collectors.base import DashboardSnapshot

logger = logging.getLogger(__name__)


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
        """Send a detailed categorized breakdown of all holdings & positions across all exchanges."""
        snapshot = self.get_latest_snapshot()
        z = snapshot.zerodha
        d_fut = snapshot.delta_futures
        d_opt = snapshot.delta_options

        lines = ["### 📋 Comprehensive Exchange-Wise Breakdown\n"]

        # 1. Zerodha Holdings
        if z.holdings:
            lines.append("**🇮🇳 Zerodha Equity Holdings (CNC):**")
            lines.append("| Symbol | Qty | Avg Price | Current | P&L |")
            lines.append("|---|---|---|---|---|")
            for h in z.holdings[:15]:  # Top 15 holdings to fit Discord message limit
                sign = "+" if h.pnl > 0 else ""
                lines.append(
                    f"| **{h.symbol}** | {h.quantity:.0f} | ₹{h.average_price:,.1f} | ₹{h.last_price:,.1f} | {sign}₹{h.pnl:,.2f} ({h.pnl_pct}%) |"
                )
            if len(z.holdings) > 15:
                lines.append(f"... and {len(z.holdings) - 15} more holdings.\n")
            else:
                lines.append("")

        # 2. Zerodha F&O Derivatives
        if z.fno_positions:
            lines.append("**🇮🇳 Zerodha F&O Derivatives:**")
            lines.append("| Symbol | Side | Qty | Entry | Current | P&L |")
            lines.append("|---|---|---|---|---|---|")
            for p in z.fno_positions:
                sign = "+" if p.pnl > 0 else ""
                lines.append(
                    f"| **{p.symbol}** | `{p.side}` | {p.quantity:.0f} | ₹{p.entry_price:,.1f} | ₹{p.current_price:,.1f} | {sign}₹{p.pnl:,.2f} |"
                )
            lines.append("")

        # 3. Zerodha MCX Commodities
        if z.commodity_positions:
            lines.append("**🪙 Zerodha MCX Commodities:**")
            lines.append("| Symbol | Side | Qty | Entry | Current | P&L |")
            lines.append("|---|---|---|---|---|---|")
            for p in z.commodity_positions:
                sign = "+" if p.pnl > 0 else ""
                lines.append(
                    f"| **{p.symbol}** | `{p.side}` | {p.quantity:.0f} | ₹{p.entry_price:,.1f} | ₹{p.current_price:,.1f} | {sign}₹{p.pnl:,.2f} |"
                )
            lines.append("")

        # 4. Delta Futures
        if d_fut.open_positions:
            lines.append("**🌐 Delta Exchange — Futures Account:**")
            lines.append("| Symbol | Side | Qty | Entry | Mark | P&L |")
            lines.append("|---|---|---|---|---|---|")
            for p in d_fut.open_positions:
                sign = "+" if p.pnl > 0 else ""
                lines.append(
                    f"| **{p.symbol}** | `{p.side}` | {p.quantity} | ${p.entry_price:,.2f} | ${p.current_price:,.2f} | {sign}${p.pnl:,.2f} |"
                )
            lines.append("")

        # 5. Delta Options
        if d_opt.open_positions:
            lines.append("**🌐 Delta Exchange — Options Account:**")
            lines.append("| Symbol | Side | Qty | Entry | Mark | P&L |")
            lines.append("|---|---|---|---|---|---|")
            for p in d_opt.open_positions:
                sign = "+" if p.pnl > 0 else ""
                lines.append(
                    f"| **{p.symbol}** | `{p.side}` | {p.quantity:.0f} | ${p.entry_price:,.2f} | ${p.current_price:,.2f} | {sign}${p.pnl:,.2f} |"
                )
            lines.append("")

        if (
            not z.holdings
            and not z.fno_positions
            and not z.commodity_positions
            and not d_fut.open_positions
            and not d_opt.open_positions
        ):
            await interaction.response.send_message(
                "ℹ️ **No active positions or holdings** found across Zerodha or Delta Exchange.",
                ephemeral=True,
            )
            return

        text = "\n".join(lines)
        if len(text) > 1900:
            text = text[:1900] + "\n...*(truncated to fit message limit)*"

        await interaction.response.send_message(text, ephemeral=True)

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
            name="Hardware Resources",
            value=(
                f"• **CPU Usage:** `{sys.cpu_percent}%`\n"
                f"• **RAM Memory:** `{sys.ram_used_gb} / {sys.ram_total_gb} GB ({sys.ram_percent}%)`\n"
                f"• **Disk Usage:** `{sys.disk_percent}%`\n"
                f"• **SoC Temperature:** `{temp_str}`"
            ),
            inline=False,
        )

        z = snapshot.zerodha
        d_fut = snapshot.delta_futures
        d_opt = snapshot.delta_options

        embed.add_field(
            name="Systemd Service Daemon Health",
            value=(
                f"• `{z.nifty_strike_status.name}`: `{z.nifty_strike_status.status.upper()}`\n"
                f"• `{z.nifty_portfolio_status.name}`: `{z.nifty_portfolio_status.status.upper()}`\n"
                f"• `{d_fut.service_status.name}`: `{d_fut.service_status.status.upper()}`\n"
                f"• `{d_opt.service_status.name}`: `{d_opt.service_status.status.upper()}`"
            ),
            inline=False,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)
