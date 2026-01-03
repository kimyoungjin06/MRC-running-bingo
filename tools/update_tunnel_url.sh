#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/submission_server/.env"
SUBMIT_JS="$REPO_ROOT/docs/submit.js"
BOARDS_JS="$REPO_ROOT/docs/boards.js"
PROGRESS_JS="$REPO_ROOT/docs/progress.js"
TEMPLATE_JS="$REPO_ROOT/docs/template.js"
SERVICE_NAME="mrc-cloudflared"

URL=$(journalctl -u "$SERVICE_NAME" --no-pager | grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -n 1 || true)

if [[ -z "$URL" ]]; then
  echo "No trycloudflare URL found in journal for $SERVICE_NAME." >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE" >&2
  exit 1
fi

if [[ ! -f "$SUBMIT_JS" ]]; then
  echo "Missing $SUBMIT_JS" >&2
  exit 1
fi
if [[ ! -f "$BOARDS_JS" ]]; then
  echo "Missing $BOARDS_JS" >&2
  exit 1
fi
if [[ ! -f "$PROGRESS_JS" ]]; then
  echo "Missing $PROGRESS_JS" >&2
  exit 1
fi
if [[ ! -f "$TEMPLATE_JS" ]]; then
  echo "Missing $TEMPLATE_JS" >&2
  exit 1
fi

# Update .env
sed -i "s|^MRC_SUBMIT_ALLOWED_ORIGINS=.*|MRC_SUBMIT_ALLOWED_ORIGINS=$URL|" "$ENV_FILE"

# Update default API base references
sed -i "s|^const DEFAULT_API_BASE = \".*\";|const DEFAULT_API_BASE = \"$URL\";|" "$SUBMIT_JS"
sed -i "s|^const DEFAULT_API_BASE = \".*\";|const DEFAULT_API_BASE = \"$URL\";|" "$BOARDS_JS"
sed -i "s|^const DEFAULT_API_BASE = \".*\";|const DEFAULT_API_BASE = \"$URL\";|" "$PROGRESS_JS"
sed -i "s|^const DEFAULT_API_BASE = \".*\";|const DEFAULT_API_BASE = \"$URL\";|" "$TEMPLATE_JS"

# Show result
printf "Updated URL to: %s\n" "$URL"

# Optional: commit and push
if [[ "${1:-}" == "--push" ]]; then
  cd "$REPO_ROOT"
  git add "$SUBMIT_JS" "$BOARDS_JS" "$PROGRESS_JS" "$TEMPLATE_JS"
  if git diff --cached --quiet; then
    echo "No changes to commit."
    exit 0
  fi
  git commit -m "Update quick tunnel URL"
  git push
fi
