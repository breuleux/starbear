import weakref
from collections import deque
from hashlib import md5
from itertools import count
from pathlib import Path
from types import FunctionType, MethodType
from typing import Union

from hrepr import hjson, hrepr, standard_html


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


class AttributeTranslator:
    def __init__(self, route, registry):
        self.route = route
        self.registry = registry

    def translate_hx_get(self, _, v):
        if isinstance(v, str):
            return v
        else:
            method_id = self.registry.register(v)
            return {"hx-get": f"{self.route}/method/{method_id}"}

    def default(self, k, v, dflt):
        if isinstance(v, Path):
            new_v = self.registry.register_file(v)
            return {k: f"{self.route}/file/{new_v}"}
        else:
            return dflt(k, v)

    def get(self, k, dflt):
        k = k.replace("-", "_")
        return getattr(self, f"translate_{k}", lambda k, v: self.default(k, v, dflt))


class Representer:
    def __init__(self, route):
        registry = self.registry = CallbackRegistry(weak=False)

        @hjson.dump.variant
        def _reg_hjson(self, fn: Union[MethodType, FunctionType]):
            method_id = registry.register(fn)
            return f"$$BEAR({method_id})"

        def reg_hjson(obj):
            return str(_reg_hjson(obj))

        self.hrepr = hrepr.configure(
            backend=standard_html.copy(
                initial_state={
                    "hjson": reg_hjson,
                    "attribute_translators": AttributeTranslator(route, registry),
                }
            )
        )
