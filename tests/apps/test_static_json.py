import requests

from starbear import simplebear

from .utils import asset_getter

asset = asset_getter(__file__)


async def exponential(x):
    return (x * 2) or 1


@simplebear
async def __app__(request):
    x = request.query_params["x"]
    return {"square": int(x) ** 2}


def test_app(app_config):
    resp = requests.get("http://127.0.0.1:9182/?x=12")
    assert resp.json() == {"square": 144}

    resp = requests.get("http://127.0.0.1:9182/?x=7")
    assert resp.json() == {"square": 49}
