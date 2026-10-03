#!/usr/bin/env bash
# On the server (Ubuntu 24.04, e.g. Oracle Cloud's free ARM server): install what Jobreach needs
# the first time, then build and (re)start it. Safe to run again: that is how an update is
# applied. deploy/ship.sh runs it for you. No Docker: Ubuntu's own packages, Node.js from
# nodejs.org (checksum verified), and three systemd services behind Caddy.
#
#   ~/jobreach/src     the code (replaced on every ship)
#   ~/jobreach/.env    settings and secrets (copied by ship.sh, readable only by this user)
#   ~/jobreach/venv    Python packages for the API and the worker
#   ~/jobreach/home    the services' home folder (LibreOffice writes there)
#   /opt/node          Node.js, for the web app
set -euo pipefail
BASE="$HOME/jobreach"
SRC="$BASE/src"
ENV_FILE="$BASE/.env"
NODE_VERSION="22.18.0"

setting() { grep -m1 "^$1=" "$ENV_FILE" | cut -d= -f2-; }
if [ ! -f "$ENV_FILE" ]; then
  echo "$ENV_FILE is missing: deploy/ship.sh copies it here from your PC." >&2
  exit 1
fi
chmod 600 "$ENV_FILE"
DOMAIN="$(setting SITE_DOMAIN)"
[ -n "$DOMAIN" ] || { echo "SITE_DOMAIN is not set in $ENV_FILE" >&2; exit 1; }

echo "== System packages (Python, LibreOffice, Carlito, Caddy)"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
  python3-venv libreoffice-writer-nogui fonts-crosextra-carlito fontconfig caddy \
  curl xz-utils ca-certificates >/dev/null

echo "== Node.js $NODE_VERSION"
if [ "$(/opt/node/bin/node --version 2>/dev/null)" != "v$NODE_VERSION" ]; then
  case "$(uname -m)" in
    aarch64) ARCH=arm64 ;;
    x86_64) ARCH=x64 ;;
    *) echo "Unsupported processor: $(uname -m)" >&2; exit 1 ;;
  esac
  TARBALL="node-v$NODE_VERSION-linux-$ARCH.tar.xz"
  TMP="$(mktemp -d)"
  curl -fsSL -o "$TMP/$TARBALL" "https://nodejs.org/dist/v$NODE_VERSION/$TARBALL"
  curl -fsSL -o "$TMP/SHASUMS256.txt" "https://nodejs.org/dist/v$NODE_VERSION/SHASUMS256.txt"
  (cd "$TMP" && grep " $TARBALL\$" SHASUMS256.txt | sha256sum -c --quiet -)
  sudo rm -rf /opt/node
  sudo mkdir -p /opt/node
  sudo tar -xJf "$TMP/$TARBALL" -C /opt/node --strip-components=1
  rm -rf "$TMP"
fi
export PATH="/opt/node/bin:$PATH"

echo "== API and worker: Python packages"
[ -d "$BASE/venv" ] || python3 -m venv "$BASE/venv"
"$BASE/venv/bin/pip" install -q --upgrade pip
"$BASE/venv/bin/pip" install -q -r "$SRC/backend/requirements.txt"
mkdir -p "$BASE/home"

echo "== Web app: build (a few minutes the first time)"
cd "$SRC/frontend"
npm ci --no-audit --no-fund --loglevel=error
NEXT_TELEMETRY_DISABLED=1 \
NEXT_PUBLIC_SUPABASE_URL="$(setting NEXT_PUBLIC_SUPABASE_URL)" \
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY="$(setting NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY)" \
NEXT_PUBLIC_API_URL="https://$DOMAIN/api" \
  npm run build --silent
cp -r public .next/standalone/
mkdir -p .next/standalone/.next
cp -r .next/static .next/standalone/.next/

echo "== Services"
for unit in jobreach-api jobreach-worker jobreach-web; do
  sed "s#__USER__#$USER#g; s#__BASE__#$BASE#g" "$SRC/deploy/systemd/$unit.service" \
    | sudo tee "/etc/systemd/system/$unit.service" >/dev/null
done
sudo systemctl daemon-reload
sudo systemctl enable -q jobreach-api jobreach-worker jobreach-web
sudo systemctl restart jobreach-api jobreach-worker jobreach-web

echo "== HTTPS (Caddy gets the certificate by itself)"
sed "s#__DOMAIN__#$DOMAIN#g" "$SRC/deploy/Caddyfile" | sudo tee /etc/caddy/Caddyfile >/dev/null
sudo systemctl enable -q caddy
sudo systemctl reload caddy 2>/dev/null || sudo systemctl restart caddy

echo "== Firewall: let HTTP and HTTPS in (Oracle's Ubuntu allows only SSH)"
for rule in "tcp 80" "tcp 443" "udp 443"; do
  set -- $rule
  sudo iptables -C INPUT -p "$1" --dport "$2" -j ACCEPT 2>/dev/null \
    || sudo iptables -I INPUT 1 -p "$1" --dport "$2" -j ACCEPT
done
if command -v netfilter-persistent >/dev/null 2>&1; then
  sudo netfilter-persistent save >/dev/null
fi

echo "== Check"
for _ in $(seq 1 30); do curl -fsS -o /dev/null http://127.0.0.1:8000/health && break; sleep 2; done
curl -fsS -o /dev/null http://127.0.0.1:8000/health && echo "API: up" || echo "API: not answering (journalctl -u jobreach-api -n 50)"
for _ in $(seq 1 15); do curl -fsS -o /dev/null http://127.0.0.1:3000/login && break; sleep 2; done
curl -fsS -o /dev/null http://127.0.0.1:3000/login && echo "Web: up" || echo "Web: not answering (journalctl -u jobreach-web -n 50)"
systemctl is-active --quiet jobreach-worker && echo "Worker: running" || echo "Worker: stopped (journalctl -u jobreach-worker -n 50)"
echo "Site: https://$DOMAIN (the certificate arrives within a minute once the DNS record points here)"
