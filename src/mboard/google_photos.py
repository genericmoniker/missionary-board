"""Google Photos API client.

To enable the Google Photos API, go to:
https://console.cloud.google.com/apis/library/photoslibrary.googleapis.com

To manage credentials (client ID and secret), go to:
https://console.cloud.google.com/apis/credentials
"""
from typing import Callable

from authlib.integrations.httpx_client import AsyncOAuth2Client  # type: ignore


def setup_auth(client_id: str, client_secret: str, redirect_uri: str):
    """Set up authorization to the user's Google Photos account."""

    # Note that authlib has built-in integration with Starlette and other frameworks
    # but in order to keep this module independent from the web framework it uses
    # the more general httpx client instead.

    scope = "https://www.googleapis.com/auth/photoslibrary.readonly"
    client = AsyncOAuth2Client(
        client_id, client_secret, scope=scope, redirect_uri=redirect_uri
    )
    auth_url, state = client.create_authorization_url(
        "https://accounts.google.com/o/oauth2/v2/auth",
        access_type="offline",
        include_granted_scopes="true",
        prompt="select_account",
    )
    return auth_url, state


async def authorize(
    client_id: str,
    client_secret: str,
    state: str,
    redirect_uri: str,
    authorization_code: str,
):
    """Authorize the user's Google Photos account.

    The client_id, client_secret, redirect_uri values are those used
    to register the application with Google.

    The state value is the one returned by setup_auth().

    The authorization_code value is the one returned by Google in the
    redirect URI query params after the user has authorized the application.
    """
    # https://docs.authlib.org/en/latest/client/oauth2.html#fetch-token
    client = AsyncOAuth2Client(client_id, client_secret, state=state)
    token = await client.fetch_token(
        "https://oauth2.googleapis.com/token",
        redirect_uri=redirect_uri,
        code=authorization_code,
        grant_type="authorization_code",
    )  # type: ignore
    return token


class GooglePhotosClient:
    """Client for the Google Photos API."""

    def __init__(
        self, token: dict, update_token: Callable, client_id: str, client_secret: str
    ):
        self.client = AsyncOAuth2Client(
            token=token,
            update_token=update_token,
            token_endpoint="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
        )

    async def get_albums(self):
        """Get the list of albums."""
        # https://developers.google.com/photos/library/reference/rest/v1/albums/list
        response = await self.client.get(
            "https://photoslibrary.googleapis.com/v1/albums",
            params={"pageSize": 50},  # 50 is the maximum (add pagination support?)
        )
        response.raise_for_status()
        return response.json().get("albums", [])

    # async def get_album(self, album_id: str):
    #     """Get the details of an album."""
    #     # https://developers.google.com/photos/library/reference/rest/v1/albums/get
    #     response = await self.client.get(
    #         f"https://photoslibrary.googleapis.com/v1/albums/{album_id}"
    #     )
    #     response.raise_for_status()
    #     return response.json().get("album", {})

    async def get_media_items(self, album_id: str):
        """Get the list of media items in an album."""
        # https://developers.google.com/photos/library/reference/rest/v1/mediaItems/search
        # If there are more than 100 items, we'll need to add pagination support.
        response = await self.client.post(
            "https://photoslibrary.googleapis.com/v1/mediaItems:search",
            json={
                "albumId": album_id,
                "pageSize": 100,
            },
        )
        response.raise_for_status()
        return response.json().get("mediaItems", [])

    # async def get_media_item(self, media_item_id: str):
    #     """Get the details of a media item."""
    #     # https://developers.google.com/photos/library/reference/rest/v1/mediaItems/get
    #     response = await self.client.get(
    #         f"https://photoslibrary.googleapis.com/v1/mediaItems/{media_item_id}"
    #     )
    #     response.raise_for_status()
    #     return response.json()

    async def get_media_item_bytes(self, media_item_id: str):
        """Get the bytes of a media item."""
        # https://developers.google.com/photos/library/reference/rest/v1/mediaItems/get
        response = await self.client.get(
            f"https://photoslibrary.googleapis.com/v1/mediaItems/{media_item_id}:getMedia"
        )
        response.raise_for_status()
        return response.content
