import subprocess, json, os, tempfile, re, argparse, hashlib, sys, time
from contextlib import contextmanager
from datetime import datetime, timedelta
from .config import ROOT, run_dir
from . import config, locking
from . import publish as publish_mod

Busy = locking.BusyLock

@contextmanager
def _lock():
    lock_path = ROOT / ".orchestrate.lock"
    with locking.exclusive_lock(lock_path):
        yield

# Only NETWORK git ops (push, ls-remote) can hang — a stalled peer/credential-helper would otherwise
# block the run forever AFTER the commit, holding both locks. They pass an explicit timeout below
# (=CRITICAL-3 guard). LOCAL ops get NO timeout: git fails fast on lock/disk, it never hangs, and a
# synthetic timeout rc would be indistinguishable from a real "clean"/"absent" answer and silently
# read as success by callers. GIT_TERMINAL_PROMPT=0 everywhere: a credential prompt fails fast
# instead of hanging on stdin. A network timeout surfaces as rc=124, handled at the two call sites.
_GIT_NET_TIMEOUT = 120

def _git(args, timeout=None):
    # env built PER CALL (not snapshotted at import) so runtime GIT_CONFIG_*/env overrides are honored.
    try:
        return subprocess.run(["git"] + args, cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=timeout, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, returncode=124, stdout="", stderr="git timed out")

def _head_has_daily(date):
    # tri-state: True = in HEAD, False = CONFIRMED absent, None = git error (caller fails closed).
    # ls-tree (not cat-file): cat-file returns rc 128 for BOTH a missing path AND a corrupt repo, so
    # a git error would masquerade as "not published" and drive a re-publish. ls-tree returns rc 0
    # for present AND absent (differing only by stdout) and rc != 0 only on a genuine error.
    r = _git(["ls-tree", "HEAD", "--", f"content/daily/{date}.md"])
    if r.returncode != 0:
        return None
    return bool(r.stdout.strip())

def _publish_state(date):
    p = run_dir(date) / "publish.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None

def decide_action(date, *, force):
    # git-authoritative: HEAD having the day's daily edition file is the reliable "published locally"
    # signal (survives runs/ scratch wipe). publish.json.pushed only optimizes skip vs re-push.
    if force:
        return "full"
    hn = _head_has_daily(date)
    if hn is None:                              # can't determine publish state (git error) -> abort,
        return "error"                          # never guess: guessing "unpublished" re-publishes a live day
    if hn:
        st = _publish_state(date)
        if st is None:                          # scratch wiped but daily in HEAD → recover by re-push
            return "push_only"
        if st.get("status") != "published":     # a held/failed manifest (e.g. a later --force run)
            return "full"                       # means this day is NOT cleanly published → regenerate
        return "skip" if st.get("pushed") is True else "push_only"
    return "full"

STAGES = ["collect", "select", "stage", "validate", "publish"]
_ARTIFACT = {"collect": "candidates.json", "select": "selection.json",
             "stage": "generation.json", "publish": "publish.json"}

