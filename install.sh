#! /bin/bash

set -x
set -euo pipefail

# Install the backend service
mkdir -p ~/.config/systemd/user
cp system/mboard.service ~/.config/systemd/user/
systemctl --user enable mboard
systemctl --user start mboard
