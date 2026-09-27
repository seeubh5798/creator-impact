#!/usr/bin/env bash
# One-time bootstrap for a fresh Ubuntu 24.04 EC2 instance (dev or prod).
#
# From your laptop, in the repo folder:
#   scp -i ~/.ssh/proofluence-dev.pem deploy/ec2-setup.sh ubuntu@<ELASTIC_IP>:~
#   ssh -i ~/.ssh/proofluence-dev.pem ubuntu@<ELASTIC_IP> 'bash ec2-setup.sh'
# Safe to re-run.
set -euo pipefail

APP_DIR=/opt/proofluence

echo "==> Installing Docker"
if ! command -v docker >/dev/null; then
  sudo apt-get update -y
  sudo apt-get install -y ca-certificates curl gnupg
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
  touch "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  echo "    Created an empty $APP_DIR/.env (permissions 600). Paste your config into it next."
fi

echo "==> Basic hardening"
sudo apt-get install -y unattended-upgrades fail2ban >/dev/null
sudo systemctl enable --now fail2ban >/dev/null 2>&1 || true
# Password SSH off (key only). Ubuntu AMIs already default to this; enforce it.
sudo sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl reload ssh 2>/dev/null || sudo systemctl reload sshd 2>/dev/null || true

# 1 GB swap keeps small instances from OOM-killing the worker on big posts.
if ! swapon --show | grep -q swapfile; then
  sudo fallocate -l 1G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile >/dev/null && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

echo
echo "Done. Next:"
echo "  1. nano $APP_DIR/.env   (paste the dev or prod template from docs/AWS_SETUP.md, fill every value)"
echo "  2. exit and ssh back in (so 'docker' works without sudo)"
echo "  3. run the 'Deploy backend' GitHub Action for this environment"
