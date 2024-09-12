import pytest

from starbear import here

from .utils import serve


@pytest.fixture(scope="module")
def app_hello():
    with serve("-m", "tests.server.app_hello") as addr:
        yield addr


def test_index(app_hello, page):
    page.goto(f"{app_hello}")
    text = page.locator("body").inner_text()
    assert "hello" in text
    assert "world" in text
    assert "Venus" in text
    assert "Jupiter" in text
    assert "Mars" in text


def test_subindex(app_hello, page):
    page.goto(f"{app_hello}/world")
    text = page.locator("body").inner_text()
    assert "hello" not in text
    assert "world" in text
    assert "Venus" in text
    assert "Jupiter" in text
    assert "Mars" in text


def test_hello(app_hello, page):
    page.goto(f"{app_hello}/hello")
    assert page.locator("h1").inner_text() == "HELLO"


def test_subdirectory(app_hello, page):
    page.goto(f"{app_hello}/world/venus")
    assert page.locator("h1").inner_text() == "VENUS!"


def test_root_argument(page):
    page.set_default_timeout(500)
    with serve("--root", here / "app_hello" / "world" / "venus.py") as addr:
        page.goto(addr)
        assert page.locator("h1").inner_text() == "VENUS!"


def test_subroutes_index(app_hello, page):
    page.goto(f"{app_hello}/world/jupiter")
    assert page.locator("h1").inner_text() == "JUPITER!"


def test_subroutes_bear(app_hello, page):
    page.goto(f"{app_hello}/world/jupiter/titan")
    assert page.locator("h1").inner_text() == "TITAN!"


def test_subroutes_simple_route(app_hello, page):
    page.goto(f"{app_hello}/world/jupiter/europa")
    assert page.locator("h1").inner_text() == "EUROPA!"


def test_subroutes_starlette_route(app_hello, page):
    page.goto(f"{app_hello}/world/jupiter/ganymede")
    assert page.locator("h1").inner_text() == "GANYMEDE!"
