import argparse
import sys

import gifnoc
from gifnoc import Command, Option

from .common import UsageError
from .config import config
from .server.config import config as server_config


def main(argv=None):
    sys.path.append(".")
    with gifnoc.cli(
        argparser=argparse.ArgumentParser(description="Start a Starbear application."),
        options=Command(
            mount="starbear",
            commands={
                "serve": Command(
                    mount="starbear.server",
                    options={
                        "starbear.dev.debug_mode": "--debug",
                        ".root": "--root",
                        ".module": Option(aliases=["--module", "-m"]),
                        ".port": Option(aliases=["--port", "-p"]),
                        ".host": "--host",
                        ".ssl.keyfile": "--ssl-keyfile",
                        ".ssl.certfile": "--ssl-certfile",
                        ".dev": Option(aliases=["--dev", "-d"]),
                        ".reload_mode": "--reload-mode",
                        ".watch": "--watch",
                        ".open_browser": "--browser",
                    },
                ),
            },
        ),
        argv=sys.argv[1:] if argv is None else argv,
    ):
        if config.command == "serve":
            from .server.serve import StarbearServer

            try:
                server = StarbearServer(server_config)
                server.run()
            except UsageError as exc:  # pragma: no cover
                exit(f"ERROR: {exc}")
            except FileNotFoundError as exc:  # pragma: no cover
                exit(f"ERROR: File not found: {exc}")
        else:  # pragma: no cover
            assert False


if __name__ == "__main__":  # pragma: no cover
    main()
