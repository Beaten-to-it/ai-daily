"""P3b: send the daily News+UseCase email via Gmail API.

git-authoritative: send decision AND body are read from origin/main (survives
runs/ scratch wipe). Secrets live OUTSIDE the repo (public Pages repo). google
libraries are imported lazily so this module imports without them.
"""
from __future__ import annotations

import argparse
import base64
import csv
import html as _html
import json
import os
import re
import stat
import tempfile
import urllib.parse
from email.message import EmailMessage
from email.utils import make_msgid, parseaddr
from pathlib import Path

from . import config, models, publish


# --- paths (repo-external secrets/ledger; env overrides) ---------------------

def config_dir() -> Path:
    return Path.home() / ".config" / "ai-daily"


def token_path() -> Path:
    return Path(os.environ.get("AI_DAILY_GOOGLE_TOKEN") or config_dir() / "google_token.json")


def client_secret_path() -> Path:
    return Path(os.environ.get("AI_DAILY_GOOGLE_CLIENT_SECRET") or config_dir() / "client_secret.json")


def ledger_path() -> Path:
    return Path(os.environ.get("AI_DAILY_EMAIL_LOG") or config_dir() / "email_delivery_log.csv")


# --- git-authoritative content access (gate + read from origin/main) ---------

_ORIGIN = "origin/main"


def _origin_show(rel: str) -> str | None:
    r = publish._git(["show", f"{_ORIGIN}:{rel}"])
    return r.stdout if r.returncode == 0 else None


def published(date: str) -> bool:
    """True iff the day's news index exists on origin/main (git-authoritative)."""
    return publish._git(["cat-file", "-e", f"{_ORIGIN}:content/news/{date}.md"]).returncode == 0


def read_content(date: str) -> tuple[str, str | None, str | None]:
    """Return (news_md, usecase_md_or_None, ax_md_or_None) — all read from origin/main (gate ref)."""
    news = _origin_show(f"content/news/{date}.md")
    if news is None:
        raise FileNotFoundError(f"origin/main has no content/news/{date}.md")
    usecase = _origin_show(f"content/usecase/{date}.md")   # None => omit section
    ax = _origin_show(f"content/ax/{date}.md")             # None => omit section
    return news, usecase, ax


# --- preprocess (front-matter strip, relref->absolute, subject) --------------

# Full shortcode = the exact ANGLE form assemble.build_news_index emits, built by
# wrapping publish._RELREF's inner pattern (single source). Any OTHER shortcode
# ({{% relref %}}, {{< ref >}}, malformed) is left un-rewritten and trips the guard.
_RELREF_FULL = re.compile(r"\{\{<\s*" + publish._RELREF.pattern + r"\s*>\}\}")
# Fail only on an un-rewritten ref/relref (= a broken POST link). Other Hugo shortcodes
# that may appear in claude -p usecase prose ({{< highlight >}} etc.) are left as literal
# text — harmless, not a broken link — instead of erroring the whole email that day.
_ANY_REF_SHORTCODE = re.compile(r"\{\{[<%]\s*/?\s*(?:rel)?ref\b")


def strip_front_matter(md: str) -> str:
    """Drop a leading YAML front-matter block (only when the file truly starts with a fence)."""
    s = md.lstrip("﻿")
    if not s.startswith("---"):
        return md
    end = s.find("\n---", 3)
    if end == -1:
        return md   # no closing fence — leave as-is
    return s[end + 4:].lstrip("\n")


def rewrite_relref(md: str) -> str:
    """Rewrite our emitted relref shortcode to an absolute pretty URL; fail on any residue."""
    base = config.SITE_BASEURL.rstrip("/")
    out = _RELREF_FULL.sub(lambda m: f"{base}/posts/{m.group(1)}/", md)
    if _ANY_REF_SHORTCODE.search(out):
        raise ValueError(f"unrewritten ref/relref shortcode remains (broken link): {out[:120]!r}")
    return out


def subject_for(news_md: str, date: str) -> str:
    title = models.parse_frontmatter_strict(news_md).get("title", "").strip()
    return title or f"[AI Daily] {date}"


def preprocess(md: str) -> str:
    return rewrite_relref(strip_front_matter(md))


# --- render (MD -> HTML email + text fallback) -------------------------------

_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_ALLOWED_SCHEMES = ("http", "https", "mailto")


