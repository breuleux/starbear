from starbear import H, Queue, bear


@bear
async def __app__(page):
    def err(_):
        raise Exception("oh no!")

    q = Queue()
    page.print(
        H.button("Error 1", id="e1", onclick=q.tag("e1")),
        H.button("Error 2", id="e2", onclick=err),
    )
    async for event in q:
        if event.tag == "e1":
            1 / 0


def test_error(app):
    app.locator("#e1").click()
    txt = app.locator(".bear--tabular-area-container.bear--active").inner_text()
    assert "An error occurred" in txt
    assert "ZeroDivisionError" not in txt
    app.disable_error_check = True


def test_error_debug(app_debug):
    app_debug.locator("#e1").click()
    txt = app_debug.locator(".bear--tabular-area-container.bear--active").inner_text()
    assert "ZeroDivisionError" in txt
    app_debug.disable_error_check = True


def test_error_in_method(app):
    app.locator("#e2").click()
    txt = app.locator(".bear--tabular-area-container.bear--active").inner_text()
    assert "Application error" in txt
    assert "oh no!" not in txt
    app.disable_error_check = True


def test_error_in_method_debug(app_debug):
    app_debug.locator("#e2").click()
    txt = app_debug.locator(".bear--tabular-area-container.bear--active").inner_text()
    assert "oh no!" in txt
    app_debug.disable_error_check = True
