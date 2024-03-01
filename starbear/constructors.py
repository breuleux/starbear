from dataclasses import dataclass

from .page import Page
from .ref import Reference

constructors = {}


@dataclass
class BrowserEvent:
    type: str = None
    inputType: str = None
    button: int = None
    buttons: int = None
    shiftKey: bool = None
    altKey: bool = None
    ctrlKey: bool = None
    metaKey: bool = None
    key: str = None
    target: Page = None
    form: Page = None
    value: object = None
    refs: list = None
    tag: str = None

    def __getitem__(self, item):
        return getattr(self, item)

    @property
    def ref(self):
        if self.refs:
            return self.refs[0]
        else:
            return None

    @property
    def obj(self):
        return self.ref.datum


class FormData(dict):
    def __init__(self, data, target, submit, refs, tag):
        super().__init__(data)
        self.target = target
        self.submit = submit
        self.refs = refs
        self.tag = tag

    @property
    def ref(self):
        if self.refs:
            return self.refs[0]
        else:
            return None

    @property
    def obj(self):
        return self.ref.datum


class NamespaceDict(dict):
    def __getattr__(self, item):
        return self[item]


def register_constructor(key):
    def deco(fn):
        constructors[key] = fn
        return fn

    return deco


@register_constructor("HTMLElement")
def _(page, selector):
    return page[selector]


@register_constructor("Event")
def _(page, data):
    return BrowserEvent(**data)


@register_constructor("FormData")
def _(page, data, target=None, submit=None, refs=None, tag=None):
    return FormData(data, target, submit, refs, tag)


@register_constructor("Promise")
def _(page, id):
    async def resolve(value):
        await page.bearlib.resolveLocalPromise(id, value)

    return resolve


@register_constructor("Reference")
def _(page, id):
    return page.representer.object_registry.resolve(id)


@register_constructor("FullReference")
def _(page, id):
    return Reference(
        page.representer.object_registry.resolve(id),
        id=id,
    )


def construct(page, dct):
    args = dict(dct)
    name = args.pop("%")
    return constructors[name](page, **args)
