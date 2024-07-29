from asyncio import Future, Queue
from pathlib import Path
from types import FunctionType, MethodType
from typing import Union

from hrepr import BlockGenerator, HTMLGenerator, hrepr
from ovld import extend_super

from .reg import (
    FileRegistry,
    FutureRegistry,
    ObjectRegistry,
    QueueRegistry,
    Reference,
    StrongRegistry,
    VFileRegistry,
    WeakRegistry,
)
from .utils import FeedbackQueue, VirtualFile


class RepresenterState:
    def __init__(self, route, strongrefs=False):
        self.route = route
        if strongrefs is True:
            self.object_registry = StrongRegistry()
        elif not strongrefs:
            self.object_registry = WeakRegistry()
        elif strongrefs < 0:
            self.object_registry = ObjectRegistry(strongrefs=-strongrefs, rotate_strongrefs=True)
        else:
            self.object_registry = ObjectRegistry(strongrefs=strongrefs, rotate_strongrefs=False)
        self.file_registry = FileRegistry()
        self.vfile_registry = VFileRegistry()
        self.future_registry = FutureRegistry()
        self.queue_registry = QueueRegistry()


class StarbearHTMLGenerator(HTMLGenerator):
    def __init__(self, representer_state):
        self.state = representer_state
        self.hrepr = hrepr
        super().__init__(block_generator_class=StarbearBlockGenerator)


class StarbearBlockGenerator(BlockGenerator):
    @property
    def route(self):
        return self.global_generator.state.route

    def register_object(self, x, **kwargs):
        return self.global_generator.state.object_registry.register(x, **kwargs)

    def register_file(self, x, **kwargs):
        return self.global_generator.state.file_registry.register(x, **kwargs)

    def register_vfile(self, x, **kwargs):
        return self.global_generator.state.vfile_registry.register(x, **kwargs)

    def register_future(self, x, **kwargs):
        return self.global_generator.state.future_registry.register(x, **kwargs)

    def register_queue(self, x, **kwargs):
        return self.global_generator.state.queue_registry.register(x, **kwargs)

    @extend_super
    def js_embed(self, fn: Union[MethodType, FunctionType]):  # noqa: F811
        method_id = self.register_object(fn)
        return f"$$BEAR.func({method_id})"

    def js_embed(self, ref: Reference):  # noqa: F811
        obj_id = self.register_object(ref.datum)
        return f"$$BEAR.ref({obj_id})"

    def js_embed(self, pth: Path):  # noqa: F811
        new_pth = self.register_file(pth)
        return f"'{self.route}/file/{new_pth}'"

    def js_embed(self, future: Future):  # noqa: F811
        fid = self.register_future(future)
        return f"$$BEAR.promise({fid})"

    def js_embed(self, queue: Queue):  # noqa: F811
        qid = self.register_queue(queue)
        return f"$$BEAR.queue({qid})"

    def js_embed(self, queue: FeedbackQueue):  # noqa: F811
        qid = self.register_queue(queue)
        return f"$$BEAR.queue({qid}, true)"

    @extend_super
    def attr_embed(self, fn: Union[MethodType, FunctionType]):  # noqa: F811
        method_id = self.register_object(fn)
        return f"$$BEAR.event.call(this, $$BEAR.func({method_id}))"

    def attr_embed(self, ref: Reference):  # noqa: F811
        obj_id = self.register_object(ref.datum, id=ref.id)
        return f"obj#{obj_id}"

    def attr_embed(self, queue: Queue):  # noqa: F811
        qid = self.register_queue(queue)
        return f"$$BEAR.event.call(this, $$BEAR.queue({qid}))"

    def attr_embed(self, pth: Path):  # noqa: F811
        new_pth = self.register_file(pth)
        return f"{self.route}/file/{new_pth}"

    def attr_embed(self, vf: VirtualFile):  # noqa: F811
        pth = self.register_vfile(vf)
        return f"{self.route}/vfile/{pth}"
