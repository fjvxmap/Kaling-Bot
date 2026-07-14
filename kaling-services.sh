#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR_Q="$(printf "%q" "$ROOT_DIR")"
WEB_DIR_Q="$(printf "%q" "$ROOT_DIR/web")"

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
CONDA_ENV_Q="$(printf "%q" "$CONDA_ENV")"
CONDA_ACTIVATE_CMD="if command -v conda >/dev/null 2>&1; then eval \"\$(conda shell.bash hook)\"; elif [ -f \"\$HOME/miniconda3/etc/profile.d/conda.sh\" ]; then . \"\$HOME/miniconda3/etc/profile.d/conda.sh\"; elif [ -f \"\$HOME/anaconda3/etc/profile.d/conda.sh\" ]; then . \"\$HOME/anaconda3/etc/profile.d/conda.sh\"; else echo 'conda not found; set PATH or install Miniconda/Anaconda' >&2; exit 1; fi; conda activate $CONDA_ENV_Q"

ALL_SERVICES=("bot" "backend" "cloudflare")

usage() {
  cat <<EOF
Usage:
  ./kaling-services.sh start [bot|backend|cloudflare ...]
  ./kaling-services.sh shutdown [bot|backend|cloudflare ...]
  ./kaling-services.sh restart [bot|backend|cloudflare ...]
  ./kaling-services.sh status [bot|backend|cloudflare ...]

Aliases:
  shutdown: stop, down, shoutdown
  cloudflare: cf, tunnel
  backend: web, django

When no service is provided, the command applies to all services.
Tmux sessions are kept alive; shutdown only sends Ctrl-C to the service pane.
EOF
}

normalize_service() {
  case "${1:-}" in
    bot) echo "bot" ;;
    backend|web|django) echo "backend" ;;
    cloudflare|cf|tunnel) echo "cloudflare" ;;
    *)
      echo "Unknown service: ${1:-}" >&2
      usage >&2
      exit 2
      ;;
  esac
}

session_for() {
  case "$1" in
    bot) echo "bot" ;;
    backend) echo "backend" ;;
    cloudflare) echo "cloudflare" ;;
  esac
}

command_for() {
  case "$1" in
    bot) echo "cd $ROOT_DIR_Q && $CONDA_ACTIVATE_CMD && python3 -m bot" ;;
    backend) echo "cd $WEB_DIR_Q && $CONDA_ACTIVATE_CMD && python3 manage.py runserver" ;;
    cloudflare) echo "cd $ROOT_DIR_Q && ./run-cloudflare-tunnel.sh" ;;
  esac
}

is_idle_command() {
  case "$1" in
    bash|zsh|sh|fish|tmux) return 0 ;;
    *) return 1 ;;
  esac
}

has_session() {
  tmux has-session -t "$1" 2>/dev/null
}

ensure_session() {
  local session="$1"
  if ! has_session "$session"; then
    tmux new-session -d -s "$session"
    echo "created tmux session: $session"
  fi
}

current_command() {
  tmux display-message -p -t "$1" "#{pane_current_command}" 2>/dev/null || true
}

wait_until_idle() {
  local session="$1"
  local attempt current

  for attempt in {1..50}; do
    current="$(current_command "$session")"
    if is_idle_command "$current"; then
      return 0
    fi
    sleep 0.2
  done

  return 1
}

services_from_args() {
  if [ "$#" -eq 0 ]; then
    printf "%s\n" "${ALL_SERVICES[@]}"
    return
  fi

  local service
  for service in "$@"; do
    normalize_service "$service"
  done
}

start_service() {
  local service="$1"
  local session command current

  session="$(session_for "$service")"
  command="$(command_for "$service")"

  ensure_session "$session"
  current="$(current_command "$session")"

  if ! is_idle_command "$current"; then
    echo "$service: already running or busy in tmux session '$session' ($current)"
    return
  fi

  tmux send-keys -t "$session" "$command" C-m
  echo "$service: started in tmux session '$session'"
}

shutdown_service() {
  local service="$1"
  local session current

  session="$(session_for "$service")"

  if ! has_session "$session"; then
    echo "$service: tmux session '$session' does not exist; skipped"
    return
  fi

  current="$(current_command "$session")"

  if is_idle_command "$current"; then
    echo "$service: already stopped; tmux session '$session' is idle"
    return
  fi

  tmux send-keys -t "$session" C-c
  echo "$service: sent Ctrl-C; tmux session '$session' kept alive"
}

restart_service() {
  local service="$1"
  local session

  session="$(session_for "$service")"
  shutdown_service "$service"

  if has_session "$session"; then
    if ! wait_until_idle "$session"; then
      echo "$service: session '$session' did not become idle; start skipped" >&2
      return 1
    fi
  fi

  start_service "$service"
}

status_service() {
  local service="$1"
  local session current

  session="$(session_for "$service")"

  if ! has_session "$session"; then
    echo "$service: no tmux session '$session'"
    return
  fi

  current="$(current_command "$session")"
  if is_idle_command "$current"; then
    echo "$service: stopped/idle in tmux session '$session'"
  else
    echo "$service: running/busy in tmux session '$session' ($current)"
  fi
}

main() {
  local action="${1:-}"
  local service
  local services=()

  if [ -z "$action" ] || [ "$action" = "-h" ] || [ "$action" = "--help" ]; then
    usage
    exit 0
  fi

  shift
  while IFS= read -r service; do
    services+=("$service")
  done < <(services_from_args "$@")

  case "$action" in
    start|up)
      for service in "${services[@]}"; do
        start_service "$service"
      done
      ;;
    shutdown|stop|down|shoutdown)
      for service in "${services[@]}"; do
        shutdown_service "$service"
      done
      ;;
    restart)
      for service in "${services[@]}"; do
        restart_service "$service"
      done
      ;;
    status|ps)
      for service in "${services[@]}"; do
        status_service "$service"
      done
      ;;
    *)
      echo "Unknown action: $action" >&2
      usage >&2
      exit 2
      ;;
  esac
}

main "$@"
