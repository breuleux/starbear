import asyncio as aio

from hrepr import H


class Page:
    def __init__(self, ws, representer, selector=None):
        self.ws = ws
        self.selector = selector
        self.representer = representer
        self.sent_resources = set()
        self.tasks = set()

    def __getitem__(self, selector):
        if self.selector is not None:
            selector = f"{self.selector} {selector}"
        return self.page_select(selector)

    def page_select(self, selector):
        return type(self)(ws=self.ws, selector=selector, representer=self.representer)

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

    async def _put(self, element, method):
        sel = self.selector or "body"
        return await self.ws.send_text(str(element(hx_swap_oob=f"{method}:{sel}")))

    async def put(self, element, method):
        for res in element.collect_resources():
            if res not in self.sent_resources:
                self.sent_resources.add(res)
                await self.page_select("head")._put(H.div(res), "beforeend")
        return await self._put(element, method)

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
        return await self.ws.receive_json()