def _safe_href(url: str) -> str:
    """Decode entities/whitespace/control chars BEFORE scheme check; allow only absolute
    http/https/mailto. Anything else (javascript:, data:, scheme-less, obfuscated) -> '#'."""
    decoded = _html.unescape(url).strip()
    decoded = "".join(c for c in decoded if ord(c) >= 0x20)   # drop control chars
    parts = urllib.parse.urlsplit(decoded)
    if parts.scheme.lower() not in _ALLOWED_SCHEMES:
        return "#"
    return decoded


def inline_md(s: str) -> str:
    """Escape once, then apply spans. Code FIRST (placeholder) so link/bold never fire
    inside code. href values are re-escaped with quote=True to prevent attribute break-out."""
    s = _html.escape(s)
    codes: list[str] = []

    def _stash(m):
        codes.append(m.group(1))
        return f"\x00CODE{len(codes) - 1}\x00"

    s = _CODE.sub(_stash, s)
    s = _LINK.sub(
        lambda m: f'<a href="{_html.escape(_safe_href(m.group(2)), quote=True)}">{m.group(1)}</a>',
        s,
    )
    s = _BOLD.sub(lambda m: f"<strong>{m.group(1)}</strong>", s)
    for i, c in enumerate(codes):
        s = s.replace(f"\x00CODE{i}\x00", f"<code>{c}</code>")
    return s


