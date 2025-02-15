# AoeBot - Discord Röst & Taunt Bot

En Discord-bot som spelar taunts, övervakar serverstatus och genererar AI-bilder med Craiyon.

## Funktioner

- **Taunt-system**: Spela Age of Empires taunts i röstkanaler med tonhöjdskontroll
- **Serverövervakning**: Övervakar aktiva spelservrar (VRising, Minecraft, Valheim, Terraria, Enshrouded)
- **Bildgenerering**: Skapar bilder med Craiyon AI
- **Anpassade röstkommandon**: Spelar Sun Tzu-citat och hanterar särskilda emoji-interaktioner

## Installation

1. Installera dependencies:
```bash
pip install -r requirements.txt
```

2. Konfigurera miljövariabler i 

.env

:
```env
DISCORD_API=din_discord_token
COMPOSE_FILE_VRISING=/sökväg/till/vrising
COMPOSE_FILE_VALHEIM=/sökväg/till/valheim
COMPOSE_FILE_ENSHROUDED=/sökväg/till/enshrouded
COMPOSE_FILE_MINECRAFT=/sökväg/till/minecraft
```

3. Skapa nödvändiga mappar:
- 

taunts

 - För lagring av .ogg/.mp3 taunt-filer
- 

suntzu

 - För lagring av Sun Tzu-citat ljudfiler

## Kommandon

- `/taunts` - Lista alla tillgängliga ljudtaunts
- `/aunts` - Visa tant-bilder (kräver aunts.jpg)
- `/taints` - Visa taints-video (kräver taints.mp4)
- `/status_update` - Tvinga statusuppdatering av server
- `/start [server]` - Starta en specifik spelserver
- `/skapa [prompt]` - Generera AI-bilder med Craiyon

## Användning

Starta boten:
```bash
python aoebot.py
```

## Dependencies

Se requirements.txt för fullständig lista över dependencies:
- discord.py
- python-dotenv
- craiyon.py
- Pillow
- psutil
- PyNaCl

## Filstruktur
```
.
├── aoebot.py
├── requirements.txt
├── .env
├── taunts/
├── suntzu/
└── .gitignore
```