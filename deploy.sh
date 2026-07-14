#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

read_env_value() {
  local key="$1"
  local env_file="$2"
  local line name value

  [ -f "$env_file" ] || return 0

  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    line="${line#"${line%%[![:space:]]*}"}"

    case "$line" in
      ""|\#*) continue ;;
      export\ *) line="${line#export }" ;;
    esac

    case "$line" in
      *=*) ;;
      *) continue ;;
    esac

    name="${line%%=*}"
    value="${line#*=}"
    name="${name%"${name##*[![:space:]]}"}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"

    if [ "$name" = "$key" ]; then
      if [[ "$value" == \"*\" && "$value" == *\" ]]; then
        value="${value:1:${#value}-2}"
      elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
        value="${value:1:${#value}-2}"
      fi
      printf "%s" "$value"
      return 0
    fi
  done < "$env_file"
}

CONDA_ENV="${KALING_CONDA_ENV:-$(read_env_value "KALING_CONDA_ENV" "$ROOT_DIR/.env")}"
CONDA_ENV="${CONDA_ENV:-myenv}"

activate_conda() {
  if command -v conda >/dev/null 2>&1; then
    eval "$(conda shell.bash hook)"
  elif [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    . "$HOME/miniconda3/etc/profile.d/conda.sh"
  elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    . "$HOME/anaconda3/etc/profile.d/conda.sh"
  else
    echo "conda not found; set PATH or install Miniconda/Anaconda" >&2
    exit 1
  fi
  conda activate "$CONDA_ENV"
}

cd "$ROOT_DIR"
git pull --ff-only

activate_conda
pip install -r requirements.txt
python3 -m py_compile bot/services/rpg/data.py bot/services/rpg/manager.py bot/cogs/rpg.py tools/rpg_admin/app.py

(
  cd "$ROOT_DIR/web"
  python3 manage.py migrate --noinput
)

"$ROOT_DIR/kaling-services.sh" restart bot backend cloudflare
