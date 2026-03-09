-- KLM Postgres schema (Sprint 1)
-- UUID primary keys everywhere
-- Stores key material encrypted-at-rest in DB (application-level encryption TBD next sprint)

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Lookup tables
CREATE TABLE IF NOT EXISTS key_types (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS key_usages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS algorithm_types (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS artifact_types (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS crypto_operation_types (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS result_types (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS performance_metric_types (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE
);

-- Core tables
CREATE TABLE IF NOT EXISTS algorithms (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE,
    type_id uuid NOT NULL REFERENCES algorithm_types(id) ON DELETE RESTRICT,
    params jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS crypto_providers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    version text NULL,
    runtime_info jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (name, version)
);

-- AlgorithmVariants is implied by CryptoOperations.algorithm_variant_id in the original design.
-- This table defines concrete variants of a base algorithm (e.g., AES-256-GCM vs AES-256-CBC).
CREATE TABLE IF NOT EXISTS algorithm_variants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    algorithm_id uuid NOT NULL REFERENCES algorithms(id) ON DELETE RESTRICT,
    name text NOT NULL,
    params jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (algorithm_id, name)
);

-- Keys: stores encrypted key material in DB.
-- Next sprint: decide exact scheme (e.g. AES-GCM with master key from env / OS secret store)
-- and implement encryption/decryption in the service layer.
CREATE TABLE IF NOT EXISTS keys (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    type_id uuid NOT NULL REFERENCES key_types(id) ON DELETE RESTRICT,
    algorithm_id uuid NOT NULL REFERENCES algorithms(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NULL,
    usage_id uuid NOT NULL REFERENCES key_usages(id) ON DELETE RESTRICT,

    -- Encrypted key material
    -- encrypted_material: ciphertext bytes
    -- encryption_*: metadata needed to decrypt (without storing the master key in DB)
    encrypted_material bytea NOT NULL,
    material_format text NOT NULL DEFAULT 'raw',
    encryption_scheme text NOT NULL DEFAULT 'app-level',
    encryption_params jsonb NOT NULL DEFAULT '{}'::jsonb,

    UNIQUE (name)
);

CREATE INDEX IF NOT EXISTS idx_keys_algorithm_id ON keys(algorithm_id);
CREATE INDEX IF NOT EXISTS idx_keys_type_id ON keys(type_id);
CREATE INDEX IF NOT EXISTS idx_keys_usage_id ON keys(usage_id);

CREATE TABLE IF NOT EXISTS files (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    original_name text NOT NULL,
    original_size_bytes bigint NOT NULL,
    original_hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS file_artifacts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id uuid NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    artifact_type_id uuid NOT NULL REFERENCES artifact_types(id) ON DELETE RESTRICT,
    path text NOT NULL,
    size_bytes bigint NOT NULL,
    hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (file_id, artifact_type_id, path)
);

CREATE INDEX IF NOT EXISTS idx_file_artifacts_file_id ON file_artifacts(file_id);

CREATE TABLE IF NOT EXISTS crypto_operations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    operation_type_id uuid NOT NULL REFERENCES crypto_operation_types(id) ON DELETE RESTRICT,

    -- file_id may be NULL for key-only operations like keygen/import/export
    file_id uuid NULL REFERENCES files(id) ON DELETE SET NULL,

    input_artifact_id uuid NULL REFERENCES file_artifacts(id) ON DELETE SET NULL,
    output_artifact_id uuid NULL REFERENCES file_artifacts(id) ON DELETE SET NULL,

    provider_id uuid NOT NULL REFERENCES crypto_providers(id) ON DELETE RESTRICT,
    algorithm_variant_id uuid NOT NULL REFERENCES algorithm_variants(id) ON DELETE RESTRICT,

    -- key_id may be NULL for operations that do not use a specific key (e.g., keygen)
    key_id uuid NULL REFERENCES keys(id) ON DELETE SET NULL,

    params jsonb NOT NULL DEFAULT '{}'::jsonb,
    started_at timestamptz NOT NULL DEFAULT now(),
    ended_at timestamptz NULL,

    result_type_id uuid NOT NULL REFERENCES result_types(id) ON DELETE RESTRICT,
    error_code text NULL,
    error_message text NULL
);

CREATE INDEX IF NOT EXISTS idx_crypto_operations_file_id ON crypto_operations(file_id);
CREATE INDEX IF NOT EXISTS idx_crypto_operations_operation_type_id ON crypto_operations(operation_type_id);
CREATE INDEX IF NOT EXISTS idx_crypto_operations_started_at ON crypto_operations(started_at);

CREATE TABLE IF NOT EXISTS performance_metrics (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    operation_id uuid NOT NULL REFERENCES crypto_operations(id) ON DELETE CASCADE,
    metric_type_id uuid NOT NULL REFERENCES performance_metric_types(id) ON DELETE RESTRICT,
    value double precision NOT NULL,
    unit text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (operation_id, metric_type_id)
);

CREATE INDEX IF NOT EXISTS idx_performance_metrics_operation_id ON performance_metrics(operation_id);

-- Seed lookup values (idempotent)
INSERT INTO key_types(name) VALUES
    ('symmetric'),
    ('asymmetric_private'),
    ('asymmetric_public')
ON CONFLICT (name) DO NOTHING;

INSERT INTO key_usages(name) VALUES
    ('file_encryption'),
    ('key_wrapping'),
    ('signing')
ON CONFLICT (name) DO NOTHING;

INSERT INTO algorithm_types(name) VALUES
    ('symmetric'),
    ('asymmetric')
ON CONFLICT (name) DO NOTHING;

INSERT INTO artifact_types(name) VALUES
    ('encrypted'),
    ('decrypted')
ON CONFLICT (name) DO NOTHING;

INSERT INTO crypto_operation_types(name) VALUES
    ('encrypt'),
    ('decrypt'),
    ('keygen'),
    ('import_key'),
    ('export_key')
ON CONFLICT (name) DO NOTHING;

INSERT INTO result_types(name) VALUES
    ('success'),
    ('fail')
ON CONFLICT (name) DO NOTHING;

INSERT INTO performance_metric_types(name) VALUES
    ('duration_ms'),
    ('peak_rss_kb'),
    ('cpu_ms'),
    ('io_read_bytes'),
    ('io_write_bytes')
ON CONFLICT (name) DO NOTHING;

COMMIT;
