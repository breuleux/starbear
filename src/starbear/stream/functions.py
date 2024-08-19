import asyncio
import inspect
import math
import time
from contextlib import asynccontextmanager
from itertools import count as _count

from ..core.utils import Queue


class MergeStream:
    def __init__(self, *streams, stay_alive=False):
        self.queue = Queue()
        self.active = 1 if stay_alive else 0
        for stream in streams:
            self.add(stream)

    async def _add(self, fut, iterator):
        try:
            result = await fut
            self.queue.put_nowait((result, iterator))
        except StopAsyncIteration:
            self.queue.put_nowait((None, False))

    def add(self, fut):
        self.active += 1
        if inspect.isasyncgen(fut):
            it = aiter(fut)
            coro = self._add(anext(it), it)
        else:
            coro = self._add(fut, None)
        return asyncio.create_task(coro)

    async def __aiter__(self):
        async for result, it in self.queue:
            if it is False:
                self.active -= 1
            elif it is None:
                yield result
                self.active -= 1
            else:
                asyncio.create_task(self._add(anext(it), it))
                yield result
            if self.active == 0:
                break


DONE = object()


class Multiplexer:
    def __init__(self, source=None):
        self.source = source
        self.queues = set()
        self.done = False
        self._is_hungry = asyncio.Future()
        if source is not None:
            self.main_coroutine = asyncio.create_task(self.run())

    def notify(self, event):
        for q in self.queues:
            q.put_nowait(event)

    def end(self):
        assert not self.main_coroutine
        self.done = True
        self.notify(DONE)

    def _be_hungry(self):
        if not self._is_hungry.done():
            self._is_hungry.set_result(True)

    @asynccontextmanager
    async def stream_context(self):
        q = Queue()
        self.queues.add(q)
        try:
            yield q
        finally:
            self.queues.discard(q)

    async def stream(self):
        if self.done:
            return
        self._be_hungry()
        async with self.stream_context() as q:
            async for event in q:
                if event is DONE:
                    break
                if q.empty:
                    self._be_hungry()
                yield event

    async def run(self):
        async for event in self.source:
            await self._is_hungry
            self._is_hungry = asyncio.Future()
            self.notify(event)
        self.main_coroutine = None
        self.end()

    def __hrepr__(self, H, hrepr):
        return hrepr(self.stream())


merge = MergeStream


async def repeat(value_or_func, *, count=None, interval):
    i = 0
    if count is None:
        count = math.inf
    while i < count:
        if callable(value_or_func):
            yield value_or_func()
        else:
            yield value_or_func
        await asyncio.sleep(interval)
        i += 1


async def count(interval):
    for i in _count():
        yield i
        await asyncio.sleep(interval)


async def take(stream, n):
    curr = 0
    async for x in stream:
        yield x
        curr += 1
        if curr >= n:
            break


async def filter(stream, fn):
    async for x in stream:
        if fn(x):
            yield x


async def map(stream, fn):
    async for x in stream:
        yield fn(x)


async def scan(stream, fn, init=None):
    current = init
    async for x in stream:
        current = fn(current, x)
        yield current


async def debounce(stream, delay=None, max_wait=None):
    MARK = object()

    async def mark(delay):
        await asyncio.sleep(delay)
        return MARK

    ms = MergeStream()
    max_time = None
    target_time = None
    ms.add(stream)
    current = None
    async for element in ms:
        now = time.time()
        if element is MARK:
            delta = target_time - now
            if delta > 0:
                ms.add(mark(delta))
            else:
                yield current
                max_time = None
                target_time = None
        else:
            new_element = target_time is None
            if max_time is None and max_wait is not None:
                max_time = now + max_wait
            target_time = now + delay
            if max_time:
                target_time = min(max_time, target_time)
            if new_element:
                ms.add(mark(target_time - now))
            current = element
