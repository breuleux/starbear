import asyncio
from dataclasses import dataclass


class Queue(asyncio.Queue):
    def tag(self, tag):
        return QueueWithTag(self, tag)


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
