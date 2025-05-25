#!/bin/bash

# This script copies photos from the local deployment to a remote server.
# To use it, you should have a server called "mboard" in your SSH config file.
# To avoid password prompts, you can set up SSH key authentication. For example:
# $ ssh-keygen -t ed25519 -C "your_email@example.com"
# $ ssh-copy-id -i ~/.ssh/id_ed25519.pub mboard

rsync --archive --progress --exclude='*/' \
    ./instance/photos/ mboard:missionary-board/instance/photos/
rsync --archive --progress --exclude='*/' \
    ./instance/extra/ mboard:missionary-board/instance/extra/
