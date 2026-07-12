#!/usr/bin/env bash
set -euo pipefail
UNIT_DIR="$HOME/.config/systemd/user"
SRC="$(cd "$(dirname "$0")/../deploy/systemd" && pwd)"
mkdir -p "$UNIT_DIR"
cp "$SRC"/ai-daily.service "$SRC"/ai-daily.timer \
   "$SRC"/ai-daily-alert.service "$SRC"/ai-daily-alert.timer "$UNIT_DIR/"
systemctl --user daemon-reload

# The unit PATH is %h/.local/bin:...  but `claude`, `opencli`, and `twitter` live under nvm, not
# there. Symlink them in so the unattended tick can find them. MUST run BEFORE `enable --now` —
# Persistent=true can fire a missed catch-up tick the instant the timer is enabled, and that
# tick needs the CLIs already on PATH. NOTE: pins the current nvm version dir — re-run this
# installer after a Node upgrade if the symlink dangles. (twitter omitted here silently drops
# ALL X coverage on every unattended tick — collect.fetch_x guard-skips when it's not on PATH.)
mkdir -p "$HOME/.local/bin"
for cli in claude opencli twitter; do
  src="$(command -v "$cli" || true)"
  if [ -n "$src" ] && [ "$src" != "$HOME/.local/bin/$cli" ]; then ln -sf "$src" "$HOME/.local/bin/$cli"; echo "symlinked $cli -> $src";
  else echo "[warn] $cli not found on PATH — publish/Reddit will degrade until installed"; fi
done

# Run user timers without an interactive login session (required for WSL unattended).
loginctl enable-linger "$USER" || echo "[warn] enable-linger failed — run: sudo loginctl enable-linger $USER"

systemctl --user enable --now ai-daily.timer ai-daily-alert.timer
# (linger + symlinks are in place before the timers can fire a Persistent catch-up tick.)
echo "installed. timers:"
systemctl --user list-timers 'ai-daily*' --no-pager || true
cat <<'EOF'

[one-time manual, for Reddit]
  Launch Chrome once with the automation profile, install the OpenCLI Browser-Bridge
  extension, and log into Reddit in it:
    google-chrome --user-data-dir="$HOME/.config/ai-daily/chrome-profile"
  (A fresh profile has NO extensions — logging into Reddit alone is not enough.)
EOF
