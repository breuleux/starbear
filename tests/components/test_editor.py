import pytest
from hrepr import H

from starbear import bear
from starbear.components.editor import Editor, colorized

editor_text = "def f(x):\n    return x * x"


@bear
async def __app__(page):
    def f(change):
        if change["event"] == "change":
            page.print(H.div(change["content"]))
        else:
            page.print(change)

    page.print(
        H.div(
            H.h1("Colorized text"),
            H.div["colorized"](colorized(text=editor_text, language="python")),
            H.h1("Interactive editor"),
            H.div["editor"](
                Editor(
                    value=editor_text,
                    autofocus=True,
                    language="python",
                    onChange=f,
                    bindings={"WinCtrl+KeyA": f},
                )
            ),
        )
    )
    await page.wait()


@pytest.fixture
def ed(app):
    app.set_default_timeout(2500)  # monaco takes time to load
    yield app.locator(".editor .starbear-editor-area")


def test_colorized(app):
    app.set_default_timeout(2500)  # monaco takes time to load
    assert app.locator(":nth-match(.colorized .mtk6, 1)").inner_text() == "def"
    assert app.locator(":nth-match(.colorized .mtk6, 2)").inner_text() == "return"


def test_editor_value(ed):
    assert ed.evaluate("async x => (await x.__object).editor.getValue()") == editor_text


def test_editor_autofocus(ed):
    assert ed.evaluate("x => x.contains(document.activeElement)")
