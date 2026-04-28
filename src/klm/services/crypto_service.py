from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from secrets import token_bytes
from typing import Any

from cryptography import __version__ as _CRYPTOGRAPHY_VERSION
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from sqlalchemy import select
from sqlalchemy.orm import Session

from klm.db import models
from klm.db.repositories import (
    AlgorithmVariantRepository,
    ArtifactTypeRepository,
    CryptoOperationRepository,
    CryptoProviderRepository,
    CryptoOperationTypeRepository,
    FileRepository,
    FileArtifactRepository,
    KeyRepository,
    KeyTypeRepository,
    KeyUsageRepository,
    PerformanceMetricRepository,
    PerformanceMetricTypeRepository,
    ResultTypeRepository,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Master key used to encrypt key material stored in DB.
# MUST be set in environment. 32 bytes hex-encoded = AES-256 key.
_MASTER_KEY_ENV = "KLM_MASTER_KEY"
_OUTPUT_DIR_ENV = "KLM_ARTIFACT_DIR"
_DEFAULT_ARTIFACT_DIR = str(Path(tempfile.gettempdir()) / "klm_artifacts")

# If KLM_MASTER_KEY is not provided, we persist a generated key here (project root).
_MASTER_KEY_FILE_NAME = ".klm_master_key"

# Provider identity
_PROVIDER_NAME = "openssl"
_PROVIDER_VERSION = "3"
_CRYPTOGRAPHY_PROVIDER_NAME = "cryptography"
_DEFAULT_FILE_BACKEND = "openssl"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], input_data: bytes | None = None) -> bytes:
    """Run an OpenSSL subprocess and return stdout bytes.

    Raises RuntimeError on non-zero exit.
    """
    result = subprocess.run(
        cmd,
        input=input_data,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"OpenSSL command failed: {' '.join(cmd)}\n"
            f"stderr: {result.stderr.decode(errors='replace')}"
        )
    return result.stdout


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _get_master_key() -> bytes:
    """Get master key bytes used to encrypt/decrypt key material stored in DB.

    Order of resolution:
    1) If env var `KLM_MASTER_KEY` is set -> use it.
    2) Else, try to load it from a local file `.klm_master_key` in the project root.
    3) Else, generate a new random 32-byte key, persist it to that file, and use it.

    The key is hex-encoded when stored in env/file.
    """

    def _parse_hex_key(raw_hex: str) -> bytes:
        key_bytes = bytes.fromhex(raw_hex.strip())
        if len(key_bytes) != 32:
            raise ValueError(
                f"{_MASTER_KEY_ENV} must be exactly 32 bytes (64 hex chars), got {len(key_bytes)} bytes"
            )
        return key_bytes

    raw = os.environ.get(_MASTER_KEY_ENV)
    if raw:
        return _parse_hex_key(raw)

    project_root = _find_project_root()
    key_file = project_root / _MASTER_KEY_FILE_NAME

    if key_file.exists():
        key_hex = key_file.read_text(encoding="utf-8").strip()
        key = _parse_hex_key(key_hex)
        os.environ[_MASTER_KEY_ENV] = key_hex
        return key

    # Generate and persist a new master key.
    key = token_bytes(32)
    key_hex = key.hex()
    key_file.write_text(key_hex + "\n", encoding="utf-8")
    os.environ[_MASTER_KEY_ENV] = key_hex
    return key


def _find_project_root() -> Path:
    """Find the project root directory.

    We look for `pyproject.toml` in parents of this file.
    Falls back to current working directory.
    """
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd().resolve()


def _artifact_dir() -> Path:
    d = Path(os.environ.get(_OUTPUT_DIR_ENV, _DEFAULT_ARTIFACT_DIR))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _results_dir_for_dir(directory: Path) -> Path:
    """Return `<directory>/results` ensuring it exists."""
    results_dir = directory.resolve() / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    return results_dir


def _is_under(child: Path, parent: Path) -> bool:
    """Return True if `child` is inside `parent` (path-wise)."""
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except Exception:
        return False


