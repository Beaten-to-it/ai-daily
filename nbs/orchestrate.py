import fcntl
from contextlib import contextmanager
from .config import ROOT

class Busy(Exception):
    pass

@contextmanager
def _lock():
    # fd-based flock: exclusive, non-blocking; kernel auto-releases on process death
    # (crash-safe — a killed run never leaves a stale lock, unlike a bare pidfile).
    lock_path = ROOT / ".orchestrate.lock"
    f = open(lock_path, "w")
    try:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise Busy("another orchestrate run holds the lock")
        yield
    finally:
        f.close()   # closing the fd releases the flock
