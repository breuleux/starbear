import weakref
from collections import deque
from hashlib import md5
from itertools import count
from pathlib import Path
from types import FunctionType, MethodType
from typing import Union

from hrepr import embed, hrepr, standard_html
from ovld import has_attribute

from .ref import ObjectRegistry, Reference, StrongRegistry
from .utils import FeedbackQueue, VirtualFile


class CallbackRegistry:
    def __init__(self, weak=False, keep=None):
        self.id = count()
        self.weak = weak
        self.keep = (keep or 10000) if self.weak else -1
        self.weak_map = {}
        self.strong_map = {}
        self.strong_ids = deque()

    def register(self, method):
        currid = next(self.id)
        weak = self.weak
        if weak:
            try:
                self.weak_map[currid] = weakref.WeakMethod(method)
            except TypeError:
                weak = False

        if not weak:
            self.strong_map[currid] = method
            self.strong_ids.append(currid)
            if len(self.strong_ids) > self.keep >= 0:
                rm = self.strong_ids.popleft()
                del self.strong_map[rm]

        return currid

    def resolve(self, id):
        try:
            m = self.weak_map[id]()
        except KeyError:
            m = self.strong_map.get(id, None)

        if m is None:
            raise KeyError(id)

        return m


class FileRegistry:
    def __init__(self):
        self.file_to_url = {}
        self.url_to_file = {}

    def find_anchor(self, filename):
        filename = filename.absolute()
        anchor = filename
        while anchor != Path("/"):
            anchor = anchor.parent
            if anchor in self.file_to_url:
                return (anchor, self.file_to_url[anchor])
        else:
            anchor = filename.parent
            while not (anchor / "starbear-anchor").exists():
                anchor = anchor.parent
                if anchor == Path("/"):
                    anchor = filename.parent
                    break
            url = md5(str(anchor).encode("utf8")).hexdigest()
            self.file_to_url[anchor] = url
            self.url_to_file[url] = anchor
            return (anchor, url)

    def register(self, filename):
        filename = filename.absolute()
        anchor, base_url = self.find_anchor(filename)
        url = str(base_url / filename.relative_to(anchor))
        return url

    def get_file_from_url(self, url):
        url = orig = Path(url)
        while url != url.parent and str(url) not in self.url_to_file:
            url = url.parent
        anchor = self.url_to_file.get(str(url), None)
        return anchor and str(anchor / orig.relative_to(url))


class VFileRegistry:
    def __init__(self):
        self.vfiles = {}

    def register(self, vfile):
        self.vfiles[vfile.name] = vfile
        return vfile.name

    def get(self, pth):
        return self.vfiles[pth]


class FutureRegistry:
    def __init__(self):
        self.current_id = count()
        self.futures = {}

    def register(self, future):
        fid = next(self.current_id)
        self.futures[fid] = future
        return fid

    def resolve(self, fid, value):
        if fid not in self.futures:
            return
        self.futures[fid].set_result(value)
        del self.futures[fid]

    def reject(self, fid, error):
        if fid not in self.futures:
            return
        self.futures[fid].set_exception(Exception(error))
        del self.futures[fid]


class QueueRegistry:
    def __init__(self):
        self.current_id = count()
        self.queues = {}

    def register(self, queue):
        qid = next(self.current_id)
        self.queues[qid] = queue
        return qid

    def put(self, qid, value):
        self.queues[qid].put_nowait(value)


class Representer:
    def __init__(self, route, strongrefs=False):
        from asyncio import Future, Queue

        representer = self

        if strongrefs:
            object_registry = self.object_registry = StrongRegistry()
        else:
            object_registry = self.object_registry = ObjectRegistry(
                strongrefs=100, rotate_strongrefs=False
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
