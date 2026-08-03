from __future__ import annotations

import re
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one occurrence, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    path = Path("app/static/operational-center.js")
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r"  async function downloadReport\(\) \{.*?\n  \}\n\n  async function enhanceCase", re.DOTALL)
    replacement = """  function downloadReport() {
    const reportWindow = window.open('/operational-report.html', '_blank', 'noopener');
    if (!reportWindow) {
      toast('Il browser ha bloccato la nuova scheda del rapporto. Consenti i popup locali e riprova.', true);
    }
  }

  async function enhanceCase"""
    updated, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise SystemExit(f"Expected one operational report function, found {count}")
    path.write_text(updated, encoding="utf-8")

    tests = Path("tests/test_operational_center_assets.py")
    text = tests.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '    assert "/api/operational/report" in script\n',
        "    assert \"window.open('/operational-report.html'\" in script\n",
        "operational report navigation assertion",
    )
    text = replace_once(
        text,
        '    assert "window.print()" in script\n',
        '    report_script = (ROOT / "app" / "static" / "operational-report.js").read_text(encoding="utf-8")\n'
        '    report_html = (ROOT / "app" / "static" / "operational-report.html").read_text(encoding="utf-8")\n'
        '    assert "window.print()" in report_script\n'
        "    assert \"fetch('/api/operational/report'\" in report_script\n"
        '    assert "onclick=" not in report_html\n'
        '    assert "http://" not in report_html and "https://" not in report_html\n',
        "report page assertions",
    )
    text = replace_once(
        text,
        '        "Correzione supervisionata",\n        "Tempo medio prima decisione",\n        "Non misurato",\n',
        '        "Correzione supervisionata",\n',
        "moved report phrases",
    )
    text = replace_once(
        text,
        '    for phrase in (\n        "Cosa controllare adesso",\n',
        '    report_script = (ROOT / "app" / "static" / "operational-report.js").read_text(encoding="utf-8")\n'
        '    assert "Tempo medio fino alla prima decisione" in report_script\n'
        '    assert "Non misurato" in report_script\n'
        '    for phrase in (\n        "Cosa controllare adesso",\n',
        "report phrase assertions",
    )
    tests.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