def _encrypt_bytes_with_master(plaintext: bytes) -> tuple[bytes, dict[str, Any]]:
    """Encrypt plaintext bytes with the master key using AES-256-CBC via OpenSSL subprocess.

    Returns (ciphertext, encryption_params).
    encryption_params contains the IV (hex) needed for decryption.
    """
    master_key = _get_master_key()
    iv = os.urandom(16)

    # openssl enc -aes-256-cbc -K <hex_key> -iv <hex_iv> -nosalt
    ciphertext = _run(
        [
            "openssl", "enc", "-aes-256-cbc",
            "-K", master_key.hex(),
            "-iv", iv.hex(),
            "-nosalt",
        ],
        input_data=plaintext,
    )

    params = {
        "scheme": "aes-256-cbc",
        "iv": iv.hex(),
    }
    return ciphertext, params


def _decrypt_bytes_with_master(ciphertext: bytes, encryption_params: dict[str, Any]) -> bytes:
    """Decrypt ciphertext bytes with the master key."""
    master_key = _get_master_key()
    iv_hex = encryption_params.get("iv")
    if not iv_hex:
        raise KeyError("iv")
    iv = bytes.fromhex(iv_hex)

    plaintext = _run(
        [
            "openssl", "enc", "-aes-256-cbc", "-d",
            "-K", master_key.hex(),
            "-iv", iv.hex(),
            "-nosalt",
        ],
        input_data=ciphertext,
    )
    return plaintext


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

