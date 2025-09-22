#! /bin/bash

# Install steps requiring root privileges.

set -x
set -euo pipefail

# Playwright
uv run playwright install-deps chromium && uv run playwright install chromium

# Install unclutter to hide the mouse cursor.
sudo apt install -y unclutter

# Set up scheduled reboot.
cp ./system/mboard-reboot.service /etc/systemd/system/
cp ./system/mboard-reboot.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable mboard-reboot.timer
systemctl restart mboard-reboot.timer

# Journal configuration (persistent logs).
mkdir -p /etc/systemd/journald.conf.d
cp ./system/mboard-journald.conf /etc/systemd/journald.conf.d/

set +x
echo "OK"
