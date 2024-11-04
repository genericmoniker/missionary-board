"""Decorator to require login for a function."""

import asyncio
import functools
import inspect
from collections.abc import Callable

from starlette.responses import RedirectResponse, Response


def login_required(func: Callable) -> Callable:
    """Require login for a function.

    If the user is not logged in, they will be redirected to the login page.

    The function must have a `request` argument.
    """

    def _func_args(func: Callable, *args, **kwargs) -> dict:
        """Get the arguments for a function, including defaults."""
        signature = inspect.signature(func)
        arguments = signature.bind(*args, **kwargs)
        arguments.apply_defaults()
        return arguments.arguments

    def _check_login(*args, **kwargs) -> RedirectResponse | None:
        """Return a redirect response if the user is not logged in."""
        request = _func_args(func, *args, **kwargs)["request"]
        if request.session.get("user") != "admin":
            return RedirectResponse(request.url_for("login"), status_code=303)
        return None

    if asyncio.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper_decorator(*args, **kwargs) -> Response:
            return _check_login(*args, **kwargs) or await func(*args, **kwargs)

        return async_wrapper_decorator

    @functools.wraps(func)
    def syc_wrapper_decorator(*args, **kwargs) -> Response:
        return _check_login(*args, **kwargs) or func(*args, **kwargs)

    return syc_wrapper_decorator
