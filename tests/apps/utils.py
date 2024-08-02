import threading
import time
from contextlib import contextmanager
from functools import partial
from pathlib import Path

import gifnoc
import uvicorn


class ThreadableServer(uvicorn.Server):
    def install_signal_handlers(self):
        pass

    def run(self, config=None):
        with gifnoc.use(config or None):
            super().run()

    @contextmanager
    def run_in_thread(self, config=None):
        # Code taken from https://stackoverflow.com/questions/61577643/python-how-to-use-fastapi-and-uvicorn-run-without-blocking-the-thread
        thread = threading.Thread(target=partial(self.run, config))
        thread.start()
        try:
            while not self.started:
                time.sleep(1e-3)
            yield
        finally:
            self.should_exit = True
            thread.join()


def asset_getter(file):
    here = Path(file)
    locations = [here.parent / "common_assets", here.parent / (here.stem + "_assets")]

    def get(name):
        for location in locations:
            candidate = location / name
            if candidate.exists():
                return candidate
        else:
            raise FileNotFoundError(name)

    return get
