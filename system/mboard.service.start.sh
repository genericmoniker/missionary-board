#!/usr/bin/env bash

# Start the Missionary Board server the first time or update to a newer version.

set -euo pipefail

username="orangepi"

echo "> Pulling latest code"
git pull

echo "> Installing dependencies"
uv sync

echo "> Starting the server"
uv run uvicorn --app-dir src --log-config conf/uvicorn.logger.json mboard.main:app

echo "> Waiting for the server to be ready"
count=0
until $(curl --output /dev/null --silent --head --fail http://127.0.0.1:8000/ready); do
    count=$((count+1))
    if [ $count -gt 30 ]; then
        echo
        echo "ERROR: The server failed to start."
        echo "Check the logs with 'journalctl --user -u mboard'."
        exit 1
    fi
    printf '.'
    sleep 1
done

echo
echo "> Refreshing the browser"
export DISPLAY=:0.0
export XAUTHORITY=/home/$username/.Xauthority
xdotool key --window $(xdotool getactivewindow) ctrl+shift+R

echo
echo "> Done"
