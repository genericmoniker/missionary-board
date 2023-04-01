# syntax = docker/dockerfile:1.2
ARG PYTHON_VERSION=3.10
FROM python:${PYTHON_VERSION}-slim-buster AS build-image

RUN export DEBIAN_FRONTEND=noninteractive && \
  apt-get update && \
  apt-get install -y --no-install-recommends curl build-essential python-dev libffi-dev libssl-dev

# Install PDM.
RUN curl -sSL https://raw.githubusercontent.com/pdm-project/pdm/main/install-pdm.py | python3 - --version=2.3.2
ENV PATH=/root/.local/bin:${PATH}

# Need Rust for Python Cryptography >=3.5 (or actually 35.0.0 -- version scheme change).
# I'm having trouble making this work (e.g. "spurious network error" trying to get pyo3
# dependency). So for now, we'll use an older version and disable rust. See also
# https://github.com/rust-lang/rustup/issues/2700 (but the workaround there didn't work
# for me).
ENV CRYPTOGRAPHY_DONT_BUILD_RUST=1

# We don't create the appuser yet, but we'll still use this as the WORKDIR
# so that shebangs in any scripts match up when we copy the virtualenv.
ENV ROOTDIR=/home/appuser

WORKDIR ${ROOTDIR}

# Install dependencies.
COPY pyproject.toml pdm.lock ./
RUN pdm install --prod --no-lock --no-editable

# ============================================================================

FROM python:${PYTHON_VERSION}-slim-buster AS run-image

# Install security updates, and some useful packages.
RUN export DEBIAN_FRONTEND=noninteractive && \
  apt-get update && \
  apt-get -y upgrade && \
  apt-get install -y --no-install-recommends tini procps net-tools && \
  apt-get -y clean && \
  rm -rf /var/lib/apt/lists/*

# Create a new user to run as.
RUN useradd --create-home appuser
USER appuser
WORKDIR /home/appuser

# Copy virtualenv
COPY --from=build-image --chown=appuser /home/appuser/.venv ./.venv
ENV PATH="/home/appuser/.venv/bin:$PATH"

# Copy in the application code.
COPY --chown=appuser . .

# Prepare for C crashes.
ENV PYTHONFAULTHANDLER=1

# Run the code when the image is run:
CMD ["tini", "--", "uvicorn", "--app-dir", "src", "--log-config conf/uvicorn.logger.json", "mboard.main:app"]
