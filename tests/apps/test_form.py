import time

from hrepr import H

from starbear import Queue, bear


@bear(template_params={"title": "formyform"})
async def __app__(page):
    q = Queue()
    fq = q.wrap(form=True)
    page.print(
        H.form(
            H.div(H.input(id="input1", name="input1", oninput=fq)),
            H.div(H.input(id="input2", name="input2", oninput=fq)),
            H.div(H.button("Clicky!")),
            onsubmit=fq,
        ),
        out := H.div(id="output"),
    )
    async for event in q:
        end = "!" if event.submit else "?"
        page[out].set(f"I say {event['input1']} and {event['input2']}{end}")


def test_title(app):
    assert app.locator("title").inner_text() == "formyform"


def test_manipulate(app):
    app.locator("#input1").fill("wow")
    time.sleep(0.05)
    assert app.locator("#output").inner_text() == "I say wow and ?"
    app.locator("#input2").fill("cool")
    time.sleep(0.05)
    assert app.locator("#output").inner_text() == "I say wow and cool?"
    app.locator("button").click()
    time.sleep(0.05)
    assert app.locator("#output").inner_text() == "I say wow and cool!"
