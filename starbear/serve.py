import asyncio as aio
import base64
import inspect
import json
import os
import traceback
from contextvars import ContextVar
from functools import cached_property, wraps
from itertools import count
from pathlib import Path
from uuid import uuid4 as uuid

from hrepr import H, Tag
from starlette.exceptions import HTTPException
from starlette.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from .constructors import NamespaceDict, construct
from .page import Page
from .repr import Representer
from .templating import Template, template
from .utils import Queue, format_error, keyword_decorator, logger

here = Path(__file__).parent

_count = count()

dev_injections = []

debug_mode = ContextVar("debug_mode", default=int(os.environ.get("STARBEAR_DEBUG", 0)))

_gc_message = (
    "It may have been garbage-collected."
    " References in the HTML trees you create are weak,"
    " so you have to keep strong references to ensure they"
    " are not collected. Likely culprits are lambda"
    " expressions or nested functions."
    "\n\nAlternatively, you can pass strongrefs=True to"
    " @bear or the constructor to force references to be"
    " kept alive, if you are confident this will not leak"
    " memory."
)


bearlib_template = Template(here / "bearlib-template.html")


def routeinfo(params="", path=None, root=False, cls=Route, **kw):
    def deco(method):
        assert method.__name__.startswith("route_")
        name = method.__name__.removeprefix("route_")
        method.routeinfo = {
            "cls": cls,
            "name": name,
            "path": path or ("/" if root else f"/{name}"),
            "root": root,
            "params": params,
            "keywords": kw,
        }
        return method

    return deco


def gather_routes(obj):
    for method_name in dir(obj):
        if method_name.startswith("route_"):
            method = getattr(obj, method_name)
            routeinfo = method.routeinfo
            yield method, routeinfo


def autoroutes(defns, prefix, mangle, wrap=None):
    routes = []
    for (method, routeinfo) in defns:
        wmeth = wrap(method, routeinfo) if wrap else method
        mname = mangle(routeinfo["name"])
        route = routeinfo["cls"](
            prefix + routeinfo["path"] + routeinfo["params"],
            wmeth,
            name=mname,
            **routeinfo["keywords"],
        )
        routes.append(route)

        if routeinfo["root"]:
            route = routeinfo["cls"](
                "/",
                wmeth,
                name=mangle("root"),
                **routeinfo["keywords"],
            )
            routes.append(route)

    return routes


class AbstractBear:
    def __init__(self):
        self.appid = next(_count)
        self.route = None
        self.router = None
        self.representer = None
        self._json_decoder = json.JSONDecoder(object_pairs_hook=self.object_pairs_hook)

    ###########
    # Methods #
    ###########

    def mangle(self, name):
        return f"app{self.appid}_{name}"

    def path_for(self, name, **kwargs):
        return self.router.url_path_for(self.mangle(name), **kwargs)

    def object_pairs_hook(self, pairs):
        return NamespaceDict(pairs)

    async def json(self, request):
        body = await request.body()
        if isinstance(body, bytes):
            body = body.decode(encoding="utf8")
        return self._json_decoder.decode(body)

    def ensure_router(self, request):
        router = request.scope["router"]
        if self.router is None:
            self.router = router
            self.app = request.scope.get("app", None)
        else:
            assert self.router is router

    ##############################
    # For standalone application #
    ##############################

    def routes(self):
        return []

    @cached_property
    def _mnt(self):
        return Mount("/", routes=self.routes())

    async def __call__(self, scope, receive, send):
        await self._mnt.handle(scope, receive, send)


