#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

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

CLOUDFLARE_TUNNEL_TOKEN="$(read_env_value "CLOUDFLARE_TUNNEL_TOKEN" "$SCRIPT_DIR/.env")"

if [ -z "${CLOUDFLARE_TUNNEL_TOKEN:-}" ]; then
  echo "CLOUDFLARE_TUNNEL_TOKEN is not set. Fill it in .env." >&2
  exit 1
fi

exec cloudflared tunnel run --token "$CLOUDFLARE_TUNNEL_TOKEN"
