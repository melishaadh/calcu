#!/usr/bin/env bash
#
# ec2-provision.sh — one-time setup for a fresh Ubuntu 22.04/24.04 EC2 instance.
#
# Installs Docker Engine + the Compose v2 plugin from Docker's official apt
# repo, lets the default user run docker without sudo, and enables Docker on
# boot. Safe to re-run.
#
# Usage (on the EC2 instance):
#   chmod +x deploy/ec2-provision.sh
#   ./deploy/ec2-provision.sh
#   # then log out and back in so the docker group membership takes effect

set -euo pipefail

echo "==> Updating base packages"
sudo apt-get update -y
sudo apt-get upgrade -y

echo "==> Installing prerequisites"
sudo apt-get install -y ca-certificates curl gnupg git ufw

echo "==> Adding Docker's official apt repository"
sudo install -m 0755 -d /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/docker.asc ]; then
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
fi
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

echo "==> Installing Docker Engine + Compose plugin"
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "==> Enabling Docker on boot"
sudo systemctl enable --now docker

echo "==> Adding user '$USER' to the docker group"
sudo usermod -aG docker "$USER"

echo "==> Configuring the host firewall (ufw)"
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw --force enable

echo
echo "Provisioning complete."
echo "Docker:  $(sudo docker --version)"
echo "Compose: $(sudo docker compose version)"
echo
echo "IMPORTANT: log out and back in (or run 'newgrp docker') before deploying,"
echo "so you can run docker commands without sudo."
