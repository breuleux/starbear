import errno
import importlib
import ipaddress
import json
import os
import random
import socket
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any, Union

import gifnoc
from gifnoc import TaggedSubclass

from ..common import UsageError
from .find import collect_locations, collect_routes, collect_routes_from_module
from .reload import (
    BaseReloader,
    FullReloader,
    InertJuriggedReloader,
    InertReloader,
    JuriggedReloader,
)


@dataclass
class StarbearSSLConfig:
    # Whether SSL is enabled
    enabled: bool = False
    # SSL key file
    keyfile: Path = None
    # SSL certificate file
    certfile: Path = None


@dataclass
class StarbearServerPlugin:
    # Whether the plugin is enabled
    enabled: bool = True

    # Whether the plugin is required (if false, only include if needed by another plugin)
    required: bool = True

    def cap_require(self):
        return []

    def cap_export(self):
        return []

    def setup(self, server):
        pass


@dataclass
class StarbearServerBaseConfig:
    # Port to serve from
    port: int = 8000
    # Hostname to serve from
    host: str = "127.0.0.1"
    # Path to watch for changes with jurigged
    watch: Union[str, bool] = None
    # Run in development mode
    dev: bool = False
    # Automatically open browser
    open_browser: bool = False
    # Reloading methodology
    reload_mode: str = "jurigged"
    # SSL configuration
    ssl: StarbearSSLConfig = field(default_factory=StarbearSSLConfig)
    # Plugins
    plugins: dict[str, TaggedSubclass[StarbearServerPlugin]] = field(default_factory=dict)

    def __post_init__(self):
        override = os.environ.get("STARBEAR_RELOAD_OVERRIDE", None)
        if override:
            self.host, self.port = json.loads(override)
            self.open_browser = False

        if self.dev and not self.watch:
            self.watch = True
        if self.watch:
            self.dev = True

    @cached_property
    def socket(self):
        host = self.host
        if host == "127.255.255.255":
            # Generate a random loopback address (127.x.x.x)
            host = ipaddress.IPv4Address("127.0.0.1") + random.randrange(2**24 - 2)
            host = str(host)

        family = socket.AF_INET6 if ":" in host else socket.AF_INET

        sock = socket.socket(family=family)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            sock.bind((host, self.port))
        except OSError as exc:
            if self.host == "127.255.255.255" and exc.errno == errno.EADDRNOTAVAIL:
                # The full 127.x.x.x range may not be available on this system
                sock.bind(("localhost", self.port))
            else:
                raise
        return sock

    def get_reloader(self, server):
        if not self.dev:
            return InertReloader(server)
        elif self.reload_mode == "manual":
            return BaseReloader(server)
        elif self.reload_mode == "jurigged":
            return JuriggedReloader(server)
        elif self.reload_mode == "jurigged_noreload":
            return InertJuriggedReloader(server)
        else:
            return FullReloader(server)

    def get_locations(self):
        return []

    def get_routes(self):
        raise NotImplementedError("Please override get_routes()")


@dataclass
class StarbearServerConfig(StarbearServerBaseConfig):
    # Directory or script
    root: str = None
    # Name of the module to run
    module: Union[str, Any] = None
    # Field in the module representing the route(s)
    module_field: str = None
    # Explicitly given routes
    routes: dict = None

    def _process_module(self):
        if isinstance(self.module, str):
            if ":" in self.module:
                self.module, self.module_field = self.module.split(":")
            self.module = importlib.import_module(self.module)

    def get_locations(self):
        if self.root:
            locations = [self.root]

        elif self.module:
            self._process_module()
            locations = [Path(self.module.__file__).parent]

        elif self.routes:
            locations = list(collect_locations(self.routes))

        return [str(loc) for loc in locations]

    def get_routes(self):
        if ((self.root is not None) + (self.module is not None) + (self.routes is not None)) != 1:
            raise UsageError(
                "Either the root or module argument must be provided, or a dict of explicit routes."
            )

        if self.root:
            return collect_routes(self.root)

        elif self.module:
            self._process_module()
            return collect_routes_from_module(self.module, self.module_field)

        elif self.routes:
            return self.routes


config = gifnoc.define(
    field="starbear.server",
    model=StarbearServerConfig,
)
