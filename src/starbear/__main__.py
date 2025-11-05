import sys
from dataclasses import dataclass

import gifnoc
from serieux import TaggedUnion

from .common import UsageError
from .server.config import config as server_config


@dataclass
class Serve:
    """Start a Starbear server."""

    # Directory or script
    # [positional]
    path: str = None

    # Reference to the module to run
    # [alias: -m]
    module: str = None

    # Port to serve from
    # [alias: -p]
    port: int = None

    # Hostname to serve from
    host: str = None

    # Path to watch for changes with jurigged
    watch: str = None

    # Run in development mode
    # [alias: -d]
    dev: bool = None

    # Automatically open browser
    browser: bool = None

    # Reloading methodology
    reload_mode: str = None

    # SSL key file
    ssl_keyfile: str = None

    # SSL certificate file
    ssl_certfile: str = None

    def __call__(self):
        cfg = {
            "starbear.server.root": self.path,
            "starbear.server.module": self.module,
            "starbear.server.port": self.port,
            "starbear.server.host": self.host,
            "starbear.server.ssl.keyfile": self.ssl_keyfile,
            "starbear.server.ssl.certfile": self.ssl_certfile,
            "starbear.server.dev": self.dev,
            "starbear.server.reload_mode": self.reload_mode,
            "starbear.server.watch": self.watch,
            "starbear.server.open_browser": self.browser,
        }
        cfg = {k: v for k, v in cfg.items() if v is not None}

        gifnoc.add_overlay(cfg)

        from .server.serve import StarbearServer

        try:
            server = StarbearServer(server_config)
            server.run()
        except UsageError as exc:  # pragma: no cover
            exit(f"ERROR: {exc}")
        except FileNotFoundError as exc:  # pragma: no cover
            exit(f"ERROR: File not found: {exc}")


def main(argv=None):
    sys.path.append(".")

    command = gifnoc.cli(
        TaggedUnion[Serve],
        mapping={"starbear.dev.debug_mode": "--debug"},
        argv=argv or sys.argv[1:],
    )
    command()


if __name__ == "__main__":  # pragma: no cover
    main()