def _default_runner(name, date, no_commit=False, stderr_sink=None):
    argv = [sys.executable, "-m", f"nbs.{name}", "--date", date]
    if name == "publish" and no_commit:
        argv.append("--no-commit")     # promote into content/ but DON'T commit (smoke-safe)
    result = subprocess.run(argv, cwd=str(ROOT), stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace")
    if stderr_sink is not None and getattr(result, "stderr", ""):
        stderr_sink[name] = result.stderr[-2000:]
    return result.returncode

def _default_email_runner(date, run_id):
    try:
        p = subprocess.run([sys.executable, "-m", "nbs.email", "--date", date, "--run-id", run_id],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:            # never hang the run (and the flock) on a stuck send
        return 1, {"status": "error", "reason": "email timed out (120s)"}
    try:
        res = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {}
    except (ValueError, IndexError):
        res = {"status": "error", "reason": "unparseable email output"}
    return p.returncode, res

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


def _input_hash(date):
    directory = run_dir(date)
    generation = directory / "generation.json"
    if not generation.is_file():
        raise FileNotFoundError("generation.json missing")
    files = [generation]
    staging = directory / "staging"
    if staging.exists():
        files.extend(sorted(path for path in staging.rglob("*") if path.is_file()))
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(directory).as_posix().encode("utf-8")
        digest.update(relative); digest.update(b"\0"); digest.update(path.read_bytes()); digest.update(b"\0")
    return digest.hexdigest()


def _current_head():
    result = _git(["rev-parse", "HEAD"])
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError("cannot resolve Git HEAD")
    return result.stdout.strip()


def _site_tree_ready():
    result = _git(["status", "--porcelain", "--", "hugo.toml", "layouts", "themes",
                   "content/_index.md", "content/daily/_index.md",
                   "content/articles/_index.md", "content/executive/_index.md",
                   "content/guides/_index.md"])
    if result.returncode != 0:
        return False, "cannot inspect site configuration"
    if result.stdout.strip():
        return False, "site configuration dirty"
    gitlink = _git(["ls-files", "--stage", "--", "themes/PaperMod"])
    if gitlink.returncode != 0:
        return False, "cannot inspect PaperMod submodule"
    if gitlink.stdout.startswith("160000 "):
        submodule = _git(["submodule", "status", "--", "themes/PaperMod"])
        pinned = gitlink.stdout.split()[1]
        if (submodule.returncode != 0 or not submodule.stdout.startswith(" ")
                or submodule.stdout[1:].split()[0] != pinned):
            return False, "PaperMod submodule is not initialized at the pinned commit"
    return True, ""


def _write_checkpoint(date, payload):
    path = run_dir(date) / "checkpoint.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        os.path.exists(tmp) and os.remove(tmp)
        raise
    return payload


def _prepare_checkpoint(date, validated_at):
    try:
        generation = json.loads((run_dir(date) / "generation.json").read_text(encoding="utf-8"))
        if generation.get("date") != date:
            return False, "generation.json date mismatch", None
        clean, reason = _site_tree_ready()
        if not clean:
            return False, reason, None
        errors = publish_mod.check_completeness(generation, run_dir(date) / "staging")
        if errors:
            return False, f"completeness: {'; '.join(errors[:8])}", None
        errors = publish_mod.build_verify(generation, content_dir=run_dir(date) / "staging")
        if errors:
            return False, f"hugo: {'; '.join(errors[:8])}", None
        checkpoint = {
            "version": 1,
            "date": date,
            "status": "validated",
            "validated_at": validated_at,
            "git_head": _current_head(),
            "input_hash": _input_hash(date),
            "validation": {"status": "ok", "errors": [], "hugo": "ok"},
            "site_tree": "clean",
            "source_health_warnings": generation.get("source_health_warnings", []),
            "counts": {"published": generation.get("published_count", len(generation.get("results", [])))},
        }
        return True, "", _write_checkpoint(date, checkpoint)
    except (OSError, ValueError, RuntimeError) as error:
        return False, str(error), None


def _checkpoint_ready(date):
    path = run_dir(date) / "checkpoint.json"
    try:
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
        if checkpoint.get("version") != 1 or checkpoint.get("date") != date:
            return False, "checkpoint date/version mismatch"
        validation = checkpoint.get("validation")
        if (checkpoint.get("status") != "validated" or not isinstance(validation, dict)
                or validation.get("status") != "ok" or validation.get("errors") != []
                or validation.get("hugo") != "ok" or checkpoint.get("site_tree") != "clean"):
            return False, "checkpoint is not validated"
        clean, reason = _site_tree_ready()
        if not clean:
            return False, reason
        if checkpoint.get("git_head") != _current_head():
            return False, "Git HEAD changed after prepare"
        if checkpoint.get("input_hash") != _input_hash(date):
            return False, "prepared inputs changed"
        generation = json.loads((run_dir(date) / "generation.json").read_text(encoding="utf-8"))
        errors = publish_mod.check_completeness(generation, run_dir(date) / "staging")
        if errors:
            return False, f"checkpoint revalidation failed: {'; '.join(errors[:8])}"
        return True, ""
    except (OSError, ValueError, RuntimeError) as error:
        return False, f"checkpoint unavailable: {error}"

def _mark_pushed(date, sha):
    p = run_dir(date) / "publish.json"
    st = _publish_state(date) or {"date": date}
    st["status"] = "published"   # we only mark after pushing a published HEAD; never keep held/failed
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
    ls = _git(["ls-remote", "origin", "refs/heads/main"], timeout=_GIT_NET_TIMEOUT)   # network: bound it
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
    # push the ACTUAL published commit (HEAD) to remote main — NOT the local `main` branch,
    # which may be stale/unrelated on a non-main or detached checkout.
    branch = _git(["symbolic-ref", "--quiet", "--short", "HEAD"])
    if branch.returncode != 0 or branch.stdout.strip() != "main":
        return "push_rejected", None, "publishing requires the local main branch"
    head = _git(["rev-parse", "HEAD"]).stdout.strip()
    if _git(["push", "origin", "HEAD:refs/heads/main"], timeout=_GIT_NET_TIMEOUT).returncode != 0:
        status, sha, reason = _classify_push_failure(head)   # rc=124 on timeout -> ls-remote decides
        if status == "published":                # remote already at HEAD → record it
            _mark_pushed(date, sha)
            return "published", sha, reason
        return status, None, reason
    if _git(["rev-parse", "origin/main"]).stdout.strip() != head:
        return "push_pending", None, "push reported success but origin/main did not advance"
    _mark_pushed(date, head)
    return "published", head, ""

_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_STATUS_EXIT = {"published":0,"prepared":0,"skipped":0,"held":2,"failed":2,
                "push_rejected":2,"push_pending":2,"busy":3,"not_ready":4}

def _blank_stages():
    return {s: {"status": "skipped", "reason": ""} for s in STAGES + ["push", "email"]}


def _read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _manifest_evidence(date, stderr_summary):
    directory = run_dir(date)
    candidates = _read_json(directory / "candidates.json", [])
    selection = _read_json(directory / "selection.json", {})
    generation = _read_json(directory / "generation.json", {})
    health = _read_json(directory / "source_health.json", [])
    checkpoint = _read_json(directory / "checkpoint.json", {})
    published = _read_json(directory / "publish.json", {})
    decisions = selection.get("decisions", []) if isinstance(selection, dict) else []
    decision_counts = {
        "select": sum(row.get("decision") == "select" for row in decisions if isinstance(row, dict)),
        "skip": sum(row.get("decision") == "skip" for row in decisions if isinstance(row, dict)),
    }
    if not decisions and isinstance(selection, dict):
        decision_counts = {
            "select": selection.get("selected_count", 0),
            "skip": selection.get("skipped_count", 0),
        }
    results = generation.get("results", []) if isinstance(generation, dict) else []
    model_errors = [row.get("error", "") for row in results
                    if isinstance(row, dict) and row.get("error")]
    head = _git(["rev-parse", "HEAD"])
    return {
        "counts": {
            "candidates": len(candidates) if isinstance(candidates, list) else 0,
            "selected": selection.get("selected_count", 0) if isinstance(selection, dict) else 0,
            "skipped": selection.get("skipped_count", 0) if isinstance(selection, dict) else 0,
            "published": generation.get("published_count", 0) if isinstance(generation, dict) else 0,
        },
        "source_health": health if isinstance(health, list) else [],
        "decisions": decision_counts,
        "warning_state": {
            "volume": generation.get("volume_status") if isinstance(generation, dict) else None,
            "source_health": generation.get("source_health_warnings", []) if isinstance(generation, dict) else [],
            "guide": generation.get("guide_error") if isinstance(generation, dict) else None,
            "executive": generation.get("executive_error") if isinstance(generation, dict) else None,
        },
        "codex_stderr_summary": dict(stderr_summary),
        "model_error_summary": model_errors[:20],
        "git": {
            "current_head": head.stdout.strip() if head.returncode == 0 else None,
            "prepared_head": checkpoint.get("git_head") if isinstance(checkpoint, dict) else None,
            "input_hash": checkpoint.get("input_hash") if isinstance(checkpoint, dict) else None,
            "publish_commit": published.get("commit_sha") if isinstance(published, dict) else None,
            "deployed_sha": published.get("deployed_sha") if isinstance(published, dict) else None,
        },
    }

def _write_run(date, payload):
    d = run_dir(date); d.mkdir(parents=True, exist_ok=True)
    p = d/"run.json"
    fd, tmp = tempfile.mkstemp(dir=str(d), suffix=".json")   # atomic: no truncated manifest on crash
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except Exception:
        os.path.exists(tmp) and os.remove(tmp); raise
    return payload

def run(date, *, force=False, no_push=False, no_commit=False, prepare_only=False,
        publish_only=False, shadow=False, runner=None, now=None, email_runner=None):
    if shadow:
        prepare_only = True
    if no_commit:
        no_push = True   # nothing committed -> a push would send an unchanged HEAD; skip it (smoke-safe)
    stderr_summary = {}
    runner = runner or (lambda n, d: _default_runner(
        n, d, no_commit=no_commit, stderr_sink=stderr_summary
    ))
    email_runner = email_runner or _default_email_runner
    now = now or datetime.now(config.KST)
    run_id = now.strftime("%Y%m%dT%H%M%S%z")
    started = now.isoformat()
    base = {"date": date, "run_id": run_id, "started_at": started,
            "status": "failed", "stages": _blank_stages(), "reason": "", "force": force,
            "prepare_only": prepare_only, "publish_only": publish_only, "shadow": shadow}
    if not _DATE.fullmatch(date or ""):
        base["status"] = "failed"; base["reason"] = "invalid date (must be YYYY-MM-DD)"
        return base   # do NOT write run.json under an unvalidated path
    if prepare_only and publish_only:
        base["reason"] = "prepare-only and publish-only are mutually exclusive"
        return base
    def finish(status, reason=""):
        base["status"] = status; base["reason"] = reason
        base.update(_manifest_evidence(date, stderr_summary))
        _write_run(date, base)                          # persist publish+push BEFORE the network email
        # email only when the day is genuinely published to origin AND this is not a dry-run.
        if status in ("published", "skipped") and not no_push and not prepare_only:
            email_started = time.monotonic()
            try:
                rc, res = email_runner(date, run_id)
                # a failed email is a P3d ALERT — normalize rc!=0 to "failed" (§12/§15).
                estatus = "failed" if rc != 0 else res.get("status", "failed")
                est = {"status": estatus, "reason": res.get("reason", "")}
            except Exception as e:                      # seam/subprocess failure must not crash the run
                est = {"status": "failed", "reason": str(e)}
            base["stages"]["email"] = est
            base["stages"]["email"]["duration_ms"] = max(
                0, int((time.monotonic() - email_started) * 1000)
            )
            base.update(_manifest_evidence(date, stderr_summary))
            _write_run(date, base)                      # best-effort re-write with the email stage
        return base
    try:
        with _lock():
            if no_commit and _head_has_daily(date) is not False:
                # a no-commit PREVIEW must never overwrite the recovery manifest of an already-
                # published date: publish would write publish.json{status:published, commit_sha:null}
                # with no actual commit, so the next real run does push_only on the STALE HEAD and
                # records the preview as deployed. Refuse on True (published) OR None (state
                # unverifiable via git) — fail closed. No run/publish state is touched.
                base["status"] = "skipped"
                base["reason"] = "no-commit preview refused: date published or state unverifiable"
                return base
            if prepare_only:
                published = _head_has_daily(date)
                if published is None:
                    return finish("failed", "cannot determine publish state (git error)")
                if published:
                    return finish("skipped", "date already published; prepare refused")
                action = "full"
            elif publish_only:
                validate_started = time.monotonic()
                state = _publish_state(date) or {}
                recover = False
                if state.get("status") == "published" and state.get("pushed") is not True:
                    try:
                        recover = (state.get("commit_sha") == _current_head()
                                   and _head_has_daily(date) is True)
                    except RuntimeError:
                        recover = False
                if recover:
                    base["stages"]["validate"] = {
                        "status": "ok", "reason": "recovering validated publish commit",
                        "duration_ms": max(0, int((time.monotonic() - validate_started) * 1000)),
                    }
                    action = "push_only"
                else:
                    ready, reason = _checkpoint_ready(date)
                    if not ready:
                        base["stages"]["validate"] = {
                            "status": "failed", "reason": reason,
                            "duration_ms": max(0, int((time.monotonic() - validate_started) * 1000)),
                        }
                        return finish("not_ready", reason)
                    base["stages"]["validate"] = {
                        "status": "ok", "reason": "checkpoint matched",
                        "duration_ms": max(0, int((time.monotonic() - validate_started) * 1000)),
                    }
                    action = "publish_only"
            else:
                action = decide_action(date, force=force)
            if action == "error":
                # decide_action could not determine publish state (git error) -> abort, don't guess.
                return finish("failed", "cannot determine publish state (git error)")
            if action == "skip":
                return finish("skipped", "already published and pushed")
            if action == "push_only":
                if no_push:   # honor dry-run on the recovery path too (else smoke pushes to origin)
                    base["stages"]["push"] = {"status": "skipped", "reason": "--no-push"}
                    return finish("published", "already published locally (push skipped)")
                push_started = time.monotonic()
                st, sha, reason = _push(date)
                base["stages"]["push"] = {
                    "status": st, "reason": reason or "push-only recovery",
                    "duration_ms": max(0, int((time.monotonic() - push_started) * 1000)),
                }
                top = "re-pushed without regeneration" if st == "published" else f"push-only recovery failed: {reason}"
                return finish("published" if st == "published" else st, top)
            pipeline = ["publish"] if action == "publish_only" else STAGES
            for name in pipeline:
                if name == "validate":
                    stage_started = time.monotonic()
                    ok, reason, _ = _prepare_checkpoint(date, started)
                    base["stages"]["validate"] = {
                        "status": "ok" if ok else "failed", "reason": reason,
                        "duration_ms": max(0, int((time.monotonic() - stage_started) * 1000)),
                    }
                    if not ok:
                        return finish("failed", f"validate: {reason}")
                    if prepare_only:
                        return finish("prepared", "validated checkpoint ready")
                    continue
                stage_started = time.monotonic()
                rc = runner(name, date)
                duration_ms = max(0, int((time.monotonic() - stage_started) * 1000))
                if name == "publish":
                    # publish exits 0 even for held/failed — but a CRASHED publish (rc!=0) must
                    # NOT be read as a stale prior publish.json{published}. Gate on rc+artifact first.
                    ok, reason = _stage_ok("publish", date, rc)
                    if not ok:
                        base["stages"]["publish"] = {"status": "failed", "reason": reason,
                                                       "duration_ms": duration_ms}
                        return finish("failed", f"publish: {reason}")
                    pj = _publish_state(date) or {}
                    pstatus = pj.get("status")
                    if pstatus not in ("published", "held", "failed"):
                        base["stages"]["publish"] = {"status": "failed", "reason": f"unknown publish status {pstatus!r}",
                                                       "duration_ms": duration_ms}
                        return finish("failed", f"unknown publish status {pstatus!r}")
                    preason = pj.get("reason", "")   # publish.py records the held/failed cause here
                    base["stages"]["publish"] = {"status": pstatus, "reason": preason,
                                                   "duration_ms": duration_ms}
                    if pstatus != "published":
                        return finish(pstatus, preason or f"publish {pstatus}")   # held/failed -> no push
                    break
                ok, reason = _stage_ok(name, date, rc)
                base["stages"][name] = {"status": "ok" if ok else "failed", "reason": reason,
                                         "duration_ms": duration_ms}
                if not ok:
                    return finish("failed", f"{name}: {reason}")
                if name == "stage":
                    generation = _read_json(run_dir(date) / "generation.json", {})
                    if (generation.get("status") == "skip-empty"
                            or generation.get("published_count") == 0):
                        return finish("held", "generation produced 0 publishable articles")
            if no_push:
                base["stages"]["push"] = {"status": "skipped", "reason": "--no-push"}
                return finish("published", "published (push skipped)")
            push_started = time.monotonic()
            st, sha, reason = _push(date)
            base["stages"]["push"] = {
                "status": st, "reason": reason,
                "duration_ms": max(0, int((time.monotonic() - push_started) * 1000)),
            }
            return finish("published" if st == "published" else st, reason)
    except Busy:
        base["status"] = "busy"; base["reason"] = "another run in progress"
        return base   # do not clobber the other run's run.json

def _today():
    return datetime.now(config.KST).strftime("%Y-%m-%d")

def _latest_checkpoint_date(today):
    current = datetime.strptime(today, "%Y-%m-%d")
    for candidate in (today, (current - timedelta(days=1)).strftime("%Y-%m-%d")):
        checkpoint = _read_json(ROOT / "runs" / candidate / "checkpoint.json", {})
        if (checkpoint.get("version") == 1 and checkpoint.get("date") == candidate
                and checkpoint.get("status") == "validated"):
            return candidate
    return None

def main(argv=None):
    ap = argparse.ArgumentParser(prog="orchestrate")
    ap.add_argument("--date", default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--no-commit", action="store_true")   # promote but don't commit/push (smoke)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--prepare-only", action="store_true")
    mode.add_argument("--publish-only", action="store_true")
    ap.add_argument("--shadow", action="store_true")
    a = ap.parse_args(argv)
    today = _today()
    date = a.date or ((_latest_checkpoint_date(today) or today) if a.publish_only else today)
    m = run(date, force=a.force, no_push=a.no_push, no_commit=a.no_commit,
            prepare_only=a.prepare_only, publish_only=a.publish_only, shadow=a.shadow)
    push = (m.get("stages", {}) or {}).get("push", {}).get("status", "-")
    print(f"[{m['status']}] {date} push={push} reason={m.get('reason','')}")
    return _STATUS_EXIT.get(m["status"], 1)

if __name__ == "__main__":
    raise SystemExit(main())
