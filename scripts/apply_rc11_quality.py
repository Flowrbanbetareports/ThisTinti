from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one occurrence, found {count}")
    return text.replace(old, new, 1)


def patch_rules() -> None:
    path = Path("app/services/rules.py")
    text = path.read_text(encoding="utf-8")
    if "def _display_decimal(" not in text:
        marker = '''def _money(value: Decimal | int | float | str) -> Decimal:
    return _decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
'''
        block = marker + '''

def _display_decimal(value, *, max_places: int = 4) -> str:
    decimal_value = _decimal(value)
    quantum = Decimal("1").scaleb(-max_places)
    if decimal_value.as_tuple().exponent < -max_places:
        decimal_value = decimal_value.quantize(quantum, rounding=ROUND_HALF_UP)
    rendered = format(decimal_value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return "0" if rendered in {"-0", ""} else rendered
'''
        text = replace_once(text, marker, block, "decimal helper")
    text = replace_once(
        text,
        '"observed_value": str(observed) if observed is not None else None,\n        "expected_value": str(expected) if expected is not None else None,',
        '"observed_value": (\n            _display_decimal(observed) if isinstance(observed, Decimal) else str(observed)\n        )\n        if observed is not None\n        else None,\n        "expected_value": (\n            _display_decimal(expected) if isinstance(expected, Decimal) else str(expected)\n        )\n        if expected is not None\n        else None,',
        "evidence formatting",
    )
    replacements = {
        'f"{label}: quantità {commercial_label} {cq:g}, consegnata complessivamente {dq:g}."':
            'f"{label}: quantità {commercial_label} {_display_decimal(cq)}, "\n                    f"consegnata complessivamente {_display_decimal(dq)}."',
        'f"{label}: fatturate complessivamente {iq:g}, riferimento disponibile {expected_for_invoice:g}."':
            'f"{label}: fatturate complessivamente {_display_decimal(iq)}, "\n                    f"riferimento disponibile {_display_decimal(expected_for_invoice)}."',
        'f"{label}: sconto medio {commercial_label} {cd:.2f}%, sconto medio fattura {idis:.2f}%."':
            'f"{label}: sconto medio {commercial_label} {_display_decimal(cd, max_places=2)}%, "\n                    f"sconto medio fattura {_display_decimal(idis, max_places=2)}%."',
        'f"{label}: aliquota media {commercial_label} {ctax:.2f}%, aliquota media fattura {itax:.2f}%."':
            'f"{label}: aliquota media {commercial_label} {_display_decimal(ctax, max_places=2)}%, "\n                    f"aliquota media fattura {_display_decimal(itax, max_places=2)}%."',
        'f"{label}: reso complessivo di {rqty:g} unità senza nota di credito nella catena."':
            'f"{label}: reso complessivo di {_display_decimal(rqty)} unità "\n                        "senza nota di credito nella catena."',
        'f"{label}: reso complessivo {rqty:g}, accreditato complessivamente {cqty:g}."':
            'f"{label}: reso complessivo {_display_decimal(rqty)}, "\n                        f"accreditato complessivamente {_display_decimal(cqty)}."',
    }
    for old, new in replacements.items():
        if old in text:
            text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")


def patch_loader() -> None:
    path = Path("app/static/app.js")
    text = path.read_text(encoding="utf-8")
    if "'/operational-learning.css'" not in text:
        text = replace_once(
            text,
            "    '/operational-center.css',\n",
            "    '/operational-center.css',\n    '/operational-learning.css',\n",
            "learning stylesheet",
        )
    if "loadScript('/operational-learning.js')" not in text:
        text = replace_once(
            text,
            "    .then(() => loadScript('/operational-center.js'))\n",
            "    .then(() => loadScript('/operational-center.js'))\n"
            "    .then(() => loadScript('/operational-learning.js'))\n",
            "learning script",
        )
    path.write_text(text, encoding="utf-8")


def patch_experience_workflow() -> None:
    path = Path(".github/workflows/simplified-experience.yml")
    text = path.read_text(encoding="utf-8")
    path_marker = '      - "app/static/product-polish.css"\n'
    additions = (
        path_marker
        + '      - "app/static/operational-center.js"\n'
        + '      - "app/static/operational-center.css"\n'
        + '      - "app/static/operational-learning.js"\n'
        + '      - "app/static/operational-learning.css"\n'
        + '      - "tests/test_operational_center_assets.py"\n'
        + '      - "scripts/check_operational_center_browser.py"\n'
    )
    occurrences = text.count(path_marker)
    if occurrences == 2 and '      - "app/static/operational-center.js"\n' not in text:
        text = text.replace(path_marker, additions)
    elif occurrences != 2 and '      - "app/static/operational-center.js"\n' not in text:
        raise SystemExit(f"experience paths: expected two markers, found {occurrences}")
    if "          node --check app/static/operational-center.js\n" not in text:
        text = replace_once(
            text,
            "          node --check app/static/product-polish.js\n",
            "          node --check app/static/product-polish.js\n"
            "          node --check app/static/operational-center.js\n"
            "          node --check app/static/operational-learning.js\n",
            "node checks",
        )
    if "Verify operational center in Chromium" not in text:
        text = replace_once(
            text,
            "      - name: Verify recovery workflow in Chromium\n",
            "      - name: Verify operational center in Chromium\n"
            "        run: python scripts/check_operational_center_browser.py\n"
            "      - name: Verify recovery workflow in Chromium\n",
            "browser step",
        )
    if "            tests/test_operational_center_assets.py \\\n" not in text:
        text = replace_once(
            text,
            "            tests/test_product_quality_pass.py \\\n",
            "            tests/test_product_quality_pass.py \\\n"
            "            tests/test_operational_center_assets.py \\\n",
            "pytest assets",
        )
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    patch_rules()
    patch_loader()
    patch_experience_workflow()
