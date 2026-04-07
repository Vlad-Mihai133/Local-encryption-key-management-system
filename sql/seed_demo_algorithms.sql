-- Seed demo data for UI: algorithms + variants
-- Run after schema.sql
--
-- PowerShell example:
--   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U klm_user -W -d klm -f .\sql\seed_demo_algorithms.sql

BEGIN;

-- Algorithms: AES (symmetric), RSA (asymmetric)
WITH symmetric_type AS (
    SELECT id FROM algorithm_types WHERE name = 'symmetric'
)
INSERT INTO algorithms (name, type_id, params)
SELECT 'AES', (SELECT id FROM symmetric_type), '{}'::jsonb
WHERE NOT EXISTS (SELECT 1 FROM algorithms WHERE name = 'AES');

WITH asymmetric_type AS (
    SELECT id FROM algorithm_types WHERE name = 'asymmetric'
)
INSERT INTO algorithms (name, type_id, params)
SELECT 'RSA', (SELECT id FROM asymmetric_type), '{}'::jsonb
WHERE NOT EXISTS (SELECT 1 FROM algorithms WHERE name = 'RSA');

-- Variants for AES
INSERT INTO algorithm_variants (algorithm_id, name, params)
SELECT a.id, 'AES-256-GCM', '{}'::jsonb
FROM algorithms a
WHERE a.name = 'AES'
  AND NOT EXISTS (
      SELECT 1 FROM algorithm_variants av
      WHERE av.algorithm_id = a.id AND av.name = 'AES-256-GCM'
  );

INSERT INTO algorithm_variants (algorithm_id, name, params)
SELECT a.id, 'AES-256-CBC', '{}'::jsonb
FROM algorithms a
WHERE a.name = 'AES'
  AND NOT EXISTS (
      SELECT 1 FROM algorithm_variants av
      WHERE av.algorithm_id = a.id AND av.name = 'AES-256-CBC'
  );

-- Variants for RSA
INSERT INTO algorithm_variants (algorithm_id, name, params)
SELECT a.id, 'RSA-2048', '{}'::jsonb
FROM algorithms a
WHERE a.name = 'RSA'
  AND NOT EXISTS (
      SELECT 1 FROM algorithm_variants av
      WHERE av.algorithm_id = a.id AND av.name = 'RSA-2048'
  );

INSERT INTO algorithm_variants (algorithm_id, name, params)
SELECT a.id, 'RSA-3072', '{}'::jsonb
FROM algorithms a
WHERE a.name = 'RSA'
  AND NOT EXISTS (
      SELECT 1 FROM algorithm_variants av
      WHERE av.algorithm_id = a.id AND av.name = 'RSA-3072'
  );

COMMIT;
