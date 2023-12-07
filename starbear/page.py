import asyncio as aio
from pathlib import Path

from hrepr import H, Tag
from hrepr.hgen import ResourceDeduplicator
from hrepr.resource import Resource


class Page:
    def __init__(
        self,
        iq,
        oq,
        representer,
        selector=None,
        query_params={},
        session={},
        track_history=True,
        sent_resources=None,
        app=None,
        loop=None,
    ):
        self.iq = iq
        self.oq = oq
        self.selector = selector
        self.query_params = query_params
        self.session = session
        self.representer = representer
        self.track_history = track_history
        self.sent_resources = sent_resources or ResourceDeduplicator()
        self.tasks = set()
        self.app = app
        self.loop = loop or aio.get_running_loop()
        self.js = JavaScriptOperation(self, [])
        self.window = JavaScriptOperation(self, [], root="window")
        self.bearlib = JavaScriptOperation(self, [], root="$$BEAR")

    def __getitem__(self, selector):
        def _map_selector(x):
            if isinstance(x, Tag):
                tid = x.attributes.get("id", None)
                if not tid:
                    raise Exception("Cannot locate element because it has no id.")
                return f"#{tid}"
            elif isinstance(x, str):
                return x
            else:
                raise TypeError("Only str or Tag can be used as a selector")

        if not isinstance(selector, tuple):
            selector = (selector,)
        selector = " ".join(map(_map_selector, selector))

        if self.selector is not None:
            selector = f"{self.selector} {selector}"

        return self.page_select(selector)

    def page_select(self, selector):
        return type(self)(
            iq=self.iq,
            oq=self.oq,
            selector=selector,
            representer=self.representer,
            track_history=self.track_history,
            sent_resources=self.sent_resources,
        )

    def with_history(self, track_history=True):
        if self.track_history == track_history:
            return self
        else:
            return type(self)(
                iq=self.iq,
                oq=self.oq,
                selector=self.selector,
                representer=self.representer,
                track_history=track_history,
                sent_resources=self.sent_resources,
            )

    def without_history(self):
        return self.with_history(False)

    def _push(self, coro):
        if aio._get_running_loop() is None:
            aio._set_running_loop(self.loop)
        task = aio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def sync(self):
        for task in list(self.tasks):
            await task

    def _to_element(self, x):
        if isinstance(x, str):
            return H.span(x)
        else:
            return self.representer.hrepr(x)

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

        parts, extra, resources = self.representer.generate(
            element, filter_resources=self.sent_resources if send_resources else None
        )
        if not resources.empty():
            yield {
                "command": "resource",
                "content": str(resources),
            }
        yield {
            "command": "put",
            "selector": sel,
            "method": method,
            "content": str(parts),
        }
        if not extra.empty():
            yield {
                "command": "put",
                "selector": sel,
                "method": "beforeend",
                "content": str(H.div(extra, style="display:none")),
            }

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
        self._push(
            self.put(element, method, history=history, send_resources=send_resources)
        )

    def queue_command(self, command, /, history=None, **arguments):
        if history is None:
            history = self.track_history
        arguments["command"] = command
        self._push(self.oq.put((arguments, history)))

    def print(self, *elements, method="beforeend"):
        for element in elements:
            element = self._to_element(element)
            self.put_nowait(element, method)

    def print_html(self, html, selector=None, method="beforeend", history=None):
        self.queue_command(
            "put",
            selector=selector or self.selector or "body",
            method=method,
            content=html,
            history=history,
        )

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

    def do(self, js, future=None):
        call_template = "$$BEAR.cb({selector}, {extractor}, {future});"
        orig_code = call_template.format(
            selector=Resource(self.selector),
            extractor=f"function () {{ {js} }}",
            future=Resource(future),
        )
        code = self.representer.printer.expand_resources(
            orig_code,
            self.representer.js_embed,
        )
        self.queue_command("eval", selector=self.selector, code=code, history=False)

    def toggle(self, toggle, value=None):
        return self.bearlib.toggle(self, toggle, value)

    def __js_embed__(self, representer):
        if self.selector is None:
            raise Exception(
                "Cannot send page reference to JS because it has no selector."
            )
        return f"document.querySelector('{self.selector}')"

    async def recv(self):
        return await self.iq.get()


def _extractor(root, sequence):
    result = root
    for entry in sequence:
        if isinstance(entry, str):
            result = f"{result}.{entry}"
        elif isinstance(entry, (list, tuple)):
            args = ",".join([str(Resource(x)) for x in entry])
            result = f"{result}({args})"
        else:
            raise TypeError()
    return f"{{ return {result}; }}"


class JavaScriptOperation:
    def __init__(self, element, sequence, root="this"):
        self.__element = element
        self.__sequence = sequence
        self.__future = aio.Future()
        self.__root = root

    def __getattr__(self, attr):
        return type(self)(self.__element, [*self.__sequence, attr], self.__root)

    __getitem__ = __getattr__

    def __call__(self, *args):
        return type(self)(self.__element, [*self.__sequence, args], self.__root)

    def __await__(self):
        self.__element.do(
            _extractor(self.__root, self.__sequence),
            future=self.__future,
        )
        return iter(self.__future)
