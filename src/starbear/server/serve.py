import threading
import webbrowser
from functools import cached_property
from graphlib import TopologicalSorter
from pathlib import Path
from textwrap import dedent

import gifnoc
import uvicorn
from hrepr import H
from starlette.applications import Starlette
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware

from ..common import logger
from ..config import config as base_config
from .config import StarbearServerConfig
from .find import compile_routes
from .plugins.session import Session


class ThreadedServer(uvicorn.Server):
    def install_signal_handlers(self):
        pass

    def run(self):
        thread = threading.Thread(target=super().run)
        thread.start()


class StarbearServer:
    def __init__(self, config: StarbearServerConfig):
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

        plugins = {name: p for name, p in self.config.plugins.items() if p.enabled}

        exports = {}
        for i, p in plugins.items():
            exports.update({x: i for x in p.cap_export()})

        if "session" not in exports:
            assert "session" not in plugins
            exports["session"] = "session"
            plugins["session"] = Session(enabled=True, required=False)

        def locate_dependencies(p):
            for x in p.cap_require():
                if x not in exports:
                    raise Exception(
                        f"Plugin '{i}' of type '{type(p).__name__}' requires the '{x}' feature, but none of the included plugins exports it."
                    )
                plugins[exports[x]].required = True
                yield exports[x]

        graph = {i: list(locate_dependencies(p)) for i, p in plugins.items()}
        order = TopologicalSorter(graph).static_order()

        for plugin_index in reversed(list(order)):
            p = plugins[plugin_index]
            if p.required:
                assert not hasattr(self, plugin_index)
                setattr(plugin_index, p)
                logger.info(f"Set up plugin: {plugin_index}")
                p.setup(self)

        self.app.starbear_instance = self

        self.inject_routes()

    def run(self):
        self._setup()
        with gifnoc.overlay(
            {
                "starbear": {
                    "dev": {
                        "debug_mode": base_config.dev.debug_mode or self.config.dev,
                        "inject": self.inject,
                    }
                }
            }
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
