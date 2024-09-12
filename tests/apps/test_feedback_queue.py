import time

from hrepr import H

from starbear import FeedbackQueue, Resource as R, bear


@bear
async def __app__(page):
    q = FeedbackQueue()

    def f(x):
        page[out].set(H.div(f"Current square: {x}"))

    page.print(
        H.script(f"run = async e => {R(f)}((await {R(q)}(e)) ** 2)"),
        H.div(H.button("Clicky!", onclick="run(event)")),
        out := H.div(id="result"),
    )
    current = 0
    async for event, resolve in q:
        await resolve(current)
        current += 1


def test_feedback(app):
    result = app.locator("#result")
    app.locator("button").click()
    time.sleep(0.1)
    assert result.inner_text() == "Current square: 0"
    app.locator("button").click()
    time.sleep(0.1)
    assert result.inner_text() == "Current square: 1"
    app.locator("button").click()
    time.sleep(0.1)
    assert result.inner_text() == "Current square: 4"
