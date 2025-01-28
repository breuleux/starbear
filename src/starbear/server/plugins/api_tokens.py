import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from apischema import ValidationError, deserialize, serialize
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse

from ...common import logger
from ..config import StarbearServerPlugin
from .permissions import make_config


class APITokensMiddleware(BaseHTTPMiddleware):
    """Authenticate users based on API tokens.

    Arguments:
        app: The application this middleware is added to.
    """

    def __init__(self, app, mapper):
        super().__init__(app)
        self.mapper = mapper

    async def dispatch(self, request, call_next):
        key = request.headers.get("X-API-KEY", None)
        if not key:
            return await call_next(request)
        user = self.mapper(key)
        if user:
            request.session["user"] = user
            return await call_next(request)
        else:
            return PlainTextResponse("Token is invalid or expired.", status_code=401)


@dataclass
class TokenData:
    name: str
    token: str
    email: str
    # expiry: Optional[datetime.datetime] = None
    # plain: bool = True


@dataclass
class APITokens(StarbearServerPlugin):
    # Configuration file in which the tokens are located
    file: Optional[Path] = None

    # Default tokens
    defaults: Optional[list[TokenData]] = None

    def cap_require(self):
        return ["session"]

    def cap_export(self):
        return ["email"]

    def get(self, key):
        if key in self.data:
            return {"email": self.data[key].email}

    def read(self):
        return self.config.read()

    def write(self, new_tokens, dry=False):
        deserialize(list[TokenData], self.config.parse(new_tokens))
        if self.config.write(new_tokens, dry=dry) and not dry:
            self.reset()

    def reset(self):
        self.config.reset()
        try:
            data = deserialize(list[TokenData], self.config.dict)
        except ValidationError as exc:
            logger.error("Could not read API tokens", exc_info=exc)
            data = []
        self.data = {token.token: token for token in data}

    def setup(self, server):
        assert self.file
        try:
            self.config = make_config(self.file, defaults=serialize(self.defaults or []))
        except json.JSONDecodeError as exc:
            sys.exit(
                f"ERROR decoding JSON: {exc}\n"
                f"Please verify if file '{self.file}' contains valid JSON."
            )
        self.reset()

        server.app.add_middleware(
            APITokensMiddleware,
            mapper=self.get,
        )
