#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected patch marker not found in {path}: {old[:100]!r}")
    if text.count(old) != 1:
        raise RuntimeError(f"Patch marker is not unique in {path}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_pdf_parser() -> None:
    path = ROOT / "app/parsers/pdf_text.py"
    helpers = dedent(
        r'''
        MONEY_TOKEN_RE = re.compile(
            r"(?<!\w)(?:US\s*)?\$\s*[0-9OIl][0-9OIl.,? ]*[0-9OIl](?!\w)",
            re.IGNORECASE,
        )
        STRONG_DOCUMENT_ID_RE = re.compile(
            r"\b(?:QUO|INV|INVOICE|PO|ORD|ORDER)[-_/][A-Z0-9][A-Z0-9._/-]{2,80}\b",
            re.IGNORECASE,
        )
        LABELLED_DOCUMENT_ID_RE = re.compile(
            r"(?:^|\n)\s*(?:QUOTE|QUOTATION|INVOICE|DOCUMENT|DOCUMENTO|NUMERO|NUMBER)"
            r"\s*(?:#|NO\.?|N\.?|NUMBER|NUMERO)?\s*[:=-]?\s*"
            r"([A-Z0-9][A-Z0-9._/'~-]{2,80})",
            re.IGNORECASE,
        )


        def _normalize_document_id(value: str) -> str | None:
            normalized = unicodedata.normalize("NFKC", value).upper().strip()
            normalized = normalized.replace("–", "-").replace("—", "-").replace("~", "-")
            normalized = normalized.replace("'", "").replace('"', "")
            normalized = re.sub(r"^[^A-Z0-9]+|[^A-Z0-9]+$", "", normalized)
            normalized = re.sub(r"-{2,}", "-", normalized)
            if not re.fullmatch(r"[A-Z0-9][A-Z0-9._/-]{2,80}", normalized):
                return None
            if not re.search(r"[A-Z]", normalized) or not re.search(r"\d", normalized):
                return None
            return normalized


        def _extract_document_number(text: str) -> tuple[str | None, dict[str, Any]]:
            candidates: list[tuple[int, str, str]] = []
            for match in STRONG_DOCUMENT_ID_RE.finditer(text):
                candidate = _normalize_document_id(match.group(0))
                if candidate:
                    candidates.append((5, candidate, "strong_business_id"))
            for match in LABELLED_DOCUMENT_ID_RE.finditer(text):
                candidate = _normalize_document_id(match.group(1))
                if candidate:
                    candidates.append((4, candidate, "explicit_label"))

            if not candidates:
                return None, {"status": "abstained", "reason": "no_reliable_candidate", "candidates": []}

            best_score = max(score for score, _, _ in candidates)
            best = [(value, source) for score, value, source in candidates if score == best_score]
            counts: dict[str, int] = {}
            for value, _ in best:
                counts[value] = counts.get(value, 0) + 1
            top_count = max(counts.values())
            winners = sorted(value for value, count in counts.items() if count == top_count)
            if len(winners) != 1:
                return None, {
                    "status": "abstained",
                    "reason": "conflicting_candidates",
                    "candidates": [value for _, value, _ in candidates],
                }
            winner = winners[0]
            source = next(source for value, source in best if value == winner)
            return winner, {
                "status": "recognized",
                "source": source,
                "score": best_score,
                "candidates": [value for _, value, _ in candidates],
            }


        def _extract_currency(text: str) -> tuple[str, dict[str, Any]]:
            upper = text.upper()
            usd_explicit = bool(re.search(r"\bUSD\b|\bUS\s*DOLLARS?\b|US\s*\$", upper))
            eur_explicit = bool(re.search(r"\bEUR\b|\bEURO\b|€", upper))
            dollar_symbol = "$" in text
            if usd_explicit or (dollar_symbol and not eur_explicit):
                if eur_explicit:
                    return "UNK", {"status": "abstained", "reason": "conflicting_currency_evidence"}
                return "USD", {
                    "status": "recognized",
                    "source": "explicit_usd" if usd_explicit else "unambiguous_dollar_symbol",
                }
            if eur_explicit:
                return "EUR", {"status": "recognized", "source": "explicit_eur"}
            return "UNK", {"status": "abstained", "reason": "no_currency_evidence"}


        def _money_decimal(token: str) -> Decimal | None:
            cleaned = token.upper().replace("US", "").replace("$", "").replace(" ", "")
            cleaned = cleaned.translate(str.maketrans({"O": "0", "I": "1", "L": "1"}))
            cleaned = re.sub(r"[^0-9.,]", "", cleaned)
            if not cleaned or not re.search(r"\d", cleaned):
                return None
            separators = [index for index, char in enumerate(cleaned) if char in ",."]
            if separators:
                last = separators[-1]
                decimals = len(cleaned) - last - 1
                if decimals == 2:
                    integer = re.sub(r"[.,]", "", cleaned[:last]) or "0"
                    cleaned = f"{integer}.{cleaned[last + 1:]}"
                else:
                    cleaned = re.sub(r"[.,]", "", cleaned)
            try:
                value = Decimal(cleaned)
            except Exception:
                return None
            if not value.is_finite() or value < 0:
                return None
            return value


        def _money_values(line: str) -> list[Decimal]:
            values: list[Decimal] = []
            for match in MONEY_TOKEN_RE.finditer(line):
                value = _money_decimal(match.group(0))
                if value is not None:
                    values.append(value)
            return values


        def _business_line(
            *,
            line_no: int,
            quantity: Decimal,
            description: str,
            unit_price: Decimal,
            source_total: Decimal | None,
            used_ocr: bool,
            extraction_method: object,
            source: str,
        ) -> ParsedLine:
            derived = quantity * unit_price
            delta = None if source_total is None else abs(source_total - derived)
            consistent = None if delta is None else delta <= max(TOTAL_TOLERANCE, derived * Decimal("0.02"))
            confidence = 0.52 if used_ocr else 0.68
            if consistent is True:
                confidence += 0.05
            elif consistent is False:
                confidence -= 0.15
            return ParsedLine(
                line_no=line_no,
                description=re.sub(r"\s+", " ", description).strip()[:1000],
                quantity=quantity,
                unit_price=unit_price,
                line_total=derived,
                confidence=max(0.20, min(confidence, 0.78)),
                raw={
                    "extraction_method": extraction_method,
                    "line_extraction_method": source,
                    "source_line_total": None if source_total is None else str(source_total),
                    "derived_line_total": str(derived),
                    "line_total_consistent": consistent,
                    "numeric_provenance": {
                        "quantity": "source",
                        "unit_price": "source",
                        "price_base_quantity": "defaulted",
                        "discount_rate": "missing",
                        "tax_rate": "missing",
                        "line_total": "derived_checked_against_source" if source_total is not None else "derived",
                    },
                },
            )


        def _extract_business_rows(
            text: str,
            *,
            used_ocr: bool,
            extraction_method: object,
        ) -> list[ParsedLine]:
            parsed: list[ParsedLine] = []
            pending: list[tuple[int, Decimal, str]] = []
            price_rows: list[tuple[int, list[Decimal]]] = []
            for line_no, raw_line in enumerate(text.splitlines(), start=1):
                line = re.sub(r"\s+", " ", raw_line).strip()
                if not line:
                    continue
                item = re.match(r"^(\d{1,5})\s+(?![.\d])(.{4,})$", line)
                if not item:
                    continue
                quantity = Decimal(item.group(1))
                remainder = item.group(2).strip()
                amounts = _money_values(remainder)
                description = MONEY_TOKEN_RE.sub(" ", remainder)
                description = re.sub(r"\s+", " ", description).strip(" -|.")
                if amounts and description:
                    unit_price = amounts[-2] if len(amounts) >= 2 else amounts[-1]
                    source_total = amounts[-1] if len(amounts) >= 2 else None
                    parsed.append(
                        _business_line(
                            line_no=line_no,
                            quantity=quantity,
                            description=description,
                            unit_price=unit_price,
                            source_total=source_total,
                            used_ocr=used_ocr,
                            extraction_method=extraction_method,
                            source="ocr_inline_business_row",
                        )
                    )
                elif not amounts and len(description) >= 6:
                    pending.append((line_no, quantity, description))

            if parsed:
                return parsed

            for line_no, raw_line in enumerate(text.splitlines(), start=1):
                amounts = _money_values(raw_line)
                if len(amounts) >= 2:
                    price_rows.append((line_no, amounts))
            if not pending or len(price_rows) < len(pending):
                return []
            for (line_no, quantity, description), (_, amounts) in zip(pending, price_rows, strict=False):
                unit_price = amounts[-2]
                source_total = amounts[-1]
                parsed.append(
                    _business_line(
                        line_no=line_no,
                        quantity=quantity,
                        description=description,
                        unit_price=unit_price,
                        source_total=source_total,
                        used_ocr=used_ocr,
                        extraction_method=extraction_method,
                        source="ocr_aligned_business_rows",
                    )
                )
            return parsed
        '''
    ).strip()
    text = path.read_text(encoding="utf-8")
    if "def _extract_document_number(" not in text:
        marker = "\n\ndef parse_pdf(path: Path, overrides: dict) -> ParsedDocument:\n"
        if marker not in text:
            raise RuntimeError("parse_pdf marker missing")
        text = text.replace(marker, f"\n\n{helpers}\n\n\ndef parse_pdf(path: Path, overrides: dict) -> ParsedDocument:\n", 1)

    old = '''    number_match = re.search(r"(?:NUMERO|N\\.?|DOCUMENTO)\\s*[:#-]?\\s*([A-Z0-9/_-]{2,})", text, re.I)\n    date_match = re.search(r"\\b(\\d{2}[/-]\\d{2}[/-]\\d{4}|\\d{4}-\\d{2}-\\d{2})\\b", text)\n    base_confidence = 0.45 if used_ocr else 0.58\n'''
    new = '''    number_value, number_metadata = _extract_document_number(text)\n    currency_value, currency_metadata = _extract_currency(text)\n    date_match = re.search(r"\\b(\\d{2}[/-]\\d{2}[/-]\\d{4}|\\d{4}-\\d{2}-\\d{2})\\b", text)\n    base_confidence = 0.45 if used_ocr else 0.58\n'''
    if old in text:
        text = text.replace(old, new, 1)
    elif "number_value, number_metadata = _extract_document_number(text)" not in text:
        raise RuntimeError("number extraction marker missing")

    old = '''        number=overrides.get("number") or (number_match.group(1) if number_match else None),\n        document_date=parse_date(overrides.get("document_date") or (date_match.group(1) if date_match else None)),\n        supplier_name=overrides.get("supplier_name") or _extract_supplier(text),\n        references=references,\n        confidence=base_confidence,\n        metadata={**extraction_metadata, "text_preview": text[:1000]},\n'''
    new = '''        number=overrides.get("number") or number_value,\n        document_date=parse_date(overrides.get("document_date") or (date_match.group(1) if date_match else None)),\n        currency=overrides.get("currency") or currency_value,\n        supplier_name=overrides.get("supplier_name") or _extract_supplier(text),\n        references=references,\n        confidence=base_confidence,\n        metadata={\n            **extraction_metadata,\n            "text_preview": text[:1000],\n            "document_number_recognition": number_metadata,\n            "currency_recognition": currency_metadata,\n        },\n'''
    if old in text:
        text = text.replace(old, new, 1)
    elif '"document_number_recognition": number_metadata' not in text:
        raise RuntimeError("ParsedDocument marker missing")

    marker = '''    if not doc.lines and doc.document_type == "payment":\n'''
    addition = '''    if not doc.lines and doc.document_type != "payment":\n        business_lines = _extract_business_rows(\n            text,\n            used_ocr=used_ocr,\n            extraction_method=extraction_metadata["extraction_method"],\n        )\n        if business_lines:\n            doc.lines.extend(business_lines)\n            doc.metadata["line_extraction_method"] = business_lines[0].raw["line_extraction_method"]\n            doc.metadata["business_line_count"] = len(business_lines)\n\n'''
    if addition not in text:
        if marker not in text:
            raise RuntimeError("business-row insertion marker missing")
        text = text.replace(marker, addition + marker, 1)

    path.write_text(text, encoding="utf-8")


def patch_benchmark_metrics() -> None:
    path = ROOT / "scripts/run_dirty_public_corpus.py"
    text = path.read_text(encoding="utf-8")
    if "def field_assertions(" not in text:
        marker = "\n\ndef evaluate_parse(parsed: Any, expected: dict[str, Any]) -> list[str]:\n"
        helper = dedent(
            '''
            def field_assertions(parsed: Any, expected: dict[str, Any]) -> list[dict[str, Any]]:
                checks: list[dict[str, Any]] = []
                for field in ("document_type", "number", "currency"):
                    if field not in expected:
                        continue
                    expected_value = expected[field]
                    observed = getattr(parsed, field)
                    status = "correct" if observed == expected_value else ("abstained" if observed in {None, "", "UNK"} else "wrong_non_null")
                    checks.append({"field": field, "expected": expected_value, "observed": observed, "status": status})
                if "minimum_lines" in expected:
                    minimum = int(expected["minimum_lines"])
                    observed_lines = len(parsed.lines)
                    checks.append(
                        {
                            "field": "line_count_minimum",
                            "expected": minimum,
                            "observed": observed_lines,
                            "status": "correct" if observed_lines >= minimum else "abstained" if observed_lines == 0 else "wrong_non_null",
                        }
                    )
                if expected.get("number_present") and "number" not in expected:
                    checks.append(
                        {
                            "field": "number_present",
                            "expected": True,
                            "observed": bool(parsed.number),
                            "status": "correct" if parsed.number else "abstained",
                        }
                    )
                return checks
            '''
        ).strip()
        if marker not in text:
            raise RuntimeError("evaluate_parse marker missing")
        text = text.replace(marker, f"\n\n{helper}\n\n\ndef evaluate_parse(parsed: Any, expected: dict[str, Any]) -> list[str]:\n", 1)

    old = '''        result["parse"] = parsed_summary(parsed)\n'''
    new = '''        result["parse"] = parsed_summary(parsed)\n        result["field_assertions"] = field_assertions(parsed, expected) if outcome == "parse" else []\n'''
    if old in text and "result[\"field_assertions\"] = field_assertions" not in text:
        text = text.replace(old, new, 1)

    old = '''        "expectation_failures": [],\n    }\n'''
    new = '''        "expectation_failures": [],\n        "field_assertions": [],\n    }\n'''
    if old in text and '"field_assertions": []' not in text:
        text = text.replace(old, new, 1)

    old = '''    characterization_cases = [\n        item for item in cases if item["expectation_mode"] == "characterize"\n    ]\n\n    frozen = bool(manifest.get("frozen"))\n'''
    new = '''    characterization_cases = [\n        item for item in cases if item["expectation_mode"] == "characterize"\n    ]\n    assertion_fields = [\n        check\n        for item in assertion_cases\n        for check in item.get("field_assertions", [])\n    ]\n    field_status_counts = Counter(check["status"] for check in assertion_fields)\n    field_total = len(assertion_fields)\n    field_correct = field_status_counts.get("correct", 0)\n    field_wrong_non_null = field_status_counts.get("wrong_non_null", 0)\n    field_abstentions = field_status_counts.get("abstained", 0)\n\n    frozen = bool(manifest.get("frozen"))\n'''
    if old in text:
        text = text.replace(old, new, 1)
    elif "field_status_counts = Counter" not in text:
        raise RuntimeError("metrics marker missing")

    old = '''            "parse_status_counts": dict(parse_status_counts),\n            "gate_passed": gate_passed,\n'''
    new = '''            "parse_status_counts": dict(parse_status_counts),\n            "asserted_field_count": field_total,\n            "asserted_field_correct": field_correct,\n            "asserted_field_wrong_non_null": field_wrong_non_null,\n            "asserted_field_abstentions": field_abstentions,\n            "asserted_field_accuracy": round(field_correct / field_total, 6) if field_total else None,\n            "wrong_non_null_rate": round(field_wrong_non_null / field_total, 6) if field_total else None,\n            "abstention_rate": round(field_abstentions / field_total, 6) if field_total else None,\n            "gate_passed": gate_passed,\n'''
    if old in text:
        text = text.replace(old, new, 1)
    elif '"asserted_field_count": field_total' not in text:
        raise RuntimeError("report metrics marker missing")

    old = '''- structured rejections: **{metrics['parse_status_counts'].get('parse_error', 0)}**\n- gate: **{gate}**\n'''
    new = '''- structured rejections: **{metrics['parse_status_counts'].get('parse_error', 0)}**\n- asserted fields correct: **{metrics['asserted_field_correct']}/{metrics['asserted_field_count']}**\n- wrong non-null asserted fields: **{metrics['asserted_field_wrong_non_null']}**\n- asserted-field abstentions: **{metrics['asserted_field_abstentions']}**\n- wrong non-null rate: **{metrics['wrong_non_null_rate']}**\n- abstention rate: **{metrics['abstention_rate']}**\n- gate: **{gate}**\n'''
    if old in text:
        text = text.replace(old, new, 1)

    old = '''            "profile": parsed.metadata.get("profile"),\n        },\n'''
    new = '''            "profile": parsed.metadata.get("profile"),\n            "document_number_recognition": parsed.metadata.get("document_number_recognition"),\n            "currency_recognition": parsed.metadata.get("currency_recognition"),\n            "line_extraction_method": parsed.metadata.get("line_extraction_method"),\n        },\n'''
    if old in text:
        text = text.replace(old, new, 1)

    path.write_text(text, encoding="utf-8")


def patch_windows_ocr_smoke() -> None:
    path = ROOT / "scripts/local_distribution_smoke.py"
    text = path.read_text(encoding="utf-8")
    if 'report["ocr"]' in text:
        return
    marker = '''        if len(original_documents) != 1:\n            raise RuntimeError(f"Expected one document, got {len(original_documents)}")\n\n        exported = client.get("/api/export", headers=auth)\n'''
    addition = '''        if len(original_documents) != 1:\n            raise RuntimeError(f"Expected one document, got {len(original_documents)}")\n\n        ocr_sample = ROOT / "samples" / "ocr_invoice.pdf"\n        with ocr_sample.open("rb") as source:\n            queued_ocr = client.post(\n                "/api/jobs/documents",\n                headers={**auth, "Idempotency-Key": "local-distribution-smoke-ocr-invoice"},\n                files={"file": ("ocr_invoice.pdf", source, "application/pdf")},\n                data={"document_type": "invoice"},\n            )\n        queued_ocr.raise_for_status()\n        ocr_job_id = queued_ocr.json()["job"]["id"]\n        ocr_job = wait_json(\n            client,\n            f"/api/jobs/{ocr_job_id}",\n            lambda response, payload: response.status_code == 200 and payload.get("status") in {"completed", "failed"},\n            timeout=120.0,\n            watched=[("server", server, logs / "server.log"), ("worker", worker, logs / "worker.log")],\n        )\n        if ocr_job["status"] != "completed":\n            raise RuntimeError(\n                f"Frozen local OCR job failed: {ocr_job}\\n"\n                f"{process_diagnostics([('worker', worker, logs / 'worker.log')])}"\n            )\n        ocr_documents_response = client.get("/api/documents", headers=auth)\n        ocr_documents_response.raise_for_status()\n        ocr_documents = [\n            item for item in ocr_documents_response.json() if item.get("source_filename") == "ocr_invoice.pdf"\n        ]\n        if len(ocr_documents) != 1:\n            raise RuntimeError(f"Expected exactly one OCR smoke document, got {len(ocr_documents)}")\n        ocr_document = ocr_documents[0]\n        if ocr_document.get("document_type") != "invoice" or ocr_document.get("number") != "INV-OCR-123":\n            raise RuntimeError(f"Frozen Windows OCR extraction mismatch: {ocr_document}")\n        report["ocr"] = {\n            "job": ocr_job["status"],\n            "document_type": ocr_document.get("document_type"),\n            "number": ocr_document.get("number"),\n            "line_count": ocr_document.get("line_count"),\n        }\n\n        exported = client.get("/api/export", headers=auth)\n'''
    if marker not in text:
        raise RuntimeError("local distribution smoke insertion marker missing")
    path.write_text(text.replace(marker, addition, 1), encoding="utf-8")


def write_tests() -> None:
    path = ROOT / "tests/test_pdf_semantics.py"
    path.write_text(
        dedent(
            '''
            from __future__ import annotations

            from pathlib import Path

            from app.parsers import pdf_text


            def parse_text(monkeypatch, tmp_path: Path, text: str):
                monkeypatch.setattr(
                    pdf_text,
                    "_extract_text",
                    lambda _path: (
                        text,
                        {"extraction_method": "local_ocr", "evidence_class": "derived", "ocr_pages": 1},
                        True,
                    ),
                )
                path = tmp_path / "scan.pdf"
                path.write_bytes(b"placeholder")
                return pdf_text.parse_pdf(path, {"document_type": "proposal"})


            def test_pdf_semantics_prefers_strong_business_id_and_usd(monkeypatch, tmp_path: Path):
                text = """PEN-LINK\nQUOTE\nQUO-01487-5Z12C3\n1 COLLECTION MAINTENANCE - PREMIUM\n1 XNET MAINTENANCE - PREMIUM\n1 COLLECTION SUPPORT - PREMIUM\n1 XNET SUPPORT - PREMIUM\n$127,566.67 $127,566.67\n$9,605.00 $9,605.00\n$127,566.67 $127,566.67\n$9,605.00 $9,605.00\n"""
                result = parse_text(monkeypatch, tmp_path, text)
                assert result.number == "QUO-01487-5Z12C3"
                assert result.currency == "USD"
                assert len(result.lines) == 4
                assert result.metadata["document_number_recognition"]["status"] == "recognized"
                assert result.metadata["currency_recognition"]["status"] == "recognized"


            def test_pdf_semantics_abstains_instead_of_inventing(monkeypatch, tmp_path: Path):
                result = parse_text(monkeypatch, tmp_path, "PEN-LINK DUTZ LINK\\nNo reliable identifier here")
                assert result.number is None
                assert result.currency == "UNK"
                assert result.metadata["document_number_recognition"]["status"] == "abstained"
                assert result.metadata["currency_recognition"]["status"] == "abstained"


            def test_pdf_semantics_extracts_inline_business_rows(monkeypatch, tmp_path: Path):
                text = """QUOTE\nQUO-04689-V8Y5D0\n1 MASTER DATABASE SERVER $10,607.80 $10,607.80\n1 HARDWARE SHIPPING $106.08 $105.08\n1 CONSULT - ONSITE SERVICES $3,500.00 $3,500.00\n"""
                result = parse_text(monkeypatch, tmp_path, text)
                assert result.number == "QUO-04689-V8Y5D0"
                assert result.currency == "USD"
                assert len(result.lines) == 3
                assert result.lines[0].description == "MASTER DATABASE SERVER"
                assert result.lines[0].unit_price == 10607.80
            '''
        ).lstrip(),
        encoding="utf-8",
    )


def remove_diagnostic_step() -> None:
    path = ROOT / ".github/workflows/dirty-public-corpus-22.yml"
    text = path.read_text(encoding="utf-8")
    diagnostic = '''      - name: Show formatter diff\n        run: ruff format --diff scripts/run_dirty_public_corpus.py tests/test_dirty_public_corpus.py || true\n'''
    if diagnostic in text:
        path.write_text(text.replace(diagnostic, "", 1), encoding="utf-8")


def main() -> None:
    patch_pdf_parser()
    patch_benchmark_metrics()
    patch_windows_ocr_smoke()
    write_tests()
    remove_diagnostic_step()


if __name__ == "__main__":
    main()
