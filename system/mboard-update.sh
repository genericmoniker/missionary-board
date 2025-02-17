#! /bin/bash

# Check for updates by comparing the current git hash with the latest git hash
# on the main branch. If there is a difference, update the system.

set -euo pipefail

# Ensure the script is run from the correct directory
cd "$(dirname "$0")/.."

current_hash=$(git rev-parse HEAD)
latest_hash=$(git ls-remote origin -h refs/heads/main | cut -f1)

if [ "$current_hash" != "$latest_hash" ]; then
    echo "System update available. Updating to commit hash ${latest_hash}..."
    git pull || { echo "Failed to pull latest changes"; exit 1; }
    ./install.sh || { echo "Failed to run install script"; exit 1; }
    sudo systemctl restart mboard || { echo "Failed to restart mboard service"; exit 1; }
    echo "System updated."
else
    echo "System is up to date at commit hash ${current_hash}."
fi
