# Kaling-Bot

Kaling-Bot is a persistent Korean RPG that can be played through Discord or its companion web client. Both clients use the same combat engine and player-state file, so equipment, jobs, abilities, exploration, bosses, enhancement, gacha, crafting, and Genesis liberation remain synchronized.

The repository runs three services:

- `bot`: the Discord bot and interactive Discord RPG UI.
- `backend`: the Django RPG client served at `theory-cta.com`.
- `cloudflare`: the Cloudflare Tunnel that publishes the backend.

The former schedule page is no longer connected to the public root URL. Its database models remain in the project only for compatibility.

## Features

- Shared Discord and web RPG progression.
- Jobs, regular and special abilities, equipment, potentials, Starforce, restoration, and Genesis liberation.
- Exploration with multi-run combat, crafting, auto-sell, gacha, and scheduled festivals.
- Party bosses, practice mode, solo-clear skips, shared normal/hard weekly entry groups, and per-participant combat state.
- Hard variants for every boss with separate rewards and mechanics.
- Private, permission-aware Discord message search across server channels.
- Local content administration with fast search, filters, preserved navigation state, validation, and bounded backups.
- A deterministic balance simulator plus live-state and real boss-engine reports.
- Atomic runtime-state merging so the Discord bot and web process can safely update different players.
- tmux service management and a GitHub Actions friendly deployment script.

## Requirements

- Linux or WSL2
- Python 3.11 recommended
- Git and `pip`
- `tmux` for `kaling-services.sh`
- Miniconda or Anaconda for the provided service scripts
- `cloudflared` when exposing the backend through Cloudflare Tunnel

Install Python dependencies from [requirements.txt](requirements.txt):

```bash
pip install -r requirements.txt
```

## Configuration

Create `.env` at the repository root. It is ignored by Git and must not be committed.

```env
DISCORD_TOKEN=
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

DJANGO_SECRET_KEY=
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=theory-cta.com,127.0.0.1,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=https://theory-cta.com
DJANGO_BASE_URL=https://theory-cta.com/

DISCORD_CLIENT_ID=
DISCORD_CLIENT_SECRET=
DISCORD_OAUTH_REDIRECT_URI=https://theory-cta.com/auth/discord/callback/

NEXON_API_BASE_URL=
NEXON_API_KEY=
NEXON_MAPLE_OCID_PATH=
NEXON_MAPLE_CHARACTER_STAT_PATH=
NEXON_MAPLE_COMBAT_POWER_JSON_PATH=final_stat.전투력

KALING_CONDA_ENV=bot
KALING_EXPLORE_LIMIT_ENABLED=true
KALING_BOSS_WEEKLY_REWARD_LIMIT_ENABLED=true
```

Optional runtime overrides:

```env
# Store bot and web progression in a different file.
KALING_RPG_STATE_PATH=/absolute/path/to/rpg_state.json

# Development login only; ignored when DJANGO_DEBUG=false.
KALING_WEB_DEV_USER_ID=
KALING_WEB_DEV_USER_NAME=Web Tester
```

The Discord application OAuth redirect URL must exactly match `DISCORD_OAUTH_REDIRECT_URI`. Production and local settings belong in `.env`; do not edit tracked content JSON merely to change server policy.

## Installation

```bash
git clone <repository-url>
cd Kaling-Bot
conda create -n myenv python=3.11
conda activate myenv
pip install -r requirements.txt
cd web
python manage.py migrate
python manage.py collectstatic --noinput
```

## Running

Run each service directly:

```bash
# Repository root
python -m bot

# Repository root (development)
cd web
python manage.py runserver

# Repository root
./run-cloudflare-tunnel.sh
```

Or manage all three in persistent tmux sessions:

```bash
./kaling-services.sh start
./kaling-services.sh status
./kaling-services.sh restart bot backend
./kaling-services.sh shutdown bot cloudflare
```

`shutdown` stops the process with `Ctrl-C` but keeps its tmux session. The conda environment is read from `KALING_CONDA_ENV` and activated inside each session.

The local web client is available at `http://127.0.0.1:8000/`. Production is intended to use `https://theory-cta.com/` through Cloudflare Tunnel.

## Web RPG

The root page is the actual RPG client, not a marketing page. Sign in through Discord to load the same profile used by the bot. The client includes:

- Dashboard, complete profile summary, and material inventory
- Searchable exploration and boss selectors
- Normal/hard difficulty switching and party lobbies
- Equipment, auto-equip, sale, and auto-sale controls
- Regular and special ability loadouts
- Starforce, special-material enhancement, memorial potentials, and trace restoration
- Gacha festivals, crafting, job advancement, and Genesis liberation

Boss sessions are intentionally process-local, like Discord interaction sessions. `kaling-services.sh` therefore runs Gunicorn with one worker and eight threads; persistent player rewards and inventory are written to the shared state store.

