# AoeBot - Discord Röst & Taunt Bot

En Discord-bot som spelar taunts, visar spelserverstatus och genererar AI-bilder.

## Funktioner

- **Taunt-system**: Skriv ett nummer i chatten (t.ex. `13`, eller `13 0.8` för pitch 0.5–2.0, `13 -1` för slumpad pitch) så spelas taunten i din röstkanal, precis som i Age of Empires. Meddelandet raderas efteråt.
- **Sun Tzu**: Skriv något med "sun tzu" i så spelas ett slumpat citat.
- **Röstroster**: När någon joinar/lämnar voice postas en emoji-lista över vem som är i röstkanalerna (`|` mellan kanaler), och kända användare får sin signaturtaunt spelad. Listan överlever omstarter via `data/roster.json`.
- **Serverstatus**: Botens status visar vilka spelservrar (docker compose-stackar) som kör. `/start` startar en.
- **Bildgenerering**: `/skapa` via Gemini (betald, veckobudget) eller gratis via [pollinations.ai](https://pollinations.ai). Nämn (@) folk i prompten så används deras avatarer som referensbilder (kräver API-nyckel, se nedan).

## Kommandon

- `/taunts` - Lista alla taunts (privat svar)
- `/top_taunts` - Mest och minst använda taunts
- `/status_update` - Uppdatera serverstatus nu
- `/start <server>` - Starta en spelserver (autocomplete)
- `/skapa <prompt>` - Generera en bild
- `/aunts`, `/taints` - Fina tanter respektive stjärt

## Konfiguration

Kopiera `.env.example` till `.env` och fyll i. Viktigast:

```env
DISCORD_API=din_discord_token
STATUS_CHANNEL_ID=895733929808650311
COMPOSE_FILE_VALHEIM=/srv/valheim        # fil eller mapp med docker-compose.yml
GEMINI_API_KEY=                          # valfritt, betald: https://aistudio.google.com/apikey
IMAGE_WEEKLY_LIMIT=50                    # betalda bilder per vecka (mån-sön), 0 = obegränsat
POLLINATIONS_API_KEY=                    # valfritt, gratis: https://enter.pollinations.ai/keys
```

Med `GEMINI_API_KEY` använder `/skapa` `gemini-3.1-flash-image` i 1K (ca 7 cent per bild; 512px kostar lika mycket) med avatarer som karaktärsreferenser. Räknaren sparas i `data/image_usage.json` och nollställs varje måndag; `IMAGE_USER_WEEKLY_LIMIT` sätter dessutom ett tak per användare. Misslyckas Gemini faller boten tillbaka på pollinations.

Utan Gemini-nyckel går allt via pollinations. Utan `POLLINATIONS_API_KEY` fungerar bara text-till-bild (modell `flux`, en bild per 15 s). Med nyckel används `klein` med avatarer som referens och `flux` som fallback.

Ljudfiler i `taunts/` ska heta `<nummer>_<namn>.mp3|ogg`. `suntzu/` innehåller citaten. Taunt-statistik sparas i `data/taunt_counts.json` (gammal `taunt_counts.pickle` migreras automatiskt).

## Köra med Docker (rekommenderat)

```bash
cp .env.example .env   # fyll i
docker compose up -d --build
docker compose logs -f
```

Compose-filen monterar `taunts/`, `suntzu/`, `data/` och dockersocketen. Varje `COMPOSE_FILE_*`-mapp måste dessutom monteras på **samma sökväg** inne i containern (se kommentaren i `docker-compose.yml`), annars hittar boten inte spelservrarnas compose-filer.

## Köra utan Docker

Kräver Python 3.10+, `ffmpeg` och `libopus` (`apt install ffmpeg libopus0`) samt docker CLI med compose-plugin.

```bash
pip install -r requirements.txt
python -m aoebot
```

## Filstruktur
```
.
├── aoebot/
│   ├── bot.py            # start, intents, cog-registrering
│   ├── config.py         # miljövariabler, kända användare, emojis
│   └── cogs/
│       ├── taunts.py     # röst, nummer-taunts, roster, /taunts, /top_taunts
│       ├── servers.py    # docker compose-status, /start, /status_update
│       └── images.py     # /skapa, /aunts, /taints
├── taunts/  suntzu/  data/
├── Dockerfile  docker-compose.yml
├── requirements.txt  .env.example
└── aunts.jpg  taints.mp4
```