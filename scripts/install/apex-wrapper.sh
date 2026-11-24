#!/usr/bin/env bash
# APEX-wrapper.sh — symlinked to ~/.local/bin/APEX.
# Activates the managed venv and execs the real APEX CLI.

apex_HOME="${apex_HOME:-$HOME/.apex}"
VENV="$apex_HOME/.venv"

if [[ ! -d "$VENV" ]]; then
    echo "APEX: venv not found at $VENV" >&2
    echo "Re-run the installer: curl -fsSL https://apex.github.io/apex/install.sh | bash" >&2
    exit 1
fi

exec "$VENV/bin/APEX" "$@"
