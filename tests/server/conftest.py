from pathlib import Path
from shutil import copytree

import pytest


@pytest.fixture
def clone(tmpdir):
    def _clone(pth):
        dest = tmpdir / pth.name
        copytree(src=pth, dst=dest)
        return Path(str(dest))

    return _clone
