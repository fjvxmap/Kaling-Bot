# Kaling Discord Bot (Python)

Local-run Discord bot starter using `discord.py` 2.x with a Cog-based slash command setup.

## Prerequisites
1) Python 3.10+ recommended
2) Install dependencies
```bash
pip install -r requirements.txt
```
3) Set environment variables
Put your Discord bot token in `.env`.

## Run
```bash
python -m bot
```

## MapleStory combat power (Nexon Open API + OpenAI)
This bot listens for natural-language messages like:
```
카링아 누구누구 전투력 알려줘
```
It uses OpenAI to extract the character name, then calls Nexon Open API to fetch combat power.

## Number baseball mode
If intent is like `카링, 숫자야구하자`, the bot starts a 4-digit number baseball session.
During the session, it listens for 4-digit numeric messages from that user in that channel
and returns strike/ball results until win or attempts run out.

## RPG mode
The bot includes a compact slash-command RPG based on the old Python console game's combat loop.

Commands:
- `/rpg 시작`: create or view your RPG profile
- `/rpg 프로필`: level, EXP, stats, daily explores, equipped weapons
- `/rpg 던전목록`: available daily dungeons
- `/rpg 탐색`: spend one daily explore and auto-battle a dungeon
- `/rpg 보스목록`: boss list and weekly reward status
- `/rpg 보스`: attempt a boss with no try limit; rewards are boss-by-boss weekly
- `/rpg 인벤토리`: owned weapons; the strongest 4 non-destroyed weapons auto-equip
- `/rpg 강화`: enhance one weapon by UID
- `/rpg 복구`: restore a destroyed weapon trace to +0
- `/rpg 스탯`: spend stat points on attack, HP, or defense

Runtime RPG state is stored at `bot/data/rpg_state.json` and ignored by Git.

## Schedule teasing when Django is down
If a message contains "카링" and GPT decides it's a schedule-related request,
the bot checks whether Django is running. If not, it replies with a playful tease
using a style reference file:
- `Kaling/bot/prompts/schedule_tease_ko.txt`

## Prompt files
You can maintain long prompts in files instead of inline code:
- Intent classification: `Kaling/bot/prompts/intent_parser_ko.txt`
- Casual chat style: `Kaling/bot/prompts/small_talk_ko.txt`
- Schedule tease style: `Kaling/bot/prompts/schedule_tease_ko.txt`
- Character speech reference lines: `Kaling/bot/prompts/reference.txt`
- OpenAI response instructions: `Kaling/bot/prompts/respond_small_talk_instructions_ko.txt`, `Kaling/bot/prompts/respond_tease_instructions_ko.txt`, `Kaling/bot/prompts/respond_annoy_reject_instructions_ko.txt`

## Character images
Put reaction images under `Kaling/img` with subfolders:
- `joy/`, `love/`, `scary/`, `tease/`

OpenAI intent parsing now also selects the image reaction mood (`joy/love/scary/tease/none`).
The bot randomly picks one file from the selected folder and sometimes sends it with text.
Supported extensions include `.gif`, `.png`, `.jpg`, `.jpeg`, `.webp`.
Control send frequency with `KALING_IMAGE_SEND_PROB` in `.env` (default `0.35`).

Set `DJANGO_BASE_URL` in `.env` if your dashboard runs elsewhere.

### Required env keys
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (default: `gpt-4o-mini`)
- `DJANGO_BASE_URL` (default: `http://127.0.0.1:8000/`)
- `NEXON_API_BASE_URL`
- `NEXON_API_KEY`
- `NEXON_MAPLE_OCID_PATH`
- `NEXON_MAPLE_CHARACTER_STAT_PATH`
- `NEXON_MAPLE_COMBAT_POWER_JSON_PATH` (dot path in JSON, default: `final_stat.전투력`)

### Notes
- API paths differ by game/region; set them in `.env`.
- If combat power is nested, use dot notation like `character.combat_power`.

## Web Dashboard (Django)
This repo includes a minimal Django dashboard scaffold under `web/`.

### Setup
```bash
pip install -r requirements.txt
cp .env.example .env
```
Fill in at least:
- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `NEXON_API_BASE_URL` and `NEXON_API_KEY` (optional for now)

### Run
```bash
cd web
python manage.py migrate
python manage.py runserver
```
Open http://127.0.0.1:8000/ to view the calendar.

### Admin
```bash
python manage.py createsuperuser
```
Then open http://127.0.0.1:8000/admin to manage schedules and availability.

## Discord OAuth (optional)
Enable Discord OAuth to auto-fill user identity on the schedule page.

Add these to `.env`:
- `DISCORD_CLIENT_ID`
- `DISCORD_CLIENT_SECRET`
- `DISCORD_OAUTH_REDIRECT_URI` (example: `http://127.0.0.1:8000/auth/discord/callback/`)

Then use the "Sign in with Discord" button on the schedule page.

## Folder structure
```
bot/                 # package root
  bot/
    __init__.py
    __main__.py      # entrypoint
    config.py        # env loader
    logging.py       # logging setup
    client.py        # bot instance
    cogs/
      __init__.py
      core.py        # sample slash command
.env.example
requirements.txt
README.md
```

## Notes
After inviting the bot to your server, use `/ping` to test the response.
