import threading
import webbrowser
from functools import cached_property
from pathlib import Path
from textwrap import dedent

import gifnoc
import uvicorn
from hrepr import H
from starlette.applications import Starlette
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware

from ..core.utils import logger
from .config import StarbearServerConfig
from .find import compile_routes


class ThreadedServer(uvicorn.Server):
    def install_signal_handlers(self):
        pass

    def run(self):
        thread = threading.Thread(target=super().run)
        thread.start()


class StarbearServer:
    def __init__(self, config):
        self.config = config

    @cached_property
    def reloader(self):
        return self.config.get_reloader(self)

    def inject_routes(self):
        collected = self.config.get_routes()
        routes = compile_routes("/", collected)
        self.reloader.inject_routes(routes)

        for route in routes:
            route._grizzlaxy_managed = True

        remainder = [
            r for r in self.app.router.routes if not getattr(r, "_grizzlaxy_managed", False)
        ]
        self.app.router.routes = routes + remainder
        self.app.map = collected

    def _setup(self):
        if self.config.watch is True:
            watch = self.config.get_locations()
        else:
            watch = self.config.watch

        self.reloader.prep()
        self.reloader.code_watch(watch)

        inject_code = self.reloader.browser_side_code()
        if inject_code:
            self.inject = [
                H.script(
                    dedent(
                        f"""window.addEventListener("load", () => {{
                        {inject_code}
                        }});
                        """
                    )
                )
            ]
        else:
            self.inject = []

        app = Starlette(routes=[])

        @app.on_event("startup")
        async def _():
            protocol = "https" if self.config.ssl.enabled else "http"
            host, port = self.config.socket.getsockname()
            url = f"{protocol}://{host}:{port}"
            logger.info(f"Serving at: \x1b[1m{url}\x1b[0m")
            if self.config.open_browser:
                webbrowser.open(url)

        def _ensure(filename, enabled):
            if not enabled or not filename:
                return None
            if not Path(filename).exists():
                raise FileNotFoundError(filename)
            return filename

        ssl_enabled = self.config.ssl.enabled
        self.ssl_keyfile = _ensure(self.config.ssl.keyfile, ssl_enabled)
        self.ssl_certfile = _ensure(self.config.ssl.certfile, ssl_enabled)

        if ssl_enabled and self.ssl_certfile and self.ssl_keyfile:
            # This doesn't seem to do anything?
            app.add_middleware(HTTPSRedirectMiddleware)

        self.app = app
        self.inject_routes()

    def run(self):
        self._setup()
        with gifnoc.overlay(
            {"starbear": {"dev": {"debug_mode": self.config.dev, "inject": self.inject}}}
        ):
            uconfig = uvicorn.Config(
                app=self.app,
                fd=self.config.socket.fileno(),
                log_level="info",
                ssl_keyfile=self.ssl_keyfile,
                ssl_certfile=self.ssl_certfile,
            )
            server_class = ThreadedServer if self.config.use_thread else uvicorn.Server
            server_class(uconfig).run()


def run(**kwargs):
    server = StarbearServer(StarbearServerConfig(**kwargs))
    server.run()
