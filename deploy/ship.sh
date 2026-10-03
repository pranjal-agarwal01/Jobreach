#!/usr/bin/env bash
# Ship Jobreach to the server, from your PC (Git Bash), at the repository's root:
#
#   deploy/ship.sh <server address> <path to the server's SSH private key>
#
# What goes: the last commit (git archive, so nothing uncommitted and nothing git-ignored) and
# deploy/.env (your settings and secrets, copied straight to the server over SSH, never to
# GitHub). Then deploy/setup.sh runs on the server. Run it again to update.
set -euo pipefail
HOST="${1:?usage: deploy/ship.sh <server address> <ssh key>}"
KEY="${2:?usage: deploy/ship.sh <server address> <ssh key>}"
USER_AT="ubuntu@$HOST"
SSH=(ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$USER_AT")

cd "$(git rev-parse --show-toplevel)"
[ -f deploy/.env ] || { echo "deploy/.env is missing: run python deploy/make_env.py first." >&2; exit 1; }
git diff --quiet HEAD -- . ':!deploy/.env' || echo "Note: uncommitted changes stay here; only the last commit ships."

echo "Copying the code ($(git rev-parse --short HEAD))..."
git archive --format=tar HEAD | "${SSH[@]}" 'rm -rf ~/jobreach/src.new && mkdir -p ~/jobreach/src.new && tar -x -C ~/jobreach/src.new'
scp -q -i "$KEY" -o StrictHostKeyChecking=accept-new deploy/.env "$USER_AT:jobreach/src.new/deploy/.env"
"${SSH[@]}" 'cd ~/jobreach && rm -rf src.old && { [ -d src ] && mv src src.old || true; } && mv src.new src && bash src/deploy/setup.sh'
