"""Configuration: environment variables and static lookup tables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent

TOKEN: str | None = os.getenv("DISCORD_API")

TAUNTS_DIR = Path(os.getenv("TAUNTS_DIR", ROOT_DIR / "taunts"))
SUNTZU_DIR = Path(os.getenv("SUNTZU_DIR", ROOT_DIR / "suntzu"))
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT_DIR / "data"))
ASSETS_DIR = Path(os.getenv("ASSETS_DIR", ROOT_DIR))

# Text channel that receives the "who is in voice" roster message.
STATUS_CHANNEL_ID = int(os.getenv("STATUS_CHANNEL_ID", "895733929808650311"))

# Seconds a user must wait between taunts.
TAUNT_COOLDOWN = float(os.getenv("TAUNT_COOLDOWN", "0.5"))

# Game servers: every COMPOSE_FILE_<NAME> variable points at a docker compose
# file, or a directory containing docker-compose.yml / compose.yml.
SERVERS: dict[str, Path] = {
    key.removeprefix("COMPOSE_FILE_").lower(): Path(value)
    for key, value in os.environ.items()
    if key.startswith("COMPOSE_FILE_") and value
}

# Image generation (pollinations.ai). Text-only works without a key; reference
# images (user avatars) require a free key from https://enter.pollinations.ai/keys
POLLINATIONS_API_KEY: str | None = os.getenv("POLLINATIONS_API_KEY") or None
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "klein" if POLLINATIONS_API_KEY else "flux")
IMAGE_FALLBACK_MODEL = os.getenv("IMAGE_FALLBACK_MODEL", "flux")
IMAGE_MAX_REFERENCES = int(os.getenv("IMAGE_MAX_REFERENCES", "4"))

EUPHEMISMS = [
    "thumb wars",
    "solitaire championships",
    "competitive napping",
    "professional procrastination",
    "solo hide and seek",
    "extreme daydreaming",
    "meditation marathon",
    "competitive cloud watching",
    "single player tag",
    "paper-rock-scissors against mirror",
]

# username -> (roster emoji, taunt number played when the user joins voice)
KNOWN_USERS: dict[str, tuple[str, int | None]] = {
    "dirtydazzle": ("<:vik:1061396237200404542>", 50),
    "ixuue": ("<:ff:895743538166366249>", 667),
    "darthdazzle": ("<:axl:898278404661596180>", 89),
    "mrseal1993": ("<:seb:895744495310733344>", 137),
    "knastatur": ("<:hurr:898280606138527824>", 30),
    "tehbaldeagle": ("<:broken:896724301435265044>", 111),
    "sjudin": ("<:jak:934386916487479326>", 73),
    "AOE_Taunts": ("<:burk:895723401090588692>", None),
    "emil0x": ("<:emil:895751124580200508>", 8),
    "paltis_": ("<:koks:1201622535805075516>", 96),
    "mangeee": ("<:hajp:896056974905602049>", 669),
    "amandasofia9485": ("<:mandy:1206331809604837476>", 101),
    ".tenex": ("<:caaaarl:1208752788318847027>", 55),
    "sarazodd": ("<:zod:1296168810511990854>", 132),
    "cho11o": ("<:bongo:898283899493433384>", 38),
    "rilleboi": ("<:monster:903686408651296769>", 53),
    "soph_85349": ("<:nolove:908730069936132178>", 56),
    "_ceder": ("<:cum:895726544696246312>", 24),
    "mrdazzle": ("<:oltorn:898641812804210759>", 69),
}

# The "tillsammans / alltid" call-and-response game.
CAT_TILLSAMMANS = "<:tillsammans:908711034511044618>"
CAT_ALLTID = "<:alltid:908711034632683593>"
CATS = {CAT_TILLSAMMANS: CAT_ALLTID, CAT_ALLTID: CAT_TILLSAMMANS}
CAT_TIMEOUT = 5.0
