from typing import Any, Generator

import pytest
import uvicorn
from playwright.sync_api import Page

from .utils import ThreadableServer


@pytest.fixture(scope="module")
def app_config(request):
    mb = request.module.__APP__
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
