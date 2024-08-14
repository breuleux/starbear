from hrepr import J

from ..common import here
from ..core.constructors import register_constructor


@register_constructor("MonacoEditor")
def _(page, id, content=None, delta=None):
    store = page.representer.store
    key = ("MonacoEditor", id)
    if content is not None:
        store[key] = content
    elif key not in store:
        raise Exception("Editor value is not available from Python.")
    elif delta is None:
        return store[key]
    else:
        value = store[key]
        for offset, length, txt in delta:
            value = value[:offset] + txt + value[offset + length :]
        store[key] = value
    return store[key]


editor_module = J(namespace=here / "editor.js")

Editor = editor_module.Editor
colorized = editor_module.colorized