def render_html(md: str, title: str, web_url: str) -> str:
    body, in_ul = [], False

    def close_ul():
        nonlocal in_ul
        if in_ul:
            body.append("</ul>"); in_ul = False

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line:
            close_ul(); continue
        if line == "---":
            close_ul(); body.append("<hr>"); continue
        if line.startswith("# "):
            close_ul(); body.append(f"<h1>{inline_md(line[2:].strip())}</h1>")
        elif line.startswith("## "):
            close_ul(); body.append(f"<h2>{inline_md(line[3:].strip())}</h2>")
        elif line.startswith("### "):
            close_ul(); body.append(f"<h3>{inline_md(line[4:].strip())}</h3>")
        elif line.startswith("> "):
            close_ul(); body.append(f"<blockquote>{inline_md(line[2:].strip())}</blockquote>")
        elif line.lstrip().startswith("- "):
            if not in_ul:
                body.append("<ul>"); in_ul = True
            body.append(f"<li>{inline_md(line.lstrip()[2:].strip())}</li>")
        else:
            close_ul(); body.append(f"<p>{inline_md(line.strip())}</p>")
    close_ul()

    web_link = ""
    safe_web = _safe_href(web_url) if web_url else "#"
    if web_url and safe_web != "#":
        web_link = (
            '<p style="margin:30px 0 0;padding-top:20px;border-top:1px solid #edf0f6;text-align:center;">'
            f'<a href="{_html.escape(safe_web, quote=True)}" '
            'style="display:inline-block;background:#2563eb;color:#fff;font-weight:700;'
            'text-decoration:none;padding:13px 24px;border-radius:10px;">\U0001F4D6 웹에서 보기</a></p>'
        )
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_html.escape(title)}</title>
<style>
body {{ margin:0; padding:0; background:#f5f7fb; color:#172033; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans KR",Arial,sans-serif; line-height:1.62; }}
.wrap {{ max-width:640px; margin:0 auto; padding:28px 14px 48px; }}
.card {{ background:#fff; border:1px solid #e7ebf3; border-radius:18px; padding:28px; }}
.eyebrow {{ color:#5b6b86; font-size:13px; letter-spacing:.08em; text-transform:uppercase; margin-bottom:8px; }}
h1 {{ font-size:26px; line-height:1.25; margin:0 0 22px; }}
h2 {{ font-size:20px; margin:34px 0 14px; padding-top:18px; border-top:1px solid #edf0f6; }}
h3 {{ font-size:17px; margin:26px 0 10px; }}
p {{ margin:10px 0; }} ul {{ padding-left:22px; margin:10px 0 18px; }} li {{ margin:7px 0; }}
a {{ color:#2563eb; text-decoration:none; font-weight:600; }}
blockquote {{ margin:14px 0 22px; padding:16px 18px; background:#eef6ff; border-left:4px solid #3b82f6; border-radius:12px; }}
hr {{ border:0; height:1px; background:#edf0f6; margin:28px 0; }}
code {{ background:#f2f4f7; border-radius:6px; padding:1px 5px; }}
.footer {{ margin-top:18px; color:#667085; font-size:12px; text-align:center; }}
@media (max-width:520px) {{ .card {{ padding:20px; border-radius:14px; }} h1 {{ font-size:23px; }} }}
</style></head>
<body><div class="wrap"><div class="card">
<div class="eyebrow">AI Daily</div>
{''.join(body)}
{web_link}
</div><div class="footer">ai-daily · 링크는 원문/상세글로 연결</div></div></body></html>
"""


def render_text(md: str, web_url: str) -> str:
    tail = f"\n\n---\n웹에서 보기: {web_url}\n" if web_url else "\n"
    return md.rstrip() + tail


# --- MIME message + recipients ----------------------------------------------

DEFAULT_RECIPIENTS = ["kimhyo75@gmail.com"]
EMAIL_SENDER = "kimhyo75@gmail.com"   # From: header = authenticated token owner (Gmail userId stays "me")


def _clean_header(s: str) -> str:
    # header injection guard: truncate at the first CR/LF — an injected `\nBcc: ...` is dropped
    return s.split("\r")[0].split("\n")[0].strip()


def resolve_recipients(override: str) -> list[str]:
    if not override:
        return list(DEFAULT_RECIPIENTS)
    out: list[str] = []
    for tok in override.split(","):
        addr = parseaddr(tok)[1].strip()
        if not addr:
            continue
        if "\r" in tok or "\n" in tok:
            raise ValueError("CR/LF in recipient")
        if "@" not in addr:
            raise ValueError(f"invalid recipient: {tok!r}")
        if addr not in out:
            out.append(addr)
    if not out:
        raise ValueError("no valid recipients")
    return out


def build_message(sender: str, to_list: list[str], subject: str, html_body: str, text_body: str) -> dict:
    mid = make_msgid(domain="ai-daily")             # our own RFC Message-ID (traceability)
    msg = EmailMessage()
    msg["From"] = _clean_header(sender)
    msg["To"] = ", ".join(to_list)
    msg["Subject"] = _clean_header(subject)
    msg["Message-ID"] = mid
    msg.set_content(text_body)                       # text/plain part
    msg.add_alternative(html_body, subtype="html")   # text/html part -> multipart/alternative
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw, "message_id": mid}


# --- credentials (gmail.send-only, atomic 0600 write-back, scope enforced) ---

SEND_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


class TokenInvalid(Exception):
    """Token missing / wrong-scope / revoked — surfaces as reason 'token_invalid'."""


def _ensure_config_dir() -> None:
    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)   # secret dir not group/world accessible


def _atomic_write(path: Path, text: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent == config_dir():
        os.chmod(path.parent, 0o700)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent))
    try:
        os.chmod(tmp, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except Exception:
        os.path.exists(tmp) and os.remove(tmp)
        raise


def _require_600(path: Path) -> None:
    m = path.stat().st_mode
    if m & (stat.S_IRWXG | stat.S_IRWXO):
        raise PermissionError(f"{path} is group/world accessible; run: chmod 600 {path}")


def _assert_send_only(path: Path) -> None:
    """Refuse any token that carries MORE than gmail.send (broad-token reuse ban)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    scopes = data.get("scopes") or ([data["scope"]] if data.get("scope") else [])
    if set(scopes) != set(SEND_SCOPES):
        raise TokenInvalid(f"token scopes {scopes} != gmail.send-only; re-run scripts/reauth_google.py")


def load_credentials(path: Path | None = None):
    """Load token; verify send-only scope; refresh if expired (atomic write-back); enforce chmod 600."""
    from google.oauth2.credentials import Credentials       # lazy
    from google.auth.transport.requests import Request
    from google.auth.exceptions import RefreshError

    path = path or token_path()
    if not path.exists():
        raise TokenInvalid(f"no token at {path}. Run: python3 scripts/reauth_google.py")
    _require_600(path)
    _assert_send_only(path)                                  # reject a broad token on a public repo
    creds = Credentials.from_authorized_user_file(str(path), SEND_SCOPES)
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError as e:
            raise TokenInvalid(f"refresh failed (revoked/expired): {e}")
        _atomic_write(path, creds.to_json())                # write-back refreshed token, keep 600
    if not creds.valid:
        raise TokenInvalid("stored Google token invalid; re-run scripts/reauth_google.py")
    return creds


# --- idempotency ledger + send + CLI ----------------------------------------

_LEDGER_HEADER = ["date", "run_id", "recipients", "subject", "gmail_ids", "message_id", "status"]


def already_sent(date: str, ledger: Path | None = None) -> bool:
    ledger = ledger or ledger_path()
    if not ledger.exists():
        return False
    with ledger.open(encoding="utf-8", newline="") as f:
        return any(row.get("date") == date and row.get("status") == "sent" for row in csv.DictReader(f))


def record_sent(date, run_id, recipients, subject, gmail_ids, message_id, status, ledger: Path | None = None) -> None:
    ledger = ledger or ledger_path()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(ledger.parent, 0o700)
    except OSError:
        pass
    new = not ledger.exists()
    with ledger.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(_LEDGER_HEADER)
        w.writerow([date, run_id, "|".join(recipients), subject, "|".join(gmail_ids), message_id, status])
    try:
        os.chmod(ledger, 0o600)   # ledger holds recipients/subject (PII) — enforce 0600 (§10)
    except OSError:
        pass


def _gmail_send(creds, message: dict, sender: str) -> str:
    from googleapiclient.discovery import build   # lazy
    service = build("gmail", "v1", credentials=creds)
    # Gmail Message resource only takes `raw` (the Message-ID header is already inside raw);
    # passing message_id as a body field would 400.
    result = service.users().messages().send(userId=sender, body={"raw": message["raw"]}).execute()
    return result["id"]


def run_email(date, *, to="", dry_run=False, force=False, run_id=None) -> dict:
    run_id = run_id or "manual"
    out = {"date": date, "status": "error", "reason": "", "recipients": [], "subject": "",
           "ids": [], "message_id": ""}
    if not published(date):
        out["status"] = "not_published"; out["reason"] = "origin/main has no news for date"
        return out
    news_md, usecase_md, ax_md = read_content(date)
    subject = subject_for(news_md, date)
    web_url = f"{config.SITE_BASEURL.rstrip('/')}/news/{date}/"
    body_md = preprocess(news_md)
    if usecase_md is not None:
        body_md += "\n\n---\n\n" + preprocess(usecase_md)
    if ax_md is not None:
        body_md += "\n\n---\n\n" + preprocess(ax_md)
    html_body = render_html(body_md, subject, web_url)
    text_body = render_text(body_md, web_url)
    recipients = resolve_recipients(to)
    out["subject"] = subject; out["recipients"] = recipients
    if dry_run:                                   # compose but never send/record — ledger-independent
        out["status"] = "dry_run"; return out
    if already_sent(date) and not force:          # idempotent gate AFTER the dry-run short-circuit
        out["status"] = "already_sent"; return out
    creds = load_credentials()                    # raises TokenInvalid on missing/broad/revoked token
    msg = build_message(EMAIL_SENDER, recipients, subject, html_body, text_body)  # From = real addr
    gid = _gmail_send(creds, msg, "me")           # Gmail API userId="me" = authenticated account
    out["ids"] = [gid]; out["message_id"] = msg["message_id"]; out["status"] = "sent"
    record_sent(date, run_id, recipients, subject, [gid], msg["message_id"], "sent")
    return out


_STATUS_EXIT = {"sent": 0, "already_sent": 0, "not_published": 0, "dry_run": 0, "error": 1}


def _today() -> str:
    from datetime import datetime
    return datetime.now(config.KST).strftime("%Y-%m-%d")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="email")
    ap.add_argument("--date", default=None)
    ap.add_argument("--to", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--run-id", default=None)
    a = ap.parse_args(argv)
    date = a.date or _today()
    _base = {"date": date, "status": "error", "reason": "", "recipients": [], "subject": "", "ids": [], "message_id": ""}
    try:
        res = run_email(date, to=a.to, dry_run=a.dry_run, force=a.force, run_id=a.run_id)
    except TokenInvalid:
        res = {**_base, "reason": "token_invalid"}          # spec §15: distinct reason for P3d/reauth
    except Exception as e:                                    # send failure etc. -> nonzero, structured
        res = {**_base, "reason": str(e)}
    print(json.dumps(res, ensure_ascii=False))
    return _STATUS_EXIT.get(res["status"], 1)


if __name__ == "__main__":
    raise SystemExit(main())
