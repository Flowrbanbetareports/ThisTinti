BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 374502cf2a83

CREATE TABLE tenants (
    id VARCHAR(36) NOT NULL, 
    name VARCHAR(180) NOT NULL, 
    status VARCHAR(30) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_tenant_status CHECK (status IN ('active', 'suspended', 'deleted'))
);

CREATE TABLE audit_events (
    id VARCHAR(36) NOT NULL, 
    tenant_id VARCHAR(36) NOT NULL, 
    actor_id VARCHAR(36), 
    action VARCHAR(100) NOT NULL, 
    entity_type VARCHAR(100), 
    entity_id VARCHAR(36), 
    payload_json TEXT NOT NULL, 
    previous_hash VARCHAR(64), 
    event_hash VARCHAR(64) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_audit_events_tenant_id ON audit_events (tenant_id);

CREATE INDEX ix_audit_tenant_created ON audit_events (tenant_id, created_at);

CREATE TABLE suppliers (
    id VARCHAR(36) NOT NULL, 
    tenant_id VARCHAR(36) NOT NULL, 
    legal_name VARCHAR(240) NOT NULL, 
    normalized_name VARCHAR(240) NOT NULL, 
    vat_id VARCHAR(40), 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    CONSTRAINT uq_supplier_tenant_name UNIQUE (tenant_id, normalized_name)
);

CREATE INDEX ix_suppliers_tenant_id ON suppliers (tenant_id);

CREATE TABLE users (
    id VARCHAR(36) NOT NULL, 
    tenant_id VARCHAR(36) NOT NULL, 
    email VARCHAR(320) NOT NULL, 
    password_hash TEXT NOT NULL, 
    role VARCHAR(30) NOT NULL, 
    active BOOLEAN NOT NULL, 
    token_version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_user_role CHECK (role IN ('admin', 'reviewer', 'viewer')), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    CONSTRAINT uq_user_email UNIQUE (email)
);

CREATE INDEX ix_users_tenant_id ON users (tenant_id);

CREATE TABLE documents (
    id VARCHAR(36) NOT NULL, 
    tenant_id VARCHAR(36) NOT NULL, 
    supplier_id VARCHAR(36), 
    document_type VARCHAR(30) NOT NULL, 
    number VARCHAR(120), 
    document_date DATE, 
    currency VARCHAR(8) NOT NULL, 
    source_filename VARCHAR(500) NOT NULL, 
    storage_path VARCHAR(1000) NOT NULL, 
    mime_type VARCHAR(150), 
    file_hash VARCHAR(64) NOT NULL, 
    parse_status VARCHAR(30) NOT NULL, 
    parse_message TEXT, 
    confidence FLOAT NOT NULL, 
    references_json TEXT NOT NULL, 
    metadata_json TEXT NOT NULL, 
    archived BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_document_type CHECK (document_type IN ('order', 'confirmation', 'delivery', 'invoice', 'return', 'credit_note')), 
    FOREIGN KEY(supplier_id) REFERENCES suppliers (id) ON DELETE SET NULL, 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    CONSTRAINT uq_document_hash_per_tenant UNIQUE (tenant_id, file_hash)
);

CREATE INDEX ix_document_tenant_supplier_type ON documents (tenant_id, supplier_id, document_type);

CREATE INDEX ix_documents_supplier_id ON documents (supplier_id);

CREATE INDEX ix_documents_tenant_id ON documents (tenant_id);

CREATE TABLE item_aliases (
    id VARCHAR(36) NOT NULL, 
    tenant_id VARCHAR(36) NOT NULL, 
    supplier_id VARCHAR(36), 
    canonical_key VARCHAR(280) NOT NULL, 
    alias VARCHAR(280) NOT NULL, 
    normalized_alias VARCHAR(280) NOT NULL, 
    confirmed_count INTEGER NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(supplier_id) REFERENCES suppliers (id) ON DELETE CASCADE, 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    CONSTRAINT uq_item_alias UNIQUE (tenant_id, supplier_id, normalized_alias)
);

CREATE INDEX ix_item_aliases_tenant_id ON item_aliases (tenant_id);

CREATE TABLE supplier_aliases (
    id VARCHAR(36) NOT NULL, 
    tenant_id VARCHAR(36) NOT NULL, 
    supplier_id VARCHAR(36) NOT NULL, 
    alias VARCHAR(240) NOT NULL, 
    normalized_alias VARCHAR(240) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(supplier_id) REFERENCES suppliers (id) ON DELETE CASCADE, 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    CONSTRAINT uq_supplier_alias UNIQUE (tenant_id, normalized_alias)
);

CREATE INDEX ix_supplier_aliases_supplier_id ON supplier_aliases (supplier_id);

CREATE INDEX ix_supplier_aliases_tenant_id ON supplier_aliases (tenant_id);

CREATE TABLE document_lines (
    id VARCHAR(36) NOT NULL, 
    tenant_id VARCHAR(36) NOT NULL, 
    document_id VARCHAR(36) NOT NULL, 
    line_no INTEGER NOT NULL, 
    sku VARCHAR(280), 
    description TEXT, 
    color VARCHAR(120), 
    size VARCHAR(120), 
    lot VARCHAR(120), 
    quantity NUMERIC(18, 4) NOT NULL, 
    unit_price NUMERIC(18, 6) NOT NULL, 
    discount_rate FLOAT NOT NULL, 
    tax_rate FLOAT NOT NULL, 
    line_total NUMERIC(18, 2) NOT NULL, 
    canonical_key VARCHAR(500), 
    confidence FLOAT NOT NULL, 
    raw_json TEXT NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE, 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_document_lines_canonical_key ON document_lines (canonical_key);

CREATE INDEX ix_document_lines_document_id ON document_lines (document_id);

CREATE INDEX ix_document_lines_tenant_id ON document_lines (tenant_id);

CREATE INDEX ix_line_tenant_document ON document_lines (tenant_id, document_id);

CREATE TABLE operation_chains (
    id VARCHAR(36) NOT NULL, 
    tenant_id VARCHAR(36) NOT NULL, 
    supplier_id VARCHAR(36), 
    order_document_id VARCHAR(36), 
    confirmation_document_id VARCHAR(36), 
    delivery_document_id VARCHAR(36), 
    invoice_document_id VARCHAR(36), 
    return_document_id VARCHAR(36), 
    credit_note_document_id VARCHAR(36), 
    reference_key VARCHAR(280), 
    status VARCHAR(30) NOT NULL, 
    confidence FLOAT NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(confirmation_document_id) REFERENCES documents (id) ON DELETE SET NULL, 
    FOREIGN KEY(credit_note_document_id) REFERENCES documents (id) ON DELETE SET NULL, 
    FOREIGN KEY(delivery_document_id) REFERENCES documents (id) ON DELETE SET NULL, 
    FOREIGN KEY(invoice_document_id) REFERENCES documents (id) ON DELETE SET NULL, 
    FOREIGN KEY(order_document_id) REFERENCES documents (id) ON DELETE SET NULL, 
    FOREIGN KEY(return_document_id) REFERENCES documents (id) ON DELETE SET NULL, 
    FOREIGN KEY(supplier_id) REFERENCES suppliers (id) ON DELETE SET NULL, 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_chain_tenant_supplier ON operation_chains (tenant_id, supplier_id);

CREATE INDEX ix_operation_chains_reference_key ON operation_chains (reference_key);

CREATE INDEX ix_operation_chains_tenant_id ON operation_chains (tenant_id);

CREATE TABLE chain_documents (
    id VARCHAR(36) NOT NULL, 
    tenant_id VARCHAR(36) NOT NULL, 
    chain_id VARCHAR(36) NOT NULL, 
    document_id VARCHAR(36) NOT NULL, 
    role VARCHAR(30) NOT NULL, 
    sequence_no INTEGER NOT NULL, 
    match_confidence FLOAT NOT NULL, 
    match_reason VARCHAR(200), 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_chain_document_role CHECK (role IN ('order', 'confirmation', 'delivery', 'invoice', 'return', 'credit_note')), 
    FOREIGN KEY(chain_id) REFERENCES operation_chains (id) ON DELETE CASCADE, 
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE, 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    CONSTRAINT uq_chain_document UNIQUE (tenant_id, document_id)
);

CREATE INDEX ix_chain_document_role ON chain_documents (tenant_id, chain_id, role);

CREATE INDEX ix_chain_documents_chain_id ON chain_documents (chain_id);

CREATE INDEX ix_chain_documents_document_id ON chain_documents (document_id);

CREATE INDEX ix_chain_documents_tenant_id ON chain_documents (tenant_id);

CREATE TABLE discrepancy_cases (
    id VARCHAR(36) NOT NULL, 
    tenant_id VARCHAR(36) NOT NULL, 
    chain_id VARCHAR(36) NOT NULL, 
    fingerprint VARCHAR(64) NOT NULL, 
    case_type VARCHAR(60) NOT NULL, 
    severity VARCHAR(20) NOT NULL, 
    amount_estimate NUMERIC(18, 2) NOT NULL, 
    confidence FLOAT NOT NULL, 
    status VARCHAR(30) NOT NULL, 
    title VARCHAR(300) NOT NULL, 
    explanation TEXT NOT NULL, 
    recommended_action TEXT NOT NULL, 
    machine_generated BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_case_severity CHECK (severity IN ('low', 'medium', 'high', 'critical')), 
    CONSTRAINT ck_case_status CHECK (status IN ('open', 'needs_review', 'confirmed', 'dismissed', 'resolved', 'superseded')), 
    FOREIGN KEY(chain_id) REFERENCES operation_chains (id) ON DELETE CASCADE, 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    CONSTRAINT uq_case_fingerprint UNIQUE (tenant_id, fingerprint)
);

CREATE INDEX ix_discrepancy_cases_chain_id ON discrepancy_cases (chain_id);

CREATE INDEX ix_discrepancy_cases_tenant_id ON discrepancy_cases (tenant_id);

CREATE TABLE evidence_links (
    id VARCHAR(36) NOT NULL, 
    tenant_id VARCHAR(36) NOT NULL, 
    case_id VARCHAR(36) NOT NULL, 
    document_id VARCHAR(36), 
    document_line_id VARCHAR(36), 
    field_name VARCHAR(120) NOT NULL, 
    observed_value TEXT, 
    expected_value TEXT, 
    note TEXT, 
    PRIMARY KEY (id), 
    FOREIGN KEY(case_id) REFERENCES discrepancy_cases (id) ON DELETE CASCADE, 
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE SET NULL, 
    FOREIGN KEY(document_line_id) REFERENCES document_lines (id) ON DELETE SET NULL, 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_evidence_links_case_id ON evidence_links (case_id);

CREATE INDEX ix_evidence_links_tenant_id ON evidence_links (tenant_id);

CREATE TABLE review_decisions (
    id VARCHAR(36) NOT NULL, 
    tenant_id VARCHAR(36) NOT NULL, 
    case_id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36), 
    decision VARCHAR(30) NOT NULL, 
    note TEXT, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_review_decision CHECK (decision IN ('confirmed', 'dismissed', 'needs_review', 'resolved')), 
    FOREIGN KEY(case_id) REFERENCES discrepancy_cases (id) ON DELETE CASCADE, 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_review_decisions_case_id ON review_decisions (case_id);

CREATE INDEX ix_review_decisions_tenant_id ON review_decisions (tenant_id);

INSERT INTO alembic_version (version_num) VALUES ('374502cf2a83') RETURNING alembic_version.version_num;

-- Running upgrade 374502cf2a83 -> 4c720e60d5f2

ALTER TABLE item_aliases ALTER COLUMN canonical_key TYPE VARCHAR(500);

CREATE TABLE validation_datasets (
    id VARCHAR(36) NOT NULL, 
    tenant_id VARCHAR(36) NOT NULL, 
    name VARCHAR(180) NOT NULL, 
    version VARCHAR(40) NOT NULL, 
    description TEXT, 
    status VARCHAR(20) NOT NULL, 
    schema_json TEXT NOT NULL, 
    created_by VARCHAR(36), 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_validation_dataset_status CHECK (status IN ('active', 'archived')), 
    FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    CONSTRAINT uq_validation_dataset_version UNIQUE (tenant_id, name, version)
);

CREATE INDEX ix_validation_datasets_tenant_id ON validation_datasets (tenant_id);

CREATE TABLE validation_runs (
    id VARCHAR(36) NOT NULL, 
    tenant_id VARCHAR(36) NOT NULL, 
    dataset_id VARCHAR(36) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    engine_version VARCHAR(40) NOT NULL, 
    scenario_count INTEGER NOT NULL, 
    true_positives INTEGER NOT NULL, 
    false_positives INTEGER NOT NULL, 
    false_negatives INTEGER NOT NULL, 
    precision FLOAT NOT NULL, 
    recall FLOAT NOT NULL, 
    f1_score FLOAT NOT NULL, 
    amount_mae NUMERIC(18, 2) NOT NULL, 
    gate_passed BOOLEAN NOT NULL, 
    details_json TEXT NOT NULL, 
    error_message TEXT, 
    created_by VARCHAR(36), 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_validation_run_status CHECK (status IN ('running', 'completed', 'failed')), 
    FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(dataset_id) REFERENCES validation_datasets (id) ON DELETE CASCADE, 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_validation_run_tenant_created ON validation_runs (tenant_id, created_at);

CREATE INDEX ix_validation_runs_dataset_id ON validation_runs (dataset_id);

CREATE INDEX ix_validation_runs_tenant_id ON validation_runs (tenant_id);

UPDATE alembic_version SET version_num='4c720e60d5f2' WHERE alembic_version.version_num = '374502cf2a83';

-- Running upgrade 4c720e60d5f2 -> 9b3f17a42d91

CREATE TABLE activity_profiles (
    id VARCHAR(36) NOT NULL, 
    tenant_id VARCHAR(36) NOT NULL, 
    activity_type VARCHAR(120) NOT NULL, 
    activity_label VARCHAR(180) NOT NULL, 
    confidence FLOAT NOT NULL, 
    status VARCHAR(30) NOT NULL, 
    evidence_json TEXT NOT NULL, 
    field_profile_json TEXT NOT NULL, 
    document_count INTEGER NOT NULL, 
    line_count INTEGER NOT NULL, 
    human_confirmed BOOLEAN NOT NULL, 
    confirmed_by VARCHAR(36), 
    confirmed_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_activity_profile_status CHECK (status IN ('learning', 'ready', 'needs_confirmation')), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    FOREIGN KEY(confirmed_by) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT uq_activity_profile_tenant UNIQUE (tenant_id)
);

CREATE INDEX ix_activity_profiles_tenant_id ON activity_profiles (tenant_id);

CREATE TABLE discovery_runs (
    id VARCHAR(36) NOT NULL, 
    tenant_id VARCHAR(36) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    activity_type VARCHAR(120), 
    activity_confidence FLOAT NOT NULL, 
    document_count INTEGER NOT NULL, 
    line_count INTEGER NOT NULL, 
    proposed_rules INTEGER NOT NULL, 
    auto_activated_rules INTEGER NOT NULL, 
    uncertain_rules INTEGER NOT NULL, 
    details_json TEXT NOT NULL, 
    error_message TEXT, 
    created_by VARCHAR(36), 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_discovery_run_status CHECK (status IN ('running', 'completed', 'failed')), 
    FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_discovery_run_tenant_created ON discovery_runs (tenant_id, created_at);

CREATE INDEX ix_discovery_runs_tenant_id ON discovery_runs (tenant_id);

CREATE TABLE rule_proposals (
    id VARCHAR(36) NOT NULL, 
    tenant_id VARCHAR(36) NOT NULL, 
    rule_code VARCHAR(100) NOT NULL, 
    title VARCHAR(240) NOT NULL, 
    description TEXT NOT NULL, 
    rationale TEXT NOT NULL, 
    confidence FLOAT NOT NULL, 
    status VARCHAR(30) NOT NULL, 
    parameters_json TEXT NOT NULL, 
    evidence_json TEXT NOT NULL, 
    source VARCHAR(30) NOT NULL, 
    confirmed_by VARCHAR(36), 
    confirmed_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_rule_proposal_status CHECK (status IN ('auto_active', 'needs_confirmation', 'confirmed', 'rejected', 'inactive')), 
    FOREIGN KEY(confirmed_by) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    CONSTRAINT uq_rule_proposal_tenant_code UNIQUE (tenant_id, rule_code)
);

CREATE INDEX ix_rule_proposals_tenant_id ON rule_proposals (tenant_id);

UPDATE alembic_version SET version_num='9b3f17a42d91' WHERE alembic_version.version_num = '4c720e60d5f2';

-- Running upgrade 9b3f17a42d91 -> b10a7c31f9d2

ALTER TABLE tenants ADD COLUMN security_version INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE tenants ADD COLUMN audit_sequence INTEGER DEFAULT '0' NOT NULL;

CREATE TABLE auth_sessions (
    id VARCHAR(36) NOT NULL, 
    tenant_id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    active BOOLEAN DEFAULT true NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    last_seen_at TIMESTAMP WITH TIME ZONE, 
    revoked_at TIMESTAMP WITH TIME ZONE, 
    revoke_reason VARCHAR(120), 
    PRIMARY KEY (id), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_auth_sessions_tenant_id ON auth_sessions (tenant_id);

CREATE INDEX ix_auth_sessions_user_id ON auth_sessions (user_id);

CREATE INDEX ix_auth_session_tenant_active ON auth_sessions (tenant_id, active);

CREATE INDEX ix_auth_session_user_active ON auth_sessions (user_id, active);

ALTER TABLE audit_events ADD COLUMN sequence_no INTEGER;

ALTER TABLE audit_events ALTER COLUMN sequence_no SET NOT NULL;

ALTER TABLE audit_events ADD CONSTRAINT uq_audit_tenant_sequence UNIQUE (tenant_id, sequence_no);

ALTER TABLE document_lines ADD COLUMN unit_of_measure VARCHAR(40);

ALTER TABLE document_lines ADD COLUMN price_base_quantity NUMERIC(24, 8) DEFAULT '1' NOT NULL;

ALTER TABLE document_lines ALTER COLUMN quantity TYPE NUMERIC(24, 8);

ALTER TABLE document_lines ALTER COLUMN unit_price TYPE NUMERIC(24, 10);

ALTER TABLE document_lines ALTER COLUMN discount_rate TYPE NUMERIC(12, 8);

ALTER TABLE document_lines ALTER COLUMN tax_rate TYPE NUMERIC(12, 8);

ALTER TABLE document_lines ALTER COLUMN line_total TYPE NUMERIC(24, 8);

UPDATE alembic_version SET version_num='b10a7c31f9d2' WHERE alembic_version.version_num = '9b3f17a42d91';

-- Running upgrade b10a7c31f9d2 -> c21d9e4a7b63

CREATE TABLE api_credentials (
    id VARCHAR(36) NOT NULL, 
    tenant_id VARCHAR(36) NOT NULL, 
    name VARCHAR(180) NOT NULL, 
    key_prefix VARCHAR(20) NOT NULL, 
    secret_hash VARCHAR(64) NOT NULL, 
    role VARCHAR(30) DEFAULT 'viewer' NOT NULL, 
    scopes_json TEXT DEFAULT '[]' NOT NULL, 
    active BOOLEAN DEFAULT true NOT NULL, 
    created_by VARCHAR(36), 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE, 
    revoked_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_api_credential_role CHECK (role IN ('reviewer', 'viewer')), 
    FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_api_credentials_tenant_id ON api_credentials (tenant_id);

CREATE INDEX ix_api_credential_tenant_active ON api_credentials (tenant_id, active);

CREATE TABLE processing_jobs (
    id VARCHAR(36) NOT NULL, 
    tenant_id VARCHAR(36) NOT NULL, 
    created_by VARCHAR(36), 
    created_by_api_credential VARCHAR(36), 
    job_type VARCHAR(40) NOT NULL, 
    status VARCHAR(20) DEFAULT 'queued' NOT NULL, 
    priority INTEGER DEFAULT '100' NOT NULL, 
    attempts INTEGER DEFAULT '0' NOT NULL, 
    max_attempts INTEGER DEFAULT '3' NOT NULL, 
    progress INTEGER DEFAULT '0' NOT NULL, 
    idempotency_key VARCHAR(180), 
    input_json TEXT DEFAULT '{}' NOT NULL, 
    result_json TEXT DEFAULT '{}' NOT NULL, 
    error_message TEXT, 
    available_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    locked_at TIMESTAMP WITH TIME ZONE, 
    locked_by VARCHAR(120), 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_processing_job_type CHECK (job_type IN ('ingest_document', 'ingest_batch', 'reprocess_document', 'reanalyze_tenant')), 
    CONSTRAINT ck_processing_job_status CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')), 
    FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(created_by_api_credential) REFERENCES api_credentials (id) ON DELETE SET NULL, 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    CONSTRAINT uq_job_tenant_idempotency UNIQUE (tenant_id, idempotency_key)
);

CREATE INDEX ix_processing_jobs_tenant_id ON processing_jobs (tenant_id);

CREATE INDEX ix_job_claim ON processing_jobs (status, available_at, created_at);

CREATE INDEX ix_job_tenant_created ON processing_jobs (tenant_id, created_at);

CREATE TABLE worker_heartbeats (
    worker_id VARCHAR(120) NOT NULL, 
    hostname VARCHAR(255) NOT NULL, 
    status VARCHAR(30) DEFAULT 'active' NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    version VARCHAR(40) DEFAULT 'unknown' NOT NULL, 
    PRIMARY KEY (worker_id)
);

CREATE INDEX ix_worker_heartbeats_last_seen_at ON worker_heartbeats (last_seen_at);

CREATE TABLE rate_limit_counters (
    key VARCHAR(255) NOT NULL, 
    window_started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    count INTEGER DEFAULT '1' NOT NULL, 
    PRIMARY KEY (key)
);

CREATE INDEX ix_rate_limit_counters_expires_at ON rate_limit_counters (expires_at);

CREATE OR REPLACE FUNCTION thistinti_assert_tenant_reference()
        RETURNS trigger AS $$
        DECLARE
            reference_id text;
            reference_tenant text;
        BEGIN
            reference_id := to_jsonb(NEW) ->> TG_ARGV[1];
            IF reference_id IS NULL OR reference_id = '' THEN
                RETURN NEW;
            END IF;

            EXECUTE format('SELECT tenant_id::text FROM %I WHERE id::text = $1', TG_ARGV[0])
            INTO reference_tenant
            USING reference_id;

            IF reference_tenant IS NULL THEN
                RAISE EXCEPTION 'Referenced row %.%=% does not exist', TG_ARGV[0], TG_ARGV[1], reference_id
                    USING ERRCODE = 'foreign_key_violation';
            END IF;
            IF reference_tenant <> NEW.tenant_id::text THEN
                RAISE EXCEPTION 'Cross-tenant reference rejected on %.%: row tenant %, referenced tenant %',
                    TG_TABLE_NAME, TG_ARGV[1], NEW.tenant_id, reference_tenant
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;;

DROP TRIGGER IF EXISTS "trg_tt_tenant_auth_sessions_user_id" ON "auth_sessions";

CREATE TRIGGER "trg_tt_tenant_auth_sessions_user_id" BEFORE INSERT OR UPDATE OF tenant_id, "user_id" ON "auth_sessions" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('users', 'user_id');

DROP TRIGGER IF EXISTS "trg_tt_tenant_api_credentials_created_by" ON "api_credentials";

CREATE TRIGGER "trg_tt_tenant_api_credentials_created_by" BEFORE INSERT OR UPDATE OF tenant_id, "created_by" ON "api_credentials" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('users', 'created_by');

DROP TRIGGER IF EXISTS "trg_tt_tenant_processing_jobs_created_by" ON "processing_jobs";

CREATE TRIGGER "trg_tt_tenant_processing_jobs_created_by" BEFORE INSERT OR UPDATE OF tenant_id, "created_by" ON "processing_jobs" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('users', 'created_by');

DROP TRIGGER IF EXISTS "trg_tt_tenant_processing_jobs_created_by_api_credential" ON "processing_jobs";

CREATE TRIGGER "trg_tt_tenant_processing_jobs_created_by_api_credential" BEFORE INSERT OR UPDATE OF tenant_id, "created_by_api_credential" ON "processing_jobs" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('api_credentials', 'created_by_api_credential');

DROP TRIGGER IF EXISTS "trg_tt_tenant_supplier_aliases_supplier_id" ON "supplier_aliases";

CREATE TRIGGER "trg_tt_tenant_supplier_aliases_supplier_id" BEFORE INSERT OR UPDATE OF tenant_id, "supplier_id" ON "supplier_aliases" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('suppliers', 'supplier_id');

DROP TRIGGER IF EXISTS "trg_tt_tenant_item_aliases_supplier_id" ON "item_aliases";

CREATE TRIGGER "trg_tt_tenant_item_aliases_supplier_id" BEFORE INSERT OR UPDATE OF tenant_id, "supplier_id" ON "item_aliases" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('suppliers', 'supplier_id');

DROP TRIGGER IF EXISTS "trg_tt_tenant_documents_supplier_id" ON "documents";

CREATE TRIGGER "trg_tt_tenant_documents_supplier_id" BEFORE INSERT OR UPDATE OF tenant_id, "supplier_id" ON "documents" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('suppliers', 'supplier_id');

DROP TRIGGER IF EXISTS "trg_tt_tenant_document_lines_document_id" ON "document_lines";

CREATE TRIGGER "trg_tt_tenant_document_lines_document_id" BEFORE INSERT OR UPDATE OF tenant_id, "document_id" ON "document_lines" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('documents', 'document_id');

DROP TRIGGER IF EXISTS "trg_tt_tenant_operation_chains_supplier_id" ON "operation_chains";

CREATE TRIGGER "trg_tt_tenant_operation_chains_supplier_id" BEFORE INSERT OR UPDATE OF tenant_id, "supplier_id" ON "operation_chains" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('suppliers', 'supplier_id');

DROP TRIGGER IF EXISTS "trg_tt_tenant_operation_chains_order_document_id" ON "operation_chains";

CREATE TRIGGER "trg_tt_tenant_operation_chains_order_document_id" BEFORE INSERT OR UPDATE OF tenant_id, "order_document_id" ON "operation_chains" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('documents', 'order_document_id');

DROP TRIGGER IF EXISTS "trg_tt_tenant_operation_chains_confirmation_document_id" ON "operation_chains";

CREATE TRIGGER "trg_tt_tenant_operation_chains_confirmation_document_id" BEFORE INSERT OR UPDATE OF tenant_id, "confirmation_document_id" ON "operation_chains" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('documents', 'confirmation_document_id');

DROP TRIGGER IF EXISTS "trg_tt_tenant_operation_chains_delivery_document_id" ON "operation_chains";

CREATE TRIGGER "trg_tt_tenant_operation_chains_delivery_document_id" BEFORE INSERT OR UPDATE OF tenant_id, "delivery_document_id" ON "operation_chains" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('documents', 'delivery_document_id');

DROP TRIGGER IF EXISTS "trg_tt_tenant_operation_chains_invoice_document_id" ON "operation_chains";

CREATE TRIGGER "trg_tt_tenant_operation_chains_invoice_document_id" BEFORE INSERT OR UPDATE OF tenant_id, "invoice_document_id" ON "operation_chains" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('documents', 'invoice_document_id');

DROP TRIGGER IF EXISTS "trg_tt_tenant_operation_chains_return_document_id" ON "operation_chains";

CREATE TRIGGER "trg_tt_tenant_operation_chains_return_document_id" BEFORE INSERT OR UPDATE OF tenant_id, "return_document_id" ON "operation_chains" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('documents', 'return_document_id');

DROP TRIGGER IF EXISTS "trg_tt_tenant_operation_chains_credit_note_document_id" ON "operation_chains";

CREATE TRIGGER "trg_tt_tenant_operation_chains_credit_note_document_id" BEFORE INSERT OR UPDATE OF tenant_id, "credit_note_document_id" ON "operation_chains" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('documents', 'credit_note_document_id');

DROP TRIGGER IF EXISTS "trg_tt_tenant_chain_documents_chain_id" ON "chain_documents";

CREATE TRIGGER "trg_tt_tenant_chain_documents_chain_id" BEFORE INSERT OR UPDATE OF tenant_id, "chain_id" ON "chain_documents" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('operation_chains', 'chain_id');

DROP TRIGGER IF EXISTS "trg_tt_tenant_chain_documents_document_id" ON "chain_documents";

CREATE TRIGGER "trg_tt_tenant_chain_documents_document_id" BEFORE INSERT OR UPDATE OF tenant_id, "document_id" ON "chain_documents" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('documents', 'document_id');

DROP TRIGGER IF EXISTS "trg_tt_tenant_discrepancy_cases_chain_id" ON "discrepancy_cases";

CREATE TRIGGER "trg_tt_tenant_discrepancy_cases_chain_id" BEFORE INSERT OR UPDATE OF tenant_id, "chain_id" ON "discrepancy_cases" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('operation_chains', 'chain_id');

DROP TRIGGER IF EXISTS "trg_tt_tenant_evidence_links_case_id" ON "evidence_links";

CREATE TRIGGER "trg_tt_tenant_evidence_links_case_id" BEFORE INSERT OR UPDATE OF tenant_id, "case_id" ON "evidence_links" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('discrepancy_cases', 'case_id');

DROP TRIGGER IF EXISTS "trg_tt_tenant_evidence_links_document_id" ON "evidence_links";

CREATE TRIGGER "trg_tt_tenant_evidence_links_document_id" BEFORE INSERT OR UPDATE OF tenant_id, "document_id" ON "evidence_links" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('documents', 'document_id');

DROP TRIGGER IF EXISTS "trg_tt_tenant_evidence_links_document_line_id" ON "evidence_links";

CREATE TRIGGER "trg_tt_tenant_evidence_links_document_line_id" BEFORE INSERT OR UPDATE OF tenant_id, "document_line_id" ON "evidence_links" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('document_lines', 'document_line_id');

DROP TRIGGER IF EXISTS "trg_tt_tenant_review_decisions_case_id" ON "review_decisions";

CREATE TRIGGER "trg_tt_tenant_review_decisions_case_id" BEFORE INSERT OR UPDATE OF tenant_id, "case_id" ON "review_decisions" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('discrepancy_cases', 'case_id');

DROP TRIGGER IF EXISTS "trg_tt_tenant_review_decisions_user_id" ON "review_decisions";

CREATE TRIGGER "trg_tt_tenant_review_decisions_user_id" BEFORE INSERT OR UPDATE OF tenant_id, "user_id" ON "review_decisions" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('users', 'user_id');

DROP TRIGGER IF EXISTS "trg_tt_tenant_validation_datasets_created_by" ON "validation_datasets";

CREATE TRIGGER "trg_tt_tenant_validation_datasets_created_by" BEFORE INSERT OR UPDATE OF tenant_id, "created_by" ON "validation_datasets" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('users', 'created_by');

DROP TRIGGER IF EXISTS "trg_tt_tenant_validation_runs_dataset_id" ON "validation_runs";

CREATE TRIGGER "trg_tt_tenant_validation_runs_dataset_id" BEFORE INSERT OR UPDATE OF tenant_id, "dataset_id" ON "validation_runs" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('validation_datasets', 'dataset_id');

DROP TRIGGER IF EXISTS "trg_tt_tenant_validation_runs_created_by" ON "validation_runs";

CREATE TRIGGER "trg_tt_tenant_validation_runs_created_by" BEFORE INSERT OR UPDATE OF tenant_id, "created_by" ON "validation_runs" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('users', 'created_by');

DROP TRIGGER IF EXISTS "trg_tt_tenant_activity_profiles_confirmed_by" ON "activity_profiles";

CREATE TRIGGER "trg_tt_tenant_activity_profiles_confirmed_by" BEFORE INSERT OR UPDATE OF tenant_id, "confirmed_by" ON "activity_profiles" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('users', 'confirmed_by');

DROP TRIGGER IF EXISTS "trg_tt_tenant_discovery_runs_created_by" ON "discovery_runs";

CREATE TRIGGER "trg_tt_tenant_discovery_runs_created_by" BEFORE INSERT OR UPDATE OF tenant_id, "created_by" ON "discovery_runs" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('users', 'created_by');

DROP TRIGGER IF EXISTS "trg_tt_tenant_rule_proposals_confirmed_by" ON "rule_proposals";

CREATE TRIGGER "trg_tt_tenant_rule_proposals_confirmed_by" BEFORE INSERT OR UPDATE OF tenant_id, "confirmed_by" ON "rule_proposals" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('users', 'confirmed_by');

ALTER TABLE "suppliers" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "suppliers" FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tt_tenant_isolation_suppliers" ON "suppliers";

CREATE POLICY "tt_tenant_isolation_suppliers" ON "suppliers" USING (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), ''))) WITH CHECK (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), '')));

ALTER TABLE "supplier_aliases" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "supplier_aliases" FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tt_tenant_isolation_supplier_aliases" ON "supplier_aliases";

CREATE POLICY "tt_tenant_isolation_supplier_aliases" ON "supplier_aliases" USING (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), ''))) WITH CHECK (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), '')));

