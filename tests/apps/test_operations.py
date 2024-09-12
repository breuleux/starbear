import time

import pytest
from hrepr import H

from starbear import bear

from .utils import asset_getter

asset = asset_getter(__file__)


@bear(strongrefs=True)
async def __app__(page):
    out = H.div("?", id="output")
    page.print(
        H.button("Set", onclick=lambda e: page[out].set(H.b("S"))),
        H.button("Print", onclick=lambda e: page[out].print(H.i("P"))),
        H.button("Clear", onclick=lambda e: page[out].clear()),
        H.button("Delete", onclick=lambda e: page[out].delete()),
        H.button(
            "Template", onclick=lambda e: page[out].template(asset("template.html"), name="deer")
        ),
        out,
    )


@pytest.fixture
def check(app):
    def fn(expected, method="text"):
        assert getattr(app.locator("#output"), f"inner_{method}")() == expected

    return fn


@pytest.fixture
def click(app):
    def fn(lbl):
        app.get_by_text(lbl).click()
        time.sleep(0.05)

    return fn


def test_set(click, check):
    click("Set")
    check("S")
    check("<b>S</b>", method="html")


def test_opseq(click, check):
    check("?")
    click("Clear")
    check("")
    click("Print")
    click("Print")
    click("Print")
    check("PPP")
    click("Set")
    check("S")
    click("Print")
    check("SP")
    check("<b>S</b><i>P</i>", method="html")


def test_delete(click, app):
    assert app.locator("#output").count() == 1
    click("Delete")
    assert app.locator("#output").count() == 0


def test_template(click, check):
    click("Template")
    check("Greetings, deer")
