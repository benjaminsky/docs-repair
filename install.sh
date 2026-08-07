#!/usr/bin/env sh
# Install metadiscourse-audit where your agent looks for skills.
#
# The skill is just a directory of files, so "installing" is copying or
# symlinking it into place. This script picks a sensible destination and
# refuses to clobber anything it did not put there.
set -eu

REPO="https://github.com/benjaminsky/metadiscourse-audit"
NAME="metadiscourse-audit"
MODE="copy"
DEST=""

usage() {
    cat <<EOF
Usage: ./install.sh [options]

  (no options)   install for the current user  (~/.claude/skills/$NAME)
  --project      install into this project     (./.claude/skills/$NAME)
  --dir PATH     install into PATH/$NAME       (any agent, any location)
  --link         symlink instead of copying, so git pull updates in place
  --uninstall    remove a previous install from the resolved destination
  -h, --help     this

Examples
  ./install.sh                      # personal, all projects
  ./install.sh --project --link     # this repo, tracks your clone
  ./install.sh --dir ~/.config/agent/skills
EOF
}

ACTION="install"
while [ $# -gt 0 ]; do
    case "$1" in
        --project)   DEST="$(pwd)/.claude/skills" ;;
        --dir)       shift; [ $# -gt 0 ] || { echo "--dir needs a path" >&2; exit 2; }; DEST="$1" ;;
        --link)      MODE="link" ;;
        --uninstall) ACTION="uninstall" ;;
        -h|--help)   usage; exit 0 ;;
        *)           echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

[ -n "$DEST" ] || DEST="$HOME/.claude/skills"
TARGET="$DEST/$NAME"

SRC="$(cd "$(dirname "$0")" && pwd)"
if [ ! -f "$SRC/SKILL.md" ]; then
    echo "error: run this from a clone of $REPO" >&2
    exit 1
fi

if [ "$ACTION" = "uninstall" ]; then
    if [ -L "$TARGET" ] || [ -d "$TARGET" ]; then
        rm -rf "$TARGET"
        echo "removed $TARGET"
    else
        echo "nothing installed at $TARGET"
    fi
    exit 0
fi

# Never overwrite something we did not install: a directory here could be a
# fork, a hand-edited copy, or an unrelated skill that happens to share a name.
if [ -L "$TARGET" ]; then
    echo "note: replacing existing symlink $TARGET"
    rm -f "$TARGET"
elif [ -d "$TARGET" ]; then
    if [ -f "$TARGET/.installed-by-metadiscourse-audit" ]; then
        rm -rf "$TARGET"
    else
        echo "error: $TARGET already exists and was not installed by this script." >&2
        echo "       Move it aside, or re-run with --uninstall first." >&2
        exit 1
    fi
fi

mkdir -p "$DEST"

if [ "$MODE" = "link" ]; then
    ln -s "$SRC" "$TARGET"
    echo "linked $TARGET -> $SRC"
else
    mkdir -p "$TARGET"
    for item in SKILL.md README.md LICENSE references scripts; do
        [ -e "$SRC/$item" ] && cp -R "$SRC/$item" "$TARGET/"
    done
    : > "$TARGET/.installed-by-metadiscourse-audit"
    echo "installed $TARGET"
fi

cat <<EOF

Done. Start a new agent session and ask in your own words, e.g.
  "the docs in ./docs read like a changelog — can you clean them up?"

The scanner also runs on its own, with no agent involved:
  python3 $TARGET/scripts/scan.py docs README.md
EOF
