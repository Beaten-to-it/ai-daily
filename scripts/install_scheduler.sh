#!/usr/bin/env bash
set -euo pipefail
UNIT_DIR="$HOME/.config/systemd/user"
SRC="$(cd "$(dirname "$0")/../deploy/systemd" && pwd)"
mkdir -p "$UNIT_DIR"
cp "$SRC"/ai-daily.service "$SRC"/ai-daily.timer \
   "$SRC"/ai-daily-alert.service "$SRC"/ai-daily-alert.timer "$UNIT_DIR/"
systemctl --user daemon-reload
systemctl --user enable --now ai-daily.timer ai-daily-alert.timer

# The unit PATH is %h/.local/bin:...  but `claude` and `opencli` live under nvm, not there.
# Symlink them in so the unattended tick can find them. NOTE: this pins the current nvm
# version dir — re-run this installer after a Node upgrade if the symlink dangles.
mkdir -p "$HOME/.local/bin"
for cli in claude opencli; do
  src="$(command -v "$cli" || true)"
  if [ -n "$src" ]; then ln -sf "$src" "$HOME/.local/bin/$cli"; echo "symlinked $cli -> $src";
  else echo "[warn] $cli not found on PATH — publish/Reddit will degrade until installed"; fi
done
# Run user timers without an interactive login session (required for WSL unattended).
loginctl enable-linger "$USER" || echo "[warn] enable-linger failed — run: sudo loginctl enable-linger $USER"
echo "installed. timers:"
systemctl --user list-timers 'ai-daily*' --no-pager || true
cat <<'EOF'

[one-time manual, for Reddit]
  Launch Chrome once with the automation profile, install the OpenCLI Browser-Bridge
  extension, and log into Reddit in it:
    google-chrome --user-data-dir="$HOME/.config/ai-daily/chrome-profile"
  (A fresh profile has NO extensions — logging into Reddit alone is not enough.)
EOF
