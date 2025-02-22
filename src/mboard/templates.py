"""Templates for the application."""

from pathlib import Path

from starlette.templating import Jinja2Templates

templates = Jinja2Templates(
    directory=str(Path(__file__).parent.parent.parent / "templates"),
)
