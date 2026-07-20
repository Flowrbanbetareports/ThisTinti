from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().upper()
    text = re.sub(r"\b(TAGLIA|TG|SIZE|COLORE|COL|COLOR|ARTICOLO|ART|CODICE|COD|MODELLO|MOD)\b", " ", text)
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return " ".join(text.split())


def normalize_code(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", normalize_text(value))


def normalize_variant(value: str | None) -> str:
    return normalize_code(value)


def canonical_item_key(
    sku: str | None, description: str | None, color: str | None, size: str | None, lot: str | None = None
) -> str:
    base = normalize_code(sku) or normalize_text(description)
    parts = [base, normalize_variant(color), normalize_variant(size), normalize_variant(lot)]
    return "|".join(parts)


def item_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    a_parts = a.split("|")
    b_parts = b.split("|")
    base = SequenceMatcher(None, a_parts[0], b_parts[0]).ratio()
    variant_hits = 0
    variant_total = 0
    for av, bv in zip(a_parts[1:], b_parts[1:]):
        if av or bv:
            variant_total += 1
            if av == bv and av:
                variant_hits += 1
            elif not av or not bv:
                variant_hits += 0.35
    variant_score = (variant_hits / variant_total) if variant_total else 1.0
    return round(base * 0.72 + variant_score * 0.28, 4)
