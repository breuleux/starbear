import asyncio as aio
import inspect
from pathlib import Path

from hrepr import H, J, Tag
from hrepr.textgen import Breakable, Sequence

from ..common import logger
from .reg import Reference
from .repr import StarbearHTMLGenerator
from .utils import Event, FeedbackEvent, Queue, Responses, format_error


def selector_for(x):
    if isinstance(x, Tag):
        if not x.id:
            raise Exception("Cannot locate element because it has no id.")
        return f"#{x.id}"
    elif isinstance(x, J):
        return f"#{x._get_id()}"
    elif isinstance(x, str):
        return x
    elif isinstance(x, Reference):
        return f'[--ref="obj#{x.id}"]'
    elif (selector := getattr(x, "selector", None)) and isinstance(selector, str):
        return selector
    else:
        raise TypeError(
            "A valid selector must be a str, Tag, Reference or an object"
            " with a string attribute named `selector`."
        )


class Component:
    @property
    def selector(self):
        return selector_for(self.node)

    def __hrepr__(self, H, hrepr):
        return self.node

    def __h__(self):
        return self.node


class AwaitableJ(J):
    def __init__(self, page=None, **kwargs):
        super().__init__(**kwargs)
        if page is not None:
            self._data.page = page

    def __await__(self):
        future = aio.Future()
        self.__do__(future)
        return iter(future)

    def __do__(self, future=None):
        self._data.page.print(J()["$$BEAR"].cb(self.thunk(), future))


async def suppress_cancel(coro):
    try:
        await coro
    except aio.CancelledError:
        logger.info(f"Cancelled: {coro}")