ALTER TABLE "item_aliases" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "item_aliases" FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tt_tenant_isolation_item_aliases" ON "item_aliases";

CREATE POLICY "tt_tenant_isolation_item_aliases" ON "item_aliases" USING (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), ''))) WITH CHECK (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), '')));

ALTER TABLE "documents" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "documents" FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tt_tenant_isolation_documents" ON "documents";

CREATE POLICY "tt_tenant_isolation_documents" ON "documents" USING (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), ''))) WITH CHECK (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), '')));

ALTER TABLE "document_lines" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "document_lines" FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tt_tenant_isolation_document_lines" ON "document_lines";

CREATE POLICY "tt_tenant_isolation_document_lines" ON "document_lines" USING (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), ''))) WITH CHECK (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), '')));

ALTER TABLE "operation_chains" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "operation_chains" FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tt_tenant_isolation_operation_chains" ON "operation_chains";

CREATE POLICY "tt_tenant_isolation_operation_chains" ON "operation_chains" USING (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), ''))) WITH CHECK (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), '')));

ALTER TABLE "chain_documents" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "chain_documents" FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tt_tenant_isolation_chain_documents" ON "chain_documents";

CREATE POLICY "tt_tenant_isolation_chain_documents" ON "chain_documents" USING (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), ''))) WITH CHECK (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), '')));

