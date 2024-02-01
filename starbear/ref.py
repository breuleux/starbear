import weakref
from collections import deque
from itertools import count
from types import MethodType

_c = count()


def _id(id=None):
    return next(_c) if id is None else id


class StrongRegistry:
    def __init__(self):
        self.map = {}

    def register(self, obj, id=None):
        currid = _id(id)
        self.map[currid] = obj
        return currid

    def resolve(self, id):
        return self.map[id]


class StrongRotatingRegistry:
    def __init__(self, keep, rotate):
        self.keep = keep
        self.rotate = rotate
        self.map = {}
        self.ids = deque()

    def register(self, obj, id=None):
        currid = _id(id)
        self.map[currid] = obj
        self.ids.append(currid)
        if len(self.ids) > self.keep >= 0:
            if self.rotate:
                rm = self.ids.popleft()
                del self.map[rm]
            else:
                raise Exception(
                    "Exceeded limit for keeping strong references to objects."
                )
        return currid

    def resolve(self, id):
        return self.map[id]


class WeakRegistry:
    def __init__(self):
        self.map = {}

    def register(self, obj, id=None):
        currid = _id(id)
        if isinstance(obj, MethodType):
            ref = weakref.WeakMethod(obj)
        else:
            ref = weakref.ref(obj)
        self.map[currid] = ref
        return currid

    def resolve(self, id):
        value = self.map[id]()
        if value is None:
            raise KeyError(id)
        else:
            return value


class ObjectRegistry:
    def __init__(self, strongrefs=False, rotate_strongrefs="limit"):
        self.wr = WeakRegistry()
        if strongrefs:
            self.sr = StrongRotatingRegistry(keep=strongrefs, rotate=rotate_strongrefs)
        else:
            self.sr = None

    def register(self, obj, id=None):
        try:
            return self.wr.register(obj, id)
        except TypeError:
            return self.sr.register(obj, id)

    def resolve(self, id):
        try:
            return self.wr.resolve(id)
        except KeyError:
            return self.sr.resolve(id)


class Reference:
    def __init__(self, datum, id=None):
        self.id = _id(id)
        self.datum = datum
