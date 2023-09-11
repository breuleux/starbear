import traceback
from functools import wraps

from hrepr import H


def with_error_display(app):
    @wraps(app)
    async def wrapped_app(page):
        page["head"].print(
            H.style(
                """
        .STARBEAR__error:empty {
            display: none;
        }
        .STARBEAR__error {
            position: absolute;
            right: 0;
            top: 0;
            border: 1px solid red;
            padding: 3px;
            max-height: 300px;
            overflow: scroll;
            white-space: pre;
            color: black;
            background: white;
        }
        """
            )
        )
        page.print(err_div := H.div["STARBEAR__error"]().autoid())
        try:
            await app(page)
        except Exception as exc:
            page[err_div].set(
                H.div(
                    H.b("An error occurred. You may need to refresh the page.\n\n"),
                    traceback.format_exc(),
                )
            )
            raise

    return wrapped_app