ALTER TABLE "discrepancy_cases" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "discrepancy_cases" FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tt_tenant_isolation_discrepancy_cases" ON "discrepancy_cases";

CREATE POLICY "tt_tenant_isolation_discrepancy_cases" ON "discrepancy_cases" USING (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), ''))) WITH CHECK (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), '')));

ALTER TABLE "evidence_links" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "evidence_links" FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tt_tenant_isolation_evidence_links" ON "evidence_links";

CREATE POLICY "tt_tenant_isolation_evidence_links" ON "evidence_links" USING (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), ''))) WITH CHECK (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), '')));

ALTER TABLE "review_decisions" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "review_decisions" FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tt_tenant_isolation_review_decisions" ON "review_decisions";

CREATE POLICY "tt_tenant_isolation_review_decisions" ON "review_decisions" USING (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), ''))) WITH CHECK (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), '')));

ALTER TABLE "validation_datasets" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "validation_datasets" FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tt_tenant_isolation_validation_datasets" ON "validation_datasets";

CREATE POLICY "tt_tenant_isolation_validation_datasets" ON "validation_datasets" USING (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), ''))) WITH CHECK (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), '')));

ALTER TABLE "validation_runs" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "validation_runs" FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tt_tenant_isolation_validation_runs" ON "validation_runs";

