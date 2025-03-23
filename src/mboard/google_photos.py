"""Google Photos API client.

To enable the Google Photos API, go to:
https://console.cloud.google.com/apis/library/photoslibrary.googleapis.com

To manage credentials (client ID and secret), go to:
https://console.cloud.google.com/apis/credentials
"""

from collections.abc import Callable

from authlib.integrations.httpx_client import AsyncOAuth2Client


class GooglePhotosClient:
    """Client for the Google Photos API."""

    def __init__(
        self,
        token: dict,
        update_token_function: Callable,
        client_id: str,
        client_secret: str,
    ) -> None:
        """Initialize the client.

        `token` is the token dictionary returned by authorize(). It should be stored
        and passed to this constructor.

        `update_token_function` is a function that will be called when the token is
        updated. It should store the new token in a database or other persistent
        storage.

        `client_id` and `client_secret` are the values used to register the application
        with Google.
        """
        self.client = AsyncOAuth2Client(
            token=token,
            update_token=update_token_function,
            token_endpoint="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
        )

    async def get_albums(self) -> list:
        """Get the list of albums."""
        # https://developers.google.com/photos/library/reference/rest/v1/albums/list
        response = await self.client.get(
            "https://photoslibrary.googleapis.com/v1/albums",
            params={"pageSize": 50},  # 50 is the maximum (add pagination support?)
        )
        response.raise_for_status()
        return response.json().get("albums", [])

    async def get_media_items(self, album_id: str) -> list:
        """Search for the list of media items in an album."""
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

    async def download(self, media_item_base_url: str) -> bytes:
        """Get the bytes of a media item."""
        response = await self.client.get(media_item_base_url)
        response.raise_for_status()
        return response.content
