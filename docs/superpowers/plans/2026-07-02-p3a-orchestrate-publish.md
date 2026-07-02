# P3a — Orchestrator + Push & Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One command runs a day's full pipeline (collect→select→stage→publish) then pushes to `origin/main` to trigger the Actions→Pages deploy — day-level idempotent, crash-safe, with no email/scheduler (those are later P3 sub-projects).

**Architecture:** New orchestrator `nbs/orchestrate.py` drives the existing per-stage CLIs (`python3 -m nbs.{collect,select,stage,publish}`) as **subprocesses**, judging each by exit code AND its artifact JSON. A **git-authoritative** idempotency guard (`git cat-file -e HEAD:content/news/<date>.md`) decides skip / push-only-recovery / full-pipeline. Push happens only when publish succeeded; push failure is classified via `git ls-remote` (not stderr) into a retryable `push_pending` vs a fatal `push_rejected`. A run-level `run.json` manifest + exit code are the only outputs P3c/P3d consume. Existing stage code is unmodified; the orchestrator owns the post-push `pushed` flag it writes into `publish.json`.

**Tech Stack:** Python 3 (stdlib only — `subprocess`, `fcntl`, `json`, `tempfile`, `os`, `argparse`, `datetime`, `contextlib`), git ≥2.23, pytest. No new deps.

## Global Constraints

- `python3` only (no bare `python`). **stdlib only** — no new dependency.
- Existing stage modules (`nbs/collect.py`, `nbs/select.py`, `nbs/stage.py`, `nbs/publish.py`) are **NOT modified** by P3a. The orchestrator is a pure driver.
- P3a pushes to `origin main` (Pages source = Actions from `main`, per P1). It does **NOT** send email or run on a schedule (P3b/P3c/P3d).
- **Date is a path component** — validate `date` as `YYYY-MM-DD` before any fs/subprocess use (reuse the P2c pattern; `nbs/publish.py` already has `_DATE_RE`).
- Build/verify/subprocess commands never wrapped in a pipe (exit code must survive) — see `[[2026-07-01-pipe-hides-build-failure]]`.
- **Idempotency invariant:** a day already published-and-pushed re-runs as a no-op (`skipped`); a day published-locally-but-not-pushed re-runs as **push-only** (never regenerates — `claude -p` is non-deterministic, so re-generating would create a divergent edition). `--force` is the only path to a forced full re-publish.
- **origin/main invariant:** only this driver writes `origin/main`. Divergence (something else pushed) → `push_rejected`, fatal, not retried into the void.
- TDD: failing test first, minimal impl, commit per task. Every commit message ends with the Co-Authored-By + Claude-Session trailer.

**Contract consumed (existing stage artifacts, all under `runs/<date>/`, gitignored scratch):**
- `nbs.collect --date <d>` → `candidates.json` (JSON list). Empty list is NOT failure. rc≠0 = failure.
- `nbs.select --date <d>` → `selection.json` `{date,items,selected_count,...}`. `selected_count==0` is NOT failure (writes the file, rc 0). Abort (schema/claude fail) = uncaught exception → rc≠0, file not written.
- `nbs.stage --date <d>` → `generation.json` `{date,status(ok|skip-empty),...}` (+ internal `staging/`, which stage rebuilds each run; the orchestrator reads only `generation.json`). rc≠0 = failure.
- `nbs.publish --date <d>` → `publish.json` `{date,status(published|held|failed),commit_sha,...}`. **publish's process exits 0 even for held/failed** — read `publish.json.status`, never publish's exit code.

**Produced (new):**
- `runs/<date>/run.json` = `{date, run_id, started_at, status, stages:{collect,select,stage,publish,push:{status,reason}}, reason, force}`, `status ∈ {published, skipped, held, failed, push_pending, push_rejected, busy}`.
- `runs/<date>/publish.json` gains `pushed`(bool) + `deployed_sha`(str) after a verified push (orchestrator writes this atomically; publish.py unchanged).

---

### Task 1: Crash-safe single-run lock

**Files:**
- Create: `nbs/orchestrate.py`
- Test: `tests/test_orchestrate.py` (new)

**Interfaces:**
- Produces: `_lock()` — context manager. Acquires an exclusive non-blocking `fcntl.flock` on `ROOT/.orchestrate.lock`. Raises `Busy` if another holder exists. Auto-released by the kernel on process death (crash-safe).
- Produces: `Busy(Exception)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_orchestrate.py (new)
import pytest
from nbs import orchestrate, config

def test_lock_is_exclusive(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(orchestrate, "ROOT", tmp_path)
    with orchestrate._lock():
        with pytest.raises(orchestrate.Busy):
            with orchestrate._lock():
                pass
    # released after the outer block — re-acquirable
    with orchestrate._lock():
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_orchestrate.py::test_lock_is_exclusive -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nbs.orchestrate'`

