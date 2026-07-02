import fcntl
import subprocess, json
from contextlib import contextmanager
from .config import ROOT, run_dir

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

def _git(args):
    return subprocess.run(["git"] + args, cwd=str(ROOT), capture_output=True, text=True)

def _head_has_news(date):
    return _git(["cat-file", "-e", f"HEAD:content/news/{date}.md"]).returncode == 0

def _publish_state(date):
    p = run_dir(date) / "publish.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None

def decide_action(date, *, force):
    # git-authoritative: HEAD having the day's news file is the reliable "published locally"
    # signal (survives runs/ scratch wipe). publish.json.pushed only optimizes skip vs re-push.
    if force:
        return "full"
    if _head_has_news(date):
        st = _publish_state(date) or {}
        return "skip" if st.get("pushed") is True else "push_only"
    return "full"

STAGES = ["collect", "select", "stage", "publish"]
_ARTIFACT = {"collect": "candidates.json", "select": "selection.json",
             "stage": "generation.json", "publish": "publish.json"}

def _default_runner(name, date):
    return subprocess.run(["python3", "-m", f"nbs.{name}", "--date", date],
                          cwd=str(ROOT)).returncode

def _stage_ok(name, date, rc):
    if rc != 0:
        return False, f"{name} exited {rc}"
    p = run_dir(date) / _ARTIFACT[name]
    if not p.exists():
        return False, f"{name} rc0 but {_ARTIFACT[name]} missing"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        return False, f"{name} artifact unreadable: {e}"
    if name == "stage" and data.get("status") not in ("ok", "skip-empty"):
        return False, f"stage status {data.get('status')!r}"
    return True, ""
