import asyncio
import functools
import traceback
from dataclasses import dataclass, field
from enum import Enum
from hashlib import md5
from mimetypes import guess_type

from hrepr.resource import JSExpression

from .reg import Reference

ABSENT = object()


def keyword_decorator(deco):
    """Wrap a decorator to optionally takes keyword arguments."""

    @functools.wraps(deco)
    def new_deco(fn=ABSENT, *args, **kwargs):
        if callable(fn):
            return deco(fn, *args, **kwargs)

        if fn is not ABSENT:
            args = (fn, *args)

        @functools.wraps(deco)
        def newer_deco(fn):
            return deco(fn, *args, **kwargs)

        return newer_deco

    return new_deco


class Queue(asyncio.Queue):
    def putleft(self, entry):
        self._queue.appendleft(entry)
        self._unfinished_tasks += 1
        self._finished.clear()
        self._wakeup_next(self._getters)

    def tag(self, arg):
        return ClientWrap(self).tag(arg)

    def wrap(self, **options):
        return ClientWrap(self, **options)

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self.get()

    def __call__(self, value):
        return self.put(value)


class Responses(Enum):
    NO_LISTENERS = "no_listeners"


@dataclass
class Event:
    __match_args__ = ("type", "value")

    type: str
    value: object


@dataclass
class FeedbackEvent(Event):
    response: asyncio.Future = field(default_factory=asyncio.Future)

    def resolve(self, response=None):
        self.response.set_result(response)

    def reject(self, error):
        self.response.set_exception(error)


def format_error(message, debug=None, exception=None, show_debug=False):
    if show_debug:
        tb = exception and traceback.format_exception(
            type(exception),
            exception,
            exception.__traceback__,
        )
        parts = [message, debug, tb and "\n".join(tb)]
        message = "\n\n".join(p for p in parts if p)
    return message


class FeedbackQueue(Queue):
    pass


class VirtualFile:
    def __init__(self, content, type=None, name=None):
        if type is None:
            if name is not None:
                type, _ = guess_type(url=name)

        self.type = type
        self.content = content
        self.name = md5(content.encode("utf8")).hexdigest()
        if name is not None:
            self.name += f"/{name}"


def rewrap(old_func, new_func):
    if isinstance(old_func, ClientWrap):
        return type(old_func)(new_func, **old_func.options)
    else:
        return new_func


class ClientWrap:
    FIELDS = {
        "debounce",
        "extract",
        "form",
        "refs",
        "pack",
        "partial",
        "toggles",
        "pre",
        "post",
        "tag",
    }

    def __init__(self, func, **options):
        if any((key := k) not in self.FIELDS for k in options):
            raise TypeError(f"Invalid argument to ClientWrap: '{key}'")

        if isinstance(func, ClientWrap):
            options = {**func.options, **options}
            func = func.func

        if "partial" in options:
            partial = options["partial"]
            if partial is None or isinstance(partial, (list, tuple)):
                options["partial"] = partial
            else:
                options["partial"] = [partial]

        if "debounce" in options:
            options["id"] = id(func)

        for x in ["pre", "post"]:
            result = options.get(x, None)
            if result is not None:
                if not isinstance(result, (list, tuple)):
                    result = [result]
                result = [
                    JSExpression(f"function (result) {{ {p} }}") if isinstance(p, str) else p
                    for p in result
                ]
                options[x] = result

        self.func = func
        self.options = options

    def tag(self, arg):
        return self.wrap(tag=arg if isinstance(arg, str) else Reference(arg))

    def wrap(self, **options):
        return type(self)(self, **options)

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    def __aiter__(self):
        return aiter(self.func)

    def __js_embed__(self, representer):
        fn = representer.js_embed(self.func)
        options = representer.js_embed(self.options)
        return f"$$BEAR.wrap({fn}, {options})"

    def __attr_embed__(self, gen):
        return f"$$BEAR.event.call(this, {gen.js_embed(self)})"