- [ ] **Step 3: Write minimal implementation**

```python
# nbs/orchestrate.py (new)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_orchestrate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nbs/orchestrate.py tests/test_orchestrate.py
git commit -m "feat(p3a): crash-safe single-run flock

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VPUtXZyTzXtKwJfkZG3e5H"
```

---

### Task 2: Git-authoritative idempotency guard

**Files:**
- Modify: `nbs/orchestrate.py`
- Test: `tests/test_orchestrate.py`

**Interfaces:**
- Consumes: `_lock`, `Busy`.
- Produces: `_git(args) -> subprocess.CompletedProcess` (cwd=ROOT, captured text).
- Produces: `_head_has_news(date) -> bool` — `git cat-file -e HEAD:content/news/<date>.md` succeeds.
- Produces: `_publish_state(date) -> dict | None` — parsed `runs/<date>/publish.json` or None.
- Produces: `decide_action(date, *, force) -> str` ∈ `{"full", "push_only", "skip"}`. `force` → `"full"`. Else: if `_head_has_news`: `"skip"` when `publish.json.pushed is True`, else `"push_only"`. If not head_has_news: `"full"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_orchestrate.py (append)
import subprocess, json
from pathlib import Path

def _git_in(args, cwd): return subprocess.run(["git"]+args, cwd=str(cwd), capture_output=True, text=True)

def _init_repo(tmp_path, monkeypatch):
    # ROOT is a SUBDIR of tmp_path so the bare remote / clone helpers can live OUTSIDE the
    # worktree (else `git add -A` in ROOT would commit the bare remote's internals — Codex R1).
    root = tmp_path/"repo"; root.mkdir()
    monkeypatch.setattr(config, "ROOT", root)
    monkeypatch.setattr(orchestrate, "ROOT", root)
    monkeypatch.setattr(orchestrate, "run_dir", lambda d: root/"runs"/d)
    _git_in(["init","-q"], root); _git_in(["config","user.email","t@t"], root); _git_in(["config","user.name","t"], root)
    (root/"content"/"news").mkdir(parents=True)
    (root/".gitignore").write_text("runs/\n.orchestrate.lock\n", encoding="utf-8")
    _git_in(["add","-A"], root); _git_in(["commit","-qm","init"], root)
    return root

def _publish_news(root, date, pushed=None):
    (root/"content"/"news").mkdir(parents=True, exist_ok=True)
    (root/"content"/"news"/f"{date}.md").write_text("x\n", encoding="utf-8")
    _git_in(["add","-A"], root); _git_in(["commit","-qm",f"publish {date}"], root)
    d = root/"runs"/date; d.mkdir(parents=True, exist_ok=True)
    pj = {"date": date, "status": "published"}
    if pushed is not None: pj["pushed"] = pushed
    (d/"publish.json").write_text(json.dumps(pj), encoding="utf-8")

def test_decide_action_full_when_never_published(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    assert orchestrate.decide_action("2026-07-01", force=False) == "full"

def test_decide_action_skip_when_pushed(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); _publish_news(root, "2026-07-01", pushed=True)
    assert orchestrate.decide_action("2026-07-01", force=False) == "skip"

def test_decide_action_pushonly_when_published_not_pushed(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); _publish_news(root, "2026-07-01", pushed=False)
    assert orchestrate.decide_action("2026-07-01", force=False) == "push_only"

def test_decide_action_pushonly_when_scratch_wiped(tmp_path, monkeypatch):
    # R2 BLOCK: news committed to HEAD but publish.json gone (runs/ wiped) -> push_only, NOT full
    root=_init_repo(tmp_path, monkeypatch); _publish_news(root, "2026-07-01", pushed=None)
    (root/"runs"/"2026-07-01"/"publish.json").unlink()
    assert orchestrate.decide_action("2026-07-01", force=False) == "push_only"

def test_decide_action_force_is_always_full(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); _publish_news(root, "2026-07-01", pushed=True)
    assert orchestrate.decide_action("2026-07-01", force=True) == "full"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_orchestrate.py::test_decide_action_pushonly_when_scratch_wiped -v`
Expected: FAIL — `module 'nbs.orchestrate' has no attribute 'decide_action'`

- [ ] **Step 3: Write minimal implementation**

```python
# nbs/orchestrate.py — add imports at top
import subprocess, json
from .config import ROOT, run_dir

# add functions
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_orchestrate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nbs/orchestrate.py tests/test_orchestrate.py
git commit -m "feat(p3a): git-authoritative idempotency guard (head_has_news primary)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VPUtXZyTzXtKwJfkZG3e5H"
```

