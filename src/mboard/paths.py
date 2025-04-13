"""Filesystem paths for the application."""

from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.parent
INSTANCE_DIR = ROOT_DIR / "instance"
PHOTOS_DIR = INSTANCE_DIR / "photos"
COOKIE_FILE = INSTANCE_DIR / "cookies"

PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
