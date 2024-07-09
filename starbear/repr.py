from pathlib import Path
from types import FunctionType, MethodType
from typing import Union

from hrepr import embed, hrepr, standard_html
from ovld import has_attribute

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


class Representer:
    def __init__(self, route, strongrefs=False):
        from asyncio import Future, Queue

        representer = self

        if strongrefs is True:
            object_registry = self.object_registry = StrongRegistry()
        elif not strongrefs:
            object_registry = self.object_registry = WeakRegistry()
        elif strongrefs < 0:
            object_registry = self.object_registry = ObjectRegistry(
                strongrefs=-strongrefs, rotate_strongrefs=True
            )
        else:
            object_registry = self.object_registry = ObjectRegistry(
                strongrefs=strongrefs, rotate_strongrefs=False
            )

        file_registry = self.file_registry = FileRegistry()
        vfile_registry = self.vfile_registry = VFileRegistry()
        future_registry = self.future_registry = FutureRegistry()
        queue_registry = self.queue_registry = QueueRegistry()
        self.route = route
        self.hrepr = hrepr

        @embed.js_embed.variant
        def js_embed(self, fn: Union[MethodType, FunctionType]):
            method_id = object_registry.register(fn)
            return f"$$BEAR.func({method_id})"

        @js_embed.register
        def js_embed(self, ref: Reference):
            obj_id = object_registry.register(ref.datum)
            return f"$$BEAR.ref({obj_id})"

        @js_embed.register
        def js_embed(self, pth: Path):
            new_pth = file_registry.register(pth)
            return f"'{route}/file/{new_pth}'"

        @js_embed.register
        def js_embed(self, future: Future):
            fid = future_registry.register(future)
            return f"$$BEAR.promise({fid})"

        @js_embed.register
        def js_embed(self, queue: Queue):
            qid = queue_registry.register(queue)
            return f"$$BEAR.queue({qid})"

        @js_embed.register
        def js_embed(self, queue: FeedbackQueue):
            qid = queue_registry.register(queue)
            return f"$$BEAR.queue({qid}, true)"

        @js_embed.register
        def js_embed(self, obj: has_attribute("__js_embed__")):
            return obj.__js_embed__(representer)

        @embed.attr_embed.variant
        def attr_embed(self, attr: str, fn: Union[MethodType, FunctionType]):
            method_id = object_registry.register(fn)
            if attr.startswith("hx_"):
                return f"{route}/method/{method_id}"
            else:
                return f"$$BEAR.event.call(this, $$BEAR.func({method_id}))"

        @attr_embed.register
        def attr_embed(self, attr: str, ref: Reference):
            obj_id = object_registry.register(ref.datum, id=ref.id)
            return f"obj#{obj_id}"

        @attr_embed.register
        def attr_embed(self, attr: str, queue: Queue):
            qid = queue_registry.register(queue)
            return f"$$BEAR.event.call(this, $$BEAR.queue({qid}))"

        @attr_embed.register
        def attr_embed(self, attr: str, pth: Path):
            new_pth = file_registry.register(pth)
            return f"{route}/file/{new_pth}"

        @attr_embed.register
        def attr_embed(self, attr: str, vf: VirtualFile):
            pth = vfile_registry.register(vf)
            return f"{route}/vfile/{pth}"

        @attr_embed.register
        def attr_embed(self, attr: str, style: dict):
            if attr == "style":
                return ";".join(f"{k}:{v}" for k, v in style.items())
            else:
                raise TypeError(f"Cannot serialize a dict for attribute '{attr}'")

        @attr_embed.register
        def attr_embed(self, attr: str, obj: has_attribute("__attr_embed__")):
            return obj.__attr_embed__(representer, attr)

        self.js_embed = js_embed
        self.attr_embed = attr_embed

        self.printer = standard_html.fork(
            js_embed=js_embed,
            attr_embed=attr_embed,
        )

    def generate(self, *args, **kwargs):
        return self.printer.generate(*args, **kwargs)

    def generate_string(self, element):
        parts, extras, resources = self.printer.generate(element)
        return str(parts)

    def __call__(self, node):
        return self.hrepr(node)
