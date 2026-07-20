from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Document, DocumentLine, Supplier
from ..parsers import ParseError, parse_file
from .file_security import scan_file
from .matching import attach_document_to_chain
from .normalizer import canonical_item_key, normalize_text
from .rules import analyze_chain


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _supplier(db: Session, tenant_id: str, name: str | None, vat_id: str | None) -> Supplier | None:
    if not name and not vat_id:
        return None
    normalized = normalize_text(name or vat_id)
    supplier = db.scalar(
        select(Supplier).where(
            Supplier.tenant_id == tenant_id,
            Supplier.normalized_name == normalized,
        )
    )
    if supplier is None:
        supplier = Supplier(
            tenant_id=tenant_id,
            legal_name=name or vat_id or "Fornitore non identificato",
            normalized_name=normalized,
            vat_id=vat_id,
        )
        db.add(supplier)
        db.flush()
    elif vat_id and not supplier.vat_id:
        supplier.vat_id = vat_id
    return supplier


def _validate_file_shape(path: Path) -> None:
    suffix = path.suffix.lower()
    with path.open("rb") as handle:
        head = handle.read(8)
    if suffix == ".pdf" and not head.startswith(b"%PDF"):
        raise ParseError("Il contenuto non corrisponde a un PDF valido")
    if suffix in {".xlsx", ".xlsm"}:
        if not head.startswith(b"PK"):
            raise ParseError("Il contenuto non corrisponde a un file Excel valido")
        try:
            with zipfile.ZipFile(path) as archive:
                infos = archive.infolist()
                if len(infos) > 5000:
                    raise ParseError("Archivio Excel con troppi elementi")
                compressed = sum(max(i.compress_size, 1) for i in infos)
                uncompressed = sum(i.file_size for i in infos)
                if uncompressed > 250 * 1024 * 1024 or uncompressed / compressed > 120:
                    raise ParseError("Archivio Excel potenzialmente anomalo")
        except zipfile.BadZipFile as exc:
            raise ParseError("Archivio Excel danneggiato") from exc


def ingest_path(
    db: Session,
    tenant_id: str,
    source_path: Path,
    original_filename: str,
    content_type: str | None,
    overrides: dict[str, Any],
) -> tuple[Document, str | None]:
    scan_file(source_path)
    _validate_file_shape(source_path)
    file_hash = _hash_file(source_path)
    existing = db.scalar(
        select(Document).where(
            Document.tenant_id == tenant_id,
            Document.file_hash == file_hash,
        )
    )
    if existing:
        return existing, "duplicate"

    tenant_dir = settings.storage_dir / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    original_name = Path(original_filename).name[:500] or "document"
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", original_name).strip("._")[:180] or "document"
    final_path = tenant_dir / f"{file_hash[:16]}-{safe_name}"
    if source_path.resolve() != final_path.resolve():
        shutil.copy2(source_path, final_path)

    document = Document(
        tenant_id=tenant_id,
        document_type=overrides.get("document_type") or "invoice",
        source_filename=original_name,
        storage_path=str(final_path),
        mime_type=content_type or mimetypes.guess_type(original_name)[0],
        file_hash=file_hash,
        parse_status="processing",
    )
    db.add(document)
    db.flush()

    try:
        parsed = parse_file(final_path, original_name, content_type, overrides)
        supplier = _supplier(db, tenant_id, parsed.supplier_name, parsed.supplier_vat)
        document.supplier_id = supplier.id if supplier else None
        document.document_type = parsed.document_type or document.document_type
        document.number = parsed.number
        document.document_date = parsed.document_date
        document.currency = parsed.currency
        document.references_json = json.dumps(parsed.references, ensure_ascii=False, default=str)
        document.metadata_json = json.dumps(parsed.metadata, ensure_ascii=False, default=str)
        document.confidence = parsed.confidence
        document.parse_message = parsed.message
        for line in parsed.lines:
            key = canonical_item_key(line.sku, line.description, line.color, line.size, line.lot)
            db.add(
                DocumentLine(
                    tenant_id=tenant_id,
                    document_id=document.id,
                    line_no=line.line_no,
                    sku=line.sku,
                    description=line.description,
                    color=line.color,
                    size=line.size,
                    lot=line.lot,
                    unit_of_measure=line.unit_of_measure,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    price_base_quantity=line.price_base_quantity,
                    discount_rate=line.discount_rate,
                    tax_rate=line.tax_rate,
                    line_total=line.line_total,
                    canonical_key=key,
                    confidence=line.confidence,
                    raw_json=json.dumps(line.raw, ensure_ascii=False, default=str),
                )
            )
        document.parse_status = "parsed" if parsed.lines else "review_required"
        db.flush()
        chain = attach_document_to_chain(db, document)
        analyze_chain(db, chain)
        return document, None
    except ParseError as exc:
        document.parse_status = "failed"
        document.parse_message = str(exc)
        document.confidence = 0.0
        db.flush()
        return document, "parse_failed"
    except Exception:
        final_path.unlink(missing_ok=True)
        raise


