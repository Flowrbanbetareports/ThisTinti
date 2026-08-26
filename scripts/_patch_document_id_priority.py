from pathlib import Path

path = Path("app/parsers/pdf_text.py")
text = path.read_text(encoding="utf-8")
old = 'candidates.append((4, candidate, "explicit_label"))'
new = 'candidates.append((6, candidate, "explicit_label"))'
if text.count(old) != 1:
    raise SystemExit("Expected exactly one explicit-label score to patch")
path.write_text(text.replace(old, new), encoding="utf-8")
