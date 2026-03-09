from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from klm.db.repositories import (
    CryptoOperationRepository,
    FileRepository,
    KeyRepository,
    PerformanceMetricRepository,
)


@dataclass
class CryptoService:
    """Service-layer placeholder.

    Responsibilities for next sprint:
    1) Key management
       - Generate AES/RSA keys using OpenSSL (or other provider)
       - Encrypt key material before storing in DB ("encrypted_material")
       - Store encryption metadata in "encryption_params" (e.g., iv/nonce, tag, kdf params)
       - Support importing/exporting keys

    2) File operations
       - Encrypt/decrypt files using OpenSSL
       - Persist File + FileArtifact records
       - Persist CryptoOperation records (with started_at/ended_at, success/fail)

    3) Performance measurement
       - Record duration_ms at minimum
       - Optionally record memory/cpu/io metrics and store into PerformanceMetrics

    Notes on key encryption-at-rest (DB):
    - Do NOT store the master key in the database.
    - Use an environment-provided master key or OS secret store.
    - Consider AES-GCM for encrypting the key bytes; store nonce/tag in encryption_params.
    - Consider key rotation strategy.
    """

    session: Session

    def __post_init__(self) -> None:
        self.keys = KeyRepository(self.session)
        self.files = FileRepository(self.session)
        self.operations = CryptoOperationRepository(self.session)
        self.metrics = PerformanceMetricRepository(self.session)

    def keygen(self, *, algorithm: str, key_type: str, usage: str, name: str, params: dict[str, Any]) -> uuid.UUID:
        """TODO: Create a new key (AES/RSA) and store it encrypted in DB.

        Expected behavior:
        - Resolve algorithm + key_type + usage (lookup tables)
        - Call provider (OpenSSL) to generate key bytes
        - Encrypt key bytes with master key
        - Insert row in Keys
        - Insert CryptoOperation row of type 'keygen'
        - Return key id
        """

        raise NotImplementedError

    def encrypt_file(self, *, file_path: str, key_id: uuid.UUID, algorithm_variant: str, params: dict[str, Any]) -> uuid.UUID:
        """TODO: Encrypt a file using an existing key.

        Expected behavior:
        - Create Files row (original_* fields)
        - Create input FileArtifact (decrypted/original) or treat as source file (design choice)
        - Run OpenSSL encryption -> output encrypted artifact on disk
        - Create FileArtifacts row for encrypted output
        - Create CryptoOperation row (encrypt)
        - Create PerformanceMetrics rows
        """

        raise NotImplementedError

    def decrypt_file(self, *, artifact_id: uuid.UUID, key_id: uuid.UUID, params: dict[str, Any]) -> uuid.UUID:
        """TODO: Decrypt an encrypted artifact.

        Expected behavior mirrors encrypt_file, writing a decrypted artifact.
        """

        raise NotImplementedError
