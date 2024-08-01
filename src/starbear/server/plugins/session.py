from dataclasses import dataclass
from uuid import uuid4

from starlette.middleware.sessions import SessionMiddleware

from ..config import StarbearServerPlugin


@dataclass
class Session(StarbearServerPlugin):
    def cap_require(self):
        return []

    def cap_export(self):
        return ["session"]

    def setup(self, server):
        server.app.add_middleware(SessionMiddleware, secret_key=uuid4().hex)
