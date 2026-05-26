-- Cleanup pentru variante demo legacy care nu mai sunt expuse de seed-ul curent.
--
-- Ce face:
-- 1) identifica variantele AEAD demo vechi care NU mai sunt seed-uite (ex. AES-128-GCM)
-- 2) le sterge DOAR daca nu sunt referite din `keys` sau `crypto_operations`
-- 3) afiseaza NOTICE pentru variantele pastrate din cauza referintelor existente

BEGIN;

DO $$
DECLARE
    variant_record record;
    key_refs bigint;
    operation_refs bigint;
BEGIN
    FOR variant_record IN
        SELECT av.id, av.name
        FROM algorithm_variants av
        JOIN algorithms a ON a.id = av.algorithm_id
        WHERE a.name = 'AES'
                    AND av.name IN ('AES-128-GCM')
    LOOP
        SELECT COUNT(*) INTO key_refs
        FROM keys k
        WHERE k.algorithm_id = variant_record.id;

        SELECT COUNT(*) INTO operation_refs
        FROM crypto_operations co
        WHERE co.algorithm_variant_id = variant_record.id;

        IF key_refs = 0 AND operation_refs = 0 THEN
            DELETE FROM algorithm_variants av
            WHERE av.id = variant_record.id;

            RAISE NOTICE 'Cleanup: varianta legacy % a fost stearsa.', variant_record.name;
        ELSE
            RAISE NOTICE 'Cleanup: varianta legacy % a fost pastrata (keys=%, operations=%).',
                variant_record.name, key_refs, operation_refs;
        END IF;
    END LOOP;
END $$;

COMMIT;