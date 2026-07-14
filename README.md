# Kaling-Bot

Kaling-Bot is a Discord bot and companion Django web service for a private game/community server. It combines conversational Discord features, MapleStory combat-power lookup, schedule access through a web dashboard, and a persistent button-driven RPG system.

The repository is designed to run as three cooperating local services:

- `bot`: the Discord bot process.
- `backend`: the Django schedule/dashboard server under `web/`.
- `cloudflare`: a Cloudflare Tunnel process for exposing the local backend.

## Features

- Discord slash commands built with `discord.py`.
- OpenAI-assisted Korean intent parsing and casual replies.
- Nexon Open API integration for MapleStory combat-power lookup.
- Number baseball mini-game.
- Django schedule dashboard with optional Discord OAuth login.
- Persistent RPG mode with dungeons, bosses, jobs, skills, equipment, crafting, enhancement, gacha, and admin-editable content.
- RPG admin web UI for editing content JSON files.
- tmux-based service management for local or Lightsail operation.
- GitHub Actions friendly deployment through `deploy.sh`.

## Requirements

- Linux or WSL2 is recommended.
- Python 3.11 is recommended. Python 3.10+ should work.
- `pip`
- `tmux` for service scripts.
- `git`
- `cloudflared` if you use Cloudflare Tunnel.
- Miniconda or Anaconda if you want to use the provided conda-based service scripts.

Python packages are listed in [requirements.txt](requirements.txt):

```bash
pip install -r requirements.txt
```

## Configuration

Create a local `.env` file at the repository root. It is intentionally not committed.

Common keys:

```env
DISCORD_TOKEN=
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

DJANGO_SECRET_KEY=
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=
DJANGO_BASE_URL=http://127.0.0.1:8000/

NEXON_API_BASE_URL=
NEXON_API_KEY=
NEXON_MAPLE_OCID_PATH=
NEXON_MAPLE_CHARACTER_STAT_PATH=
NEXON_MAPLE_COMBAT_POWER_JSON_PATH=final_stat.전투력

DISCORD_CLIENT_ID=
DISCORD_CLIENT_SECRET=
DISCORD_OAUTH_REDIRECT_URI=

KALING_CONDA_ENV=myenv
KALING_EXPLORE_LIMIT_ENABLED=false
KALING_BOSS_WEEKLY_REWARD_LIMIT_ENABLED=false
```

Production can override behavior without changing tracked JSON files:

```env
KALING_CONDA_ENV=bot
KALING_EXPLORE_LIMIT_ENABLED=true
KALING_BOSS_WEEKLY_REWARD_LIMIT_ENABLED=true
```

## Installation

```bash
git clone <repo-url>
cd Kaling-Bot
pip install -r requirements.txt
```

If you use conda:

```bash
conda create -n myenv python=3.11
conda activate myenv
pip install -r requirements.txt
```

Initialize the Django database:

```bash
cd web
python manage.py migrate
```

## Running Locally

Run the Discord bot:

```bash
python -m bot
```

Run the Django backend:

```bash
cd web
python manage.py runserver
```

Run the Cloudflare Tunnel:

```bash
./run-cloudflare-tunnel.sh
```

## Service Management

`kaling-services.sh` manages the three services in persistent tmux sessions. It reads `KALING_CONDA_ENV` from `.env`.

Start all services:

```bash
./kaling-services.sh start
```

Start selected services:

```bash
./kaling-services.sh start bot backend
```

Stop selected services while keeping tmux sessions alive:

```bash
./kaling-services.sh shutdown bot cloudflare
```

Restart all services:

```bash
./kaling-services.sh restart
```

Check status:

```bash
./kaling-services.sh status
```

Compatibility wrappers are also available:

```bash
./start-services.sh
./shutdown-services.sh
```

## Discord Usage

Core checks:

- `/ping`: verify that the bot is alive.

RPG commands:

