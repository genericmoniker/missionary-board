"""Church website access.

This module is deliberately similar to the lcr_session module, but is intended to be an
abstraction that can handle authentication in different ways because sometimes
lcr_session is broken.
"""

import asyncio
import getpass
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
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
from tenacity import after_log, retry, stop_after_attempt, wait_fixed

logger = logging.getLogger(__name__)


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
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        self._user = None

    async def get_json(self, url: URL | str) -> dict:
        """Get JSON data from a URL."""
        if isinstance(url, URL):
            if self._user is None:
                await self._login()
            if self._user is None:
                msg = "Failed to log in and get user info."
                raise RuntimeError(msg)
            url = url.render(**asdict(self._user))
        headers = {"Accept": "application/json"}
        response = await self._client.get(url, headers=headers)
        if response.status_code == httpx.codes.UNAUTHORIZED:
            await self._login()
            response = await self._client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    async def _login(self) -> None:
        async with (
            async_playwright() as playwright,
            _playwright_browser(playwright) as browser,
            _playwright_context(browser) as context,
        ):
            logger.info("Logging in as %s", self._username)

            # URL that will redirect to the login page if not authenticated.
            url = URL("lcr").render()

            page = await context.new_page()
            await page.goto(url)

            await page.fill('input[id="username-input"]', self._username)
            await page.keyboard.press("Enter")

            await page.fill('input[type="password"]', self._password)
            await page.keyboard.press("Enter")
            await page.wait_for_url(url)

            # This is a bit weird. The first attempt to load the user URL fails with a
            # 401, but a reload usually succeeds and appears to set additional cookies.
            logger.debug("Getting user info")
            url = URL("directory", "api/v4/user").render()
            response = await page.goto(url)
            count = 1
            max_retries = 3
            while not await _is_successful_user_response(response):
                logger.debug("Retrying user info fetch (%d/%d)", count, max_retries)
                if count >= max_retries:
                    msg = f"Failed to get user info: {response}"
                    raise RuntimeError(msg)
                await asyncio.sleep(5)
                response = await page.reload()
                count += 1
            user = await response.json()  # type: ignore
            self._user = _User(
                unit=user["homeUnits"][0],
                parent_unit=user["parentUnits"][0],
                member_id=user["individualId"],
                uuid=user["uuid"],
            )

            # Copy cookies (and maybe an authorization header) to the httpx client.
            self._client.cookies.clear()
            for cookie in await context.cookies():
                if "name" in cookie and "value" in cookie:
                    cookie_name = cookie["name"]
                    cookie_value = cookie["value"]
                    self._client.cookies.set(cookie_name, cookie_value)
                    logger.debug("Set cookie %s (%s)", cookie_name, len(cookie_value))

                    # Some APIs may require an Authorization header with a bearer token.
                    if cookie_name == "oauth_id_token":
                        self._client.headers.update(
                            {"Authorization": f"Bearer {cookie_value}"}
                        )


async def _is_successful_user_response(response: Response | None) -> bool:
    if response is None:
        return False
    if response.status == httpx.codes.UNAUTHORIZED:
        return False
    return "homeUnits" in await response.json()


@retry(
    stop=stop_after_attempt(4),
    wait=wait_fixed(2),
    after=after_log(logger, logging.DEBUG),
)
async def _get_user(page: Page, url: str) -> _User:
    """Get user info from the Church directory API."""
    await page.wait_for_url(url)
    response = await page.reload()
    if response is None or response.status != httpx.codes.OK:
        msg = f"Failed to get user info: {response}"
        raise RuntimeError(msg)
    user = await response.json()
    if "uuid" not in user:
        msg = f"Failed to get user info: {user}"
        raise RuntimeError(msg)
    return _User(
        unit=user["homeUnits"][0],
        parent_unit=user["parentUnits"][0],
        member_id=user["individualId"],
        uuid=user["uuid"],
    )


@asynccontextmanager
async def _playwright_browser(playwright: Playwright) -> AsyncIterator[Browser]:
    browser = await playwright.chromium.launch(headless=False)
    try:
        yield browser
    finally:
        await browser.close()


@asynccontextmanager
async def _playwright_context(browser: Browser) -> AsyncIterator[BrowserContext]:
    context = await browser.new_context()
    try:
        yield context
    finally:
        await context.close()


async def test_main() -> None:
    """Manual test entry point."""
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

    username = input("Username: ")
    password = getpass.getpass("Password: ")
    session = Session(username, password)
    url = URL(
        "lcr",
        "api/orgs/full-time-missionaries",
        "lang=eng&unitNumber={parent_unit}",
    )
    data = await session.get_json(url)
    print(data)  # noqa: T201


if __name__ == "__main__":
    asyncio.run(test_main())
