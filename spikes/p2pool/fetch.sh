#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
DEST=$(realpath -m "$1")
mkdir -p "$DEST"
[[ -z $(ls -A "$DEST") ]] || { echo 'destination must be empty' >&2; exit 1; }
ARCHIVE="$DEST/source.tar.gz"
URL=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["archive_url"])' "$HERE/upstream.json")
SHA=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["archive_sha256"])' "$HERE/upstream.json")
curl --fail --location --silent --show-error "$URL" -o "$ARCHIVE"
printf '%s  %s\n' "$SHA" "$ARCHIVE" | sha256sum --check -
mkdir "$DEST/source"
tar -xzf "$ARCHIVE" --strip-components=1 -C "$DEST/source"
echo "$DEST/source"
