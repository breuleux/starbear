from pathlib import Path

import pytest

from starbear.server.find import (
    collect_locations,
    collect_routes,
    collect_routes_from_module,
    compile_routes,
)


def test_compile_routes_error():
    with pytest.raises(TypeError):
        compile_routes("/", {"/": "???"})


def test_collect_routes_error():
    with pytest.raises(FileNotFoundError):
        collect_routes("nonexistent")


def test_collect_locations():
    from . import app_hello

    locs = collect_locations(collect_routes_from_module(app_hello))
    assert all(x.is_relative_to(Path(app_hello.__file__).parent) for x in locs)
