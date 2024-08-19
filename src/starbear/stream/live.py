from functools import cached_property

from hrepr import H

from .functions import Multiplexer

RESET = object()


def live(obj, hrepr=None, **listeners):
    if hasattr(obj, "__live_element__"):
        elem = obj.__live_element__(H, hrepr)
    else:
        elem = H.live_element()
    return elem(runner=obj.__live__, id=True, **listeners)


class GeneratorPrinter:
    def __init__(self, generator):
        self.generator = generator


class Inplace(GeneratorPrinter):
    async def __live__(self, elem):
        async for obj in self.generator:
            elem.set(obj)


class Print(GeneratorPrinter):
    async def __live__(self, elem):
        async for obj in self.generator:
            if elem is RESET:
                elem.clear()
            else:
                elem.print(obj)


class Watchable:
    @cached_property
    def _mx(self):
        return Multiplexer()

    def notify(self, event):
        self._mx.notify(event)

    def watch_context(self):
        return self._mx.stream_context()

    async def watch(self):
        return await self._mx.stream()
