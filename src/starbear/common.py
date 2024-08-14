import logging
import sys
import traceback
from pathlib import Path


def _here(depth):
    fr = sys._getframe(depth)
    filename = fr.f_code.co_filename
    return Path(filename).parent


class UsageError(Exception):
    pass


class StarbearHandler(logging.StreamHandler):
    def format(self, record):
        def _brack(s):
            return f"[\033[36m{s}\033[0m]" if s else ""

        process = getattr(record, "proc", None)
        user = getattr(record, "user", None)
        tb = getattr(record, "traceback", None)
        colors = {
            "INFO": "32",
            "WARNING": "33",
            "ERROR": "31",
        }
        color = colors.get(record.levelname, "95")
        prefix = f"\033[{color}m{record.levelname}\033[0m:   {_brack(record.name)}{_brack(process)}{_brack(user)}"
        msg = record.msg
        if tb:
            msg += "\n" + traceback.format_exc()
        if "\n" in msg:
            lines = f"\n\033[{color}m>\033[0m ".join(msg.split("\n"))
            return f"{prefix} {lines}"
        else:
            return f"{prefix} {msg}"


logger = logging.getLogger("starbear")
logger.setLevel(level=logging.INFO)
logger.addHandler(StarbearHandler(sys.stderr))


def __getattr__(attr):
    if attr == "here":
        return _here(2)

    raise AttributeError(attr)
