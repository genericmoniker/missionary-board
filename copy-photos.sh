#!/bin/bash

# This script copies photos from the local deployment to a remote server.
# To use it, you should have a server called "mboard" in your SSH config file.

rsync -a --progress --exclude='*/' \
    ./instance/photos/ mboard:missionary-board/instance/photos/