@dataclass
class CryptoService:
    """Crypto service backed by OpenSSL subprocesses.

    Supported operations:
    - keygen  : generate AES or RSA keys, store encrypted in DB
    - encrypt_file : encrypt a file with an existing key
    - decrypt_file : decrypt an encrypted artifact
    """

    session: Session

    def __post_init__(self) -> None:
        self.keys = KeyRepository(self.session)
        self.files = FileRepository(self.session)
        self.operations = CryptoOperationRepository(self.session)
        self.metrics = PerformanceMetricRepository(self.session)
        self.file_artifacts = FileArtifactRepository(self.session)
        self.variants = AlgorithmVariantRepository(self.session)
        self.key_types = KeyTypeRepository(self.session)
        self.key_usages = KeyUsageRepository(self.session)
        self.artifact_types = ArtifactTypeRepository(self.session)
        self.crypto_op_types = CryptoOperationTypeRepository(self.session)
        self.result_types = ResultTypeRepository(self.session)
        self.providers = CryptoProviderRepository(self.session)
        self.metric_types = PerformanceMetricTypeRepository(self.session)

    # ------------------------------------------------------------------
    # Internal lookup helpers
    # ------------------------------------------------------------------

    def _get_key_bytes(self, key: models.Key) -> bytes:
        """Return usable key material bytes for OpenSSL.

        Expected DB format is encrypted (BYTEA) + encryption_params containing an IV.
        For backwards compatibility with old UI-imported keys, if the IV is missing
        we treat `encrypted_material` as already-raw key bytes.
        """
        try:
            if isinstance(key.encryption_params, dict) and key.encryption_params.get("iv"):
                return _decrypt_bytes_with_master(bytes(key.encrypted_material), key.encryption_params)
        except KeyError:
            # fall through to raw
            pass

        # Legacy/"import" keys: material stored as-is.
        return bytes(key.encrypted_material)

    def _find_original_decrypted_path(self, file_id: uuid.UUID) -> Path | None:
        """Best-effort: find the path of the originally added plaintext file.

        We prefer a decrypted artifact path that is *outside* our artifact temp dir
        (e.g. a user-selected file on Desktop/Project folder), because later decrypt
        operations may create additional decrypted artifacts under temp.
        """
        decrypted_type = self._require_artifact_type("decrypted")
        artifact_root = _artifact_dir().resolve(strict=False)

        stmt = (
            select(models.FileArtifact)
            .where(
                models.FileArtifact.file_id == file_id,
                models.FileArtifact.artifact_type_id == decrypted_type.id,
            )
            .order_by(models.FileArtifact.created_at.asc())
        )

        for art in self.session.scalars(stmt):
            if not art.path:
                continue
            p = Path(art.path).resolve(strict=False)
            name_lower = p.name.lower()

            # Ignore meta sidecars and encrypted-looking files.
            if name_lower.endswith(".meta"):
                continue
            if name_lower.endswith(".enc") or ".enc." in name_lower:
                continue

            # Prefer paths outside artifact temp dir.
            if _is_under(p, artifact_root):
                continue

            return p

        return None

    def _require_key_type(self, name: str) -> models.KeyType:
        kt = self.key_types.get_by_name(name)
        if not kt:
            raise ValueError(f"KeyType '{name}' not found in DB. Check seed data.")
        return kt

    def _require_key_usage(self, name: str) -> models.KeyUsage:
        ku = self.key_usages.get_by_name(name)
        if not ku:
            raise ValueError(f"KeyUsage '{name}' not found in DB. Check seed data.")
        return ku

    def _require_artifact_type(self, name: str) -> models.ArtifactType:
        at = self.artifact_types.get_by_name(name)
        if not at:
            raise ValueError(f"ArtifactType '{name}' not found in DB. Check seed data.")
        return at

    def _require_op_type(self, name: str) -> models.CryptoOperationType:
        ot = self.crypto_op_types.get_by_name(name)
        if not ot:
            raise ValueError(f"CryptoOperationType '{name}' not found in DB. Check seed data.")
        return ot

    def _require_result_type(self, name: str) -> models.ResultType:
        rt = self.result_types.get_by_name(name)
        if not rt:
            raise ValueError(f"ResultType '{name}' not found in DB. Check seed data.")
        return rt

    def _provider_identity(self, backend: str) -> tuple[str, str]:
        if backend == _CRYPTOGRAPHY_PROVIDER_NAME:
            return _CRYPTOGRAPHY_PROVIDER_NAME, _CRYPTOGRAPHY_VERSION
        if backend == _PROVIDER_NAME:
            return _PROVIDER_NAME, _PROVIDER_VERSION
        raise ValueError(f"Unsupported crypto backend '{backend}'.")

    def _get_or_create_provider(self, backend: str = _PROVIDER_NAME) -> models.CryptoProvider:
        provider_name, provider_version = self._provider_identity(backend)
        provider = self.providers.get_by_name(provider_name)
        if not provider:
            provider = models.CryptoProvider(
                name=provider_name,
                version=provider_version,
                runtime_info={},
            )
            self.providers.add(provider)
            self.session.flush()
        return provider

    def _require_metric_type(self, name: str) -> models.PerformanceMetricType:
        mt = self.metric_types.get_by_name(name)
        if not mt:
            raise ValueError(f"PerformanceMetricType '{name}' not found in DB.")
        return mt

    # ------------------------------------------------------------------
    # keygen
    # ------------------------------------------------------------------

    def keygen(
        self,
        *,
        algorithm: str,
        key_type: str,
        usage: str,
        name: str,
        params: dict[str, Any],
    ) -> uuid.UUID:
        """Generate a key (AES or RSA) and store it encrypted in the DB.

        params must contain:
          - variant_id (str UUID): the AlgorithmVariant to associate with the key

        Returns the new key's UUID.
        """
        if self.keys.exists_by_name(name):
            raise ValueError(f"A key named '{name}' already exists.")

        variant_id = uuid.UUID(params["variant_id"])
        variant = self.variants.get(variant_id)
        if not variant:
            raise ValueError(f"AlgorithmVariant '{variant_id}' not found.")

        kt = self._require_key_type(key_type)
        ku = self._require_key_usage(usage)
        provider = self._get_or_create_provider(_PROVIDER_NAME)
        op_type = self._require_op_type("keygen")
        result_type_success = self._require_result_type("success")
        result_type_fail = self._require_result_type("fail")

        started_at = datetime.now(timezone.utc)
        t0 = time.perf_counter()

        operation = models.CryptoOperation(
            operation_type_id=op_type.id,
            provider_id=provider.id,
            algorithm_variant_id=variant.id,
            params=params,
            started_at=started_at,
            result_type_id=result_type_success.id,
        )
        self.operations.add(operation)
        self.session.flush()

        try:
            key_bytes = self._generate_key_bytes(algorithm.upper(), variant)
            encrypted_material, enc_params = _encrypt_bytes_with_master(key_bytes)
            elapsed_ms = (time.perf_counter() - t0) * 1000

            key = models.Key(
                name=name,
                type_id=kt.id,
                algorithm_id=variant.id,
                usage_id=ku.id,
                status="active",
                encrypted_material=encrypted_material,
                material_format="raw",
                encryption_scheme="app-level-aes-256-cbc",
                encryption_params=enc_params,
            )
            self.keys.add(key)
            self.session.flush()

            operation.key_id = key.id
            operation.ended_at = datetime.now(timezone.utc)
            self._record_duration(operation, elapsed_ms)

            return key.id

        except Exception as exc:
            operation.result_type_id = result_type_fail.id
            operation.ended_at = datetime.now(timezone.utc)
            operation.error_message = str(exc)
            raise

    def _generate_key_bytes(self, algorithm: str, variant: models.AlgorithmVariant) -> bytes:
        """Dispatch to the correct OpenSSL keygen command."""
        if algorithm == "AES":
            return self._gen_aes_key(variant)
        elif algorithm == "RSA":
            return self._gen_rsa_key(variant)
        else:
            raise NotImplementedError(f"Key generation for algorithm '{algorithm}' is not supported.")

    def _gen_aes_key(self, variant: models.AlgorithmVariant) -> bytes:
        """Generate random AES key bytes.

        Variant name examples: AES-128-CBC, AES-192-CBC, AES-256-CBC, AES-256-CTR.
        We extract the key size (128/192/256 bits) from the variant name or params.
        """
        # Try to read key size from variant params, fall back to parsing name
        key_bytes_count = self._key_bits_for_variant(variant) // 8
        # openssl rand -hex <n> returns hex string; we use binary output
        raw = _run(["openssl", "rand", str(key_bytes_count)])
        return raw

    def _gen_rsa_key(self, variant: models.AlgorithmVariant) -> bytes:
        """Generate RSA private key in PEM format.

        Variant name examples: RSA-2048, RSA-4096.
        """
        key_bits = variant.params.get("key_bits")
        if not key_bits:
            for part in variant.name.replace("-", " ").split():
                if part.isdigit():
                    key_bits = int(part)
                    break
        if not key_bits:
            key_bits = 2048

        pem = _run(["openssl", "genrsa", str(int(key_bits))])
        return pem

    # ------------------------------------------------------------------
    # encrypt_file
    # ------------------------------------------------------------------

    def encrypt_file(
        self,
        *,
        file_path: str,
        key_id: uuid.UUID,
        algorithm_variant: str,
        params: dict[str, Any],
    ) -> uuid.UUID:
        """Encrypt a file using an existing key from DB.

        Returns the UUID of the output (encrypted) FileArtifact.
        """
        src = Path(file_path)
        if not src.exists():
            raise ValueError(f"File not found: {file_path}")

        key = self.keys.get(key_id)
        if not key:
            raise ValueError(f"Key '{key_id}' not found.")
        if key.status != "active":
            raise ValueError(f"Key '{key_id}' is not active (status={key.status}).")

        variant = self._resolve_variant(key, algorithm_variant)
        operation_params = dict(params)
        backend = self._select_file_backend(operation_params, variant=variant)
        provider = self._get_or_create_provider(backend)
        op_type = self._require_op_type("encrypt")
        result_type_success = self._require_result_type("success")
        result_type_fail = self._require_result_type("fail")
        encrypted_type = self._require_artifact_type("encrypted")
        decrypted_type = self._require_artifact_type("decrypted")

        # Create or get File record for the source file
        original_hash = _sha256_file(file_path)
        original_size = src.stat().st_size
        file_record = self._get_or_create_file(src, original_hash, original_size)
        self.session.flush()

        # Source artifact (decrypted/original)
        input_artifact = self._get_or_create_artifact(
            file_record, decrypted_type, str(src.resolve()), original_size, original_hash
        )
        self.session.flush()

        started_at = datetime.now(timezone.utc)
        t0 = time.perf_counter()

        operation = models.CryptoOperation(
            operation_type_id=op_type.id,
            file_id=file_record.id,
            input_artifact_id=input_artifact.id,
            provider_id=provider.id,
            algorithm_variant_id=variant.id,
            key_id=key.id,
            params={**operation_params, "crypto_backend": backend},
            started_at=started_at,
            result_type_id=result_type_success.id,
        )
        self.operations.add(operation)
        self.session.flush()

        try:
            key_bytes = self._get_key_bytes(key)

            # Determine output path: put results next to the originally added file (if we can find it).
            original_path = self._find_original_decrypted_path(file_record.id)
            base_dir = (original_path.parent if original_path else src.resolve().parent)
            out_dir = _results_dir_for_dir(base_dir)
            base_name = (original_path.stem if original_path else src.stem)
            out_name = f"{base_name}.{variant.name}.enc"
            out_path = self._next_available_artifact_path(
                file_record.id,
                encrypted_type.id,
                out_dir / out_name,
            )

            self._encrypt_file_with_backend(
                backend=backend,
                src=str(src),
                dst=str(out_path),
                key_bytes=key_bytes,
                variant=variant,
            )
            self._merge_artifact_metadata(
                str(out_path),
                {
                    "original_name": file_record.original_name,
                    "original_suffix": Path(file_record.original_name).suffix,
                    "algorithm_variant": variant.name,
                },
            )

            elapsed_ms = (time.perf_counter() - t0) * 1000
            enc_hash = _sha256_file(str(out_path))
            enc_size = out_path.stat().st_size

            # Output artifact
            output_artifact = models.FileArtifact(
                file_id=file_record.id,
                artifact_type_id=encrypted_type.id,
                path=str(out_path),
                size_bytes=enc_size,
                hash=enc_hash,
            )
            self.file_artifacts.add(output_artifact)
            self.session.flush()

            operation.output_artifact_id = output_artifact.id
            operation.ended_at = datetime.now(timezone.utc)
            self._record_duration(operation, elapsed_ms)

            return output_artifact.id

        except Exception as exc:
            operation.result_type_id = result_type_fail.id
            operation.ended_at = datetime.now(timezone.utc)
            operation.error_message = str(exc)
            raise

    def _openssl_encrypt_file(
        self,
        src: str,
        dst: str,
        key_bytes: bytes,
        variant: models.AlgorithmVariant,
    ) -> None:
        """Encrypt src -> dst using openssl enc."""
        cipher, iv = self._cipher_and_iv_for_variant(variant)
        cmd = [
            "openssl", "enc", f"-{cipher}",
            "-K", key_bytes.hex(),
            "-iv", iv.hex(),
            "-nosalt",
            "-in", src,
            "-out", dst,
        ]
        _run(cmd)
        self._write_artifact_metadata(dst, {"backend": _PROVIDER_NAME, "cipher": cipher, "iv": iv.hex()})

    def _cryptography_encrypt_file(
        self,
        src: str,
        dst: str,
        key_bytes: bytes,
        variant: models.AlgorithmVariant,
    ) -> None:
        plaintext = Path(src).read_bytes()
        cipher, mode_name, iv = self._build_cryptography_cipher(key_bytes, variant)
        encryptor = cipher.encryptor()

        if mode_name == "CBC":
            padder = padding.PKCS7(algorithms.AES.block_size).padder()
            plaintext = padder.update(plaintext) + padder.finalize()

        ciphertext = encryptor.update(plaintext) + encryptor.finalize()
        Path(dst).write_bytes(ciphertext)

        meta = {
            "backend": _CRYPTOGRAPHY_PROVIDER_NAME,
            "mode": mode_name,
            "iv": iv.hex(),
        }
        if mode_name == "GCM":
            meta["tag"] = encryptor.tag.hex()
        self._write_artifact_metadata(dst, meta)

    def _encrypt_file_with_backend(
        self,
        *,
        backend: str,
        src: str,
        dst: str,
        key_bytes: bytes,
        variant: models.AlgorithmVariant,
    ) -> None:
        if backend == _PROVIDER_NAME:
            self._openssl_encrypt_file(src=src, dst=dst, key_bytes=key_bytes, variant=variant)
            return
        if backend == _CRYPTOGRAPHY_PROVIDER_NAME:
            self._cryptography_encrypt_file(src=src, dst=dst, key_bytes=key_bytes, variant=variant)
            return
        raise ValueError(f"Unsupported crypto backend '{backend}'.")

    # ------------------------------------------------------------------
    # decrypt_file
    # ------------------------------------------------------------------

    def decrypt_file(
        self,
        *,
        artifact_id: uuid.UUID,
        key_id: uuid.UUID,
        params: dict[str, Any],
    ) -> uuid.UUID:
        """Decrypt an encrypted FileArtifact.

        Returns the UUID of the output (decrypted) FileArtifact.
        """
        artifact = self.file_artifacts.get(artifact_id)
        if not artifact:
            raise ValueError(f"FileArtifact '{artifact_id}' not found.")

        key = self.keys.get(key_id)
        if not key:
            raise ValueError(f"Key '{key_id}' not found.")

        variant = self.variants.get(key.algorithm_id)
        if not variant:
            raise ValueError("Could not resolve AlgorithmVariant for key.")

        enc_path = Path(artifact.path)
        meta = self._read_artifact_metadata(str(enc_path))
        backend = self._select_file_backend(params, variant=variant, metadata_backend=meta.get("backend"))
        provider = self._get_or_create_provider(backend)
        op_type = self._require_op_type("decrypt")
        result_type_success = self._require_result_type("success")
        result_type_fail = self._require_result_type("fail")
        decrypted_type = self._require_artifact_type("decrypted")

        started_at = datetime.now(timezone.utc)
        t0 = time.perf_counter()

        operation = models.CryptoOperation(
            operation_type_id=op_type.id,
            file_id=artifact.file_id,
            input_artifact_id=artifact.id,
            provider_id=provider.id,
            algorithm_variant_id=variant.id,
            key_id=key.id,
            params={**params, "crypto_backend": backend},
            started_at=started_at,
            result_type_id=result_type_success.id,
        )
        self.operations.add(operation)
        self.session.flush()

        try:
            key_bytes = self._get_key_bytes(key)

            original_path = self._find_original_decrypted_path(artifact.file_id)
            base_dir = (original_path.parent if original_path else enc_path.resolve().parent)
            out_dir = _results_dir_for_dir(base_dir)

            # Friendly name based on the original, if available.
            if original_path:
                out_name = f"{original_path.stem}.decrypted{original_path.suffix}"
            else:
                out_name = self._decrypted_output_name(enc_path=enc_path, meta=meta)

            out_path = self._next_available_artifact_path(
                artifact.file_id,
                decrypted_type.id,
                out_dir / out_name,
            )

            self._decrypt_file_with_backend(
                backend=backend,
                src=str(enc_path),
                dst=str(out_path),
                key_bytes=key_bytes,
                variant=variant,
                meta=meta,
            )

            elapsed_ms = (time.perf_counter() - t0) * 1000
            dec_hash = _sha256_file(str(out_path))
            dec_size = out_path.stat().st_size

            output_artifact = models.FileArtifact(
                file_id=artifact.file_id,
                artifact_type_id=decrypted_type.id,
                path=str(out_path),
                size_bytes=dec_size,
                hash=dec_hash,
            )
            self.file_artifacts.add(output_artifact)
            self.session.flush()

            operation.output_artifact_id = output_artifact.id
            operation.ended_at = datetime.now(timezone.utc)
            self._record_duration(operation, elapsed_ms)

            return output_artifact.id

        except Exception as exc:
            operation.result_type_id = result_type_fail.id
            operation.ended_at = datetime.now(timezone.utc)
            operation.error_message = str(exc)
            raise

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------

    def _resolve_variant(self, key: models.Key, variant_name: str) -> models.AlgorithmVariant:
        """Resolve AlgorithmVariant by name; falls back to the key's own variant."""
        base_variant = self.variants.get(key.algorithm_id)
        if not base_variant:
            raise ValueError(f"Could not resolve AlgorithmVariant for key '{key.id}'.")

        if not variant_name or base_variant.name == variant_name:
            return base_variant

        # Try to find by name within the same algorithm as the key's variant.
        found = self.variants.get_by_name(variant_name, base_variant.algorithm_id)
        if found:
            return found

        return base_variant

    def _requested_backend(self, params: dict[str, Any]) -> str | None:
        raw = params.get("crypto_backend") or params.get("backend")
        if raw is None:
            return None
        value = str(raw).strip().lower()
        if not value or value == "auto":
            return None
        if value not in {_PROVIDER_NAME, _CRYPTOGRAPHY_PROVIDER_NAME}:
            raise ValueError(f"Unsupported crypto backend '{raw}'.")
        return value

    def _select_file_backend(
        self,
        params: dict[str, Any],
        *,
        variant: models.AlgorithmVariant,
        metadata_backend: str | None = None,
    ) -> str:
        requested = self._requested_backend(params)
        if metadata_backend:
            stored = self._requested_backend({"crypto_backend": metadata_backend}) or _DEFAULT_FILE_BACKEND
            if requested and requested != stored:
                raise ValueError(
                    f"Encrypted artifact was created with backend '{stored}', not '{requested}'."
                )
            return stored
        if requested:
            return requested
        mode_name = self._variant_mode_name(variant)
        if mode_name in {"GCM", "CCM"}:
            return _CRYPTOGRAPHY_PROVIDER_NAME
        return _DEFAULT_FILE_BACKEND

    def _key_bits_for_variant(self, variant: models.AlgorithmVariant) -> int:
        key_bits = variant.params.get("key_bits")
        if not key_bits:
            for part in variant.name.replace("-", " ").split():
                if part.isdigit():
                    key_bits = int(part)
                    break
        if not key_bits:
            key_bits = 256
        return int(key_bits)

    def _variant_mode_name(self, variant: models.AlgorithmVariant) -> str:
        name_upper = variant.name.upper()
        if name_upper.startswith("RSA") or " RSA" in name_upper:
            raise NotImplementedError("encrypt/decrypt is not supported for RSA file variants.")

        for mode_name in ("GCM", "CCM", "CTR", "CBC"):
            if name_upper.endswith(f"-{mode_name}"):
                return mode_name

        mode_name = str(variant.params.get("mode", "CBC")).upper()
        if mode_name in {"CBC", "CTR", "GCM", "CCM"}:
            return mode_name
        raise NotImplementedError(f"Unsupported AES mode '{mode_name}' for variant '{variant.name}'.")

    def _cipher_and_iv_for_variant(
        self, variant: models.AlgorithmVariant
    ) -> tuple[str, bytes]:
        """Map variant name to an OpenSSL cipher string and generate a fresh IV."""
        mode_name = self._variant_mode_name(variant)
        key_bits = self._key_bits_for_variant(variant)

        if mode_name in {"GCM", "CCM"}:
            raise NotImplementedError(
                f"Variant '{variant.name}' is not supported by 'openssl enc' because AEAD ciphers are not available there. "
                "Use CBC/CTR variants or switch to a different crypto backend for GCM/CCM."
            )

        if mode_name not in {"CBC", "CTR"}:
            raise NotImplementedError(f"Variant '{variant.name}' is not supported by 'openssl enc'.")

        cipher = str(variant.params.get("openssl_cipher", f"aes-{key_bits}-{mode_name.lower()}"))

        cipher_upper = cipher.upper()
        if cipher_upper.endswith("-GCM") or cipher_upper.endswith("-CCM"):
            raise NotImplementedError(
                f"OpenSSL cipher '{cipher}' is AEAD and is not supported through 'openssl enc'."
            )

        # Determine IV size based on the *actual cipher* chosen.
        # CBC/CTR use a 16-byte IV for AES.
        iv_size = 16
        iv = os.urandom(iv_size)
        return cipher, iv

    def _build_cryptography_cipher(
        self,
        key_bytes: bytes,
        variant: models.AlgorithmVariant,
        *,
        iv: bytes | None = None,
        tag: bytes | None = None,
    ) -> tuple[Cipher, str, bytes]:
        mode_name = self._variant_mode_name(variant)
        key_bits = self._key_bits_for_variant(variant)
        expected_key_len = key_bits // 8
        if len(key_bytes) != expected_key_len:
            raise ValueError(
                f"Key length mismatch for variant '{variant.name}': expected {expected_key_len} bytes, got {len(key_bytes)}."
            )

        if mode_name in {"CBC", "CTR"}:
            iv = iv or os.urandom(16)
        elif mode_name == "GCM":
            iv = iv or os.urandom(12)
        else:
            raise NotImplementedError(
                f"Variant '{variant.name}' is not supported by the cryptography backend."
            )

        algorithm = algorithms.AES(key_bytes)
        if mode_name == "CBC":
            mode = modes.CBC(iv)
        elif mode_name == "CTR":
            mode = modes.CTR(iv)
        else:
            mode = modes.GCM(iv, tag) if tag is not None else modes.GCM(iv)
        return Cipher(algorithm, mode), mode_name, iv

    def _openssl_decrypt_file(
        self,
        *,
        src: str,
        dst: str,
        key_bytes: bytes,
        meta: dict[str, Any],
    ) -> None:
        try:
            cipher = meta["cipher"]
            iv_hex = meta["iv"]
        except KeyError as exc:
            missing = exc.args[0] if exc.args else "<unknown>"
            raise RuntimeError(f"Metadata file missing '{missing}' for '{src}.meta'.") from exc

        iv = bytes.fromhex(iv_hex)
        cmd = [
            "openssl", "enc", f"-{cipher}", "-d",
            "-K", key_bytes.hex(),
            "-iv", iv.hex(),
            "-nosalt",
            "-in", src,
            "-out", dst,
        ]
        _run(cmd)

    def _cryptography_decrypt_file(
        self,
        *,
        src: str,
        dst: str,
        key_bytes: bytes,
        variant: models.AlgorithmVariant,
        meta: dict[str, Any],
    ) -> None:
        try:
            iv = bytes.fromhex(meta["iv"])
        except KeyError as exc:
            missing = exc.args[0] if exc.args else "<unknown>"
            raise RuntimeError(f"Metadata file missing '{missing}' for '{src}.meta'.") from exc

        tag_hex = meta.get("tag")
        tag = bytes.fromhex(tag_hex) if tag_hex else None
        cipher, mode_name, _ = self._build_cryptography_cipher(key_bytes, variant, iv=iv, tag=tag)
        ciphertext = Path(src).read_bytes()
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        if mode_name == "CBC":
            unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
            plaintext = unpadder.update(plaintext) + unpadder.finalize()

        Path(dst).write_bytes(plaintext)

    def _decrypt_file_with_backend(
        self,
        *,
        backend: str,
        src: str,
        dst: str,
        key_bytes: bytes,
        variant: models.AlgorithmVariant,
        meta: dict[str, Any],
    ) -> None:
        if backend == _PROVIDER_NAME:
            self._openssl_decrypt_file(src=src, dst=dst, key_bytes=key_bytes, meta=meta)
            return
        if backend == _CRYPTOGRAPHY_PROVIDER_NAME:
            self._cryptography_decrypt_file(
                src=src,
                dst=dst,
                key_bytes=key_bytes,
                variant=variant,
                meta=meta,
            )
            return
        raise ValueError(f"Unsupported crypto backend '{backend}'.")

    def _next_available_artifact_path(
        self,
        file_id: uuid.UUID,
        artifact_type_id: uuid.UUID,
        preferred_path: Path,
    ) -> Path:
        candidate = preferred_path
        counter = 2
        while candidate.exists() or self.file_artifacts.get_by_file_type_path(
            file_id,
            artifact_type_id,
            str(candidate),
        ):
            candidate = preferred_path.with_name(
                f"{preferred_path.stem}-{counter}{preferred_path.suffix}"
            )
            counter += 1
        return candidate

    def _decrypted_output_name(self, *, enc_path: Path, meta: dict[str, Any]) -> str:
        original_name = meta.get("original_name")
        if original_name:
            original_path = Path(str(original_name))
            suffix = original_path.suffix
            stem = original_path.stem
            return f"{stem}.decrypted{suffix}"
        return f"{enc_path.stem}.decrypted"

    def _write_artifact_metadata(self, path: str, metadata: dict[str, Any]) -> None:
        meta_path = Path(path + ".meta")
        meta_path.write_text(json.dumps(metadata), encoding="utf-8")

    def _merge_artifact_metadata(self, path: str, extra_metadata: dict[str, Any]) -> None:
        metadata = self._read_artifact_metadata(path)
        metadata.update(extra_metadata)
        self._write_artifact_metadata(path, metadata)

    def _read_artifact_metadata(self, path: str) -> dict[str, Any]:
        meta_path = Path(path + ".meta")
        if not meta_path.exists():
            raise RuntimeError(f"Metadata file not found: {meta_path}")
        return json.loads(meta_path.read_text(encoding="utf-8"))

    def _get_or_create_file(
        self, src: Path, original_hash: str, original_size: int
    ) -> models.File:
        existing = self.files.get_by_path(str(src.resolve()))
        if existing:
            return existing
        file_record = models.File(
            name=src.name,
            original_name=src.name,
            original_size_bytes=original_size,
            original_hash=original_hash,
        )
        self.files.add(file_record)
        return file_record

    def _get_or_create_artifact(
        self,
        file_record: models.File,
        artifact_type: models.ArtifactType,
        path: str,
        size: int,
        hash_: str,
    ) -> models.FileArtifact:
        existing = self.file_artifacts.get_by_file_type_path(file_record.id, artifact_type.id, path)
        if existing:
            return existing
        artifact = models.FileArtifact(
            file_id=file_record.id,
            artifact_type_id=artifact_type.id,
            path=path,
            size_bytes=size,
            hash=hash_,
        )
        self.file_artifacts.add(artifact)
        return artifact

    def _record_duration(self, operation: models.CryptoOperation, elapsed_ms: float) -> None:
        """Record duration_ms PerformanceMetric for a completed operation."""
        try:
            mt = self._require_metric_type("duration_ms")
            metric = models.PerformanceMetric(
                operation_id=operation.id,
                metric_type_id=mt.id,
                value=elapsed_ms,
                unit="ms",
            )
            self.metrics.add(metric)
        except Exception:
            # Non-critical: don't fail the operation if metrics fail
            pass