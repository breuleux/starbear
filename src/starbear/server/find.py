"""Find spacebears/routes in a file or directory"""

import importlib
import pkgutil
import runpy
import sys
from functools import reduce
from pathlib import Path

import starlette
from ovld import ovld
from starlette.routing import Mount, Route

import starbear

from ..core.app import AbstractBear
from .index import Index


def collect_routes_from_module(mod, module_field=None):
    def process_module(path, submod, ispkg):
        subroutes = getattr(submod, module_field or "__app__", None)
        if subroutes is not None:
            routes[path] = subroutes
        elif ispkg:
            routes[path] = collect_routes_from_module(submod)

    locations = mod.__spec__.submodule_search_locations
    routes = {}
    if locations is None:
        process_module("/", mod, False)
    else:
        for info in pkgutil.iter_modules(locations, prefix=f"{mod.__name__}."):
            submod = importlib.import_module(info.name)
            path = f"/{submod.__name__.split('.')[-1]}/"
            process_module(path, submod, info.ispkg)

    if "/index/" not in routes.keys():
        routes["/index/"] = Index()

    return routes


def _flatten(routes):
    return reduce(list.__iadd__, routes, [])


def _mount(path, routes):
    if path == "/":
        return routes
    else:
        return [Mount(path, routes=routes)]


def collect_routes(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Cannot find route from non-existent path: {path}")

    if path.is_dir():
        sys.path.append(str(path.parent))
        mod = importlib.import_module(path.stem)
        return {"/": collect_routes_from_module(mod)}

    else:
        glb = runpy.run_path(str(path))
        return {"/": glb["__app__"]}


@ovld
def compile_routes(path, routes: dict):
    routes = {pth.rstrip("/"): r for pth, r in routes.items()}
    if "/" not in routes:
        if "/index" in routes:
            routes["/"] = routes["/index"]
        else:
            routes["/"] = Index()
    return _mount(
        path,
        _flatten([compile_routes(path2, route) for path2, route in routes.items()]),
    )


@ovld
def compile_routes(path, mb: AbstractBear):  # noqa: F811
    return _mount(path, mb.routes())


@ovld
def compile_routes(path, obj: object):  # noqa: F811
    # TODO: better error when someone forgets @bear
    if callable(obj):
        cls = getattr(obj, "route_class", Route)
        route_parameters = getattr(obj, "route_parameters", {})
        return [cls(path, obj, **route_parameters)]
    else:
        raise TypeError(f"Cannot compile route for {path}: {obj}")


@ovld
def compile_routes(path, obj: Route):  # noqa: F811
    assert obj.path == path
    return [obj]


exclusions = {
    Path(starbear.__file__).parent,
    Path(starlette.__file__).parent,
}


@ovld
def collect_locations(routes: dict):  # noqa: F811
    rval = set()
    for subroutes in routes.values():
        rval.update(collect_locations(subroutes))
    return rval


@ovld
def collect_locations(b: AbstractBear):  # noqa: F811
    return collect_locations(getattr(b, "fn", None))


@ovld
def collect_locations(obj: object):  # noqa: F811
    if hasattr(obj, "__globals__"):
        loc = obj.__globals__.get("__file__", None)
        if not loc or any(Path(loc).is_relative_to(x) for x in exclusions):
            return set()
        return {Path(loc).parent}
    elif hasattr(obj, "__call__"):
        return collect_locations(obj.__call__)
    else:
        return set()
