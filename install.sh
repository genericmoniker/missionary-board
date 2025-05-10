#! /bin/bash

set -x
set -euo pipefail

command -v uv >/dev/null 2>&1 || { curl -LsSf https://astral.sh/uv/install.sh | sh; }

git config pull.ff only

uv sync

# Install services
mkdir -p ~/.config/systemd/user
cp ./system/*.service ~/.config/systemd/user/
cp ./system/*.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable mboard.service
systemctl --user restart mboard.service
systemctl --user enable mboard-update.timer
systemctl --user restart mboard-update.timer

# Install the desktop files to run the browser and unclutter on startup.
mkdir -p ~/.config/autostart
cp ./system/*.desktop ~/.config/autostart/

set +x
echo "OK"
