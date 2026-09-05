"""Bot entry point."""

from __future__ import annotations

import asyncio
import logging
import sys

import aiohttp
import discord
from discord.ext import commands

from aoebot import config
from aoebot.cogs.images import Images
from aoebot.cogs.servers import Servers
from aoebot.cogs.taunts import Taunter

log = logging.getLogger(__name__)


class AoeBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True
        intents.voice_states = True
        intents.message_content = True
        # No prefix commands exist; everything is slash commands or raw messages.
        super().__init__(
            command_prefix=commands.when_mentioned,
            help_command=None,
            intents=intents,
        )
        self.http_session: aiohttp.ClientSession | None = None

    async def setup_hook(self) -> None:
        self.http_session = aiohttp.ClientSession()
        await self.add_cog(Taunter(self))
        await self.add_cog(Servers(self))
        await self.add_cog(Images(self))
        # Sync once per process, not on every on_ready (which fires on reconnect).
        synced = await self.tree.sync()
        log.info("Synced %d application commands", len(synced))

    async def on_ready(self) -> None:
        log.info("Logged in as %s (ID: %s)", self.user, self.user.id if self.user else "?")

    async def on_resumed(self) -> None:
        log.info("Session resumed")

    async def close(self) -> None:
        await super().close()
        if self.http_session is not None:
            await self.http_session.close()


async def wait_for_network(host: str = "discord.com", port: int = 443,
                           attempts: int = 60, delay: float = 5.0) -> bool:
    """Block until a TCP connection to Discord succeeds (useful right after boot)."""
    for attempt in range(1, attempts + 1):
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=5)
            writer.close()
            await writer.wait_closed()
            return True
        except (OSError, asyncio.TimeoutError):
            log.warning("Waiting for network... attempt %d/%d", attempt, attempts)
            await asyncio.sleep(delay)
    return False


def main() -> None:
    discord.utils.setup_logging(level=logging.INFO, root=True)

    if not config.TOKEN:
        log.error("DISCORD_API is not set (put it in .env or the environment)")
        sys.exit(1)
    if not discord.opus.is_loaded():
        try:
            discord.opus._load_default()  # noqa: SLF001 - discord.py does this lazily anyway
        except Exception:
            log.warning("libopus not found; voice playback will fail. Install libopus0 / opus.")

    if not asyncio.run(wait_for_network()):
        log.error("No network after repeated attempts, exiting")
        sys.exit(1)

    bot = AoeBot()
    # log_handler=None: logging already configured above.
    bot.run(config.TOKEN, log_handler=None)
