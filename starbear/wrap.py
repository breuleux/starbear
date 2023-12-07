import traceback
from functools import wraps

from hrepr import H


def with_error_display(app):
    @wraps(app)
    async def wrapped_app(page):
        try:
            await app(page)
        except Exception as exc:
            page["#starbear-error"].set(
                H.div(
                    H.b("An error occurred. You may need to refresh the page.\n\n"),
                    traceback.format_exc(),
                )
            )
            raise

    return wrapped_app
