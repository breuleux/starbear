import asyncio as aio
import inspect
import json
from pathlib import Path

from hrepr import HTML, H
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount, Route, WebSocketRoute

from .page import Page
from .repr import Representer

here = Path(__file__).parent


class Queue2(aio.Queue):
    def putleft(self, entry):
        self._queue.appendleft(entry)
        self._unfinished_tasks += 1
        self._finished.clear()
        self._wakeup_next(self._getters)


class Cub:
    def __init__(self, mother, session):
        self.mother = mother
        self.fn = mother.fn
        self.path = mother.path
        self.session = session
        self.methods = {}
        self.representer = Representer()
        self.iq = aio.Queue()
        self.oq = Queue2()
        self.history = []
        self.reset = False
        self.ws = None
        self.page = Page(self.iq, self.oq, representer=self.representer)
        self.coro = aio.create_task(self.run())

    async def run(self):
        await self.fn(self.page)
        await self.page.sync()

    async def route_main(self, request):
        with open(here / "base-template.html") as tpf:
            self.reset = True
            return HTMLResponse(
                tpf.read().replace("{{{route}}}", f"{self.path}/{self.session}")
            )

    async def route_socket(self, ws):
        async def recv():
            while True:
                data = await ws.receive_json()
                self.iq.put_nowait(data)

        async def send():
            while True:
                txt, in_history = await self.oq.get()
                try:
                    await ws.send_text(txt)
                    if in_history:
                        self.history.append(txt)
                except RuntimeError:
                    # Put the unsent element back into the queue
                    self.oq.putleft((txt, in_history))
                    break

        if self.ws:
            try:
                await self.ws.close()
            except RuntimeError:
                pass

        await ws.accept()
        self.ws = ws

        if self.reset:
            for entry in self.history:
                await ws.send_text(entry)
            self.reset = False

        await aio.wait([recv(), send()], return_when=aio.FIRST_COMPLETED)

    async def route_method(self, request):
        method_id = request.path_params["method"]
        method = self.representer.registry.resolve(method_id)
        args = json.loads((await request.body()).decode("utf8"))
        result = method(*args)
        if inspect.iscoroutine(result):
            result = await result
        if isinstance(result, HTML):
            return HTMLResponse(self.representer.hrepr(result))
        else:
            return JSONResponse(result)


class MotherBear:
    def __init__(self, fn, path):
        self.fn = fn
        self.path = path
        self.cubs = {}

    def _get(self, request):
        sess = request.path_params["session"]
        if sess not in self.cubs:
            self.cubs[sess] = Cub(self, sess)
        return self.cubs[sess]

    async def route_dispatch(self, request):
        return HTMLResponse(str(H.span("nothing to see here")))

    async def route_main(self, request):
        return await self._get(request).route_main(request)

    async def route_socket(self, ws):
        return await self._get(ws).route_socket(ws)

    async def route_method(self, request):
        return await self._get(request).route_method(request)

    def routes(self):
        return Mount(
            self.path,
            routes=[
                Route("/", self.route_dispatch),
                Route("/{session:int}/", self.route_main),
                Route(
                    "/{session:int}/method/{method:int}",
                    self.route_method,
                    methods=["GET", "POST"],
                ),
                WebSocketRoute("/{session:int}/socket", self.route_socket),
            ],
        )


def bear(path):
    def deco(fn):
        return MotherBear(fn, path).routes()

    return deco
