-- Migrare: aliniaza `keys.algorithm_id` sa refere `algorithm_variants(id)`.
--
-- Cand ai nevoie de asta?
-- - Doar daca baza ta de date a fost creata cu o schema veche in care:
--   `keys.algorithm_id -> algorithms(id)`.
--
-- Ce face scriptul:
-- 1) Adauga o coloana temporara `algorithm_variant_id`
-- 2) Map-eaza fiecare cheie la o varianta (prima varianta a algoritmului)
-- 3) Valideaza ca toate cheile au fost mapate
-- 4) Schimba FK-ul si redenumeste coloana inapoi la `algorithm_id`
--
-- Atentie:
-- - Daca un algoritm NU are nici o varianta in `algorithm_variants`, migrarea se opreste cu eroare.
-- - Mapping-ul poate fi ambigu (un algoritm poate avea mai multe variante). Scriptul alege prima varianta
--   dupa `created_at` (apoi `id`). Daca vrei alt criteriu, ajusteaza UPDATE-ul.

BEGIN;

DO $$
DECLARE
    fk_target text;
    unmapped_count bigint;
BEGIN
    -- Detectam tinta FK-ului curent (daca exista constraint-ul clasic).
    SELECT c2.relname
    INTO fk_target
    FROM pg_constraint con
    JOIN pg_class c1 ON c1.oid = con.conrelid
    JOIN pg_class c2 ON c2.oid = con.confrelid
    WHERE con.contype = 'f'
      AND c1.relname = 'keys'
      AND con.conname = 'keys_algorithm_id_fkey';

    IF fk_target = 'algorithm_variants' THEN
        RAISE NOTICE 'Migrare: deja OK (keys_algorithm_id_fkey -> algorithm_variants).';
        RETURN;
    ELSIF fk_target IS NOT NULL AND fk_target <> 'algorithms' THEN
        RAISE EXCEPTION 'Migrare: FK unexpected. keys_algorithm_id_fkey pointeaza la: %', fk_target;
    END IF;

    -- Heuristic: daca nu exista FK, incercam sa detectam dupa valori.
    IF fk_target IS NULL THEN
        SELECT COUNT(*)
        INTO unmapped_count
        FROM keys k
        LEFT JOIN algorithm_variants av ON av.id = k.algorithm_id
        WHERE av.id IS NULL;

        IF unmapped_count = 0 THEN
            RAISE NOTICE 'Migrare: nu exista FK, dar valorile keys.algorithm_id arata ca sunt deja variante. Skip.';
            RETURN;
        END IF;
    END IF;

    EXECUTE 'ALTER TABLE keys ADD COLUMN IF NOT EXISTS algorithm_variant_id uuid';

    -- Mapare: keys.algorithm_id (vechi: algorithms.id) -> algorithm_variants.id
    EXECUTE $sql$
        UPDATE keys k
        SET algorithm_variant_id = av_pick.id
        FROM LATERAL (
            SELECT av.id
            FROM algorithm_variants av
            WHERE av.algorithm_id = k.algorithm_id
            ORDER BY av.created_at ASC, av.id ASC
            LIMIT 1
        ) av_pick
        WHERE k.algorithm_variant_id IS NULL
    $sql$;

    SELECT COUNT(*)
    INTO unmapped_count
    FROM keys
    WHERE algorithm_variant_id IS NULL;

    IF unmapped_count > 0 THEN
        RAISE EXCEPTION 'Migrare blocata: % chei nu au putut fi mapate la o varianta. Creeaza variantele lipsa in algorithm_variants sau seteaza manual.', unmapped_count;
    END IF;

    -- Schimbam constraint-ul.
    EXECUTE 'ALTER TABLE keys DROP CONSTRAINT IF EXISTS keys_algorithm_id_fkey';

    EXECUTE 'ALTER TABLE keys ADD CONSTRAINT keys_algorithm_variant_id_fkey FOREIGN KEY (algorithm_variant_id) REFERENCES algorithm_variants(id) ON DELETE RESTRICT';

    -- Inlocuim coloana veche.
    EXECUTE 'ALTER TABLE keys DROP COLUMN IF EXISTS algorithm_id';
    EXECUTE 'ALTER TABLE keys RENAME COLUMN algorithm_variant_id TO algorithm_id';
    EXECUTE 'ALTER TABLE keys RENAME CONSTRAINT keys_algorithm_variant_id_fkey TO keys_algorithm_id_fkey';

    -- Index (recreat pe coloana noua).
    EXECUTE 'DROP INDEX IF EXISTS idx_keys_algorithm_id';
    EXECUTE 'CREATE INDEX IF NOT EXISTS idx_keys_algorithm_id ON keys(algorithm_id)';

    RAISE NOTICE 'Migrare completata: keys.algorithm_id -> algorithm_variants(id)';
END $$;

COMMIT;
