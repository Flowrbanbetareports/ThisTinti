from __future__ import annotations

import re
from collections import defaultdict
from difflib import SequenceMatcher
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import Document, DocumentLine, ItemAlias, OperationChain
from .normalizer import normalize_code, normalize_text, normalize_variant

_COLOR_ALIASES = {
    "NAVY": "BLU",
    "BLUE": "BLU",
    "BLUENAVY": "BLU",
    "NERO": "NERO",
    "BLACK": "NERO",
    "BIANCO": "BIANCO",
    "WHITE": "BIANCO",
    "GRIGIO": "GRIGIO",
    "GREY": "GRIGIO",
    "GRAY": "GRIGIO",
    "ROSSO": "ROSSO",
    "RED": "ROSSO",
    "VERDE": "VERDE",
    "GREEN": "VERDE",
    "BEIGE": "BEIGE",
    "MARRONE": "MARRONE",
    "BROWN": "MARRONE",
}


def _normalized_color(value: str | None) -> str:
    normalized = normalize_variant(value)
    return _COLOR_ALIASES.get(normalized, normalized)


def _normalized_size(value: str | None) -> str:
    normalized = normalize_variant(value)
    return normalized.removeprefix("EU").removeprefix("IT")


def _numeric_tokens(value: str | None) -> set[str]:
    return {token for token in re.findall(r"\d+", normalize_text(value)) if len(token) >= 2}


def _word_tokens(value: str | None) -> set[str]:
    return {token for token in normalize_text(value).split() if len(token) >= 3 and not token.isdigit()}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def line_similarity(a: DocumentLine, b: DocumentLine) -> float:
    """Conservative explainable similarity between two commercial document lines."""
    if a.canonical_key and a.canonical_key == b.canonical_key:
        return 1.0

    for left, right in (
        (_normalized_color(a.color), _normalized_color(b.color)),
        (_normalized_size(a.size), _normalized_size(b.size)),
        (normalize_variant(a.lot), normalize_variant(b.lot)),
    ):
        if left and right and left != right:
            return 0.0

    a_sku, b_sku = normalize_code(a.sku), normalize_code(b.sku)
    a_desc, b_desc = normalize_text(a.description), normalize_text(b.description)
    sku_ratio = SequenceMatcher(None, a_sku, b_sku).ratio() if a_sku and b_sku else 0.0
    desc_ratio = SequenceMatcher(None, a_desc, b_desc).ratio() if a_desc and b_desc else 0.0
    word_overlap = _jaccard(_word_tokens(a.description), _word_tokens(b.description))
    a_sku_numbers, b_sku_numbers = _numeric_tokens(a.sku), _numeric_tokens(b.sku)
    if a_sku_numbers and b_sku_numbers:
        numeric_overlap = bool(a_sku_numbers & b_sku_numbers)
    elif not a_sku or not b_sku:
        numeric_overlap = bool(
            (_numeric_tokens(a.sku) | _numeric_tokens(a.description))
            & (_numeric_tokens(b.sku) | _numeric_tokens(b.description))
        )
    else:
        numeric_overlap = False

    if a_sku and b_sku and a_sku == b_sku:
        score = 0.99
    elif a_sku and b_sku and min(len(a_sku), len(b_sku)) >= 4 and (a_sku in b_sku or b_sku in a_sku):
        score = 0.95
    elif numeric_overlap and max(desc_ratio, word_overlap) >= 0.50:
        score = 0.93 + min(0.04, max(desc_ratio, word_overlap) * 0.04)
    else:
        score = sku_ratio * 0.62 + max(desc_ratio, word_overlap) * 0.38

    # Different explicit SKUs without shared numeric evidence require a very strong textual match.
    if a_sku and b_sku and not numeric_overlap and sku_ratio < 0.78:
        score = min(score, 0.84 if max(desc_ratio, word_overlap) > 0.90 else 0.72)
    return round(max(0.0, min(1.0, score)), 4)


def alias_tokens(line: DocumentLine) -> list[str]:
    values = [normalize_code(line.sku), normalize_text(line.description)]
    return [value for value in dict.fromkeys(values) if value]


def _alias_map(db: Session, tenant_id: str, supplier_ids: set[str | None]) -> dict[tuple[str | None, str], str]:
    stmt = select(ItemAlias).where(ItemAlias.tenant_id == tenant_id)
    non_null = {supplier_id for supplier_id in supplier_ids if supplier_id}
    if non_null:
        stmt = stmt.where(or_(ItemAlias.supplier_id.in_(non_null), ItemAlias.supplier_id.is_(None)))
    else:
        stmt = stmt.where(ItemAlias.supplier_id.is_(None))
    aliases = list(db.scalars(stmt))
    result: dict[tuple[str | None, str], str] = {}
    for alias in aliases:
        result[(alias.supplier_id, alias.normalized_alias)] = alias.canonical_key
    return result


def _resolved_key(line: DocumentLine, supplier_id: str | None, aliases: dict[tuple[str | None, str], str]) -> str:
    for token in alias_tokens(line):
        if (supplier_id, token) in aliases:
            return aliases[(supplier_id, token)]
        if (None, token) in aliases:
            return aliases[(None, token)]
    return line.canonical_key or f"line:{line.id}"


def group_chain_lines(
    db: Session,
    chain: OperationChain,
    documents_by_role: dict[str, list[Document]],
    *,
    fuzzy_threshold: float = 0.90,
) -> dict[str, dict[str, list[DocumentLine]]]:
    entries: list[tuple[str, Document, DocumentLine, str]] = []
    suppliers = {document.supplier_id for documents in documents_by_role.values() for document in documents}
    aliases = _alias_map(db, chain.tenant_id, suppliers)
    for role, documents in documents_by_role.items():
        for document in documents:
            for line in document.lines:
                entries.append((role, document, line, _resolved_key(line, document.supplier_id, aliases)))

    parent = list(range(len(entries)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    exact: dict[str, int] = {}
    for index, (_, _, _, resolved) in enumerate(entries):
        if resolved in exact:
            union(index, exact[resolved])
        else:
            exact[resolved] = index

    for left in range(len(entries)):
        left_role, left_document, left_line, _ = entries[left]
        for right in range(left + 1, len(entries)):
            if find(left) == find(right):
                continue
            right_role, right_document, right_line, _ = entries[right]
            if left_document.id == right_document.id or left_role == right_role:
                continue
            if line_similarity(left_line, right_line) >= fuzzy_threshold:
                union(left, right)

    cluster_keys: dict[int, str] = {}
    for index, (_, _, line, resolved) in enumerate(entries):
        root = find(index)
        candidate = resolved or line.canonical_key or f"line:{line.id}"
        current = cluster_keys.get(root)
        if current is None or (candidate.count("|") > current.count("|")) or (len(candidate) < len(current)):
            cluster_keys[root] = candidate

    grouped: dict[str, dict[str, list[DocumentLine]]] = {role: defaultdict(list) for role in documents_by_role}
    for index, (role, _, line, _) in enumerate(entries):
        grouped[role][cluster_keys[find(index)]].append(line)
    return {role: dict(groups) for role, groups in grouped.items()}
