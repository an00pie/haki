#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/pip" install -r "$ROOT/backend/requirements.txt"
if [ ! -f "$ROOT/.env" ]; then cp "$ROOT/.env.example" "$ROOT/.env"; fi
cd "$ROOT/extension"
npm install
printf '\nSetup complete. Start the local API:\n  %s/.venv/bin/uvicorn app.main:app --app-dir %s/backend --host 127.0.0.1 --port 8000 --reload\n' "$ROOT" "$ROOT"
printf 'Build the extension:\n  cd %s/extension && npm run build\n' "$ROOT"
printf 'Load unpacked extension/dist from chrome://extensions in Developer mode.\n'
