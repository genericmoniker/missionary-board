#!/usr/bin/env bash

# Start the Missionary Board server the first time or update to a newer version.

set -euo pipefail

username="orangepi"

echo "> Pulling latest image"
docker pull "genericmoniker/mboard:main"

echo "> Removing previous container"
docker stop mboard || true && docker rm mboard || true

echo "> Running latest image as a new container"
docker run \
    -d \
    --name="mboard" \
    -p 8000:8000 \
    --restart=always \
    --volume="/home/$username/mboard/instance:/home/appuser/instance" \
    -e TZ=America/Denver \
    "genericmoniker/mboard:main"

dangling_images=$(docker images -qa -f 'dangling=true')
if [ -n "$dangling_images" ]; then
    echo "> Removing dangling images"
    docker image rm $dangling_images
fi

echo "> Waiting for the server to be ready"
count=0
until $(curl --output /dev/null --silent --head --fail http://127.0.0.1:8000/ready); do
    count=$((count+1))
    if [ $count -gt 30 ]; then
        echo
        echo "ERROR: The server failed to start."
        echo "Check the logs with 'docker logs mboard'."
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
