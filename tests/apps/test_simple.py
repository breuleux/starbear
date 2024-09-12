from hrepr import H

from starbear import bear


@bear
async def __app__(page):
    page.print(H.div("hello world!", id="hello"))


def test_title(app):
    assert app.locator("title").inner_text() == "Starbear"


def test_charset(app):
    assert app.locator('meta[http-equiv="Content-type"]').get_attribute("charset") == "UTF-8"


def test_hello(app):
    assert app.locator("#hello").inner_text() == "hello world!"
    assert app.locator("html").inner_text() == "hello world!"  # Check there's no junk
