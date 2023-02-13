"""Google Photos API client.

To enable the Google Photos API, go to:
https://console.cloud.google.com/apis/library/photoslibrary.googleapis.com

To manage credentials (client ID and secret), go to:
https://console.cloud.google.com/apis/credentials
"""
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
    redirect URI after the user has authorized the application.
    """
    # https://docs.authlib.org/en/latest/client/oauth2.html#fetch-token
    client = AsyncOAuth2Client(client_id, client_secret, state=state)
    token = await client.fetch_token(
        "https://oauth2.googleapis.com/token",
        redirect_uri=redirect_uri,
        code=authorization_code,
        grant_type="authorization_code",
    )  # type: ignore # This becomes an awaitable through some trickery in authlib.
    print(token)
    # return full credentials
