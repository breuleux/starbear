import asyncio as aio

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
        self.window = JavaScriptOperation(self, [], False)

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

    async def _put(self, element, method, history=None, send_resources=False):
        if history is None:
            history = self.track_history
        sel = self.selector or "body"
        element = element(hx_swap_oob=f"{method}:{sel}")
        parts, extra, resources = self.representer.generate(
            element, filter_resources=self.sent_resources if send_resources else None
        )
        if not resources.empty():
            await self.page_select("head")._put(H.div(resources), "beforeend")
        to_send = str(parts)
        if extra:
            to_send += str(
                H.div(extra, style="display:none", hx_swap_oob=f"beforeend:{sel}")
            )
        return await self.oq.put((to_send, history))

    async def put(self, element, method, history=None):
        return await self._put(element, method, history=history, send_resources=True)

    def print(self, *elements, method="beforeend"):
        for element in elements:
            element = H.div(self._to_element(element))
            self._push(self.put(element, method))

    def print_html(self, html):
        self._push(self._put(H.div(H.raw(html)), "beforeend"))

    def set(self, element):
        element = H.div(self._to_element(element))
        self._push(self.put(element, "innerHTML"))

    def replace(self, element):
        element = self._to_element(element)
        self._push(self.put(element, "outerHTML"))

    def clear(self):
        self._push(self.put(H.span(), "innerHTML"))

    def delete(self):
        self._push(self.put(H.span(), "outerHTML"))

    def do(self, js):
        self.page_select("body").without_history().print(
            H.script(
                call_template.format(
                    selector=Resource(self.selector),
                    extractor=f"function () {{ {js} }}",
                    future="null",
                )
            ),
        )

    def toggle(self, toggle, value=None):
        return self.window["$$BEAR_TOGGLE"](self, toggle, value)

    def __js_embed__(self, representer):
        if self.selector is None:
            raise Exception(
                "Cannot send page reference to JS because it has no selector."
            )
        return f"document.querySelector('{self.selector}')"

    async def recv(self):
        return await self.iq.get()


call_template = "$$BEAR_CB({selector}, {extractor}, {future});"


def _extractor(sequence):
    result = "x"
    for entry in sequence:
        if isinstance(entry, str):
            result = f"{result}.{entry}"
        elif isinstance(entry, (list, tuple)):
            args = ",".join([str(Resource(x)) for x in entry])
            result = f"{result}({args})"
        else:
            raise TypeError()
    return f"(x => {result})"


class JavaScriptOperation:
    def __init__(self, element, sequence, selector=None):
        self.__element = element
        self.__sequence = sequence
        self.__future = aio.Future()
        self.__selector = (
            False if selector is False else (selector or self.__element.selector)
        )

    def __getattr__(self, attr):
        return type(self)(self.__element, [*self.__sequence, attr], self.__selector)

    __getitem__ = __getattr__

    def __call__(self, *args):
        return type(self)(self.__element, [*self.__sequence, args], self.__selector)

    def __await__(self):
        self.__element.page_select("body").without_history().print(
            H.script(
                call_template.format(
                    selector=Resource(self.__selector or None),
                    extractor=_extractor(self.__sequence),
                    future=Resource(self.__future),
                )
            ),
        )
        return iter(self.__future)
