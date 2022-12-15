import weakref
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
        self.file_to_url = {}
        self.url_to_file = {}

    def register_file(self, pth):
        pth = pth.absolute()
        if pth not in self.file_to_url:
            anchor = pth.parent
            while not (anchor / "spacebear-anchor").exists():
                anchor = anchor.parent
                if anchor == Path("/"):
                    anchor = pth.parent
                    break
            dirname = md5(str(anchor).encode("utf8")).hexdigest()
            url = str(dirname / pth.relative_to(anchor))
            self.file_to_url[pth] = url
            self.url_to_file[url] = pth
        return self.file_to_url[pth]

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


class Representer:
    def __init__(self, route):
        registry = self.registry = CallbackRegistry(weak=False)
        self.route = route
        self.hrepr = hrepr

        @embed.js_embed.variant
        def js_embed(self, fn: Union[MethodType, FunctionType]):
            method_id = registry.register(fn)
            return f"$$BEAR({method_id})"

        @js_embed.register
        def js_embed(self, pth: Path):
            new_pth = registry.register_file(pth)
            return f"'{route}/file/{new_pth}'"

        @embed.attr_embed.variant
        def attr_embed(self, attr: str, fn: Union[MethodType, FunctionType]):
            method_id = registry.register(fn)
            if attr.startswith("hx_"):
                return f"{route}/method/{method_id}"
            else:
                return f"$$BEAR({method_id})"

        @attr_embed.register
        def attr_embed(self, attr: str, pth: Path):
            new_pth = registry.register_file(pth)
            return f"{route}/file/{new_pth}"

        self.printer = standard_html.fork(
            js_embed=js_embed,
            attr_embed=attr_embed,
        )

    def generate(self, *args, **kwargs):
        return self.printer.generate(*args, **kwargs)

    def __call__(self, node):
        return self.hrepr(node)
