#! /bin/bash

set -x
set -euo pipefail

git config pull.ff only

# Install the backend service
mkdir -p ~/.config/systemd/user
cp ./system/mboard.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable mboard
systemctl --user restart mboard 

# Install the autostart file to run the browser
cp ./system/mboard.desktop ~/.config/autostart/
