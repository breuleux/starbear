import threading
import time
from contextlib import contextmanager
from pathlib import Path

import uvicorn


class ThreadableServer(uvicorn.Server):
    def install_signal_handlers(self):
        pass

    @contextmanager
    def run_in_thread(self):
        # Code taken from https://stackoverflow.com/questions/61577643/python-how-to-use-fastapi-and-uvicorn-run-without-blocking-the-thread
        thread = threading.Thread(target=self.run)
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
