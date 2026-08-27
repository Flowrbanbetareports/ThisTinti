from pathlib import Path

path = Path("scripts/evaluate_dirty_public_semantics.py")
text = path.read_text(encoding="utf-8")
needle = "from collections import Counter\n"
if text.count(needle) != 1:
    raise SystemExit("Expected exactly one unused Counter import")
path.write_text(text.replace(needle, ""), encoding="utf-8")
