import os
import re
import shlex
import signal
import subprocess
from contextlib import contextmanager


@contextmanager
def serve(*args):
    # args = ["coverage", "run", "--include", "src", "-m", "starbear", "serve", "-p", "0", *map(str, args)]
    args = ["starbear", "serve", "-p", "0", *map(str, args)]
    cmd = shlex.join(args)
    print("Running command:", cmd)
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    try:
        while True:
            line = proc.stderr.readline().decode("utf8")
            print(line, end="")
            if m := re.match(string=line, pattern=r".*Serving at:.*(https?://[a-zA-Z0-9_.:]+)"):
                yield m.groups()[0]
                break
            if re.match(string=line, pattern=r".*(Error|Exception).*"):
                raise Exception(f"Command failed: '{cmd}'")
    finally:
        proc.send_signal(signal.SIGINT)
        proc.wait()