---

### Task 3: Stage runner + per-stage success validation

**Files:**
- Modify: `nbs/orchestrate.py`
- Test: `tests/test_orchestrate.py`

**Interfaces:**
- Produces: `STAGES = ["collect", "select", "stage", "publish"]`.
- Produces: `_default_runner(name, date) -> int` — `subprocess.run(["python3","-m",f"nbs.{name}","--date",date], cwd=ROOT).returncode`.
- Produces: `_stage_ok(name, date, rc) -> (bool, str)` — validates a stage's outcome by rc AND its artifact JSON. Rules: rc≠0 → (False, reason). collect → `candidates.json` must exist. select → `selection.json` must exist. stage → `generation.json.status ∈ {ok, skip-empty}`. publish → not validated here (its outcome is read separately from `publish.json.status`, since publish exits 0 even for held/failed); `_stage_ok("publish", …)` returns (True, "") when rc==0 and `publish.json` exists. Missing/corrupt artifact after rc0 → (False, reason).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_orchestrate.py (append)
def _mk(root, date, name, payload):
    d = root/"runs"/date; d.mkdir(parents=True, exist_ok=True)
    (d/f"{ {'collect':'candidates','select':'selection','stage':'generation','publish':'publish'}[name] }.json"
     ).write_text(json.dumps(payload), encoding="utf-8")

