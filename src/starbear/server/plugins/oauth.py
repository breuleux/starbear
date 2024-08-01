from dataclasses import dataclass, field

from authlib.integrations.starlette_client import OAuth
from hrepr import H
from starlette.config import Config
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import HTMLResponse, RedirectResponse

from ..config import StarbearServerPlugin


class OAuthMiddleware(BaseHTTPMiddleware):
    """Gate all routes behind OAuth.

    Arguments:
        app: The application this middleware is added to.
        oauth: The OAuth object.
        is_authorized: A function that takes (user, path) and returns whether the
            given user can access the given path. In all cases, the user must identify
            themselves through OAuth prior to this. The user's email is in `user["email"]`.
            The default function always returns True.
    """

    def __init__(self, app, oauth, is_authorized=lambda user, path: True):
        super().__init__(app)
        self.oauth = oauth
        self.router = app
        self.is_authorized = is_authorized
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
        if (path := request.url.path).startswith("/_/"):
            return await call_next(request)

        user = request.session.get("user")
        if not user:
            request.session["redirect_after_login"] = str(request.url)
            return RedirectResponse(url="/_/login")
        elif not self.is_authorized(user, path):
            content = H.body(
                H.h2("Forbidden"),
                H.p("User ", H.b(user["email"]), " cannot access this page."),
                H.a("Logout", href="/_/logout"),
            )
            return HTMLResponse(str(content), status_code=403)
        else:
            return await call_next(request)


@dataclass
class OAuth(StarbearServerPlugin):
    name: str = None
    server_metadata_url: str = None
    client_kwargs: dict = field(default_factory=dict)
    environ: dict = field(default_factory=dict)

    def setup(self, server):
        oauth_config = Config(environ=self.oauth.environ)
        oauth_module = OAuth(oauth_config)
        oauth_module.register(
            name=self.oauth.name,
            server_metadata_url=self.oauth.server_metadata_url,
            client_kwargs=self.oauth.client_kwargs,
        )
        server.app.add_middleware(
            OAuthMiddleware,
            oauth=oauth_module,
            # is_authorized=permissions,
        )
        # server.app.add_middleware(SessionMiddleware, secret_key=uuid4().hex)
