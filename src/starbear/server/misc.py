from starlette.routing import Route


def simple_route(fn=None, *, route_class=Route, **kwargs):
    def wrap(fn):
        fn.route_class = route_class
        fn.route_parameters = kwargs
        return fn

    return wrap if fn is None else wrap(fn)