CREATE POLICY "tt_tenant_isolation_validation_runs" ON "validation_runs" USING (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), ''))) WITH CHECK (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), '')));

ALTER TABLE "activity_profiles" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "activity_profiles" FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tt_tenant_isolation_activity_profiles" ON "activity_profiles";

CREATE POLICY "tt_tenant_isolation_activity_profiles" ON "activity_profiles" USING (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), ''))) WITH CHECK (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), '')));

ALTER TABLE "discovery_runs" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "discovery_runs" FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tt_tenant_isolation_discovery_runs" ON "discovery_runs";

CREATE POLICY "tt_tenant_isolation_discovery_runs" ON "discovery_runs" USING (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), ''))) WITH CHECK (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), '')));

ALTER TABLE "rule_proposals" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "rule_proposals" FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tt_tenant_isolation_rule_proposals" ON "rule_proposals";

CREATE POLICY "tt_tenant_isolation_rule_proposals" ON "rule_proposals" USING (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), ''))) WITH CHECK (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), '')));

ALTER TABLE "audit_events" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "audit_events" FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tt_tenant_isolation_audit_events" ON "audit_events";

CREATE POLICY "tt_tenant_isolation_audit_events" ON "audit_events" USING (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), ''))) WITH CHECK (tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), '')));

UPDATE alembic_version SET version_num='c21d9e4a7b63' WHERE alembic_version.version_num = 'b10a7c31f9d2';

