#!/bin/sh
# AMVFX installer (macOS/Linux): checkbox GUI when a display is available,
# terminal prompts otherwise. Pass flags through, e.g.
#   ./install.sh --yes
#   ./install.sh --with-blender --no-ae-panel --dry-run
cd "$(dirname "$0")" || exit 1
exec python3 install.py "$@"