class Page:
    def __init__(
        self,
        instance,
        selector=None,
        track_history=True,
        hgen=None,
        debug=False,
        loop=None,
        tasks=None,
    ):
        self.instance = instance
        self.iq = instance.iq
        self.oq = instance.oq
        self.query_params = instance.query_params
        self.session = instance.session
        self.representer = instance.representer
        self.hgen = hgen or StarbearHTMLGenerator(instance.representer)
        self.selector = selector
        self.track_history = track_history
        self.tasks = set() if tasks is None else tasks
        self.debug = debug
        self.loop = loop or aio.get_running_loop()
        self.js = AwaitableJ(page=self, object=self.selector)
        self.window = AwaitableJ(page=self)
        self.bearlib = AwaitableJ(page=self)["$$BEAR"]

    def __getitem__(self, selector):
        if not isinstance(selector, tuple):
            selector = (selector,)
        selector = " ".join(map(selector_for, selector))

        if self.selector is not None:
            selector = f"{self.selector} {selector}"

        return self.page_select(selector)

    def page_select(self, selector):
        return type(self)(
            instance=self.instance,
            selector=selector,
            track_history=self.track_history,
            hgen=self.hgen,
            debug=self.debug,
            loop=self.loop,
            tasks=self.tasks,
        )

    def with_history(self, track_history=True):
        if self.track_history == track_history:
            return self
        else:
            return type(self)(
                instance=self.instance,
                selector=self.selector,
                track_history=track_history,
                hgen=self.hgen,
                debug=self.debug,
                loop=self.loop,
            )

    def without_history(self):
        return self.with_history(False)

    def _done_cb(self, future):
        self.tasks.discard(future)
        if exc := future.exception():
            self.error(
                message="An error occurred trying to represent data.",
                exception=exc,
            )

    def _push(self, coro, label=None):
        if aio._get_running_loop() is None:
            aio._set_running_loop(self.loop)
        task = aio.create_task(suppress_cancel(coro), name=label)
        self.tasks.add(task)
        task.add_done_callback(self._done_cb)

    async def sync(self):
        while self.tasks:
            task = self.tasks.pop()
            await task

    def _to_element(self, x):
        if isinstance(x, str):
            return H.span(x)
        else:
            return self.hgen.hrepr(x)

    def _generate_put_commands(self, element, method, send_resources=False):
        sel = self.selector or "body"
        if not element:
            yield {
                "command": "put",
                "selector": sel,
                "method": method,
                "content": "",
            }
            return

        blk = self.hgen.blockgen(element)

        if send_resources and blk.processed_resources:
            yield {
                "command": "resource",
                "content": str(H.inline(blk.processed_resources)),
            }
        yield {
            "command": "put",
            "selector": sel,
            "method": method,
            "content": str(blk.result),
        }
        for xtra in blk.processed_extra:
            s = str(xtra.start)
            e = str(xtra.end)
            if (
                isinstance(xtra, Breakable)
                and s.startswith("<script")
                and "src=" not in s
                and e == "</script>"
            ):
                yield {
                    "command": "eval",
                    "code": str(Sequence(*xtra.body)),
                    "module": 'type="module"' in s,
                }
            else:
                yield {
                    "command": "put",
                    "selector": sel,
                    "method": "beforeend",
                    "content": str(H.div(xtra, style="display:none")),
                }
        for elem_id, (lg, listeners) in blk.live_generators.items():
            coro = lg(self[f"#{elem_id}"])
            if inspect.isasyncgen(coro):
                self._push(self._wrap_async_gen(coro, listeners), label=elem_id)
            else:
                self._push(coro, label=elem_id)

    async def _wrap_async_gen(self, agen, listeners):
        agen = aiter(agen)
        send_back = None

        while True:
            try:
                result = await agen.asend(send_back)
                processed = False
                keys = [True]
                if isinstance(result, Event):
                    keys.append(result.type)
                for key in keys:
                    method = listeners.get(key, None)
                    if isinstance(method, Queue):
                        method.put_nowait(result)
                        processed = True
                    elif method is None:
                        pass
                    else:
                        method(result)
                        processed = True
                if isinstance(result, FeedbackEvent):
                    if not processed:
                        result.resolve(Responses.NO_LISTENERS)
                    send_back = result.response
                else:
                    send_back = None

            except StopAsyncIteration:
                break

            except Exception as exc:
                self.error(f"Error in {agen}", exception=exc)
                raise

    async def put(self, element, method, history=None, send_resources=True):
        if history is None:
            history = self.track_history
        await self.oq.put(
            (
                list(self._generate_put_commands(element, method, send_resources)),
                history,
            )
        )

    def put_nowait(self, element, method, history=None, send_resources=True):
        self._push(self.put(element, method, history=history, send_resources=send_resources))

    def queue_command(self, command, /, history=None, **arguments):
        if history is None:
            history = self.track_history
        arguments["command"] = command
        self._push(self.oq.put((arguments, history)))

    def set_title(self, title):
        self.queue_command("put", selector="head title", content=title, method="innerHTML")

    def add_resources(self, *resources, type=None):
        def _build(resource, name):
            if name.endswith(".css") or type == "text/css":
                return H.link(rel="stylesheet", href=resource)
            elif name.endswith(".js") or type == "text/javascript":
                return H.script(src=resource)
            elif name.endswith(".ico"):
                return H.link(rel="icon", href=resource)
            else:
                raise ValueError(f"Cannot determine resource type for '{resource}'")

        for resource in resources:
            if isinstance(resource, str):
                if resource.startswith("http://") or resource.startswith("https://"):
                    node = _build(resource, resource)
                else:
                    node = _build(Path(resource), resource)
            elif isinstance(resource, Path):
                node = _build(resource, resource.suffix)
            elif isinstance(resource, Tag):
                node = resource
            else:
                raise TypeError("resource argument should be a Path or a Tag object")

            text = self.hgen.to_string(node)
            self.queue_command("resource", content=text)

    def print(self, *elements, method="beforeend"):
        for element in elements:
            element = self._to_element(element)
            self.put_nowait(element, method)

    def error(self, message, debug=None, exception=None):
        if not isinstance(message, str):
            message = str(self.hgen.hrepr(message))
        self.queue_command("error", content=format_error(message, debug, exception, self.debug))

    def log(self, message):
        if not isinstance(message, str):
            message = self.representer.hrepr(message)
        self.queue_command("log", content=str(message))

    def print_html(self, html, selector=None, method="beforeend", history=None):
        self.queue_command(
            "put",
            selector=selector or self.selector or "body",
            method=method,
            content=html,
            history=history,
        )

    def template(self, template_file, integration_method="innerHTML", **params):
        filled = self.instance.template(template_file, **params)
        self.put_nowait(filled, integration_method)

    def set(self, element):
        element = self._to_element(element)
        self.put_nowait(element, "innerHTML")

    def replace(self, element):
        element = self._to_element(element)
        self.put_nowait(element, "outerHTML")

    def clear(self):
        self.put_nowait("", "innerHTML")

    def delete(self):
        self.put_nowait("", "outerHTML")

    async def eval(self, code):
        return await self.js.eval(code)

    def exec(self, code, future=None):
        self.js.exec(code).__do__(future)

    def toggle(self, toggle, value=None):
        return self.bearlib.toggle(self, toggle, value)

    def __hrepr__(self, H, hrepr):
        return hrepr.make.instance(
            title="Page",
            fields=[["selector", self.selector]],
            delimiter=":",
        )

    def __js_embed__(self, representer):
        if self.selector is None:
            raise Exception("Cannot send page reference to JS because it has no selector.")
        return f"document.querySelector('{self.selector}')"

    async def recv(self):
        return await self.iq.get()

    async def wait(self, timeout=None):
        await aio.sleep(1_000_000_000 if timeout is None else timeout)