- `/rpg 시작`: create or view your RPG profile.
- `/rpg 프로필`: show level, job, stats, resources, and equipment.
- `/rpg 던전목록`: list available dungeons.
- `/rpg 탐색`: open dungeon exploration UI or run a selected dungeon.
- `/rpg 보스목록`: list bosses and start availability.
- `/보스` or `/rpg 보스`: open the boss selection panel.
- `/rpg 전직목록`: show jobs and advancement information.
- `/rpg 전직`: open job advancement UI.
- `/rpg 인벤토리`: open inventory/equipment UI.
- `/rpg 장착`: open equipment UI directly.
- `/rpg 판매`: sell selected unequipped equipment.
- `/rpg 자동판매`: configure automatic sale rules.
- `/rpg 가챠`: open gacha UI.
- `/rpg 어빌리티`: equip boss/dungeon abilities.
- `/rpg 강화`: open enhancement and restoration UI.
- `/rpg 복구`: open restoration UI for destroyed equipment traces.

Natural-language features:

- MapleStory combat-power lookup through Korean requests addressed to Kaling.
- Number baseball sessions through Korean natural-language prompts.
- Schedule-related replies when the Django backend is unavailable.

## RPG Admin UI

The RPG content editor is a local admin tool for JSON content under `bot/services/rpg/content/`.

Run it with:

```bash
python -m tools.rpg_admin --host 127.0.0.1 --port 8787
```

Open:

```text
http://127.0.0.1:8787
```

The admin UI can edit:

- Items and item stats
- Materials
- Jobs and job trees
- Skills and effects
- Stack effects
- Dungeons and enemies
- Bosses, warnings, HP effects, HP locks, CT rules, rewards
- Gacha pools
- Global RPG settings

Backups are written under `.rpg_content_backups/`.

## RPG Data And State

Tracked RPG content:

```text
bot/services/rpg/content/
```

Runtime player state:

```text
bot/data/rpg_state.json
```

Runtime state is ignored by Git. Do not overwrite production state with local test state.

Useful content references:

- [bot/services/rpg/content/README.md](bot/services/rpg/content/README.md)
- [tools/rpg_admin/README.md](tools/rpg_admin/README.md)
- [tools/rpg_balance/README.md](tools/rpg_balance/README.md)

## Django Dashboard

Run migrations:

```bash
cd web
python manage.py migrate
```

Start the server:

```bash
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

Create an admin user:

```bash
python manage.py createsuperuser
```

Open:

```text
http://127.0.0.1:8000/admin
```

## Deployment

The repository includes a deployment script for a persistent Linux server such as AWS Lightsail:

```bash
cd ~/Kaling-Bot
./deploy.sh
```

`deploy.sh` performs these steps:

1. Backs up `bot/data/rpg_state.json` and `web/db.sqlite3` into `.deploy_backups/`.
2. Runs `git pull --ff-only`.
3. Activates the conda environment from `KALING_CONDA_ENV`.
4. Installs Python requirements.
5. Runs Python compile checks.
6. Runs Django migrations.
7. Restarts `bot`, `backend`, and `cloudflare` through `kaling-services.sh`.

For GitHub Actions deployment, configure repository secrets for the SSH host, username, and private key. The private key secret must include the full PEM header and footer.

## Development Checks

Run Python compile checks:

```bash
python -m py_compile bot/services/rpg/data.py bot/services/rpg/manager.py bot/cogs/rpg.py tools/rpg_admin/app.py
```

Validate RPG content through the admin app helpers:

```bash
python -c "from tools.rpg_admin.app import read_content, normalize_content, validate_content; c=read_content(); normalize_content(c); e=validate_content(c); print(f'errors={len(e)}'); print('\n'.join(e[:30]))"
```

## Repository Layout

```text
bot/                         Discord bot package and RPG runtime
bot/cogs/                    Discord cogs
bot/services/rpg/            RPG data models, content loader, manager, store
bot/services/rpg/content/    Tracked RPG content JSON
bot/data/                    Runtime RPG state
web/                         Django dashboard
tools/rpg_admin/             RPG content admin UI
tools/rpg_balance/           RPG balance analysis tools
docs/                        Reference documents
img/                         Reaction images
kaling-services.sh           tmux service manager
deploy.sh                    Server deployment script
```

## Notes

- Keep secrets and server-specific toggles in `.env`.
- Keep production runtime state out of Git.
- Prefer changing RPG content through the admin UI when possible.
