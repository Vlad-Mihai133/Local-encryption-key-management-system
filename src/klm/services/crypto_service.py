from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
_DEFAULT_ARTIFACT_DIR = "/tmp/klm_artifacts"

# Provider identity
_PROVIDER_NAME = "openssl"
_PROVIDER_VERSION = "3"


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
    """Read master key from environment (hex-encoded, 32 bytes = 64 hex chars)."""
    raw = os.environ.get(_MASTER_KEY_ENV)
    if not raw:
        raise RuntimeError(
            f"Environment variable {_MASTER_KEY_ENV} is not set. "
            "Generate one with: openssl rand -hex 32"
        )
    key = bytes.fromhex(raw.strip())
    if len(key) != 32:
        raise ValueError(f"{_MASTER_KEY_ENV} must be exactly 32 bytes (64 hex chars)")
    return key


def _artifact_dir() -> Path:
    d = Path(os.environ.get(_OUTPUT_DIR_ENV, _DEFAULT_ARTIFACT_DIR))
    d.mkdir(parents=True, exist_ok=True)
    return d


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
    iv = bytes.fromhex(encryption_params["iv"])

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

    def _get_or_create_provider(self) -> models.CryptoProvider:
        provider = self.providers.get_by_name(_PROVIDER_NAME)
        if not provider:
            provider = models.CryptoProvider(
                name=_PROVIDER_NAME,
                version=_PROVIDER_VERSION,
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
        provider = self._get_or_create_provider()
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

        Variant name examples: AES-128, AES-192, AES-256, AES-256-GCM, AES-256-CBC.
        We extract the key size (128/192/256 bits) from the variant name or params.
        """
        # Try to read key size from variant params, fall back to parsing name
        key_bits = variant.params.get("key_bits")
        if not key_bits:
            for part in variant.name.replace("-", " ").split():
                if part.isdigit():
                    key_bits = int(part)
                    break
        if not key_bits:
            key_bits = 256  # sensible default

        key_bytes_count = int(key_bits) // 8
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
        provider = self._get_or_create_provider()
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
            params=params,
            started_at=started_at,
            result_type_id=result_type_success.id,
        )
        self.operations.add(operation)
        self.session.flush()

        try:
            # Decrypt key material from DB
            key_bytes = _decrypt_bytes_with_master(
                bytes(key.encrypted_material), key.encryption_params
            )

            # Determine output path
            out_path = _artifact_dir() / f"{file_record.id}_{variant.name}.enc"

            # Run OpenSSL encryption
            self._openssl_encrypt_file(
                src=str(src),
                dst=str(out_path),
                key_bytes=key_bytes,
                variant=variant,
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
        # Store IV in variant params for later use (or pass via params dict)
        # We embed IV into the output artifact path metadata via a sidecar file
        meta_path = dst + ".meta"
        with open(meta_path, "w") as f:
            json.dump({"cipher": cipher, "iv": iv.hex()}, f)

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

        provider = self._get_or_create_provider()
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
            params=params,
            started_at=started_at,
            result_type_id=result_type_success.id,
        )
        self.operations.add(operation)
        self.session.flush()

        try:
            key_bytes = _decrypt_bytes_with_master(
                bytes(key.encrypted_material), key.encryption_params
            )

            enc_path = Path(artifact.path)
            meta_path = str(enc_path) + ".meta"
            if not Path(meta_path).exists():
                raise RuntimeError(f"Metadata file not found: {meta_path}")

            with open(meta_path) as f:
                meta = json.load(f)

            cipher = meta["cipher"]
            iv = bytes.fromhex(meta["iv"])

            out_path = _artifact_dir() / f"{artifact.file_id}_decrypted{enc_path.suffix}"

            cmd = [
                "openssl", "enc", f"-{cipher}", "-d",
                "-K", key_bytes.hex(),
                "-iv", iv.hex(),
                "-nosalt",
                "-in", str(enc_path),
                "-out", str(out_path),
            ]
            _run(cmd)

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
        if variant_name:
            variant = self.variants.get(key.algorithm_id)
            if variant and variant.name == variant_name:
                return variant
            # Try to find by name within the same algorithm
            alg_variant = self.variants.get(key.algorithm_id)
            if alg_variant:
                found = AlgorithmVariantRepository(self.session).get_by_name(
                    variant_name, alg_variant.algorithm_id
                )
                if found:
                    return found
        variant = self.variants.get(key.algorithm_id)
        if not variant:
            raise ValueError(f"Could not resolve AlgorithmVariant for key '{key.id}'.")
        return variant

    def _cipher_and_iv_for_variant(
        self, variant: models.AlgorithmVariant
    ) -> tuple[str, bytes]:
        """Map variant name to an OpenSSL cipher string and generate a fresh IV."""
        name_upper = variant.name.upper()

        # Determine IV size: GCM/CCM use 12 bytes, CBC/CTR use 16 bytes
        if "GCM" in name_upper or "CCM" in name_upper:
            iv_size = 12
        else:
            iv_size = 16

        # Map to OpenSSL cipher name
        cipher_map = {
            "AES-256-GCM": "aes-256-cbc",   # OpenSSL CLI doesn't support GCM directly; use CBC fallback
            "AES-256-CBC": "aes-256-cbc",
            "AES-128-CBC": "aes-128-cbc",
            "AES-192-CBC": "aes-192-cbc",
            "AES-256-CTR": "aes-256-ctr",
            "AES-128-GCM": "aes-128-cbc",
        }
        cipher = cipher_map.get(name_upper)
        if not cipher:
            # Try to derive from variant params or use a safe default
            cipher = variant.params.get("openssl_cipher", "aes-256-cbc")

        iv = os.urandom(iv_size)
        return cipher, iv

    def _get_or_create_file(
        self, src: Path, original_hash: str, original_size: int
    ) -> models.File:
        existing = self.files.get_by_path(str(src.resolve())) if hasattr(self.files, "get_by_path") else None
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
        existing = self.file_artifacts.get_by_file_type_path(
            file_record.id, artifact_type.id, path
        ) if hasattr(self.file_artifacts, "get_by_file_type_path") else None
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