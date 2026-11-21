"""
ui/views.py
===========
Interactive Discord Buttons attached to the live pinned dashboard embed.
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
        super().__init__(timeout=None)  # Persistent view (never expires)
        self.refresh_callback = refresh_callback
        self.get_latest_snapshot = get_latest_snapshot

    @discord.ui.button(
        label="Refresh Now",
        style=discord.ButtonStyle.primary,
        emoji="🔄",
        custom_id="btn_refresh_dashboard",
    )
    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Immediately trigger fresh data collection and update embed."""
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
        """Send a detailed markdown breakdown of all open positions (visible only to user)."""
        snapshot = self.get_latest_snapshot()
        all_positions = []
        all_positions.extend(snapshot.zerodha.open_positions)
        all_positions.extend(snapshot.delta_futures.open_positions)
        all_positions.extend(snapshot.delta_options.open_positions)

        if not all_positions:
            await interaction.response.send_message(
                "ℹ️ **No active open positions** across Zerodha or Delta Exchange at this moment.",
                ephemeral=True,
            )
            return

        lines = ["### 📋 Comprehensive Open Positions Breakdown\n"]
        lines.append("| Exchange | Symbol | Side | Qty | Entry | Current | P&L |")
        lines.append("|---|---|---|---|---|---|---|")

        for p in all_positions:
            sym_curr = "₹" if p.exchange == "NSE" else "$"
            sign = "+" if p.pnl > 0 else ""
            lines.append(
                f"| `{p.exchange}` | **{p.symbol}** | `{p.side}` | `{p.quantity}` | "
                f"{sym_curr}{p.entry_price:,.1f} | {sym_curr}{p.current_price:,.1f} | "
                f"**{sign}{sym_curr}{p.pnl:,.2f}** ({p.pnl_pct}%) |"
            )

        text = "\n".join(lines)
        # Discord limit is 2000 chars per message
        if len(text) > 1900:
            text = text[:1900] + "\n...*(truncated)*"

        await interaction.response.send_message(text, ephemeral=True)

    @discord.ui.button(
        label="Pi Health",
        style=discord.ButtonStyle.success,
        emoji="🩺",
        custom_id="btn_pi_health",
    )
    async def btn_health(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Send detailed systemd & OS diagnostic card (ephemeral)."""
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
