from dataclasses import dataclass, field

from authlib.integrations.starlette_client import OAuth as OAuthClient
from starlette.config import Config
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

from ..config import StarbearServerPlugin


class OAuthMiddleware(BaseHTTPMiddleware):
    """Gate all routes behind OAuth.

    Arguments:
        app: The application this middleware is added to.
        oauth: The OAuth object.
    """

    def __init__(self, app, oauth):
        super().__init__(app)
        self.oauth = oauth
        self.router = app
        while not hasattr(self.router, "add_route"):
            self.router = self.router.app
        self.add_routes()

    def add_routes(self):
        self.router.add_route("/_/login", self.route_login)
        self.router.add_route("/_/logout", self.route_logout)
        self.router.add_route("/_/auth", self.route_auth, name="auth")

    async def route_login(self, request):
        redirect_uri = request.url_for("auth")
        return await self.oauth.google.authorize_redirect(request, str(redirect_uri))

    async def route_auth(self, request):
        token = await self.oauth.google.authorize_access_token(request)
        user = token.get("userinfo")
        if user:
            request.session["user"] = user
        red = request.session.get("redirect_after_login", "/")
        return RedirectResponse(url=red)

    async def route_logout(self, request):
        request.session.pop("user", None)
        return RedirectResponse(url="/")

    async def dispatch(self, request, call_next):
        if request.url.path.startswith("/_/"):
            return await call_next(request)

        user = request.session.get("user")
        if not user:
            request.session["redirect_after_login"] = str(request.url)
            return RedirectResponse(url="/_/login")
        else:
            return await call_next(request)


@dataclass
class OAuth(StarbearServerPlugin):
    name: str = None
    server_metadata_url: str = None
    client_kwargs: dict = field(default_factory=dict)
    environ: dict = field(default_factory=dict)

    def cap_require(self):
        return ["session"]

    def cap_export(self):
        return ["email"]

    def setup(self, server):
        oauth_config = Config(environ=self.environ)
        oauth_module = OAuthClient(oauth_config)
        oauth_module.register(
            name=self.name,
            server_metadata_url=self.server_metadata_url,
            client_kwargs=self.client_kwargs,
        )
        server.app.add_middleware(
            OAuthMiddleware,
            oauth=oauth_module,
        )
