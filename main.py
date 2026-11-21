"""
main.py
=======
Production daemon for Discord Algo Dashboard.
Aggregates Zerodha (Kite) + Delta Exchange (Futures & Options) + Systemd on Raspberry Pi.
Maintains a single live-updating pinned Discord embed with interactive controls.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import discord

from config.settings import config
from collectors.base import DashboardSnapshot
from collectors.delta_collector import DeltaAccountCollector
from collectors.system_collector import SystemCollector
from collectors.zerodha_collector import ZerodhaCollector
from ui.embed_builder import DashboardEmbedBuilder
from ui.views import DashboardView

# Configure Structured Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("algo_dashboard")


class AlgoDashboardBot(discord.Client):
    """Discord Client that runs the live-refresh dashboard loop."""

    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)

        # Collectors
        self.system_collector = SystemCollector(config.services)

        # Initialize Zerodha Collector
        z_creds = config.get_zerodha_creds()
        self.zerodha_collector = ZerodhaCollector(
            api_key=z_creds["api_key"],
            access_token=z_creds["access_token"],
            portfolio_dir=config.nifty_portfolio_dir,
        )

        # Initialize Delta Futures Collector
        df_creds = config.get_delta_futures_creds()
        self.delta_futures_collector = DeltaAccountCollector(
            account_label="Delta Futures",
            api_key=df_creds["api_key"],
            api_secret=df_creds["api_secret"],
            base_url=df_creds["base_url"],
        )

        # Initialize Delta Options Collector
        dopt_creds = config.get_delta_options_creds()
        self.delta_options_collector = DeltaAccountCollector(
            account_label="Delta Short Straddle",
            api_key=dopt_creds["api_key"],
            api_secret=dopt_creds["api_secret"],
            base_url=dopt_creds["base_url"],
        )

        self.latest_snapshot: DashboardSnapshot = DashboardSnapshot()
        self.dashboard_message: Optional[discord.Message] = None
        self.view: Optional[DashboardView] = None
        self._loop_task: Optional[asyncio.Task] = None

    async def setup_hook(self) -> None:
        """Register persistent views so buttons work across bot restarts."""
        self.view = DashboardView(
            refresh_callback=self.collect_and_update,
            get_latest_snapshot=lambda: self.latest_snapshot,
        )
        self.add_view(self.view)

    async def on_ready(self) -> None:
        logger.info(f"✅ Discord Bot logged in as: {self.user} (ID: {self.user.id})")

        if not config.channel_id:
            logger.error("❌ DISCORD_CHANNEL_ID is not configured in .env! Cannot post dashboard.")
            return

        channel = self.get_channel(config.channel_id)
        if not channel:
            try:
                channel = await self.fetch_channel(config.channel_id)
            except Exception as e:
                logger.error(f"❌ Failed to find channel ID {config.channel_id}: {e}")
                return

        if not isinstance(channel, discord.TextChannel):
            logger.error(f"❌ Channel {config.channel_id} is not a text channel.")
            return

        # Find or initialize master dashboard message
        await self._init_dashboard_message(channel)

        # Start live background refresh loop
        if not self._loop_task or self._loop_task.done():
            self._loop_task = asyncio.create_task(self._background_refresh_loop())

    async def _init_dashboard_message(self, channel: discord.TextChannel) -> None:
        """Find existing pinned message or create a new one."""
        saved_msg_id = self._load_saved_message_id()

        if saved_msg_id:
            try:
                msg = await channel.fetch_message(saved_msg_id)
                self.dashboard_message = msg
                logger.info(f"📌 Re-attached to existing dashboard message ID: {saved_msg_id}")
                return
            except discord.NotFound:
                logger.warning("Saved dashboard message not found (deleted?). Creating new one.")
            except Exception as e:
                logger.warning(f"Error fetching saved message: {e}")

        # Post new dashboard message and pin it
        logger.info("Posting fresh dashboard embed to channel...")
        initial_embed = discord.Embed(
            title="⏳ Initializing Algo Dashboard...",
            description="Connecting to Zerodha Kite Connect and Delta Exchange...",
            color=0x33B5E5,
        )
        msg = await channel.send(embed=initial_embed, view=self.view)
        try:
            await msg.pin()
        except Exception as e:
            logger.warning(f"Could not pin message (check bot permissions): {e}")

        self.dashboard_message = msg
        self._save_message_id(msg.id)
        logger.info(f"📌 Dashboard posted and pinned! Message ID: {msg.id}")

    def _load_saved_message_id(self) -> Optional[int]:
        if config.state_file.exists():
            try:
                with open(config.state_file, "r") as f:
                    data = json.load(f)
                    return data.get("dashboard_message_id")
            except Exception:
                pass
        return None

    def _save_message_id(self, msg_id: int) -> None:
        config.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config.state_file, "w") as f:
            json.dump({"dashboard_message_id": msg_id, "updated_at": datetime.now().isoformat()}, f, indent=2)

    async def collect_and_update(self) -> DashboardSnapshot:
        """Collect all data across all 4 algos and edit the pinned embed."""
        # Refresh credentials in case daily auto-login generated a new Kite token
        z_creds = config.get_zerodha_creds()
        self.zerodha_collector.update_credentials(z_creds["api_key"], z_creds["access_token"])

        # Fetch data asynchronously using thread pool so network I/O doesn't block event loop
        loop = asyncio.get_running_loop()

        sys_metrics = await loop.run_in_executor(None, self.system_collector.get_metrics)
        ns_health = await loop.run_in_executor(
            None, self.system_collector.get_service_status, config.services["nifty_strike"]
        )
        np_health = await loop.run_in_executor(
            None, self.system_collector.get_service_status, config.services["nifty_portfolio"]
        )
        df_health = await loop.run_in_executor(
            None, self.system_collector.get_service_status, config.services["delta_futures"]
        )
        do_health = await loop.run_in_executor(
            None, self.system_collector.get_service_status, config.services["delta_options"]
        )

        z_data = await loop.run_in_executor(None, self.zerodha_collector.collect)
        z_data.nifty_strike_status = ns_health
        z_data.nifty_portfolio_status = np_health

        df_data = await loop.run_in_executor(None, self.delta_futures_collector.collect)
        df_data.service_status = df_health

        do_data = await loop.run_in_executor(None, self.delta_options_collector.collect)
        do_data.service_status = do_health

        snapshot = DashboardSnapshot(
            system=sys_metrics,
            zerodha=z_data,
            delta_futures=df_data,
            delta_options=do_data,
        )
        self.latest_snapshot = snapshot

        # Build embed
        embed = DashboardEmbedBuilder.build(snapshot)

        # Edit message in-place
        if self.dashboard_message:
            try:
                await self.dashboard_message.edit(embed=embed, view=self.view)
            except discord.NotFound:
                logger.warning("Dashboard message was deleted. Recreating...")
                channel = self.dashboard_message.channel
                if isinstance(channel, discord.TextChannel):
                    await self._init_dashboard_message(channel)
            except Exception as e:
                logger.error(f"Failed to edit dashboard embed: {e}")

        return snapshot

    async def _background_refresh_loop(self) -> None:
        """Background loop continuously refreshing the dashboard."""
        await self.wait_until_ready()
        logger.info(f"🔄 Starting background live refresh loop (Interval: {config.refresh_interval}s)")

        while not self.is_closed():
            try:
                await self.collect_and_update()
            except Exception as e:
                logger.error(f"Unexpected error in dashboard refresh loop: {e}", exc_info=True)

            await asyncio.sleep(config.refresh_interval)


def main():
    if not config.bot_token:
        logger.error("❌ DISCORD_BOT_TOKEN is missing! Please configure it in your .env file.")
        print("\n" + "=" * 65)
        print("ERROR: DISCORD_BOT_TOKEN is not set in .env")
        print("1. Copy .env.example to .env")
        print("2. Add your DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID")
        print("=" * 65 + "\n")
        sys.exit(1)

    bot = AlgoDashboardBot()
    try:
        bot.run(config.bot_token)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")


if __name__ == "__main__":
    main()