def test_stage_ok_rejects_nonzero_rc(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    ok, _ = orchestrate._stage_ok("collect", "2026-07-01", 1)
    assert ok is False

def test_stage_ok_collect_needs_artifact(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    ok, _ = orchestrate._stage_ok("collect", "2026-07-01", 0)   # rc0 but no candidates.json
    assert ok is False
    _mk(root, "2026-07-01", "collect", [])
    assert orchestrate._stage_ok("collect", "2026-07-01", 0)[0] is True   # empty list is OK

def test_stage_ok_stage_status(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    _mk(root, "2026-07-01", "stage", {"date":"2026-07-01","status":"skip-empty"})
    assert orchestrate._stage_ok("stage", "2026-07-01", 0)[0] is True
    _mk(root, "2026-07-01", "stage", {"date":"2026-07-01","status":"weird"})
    assert orchestrate._stage_ok("stage", "2026-07-01", 0)[0] is False

def test_default_runner_shape(monkeypatch):
    calls = {}
    def fake_run(argv, cwd=None, **kw):
        calls["argv"]=argv; calls["cwd"]=cwd
        class R: returncode=0
        return R()
    monkeypatch.setattr(orchestrate.subprocess, "run", fake_run)
    rc = orchestrate._default_runner("collect", "2026-07-01")
    assert rc==0 and calls["argv"]==["python3","-m","nbs.collect","--date","2026-07-01"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_orchestrate.py::test_stage_ok_stage_status -v`
Expected: FAIL — `module 'nbs.orchestrate' has no attribute '_stage_ok'`

- [ ] **Step 3: Write minimal implementation**

```python
# nbs/orchestrate.py — add
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_orchestrate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nbs/orchestrate.py tests/test_orchestrate.py
git commit -m "feat(p3a): stage runner + per-stage success validation (rc AND artifact)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VPUtXZyTzXtKwJfkZG3e5H"
```

---

### Task 4: Push + ls-remote non-ff classification + pushed marker

**Files:**
- Modify: `nbs/orchestrate.py`
- Test: `tests/test_orchestrate.py`

**Interfaces:**
- Produces: `_mark_pushed(date, sha)` — atomically set `pushed=true`+`deployed_sha=sha` in `runs/<date>/publish.json` (create a minimal `{date,status:published,pushed,deployed_sha}` if the file is absent, e.g. scratch wiped). temp + `os.replace`.
- Produces: `_classify_push_failure(head) -> (status, sha|None, reason)` — query `git ls-remote origin refs/heads/main`; empty/failed → `("push_pending", None, …)`; remote SHA == head → `("published", sha, …)` (push actually landed); remote SHA NOT an ancestor of HEAD → `("push_rejected", None, …)` (divergence); else → `("push_pending", None, …)` (remote behind → transient). No stderr parsing.
- Produces: `_push(date) -> (status, sha|None, reason)` — `git push origin main`; on success verify `git rev-parse origin/main == HEAD`, `_mark_pushed`, return `("published", sha, "")`. On failure classify via `_classify_push_failure(head)`; if that resolves to `published` (remote already at HEAD), `_mark_pushed` and return published.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_orchestrate.py (append)
import os

def _init_repo_with_remote(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)           # root = tmp_path/repo
    bare = tmp_path/"remote.git"                      # SIBLING of root — outside the worktree
    _git_in(["init","--bare","-q",str(bare)], tmp_path)
    _git_in(["remote","add","origin",str(bare)], root)
    _git_in(["branch","-M","main"], root)
    return root, bare

def test_push_success_marks_pushed(tmp_path, monkeypatch):
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    _publish_news(root, "2026-07-01", pushed=False)
    status, sha, _ = orchestrate._push("2026-07-01")
    assert status=="published" and sha
    st = json.loads((root/"runs"/"2026-07-01"/"publish.json").read_text())
    assert st["pushed"] is True and st["deployed_sha"]==sha

def test_push_rejected_on_divergence(tmp_path, monkeypatch):
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    # seed origin/main with an unrelated commit so local push is non-fast-forward
    other = tmp_path/"other"; _git_in(["clone","-q",str(bare),str(other)], tmp_path)
    _git_in(["config","user.email","o@o"], other); _git_in(["config","user.name","o"], other)
    (other/"x.txt").write_text("o\n"); _git_in(["add","-A"], other)
    _git_in(["commit","-qm","other"], other); _git_in(["branch","-M","main"], other); _git_in(["push","-q","origin","main"], other)
    _publish_news(root, "2026-07-01", pushed=False)
    status, sha, _ = orchestrate._push("2026-07-01")
    assert status=="push_rejected" and sha is None

def test_mark_pushed_creates_when_absent(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    orchestrate._mark_pushed("2026-07-01", "deadbeef")
    st = json.loads((root/"runs"/"2026-07-01"/"publish.json").read_text())
    assert st["pushed"] is True and st["deployed_sha"]=="deadbeef" and st["status"]=="published"

def test_classify_push_failure_discriminates(tmp_path, monkeypatch):
    # discriminates the merge-base DIRECTION: a remote that is BEHIND (ancestor of HEAD) must be
    # push_pending, not push_rejected. Reversing the is-ancestor args would break this case.
    root=_init_repo(tmp_path, monkeypatch)
    orig = orchestrate._git
    def stub(stdout):
        def g(args):
            if args[:2]==["ls-remote","origin"]:
                return type("R",(),{"returncode":0,"stdout":stdout})()
            return orig(args)
        monkeypatch.setattr(orchestrate, "_git", g)
    A=_git_in(["rev-parse","HEAD"], root).stdout.strip()
    (root/"b").write_text("b"); _git_in(["add","-A"], root); _git_in(["commit","-qm","B"], root)
    C=_git_in(["rev-parse","HEAD"], root).stdout.strip()
    stub(f"{C}\trefs/heads/main\n"); assert orchestrate._classify_push_failure(C)[0]=="published"     # equal
    stub(f"{A}\trefs/heads/main\n"); assert orchestrate._classify_push_failure(C)[0]=="push_pending"  # behind (direction!)
    stub("0"*40+"\trefs/heads/main\n"); assert orchestrate._classify_push_failure(C)[0]=="push_rejected"  # diverged
    stub(""); assert orchestrate._classify_push_failure(C)[0]=="push_pending"                          # empty/unreachable
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_orchestrate.py::test_push_rejected_on_divergence -v`
Expected: FAIL — `module 'nbs.orchestrate' has no attribute '_push'`

- [ ] **Step 3: Write minimal implementation**

```python
# nbs/orchestrate.py — add imports
import os, tempfile

def _mark_pushed(date, sha):
    p = run_dir(date) / "publish.json"
    st = _publish_state(date) or {"date": date, "status": "published"}
    st["pushed"] = True
    st["deployed_sha"] = sha
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except Exception:
        os.path.exists(tmp) and os.remove(tmp); raise

def _classify_push_failure(head):
    # classify a FAILED `git push` by querying the live remote (never parse git stderr).
    ls = _git(["ls-remote", "origin", "refs/heads/main"])
    if ls.returncode != 0 or not ls.stdout.strip():
        return "push_pending", None, "origin/main absent or ls-remote failed"
    remote_sha = ls.stdout.split()[0]
    if remote_sha == head:                       # push actually landed (client died post-update)
        return "published", remote_sha, "push rc!=0 but origin/main already equals HEAD"
    # non-fast-forward iff the remote tip is NOT an ancestor of our HEAD (origin diverged)
    if _git(["merge-base", "--is-ancestor", remote_sha, "HEAD"]).returncode != 0:
        return "push_rejected", None, f"origin/main diverged (remote {remote_sha[:12]} not ancestor of HEAD)"
    return "push_pending", None, "push failed but origin is behind (transient)"

def _push(date):
    # returns (status, sha_or_None, reason). status ∈ {published, push_pending, push_rejected}
    head = _git(["rev-parse", "HEAD"]).stdout.strip()
    if _git(["push", "origin", "main"]).returncode != 0:
        status, sha, reason = _classify_push_failure(head)
        if status == "published":                # remote already at HEAD → record it
            _mark_pushed(date, sha)
            return "published", sha, reason
        return status, None, reason
    if _git(["rev-parse", "origin/main"]).stdout.strip() != head:
        return "push_pending", None, "push reported success but origin/main did not advance"
    _mark_pushed(date, head)
    return "published", head, ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_orchestrate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nbs/orchestrate.py tests/test_orchestrate.py
git commit -m "feat(p3a): push + ls-remote non-ff classification + atomic pushed marker

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VPUtXZyTzXtKwJfkZG3e5H"
```

---

### Task 5: `run()` orchestration + run.json manifest

**Files:**
- Modify: `nbs/orchestrate.py`
- Test: `tests/test_orchestrate.py`

**Interfaces:**
- Consumes: `_lock`, `Busy`, `decide_action`, `_default_runner`, `_stage_ok`, `_publish_state`, `_push`, `run_dir`, `_DATE`.
- Produces: `_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")` (date validation).
- Produces: `run(date, *, force=False, no_push=False, runner=None, now=None) -> dict` — the `run.json` manifest (also written to `runs/<date>/run.json`). `runner` defaults to `_default_runner` (test seam). `now` defaults to `datetime.now(config.KST)` (test seam for `run_id`/`started_at`).
  - Flow: validate date → acquire `_lock` (Busy → `status="busy"`, no manifest write outside run_dir) → `action = decide_action` → `skip` returns `skipped` → `push_only` calls `_push` (no stages) → `full` runs `collect,select,stage` (fail-fast via `_stage_ok`), then `publish` (read `publish.json.status`: held/failed → no push), then if published and not `no_push` → `_push`. → assemble manifest, write `run.json`, return.
- Produces: `_STATUS_EXIT = {"published":0,"skipped":0,"held":1,"failed":1,"push_rejected":1,"push_pending":2,"busy":3}` (exit-code mapping used by `main`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_orchestrate.py (append)
from datetime import datetime

def _fixed_now(): return datetime(2026,7,1,9,0,0, tzinfo=config.KST)

def _fake_runner_factory(root, *, outcomes):
    # outcomes: dict stage-> ("ok"|"rc1"|"held"|"empty"). Writes the artifact a real stage would,
    # and for a successful publish, commits content/news/<date>.md so head_has_news becomes true.
    def runner(name, date):
        d = root/"runs"/date; d.mkdir(parents=True, exist_ok=True)
        o = outcomes.get(name, "ok")
        if name=="collect":
            (d/"candidates.json").write_text(json.dumps([] if o=="empty" else [{"url":"u"}])); return 0 if o!="rc1" else 1
        if name=="select":
            (d/"selection.json").write_text(json.dumps({"date":date,"items":[],"selected_count":0 if o=="empty" else 3})); return 0 if o!="rc1" else 1
        if name=="stage":
            (d/"generation.json").write_text(json.dumps({"date":date,"status":"skip-empty" if o=="empty" else "ok"})); return 0 if o!="rc1" else 1
        if name=="publish":
            if o=="rc1":                      # crashed publish: leave any stale publish.json, rc!=0
                return 1
            status = "held" if o=="held" else "published"
            (d/"publish.json").write_text(json.dumps({"date":date,"status":status,"commit_sha":"abc"}))
            if status=="published":
                (root/"content"/"news").mkdir(parents=True, exist_ok=True)
                (root/"content"/"news"/f"{date}.md").write_text("x\n")
                _git_in(["add","-A"], root); _git_in(["commit","-qm",f"pub {date}"], root)
            return 0
    return runner

def test_run_full_publishes_and_pushes(tmp_path, monkeypatch):
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    m = orchestrate.run("2026-07-01", runner=_fake_runner_factory(root, outcomes={}), now=_fixed_now())
    assert m["status"]=="published"
    assert m["stages"]["push"]["status"]=="published"
    st = json.loads((root/"runs"/"2026-07-01"/"publish.json").read_text())
    assert st["pushed"] is True
    assert (root/"runs"/"2026-07-01"/"run.json").exists() and m["run_id"] and m["started_at"]

def _spy_push(monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(orchestrate, "_push",
                        lambda date: (calls.__setitem__("n", calls["n"]+1) or ("published", "sha", "")))
    return calls

def test_run_held_does_not_push(tmp_path, monkeypatch):
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    pushes = _spy_push(monkeypatch)
    m = orchestrate.run("2026-07-01", runner=_fake_runner_factory(root, outcomes={"publish":"held"}), now=_fixed_now())
    assert m["status"]=="held" and m["stages"]["push"]["status"]=="skipped" and pushes["n"]==0

def test_run_publish_crash_not_reported_published(tmp_path, monkeypatch):
    # BLOCK: a stale publish.json{published} + a crashed publish (rc!=0) must be FAILED, never pushed
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    d = root/"runs"/"2026-07-01"; d.mkdir(parents=True, exist_ok=True)
    (d/"publish.json").write_text(json.dumps({"date":"2026-07-01","status":"published"}))  # stale from prior run
    pushes = _spy_push(monkeypatch)
    m = orchestrate.run("2026-07-01", runner=_fake_runner_factory(root, outcomes={"publish":"rc1"}), now=_fixed_now())
    assert m["status"]=="failed" and m["stages"]["publish"]["status"]=="failed" and pushes["n"]==0

def test_run_aborts_on_stage_failure(tmp_path, monkeypatch):
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    m = orchestrate.run("2026-07-01", runner=_fake_runner_factory(root, outcomes={"select":"rc1"}), now=_fixed_now())
    assert m["status"]=="failed" and m["stages"]["select"]["status"]=="failed"
    assert m["stages"]["stage"]["status"]=="skipped"   # never ran

def test_run_skips_when_already_pushed(tmp_path, monkeypatch):
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    orchestrate.run("2026-07-01", runner=_fake_runner_factory(root, outcomes={}), now=_fixed_now())  # publishes+pushes
    called = {"n":0}
    def spy(name, date): called["n"]+=1; return 0
    m = orchestrate.run("2026-07-01", runner=spy, now=_fixed_now())
    assert m["status"]=="skipped" and called["n"]==0   # no stage ran

def test_run_pushonly_recovers_without_regen(tmp_path, monkeypatch):
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    # simulate published-locally-but-not-pushed: commit news, publish.json pushed=false, origin empty
    _publish_news(root, "2026-07-01", pushed=False)
    called = {"n":0}
    def spy(name, date): called["n"]+=1; return 0
    m = orchestrate.run("2026-07-01", runner=spy, now=_fixed_now())
    assert m["status"]=="published" and called["n"]==0   # push-only, no regeneration
    assert json.loads((root/"runs"/"2026-07-01"/"publish.json").read_text())["pushed"] is True

def test_run_no_push_flag(tmp_path, monkeypatch):
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    pushes = _spy_push(monkeypatch)
    m = orchestrate.run("2026-07-01", runner=_fake_runner_factory(root, outcomes={}), no_push=True, now=_fixed_now())
    assert m["status"]=="published" and m["stages"]["push"]["status"]=="skipped" and pushes["n"]==0
    assert json.loads((root/"runs"/"2026-07-01"/"publish.json").read_text()).get("pushed") is None

def test_run_pushonly_respects_no_push(tmp_path, monkeypatch):
    # --no-push MUST be honored on the push_only recovery path too, else a dry-run smoke on a
    # published-locally-not-pushed day pushes to the real origin.
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    _publish_news(root, "2026-07-01", pushed=False)   # recovery state
    m = orchestrate.run("2026-07-01", runner=(lambda n, d: 0), no_push=True, now=_fixed_now())
    assert m["stages"]["push"]["status"]=="skipped"
    assert _git_in(["ls-remote","origin","refs/heads/main"], root).stdout.strip()==""   # NOT pushed

def test_run_rejects_bad_date(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    m = orchestrate.run("../evil", now=_fixed_now())
    assert m["status"]=="failed" and not (tmp_path/"evil").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_orchestrate.py::test_run_full_publishes_and_pushes -v`
Expected: FAIL — `module 'nbs.orchestrate' has no attribute 'run'`

- [ ] **Step 3: Write minimal implementation**

```python
# nbs/orchestrate.py — add imports
import re
from datetime import datetime
from . import config

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_STATUS_EXIT = {"published":0,"skipped":0,"held":1,"failed":1,
                "push_rejected":1,"push_pending":2,"busy":3}

def _blank_stages():
    return {s: {"status": "skipped", "reason": ""} for s in STAGES + ["push"]}

def _write_run(date, payload):
    (run_dir(date)).mkdir(parents=True, exist_ok=True)
    (run_dir(date)/"run.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

def run(date, *, force=False, no_push=False, runner=None, now=None):
    runner = runner or _default_runner
    now = now or datetime.now(config.KST)
    run_id = now.strftime("%Y%m%dT%H%M%S%z")
    started = now.isoformat()
    base = {"date": date, "run_id": run_id, "started_at": started,
            "status": "failed", "stages": _blank_stages(), "reason": "", "force": force}
    if not _DATE.fullmatch(date or ""):
        base["status"] = "failed"; base["reason"] = "invalid date (must be YYYY-MM-DD)"
        return base   # do NOT write run.json under an unvalidated path
    def finish(status, reason=""):
        base["status"] = status; base["reason"] = reason
        return _write_run(date, base)
    try:
        with _lock():
            action = decide_action(date, force=force)
            if action == "skip":
                return finish("skipped", "already published and pushed")
            if action == "push_only":
                if no_push:   # honor dry-run on the recovery path too (else smoke pushes to origin)
                    base["stages"]["push"] = {"status": "skipped", "reason": "--no-push"}
                    return finish("published", "already published locally (push skipped)")
                st, sha, reason = _push(date)
                base["stages"]["push"] = {"status": st, "reason": reason or "push-only recovery"}
                top = "re-pushed without regeneration" if st == "published" else f"push-only recovery failed: {reason}"
                return finish("published" if st == "published" else st, top)
            # action == "full"
            for name in STAGES:
                rc = runner(name, date)
                if name == "publish":
                    # publish exits 0 even for held/failed — but a CRASHED publish (rc!=0) must
                    # NOT be read as a stale prior publish.json{published}. Gate on rc+artifact first.
                    ok, reason = _stage_ok("publish", date, rc)
                    if not ok:
                        base["stages"]["publish"] = {"status": "failed", "reason": reason}
                        return finish("failed", f"publish: {reason}")
                    pj = _publish_state(date) or {}
                    pstatus = pj.get("status")
                    if pstatus not in ("published", "held", "failed"):
                        base["stages"]["publish"] = {"status": "failed", "reason": f"unknown publish status {pstatus!r}"}
                        return finish("failed", f"unknown publish status {pstatus!r}")
                    preason = pj.get("reason", "")   # publish.py records the held/failed cause here
                    base["stages"]["publish"] = {"status": pstatus, "reason": preason}
                    if pstatus != "published":
                        return finish(pstatus, preason or f"publish {pstatus}")   # held/failed -> no push
                    break
                ok, reason = _stage_ok(name, date, rc)
                base["stages"][name] = {"status": "ok" if ok else "failed", "reason": reason}
                if not ok:
                    return finish("failed", f"{name}: {reason}")
            if no_push:
                base["stages"]["push"] = {"status": "skipped", "reason": "--no-push"}
                return finish("published", "published (push skipped)")
            st, sha, reason = _push(date)
            base["stages"]["push"] = {"status": st, "reason": reason}
            return finish("published" if st == "published" else st, reason)
    except Busy:
        base["status"] = "busy"; base["reason"] = "another run in progress"
        return base   # do not clobber the other run's run.json
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_orchestrate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nbs/orchestrate.py tests/test_orchestrate.py
git commit -m "feat(p3a): run() orchestration (guard->stages->publish-status->push) + run.json

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VPUtXZyTzXtKwJfkZG3e5H"
```

---

### Task 6: CLI `main()` — default today (KST), `--force`, `--no-push`, exit codes

**Files:**
- Modify: `nbs/orchestrate.py`
- Test: `tests/test_orchestrate.py`

**Interfaces:**
- Produces: `_today() -> str` — `datetime.now(config.KST).strftime("%Y-%m-%d")`.
- Produces: `main(argv=None) -> int` — argparse (`--date` default `_today()`, `--force`, `--no-push`), calls `run`, prints one status line, returns `_STATUS_EXIT[status]`.
- `if __name__ == "__main__": raise SystemExit(main())`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_orchestrate.py (append)
def test_main_returns_exit_code(tmp_path, monkeypatch, capsys):
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    monkeypatch.setattr(orchestrate, "run", lambda date, **kw: {"status":"held","stages":{},"reason":"floor","date":date})
    code = orchestrate.main(["--date","2026-07-01"])
    assert code == 1   # held -> 1

def test_main_defaults_to_today(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    seen = {}
    monkeypatch.setattr(orchestrate, "run", lambda date, **kw: seen.update(date=date, kw=kw) or {"status":"published","stages":{},"reason":"","date":date})
    monkeypatch.setattr(orchestrate, "_today", lambda: "2026-07-09")
    orchestrate.main([])
    assert seen["date"]=="2026-07-09" and seen["kw"]["force"] is False and seen["kw"]["no_push"] is False

def test_main_passes_flags(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    seen = {}
    monkeypatch.setattr(orchestrate, "run", lambda date, **kw: seen.update(kw=kw) or {"status":"published","stages":{},"reason":"","date":date})
    orchestrate.main(["--date","2026-07-01","--force","--no-push"])
    assert seen["kw"]["force"] is True and seen["kw"]["no_push"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_orchestrate.py::test_main_passes_flags -v`
Expected: FAIL — `module 'nbs.orchestrate' has no attribute 'main'`

- [ ] **Step 3: Write minimal implementation**

```python
# nbs/orchestrate.py — add
import argparse

def _today():
    return datetime.now(config.KST).strftime("%Y-%m-%d")

def main(argv=None):
    ap = argparse.ArgumentParser(prog="orchestrate")
    ap.add_argument("--date", default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args(argv)
    date = a.date or _today()
    m = run(date, force=a.force, no_push=a.no_push)
    push = (m.get("stages", {}) or {}).get("push", {}).get("status", "-")
    print(f"[{m['status']}] {date} push={push} reason={m.get('reason','')}")
    return _STATUS_EXIT.get(m["status"], 1)

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_orchestrate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nbs/orchestrate.py tests/test_orchestrate.py
git commit -m "feat(p3a): orchestrate CLI (today KST default, --force/--no-push, exit codes)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VPUtXZyTzXtKwJfkZG3e5H"
```

---

### Task 7: Full-suite regression + real dry-run smoke + docs

**Files:**
- Create: `scripts/p3a_smoke.sh`
- Modify: `.gitignore` (add `.orchestrate.lock` if not covered), `docs/superpowers/HANDOFF.md`
- Test: full `pytest`

- [ ] **Step 1: Full-suite regression**

Run: `python3 -m pytest -q`
Expected: PASS (P2c 117 + new P3a orchestrate tests). No existing test regressed (P3a modifies no existing module).

- [ ] **Step 2: Ensure `.orchestrate.lock` is gitignored**

Check `.gitignore` contains a line covering `.orchestrate.lock` (add it under the run-scratch section if missing):

```
.orchestrate.lock
```

- [ ] **Step 3: Write the real dry-run smoke script**

```bash
# scripts/p3a_smoke.sh
#!/usr/bin/env bash
# P3a real smoke: run the full pipeline for a date WITHOUT pushing (--no-push), then show
# run.json. Needs Claude Code env (collect/select/stage call claude -p). Leaves a dirty tree;
# clean up with the date-scoped commands the P2c smoke prints (content/news|posts|usecase, ledger).
set -euo pipefail
DATE="${1:?usage: p3a_smoke.sh <date>}"
export PATH="$HOME/.local/bin:$PATH"
python3 -m nbs.orchestrate --date "$DATE" --no-push
echo "--- run.json ---"; cat "runs/$DATE/run.json"
echo "--- publish.json ---"; cat "runs/$DATE/publish.json" 2>/dev/null || true
```

- [ ] **Step 4: Run the real dry-run smoke (Claude Code env)**

```bash
export PATH="$HOME/.local/bin:$PATH"
chmod +x scripts/p3a_smoke.sh
bash scripts/p3a_smoke.sh 2026-07-02
```
Expected: `run.json` `status=published` (or `held` if that day's evidence is below floor — both are valid non-crash outcomes), `stages.push.status=skipped` (`--no-push`), `publish.json` present. Then run the P2c-style date-scoped cleanup so the tree is clean.

- [ ] **Step 5: Update HANDOFF** — set P3a to DONE-pending-merge, note the real dry-run smoke result, and that push/live-deploy is exercised only by unit tests (real push deferred to a manual verification or P3c scheduler run). List P3b/P3c/P3d as the remaining P3 sub-projects.

- [ ] **Step 6: Commit**

```bash
git add scripts/p3a_smoke.sh .gitignore docs/superpowers/HANDOFF.md
git commit -m "test(p3a): full regression + real dry-run smoke + HANDOFF update

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VPUtXZyTzXtKwJfkZG3e5H"
```

---

## Notes / deferred (carry to review)

- Real `git push` to the live origin is exercised only by unit tests (bare-remote in tmp). The real smoke uses `--no-push` to avoid publishing a real edition mid-development; the first real push is a deliberate manual step (or the first P3c scheduled run).
- `push_pending` (exit 2) is the "retry via catchup" signal for P3c; `push_rejected`/`held`/`failed` (exit 1) are "give up + alert" for P3d. `busy` (exit 3) means a concurrent run held the lock.
- The orchestrator never sends email and never runs on a timer — Gmail (P3b), systemd/preflight/catchup/Reddit-Chrome (P3c), alerts/metrics (P3d) are separate sub-projects.
- Lock is global (one orchestrate at a time), not per-date — two dates must not run concurrently anyway (shared git index).
