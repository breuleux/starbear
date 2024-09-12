from hrepr import H, J

from starbear import simplebear

from .utils import asset_getter

asset = asset_getter(__file__)


async def exponential(x):
    return (x * 2) or 1


@simplebear
async def __app__(request):
    return H.div(
        H.h1("Hello!", id="content"),
        J(module=asset("counter.js"))(increment=10, cls="c1"),
        J(module=asset("complex-counter.js"))(increment=exponential, cls="c2"),
    )


def test_simple(app):
    assert app.locator("#content").inner_text() == "Hello!"


def test_counter(app):
    counter = app.locator(".c1")
    value0 = int(counter.inner_text())
    counter.click()
    value1 = int(counter.inner_text())
    counter.click()
    value2 = int(counter.inner_text())
    assert value2 == value1 + 10 == value0 + 20


def test_complex_counter(app):
    counter = app.locator(".c2")
    for i in range(5):
        counter.click()
        assert int(counter.inner_text()) == 2**i
