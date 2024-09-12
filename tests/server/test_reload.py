import time
from contextlib import contextmanager

import pytest

from starbear import here

from .utils import serve


@pytest.fixture
def venus_mod(page, clone):
    tmp = clone(here / "app_hello")

    @contextmanager
    def load(*args, regoto=False):
        page.set_default_timeout(2500)
        with serve("--root", tmp, *args) as addr:
            page.goto(f"{addr}/world/venus")
            h1 = page.locator("h1")
            assert h1.inner_text() == "VENUS!"
            vfile = tmp / "world" / "venus.py"
            vfile.write_text(vfile.read_text().replace("VENUS!", "VENUSAUR!"))
            yield page
            if regoto:
                page.goto(f"{addr}/world/venus")
            assert h1.inner_text() == "VENUSAUR!"

    return load


@pytest.fixture
def pause(request):
    return request.config.getoption("--reload-pause")


def test_manual(venus_mod, pause):
    with venus_mod("--dev", "--reload-mode", "manual", regoto=True) as page:
        page.locator('.bear--tabular-button:has-text("⟳")').click()
        time.sleep(pause)


def test_jurigged(venus_mod, pause):
    with venus_mod("--dev"):
        time.sleep(pause)


def test_full(venus_mod, pause):
    with venus_mod("--dev", "--reload-mode", "full", regoto=True):
        time.sleep(pause)
