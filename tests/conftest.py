from typing import Any, Generator

import pytest
import uvicorn
from playwright.sync_api import Page

from starbear.server.serve import ThreadableServer


def pytest_addoption(parser):
    parser.addoption(
        "--reload-pause",
        action="store",
        default="0.5",
        type=float,
        help="How long to pause in reload tests",
    )


@pytest.fixture(scope="module")
def app_config(request):
    mb = request.module.__app__
    port = 9182
    config = uvicorn.Config(app=mb, port=port)
    server = ThreadableServer(config=config)
    with server.run_in_thread():
        yield config


@pytest.fixture
def app(page, app_config) -> Generator[Page, Any, Any]:
    page.goto("http://127.0.0.1:9182/")
    page.set_default_timeout(500)
    yield page
    if not getattr(page, "disable_error_check", False):
        assert page.locator(".bear--tabular").inner_text() == ""


@pytest.fixture(scope="module")
def app_debug_config(request):
    mb = request.module.__app__
    port = 9183
    config = uvicorn.Config(app=mb, port=port)
    server = ThreadableServer(config=config)
    with server.run_in_thread(config={"starbear": {"dev": {"debug_mode": True}}}):
        yield config


@pytest.fixture
def app_debug(page, app_debug_config) -> Generator[Page, Any, Any]:
    page.goto("http://127.0.0.1:9183/")
    page.set_default_timeout(500)
    yield page
    if not getattr(page, "disable_error_check", False):
        assert page.locator(".bear--tabular").inner_text() == ""