## Discord RPG

Common commands:

- `/rpg 시작`, `/rpg 프로필`
- `/rpg 탐색`, `/rpg 던전목록`
- `/보스`, `/rpg 보스`, `/rpg 보스목록`
- `/rpg 인벤토리`, `/rpg 장착`, `/rpg 판매`, `/rpg 자동판매`
- `/rpg 어빌리티`, `/rpg 강화`, `/rpg 복구`
- `/rpg 가챠`, `/rpg 전직`, `/rpg 전직목록`
- `/메시지검색 키워드:[검색어]` (optional `채널` and `기간`; private paginated results)

Message search checks only channels that both the requester and bot can read, including accessible active and archived threads. The optional period presets are 24 hours, 7/30/90 days, one year, or the complete history (the default). Within that period it has no bot-side message, channel, result, or time cutoff, so broad searches can take a while. Results remain visible only to the requester; if a long search outlives Discord's private interaction response and direct messages are allowed, the bot falls back to a DM. The Discord application's Message Content Intent must be enabled.

The bot also includes MapleStory combat-power lookup, conversational replies, and number baseball.

## Content Admin

The local admin edits tracked JSON under `bot/services/rpg/content/`:

```bash
python -m tools.rpg_admin --host 127.0.0.1 --port 8787
```

Open `http://127.0.0.1:8787`. This command is local-only; the admin is not started by the service manager or deploy script.

Useful controls:

- `Ctrl+K`: global content search
- `Ctrl+S`: validate and save
- Per-section search and filters for large item, material, job, skill, dungeon, and boss lists
- Searchable relation pickers instead of unbounded native dropdowns
- Session-preserved filters, expanded groups, selections, and scroll positions

Successful saves create bounded backups in `.rpg_content_backups/`. See [the admin reference](tools/rpg_admin/README.md).

## Balance Analysis

Run the synthetic job and equipment matrix:

```bash
python -m tools.rpg_balance --details
```

Analyze a read-only production snapshot without copying it into tracked content:

```bash
python -m tools.rpg_balance \
  --state /path/to/server_rpg_state.json \
  --enemy-level 50 --enemy-defense 0.85 --turns 30
```

Run those profiles through every hard boss with the actual boss engine:

```bash
python -m tools.rpg_balance \
  --state /path/to/server_rpg_state.json \
  --hard-report --trials 10
```

State files matching `server_rpg_state*.json` are ignored. See [the balance tool reference](tools/rpg_balance/README.md).

## State Safety

Tracked game definitions live in:

```text
bot/services/rpg/content/
```

Runtime player state defaults to:

```text
bot/data/rpg_state.json
```

Runtime state and lock files are ignored by Git. Item identifiers are collision-resistant, and writes use an OS file lock plus a three-way merge so independent bot and web updates are not silently discarded. Keep the backend and bot pointed at the same `KALING_RPG_STATE_PATH` when using an override.

## Deployment

On a persistent Linux host such as AWS Lightsail:

```bash
cd ~/Kaling-Bot
./deploy.sh
```

The script:

1. Backs up RPG state and the Django database to `.deploy_backups/`.
2. Pulls the current branch with `git pull --ff-only`.
3. Activates `KALING_CONDA_ENV` and installs requirements.
4. Compiles core Python modules.
5. Runs Django migrations and `collectstatic`.
6. Restarts `bot`, `backend`, and `cloudflare` through tmux.

For GitHub Actions SSH deployment, keep the server host, user, and full private key in repository Actions secrets. Secrets are not exposed merely because the repository is public, but workflow files and command output are public, so never echo them.

## Development Checks

```bash
python -m unittest discover -s tests -v
python -m py_compile bot/services/rpg/data.py bot/services/rpg/manager.py bot/cogs/rpg.py tools/rpg_admin/app.py web/rpg_web/views.py
node --check tools/rpg_admin/static/app.js
node --check web/rpg_web/static/rpg_web/app.js
cd web && python manage.py check
```

Validate all RPG content without starting the admin server:

```bash
python -c "from tools.rpg_admin.app import read_content, normalize_content, validate_content; c=read_content(); normalize_content(c); e=validate_content(c); print(f'errors={len(e)}'); print('\\n'.join(e[:30]))"
```

## Repository Layout

```text
bot/                         Discord bot and shared RPG runtime
bot/services/rpg/content/    Tracked RPG definitions
bot/data/                    Ignored runtime player state
web/rpg_web/                 Django RPG client and API
web/scheduler/               OAuth and retained schedule compatibility code
tools/rpg_admin/             Local content administration UI
tools/rpg_balance/           Balance and live-state analysis
tests/                       RPG, store, hard-mode, potential, and web tests
deploy.sh                    Server update workflow
kaling-services.sh           tmux service manager
```
