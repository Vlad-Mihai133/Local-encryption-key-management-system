from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from klm.services.crypto_service import CryptoService


OPENSSL_AVAILABLE = shutil.which("openssl") is not None


def _service() -> CryptoService:
    return object.__new__(CryptoService)


def _variant(name: str, **params):
    return SimpleNamespace(name=name, params=params)


def _read_meta(path: Path) -> dict[str, str]:
    return _service()._read_artifact_metadata(str(path))


def test_auto_backend_prefers_cryptography_for_gcm() -> None:
    service = _service()
    backend = service._select_file_backend({}, variant=_variant("AES-256-GCM"))
    assert backend == "cryptography"


def test_cryptography_backend_roundtrip_gcm(tmp_path: Path) -> None:
    service = _service()
    key = bytes.fromhex("00" * 32)
    variant = _variant("AES-256-GCM")
    src = tmp_path / "plain.txt"
    enc = tmp_path / "cipher.bin"
    dec = tmp_path / "plain.out"
    payload = b"mesaj de test pentru GCM via cryptography"
    src.write_bytes(payload)

    service._cryptography_encrypt_file(str(src), str(enc), key, variant)
    meta = _read_meta(enc)

    service._cryptography_decrypt_file(
        src=str(enc),
        dst=str(dec),
        key_bytes=key,
        variant=variant,
        meta=meta,
    )

    assert dec.read_bytes() == payload
    assert meta["backend"] == "cryptography"
    assert meta["mode"] == "GCM"
    assert "tag" in meta


def test_decrypted_output_name_uses_original_name_from_metadata() -> None:
    service = _service()
    output_name = service._decrypted_output_name(
        enc_path=Path("test.txt.AES-256-GCM.enc"),
        meta={"original_name": "test.txt.txt"},
    )

    assert output_name == "test.txt.decrypted.txt"


def test_merge_artifact_metadata_preserves_backend_fields(tmp_path: Path) -> None:
    service = _service()
    artifact = tmp_path / "cipher.bin"
    service._write_artifact_metadata(str(artifact), {"backend": "cryptography", "mode": "GCM"})

    service._merge_artifact_metadata(
        str(artifact),
        {"original_name": "hello.txt", "algorithm_variant": "AES-256-GCM"},
    )
    meta = _read_meta(artifact)

    assert meta["backend"] == "cryptography"
    assert meta["mode"] == "GCM"
    assert meta["original_name"] == "hello.txt"
    assert meta["algorithm_variant"] == "AES-256-GCM"


@pytest.mark.skipif(not OPENSSL_AVAILABLE, reason="openssl CLI is required for cross-backend tests")
def test_openssl_encrypt_cryptography_decrypt_cbc(tmp_path: Path) -> None:
    service = _service()
    key = bytes.fromhex("11" * 32)
    variant = _variant("AES-256-CBC")
    src = tmp_path / "plain.txt"
    enc = tmp_path / "cipher.bin"
    dec = tmp_path / "plain.out"
    payload = b"compatibility test between openssl and cryptography" * 3
    src.write_bytes(payload)

    service._openssl_encrypt_file(str(src), str(enc), key, variant)
    meta = _read_meta(enc)

    service._cryptography_decrypt_file(
        src=str(enc),
        dst=str(dec),
        key_bytes=key,
        variant=variant,
        meta=meta,
    )

    assert dec.read_bytes() == payload
    assert meta["backend"] == "openssl"


@pytest.mark.skipif(not OPENSSL_AVAILABLE, reason="openssl CLI is required for cross-backend tests")
def test_cryptography_encrypt_openssl_decrypt_cbc(tmp_path: Path) -> None:
    service = _service()
    key = bytes.fromhex("22" * 32)
    variant = _variant("AES-256-CBC")
    src = tmp_path / "plain.txt"
    enc = tmp_path / "cipher.bin"
    dec = tmp_path / "plain.out"
    payload = b"backend interoperability works in both directions" * 2
    src.write_bytes(payload)

    service._cryptography_encrypt_file(str(src), str(enc), key, variant)
    meta = _read_meta(enc)

    service._openssl_decrypt_file(
        src=str(enc),
        dst=str(dec),
        key_bytes=key,
        meta={"cipher": "aes-256-cbc", "iv": meta["iv"]},
    )

    assert dec.read_bytes() == payload
    assert meta["backend"] == "cryptography"