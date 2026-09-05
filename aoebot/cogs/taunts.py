"""Voice taunts: type a number in chat, the bot plays that sound in your voice channel."""

from __future__ import annotations

import asyncio
import json
import logging
import pickle
import random
import re
import time
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from aoebot import config

log = logging.getLogger(__name__)

AUDIO_SUFFIXES = {".mp3", ".ogg", ".wav", ".m4a", ".flac"}
TAUNT_FILE_RE = re.compile(r"^(\d+)_(.*)$")
SAVE_DEBOUNCE_SECONDS = 30.0
MAX_MESSAGE = 1900


def load_taunts(directory: Path) -> dict[int, Path]:
    """Map taunt number -> file for files named ``<number>_<name>.<ext>``."""
    taunts: dict[int, Path] = {}
    if not directory.is_dir():
        log.warning("Taunt directory %s does not exist", directory)
        return taunts
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() not in AUDIO_SUFFIXES:
            continue
        match = TAUNT_FILE_RE.match(path.stem)
        if not match:
            log.warning("Ignoring taunt file with unexpected name: %s", path.name)
            continue
        number = int(match.group(1))
        if number in taunts:
            log.warning("Duplicate taunt number %d: %s and %s", number, taunts[number].name, path.name)
            continue
        taunts[number] = path
    return taunts


def taunt_label(path: Path) -> str:
    match = TAUNT_FILE_RE.match(path.stem)
    return match.group(2) if match else path.stem


def load_audio_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        log.warning("Audio directory %s does not exist", directory)
        return []
    return sorted(p for p in directory.iterdir() if p.suffix.lower() in AUDIO_SUFFIXES)


def pitch_options(pitch: float | None) -> str | None:
    if pitch is None:
        return None
    return f"-af asetrate=44100*{pitch:.4f},aresample=44100,atempo={1 / pitch:.4f}"


def parse_pitch(token: str) -> float | None:
    """Pitch argument: clamp to [0.5, 2.0]; values <= 0 mean random."""
    value = float(token)
    if value > 0:
        return max(0.5, min(value, 2.0))
    return random.random() + 0.5


