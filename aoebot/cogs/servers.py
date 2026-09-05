"""Game server status and control via docker compose."""

from __future__ import annotations

import asyncio
import logging
import random
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, tasks

from aoebot import config

log = logging.getLogger(__name__)

COMPOSE_FILENAMES = ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")


def resolve_compose_file(path: Path) -> Path | None:
    if path.is_file():
        return path
    if path.is_dir():
        for name in COMPOSE_FILENAMES:
            candidate = path / name
            if candidate.is_file():
                return candidate
    return None


async def run_compose(compose_file: Path, *args: str, timeout: float) -> tuple[int, str]:
    """Run ``docker compose -f <file> <args>`` without blocking the event loop."""
    proc = await asyncio.create_subprocess_exec(
        "docker", "compose", "-f", str(compose_file), *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return 124, f"timed out after {timeout:.0f}s"
    return proc.returncode or 0, out.decode(errors="replace").strip()


class Servers(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.servers: dict[str, Path] = {}
        for name, path in config.SERVERS.items():
            compose_file = resolve_compose_file(path)
            if compose_file is None:
                log.warning("COMPOSE_FILE_%s=%s: no compose file found", name.upper(), path)
                continue
            self.servers[name] = compose_file
        log.info("Configured servers: %s", ", ".join(sorted(self.servers)) or "none")
        self.running: set[str] = set()
        self.status_loop.start()

    async def cog_unload(self) -> None:
        self.status_loop.cancel()

    async def is_running(self, name: str) -> bool:
        code, out = await run_compose(self.servers[name], "ps", "--status", "running", "-q", timeout=30)
        if code != 0:
            log.warning("docker compose ps failed for %s (exit %d): %s", name, code, out[:300])
            return False
        return bool(out)

    async def refresh_running(self) -> set[str]:
        results = await asyncio.gather(*(self.is_running(n) for n in self.servers), return_exceptions=True)
        running: set[str] = set()
        for name, result in zip(self.servers, results):
            if isinstance(result, BaseException):
                log.warning("Status check failed for %s: %r", name, result)
            elif result:
                running.add(name)
        self.running = running
        return running

    async def update_status(self) -> str:
        running = await self.refresh_running()
        text = " | ".join(sorted(n.title() for n in running)) if running else random.choice(config.EUPHEMISMS)
        activity = discord.Activity(type=discord.ActivityType.competing, name=text)
        await self.bot.change_presence(status=discord.Status.online, activity=activity)
        return text

    @tasks.loop(seconds=60)
    async def status_loop(self) -> None:
        try:
            await self.update_status()
        except Exception:
            log.exception("update_status failed")

    @status_loop.before_loop
    async def before_status_loop(self) -> None:
        await self.bot.wait_until_ready()

    # ----------------------------------------------------------- slash commands

    @app_commands.command(name="status_update", description="Updates the status of the servers")
    async def status_update_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        text = await self.update_status()
        await interaction.followup.send(f"Status: {text}", ephemeral=True)

    async def server_autocomplete(self, interaction: discord.Interaction,
                                  current: str) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=name, value=name)
            for name in sorted(self.servers)
            if current.lower() in name
        ][:25]

    @app_commands.command(name="start", description="Start the specified server, hosted in docker")
    @app_commands.describe(server="Which server to start")
    @app_commands.autocomplete(server=server_autocomplete)
    async def start_command(self, interaction: discord.Interaction, server: str) -> None:
        name = server.lower().strip()
        if name not in self.servers:
            await interaction.response.send_message(
                f"Server not found. Known servers: {', '.join(sorted(self.servers)) or 'none'}",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        if await self.is_running(name):
            await interaction.followup.send(f"{name.title()} is already running", ephemeral=True)
            return
        log.info("%s requested start of %s", interaction.user, name)
        code, out = await run_compose(self.servers[name], "up", "-d", timeout=900)
        if code != 0:
            log.error("docker compose up failed for %s (exit %d): %s", name, code, out)
            await interaction.followup.send(
                f"Failed to start {name.title()} (exit {code}):\n```\n{out[-1500:] or 'no output'}\n```",
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            f"{name.title()} server booting up, might take a minute to start", ephemeral=True
        )
        await self.update_status()
