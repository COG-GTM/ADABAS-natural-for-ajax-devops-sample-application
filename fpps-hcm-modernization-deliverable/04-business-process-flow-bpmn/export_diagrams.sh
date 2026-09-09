#!/usr/bin/env bash
# Export every ```mermaid block in process-flows.md to diagrams/<n>-<slug>.svg and .png
# using @mermaid-js/mermaid-cli. Renderer helper only; the Mermaid source in the
# Markdown remains the authoritative diagram.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/process-flows.md"
OUT="$HERE/diagrams"
mkdir -p "$OUT"
python3 - "$SRC" "$OUT" <<'PY'
import re, sys, pathlib
src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
text = src.read_text(encoding="utf-8")
slugs = ["p1-list-cruises", "p2-cruise-detail", "p3-customer-lookup-create-modify", "p4-book-cruise"]
blocks = re.findall(r"```mermaid\n(.*?)```", text, re.S)
assert len(blocks) == len(slugs), (len(blocks), len(slugs))
for slug, block in zip(slugs, blocks):
    (out / f"{slug}.mmd").write_text(block, encoding="utf-8")
PY
for f in "$OUT"/*.mmd; do
  base="${f%.mmd}"
  npx -y @mermaid-js/mermaid-cli -q -i "$f" -o "$base.svg" -b white
  npx -y @mermaid-js/mermaid-cli -q -i "$f" -o "$base.png" -b white -w 2200
done
ls -la "$OUT"
