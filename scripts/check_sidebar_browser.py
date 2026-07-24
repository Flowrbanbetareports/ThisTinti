from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def browser_executable() -> str | None:
    configured = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
    if configured and Path(configured).is_file():
        return configured
    for candidate in ("google-chrome", "chromium", "chromium-browser"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def build_document() -> str:
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    body = index.split("<body>", 1)[1].split("</body>", 1)[0]
    body = re.sub(r'<script src="/app\.js(?:\?v=[^"]+)?" defer></script>', "", body)
    css = "\n".join(
        (STATIC / name).read_text(encoding="utf-8")
        for name in (
            "styles-original.css",
            "styles.css",
            "onboarding.css",
            "sidebar-scroll.css",
            "local-first-run.css",
        )
    ).replace('@import url("/styles-original.css");', "")
    scripts = "\n".join(
        f"<script>{(STATIC / name).read_text(encoding='utf-8')}</script>"
        for name in ("onboarding.js", "sidebar-scroll.js")
    )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<style>{css}</style></head><body>{body}{scripts}</body></html>"
    )


def main() -> None:
    document = build_document()
    executable = browser_executable()
    with sync_playwright() as playwright:
        launch_args = {"headless": True}
        if executable:
            launch_args["executable_path"] = executable
        browser = playwright.chromium.launch(**launch_args)
        page = browser.new_page(viewport={"width": 1380, "height": 700})
        page.set_content(document, wait_until="load")
        page.evaluate(
            """() => {
              document.querySelector('#authView').classList.add('hidden');
              document.querySelector('#appView').classList.remove('hidden');
              document.querySelector('#advancedNavPanel').classList.add('open');
              document.querySelector('#advancedNavToggle').classList.add('open');
            }"""
        )
        page.wait_for_timeout(100)
        before = page.evaluate(
            """() => {
              const nav = document.querySelector('.nav-list');
              const panel = document.querySelector('#advancedNavPanel');
              return {
                clientHeight: nav.clientHeight,
                scrollHeight: nav.scrollHeight,
                scrollTop: nav.scrollTop,
                panelClientHeight: panel.clientHeight,
                panelScrollHeight: panel.scrollHeight,
                pageScrollTop: window.scrollY,
              };
            }"""
        )
        if before["scrollHeight"] <= before["clientHeight"]:
            raise SystemExit(f"Sidebar has no real overflow: {before}")
        if before["panelClientHeight"] < before["panelScrollHeight"]:
            raise SystemExit(f"Advanced navigation is internally clipped: {before}")

        gesture = page.evaluate(
            """() => {
              const sidebar = document.querySelector('.sidebar');
              const nav = document.querySelector('.nav-list');
              const event = new WheelEvent('wheel', {
                deltaY: 120,
                deltaMode: WheelEvent.DOM_DELTA_PIXEL,
                bubbles: true,
                cancelable: true,
              });
              const dispatched = sidebar.dispatchEvent(event);
              return {
                dispatched,
                prevented: event.defaultPrevented,
                scrollTop: nav.scrollTop,
                pageScrollTop: window.scrollY,
              };
            }"""
        )
        browser.close()

    if not gesture["prevented"] or gesture["scrollTop"] <= 0:
        raise SystemExit(f"Touchpad-equivalent gesture did not scroll sidebar: {gesture}")
    if gesture["pageScrollTop"] != 0:
        raise SystemExit(f"Workspace moved while scrolling sidebar: {gesture}")
    print(json.dumps({"before": before, "gesture": gesture}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
