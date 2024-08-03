import inspect
from functools import cached_property
from pathlib import Path

from hrepr import J
from ..core import Component, rewrap

here = Path(__file__).parent


class Editor(Component):
    def __init__(
        self,
        on_change,
        initial_value,
        bindings,
        autofocus=True,
        debounce=0.25,
        language="text",
        max_height=0,
        first_lineno=False,
        highlight=None,
        options={},
    ):
        self.value = initial_value
        self._on_change = on_change
        self.bindings = bindings
        self.autofocus = autofocus
        self.debounce = debounce
        self.language = language
        self.max_height = max_height
        self.first_lineno = first_lineno
        self.highlight = highlight
        self.options = options

    def event_wrap(self, func):
        async def on_event(evt):
            if evt.get("delta", None):
                for offset, length, txt in evt.delta:
                    self.value = self.value[:offset] + txt + self.value[offset + length :]
            elif evt.get("content", None) is not None:
                self.value = evt.content
            if func:
                if "delta" in evt:
                    del evt["delta"]
                evt["content"] = self.value
                result = func(evt)
                if inspect.isawaitable(result):
                    await result

        return rewrap(func, on_event)

    @cached_property
    def node(self):
        defaults = {
            "lineNumbers": False,
            "minimap": {"enabled": False},
            "scrollBeyondLastLine": False,
            "overviewRulerLanes": 0,
            "folding": False,
            "automaticLayout": True,
        }
        overrides = {
            "value": self.value,
            "language": self.language,
        }
        return J(namespace=here / "editor.js").Editor(
            onChange=self.event_wrap(self._on_change),
            onChangeDebounce=self.debounce,
            autofocus=self.autofocus,
            sendDeltas=True,
            maxHeight=self.max_height,
            firstLineno=self.first_lineno,
            highlight=self.highlight,
            editor=defaults | self.options | overrides,
            bindings={k: self.event_wrap(fn) for k, fn in self.bindings.items()},
        )


class ColorizedText(Component):
    def __init__(self, text, language):
        self.text = text
        self.language = language

    @cached_property
    def node(self):
        return J(namespace=here / "editor.js").colorized(
            text=self.text,
            language=self.language,
        )
