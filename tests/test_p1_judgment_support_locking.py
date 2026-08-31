from __future__ import annotations

from sqlalchemy.dialects import postgresql

from app.legacy_cases_api import _case_query, _locked_case_query
from app.services.judgment_provenance import (
    _locked_chain_membership_query,
    _locked_chain_query,
    _locked_document_lines_query,
    _locked_documents_query,
)


def _postgres_sql(statement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).upper()


def test_p1_support_queries_are_real_postgresql_row_locks():
    statements = (
        _locked_chain_query(tenant_id="tenant-1", chain_id="chain-1"),
        _locked_chain_membership_query(tenant_id="tenant-1", chain_id="chain-1"),
        _locked_documents_query(tenant_id="tenant-1", document_ids=("doc-b", "doc-a")),
        _locked_document_lines_query(tenant_id="tenant-1", document_ids=("doc-b", "doc-a")),
    )

    for statement in statements:
        sql = _postgres_sql(statement)
        assert "FOR UPDATE" in sql


def test_support_lock_queries_are_scoped_and_deterministically_ordered():
    membership_sql = _postgres_sql(_locked_chain_membership_query(tenant_id="tenant-1", chain_id="chain-1"))
    document_sql = _postgres_sql(_locked_documents_query(tenant_id="tenant-1", document_ids=("doc-b", "doc-a")))
    line_sql = _postgres_sql(_locked_document_lines_query(tenant_id="tenant-1", document_ids=("doc-b", "doc-a")))

    assert "CHAIN_DOCUMENTS.TENANT_ID = 'TENANT-1'" in membership_sql
    assert "CHAIN_DOCUMENTS.CHAIN_ID = 'CHAIN-1'" in membership_sql
    assert "ORDER BY CHAIN_DOCUMENTS.ID" in membership_sql

    assert "DOCUMENTS.TENANT_ID = 'TENANT-1'" in document_sql
    assert "ORDER BY DOCUMENTS.ID" in document_sql

    assert "DOCUMENT_LINES.TENANT_ID = 'TENANT-1'" in line_sql
    assert "ORDER BY DOCUMENT_LINES.ID" in line_sql


def test_review_path_keeps_unlocked_lookup_separate_from_case_serialization():
    initial_sql = _postgres_sql(_case_query(case_id="case-1", tenant_id="tenant-1"))
    locked_sql = _postgres_sql(_locked_case_query(case_id="case-1", tenant_id="tenant-1"))

    assert "FOR UPDATE" not in initial_sql
    assert "FOR UPDATE" in locked_sql
