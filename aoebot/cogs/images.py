"""Image generation (Gemini, pollinations.ai) and static media commands."""

from __future__ import annotations

import base64
import json
import logging
import random
import re
import time
from datetime import date
from io import BytesIO
from pathlib import Path
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
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
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


def current_week() -> str:
    year, week, _ = date.today().isocalendar()
    return f"{year}-W{week:02d}"


class WeeklyUsage:
    """Counts paid generations per ISO week, persisted as a small JSON file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.week = current_week()
        self.total = 0
        self.users: dict[str, int] = {}
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return
        except (OSError, ValueError) as e:
            log.warning("Could not read %s: %s", self.path, e)
            return
        if data.get("week") == self.week:
            self.total = int(data.get("total", 0))
            self.users = {str(k): int(v) for k, v in data.get("users", {}).items()}

    def _rollover(self) -> None:
        week = current_week()
        if week != self.week:
            self.week, self.total, self.users = week, 0, {}

    def remaining(self, user_id: int) -> int:
        """Paid images this user may still generate this week."""
        self._rollover()
        left = 10**9
        if config.IMAGE_WEEKLY_LIMIT > 0:
            left = min(left, config.IMAGE_WEEKLY_LIMIT - self.total)
        if config.IMAGE_USER_WEEKLY_LIMIT > 0:
            left = min(left, config.IMAGE_USER_WEEKLY_LIMIT - self.users.get(str(user_id), 0))
        return max(left, 0)

    def record(self, user_id: int) -> None:
        self._rollover()
        self.total += 1
        self.users[str(user_id)] = self.users.get(str(user_id), 0) + 1
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"week": self.week, "total": self.total, "users": self.users}, f, indent=1)
        tmp.replace(self.path)


class Images(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._last_request = 0.0
        self.usage = WeeklyUsage(config.DATA_DIR / "image_usage.json")
        if config.GEMINI_API_KEY:
            log.info("/skapa uses %s at %s, %d used of %d this week", config.GEMINI_IMAGE_MODEL,
                     config.GEMINI_IMAGE_SIZE, self.usage.total, config.IMAGE_WEEKLY_LIMIT)

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

    async def fetch_avatar(self, member: discord.Member) -> bytes | None:
        try:
            return await member.display_avatar.replace(size=512, static_format="png").read()
        except discord.HTTPException as e:
            log.warning("Could not fetch avatar for %s: %s", member, e)
            return None

    async def generate_gemini(self, prompt: str, members: list[discord.Member]) -> tuple[bytes, str, int]:
        """Generate with the Gemini Interactions API; avatars go in as character references.

        Returns (image bytes, mime type, number of references used).
        """
        model = config.GEMINI_IMAGE_MODEL
        # Interleave label and image so each avatar is bound to its name by
        # adjacency rather than by "image N is ..." counting.
        items: list[dict[str, str]] = [{"type": "text", "text": prompt}]
        refs = 0
        for member in members:
            avatar = await self.fetch_avatar(member)
            if avatar is None:
                continue
            items.append({"type": "text", "text": f"This is {member.display_name}:"})
            items.append({"type": "image", "mime_type": "image/png",
                          "data": base64.b64encode(avatar).decode("ascii")})
            refs += 1
        if refs:
            items.append({"type": "text", "text": (
                "The pictures above are the profile pictures of the people named in the prompt. "
                "Depict each named person so they are clearly recognisable from their picture."
            )})
        body = {
            "model": model,
            "input": items,
            "response_format": {
                "type": "image",
                "mime_type": "image/jpeg",
                "aspect_ratio": "1:1",
                "image_size": config.GEMINI_IMAGE_SIZE,
            },
        }
        headers = {"x-goog-api-key": config.GEMINI_API_KEY or "", "Content-Type": "application/json"}
        async with self.session.post(GEMINI_ENDPOINT, json=body, headers=headers,
                                     timeout=REQUEST_TIMEOUT) as resp:
            payload = await resp.json(content_type=None)
            if resp.status != 200:
                detail = None
                if isinstance(payload, dict):
                    detail = payload.get("error", {}).get("message")
                raise ImageGenerationError(f"{model}: HTTP {resp.status} {detail or str(payload)[:300]}")

        # Response shape (verified live): steps[] -> {"type": "model_output",
        # "content": [{"type": "image", "mime_type", "data"}]}; a refusal comes
        # back as a "text" content item instead.
        texts: list[str] = []
        for step in payload.get("steps") or []:
            if step.get("type") != "model_output":
                continue
            for item in step.get("content") or []:
                if item.get("type") == "image" and item.get("data"):
                    usage = payload.get("usage") or {}
                    log.info("Gemini %s: %s tokens out, %s in", model,
                             usage.get("total_output_tokens"), usage.get("total_input_tokens"))
                    return base64.b64decode(item["data"]), item.get("mime_type", "image/jpeg"), refs
                if item.get("type") == "text":
                    texts.append(item.get("text", ""))
        errors = "; ".join(e.get("message", "") for e in payload.get("errors") or [])
        detail = errors or " ".join(texts).strip() or f"status={payload.get('status')} keys={sorted(payload)}"
        raise ImageGenerationError(f"{model}: no image returned ({detail[:300]})")

    @staticmethod
    async def send_image(interaction: discord.Interaction, prompt: str, note: str,
                         data: bytes, content_type: str) -> None:
        ext = "png" if "png" in content_type else "jpg"
        await interaction.followup.send(
            content=f"**{prompt}**\n-# {note}",
            file=discord.File(BytesIO(data), filename=f"skapa.{ext}"),
        )

    @app_commands.command(
        name="skapa",
        description="Skapar bilder med AI. @-nämn folk (välj i popupen) så används deras avatarer.",
    )
    @app_commands.describe(
        prompt="Vad ska skapas? Skriv @ och välj personen i popupen, t.ex. '@Axel och @Seb slåss mot en drake'"
    )
    async def skapa_command(self, interaction: discord.Interaction, prompt: str) -> None:
        use_gemini = bool(config.GEMINI_API_KEY)
        if use_gemini:
            if self.usage.remaining(interaction.user.id) <= 0:
                await interaction.response.send_message(
                    "Veckans bildbudget är slut. Kvoten nollställs på måndag.", ephemeral=True
                )
                return
        elif not config.POLLINATIONS_API_KEY:
            wait = self._last_request + ANONYMOUS_COOLDOWN - time.monotonic()
            if wait > 0:
                await interaction.response.send_message(
                    f"Chilla, vänta {wait:.0f} s till.", ephemeral=True
                )
                return
        self._last_request = time.monotonic()
        await interaction.response.defer(thinking=True)

        clean_prompt, members = resolve_mentions(interaction.guild, prompt)
        members = members[: config.IMAGE_MAX_REFERENCES]
        errors: list[str] = []

        if use_gemini:
            try:
                data, content_type, refs = await self.generate_gemini(clean_prompt, members)
            except (ImageGenerationError, aiohttp.ClientError, TimeoutError, ValueError) as e:
                log.warning("Gemini generation failed: %s", e)
                errors.append(str(e))
            else:
                self.usage.record(interaction.user.id)
                note = config.GEMINI_IMAGE_MODEL + (f", {refs} avatar(s)" if refs else "")
                if config.IMAGE_WEEKLY_LIMIT or config.IMAGE_USER_WEEKLY_LIMIT:
                    note += f", {self.usage.remaining(interaction.user.id)} kvar denna vecka"
                await self.send_image(interaction, clean_prompt, note, data, content_type)
                return

        # pollinations.ai, either as the only backend or as a free fallback
        references = [m.display_avatar.replace(size=512, static_format="png").url for m in members]
        if references and not config.POLLINATIONS_API_KEY:
            log.info("No POLLINATIONS_API_KEY; ignoring %d avatar references", len(references))
            references = []
        attempts = [(config.IMAGE_MODEL, references)]
        if config.IMAGE_FALLBACK_MODEL != config.IMAGE_MODEL:
            attempts.append((config.IMAGE_FALLBACK_MODEL, []))

        for model, refs in attempts:
            try:
                data, content_type = await self.generate(clean_prompt, model, refs)
            except (ImageGenerationError, aiohttp.ClientError, TimeoutError) as e:
                log.warning("Image generation failed: %s", e)
                errors.append(str(e))
                continue
            note = model + (f", {len(refs)} avatar(s)" if refs else "")
            if errors:
                note += " (fallback)"
            await self.send_image(interaction, clean_prompt, note, data, content_type)
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
