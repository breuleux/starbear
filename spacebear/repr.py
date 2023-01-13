import weakref
from asyncio import Future
from collections import deque
from hashlib import md5
from itertools import count
from pathlib import Path
from types import FunctionType, MethodType
from typing import Union

from hrepr import embed, hrepr, standard_html


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
            while not (anchor / "spacebear-anchor").exists():
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


class Representer:
    def __init__(self, route):
        callback_registry = self.callback_registry = CallbackRegistry(weak=False)
        file_registry = self.file_registry = FileRegistry()
        future_registry = self.future_registry = FutureRegistry()
        self.route = route
        self.hrepr = hrepr

        @embed.js_embed.variant
        def js_embed(self, fn: Union[MethodType, FunctionType]):
            method_id = callback_registry.register(fn)
            return f"$$BEAR_FUNC({method_id})"

        @js_embed.register
        def js_embed(self, pth: Path):
            new_pth = file_registry.register(pth)
            return f"'{route}/file/{new_pth}'"

        @js_embed.register
        def js_embed(self, future: Future):
            fid = future_registry.register(future)
            return f"(new $$BEAR_PROMISE({fid}))"

        @embed.attr_embed.variant
        def attr_embed(self, attr: str, fn: Union[MethodType, FunctionType]):
            method_id = callback_registry.register(fn)
            if attr.startswith("hx_"):
                return f"{route}/method/{method_id}"
            else:
                return f"$$BEAR({method_id})"

        @attr_embed.register
        def attr_embed(self, attr: str, pth: Path):
            new_pth = file_registry.register(pth)
            return f"{route}/file/{new_pth}"

        self.printer = standard_html.fork(
            js_embed=js_embed,
            attr_embed=attr_embed,
        )

    def generate(self, *args, **kwargs):
        return self.printer.generate(*args, **kwargs)

    def __call__(self, node):
        return self.hrepr(node)
