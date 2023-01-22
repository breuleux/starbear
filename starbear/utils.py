import asyncio
import functools
from dataclasses import dataclass
from hashlib import md5
from mimetypes import guess_type
from typing import Union

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
    func: object
    debounce: float = 0
    extract: Union[list[str], str] = None
    form: bool = False
    pack: bool = False
    partial: object = ABSENT

    @property
    def options(self):
        if self.partial is ABSENT:
            part = None
        elif not isinstance(self.partial, (list, tuple)):
            part = [self.partial]
        return {
            "id": id(self),
            "debounce": self.debounce,
            "extract": self.extract,
            "form": self.form,
            "pack": self.pack,
            "partial": part,
        }

    def __aiter__(self):
        return self.func
