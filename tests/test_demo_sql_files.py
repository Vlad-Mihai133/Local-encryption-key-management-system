from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_seed_demo_algorithms_uses_supported_variants() -> None:
    content = (PROJECT_ROOT / "sql" / "seed_demo_algorithms.sql").read_text(encoding="utf-8")

    assert "AES-128-CBC" in content
    assert "AES-192-CBC" in content
    assert "AES-256-CBC" in content
    assert "AES-256-CTR" in content
    assert "AES-256-GCM" in content


def test_cleanup_script_targets_legacy_demo_variants_safely() -> None:
    content = (PROJECT_ROOT / "sql" / "cleanup_legacy_demo_variants.sql").read_text(encoding="utf-8")

    assert "AES-128-GCM" in content
    assert "crypto_operations" in content
    assert "keys" in content
    assert "RAISE NOTICE" in content


def test_migration_script_still_targets_algorithm_variants() -> None:
    content = (PROJECT_ROOT / "sql" / "migrate_keys_algorithm_id_to_variants.sql").read_text(encoding="utf-8")

    assert "algorithm_variants" in content
    assert "ALTER TABLE keys" in content
    assert "algorithm_variant_id" in content