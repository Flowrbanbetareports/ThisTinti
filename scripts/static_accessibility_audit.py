#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILES = (ROOT / "app/static/index.html", ROOT / "site/index.html")


class AccessibilityParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html_lang = ""
        self.has_title = False
        self.in_title = False
        self.title_text: list[str] = []
        self.viewport = False
        self.main_count = 0
        self.aria_live_count = 0
        self.ids: set[str] = set()
        self.duplicate_ids: list[str] = []
        self.label_for: set[str] = set()
        self.label_depth = 0
        self.nested_labeled_controls: set[str] = set()
        self.controls: list[dict[str, str]] = []
        self.buttons: list[dict[str, Any]] = []
        self.button_stack: list[dict[str, Any]] = []
        self.issues: list[str] = []

    @staticmethod
    def _attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {name.lower(): value or "" for name, value in attrs}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        values = self._attrs(attrs)
        element_id = values.get("id", "").strip()
        if element_id:
            if element_id in self.ids:
                self.duplicate_ids.append(element_id)
            self.ids.add(element_id)

        if tag == "html":
            self.html_lang = values.get("lang", "").strip()
        elif tag == "title":
            self.in_title = True
        elif tag == "meta" and values.get("name", "").lower() == "viewport":
            self.viewport = bool(values.get("content", "").strip())
        elif tag == "main":
            self.main_count += 1

        if values.get("aria-live", "").lower() in {"polite", "assertive"}:
            self.aria_live_count += 1

        tabindex = values.get("tabindex", "").strip()
        if tabindex:
            try:
                if int(tabindex) > 0:
                    self.issues.append(f"tabindex positivo su <{tag}>#{element_id or '-'}")
            except ValueError:
                self.issues.append(f"tabindex non numerico su <{tag}>#{element_id or '-'}")

        if tag == "label":
            self.label_depth += 1
            target = values.get("for", "").strip()
            if target:
                self.label_for.add(target)

        if tag in {"input", "select", "textarea"}:
            control_type = values.get("type", "text").lower()
            if control_type not in {"hidden", "button", "submit", "reset", "image"}:
                self.controls.append(
                    {
                        "tag": tag,
                        "id": element_id,
                        "name": values.get("name", "").strip(),
                        "aria_label": values.get("aria-label", "").strip(),
                        "aria_labelledby": values.get("aria-labelledby", "").strip(),
                        "title": values.get("title", "").strip(),
                    }
                )
                if self.label_depth and element_id:
                    self.nested_labeled_controls.add(element_id)

        if tag == "button":
            button = {
                "id": element_id,
                "aria_label": values.get("aria-label", "").strip(),
                "aria_labelledby": values.get("aria-labelledby", "").strip(),
                "title": values.get("title", "").strip(),
                "text": [],
            }
            self.buttons.append(button)
            self.button_stack.append(button)

        if tag == "a" and values.get("target", "").lower() == "_blank":
            rel = {part.lower() for part in values.get("rel", "").split()}
            if "noopener" not in rel:
                self.issues.append(f"link target=_blank senza noopener: #{element_id or '-'}")

        if tag == "img" and "alt" not in values:
            self.issues.append(f"immagine senza attributo alt: #{element_id or '-'}")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self.in_title = False
            self.has_title = bool("".join(self.title_text).strip())
        elif tag == "label":
            self.label_depth = max(0, self.label_depth - 1)
        elif tag == "button" and self.button_stack:
            self.button_stack.pop()

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_text.append(data)
        if self.button_stack:
            self.button_stack[-1]["text"].append(data)

    def failures(self, *, require_live_region: bool) -> list[str]:
        failures = list(self.issues)
        if not self.html_lang:
            failures.append("attributo lang mancante su <html>")
        if not self.has_title:
            failures.append("titolo del documento mancante o vuoto")
        if not self.viewport:
            failures.append("meta viewport mancante")
        if self.main_count != 1:
            failures.append(f"atteso un solo elemento <main>, trovati {self.main_count}")
        if require_live_region and self.aria_live_count < 1:
            failures.append("regione aria-live mancante")
        failures.extend(f"ID duplicato: {element_id}" for element_id in sorted(set(self.duplicate_ids)))

        for control in self.controls:
            element_id = control["id"]
            named = bool(
                control["aria_label"]
                or control["aria_labelledby"]
                or control["title"]
                or (element_id and element_id in self.label_for)
                or (element_id and element_id in self.nested_labeled_controls)
            )
            if not element_id:
                failures.append(f"controllo <{control['tag']}> senza id")
            if not named:
                failures.append(f"controllo senza nome accessibile: <{control['tag']}>#{element_id or '-'}")

        for button in self.buttons:
            text = "".join(button["text"]).strip()
            if not (text or button["aria_label"] or button["aria_labelledby"] or button["title"]):
                failures.append(f"pulsante senza nome accessibile: #{button['id'] or '-'}")
        return failures


def audit_file(path: Path) -> dict[str, Any]:
    parser = AccessibilityParser()
    parser.feed(path.read_text(encoding="utf-8"))
    failures = parser.failures(require_live_region=path.as_posix().endswith("app/static/index.html"))
    return {
        "path": str(path.relative_to(ROOT)),
        "passed": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "metrics": {
            "main_count": parser.main_count,
            "control_count": len(parser.controls),
            "button_count": len(parser.buttons),
            "aria_live_count": parser.aria_live_count,
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic structural accessibility checks on ThisTinti HTML.")
    parser.add_argument("files", nargs="*", type=Path, help="HTML files; defaults to the app and public site entrypoints")
    parser.add_argument("--report", type=Path, help="Write a JSON report")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    files = tuple(path.resolve() for path in args.files) if args.files else DEFAULT_FILES
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        print(f"Accessibility audit inputs missing: {', '.join(missing)}", file=sys.stderr)
        return 2

    results = [audit_file(path) for path in files]
    report = {
        "schema": "thistinti.static-accessibility-audit.v1",
        "standard_target": "WCAG 2.2 AA",
        "passed": all(result["passed"] for result in results),
        "results": results,
        "limitations": [
            "Structural automation does not prove WCAG conformance.",
            "Keyboard, focus, contrast, reflow and assistive technology checks remain manual.",
        ],
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