def reprocess_document(db: Session, document: Document, overrides: dict[str, Any]) -> Document:
    """Reparse a stored file atomically and rebuild its chain membership."""
    from sqlalchemy import delete

    from ..models import ChainDocument, DocumentLine, OperationChain
    from .matching import PRIMARY_FIELD_BY_TYPE

    path = Path(document.storage_path)
    if not path.exists():
        raise ParseError("File sorgente non più disponibile")

    # Parse first. A failed parse must not destroy the last known-good extraction.
    parsed = parse_file(path, document.source_filename, document.mime_type, overrides)
    supplier = _supplier(db, document.tenant_id, parsed.supplier_name, parsed.supplier_vat)

    old_links = list(
        db.scalars(
            select(ChainDocument).where(
                ChainDocument.tenant_id == document.tenant_id,
                ChainDocument.document_id == document.id,
            )
        )
    )
    old_chain_ids = {link.chain_id for link in old_links}
    old_roles = {link.chain_id: link.role for link in old_links}
    for link in old_links:
        db.delete(link)
    db.flush()

    # Repair primary pointers before the document is matched again.
    for chain_id in old_chain_ids:
        chain = db.get(OperationChain, chain_id)
        if not chain:
            continue
        role = old_roles[chain_id]
        primary_field = PRIMARY_FIELD_BY_TYPE[role]
        if getattr(chain, primary_field) == document.id:
            replacement = db.scalar(
                select(ChainDocument.document_id)
                .where(
                    ChainDocument.tenant_id == document.tenant_id,
                    ChainDocument.chain_id == chain.id,
                    ChainDocument.role == role,
                )
                .order_by(ChainDocument.sequence_no)
            )
            setattr(chain, primary_field, replacement)

    db.execute(delete(DocumentLine).where(DocumentLine.document_id == document.id))
    document.supplier_id = supplier.id if supplier else None
    document.document_type = parsed.document_type or document.document_type
    document.number = parsed.number or document.number
    document.document_date = parsed.document_date or document.document_date
    document.currency = parsed.currency
    document.references_json = json.dumps(parsed.references, ensure_ascii=False, default=str)
    document.metadata_json = json.dumps(parsed.metadata, ensure_ascii=False, default=str)
    document.confidence = parsed.confidence
    document.parse_message = parsed.message
    for line in parsed.lines:
        key = canonical_item_key(line.sku, line.description, line.color, line.size, line.lot)
        db.add(
            DocumentLine(
                tenant_id=document.tenant_id,
                document_id=document.id,
                line_no=line.line_no,
                sku=line.sku,
                description=line.description,
                color=line.color,
                size=line.size,
                lot=line.lot,
                unit_of_measure=line.unit_of_measure,
                quantity=line.quantity,
                unit_price=line.unit_price,
                price_base_quantity=line.price_base_quantity,
                discount_rate=line.discount_rate,
                tax_rate=line.tax_rate,
                line_total=line.line_total,
                canonical_key=key,
                confidence=line.confidence,
                raw_json=json.dumps(line.raw, ensure_ascii=False, default=str),
            )
        )
    document.parse_status = "parsed" if parsed.lines else "review_required"
    db.flush()

    # Re-evaluate old chains after detachment, then place the corrected document.
    for chain_id in old_chain_ids:
        chain = db.get(OperationChain, chain_id)
        if chain:
            analyze_chain(db, chain)
    new_chain = attach_document_to_chain(db, document)
    analyze_chain(db, new_chain)
    return document
