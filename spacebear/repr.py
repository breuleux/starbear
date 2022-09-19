import weakref
from collections import deque
from itertools import count
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
    def __init__(self):
        registry = self.registry = CallbackRegistry(weak=False)

        @hjson.dump.variant
        def _reg_hjson(self, fn: Union[MethodType, FunctionType]):
            method_id = registry.register(fn)
            return f"$$BEAR({method_id})"

        def reg_hjson(obj):
            return str(_reg_hjson(obj))

        self.hrepr = hrepr.configure(
            backend=standard_html.copy(initial_state={"hjson": reg_hjson})
        )
