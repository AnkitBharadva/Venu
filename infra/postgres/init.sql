-- ==============================================================================
-- SIH26155 GenAI Content Transformation Platform
-- Database Initialization: Metadata Store & Append-Only Tamper-Evident Audit Log
-- ==============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ------------------------------------------------------------------------------
-- 1. Source Documents (Normalized Ingestion Layer)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS source_documents (
    doc_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_filename VARCHAR(512) NOT NULL,
    content_type VARCHAR(128) NOT NULL,
    checksum VARCHAR(64) NOT NULL,                      -- SHA-256 of raw file
    encrypted_file_path VARCHAR(1024) NOT NULL,         -- Path to AES-256 encrypted file on disk
    raw_text TEXT,
    structural_metadata JSONB DEFAULT '{}'::jsonb,      -- Headings, page offsets, audio timestamps
    uploader_id VARCHAR(128) NOT NULL DEFAULT 'operator_default',
    upload_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_source_documents_checksum ON source_documents(checksum);
CREATE INDEX IF NOT EXISTS idx_source_documents_uploader ON source_documents(uploader_id);
CREATE INDEX IF NOT EXISTS idx_source_documents_upload_timestamp ON source_documents(upload_timestamp DESC);

-- ------------------------------------------------------------------------------
-- 2. Append-Only Tamper-Evident Audit Log
-- Every operator action (upload, generate, edit, approve, export) is cryptographically chained.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    actor VARCHAR(128) NOT NULL,
    action VARCHAR(64) NOT NULL,                        -- 'upload', 'generate', 'edit', 'approve', 'reject', 'export'
    doc_id UUID REFERENCES source_documents(doc_id) ON DELETE SET NULL,
    output_id UUID,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_hash VARCHAR(64),
    details JSONB DEFAULT '{}'::jsonb,
    prev_hash VARCHAR(64) NOT NULL,                     -- Hash of previous audit row (genesis: 64 zeros)
    hash VARCHAR(64) NOT NULL                           -- SHA-256(prev_hash + actor + action + timestamp + details)
);

CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_actor ON audit_log(actor);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_log_doc_id ON audit_log(doc_id);

-- Enforce Strict Append-Only Behavior via Trigger (Disallow UPDATE and DELETE on audit_log)
CREATE OR REPLACE FUNCTION prevent_audit_log_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'SECURITY VIOLATION: audit_log table is append-only. Modifying or deleting audit records is strictly prohibited.';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_audit_log_update ON audit_log;
CREATE TRIGGER trg_prevent_audit_log_update
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_mutation();

-- ------------------------------------------------------------------------------
-- 3. Generated Deliverables (Draft vs Final Human Review)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS generated_outputs (
    output_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id UUID NOT NULL REFERENCES source_documents(doc_id) ON DELETE RESTRICT,
    deliverable_type VARCHAR(64) NOT NULL,              -- 'linkedin', 'twitter_thread', 'advisory', 'executive_summary', 'presentation', 'video_package', 'infographic'
    status VARCHAR(32) NOT NULL DEFAULT 'draft',        -- 'draft', 'in_review', 'final', 'rejected'
    content JSONB NOT NULL,                             -- Generated text blocks with embedded sentence IDs
    citations JSONB NOT NULL DEFAULT '[]'::jsonb,       -- Mappings of sentence_id -> {chunk_id, offset_start, offset_end}
    format_metadata JSONB DEFAULT '{}'::jsonb,
    reviewer_id VARCHAR(128),
    reviewer_notes TEXT,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_generated_outputs_doc_id ON generated_outputs(doc_id);
CREATE INDEX IF NOT EXISTS idx_generated_outputs_status ON generated_outputs(status);
CREATE INDEX IF NOT EXISTS idx_generated_outputs_type ON generated_outputs(deliverable_type);

-- Insert Genesis Audit Log Entry if empty
INSERT INTO audit_log (actor, action, timestamp, details, prev_hash, hash)
SELECT 
    'system_bootstrap',
    'system_initialization',
    NOW(),
    '{"message": "Audit log hash chain initialized in air-gapped environment."}'::jsonb,
    '0000000000000000000000000000000000000000000000000000000000000000',
    encode(digest('0000000000000000000000000000000000000000000000000000000000000000:system_bootstrap:system_initialization:genesis', 'sha256'), 'hex')
WHERE NOT EXISTS (SELECT 1 FROM audit_log LIMIT 1);
