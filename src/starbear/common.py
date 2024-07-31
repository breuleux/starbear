import sys
from pathlib import Path


def here(depth=1):
    fr = sys._getframe(depth)
    filename = fr.f_code.co_filename
    return Path(filename).parent


class UsageError(Exception):
    pass
