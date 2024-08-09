import asyncio
import atexit
import json
import logging
import os
import sys
from asyncio import Future
from pathlib import Path
from uuid import uuid4

from sse_starlette.sse import EventSourceResponse
from starlette.routing import Route
from watchdog.observers import Observer

logger = logging.getLogger("starbear")


def restart():  # pragma: no cover
    # Note: It may be difficult to get coverage for this file, because restart() may prevent coverage
    # data from being written to the file.

    def x(args):
        atexit._run_exitfuncs()
        os.execl(sys.executable, sys.executable, *args)  # pragma: no cover

    p = Path(sys.argv[0])
    if p.name == "__main__.py":
        init = p.parent / "__init__.py"
        for m, obj in sys.modules.items():
            if getattr(obj, "__file__", None) == str(init):
                x(["-m", m, *sys.argv[1:]])
        else:
            raise SystemError("Cannot figure out how to restart starbear.")
    else:
        x(sys.argv)


class Looper:
    def __init__(self, reloader):
        self.future = None
        self.reloader = reloader
        self.reloader.activity.append(self.handle)

    def handle(self):
        if self.future and not self.future.done():
            self.future.set_result(True)

    async def __aiter__(self):
        try:
            while True:
                self.future = Future()
                await self.future
                await asyncio.sleep(0.05)
                yield True
        except asyncio.CancelledError:
            self.reloader.activity.remove(self.handle)


async def autofire():
    yield True


class InertReloader:
    def __init__(self, server):
        self.server = server
        self.uuid = uuid4().hex
        self.activity = []
        self.has_fired = False

    def prep(self):
        pass

    def code_watch(self, watch):
        pass

    def browser_side_code(self):
        return None

    def inject_routes(self, routes):
        pass


class BaseReloader(InertReloader):
    def browser_side_code(self):
        return f"""
        let src = new EventSource("/!!{self.uuid}/events");
        function reboot() {{
            fetch("/!!{self.uuid}/reboot");
            setTimeout(() => window.location.reload(), 500);
        }}
        $$BEAR.tabs.addButton("⟳", reboot);
        """

    def code_watch(self, watch):
        self.obs = Observer()
        if not isinstance(watch, list):  # pragma: no cover
            watch = [watch]
        for w in watch:
            self.obs.schedule(self, w, recursive=True)
        self.obs.start()

    async def route_events(self, request):
        return EventSourceResponse(Looper(self))

    async def reboot(self, request):
        logger.info("Rebooting the server...")
        os.environ["STARBEAR_RELOAD_OVERRIDE"] = json.dumps(
            tuple(self.server.config.socket.getsockname())
        )
        self.server.config.socket.close()
        restart()

    def inject_routes(self, routes):
        routes.insert(0, Route(f"/!!{self.uuid}/events", self.route_events))
        routes.insert(0, Route(f"/!!{self.uuid}/reboot", self.reboot))

    def is_watched(self, pth):
        return not ("__pycache__" in pth or pth.endswith(".pyc"))

    def fire(self):
        self.has_fired = True
        for listener in self.activity:
            listener()

    def dispatch(self, event):
        if self.is_watched(event.src_path):
            self.fire()


class JuriggedReloader(BaseReloader):
    def __init__(self, server):
        from jurigged.codetools import CodeFileOperation
        from jurigged.register import registry

        super().__init__(server)
        self.registry = registry
        self.op = CodeFileOperation

    def prep(self):
        # Sometimes has to be done before importing the module to watch in order
        # to properly collect function data
        import codefind  # noqa: F401

    def code_watch(self, watch):
        import jurigged

        super().code_watch(watch)
        jurigged.watch(watch)
        self.activity.append(self.server.inject_routes)
        self.registry.activity.register(self.handle_jurigged)

    def browser_side_code(self):
        code = super().browser_side_code()
        return (
            code
            + """
        src.onmessage = e => {
            window.location.reload();
        };
        """
        )

    def handle_jurigged(self, event):
        if isinstance(event, self.op):
            self.fire()

    def is_watched(self, pth):
        return super().is_watched(pth) and not pth.endswith(".py")


class InertJuriggedReloader(JuriggedReloader):
    def browser_side_code(self):
        return ""

    def handle_jurigged(self, event):
        pass


class FullReloader(BaseReloader):
    def __init__(self, server):
        super().__init__(server)
        self.donezo = False

    async def route_events(self, request):
        if self.has_fired:
            return EventSourceResponse(autofire())
        else:
            return EventSourceResponse(Looper(self))

    def browser_side_code(self):
        code = super().browser_side_code()
        return (
            code
            + """
        src.onmessage = reboot;
        """
        )
