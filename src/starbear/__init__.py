from hrepr import H, J, returns
from hrepr.resource import Resource

from .common import UsageError, _here
from .config import config
from .core.app import bear, simplebear
from .core.constructors import BrowserEvent, FormData, NamespaceDict, register_constructor
from .core.page import Component, Page, selector_for
from .core.reg import Reference
from .core.repr import hrepr
from .core.templating import Template, template
from .core.utils import (
    ClientWrap,
    Event,
    FeedbackEvent,
    FeedbackQueue,
    Queue,
    Responses,
    VirtualFile,
    rewrap,
)
from .stream.live import GeneratorPrinter, Inplace, Print, Watchable, live
from .version import version

__all__ = [
    "H",
    "J",
    "returns",
    "Resource",
    "UsageError",
    "here",
    "config",
    "bear",
    "simplebear",
    "BrowserEvent",
    "FormData",
    "NamespaceDict",
    "register_constructor",
    "Component",
    "Page",
    "selector_for",
    "Reference",
    "hrepr",
    "live",
    "Inplace",
    "GeneratorPrinter",
    "Print",
    "Watchable",
    "Template",
    "template",
    "ClientWrap",
    "Event",
    "FeedbackEvent",
    "FeedbackQueue",
    "Queue",
    "Responses",
    "VirtualFile",
    "rewrap",
    "version",
]


def __getattr__(attr):
    if attr == "here":
        return _here(2)

    raise AttributeError(attr)