class Taunter(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.taunts = load_taunts(config.TAUNTS_DIR)
        self.suntzu = load_audio_files(config.SUNTZU_DIR)
        log.info("Loaded %d taunts and %d Sun Tzu quotes", len(self.taunts), len(self.suntzu))

        self.counts_path = config.DATA_DIR / "taunt_counts.json"
        self.counts: dict[int, int] = self._load_counts()
        self._save_task: asyncio.Task | None = None

        self.cooldowns: dict[int, float] = {}  # user id -> monotonic deadline
        self.roster_message: discord.Message | None = None
        self._voice_lock = asyncio.Lock()

        self.cat_task: asyncio.Task | None = None
        self.cat_expected: str | None = None

    # ------------------------------------------------------------------ counts

    def _load_counts(self) -> dict[int, int]:
        try:
            with open(self.counts_path, encoding="utf-8") as f:
                return {int(k): int(v) for k, v in json.load(f).items()}
        except FileNotFoundError:
            pass
        except Exception:
            log.exception("Could not read %s, starting with empty counts", self.counts_path)
            return {}
        # Migrate from the old pickle format (a list indexed by taunt number).
        for legacy in (config.DATA_DIR / "taunt_counts.pickle", config.ROOT_DIR / "taunt_counts.pickle"):
            if legacy.is_file():
                try:
                    with open(legacy, "rb") as f:
                        data = pickle.load(f)  # noqa: S301 - our own legacy file
                    counts = {i: int(c) for i, c in enumerate(data) if c}
                    log.info("Migrated %d taunt counts from %s", len(counts), legacy)
                    return counts
                except Exception:
                    log.exception("Could not migrate %s", legacy)
        return {}

    def _write_counts(self) -> None:
        self.counts_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.counts_path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in sorted(self.counts.items())}, f, indent=0)
        tmp.replace(self.counts_path)

    async def save_counts(self) -> None:
        try:
            await asyncio.to_thread(self._write_counts)
            log.debug("Saved taunt counts")
        except Exception:
            log.exception("Error saving taunt counts")

    def _schedule_save(self) -> None:
        if self._save_task is None or self._save_task.done():
            self._save_task = asyncio.create_task(self._debounced_save())

    async def _debounced_save(self) -> None:
        await asyncio.sleep(SAVE_DEBOUNCE_SECONDS)
        await self.save_counts()

    async def cog_unload(self) -> None:
        if self._save_task is not None:
            self._save_task.cancel()
        if self.cat_task is not None:
            self.cat_task.cancel()
        await self.save_counts()

    # ------------------------------------------------------------------- voice

    async def ensure_voice(self, channel: discord.VoiceChannel | discord.StageChannel) -> discord.VoiceClient:
        """Return a voice client connected to ``channel``, connecting or moving as needed."""
        async with self._voice_lock:
            vc = channel.guild.voice_client
            if isinstance(vc, discord.VoiceClient) and vc.is_connected():
                if vc.channel.id != channel.id:
                    await vc.move_to(channel)
                return vc
            if vc is not None:
                # Stale client left behind after a dropped connection.
                await vc.disconnect(force=True)
            return await channel.connect(timeout=15, self_deaf=True)

    def play_file(self, vc: discord.VoiceClient, path: Path, pitch: float | None = None) -> None:
        if vc.is_playing() or vc.is_paused():
            vc.stop()
        source = discord.FFmpegPCMAudio(str(path), options=pitch_options(pitch))

        def after(error: Exception | None) -> None:
            if error:
                log.error("Playback of %s failed: %s", path.name, error)

        vc.play(source, after=after)

    async def play_taunt(self, channel: discord.VoiceChannel | discord.StageChannel,
                         number: int, pitch: float | None = None) -> bool:
        path = self.taunts.get(number)
        if path is None:
            return False
        vc = await self.ensure_voice(channel)
        self.play_file(vc, path, pitch)
        self.counts[number] = self.counts.get(number, 0) + 1
        self._schedule_save()
        return True

    def on_cooldown(self, user_id: int) -> bool:
        now = time.monotonic()
        deadline = self.cooldowns.get(user_id)
        if deadline is not None and deadline > now:
            return True
        self.cooldowns[user_id] = now + config.TAUNT_COOLDOWN
        if len(self.cooldowns) > 500:
            self.cooldowns = {u: d for u, d in self.cooldowns.items() if d > now}
        return False

    async def voice_channel_for(self, message: discord.Message) -> discord.VoiceChannel | discord.StageChannel | None:
        """The author's voice channel, or None (after telling them off)."""
        member = message.author
        if not isinstance(member, discord.Member) or member.voice is None or member.voice.channel is None:
            await self.reply_briefly(message, "Joina en voice channel din tönt!")
            return None
        if self.on_cooldown(member.id):
            await self.reply_briefly(message, "Chilla fan", seconds=3)
            return None
        return member.voice.channel

    @staticmethod
    async def reply_briefly(message: discord.Message, text: str, seconds: float = 5) -> None:
        try:
            await message.reply(text, mention_author=False, delete_after=seconds)
        except discord.HTTPException:
            log.debug("Could not reply in %s", message.channel, exc_info=True)

    @staticmethod
    async def delete_quietly(message: discord.Message) -> None:
        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden):
            pass
        except discord.HTTPException:
            log.warning("Could not delete message %s", message.id, exc_info=True)

    # ---------------------------------------------------------------- messages

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return
        content = message.content.strip()
        if not content:
            return
        try:
            if content in config.CATS:
                await self.handle_cats(message)
                return
            parts = content.split()
            if parts[0].isdigit():
                await self.handle_number(message, parts)
            elif "sun tzu" in content.lower():
                await self.handle_suntzu(message)
        except Exception:
            log.exception("Error handling message %r", content[:80])

    async def handle_number(self, message: discord.Message, parts: list[str]) -> None:
        number = int(parts[0])
        if number not in self.taunts or len(parts) > 2:
            return  # not a taunt, leave the message alone
        pitch: float | None = None
        if len(parts) == 2:
            try:
                pitch = parse_pitch(parts[1])
            except ValueError:
                return  # "5 minutes" and the like
        channel = await self.voice_channel_for(message)
        if channel is None:
            return
        await self.play_taunt(channel, number, pitch)
        await self.delete_quietly(message)

    async def handle_suntzu(self, message: discord.Message) -> None:
        if not self.suntzu:
            return
        channel = await self.voice_channel_for(message)
        if channel is None:
            return
        vc = await self.ensure_voice(channel)
        self.play_file(vc, random.choice(self.suntzu))
        await self.delete_quietly(message)

    async def handle_cats(self, message: discord.Message) -> None:
        if self.cat_task is None or self.cat_task.done():
            self.cat_expected = config.CATS[message.content]
            self.cat_task = asyncio.create_task(self._cat_timeout(message.channel))
        elif message.content == self.cat_expected:
            self.cat_task.cancel()
            self.cat_task = None

    async def _cat_timeout(self, channel: discord.abc.Messageable) -> None:
        await asyncio.sleep(config.CAT_TIMEOUT)
        try:
            await channel.send("Ingen svarade, skäms!")
            if self.cat_expected:
                await channel.send(self.cat_expected)
        except discord.HTTPException:
            log.warning("Could not send cat response", exc_info=True)

    # ------------------------------------------------------------- voice state

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState,
                                    after: discord.VoiceState) -> None:
        if before.channel == after.channel:
            return  # mute/deafen/stream changes
        try:
            await self.disconnect_if_alone(member.guild)
            channel = after.channel or before.channel
            if channel is not None:
                await self.update_roster(channel)
            if after.channel is not None and not member.bot:
                await self.play_join_taunt(member, after.channel)
        except Exception:
            log.exception("Error handling voice state update for %s", member)

    async def disconnect_if_alone(self, guild: discord.Guild) -> None:
        vc = guild.voice_client
        if isinstance(vc, discord.VoiceClient) and vc.channel is not None:
            if not any(not m.bot for m in vc.channel.members):
                log.info("Alone in %s, disconnecting", vc.channel)
                await vc.disconnect()

    async def update_roster(self, channel: discord.VoiceChannel | discord.StageChannel) -> None:
        names = "".join(
            config.KNOWN_USERS[m.name][0] for m in channel.members if m.name in config.KNOWN_USERS
        )
        text_channel = self.bot.get_channel(config.STATUS_CHANNEL_ID)
        if not isinstance(text_channel, discord.abc.Messageable):
            return
        if self.roster_message is not None:
            await self.delete_quietly(self.roster_message)
            self.roster_message = None
        if names:
            self.roster_message = await text_channel.send(names)

    async def play_join_taunt(self, member: discord.Member,
                              channel: discord.VoiceChannel | discord.StageChannel) -> None:
        entry = config.KNOWN_USERS.get(member.name)
        if entry is None or entry[1] is None:
            return
        await self.play_taunt(channel, entry[1], random.random() + 0.5)

    # ----------------------------------------------------------- slash commands

    @app_commands.command(name="taunts", description="Sends you a message with all available taunts")
    async def taunts_command(self, interaction: discord.Interaction) -> None:
        lines = [f"{number:<4}{taunt_label(path)}" for number, path in sorted(self.taunts.items())]
        if not lines:
            await interaction.response.send_message("No taunts found.", ephemeral=True)
            return
        chunks: list[str] = []
        current = ""
        for line in lines:
            if len(current) + len(line) + 1 > MAX_MESSAGE:
                chunks.append(current)
                current = ""
            current += line + "\n"
        chunks.append(current)
        await interaction.response.send_message(f"Available taunts:\n```\n{chunks[0]}```", ephemeral=True)
        for chunk in chunks[1:]:
            await interaction.followup.send(f"```\n{chunk}```", ephemeral=True)

    @app_commands.command(name="top_taunts", description="Shows the most and least used taunts")
    async def top_taunts_command(self, interaction: discord.Interaction) -> None:
        active = [(n, c) for n, c in self.counts.items() if c > 0]
        if not active:
            await interaction.response.send_message("No taunts have been used yet!", ephemeral=True)
            return
        active.sort(key=lambda item: item[1], reverse=True)
        total = sum(c for _, c in active)

        def fmt(items: list[tuple[int, int]]) -> str:
            rows = []
            for number, count in items:
                label = taunt_label(self.taunts[number]) if number in self.taunts else "?"
                rows.append(f"#{number} {label}: {count} uses ({count / total * 100:.1f}%)")
            return "\n".join(rows)

        text = (
            f"**Top 5 Most Used Taunts:**\n```\n{fmt(active[:5])}\n```\n"
            f"**Least Used Taunts:**\n```\n{fmt(active[-5:])}\n```\n"
            f"Total: {total} taunts played."
        )
        await interaction.response.send_message(text)
