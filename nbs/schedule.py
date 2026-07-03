import os, subprocess, shutil
from pathlib import Path
from . import config

def _git(root, *args):
    return subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True)

def _git_credentials_present():
    return (Path.home() / ".git-credentials").exists()

def _display_present():
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))

def _writeset(date):
    # EXACTLY mirror publish.date_writeset (nbs/publish.py:98-106) — the set rollback touches.
    # Broader (e.g. `{date}*`) would abort today over a same-date-PREFIX non-write-set draft;
    # narrower would miss a file rollback clobbers. posts are `{date}-*.md`; news/usecase/ax are
    # the exact `{date}.md`; published.csv (date's rows rewritten by rollback) is always included.
    return [f"content/posts/{date}-*.md", f"content/news/{date}.md",
            f"content/usecase/{date}.md", f"content/ax/{date}.md", "data/published.csv"]

def preflight(root=config.ROOT, date=None):
    date = date or "0000-00-00"   # caller (run_tick) passes the tick date; guard against None
    # HARD (only what orchestrate can't cleanly self-handle):
    # 1) THIS date's write-set must be clean — orchestrate's rollback `git checkout` would else
    #    destroy the user's uncommitted changes (spec §172).
    dirty = _git(root, "status", "--porcelain", "--", *_writeset(date)).stdout.strip()
    if dirty:
        return {"ok": False, "reason": f"write-set dirty: {dirty.splitlines()[0]}", "reddit_ok": False}
    # 2) git identity + credentials (commit/push preconditions; push_only path needs these too).
    name = _git(root, "config", "user.name").stdout.strip()
    email = _git(root, "config", "user.email").stdout.strip()
    if not (name and email):
        return {"ok": False, "reason": "git identity missing", "reddit_ok": False}
    if not _git_credentials_present():
        return {"ok": False, "reason": "~/.git-credentials missing", "reddit_ok": False}
    # SOFT (warn, never abort): a real hugo/deps miss is caught cleanly by orchestrate's
    # per-stage rc, and push_only/skip recovery doesn't need hugo — so these never gate the tick.
    if not shutil.which("hugo"):
        print("[preflight] warn: hugo not on PATH (a full run's build-verify would fail this tick)")
    # display absence only disables Reddit (publish proceeds RSS+X).
    return {"ok": True, "reason": "", "reddit_ok": _display_present()}
