from hrepr import H, Tag

from starbear import template


def test_template_int():
    tpl = "<div>{{x}}</div>"
    result = template(tpl, x=3)
    assert isinstance(result, Tag)
    assert str(result) == "<div>3</div>"


def test_template_tag():
    tpl = "<div>{{x}}</div>"
    result = template(tpl, x=H.b("hello"))
    assert str(result) == "<div><b>hello</b></div>"
