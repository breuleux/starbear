import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass

from hrepr import H

from .utils import Queue


def live(obj, hrepr=None, **listeners):
    if hasattr(obj, "__live_element__"):
        elem = obj.__live_element__(H, hrepr)
    else:
        elem = H.live_element()
    return elem(runner=obj.__live__, id=True, **listeners)


@dataclass
class AutoRefresh:
    func: object
    refresh_rate: float = 0.05

    async def __live__(self, element):
        while True:
            value = self.func() if callable(self.func) else self.func
            if value is not None:
                element.set(value)
            await asyncio.sleep(self.refresh_rate)


class Watchable:
    def notify(self, event):
        for q in getattr(self, "_queues", ()):
            q.put_nowait(event)

    @asynccontextmanager
    async def watch_context(self):
        q = Queue()
        if not hasattr(self, "_queues"):
            self._queues = set()
        self._queues.add(q)
        try:
            yield q
        finally:
            self._queues.discard(q)

    async def watch(self):
        async with self.watch_context() as q:
            async for event in q:
                yield event
