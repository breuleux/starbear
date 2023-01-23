import asyncio
import functools
from dataclasses import dataclass
from hashlib import md5
from mimetypes import guess_type

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
    def tag(self, tag):
        return ClientWrap(self, partial=[tag], pack=True)

    def wrap(self, **options):
        return ClientWrap(self, **options)

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self.get()


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


@dataclass
class ClientWrap:
    DEFAULTS = {
        "debounce": 0,
        "extract": None,
        "form": False,
        "pack": False,
        "partial": None,
    }

    def __init__(self, func, **options):
        if any((key := k) not in self.DEFAULTS for k in options):
            raise TypeError(f"Invalid argument to ClientWrap: '{key}'")

        if isinstance(func, ClientWrap):
            inherit = func.options
            func = func.func
        else:
            inherit = self.DEFAULTS

        options = {**inherit, **options}

        partial = options["partial"]
        if partial is None or isinstance(partial, (list, tuple)):
            options["partial"] = partial
        else:
            options["partial"] = [partial]

        options["id"] = id(func)

        self.func = func
        self.options = options

    def wrap(self, **options):
        return type(self)(self, **options)

    def __aiter__(self):
        return self.func

    def __js_embed__(self, representer):
        fn = representer.js_embed(self.func)
        options = representer.js_embed(self.options)
        return f"$$BEAR_WRAP({fn}, {options})"

    def __attr_embed__(self, representer, attr):
        return f"$$BEAR_EVENT({representer.js_embed(self)})"
