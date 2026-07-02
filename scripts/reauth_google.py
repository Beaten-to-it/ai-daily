#!/usr/bin/env python3
"""Mint a NEW gmail.send-only OAuth token for ai-daily's daily email.

MUST be run by a human (opens a browser). In a Claude Code session, prefix with `!`:
    ! python3 -m pip install --break-system-packages google-auth-oauthlib
    ! python3 scripts/reauth_google.py

Writes the token OUTSIDE the repo (public Pages repo) at email.token_path()
(default ~/.config/ai-daily/google_token.json, chmod 600). Uses ONLY the
gmail.send scope — never inherits a prior token's broader scopes.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nbs import email as em

SCOPES = list(em.SEND_SCOPES)   # gmail.send only — single source


def main() -> int:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ModuleNotFoundError:
        sys.exit("ERROR: pip install --break-system-packages google-auth-oauthlib")
    em._ensure_config_dir()                    # ~/.config/ai-daily/ at chmod 700
    secret = em.client_secret_path()
    if not secret.exists():
        sys.exit(f"ERROR: no client_secret at {secret}. Copy the OAuth Desktop client there.")
    em._require_600(secret)                     # refuse a group/world-readable client_secret (§10)
    token = em.token_path()
    print(f"client_secret: {secret}\nscopes: {SCOPES}\nOpening browser — approve consent.\n")
    flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    em._atomic_write(token, creds.to_json())   # chmod 600
    print(f"OK: token written to {token}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
