import asyncio as aio
import base64
import inspect
import json
import traceback
from functools import wraps
from pathlib import Path
from uuid import uuid4 as uuid

from hrepr import Tag
from starlette.exceptions import HTTPException
from starlette.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
)
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.websockets import WebSocketDisconnect

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
        self.route = f"{self.path}/{self.session}"
        self.methods = {}
        self.representer = Representer(self.route)
        self.iq = aio.Queue()
        self.oq = Queue2()
        self.history = []
        self.reset = False
        self.ws = None
        self.page = Page(self.iq, self.oq, representer=self.representer)
        self.coro = aio.create_task(self.run())
        self._sd_coro = None

    def schedule_selfdestruct(self):
        async def sd():
            await aio.sleep(self.mother.session_timeout)
            del self.mother.cubs[self.session]
            self.coro.cancel()
            print(f"Destroyed session: {self.session}")

        if self.mother.session_timeout is not None:
            self._sd_coro = aio.create_task(sd())

    def unschedule_selfdestruct(self):
        if self._sd_coro:
            self._sd_coro.cancel()
            self._sd_coro = None

    async def run(self):
        try:
            await self.fn(self.page)
            await self.page.sync()
        except Exception as exc:
            traceback.print_exc()

    async def route_main(self, request):
        self.unschedule_selfdestruct()
        with open(here / "base-template.html") as tpf:
            self.reset = True
            return HTMLResponse(tpf.read().replace("{{{route}}}", self.route))

    async def route_socket(self, ws):
        self.unschedule_selfdestruct()

        async def recv():
            while True:
                try:
                    data = await ws.receive_json()
                    self.iq.put_nowait(data)
                except WebSocketDisconnect:
                    break
            print("recv stopped")

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
            print("send stopped")

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
        self.schedule_selfdestruct()

    async def route_method(self, request):
        method_id = request.path_params["method"]
        method = self.representer.callback_registry.resolve(method_id)
        try:
            args = await request.json()
        except json.JSONDecodeError:
            args = [await request.body()]
        result = method(*args, **request.query_params)
        if inspect.iscoroutine(result):
            result = await result
        if isinstance(result, Tag):
            return HTMLResponse(self.representer(result))
        else:
            return JSONResponse(result)

    async def route_post(self, request):
        data = await request.json()
        if "value" in data:
            self.representer.future_registry.resolve(
                fid=data["reqid"],
                value=data["value"],
            )
        else:
            self.representer.future_registry.reject(
                fid=data["reqid"],
                error=data["error"],
            )
        return JSONResponse({"status": "ok"})

    async def route_queue(self, request):
        data = await request.json()
        self.representer.queue_registry.put(
            qid=data["reqid"],
            value=data["value"],
        )
        return JSONResponse({"status": "ok"})


def forward_cub(fn):
    @wraps(fn)
    async def fwd(self, request):
        session = request.path_params["session"]
        cub = self._get(session)
        if cub is None:
            print(f"Trying to access missing session: {session}")
            return JSONResponse({"missing": session}, status_code=404)
        else:
            return await fn(self, request, cub)

    return fwd


class MotherBear:
    def __init__(self, fn, path, session_timeout=60, hide_sessions=True):
        self.fn = fn
        self.path = path
        self.session_timeout = session_timeout
        self.hide_sessions = hide_sessions
        self.cubs = {}

    def _get(self, sess, ensure=False):
        if sess not in self.cubs:
            if ensure:
                print(f"Creating session: {sess}")
                self.cubs[sess] = Cub(self, sess)
            else:
                return None
        return self.cubs[sess]

    async def route_dispatch(self, request):
        session = base64.urlsafe_b64encode(uuid().bytes).decode("utf8").strip("=")
        if self.hide_sessions:
            return await self._get(session, ensure=True).route_main(request)
        else:
            return RedirectResponse(url=f"{self.path}/{session}")

    async def route_main(self, request):
        session = request.path_params["session"]
        return await self._get(session, ensure=True).route_main(request)

    @forward_cub
    async def route_socket(self, ws, cub):
        return await cub.route_socket(ws)

    @forward_cub
    async def route_method(self, request, cub):
        return await cub.route_method(request)

    @forward_cub
    async def route_file(self, request, cub):
        pth = cub.representer.file_registry.get_file_from_url(
            request.path_params["path"]
        )
        if pth is None:
            raise HTTPException(
                status_code=404, detail="File not found or not available."
            )
        return FileResponse(pth, headers={"Cache-Control": "no-cache"})

    @forward_cub
    async def route_post(self, request, cub):
        return await cub.route_post(request)

    @forward_cub
    async def route_queue(self, request, cub):
        return await cub.route_queue(request)

    async def route_static(self, request):
        pth = here / request.path_params["path"]
        return FileResponse(pth, headers={"Cache-Control": "no-cache"})

    def routes(self):
        return Mount(
            self.path,
            routes=[
                Route("/", self.route_dispatch),
                Route("/{session:str}/static/{path:path}", self.route_static),
                Route("/{session:str}/", self.route_main),
                Route(
                    "/{session:str}/method/{method:int}",
                    self.route_method,
                    methods=["GET", "POST"],
                ),
                Route("/{session:str}/file/{path:path}", self.route_file),
                Route("/{session:str}/post", self.route_post, methods=["POST"]),
                Route("/{session:str}/queue", self.route_queue, methods=["POST"]),
                WebSocketRoute("/{session:str}/socket", self.route_socket),
            ],
        )


def bear(path):
    def deco(fn):
        return MotherBear(fn, path).routes()

    return deco
