import weakref
from collections import deque
from hashlib import md5
from itertools import count
from pathlib import Path
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
                raise Exception("Exceeded limit for keeping strong references to objects.")
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
    def __init__(self, strongrefs=100, rotate_strongrefs=True):
        self.wr = WeakRegistry()
        self.sr = StrongRotatingRegistry(keep=strongrefs, rotate=rotate_strongrefs)

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
