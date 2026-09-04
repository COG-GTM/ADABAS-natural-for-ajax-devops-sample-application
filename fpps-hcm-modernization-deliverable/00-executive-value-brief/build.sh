#!/usr/bin/env bash
# Rebuild the executive value brief (figure -> branded DOCX -> PDF).
#
# Requires: node (npx @mermaid-js/mermaid-cli), LibreOffice, pdftoppm, and a
# checkout of the Cognition collateral toolkit that provides the canonical
# template and builder:
#   RFP_REPO=/path/to/federal_RFP_responses  (default: ../../../federal-RFP-responses)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RFP_REPO="${RFP_REPO:-$HERE/../../../federal-RFP-responses}"
BUILDER="$RFP_REPO/scripts/build_cognition_docx.py"
TEMPLATE="$RFP_REPO/templates/_TEMPLATE - COPY THIS.docx"
OUT="$HERE/Cognition-FPPS-HCM-Executive-Value-Brief"

[ -f "$BUILDER" ] || { echo "builder not found: $BUILDER (set RFP_REPO)"; exit 1; }

# 1. Figures (Mermaid -> SVG/PNG; the PDF embeds the PNG)
for f in "$HERE"/diagrams/*.mmd; do
  npx -y @mermaid-js/mermaid-cli -i "$f" -o "${f%.mmd}.svg" -b white
  npx -y @mermaid-js/mermaid-cli -i "$f" -o "${f%.mmd}.png" -b white -s 3
done

# 2. Branded DOCX from the Markdown source
python3 "$BUILDER" \
  --template "$TEMPLATE" \
  --markdown "$HERE/executive-value-brief.md" \
  --out "$OUT.docx" \
  --title 'From Natural and ADABAS to Oracle HCM' \
  --subtitle 'A requirements-first modernization baseline — executive value brief for SMX and the Department of the Interior, Interior Business Center (FPPS)' \
  --presenter 'Prepared by Cognition AI, Inc.' \
  --date "$(date +'%B %Y')" \
  --footer-title 'FPPS → HCM executive value brief'

# 3. PDF
( cd "$HERE" && libreoffice --headless --convert-to pdf "$OUT.docx" >/dev/null )
echo "wrote $OUT.pdf"
