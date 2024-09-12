import asyncio
import time
from dataclasses import dataclass

from hrepr import H

from starbear.core.app import bear
from starbear.core.utils import FeedbackEvent, Queue, Responses
from starbear.stream.live import live

base_delay = 0.1


@dataclass
class Teddy:
    value: str

    async def __live__(self, element):
        element.print(self.value)


@dataclass
class OOBPrinter:
    value: str
    delay: float
    target: str

    async def __live__(self, element):
        await asyncio.sleep(self.delay)
        element.page_select(self.target).print(self.value)


@dataclass
class Producer:
    alpha: int

    async def __live__(self, element):
        element.print(
            H.div["good"]("good: "),
            H.div["bad"]("bad: "),
            H.div["unknown"]("unknown: "),
        )
        for i in range(10):
            etype = "odd" if i % 2 == 1 else "even"
            goodness = await (yield FeedbackEvent(etype, self.alpha**i))
            if goodness is True:
                element[".good"].print(H.b(i))
            elif goodness is False:
                element[".bad"].print(H.b(i))
            elif goodness is Responses.NO_LISTENERS:
                element[".unknown"].print(H.b(i))


@bear
async def __app__(page):
    q = Queue()
    page.print(container := H.div(id=True))
    page.print(H.div(id="out-of-band1"))
    page.print(H.div(id="out-of-band2"))
    page.print(H.div(Teddy("hello"), id="teddy"))
    # The first OOBPrinter is erased by the second, which means that it should be
    # cancelled. Might be fiddly with the delays.
    page[container].set(
        OOBPrinter(value="should not happen", delay=2 * base_delay, target="#out-of-band1")
    )
    page[container].set(OOBPrinter(value="yay!", delay=base_delay, target="#out-of-band2"))
    page.print(live(Producer(2), on_produce_odd=q))
    async for event in q:
        assert event.type == "odd"
        event.resolve(event.value == 32)


def test_teddy(app):
    assert app.locator("#teddy").inner_text() == "hello"


def test_delayed(app):
    # Try increasing base_delay if this fails
    time.sleep(3 * base_delay)
    assert app.locator("#out-of-band1").inner_text() == ""
    assert app.locator("#out-of-band2").inner_text() == "yay!"


def test_events(app):
    assert app.locator(".good").inner_text() == "good: 5"
    assert app.locator(".bad").inner_text() == "bad: 1379"
    assert app.locator(".unknown").inner_text() == "unknown: 02468"
