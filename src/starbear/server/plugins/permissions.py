import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Optional

from hrepr import H
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import HTMLResponse

from ...common import UsageError
from ..config import StarbearServerPlugin


class PermissionsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, is_authorized):
        super().__init__(app)
        self.router = app
        self.is_authorized = is_authorized

    async def dispatch(self, request, call_next):
        if (path := request.url.path).startswith("/_/"):
            return await call_next(request)

        user = request.session.get("user")
        if not self.is_authorized(user, path):
            content = H.body(
                H.h2("Forbidden"),
                H.p("User ", H.b(user["email"]), " cannot access this page."),
                H.a("Logout", href="/_/logout"),
            )
            return HTMLResponse(str(content), status_code=403)
        else:
            return await call_next(request)


@dataclass
class Permissions(StarbearServerPlugin):
    # Configuration file in which the permissions are located
    file: Optional[Path] = None

    # Default permissions to bootstrap the configuration file
    defaults: Optional[dict] = None

    def cap_require(self):
        return ["email"]

    def cap_export(self):
        return []

    def setup(self, server):
        if self.file:
            try:
                permissions = PermissionFile(self.file, defaults=self.defaults)
            except json.JSONDecodeError as exc:
                sys.exit(
                    f"ERROR decoding JSON: {exc}\n"
                    f"Please verify if file '{self.file}' contains valid JSON."
                )
        elif self.defaults:
            permissions = PermissionDict(self.defaults)
        else:
            raise UsageError("The permissions plugin should specify a file and/or defaults.")

        self.permissions = permissions
        server.app.add_middleware(PermissionsMiddleware, is_authorized=permissions)


class ConfigFile:
    def __init__(self, file, defaults=None):
        self.dict = None
        self.file = file
        if not self.file.exists():
            if defaults is None:
                raise FileNotFoundError(self.file)
            else:
                self.write(defaults)
        self.reset()

    def reset(self):
        self.dict = self.parse(self.read())

    def read(self):
        return self.file.read_text()

    def write(self, new_content, dry=False):
        if not isinstance(new_content, str):
            new_content = self.unparse(new_content)
        if dry:
            # Check that the new content is valid
            self.parse(new_content)
        else:
            if self.file.exists():
                previous = self.read()
            else:
                previous = self.unparse({})
            self.file.write_text(new_content)
            try:
                self.reset()
            except Exception:
                self.file.write_text(previous)
                self.reset()
                raise
        return True


class JSONFile(ConfigFile):
    def parse(self, content):
        return json.loads(content)

    def unparse(self, data):
        return json.dumps(data)


class YAMLFile(ConfigFile):
    def parse(self, content):
        import yaml

        return yaml.safe_load(content)

    def unparse(self, data):
        import yaml

        return yaml.safe_dump(data)


extensions_map = {
    ".json": JSONFile,
    ".yaml": YAMLFile,
    ".yml": YAMLFile,
}


def make_config(config_file, defaults=None):
    config_file = Path(config_file)
    suffix = config_file.suffix
    cls = extensions_map.get(suffix, None)
    if cls is None:
        raise UsageError(f"Unknown config file extension: {suffix}")
    else:
        return cls(config_file, defaults=defaults)


def parse_config():
    return make_config().dict


class PermissionDict:
    def __init__(self, permissions):
        self.permissions = permissions
        self.reset()

    def reset(self):
        self.cache = defaultdict(dict)
        self.wild = defaultdict(list)
        for path, allowed in self.permissions.items():
            if path == "/":
                path = ("",)
            else:
                path = tuple(path.split("/"))
            for user in allowed:
                if "*" in user:
                    self.wild[path].append(user)
                else:
                    self.cache[path][user] = True

    def __call__(self, user, path):
        path, *_ = path.split("!", 1)
        path = path.removesuffix("/")
        if path == "/":
            parts = ("",)
        else:
            parts = tuple(path.split("/"))
        email = user["email"]
        partials = [(*parts[: i + 1], "**") for i in range(len(parts))]
        to_check = [parts, *partials]
        for current in to_check:
            cache = self.cache[current]
            if email in cache:
                if cache[email]:
                    return True
            else:
                for wild in self.wild[current]:
                    if fnmatch(email, wild):
                        cache[email] = True
                        return True
                else:
                    cache[email] = False
        return False


class PermissionFile(PermissionDict):
    def __init__(self, permissions_file, defaults=None):
        self.file = make_config(permissions_file, defaults=defaults)
        super().__init__(self.file.dict)

    def reset(self):
        self.permissions = self.file.dict
        super().reset()

    def read(self):
        return self.file.read()

    def write(self, new_permissions, dry=False):
        if self.file.write(new_permissions, dry=dry) and not dry:
            self.reset()
