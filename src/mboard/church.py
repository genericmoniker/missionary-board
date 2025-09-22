"""Church website access.

This module is deliberately similar to the lcr_session module, but is intended to be an
abstraction that can handle authentication in different ways because sometimes
lcr_session is out-of-sync with the Church's website.

To switch to using lcr_session, make Session a base class and create subclasses for each
authentication method. Then the `create` function can be modified to return an instance
of the appropriate subclass.
"""

import asyncio
import getpass
import logging
import sys
from dataclasses import asdict, dataclass

import httpx
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    Response,
    async_playwright,
)

logger = logging.getLogger(__name__)


_HEADLESS = True  # Set to False for testing/debugging the Playwright browser.


@dataclass
class _User:
    """A user of the Church's website."""

    unit: int
    """Assigned unit number. For example, the Ward unit number."""

    parent_unit: int
    """Parent unit number, for example the stake."""

    member_id: int
    """Member ID according to LCR"""

    uuid: str
    """Unique UUID for the user."""


class URL:
    """A URL under the "churchofjesuschrist.org" domain.

    Attributes:
        subdomain: The subdomain to prepend to the base domain.
        path: The path to append to the base domain.
        query: The query string to append to the URL.

    Example:
        url = URL(subdomain="example", path="/hi", query="unitNumber={parent_unit}")
        render result: "https://example.churchofjesuschrist.org/hi?unitNumber=123456"

    """

    def __init__(self, subdomain: str, path: str = "", query: str = "") -> None:
        path = path if path.startswith("/") else f"/{path}"
        query = query if query == "" or query.startswith("?") else f"?{query}"
        self._raw = f"https://{subdomain}.churchofjesuschrist.org{path}{query}"

    def render(self, **kwargs: dict | None) -> str:
        """Render the URL with template parameters replaced from the user object."""
        return self._raw.format(**(kwargs or {}))


class Session:
    """A session for accessing the Church's website."""

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._user: _User | None = None

    @classmethod
    async def create(cls, username: str, password: str) -> "Session":
        """Asynchronously create and initialize a new instance of the Session class."""
        self = cls(username, password)
        context_manager = async_playwright()
        self._playwright = await context_manager.start()
        self._browser = await self._playwright.chromium.launch(headless=_HEADLESS)
        self._context = await self._browser.new_context()
        self._page = await self._context.new_page()
        return self

    async def close(self) -> None:
        """Close the session and clean up resources."""
        if self._page is not None:
            await self._page.close()
            self._page = None
        if self._context is not None:
            await self._context.close()
            self._context = None
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def get_json(self, url: URL | str) -> dict:
        """Get JSON data from a URL."""
        if self._page is None:
            msg = "Use `Session.create` to initialize the session."
            raise RuntimeError(msg)

        if isinstance(url, URL):
            if self._user is None:
                await self._login()
            if self._user is None:
                msg = "Failed to log in and get user info."
                raise RuntimeError(msg)
            url = url.render(**asdict(self._user))

        response = await self._page.goto(url)
        if response is None or response.status == httpx.codes.UNAUTHORIZED:
            await self._login()
            response = await self._page.goto(url)
        if response is None or response.status != httpx.codes.OK:
            msg = f"Failed to get JSON data: {response}"
            raise RuntimeError(msg)
        return await response.json()

    async def _login(self) -> None:
        if self._page is None:
            msg = "Use `Session.create` to initialize the session."
            raise RuntimeError(msg)

        logger.info("Logging in as %s", self._username)

        # URL that will redirect to the login page if not authenticated.
        url = URL("lcr").render()

        # Handle the login interaction.
        await self._page.goto(url)
        await self._page.fill('input[id="username-input"]', self._username)
        await self._page.keyboard.press("Enter")
        await self._page.fill('input[type="password"]', self._password)
        await self._page.keyboard.press("Enter")
        await self._page.wait_for_url(url)

        # This is a bit weird. The first attempt to load the user URL fails with a
        # 401, but a reload usually succeeds and appears to set additional cookies.
        logger.debug("Getting user info")
        url = URL("directory", "api/v4/user").render()
        response = await self._page.goto(url)
        count = 1
        max_retries = 3
        while not await _is_successful_user_response(response):
            logger.debug("Retrying user info fetch (%d/%d)", count, max_retries)
            if count >= max_retries:
                msg = f"Failed to get user info: {response}"
                raise RuntimeError(msg)
            await asyncio.sleep(5)
            response = await self._page.reload()
            count += 1
        user = await response.json()  # type: ignore
        self._user = _User(
            unit=user["homeUnits"][0],
            parent_unit=user["parentUnits"][0],
            member_id=user["individualId"],
            uuid=user["uuid"],
        )


async def _is_successful_user_response(response: Response | None) -> bool:
    if response is None:
        return False
    if response.status == httpx.codes.UNAUTHORIZED:
        return False
    return "homeUnits" in await response.json()


async def test_main() -> None:
    """Manual test entry point."""
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

    username = input("Username: ")
    password = getpass.getpass("Password: ")
    session = await Session.create(username, password)
    url = URL(
        "lcr",
        "api/orgs/full-time-missionaries",
        "lang=eng&unitNumber={parent_unit}",
    )
    data = await session.get_json(url)
    print(data)  # noqa: T201
    await session.close()


if __name__ == "__main__":
    asyncio.run(test_main())
