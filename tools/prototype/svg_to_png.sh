#!/usr/bin/env bash
# Renders every SVG in a folder to PNG with headless Firefox (no other converter needed).
# Usage: tools/prototype/svg_to_png.sh DIR
set -euo pipefail
dir=$(cd "$1" && pwd)
for f in "$dir"/*.svg; do
  size=$(python3 -c "import re,sys; s=open(sys.argv[1]).read(500); print(*[round(float(v)) for v in re.search(r'width=\"([\d.]+)\" height=\"([\d.]+)\"', s).groups()], sep=',')" "$f")
  profile=$(mktemp -d)
  timeout 90 firefox --headless --no-remote --profile "$profile" --window-size="$size" --screenshot "${f%.svg}.png" "file://$f" >/dev/null 2>&1
  rm -rf "$profile"
  echo "${f%.svg}.png"
done