-- Running upgrade c21d9e4a7b63 -> d42a0f61be90

ALTER TABLE documents DROP CONSTRAINT ck_document_type;

ALTER TABLE documents ADD CONSTRAINT ck_document_type CHECK (document_type IN ('proposal', 'order', 'confirmation', 'delivery', 'invoice', 'payment', 'return', 'credit_note'));

ALTER TABLE chain_documents DROP CONSTRAINT ck_chain_document_role;

ALTER TABLE chain_documents ADD CONSTRAINT ck_chain_document_role CHECK (role IN ('proposal', 'order', 'confirmation', 'delivery', 'invoice', 'payment', 'return', 'credit_note'));

ALTER TABLE processing_jobs DROP CONSTRAINT ck_processing_job_type;

ALTER TABLE processing_jobs ADD CONSTRAINT ck_processing_job_type CHECK (job_type IN ('ingest_document', 'ingest_batch', 'reprocess_document', 'reanalyze_tenant', 'red_team_tenant'));

ALTER TABLE operation_chains ADD COLUMN proposal_document_id VARCHAR(36);

ALTER TABLE operation_chains ADD COLUMN payment_document_id VARCHAR(36);

ALTER TABLE operation_chains ADD CONSTRAINT fk_operation_chains_proposal_document FOREIGN KEY(proposal_document_id) REFERENCES documents (id) ON DELETE SET NULL;

ALTER TABLE operation_chains ADD CONSTRAINT fk_operation_chains_payment_document FOREIGN KEY(payment_document_id) REFERENCES documents (id) ON DELETE SET NULL;

DROP TRIGGER IF EXISTS "trg_tt_tenant_operation_chains_proposal_document_id" ON "operation_chains";

CREATE TRIGGER "trg_tt_tenant_operation_chains_proposal_document_id" BEFORE INSERT OR UPDATE OF tenant_id, "proposal_document_id" ON "operation_chains" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('documents', 'proposal_document_id');

DROP TRIGGER IF EXISTS "trg_tt_tenant_operation_chains_payment_document_id" ON "operation_chains";

CREATE TRIGGER "trg_tt_tenant_operation_chains_payment_document_id" BEFORE INSERT OR UPDATE OF tenant_id, "payment_document_id" ON "operation_chains" FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('documents', 'payment_document_id');

UPDATE alembic_version SET version_num='d42a0f61be90' WHERE alembic_version.version_num = 'c21d9e4a7b63';

COMMIT;

