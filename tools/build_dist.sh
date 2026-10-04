#!/usr/bin/env bash
# Build judge-facing Ren'Py distributions.
#
# Ren'Py's `distribute` command copies the WORKING DIRECTORY, not the git tree.
# That means .gitignore does NOT protect us here: a local game/secrets.json is
# copied straight into every build and would ship real credentials to judges.
# There is no CLI flag for Ren'Py's files_filter, so we move the file aside for
# the duration of the build and restore it afterwards.
#
# Usage: tools/build_dist.sh [destination_dir]
#   default destination: /tmp/dist
set -euo pipefail

SDK="${RENPY_SDK:-/home/sonica/Downloads/renpy-8.5.3-sdk}"
PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${1:-/tmp/dist}"
SECRETS="$PROJECT/game/secrets.json"
STASH=""

cleanup() {
    if [ -n "$STASH" ] && [ -f "$STASH" ]; then
        mv "$STASH" "$SECRETS"
        echo "restored $SECRETS"
    fi
}
trap cleanup EXIT INT TERM

if [ -f "$SECRETS" ]; then
    STASH="$(mktemp "${TMPDIR:-/tmp}/rbd-secrets.XXXXXX.json")"
    mv "$SECRETS" "$STASH"
    echo "stashed $SECRETS out of the build"
fi

mkdir -p "$DEST"
echo "building distributions -> $DEST"
"$SDK/renpy.sh" "$SDK" distribute "$PROJECT" --destination "$DEST"

cleanup
STASH=""

echo
echo "verifying no credentials in the output:"
found=0
while IFS= read -r archive; do
    if case "$archive" in
        *.zip) unzip -l "$archive" ;;
        *.tar.bz2) tar -tjf "$archive" ;;
    esac | grep -q "game/secrets\.json$"; then
        echo "  FAIL $archive contains game/secrets.json"
        found=1
    else
        echo "  ok   $archive"
    fi
done < <(find "$DEST" -maxdepth 1 -type f \( -name '*.zip' -o -name '*.tar.bz2' \))
[ "$found" -eq 0 ] || { echo "BUILD CONTAINS SECRETS -- do not distribute"; exit 1; }

echo
echo "done. artifacts:"
ls -la "$DEST" | awk 'NR>2 {printf "  %8.1f MB  %s\n", $5/1048576, $9}'