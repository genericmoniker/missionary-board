#! /bin/bash

set -x
set -euo pipefail

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

# Install the autostart file to run the browser
cp ./system/mboard.desktop ~/.config/autostart/
