import asyncio as aio
import base64
import inspect
import json
import traceback
from functools import cached_property, wraps
from itertools import count
from pathlib import Path
from uuid import uuid4 as uuid

from hrepr import Tag
from starlette.exceptions import HTTPException
from starlette.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.websockets import WebSocketDisconnect

from .page import Page
from .repr import Representer
from .utils import keyword_decorator
from .wrap import with_error_display

here = Path(__file__).parent

_count = count()

construct = {}


def register_constructor(key):
    def deco(fn):
        construct[key] = fn
        return fn

    return deco


@register_constructor("HTMLElement")
def _(page, selector):
    return page[selector]


class Queue2(aio.Queue):
    def putleft(self, entry):
        self._queue.appendleft(entry)
        self._unfinished_tasks += 1
        self._finished.clear()
        self._wakeup_next(self._getters)


class Cub:
    def __init__(self, mother, process, query_params={}, session={}):
        self.mother = mother
        self.fn = mother.fn
        self.process = process
        self.query_params = query_params
        self.session = session
        self.route = self.mother.path_for("main", process=self.process).rstrip("/")
        self.methods = {}
        self.representer = Representer(self.route)
        self.iq = aio.Queue()
        self.oq = Queue2()
        self.history = []
        self.reset = False
        self.ws = None
        self.page = Page(
            self.iq,
            self.oq,
            representer=self.representer,
            query_params=query_params,
            session=session,
        )
        self.coro = aio.create_task(self.run())
        self._sd_coro = None

    def schedule_selfdestruct(self):
        async def sd():
            await aio.sleep(self.mother.process_timeout)
            del self.mother.cubs[self.process]
            self.coro.cancel()
            print(f"Destroyed process: {self.process}")

        if self.mother.process_timeout is not None:
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

    def _object_hook(self, dct):
        if "%" in dct:
            args = dict(dct)
            args.pop("%")
            return construct[dct["%"]](self.page, **args)
        else:
            return dct

    async def json(self, request):
        body = await request.body()
        return json.loads(body, object_hook=self._object_hook)

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

        await aio.wait(
            [aio.create_task(recv()), aio.create_task(send())],
            return_when=aio.FIRST_COMPLETED,
        )
        self.schedule_selfdestruct()

    async def route_method(self, request):
        method_id = request.path_params["method"]
        method = self.representer.callback_registry.resolve(method_id)
        try:
            args = await self.json(request)
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
        data = await self.json(request)
        if "error" in data:
            self.representer.future_registry.reject(
                fid=data["reqid"],
                error=data["error"],
            )
        else:
            self.representer.future_registry.resolve(
                fid=data["reqid"],
                value=data.get("value", None),
            )
        return JSONResponse({"status": "ok"})

    async def route_queue(self, request):
        data = await self.json(request)
        self.representer.queue_registry.put(
            qid=data["reqid"],
            value=data["value"],
        )
        return JSONResponse({"status": "ok"})


def get_process_from_request(request):
    process_base = request.path_params.get("process", None)
    if process_base is None:
        process_base = base64.urlsafe_b64encode(uuid().bytes).decode("utf8").strip("=")
    return process_base


def forward_cub(fn):
    @wraps(fn)
    async def fwd(self, request):
        process = get_process_from_request(request)
        cub = self._get(process, query_params=request.query_params)
        if cub is None:
            print(f"Trying to access missing process: {process}")
            return JSONResponse({"missing": process}, status_code=404)
        else:
            return await fn(self, request, cub)

    return fwd


class MotherBear:
    def __init__(self, fn, process_timeout=60, hide_processes=True):
        self.fn = fn
        self.doc = getattr(fn, "__doc__", None)
        self.router = None
        self.process_timeout = process_timeout
        self.hide_processes = hide_processes
        self.cubs = {}
        self.appid = next(_count)

    def _get(self, proc, query_params={}, session={}, ensure=False):
        if proc not in self.cubs:
            if ensure:
                print(f"Creating process: {proc}")
                self.cubs[proc] = Cub(
                    self, proc, query_params=query_params, session=session
                )
            else:
                return None
        return self.cubs[proc]

    def path_for(self, name, **kwargs):
        return self.router.url_path_for(self._mangle(name), **kwargs)

    def _ensure_router(self, request):
        router = request.scope["router"]
        if self.router is None:
            self.router = router
        else:
            assert self.router is router

    async def route_dispatch(self, request):
        self._ensure_router(request)
        process = get_process_from_request(request)
        main_path = self.path_for("main", process=process)
        if self.hide_processes:
            try:
                session = request.session
            except AssertionError:
                session = {}
            return await self._get(
                process, query_params=request.query_params, session=session, ensure=True
            ).route_main(request)
        else:
            url = main_path
            if request.query_params:
                url = f"{url}?{request.query_params}"
            return RedirectResponse(url=url)

    async def route_main(self, request):
        self._ensure_router(request)
        process = get_process_from_request(request)
        return await self._get(
            process, query_params=request.query_params, ensure=True
        ).route_main(request)

    @forward_cub
    async def route_socket(self, ws, cub):
        self._ensure_router(ws)
        return await cub.route_socket(ws)

    @forward_cub
    async def route_method(self, request, cub):
        self._ensure_router(request)
        return await cub.route_method(request)

    @forward_cub
    async def route_file(self, request, cub):
        self._ensure_router(request)
        pth = cub.representer.file_registry.get_file_from_url(
            request.path_params["path"]
        )
        if pth is None:
            raise HTTPException(
                status_code=404, detail="File not found or not available."
            )
        return FileResponse(pth, headers={"Cache-Control": "no-cache"})

    @forward_cub
    async def route_vfile(self, request, cub):
        self._ensure_router(request)
        vf = cub.representer.vfile_registry.get(request.path_params["path"])
        return Response(content=vf.content, media_type=vf.type)

    @forward_cub
    async def route_post(self, request, cub):
        self._ensure_router(request)
        return await cub.route_post(request)

    @forward_cub
    async def route_queue(self, request, cub):
        self._ensure_router(request)
        return await cub.route_queue(request)

    async def route_static(self, request):
        self._ensure_router(request)
        pth = here / request.path_params["path"]
        return FileResponse(pth, headers={"Cache-Control": "no-cache"})

    def _mangle(self, name):
        return f"app{self.appid}_{name}"

    def _make_route(self, name, path, cls=Route, **kwargs):
        return cls(
            path,
            getattr(self, f"route_{name}"),
            name=self._mangle(name),
            **kwargs,
        )

    def routes(self):
        return [
            self._make_route("dispatch", "/"),
            self._make_route("static", "/{process:str}/static/{path:path}"),
            self._make_route("main", "/{process:str}/"),
            self._make_route(
                "method",
                "/{process:str}/method/{method:int}",
                methods=["GET", "POST"],
            ),
            self._make_route("file", "/{process:str}/file/{path:path}"),
            self._make_route("vfile", "/{process:str}/vfile/{path:path}"),
            self._make_route("post", "/{process:str}/post", methods=["POST"]),
            self._make_route("queue", "/{process:str}/queue", methods=["POST"]),
            self._make_route("socket", "/{process:str}/socket", cls=WebSocketRoute),
        ]

    @cached_property
    def _mnt(self):
        return Mount("/", routes=self.routes())

    async def __call__(self, scope, receive, send):
        await self._mnt.handle(scope, receive, send)


@keyword_decorator
def bear(fn, display_errors=True, **kwargs):
    if display_errors:
        fn = with_error_display(fn)
    return MotherBear(fn, **kwargs)
