#!/bin/bash

# Multi-platform Docker image build.

set -euo pipefail

IMAGE_NAME="genericmoniker/mboard"
CACHE_IMAGE_NAME="genericmoniker/mboard-cache"

# Get the Git commit and branch.
GIT_COMMIT=$(set -e && git rev-parse --short HEAD)
GIT_BRANCH=$(set -e && git rev-parse --abbrev-ref HEAD)

GIT_DEFAULT_BRANCH="main"

# Set two complete image names:
IMAGE_WITH_COMMIT="${IMAGE_NAME}:commit-${GIT_COMMIT}"
IMAGE_WITH_BRANCH="${IMAGE_NAME}:${GIT_BRANCH}"
IMAGE_WITH_DEFAULT_BRANCH="${IMAGE_NAME}:${GIT_DEFAULT_BRANCH}"
CACHE_IMAGE_WITH_BRANCH="${CACHE_IMAGE_NAME}:${GIT_BRANCH}"

# Build the image, giving it two names.
#
# Multiplatform build:
# * linux/arm/v7 to run on Raspberry Pi 2
# * linux/arm/v8 to run on Orange Pi 3 LTS
# * linux/arm64 for new Pis
# * linux/amd64 for desktop
docker buildx build \
       -t "${IMAGE_WITH_COMMIT}" \
       -t "${IMAGE_WITH_BRANCH}" \
       --label "git-commit=${GIT_COMMIT}" \
       --label "git-branch=${GIT_BRANCH}" \
       --platform linux/arm/v8 \
       --progress plain \
       --push \
       .
    #    --cache-from=type=registry,ref="${CACHE_IMAGE_WITH_BRANCH}" \
    #    --cache-to=type=registry,ref="${CACHE_IMAGE_WITH_BRANCH}",mode=max \
