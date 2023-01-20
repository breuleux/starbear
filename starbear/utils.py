import asyncio
import functools
from dataclasses import dataclass
from hashlib import md5
from mimetypes import guess_type
from uuid import uuid4

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
        return QueueWithTag(self, tag)

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self.get()


class QueueWithTag:
    def __init__(self, queue=None, tag=None):
        self.queue = queue or asyncio.Queue()
        self.tag = tag


@dataclass
class QueueResult:
    args: list
    tag: str

    @property
    def arg(self):
        assert len(self.args) == 1
        return self.args[0]


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
