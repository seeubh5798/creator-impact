#!/usr/bin/env bash
# One-time bootstrap for a fresh Ubuntu 24.04 EC2 instance.
# Run as the default user:  curl -fsSL https://raw.githubusercontent.com/seeubh5798/creator-impact/prod/deploy/ec2-setup.sh | bash
# (or copy the file over and run `bash ec2-setup.sh`). Safe to re-run.
set -euo pipefail

APP_DIR=/opt/creator-impact

echo "==> Installing Docker"
if ! command -v docker >/dev/null; then
  sudo apt-get update -y
  sudo apt-get install -y ca-certificates curl
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi
sudo usermod -aG docker "$USER"

echo "==> Preparing $APP_DIR"
sudo mkdir -p "$APP_DIR"
sudo chown "$USER":"$USER" "$APP_DIR"
if [ ! -f "$APP_DIR/.env" ]; then
  curl -fsSL https://raw.githubusercontent.com/seeubh5798/creator-impact/prod/deploy/env.prod.example -o "$APP_DIR/.env" 2>/dev/null || true
  chmod 600 "$APP_DIR/.env"
  echo "    Created $APP_DIR/.env from the example. EDIT IT before the first deploy."
fi

echo "==> Basic hardening"
sudo apt-get install -y unattended-upgrades fail2ban >/dev/null
sudo systemctl enable --now fail2ban >/dev/null 2>&1 || true

# 1 GB swap keeps a t3.small from OOM-killing the worker on big posts.
if ! swapon --show | grep -q swapfile; then
  sudo fallocate -l 1G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile >/dev/null && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

echo
echo "Done. Next:"
echo "  1. nano $APP_DIR/.env   (fill in every value)"
echo "  2. log out and back in so 'docker' works without sudo"
echo "  3. push to the prod branch; the GitHub Action deploys here"
