import re
from pathlib import Path
from typing import Union

from hrepr import H, Tag
from lxml.html import html5parser
from ovld import ovld


class Placeholder:
    def __init__(self, type, name):
        self.type = type
        self.name = name

    def __str__(self):
        return "{{" + self.type + ":" + self.name + "}}"

    __repr__ = __str__


class PlaceholderSequence(list):
    pass


def _parse_template(path_or_string):
    if isinstance(path_or_string, Path):
        source = path_or_string.read_text()
    elif isinstance(path_or_string, str):
        source = path_or_string
    else:
        raise TypeError("path_or_string argument should be a Path or a str")

    html = html5parser.fromstring(source)
    return _html_to_h(html)


def _extract_placeholders(txt, single=False):
    parts = re.split(string=txt, pattern=r"\{\{ *([a-zA-Z0-9_]* *:?[^}]+) *\}\}")
    results = []
    for i, p in enumerate(parts):
        if i % 2 == 0:
            if p:
                results.append(p)
        else:
            if ":" in p:
                typ, name = p.split(":")
            else:
                typ = "variable"
                name = p
            results.append(Placeholder(type=typ, name=name))
    if single:
        if not results:
            return ""
        elif len(results) == 1:
            return results[0]
        else:
            return PlaceholderSequence(results)
    return results


def _html_to_h(etree):
    base_node = getattr(H, etree.tag.split("}")[1])
    children = []
    if etree.text:
        children.extend(_extract_placeholders(etree.text))
    for subtree in etree:
        children.append(_html_to_h(subtree))
        if subtree.tail:
            children.append(subtree.tail)
    return base_node.fill(
        attributes=dict(
            (x, True if y == "" else _extract_placeholders(y, single=True))
            for x, y in etree.items()
        ),
        children=children,
    )


@ovld
def _template(nodes: Union[list, tuple], values: dict):
    return type(nodes)(_template(node, values) for node in nodes)


@ovld
def _template(seq: PlaceholderSequence, values: dict):
    return "".join(map(str, (_template(x, values) for x in seq)))


@ovld
def _template(node: Placeholder, values: dict):
    processor = values[f"_{node.type}"]
    return _template(processor(node.name), values)


@ovld
def _template(node: Tag, values: dict):
    return Tag(node.name).fill(
        children=[_template(child, values) for child in node.children],
        attributes={k: _template(v, values) for k, v in node.attributes.items()},
    )


@ovld
def _template(node: object, values: dict):
    return node


_cached_templates = {}


class Template:
    def __init__(self, tpl):
        if isinstance(tpl, Tag):
            self.template = tpl
        elif isinstance(tpl, (str, Path)):
            tpl = _parse_template(tpl)
        self.template = tpl

    def __call__(self, **values):
        values.setdefault("_variable", lambda name: values[name])
        return _template(self.template, values)


def template(tpl, nocache=False, /, **values):
    if isinstance(tpl, Tag):
        return Template(tpl)(**values)
    if tpl not in _cached_templates or nocache:
        _cached_templates[tpl] = Template(tpl)
    return _cached_templates[tpl](**values)
