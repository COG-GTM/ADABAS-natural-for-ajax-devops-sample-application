"""Every relative link and back-ticked repository path in the modernization
deliverable must resolve to a file or directory in this checkout.

Checked forms: Markdown links ``[text](path)`` and ``[text](path#anchor)``,
image links ``![alt](path)``, and back-ticked paths that start with ``../``,
``./``, ``docs/``, ``tests/``, ``tools/``, ``SunnyIslands/`` or
``fpps-hcm-modernization-deliverable/`` (glob characters are allowed and must
match at least one file; a trailing ``:12-40`` line citation is ignored).
External URLs, bare anchors and ``...`` placeholders are skipped.
"""

import glob
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = REPO_ROOT / "fpps-hcm-modernization-deliverable"

_ROOT_DIRS = ("docs/", "tests/", "tools/", "SunnyIslands/",
              "fpps-hcm-modernization-deliverable/")
_MD_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_TICK_PATH_RE = re.compile(
    r"`((?:\.\.?/|docs/|tests/|tools/|SunnyIslands/|"
    r"fpps-hcm-modernization-deliverable/)[^`\s]*)`")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _prose_lines(text):
    """Lines outside fenced code blocks."""
    fence = None
    for line in text.splitlines():
        m = _FENCE_RE.match(line)
        if m:
            fence = None if fence == m.group(1) else (fence or m.group(1))
            continue
        if fence is None:
            yield line


def _targets(md_file):
    for line in _prose_lines(md_file.read_text(encoding="utf-8")):
        for m in _MD_LINK_RE.finditer(line):
            yield m.group(1)
        for m in _TICK_PATH_RE.finditer(line):
            yield m.group(1)


def _resolves(md_file, target):
    if re.match(r"[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
        return True
    if "..." in target:  # placeholder in a convention, not a reference
        return True
    path = target.split("#", 1)[0]
    path = re.sub(r":\d+(?:-\d+)?$", "", path)  # ``file:12-40`` line citation
    base = REPO_ROOT if path.startswith(_ROOT_DIRS) else md_file.parent
    path = path.rstrip("/")
    if not path:
        return True
    candidate = (base / path)
    if candidate.exists():
        return True
    return bool(glob.glob(str(candidate)))


class DeliverableLinks(unittest.TestCase):
    def test_every_relative_reference_resolves(self):
        broken = []
        for md in sorted(PACKAGE.rglob("*.md")):
            for target in _targets(md):
                if not _resolves(md, target):
                    broken.append(f"{md.relative_to(REPO_ROOT)} -> {target}")
        self.assertEqual(broken, [], "\n" + "\n".join(broken))

    def test_package_has_hub_and_all_capability_directories(self):
        dirs = sorted(p.name for p in PACKAGE.iterdir() if p.is_dir())
        self.assertEqual([d[:2] for d in dirs], [f"{i:02d}" for i in range(11)])
        for d in dirs:
            self.assertTrue((PACKAGE / d / "README.md").is_file(), d)


if __name__ == "__main__":
    unittest.main()
