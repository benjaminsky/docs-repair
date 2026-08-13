#!/usr/bin/env sh
# Install these skills where your agent looks for skills.
#
# A skill is just a directory of files, so "installing" is copying or
# symlinking each one into place. This script picks a sensible destination
# and refuses to clobber anything it did not put there.
set -eu

REPO="https://github.com/benjaminsky/docs-repair"
MODE="copy"
DEST=""

usage() {
    cat <<EOF
Usage: ./install.sh [options]

  (no options)   install for the current user  (~/.claude/skills/<name>)
  --project      install into this project     (./.claude/skills/<name>)
  --dir PATH     install into PATH/<name>      (any agent, any location)
  --skill NAME   install only NAME (default: every skill in skills/)
  --link         symlink instead of copying, so git pull updates in place
  --uninstall    remove a previous install from the resolved destination
  -h, --help     this

Examples
  ./install.sh                      # personal, all projects, all skills
  ./install.sh --project --link     # this repo, tracks your clone
  ./install.sh --skill metadiscourse-audit
EOF
}

ACTION="install"
ONLY=""
while [ $# -gt 0 ]; do
    case "$1" in
        --project)   DEST="$(pwd)/.claude/skills" ;;
        --dir)       shift; [ $# -gt 0 ] || { echo "--dir needs a path" >&2; exit 2; }; DEST="$1" ;;
        --skill)     shift; [ $# -gt 0 ] || { echo "--skill needs a name" >&2; exit 2; }; ONLY="$1" ;;
        --link)      MODE="link" ;;
        --uninstall) ACTION="uninstall" ;;
        -h|--help)   usage; exit 0 ;;
        *)           echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

[ -n "$DEST" ] || DEST="$HOME/.claude/skills"

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
[ -d "$REPO_ROOT/skills" ] || { echo "error: run this from a clone of $REPO" >&2; exit 1; }

install_one() {
    NAME="$1"
    SRC="$REPO_ROOT/skills/$NAME"
    TARGET="$DEST/$NAME"
    if [ ! -f "$SRC/SKILL.md" ]; then
        echo "error: no such skill: $NAME" >&2
        exit 1
    fi

    if [ "$ACTION" = "uninstall" ]; then
        if [ -L "$TARGET" ] || [ -d "$TARGET" ]; then
            rm -rf "$TARGET"
            echo "removed $TARGET"
        else
            echo "nothing installed at $TARGET"
        fi
        return
    fi

    # Never overwrite something we did not install: a directory here could be
    # a fork, a hand-edited copy, or an unrelated skill sharing a name. The
    # older marker name is honoured so pre-1.4 installs still upgrade.
    if [ -L "$TARGET" ]; then
        echo "note: replacing existing symlink $TARGET"
        rm -f "$TARGET"
    elif [ -d "$TARGET" ]; then
        if [ -f "$TARGET/.installed-by-benjaminsky-skills" ] \
            || [ -f "$TARGET/.installed-by-metadiscourse-audit" ]; then
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
        for item in SKILL.md references scripts; do
            [ -e "$SRC/$item" ] && cp -R "$SRC/$item" "$TARGET/"
        done
        for item in README.md LICENSE; do
            [ -e "$REPO_ROOT/$item" ] && cp "$REPO_ROOT/$item" "$TARGET/"
        done
        : > "$TARGET/.installed-by-benjaminsky-skills"
        echo "installed $TARGET"
    fi
}

if [ -n "$ONLY" ]; then
    install_one "$ONLY"
else
    for dir in "$REPO_ROOT"/skills/*/; do
        install_one "$(basename "$dir")"
    done
fi

[ "$ACTION" = "uninstall" ] && exit 0

cat <<EOF

Done. Start a new agent session and ask in your own words, e.g.
  "the docs in ./docs read like a changelog — can you clean them up?"
  "docs/ was written by coding-agent sessions and it shows — de-slop it"

The scanners also run on their own, with no agent involved:
  python3 $DEST/metadiscourse-audit/scripts/scan.py docs README.md
  python3 $DEST/ai-slop-audit/scripts/scan.py docs README.md
EOF
