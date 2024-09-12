from starlette.responses import HTMLResponse
from starlette.routing import Route

from starbear import H, bear
from starbear.server.misc import simple_route


@bear
async def jupiter(page):
    """Planet Jupiter"""
    page.print(H.h1("JUPITER!"))


@bear
async def titan(page):
    """Moon titan"""
    page.print(H.h1("TITAN!"))


@simple_route
async def europa(request):
    return HTMLResponse("<h1>EUROPA!</h1>")


async def ganymede(request):
    return HTMLResponse("<h1>GANYMEDE!</h1>")


__app__ = {
    "/index": jupiter,
    "/titan": titan,
    "/europa": europa,
    "/ganymede": Route("/ganymede", endpoint=ganymede),
}