class BasicBear(AbstractBear):
    def __init__(self, template, template_params):
        super().__init__()
        self.route = None
        self._template = template
        self._template_params = {
            "title": "Starbear",
            "body": "",
            "connect_line": "",
            "bearlib": bearlib_template,
            **template_params,
        }

    ###################
    # Basic functions #
    ###################

    def template_asset(self, name, where):
        return (
            self.route
            + "/file/"
            + self.representer.file_registry.register(where / name)
        )

    def template(self, template_path=None, **params):
        template_path = template_path or self._template
        location = template_path.parent
        agg_params = {
            **self._template_params,
            "route": self.route,
            "dev": dev_injections,
            **params,
        }
        return template(
            template_path,
            **agg_params,
            _asset=lambda name: self.template_asset(name, location),
            _std=lambda name: self.template_asset(name, here),
        )

    def error_response(self, code, message, debug=None, exception=None):
        msg = format_error(
            message=message,
            debug=debug,
            exception=exception,
            show_debug=debug_mode.get(),
        )
        return JSONResponse({"message": msg}, status_code=code)

    ################
    # Basic routes #
    ################

    @routeinfo("/{method:int}", methods=["GET", "POST"])
    async def route_method(self, request):
        method_id = request.path_params["method"]
        try:
            method = self.representer.object_registry.resolve(method_id)
        except KeyError:
            return self.error_response(
                code=404,
                message="Application error: method not found.",
                debug=_gc_message,
            )
        try:
            args = await self.json(request)
        except json.JSONDecodeError:
            args = [await request.body()]
        try:
            result = method(*args, **request.query_params)
        except Exception as exc:
            return self.error_response(
                code=500,
                message="Application error.",
                exception=exc,
            )
        if inspect.iscoroutine(result):
            result = await result
        if isinstance(result, Tag):
            return HTMLResponse(self.representer(result))
        else:
            return JSONResponse(result)

    @routeinfo(methods=["POST"])
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

    @routeinfo(methods=["POST"])
    async def route_queue(self, request):
        data = await self.json(request)
        self.representer.queue_registry.put(
            qid=data["reqid"],
            value=data["value"],
        )
        return JSONResponse({"status": "ok"})

    @routeinfo("/{path:path}")
    async def route_file(self, request):
        pth = self.representer.file_registry.get_file_from_url(
            request.path_params["path"]
        )
        if pth is None:
            raise HTTPException(
                status_code=404, detail="File not found or not available."
            )
        return FileResponse(pth, headers={"Cache-Control": "no-cache"})

    @routeinfo("/{path:path}")
    async def route_vfile(self, request):
        vf = self.representer.vfile_registry.get(request.path_params["path"])
        return Response(content=vf.content, media_type=vf.type)


class LoneBear(BasicBear):
    def __init__(self, fn, template=None, template_params={}, strongrefs=False):
        super().__init__(
            template=template or (here / "page-template.html"),
            template_params=template_params,
        )
        self.strongrefs = strongrefs
        self.fn = fn
        self.__doc__ = getattr(fn, "__doc__", None)

    ####################
    # Route generation #
    ####################

    def ensure_representer(self, request):
        self.ensure_router(request)
        if self.representer is None:
            self.route = self.path_for("main").rstrip("/")
            self.representer = Representer(self.route, strongrefs=self.strongrefs)

    def wrap_route(self, method, routeinfo):
        @wraps(method)
        async def wrapped(request):
            self.ensure_representer(request)
            return await method(request)

        return wrapped

    def routes(self):
        return autoroutes(
            defns=gather_routes(self),
            prefix="/!",
            mangle=self.mangle,
            wrap=self.wrap_route,
        )

    @routeinfo(root=True)
    async def route_main(self, request):
        response = await self.fn(request)
        if isinstance(response, Tag):
            if response.name != "html":
                response = self.template(body=response)
            html = self.representer.generate_string(response)
            return HTMLResponse(f"<!DOCTYPE html>\n{html}")
        elif isinstance(response, dict):
            return JSONResponse(response)
        else:
            return PlainTextResponse(str(response))


