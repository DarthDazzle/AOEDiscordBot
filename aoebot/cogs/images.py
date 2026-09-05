"""Image generation (pollinations.ai) and static media commands."""

from __future__ import annotations

import logging
import random
import re
import time
from io import BytesIO
from urllib.parse import quote

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from aoebot import config

log = logging.getLogger(__name__)

# gen.pollinations.ai rejects anonymous generations (401); the legacy host still
# serves text-to-image without a key but ignores reference images.
KEYED_ENDPOINT = "https://gen.pollinations.ai/image/"
ANONYMOUS_ENDPOINT = "https://image.pollinations.ai/prompt/"
MENTION_RE = re.compile(r"<@!?(\d+)>")
ANONYMOUS_COOLDOWN = 15.0  # pollinations anonymous tier: one request per 15 s
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=240)


class ImageGenerationError(Exception):
    pass


def resolve_mentions(guild: discord.Guild | None, prompt: str) -> tuple[str, list[discord.Member]]:
    """Replace ``<@id>`` mentions with display names; return the mentioned members."""
    members: list[discord.Member] = []

    def replace(match: re.Match[str]) -> str:
        if guild is None:
            return match.group(0)
        member = guild.get_member(int(match.group(1)))
        if member is None:
            return match.group(0)
        if member not in members:
            members.append(member)
        return member.display_name

    return MENTION_RE.sub(replace, prompt).strip(), members


class Images(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._last_request = 0.0

    @property
    def session(self) -> aiohttp.ClientSession:
        session = getattr(self.bot, "http_session", None)
        if session is None:
            raise RuntimeError("HTTP session not initialised")
        return session

    async def generate(self, prompt: str, model: str, references: list[str]) -> tuple[bytes, str]:
        params: dict[str, str] = {
            "model": model,
            "width": "1024",
            "height": "1024",
            "nologo": "true",
            "seed": str(random.randrange(1, 2**31)),
        }
        if references:
            params["image"] = "|".join(references)
        headers = {}
        if config.POLLINATIONS_API_KEY:
            headers["Authorization"] = f"Bearer {config.POLLINATIONS_API_KEY}"
            endpoint = KEYED_ENDPOINT
        else:
            endpoint = ANONYMOUS_ENDPOINT
        url = endpoint + quote(prompt, safe="")
        async with self.session.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT) as resp:
            if resp.status != 200:
                body = (await resp.text())[:300]
                raise ImageGenerationError(f"{model}: HTTP {resp.status} {body}")
            content_type = resp.headers.get("Content-Type", "image/jpeg")
            return await resp.read(), content_type

    @app_commands.command(
        name="skapa",
        description="Skapar bilder med AI. @-nämn folk (välj i popupen) så används deras avatarer.",
    )
    @app_commands.describe(
        prompt="Vad ska skapas? Skriv @ och välj personen i popupen, t.ex. '@Axel och @Seb slåss mot en drake'"
    )
    async def skapa_command(self, interaction: discord.Interaction, prompt: str) -> None:
        if not config.POLLINATIONS_API_KEY:
            wait = self._last_request + ANONYMOUS_COOLDOWN - time.monotonic()
            if wait > 0:
                await interaction.response.send_message(
                    f"Chilla, vänta {wait:.0f} s till.", ephemeral=True
                )
                return
        self._last_request = time.monotonic()
        await interaction.response.defer(thinking=True)

        clean_prompt, members = resolve_mentions(interaction.guild, prompt)
        references = [
            m.display_avatar.replace(size=512, static_format="png").url
            for m in members[: config.IMAGE_MAX_REFERENCES]
        ]
        if references and not config.POLLINATIONS_API_KEY:
            log.info("No POLLINATIONS_API_KEY; ignoring %d avatar references", len(references))
            references = []

        attempts = [(config.IMAGE_MODEL, references)]
        if config.IMAGE_FALLBACK_MODEL != config.IMAGE_MODEL:
            attempts.append((config.IMAGE_FALLBACK_MODEL, []))

        errors: list[str] = []
        for model, refs in attempts:
            try:
                data, content_type = await self.generate(clean_prompt, model, refs)
            except (ImageGenerationError, aiohttp.ClientError, TimeoutError) as e:
                log.warning("Image generation failed: %s", e)
                errors.append(str(e))
                continue
            ext = "png" if "png" in content_type else "jpg"
            note = f"-# {model}" + (f", {len(refs)} avatar(s)" if refs else "")
            if len(errors):
                note += " (fallback)"
            await interaction.followup.send(
                content=f"**{clean_prompt}**\n{note}",
                file=discord.File(BytesIO(data), filename=f"skapa.{ext}"),
            )
            return

        await interaction.followup.send(
            "Kunde inte skapa någon bild.\n```\n" + "\n".join(errors)[-1500:] + "\n```"
        )

    @app_commands.command(name="aunts", description="Sends you a message with two very nice aunts")
    async def aunts_command(self, interaction: discord.Interaction) -> None:
        await self.send_asset(interaction, "aunts.jpg", "Fina tanter.")

    @app_commands.command(name="taints", description="Sends you a message with all available taints")
    async def taints_command(self, interaction: discord.Interaction) -> None:
        await self.send_asset(interaction, "taints.mp4", "Fin stjärt.")

    async def send_asset(self, interaction: discord.Interaction, filename: str, reply: str) -> None:
        path = config.ASSETS_DIR / filename
        if not path.is_file():
            await interaction.response.send_message(f"{filename} saknas på servern.", ephemeral=True)
            return
        # Post the file as a plain channel message and acknowledge privately,
        # so the media shows up without the "used /command" header.
        await interaction.response.send_message(reply, ephemeral=True)
        if isinstance(interaction.channel, discord.abc.Messageable):
            await interaction.channel.send(file=discord.File(path))
