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

## Schedule teasing when Django is down
If a message contains "카링" and GPT decides it's a schedule-related request,
the bot checks whether Django is running. If not, it replies with a playful tease
using a style reference file:
- `Kaling/bot/prompts/schedule_tease_ko.txt`

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
