#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
command -v docker >/dev/null 2>&1 || { echo 'Install and start Docker Desktop (or Docker Engine + Compose) first.' >&2; exit 1; }
docker info >/dev/null
photo_folder="${1:-$HOME/Pictures}"
[ -d "$photo_folder" ] || { echo 'Pass an existing photographs parent folder as the first argument.' >&2; exit 1; }
FRAMEWISE_PHOTOS_PATH=$(cd "$photo_folder" && pwd)
export FRAMEWISE_PHOTOS_PATH
FRAMEWISE_PORT=${FRAMEWISE_PORT:-8765}
export FRAMEWISE_PORT
if command -v sha256sum >/dev/null 2>&1; then
  FRAMEWISE_WORKSPACE_ID=$(printf '%s' "$FRAMEWISE_PHOTOS_PATH" | sha256sum | cut -c1-12)
else
  FRAMEWISE_WORKSPACE_ID=$(printf '%s' "$FRAMEWISE_PHOTOS_PATH" | shasum -a 256 | cut -c1-12)
fi
export FRAMEWISE_WORKSPACE_ID
if ! docker image inspect framewise:0.2.0 >/dev/null 2>&1; then
  if [ -f framewise-image.tar ]; then docker image load --input framewise-image.tar; else docker compose build; fi
fi
docker compose up -d --no-build --wait --wait-timeout 180
echo "Framewise: http://127.0.0.1:$FRAMEWISE_PORT — use Scan > Choose folder."
case "$(uname -s)" in
  Darwin) open "http://127.0.0.1:$FRAMEWISE_PORT" ;;
  Linux) if command -v xdg-open >/dev/null 2>&1; then xdg-open "http://127.0.0.1:$FRAMEWISE_PORT" >/dev/null 2>&1 || true; fi ;;
esac