class Cub(BasicBear):
    def __init__(
        self,
        mother,
        process,
        query_params={},
        session={},
        template=None,
        template_params={},
        strongrefs=False,
    ):
        super().__init__(
            template=template or (here / "page-template.html"),
            template_params={"connect_line": "bear.connect()", **template_params},
        )
        self.mother = mother
        self.fn = mother.fn
        self.process = process
        self.query_params = query_params
        self.session = session
        self.route = self.mother.path_for("main", process=self.process).rstrip("/")
        self.representer = Representer(self.route, strongrefs=strongrefs)
        self.iq = Queue()
        self.oq = Queue()
        self.history = []
        self.reset = False
        self.ws = None
        self.page = Page(instance=self, debug=debug_mode.get())
        self.coro = aio.create_task(self.run())
        self._sd_coro = None
        self.log("info", "Created process")

    def log(self, level, msg, **extra):
        try:
            user = self.session.get("user", {}).get("email", None)
        except:
            logger.error("Could not get user")
        getattr(logger, level)(msg, extra={"proc": self.process, "user": user, **extra})

    def schedule_selfdestruct(self):
        async def sd():
            await aio.sleep(self.mother.process_timeout)
            del self.mother.cubs[self.process]
            self.coro.cancel()
            self.log("info", "Destroyed process")

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
            self.log("error", str(exc), traceback=traceback)
            self.page.error(
                message=H.b("An error occurred. You may need to refresh the page."),
                exception=exc,
            )
        finally:
            self.log("info", "Finished process")

    def object_pairs_hook(self, pairs):
        dct = NamespaceDict(pairs)
        if "%" in dct:
            return construct(self.page, dct)
        else:
            return dct

    async def json(self, request):
        try:
            return await super().json(request)
        except KeyError as exc:
            self.page.error(
                message=f"Error constructing: reference {exc.args[0]} not found",
                debug=_gc_message,
            )
            raise
        except Exception as exc:
            self.page.error(
                message="Error constructing object",
                exception=exc,
            )
            raise

    ##############
    # Cub routes #
    ##############

    @routeinfo(root=True)
    async def route_main(self, request):
        self.unschedule_selfdestruct()
        node = self.template()
        self.reset = True
        html = self.representer.generate_string(node)
        return HTMLResponse(
            f"<!DOCTYPE html>\n{html}",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    @routeinfo(cls=WebSocketRoute)
    async def route_socket(self, ws):
        self.unschedule_selfdestruct()

        async def recv():
            while True:
                try:
                    data = await ws.receive_json()
                    self.iq.put_nowait(data)
                except WebSocketDisconnect:
                    break

        async def send():
            while True:
                obj, in_history = await self.oq.get()
                try:
                    await ws.send_json(obj)
                    if in_history:
                        self.history.append(obj)
                except RuntimeError:
                    # Put the unsent element back into the queue
                    self.oq.putleft((obj, in_history))
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

        await aio.wait(
            [aio.create_task(recv()), aio.create_task(send())],
            return_when=aio.FIRST_COMPLETED,
        )
        self.schedule_selfdestruct()


def get_process_from_request(request):
    process_base = request.path_params.get("process", None)
    if process_base is None:
        process_base = base64.urlsafe_b64encode(uuid().bytes).decode("utf8").strip("=")
    return process_base


class MotherBear(AbstractBear):
    def __init__(self, fn, process_timeout=60, hide_processes=True, **cub_params):
        super().__init__()
        self.fn = fn
        self.__doc__ = getattr(fn, "__doc__", None)
        self.router = None
        self.process_timeout = process_timeout
        self.hide_processes = hide_processes
        self.cub_params = cub_params
        self.cubs = {}

    def _get(self, proc, query_params={}, session={}, ensure=False):
        if proc not in self.cubs:
            if ensure:
                self.cubs[proc] = Cub(
                    self,
                    proc,
                    query_params=query_params,
                    session=session,
                    **self.cub_params,
                )
            else:
                return None
        return self.cubs[proc]

    #################
    # Mother routes #
    #################

    @routeinfo(root=True)
    async def route_dispatch(self, request):
        self.ensure_router(request)
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

    ####################
    # Construct routes #
    ####################

    def wrap_route(self, method, routeinfo):
        ensure = routeinfo["root"]

        @wraps(method)
        async def forward(request):
            self.ensure_router(request)
            process = get_process_from_request(request)
            cub = self._get(process, query_params=request.query_params, ensure=ensure)
            if cub is None:
                logger.warning(f"Trying to access missing process: {process}")
                if isinstance(request, WebSocket):
                    await request.accept()
                    await request.close(code=3002, reason="Missing application")
                else:
                    return JSONResponse(
                        {
                            "missing": process,
                            "message": "Session killed. Please refresh.",
                        },
                        status_code=404,
                    )
            else:
                return await method(cub, request)

        return forward

    def routes(self):
        return [
            *autoroutes(
                defns=gather_routes(self),
                prefix="",
                mangle=self.mangle,
            ),
            Mount(
                "/!{process:str}/",
                routes=autoroutes(
                    defns=gather_routes(Cub),
                    prefix="",
                    mangle=self.mangle,
                    wrap=self.wrap_route,
                ),
            ),
        ]


class ConfigurableBear(MotherBear):
    def __init__(self, config, **params):
        super().__init__(self.app, **params)
        self.config = config


class ConfigurableSimpleBear(LoneBear):
    def __init__(self, config, **params):
        super().__init__(self.app, **params)
        self.config = config


@keyword_decorator
def bear(fn, **kwargs):
    return MotherBear(fn, **kwargs)


def simplebear(fn, **kwargs):
    return LoneBear(fn, **kwargs)
