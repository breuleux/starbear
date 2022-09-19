import asyncio as aio

from hrepr import H


class Page:
    def __init__(self, iq, oq, representer, selector=None, track_history=True):
        self.iq = iq
        self.oq = oq
        self.selector = selector
        self.representer = representer
        self.track_history = track_history
        self.sent_resources = set()
        self.tasks = set()

    def __getitem__(self, selector):
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
            )

    def without_history(self):
        return self.with_history(False)

    def _push(self, coro):
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

    async def _put(self, element, method, history=None):
        if history is None:
            history = self.track_history
        sel = self.selector or "body"
        txt = str(element(hx_swap_oob=f"{method}:{sel}"))
        return await self.oq.put((txt, history))

    async def put(self, element, method, history=None):
        for res in element.collect_resources():
            if res not in self.sent_resources:
                self.sent_resources.add(res)
                await self.page_select("head")._put(H.div(res), "beforeend")
        return await self._put(element, method, history=history)

    def print(self, element):
        element = H.div(self._to_element(element))
        self._push(self.put(element, "beforeend"))

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

    async def recv(self):
        return await self.iq.get()
