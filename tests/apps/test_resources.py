from hrepr import H, J

from starbear import bear

from .utils import asset_getter

asset = asset_getter(__file__)


@bear(
    template=asset("template.html"),
    template_params={"title": "Test", "name": "Balthazar"},
    strongrefs=True,
)
async def __app__(page):
    page.add_resources(asset("stylo.css"))
    page["#box"].print(H.p["blue"]("Adding a line to the box.", id="added"))

    page.print(H.h3("Clicking the button should show 10, 20, 30, ..."))
    counter = J(module=asset("counter.js"))(increment=10, cls="c1")
    page.print(counter)
    page[counter].js.activate().__do__()

    page.print(H.h3("Clicking the button should show 0, 2, 4, ... in the blue box above it"))
    page.print(fc_target := H.div["blue"]("xxxxx", id="fancy"))
    fancy_counter = J(module=asset("fancy-counter.js"))(
        increment=2, target=page[fc_target], cls="c2"
    )
    page.print(fancy_counter)


def test_page_template(app):
    assert app.locator("title").inner_text() == "Test!"
    assert "Balthazar" in app.locator("#box").inner_text()


def test_style(app):
    added = app.locator("#added")
    assert added.evaluate("x => getComputedStyle(x).color") == "rgb(0, 0, 255)"
    assert added.evaluate("x => getComputedStyle(x).border") == "3px solid rgb(0, 0, 255)"


def test_counter(app):
    counter = app.locator(".c1")
    value0 = int(counter.inner_text())
    counter.click()
    value1 = int(counter.inner_text())
    counter.click()
    value2 = int(counter.inner_text())
    assert value2 == value1 + 10 == value0 + 20


def test_counter_initial_activation(app):
    assert app.locator(".c1").inner_text() == "10"


def test_fancy(app):
    counter = app.locator(".c2")
    target = app.locator("#fancy")
    counter.click()
    value0 = int(target.inner_text())
    counter.click()
    value1 = int(target.inner_text())
    counter.click()
    value2 = int(target.inner_text())
    assert value2 == value1 + 2 == value0 + 4
