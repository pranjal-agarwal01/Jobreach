#!/usr/bin/env bash
# On the server (Ubuntu 24.04 on Oracle Cloud): install Docker the first time, let web traffic
# through the server's own firewall, then build and (re)start Jobreach. Safe to run again: that
# is how an update is applied. deploy/ship.sh runs it for you.
set -euo pipefail
cd "$(dirname "$0")"                    # the deploy/ folder

if ! command -v docker >/dev/null 2>&1; then
  echo "Installing Docker (Ubuntu's own packages)..."
  sudo apt-get update -y
  sudo apt-get install -y docker.io docker-compose-v2
  sudo systemctl enable --now docker
fi

# Oracle's Ubuntu images accept only SSH at the server's firewall. Let HTTP and HTTPS in.
for rule in "tcp 80" "tcp 443" "udp 443"; do
  set -- $rule
  sudo iptables -C INPUT -p "$1" --dport "$2" -j ACCEPT 2>/dev/null \
    || sudo iptables -I INPUT 1 -p "$1" --dport "$2" -j ACCEPT
done
if command -v netfilter-persistent >/dev/null 2>&1; then
  sudo netfilter-persistent save >/dev/null
fi

if [ ! -f .env ]; then
  echo "deploy/.env is missing: deploy/ship.sh copies it here from your PC." >&2
  exit 1
fi
chmod 600 .env

echo "Building and starting (the first build takes a few minutes)..."
sudo docker compose up -d --build --remove-orphans
sudo docker image prune -f >/dev/null
sudo docker compose ps
