from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from sqlalchemy import func, select

T = TypeVar("T")


@dataclass(frozen=True)
class Repository(Generic[T]):
    """Very small repository abstraction.

    Next sprint ideas:
    - Add pagination helpers
    - Add transactional unit-of-work wrapper
    - Enforce domain validations (e.g., key status transitions)
    """

    session: Session


@dataclass(frozen=True)
class KeyRepository(Repository[models.Key]):
    def get(self, key_id: uuid.UUID) -> models.Key | None:
        return self.session.get(models.Key, key_id)

    def get_by_name(self, name: str) -> models.Key | None:
        stmt = select(models.Key).where(models.Key.name == name)
        return self.session.scalar(stmt)

    def add(self, key: models.Key) -> None:
        self.session.add(key)
    #pentru listare în CLI/admin/demo
    def list_all(self) -> list[models.Key]:
        stmt = select(models.Key).order_by(models.Key.created_at.desc())
        return list(self.session.scalars(stmt))
    #util la keygen
    def exists_by_name(self, name: str) -> bool:
        return self.get_by_name(name) is not None
    #pentru AES vs RSA
    def list_by_algorithm(self, algorithm_id: int) -> list[models.Key]:
        stmt = select(models.Key).where(models.Key.algorithm_id == algorithm_id)
        return list(self.session.scalars(stmt))
    #pentru file_encryption, signing
    def list_by_usage(self, usage_id: int) -> list[models.Key]:
        stmt = select(models.Key).where(models.Key.usage_id == usage_id)
        return list(self.session.scalars(stmt))
    #CRUD minim
    def delete(self, key: models.Key) -> None:
        self.session.delete(key)



@dataclass(frozen=True)
class FileRepository(Repository[models.File]):
    def get(self, file_id: uuid.UUID) -> models.File | None:
        return self.session.get(models.File, file_id)

    def add(self, file: models.File) -> None:
        self.session.add(file)
    #nu duplicam fisere
    def list_all(self) -> list[models.File]:
        stmt = select(models.File).order_by(models.File.created_at.desc())
        return list(self.session.scalars(stmt))
    #util cli
    def get_by_path(self, path: str) -> models.File | None:
        stmt = select(models.File).where(models.File.path == path)
        return self.session.scalar(stmt)
    #validare
    def get_by_sha256(self, sha256: str) -> models.File | None:
        stmt = select(models.File).where(models.File.sha256 == sha256)
        return self.session.scalar(stmt)

    def exists_by_sha256(self, sha256: str) -> bool:
        return self.get_by_sha256(sha256) is not None

    def delete(self, file: models.File) -> None:
        self.session.delete(file)


@dataclass(frozen=True)
class CryptoOperationRepository(Repository[models.CryptoOperation]):
    def get(self, operation_id: uuid.UUID) -> models.CryptoOperation | None:
        return self.session.get(models.CryptoOperation, operation_id)

    def add(self, operation: models.CryptoOperation) -> None:
        self.session.add(operation)
    def list_all(self) -> list[models.CryptoOperation]:
        stmt = select(models.CryptoOperation).order_by(models.CryptoOperation.started_at.desc())
        return list(self.session.scalars(stmt))

    def list_by_key(self, key_id: uuid.UUID) -> list[models.CryptoOperation]:
        stmt = select(models.CryptoOperation).where(models.CryptoOperation.key_id == key_id)
        return list(self.session.scalars(stmt))

    def list_by_file(self, file_id: uuid.UUID) -> list[models.CryptoOperation]:
        stmt = select(models.CryptoOperation).where(models.CryptoOperation.file_id == file_id)
        return list(self.session.scalars(stmt))

    def list_by_provider(self, provider_id: int) -> list[models.CryptoOperation]:
        stmt = select(models.CryptoOperation).where(models.CryptoOperation.provider_id == provider_id)
        return list(self.session.scalars(stmt))

    def list_recent(self, limit: int = 20) -> list[models.CryptoOperation]:
        stmt = (
            select(models.CryptoOperation)
            .order_by(models.CryptoOperation.started_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def delete(self, operation: models.CryptoOperation) -> None:
        self.session.delete(operation)


@dataclass(frozen=True)
class PerformanceMetricRepository(Repository[models.PerformanceMetric]):
    def add(self, metric: models.PerformanceMetric) -> None:
        self.session.add(metric)
    def get(self, metric_id: uuid.UUID) -> models.PerformanceMetric | None:
        return self.session.get(models.PerformanceMetric, metric_id)

    def add_many(self, metrics: list[models.PerformanceMetric]) -> None:
        self.session.add_all(metrics)

    def list_by_operation(self, operation_id: uuid.UUID) -> list[models.PerformanceMetric]:
        stmt = select(models.PerformanceMetric).where(
            models.PerformanceMetric.operation_id == operation_id
        )
        return list(self.session.scalars(stmt))

    def list_all(self) -> list[models.PerformanceMetric]:
        stmt = select(models.PerformanceMetric)
        return list(self.session.scalars(stmt))

    def delete(self, metric: models.PerformanceMetric) -> None:
        self.session.delete(metric)

#aici avem lookup repositories ptc avem tabele cu date fixe: id     name
#                                                             1     AES
#                                                             2     RSA , iar CLI primeste cv de genul
'''--algorithm AES
--key-type symmetric
--usage file_encryption , dar avem nevoie de
 algorithm_id = 1
key_type_id = 1
usage_id = 1'''
@dataclass(frozen=True)
class AlgorithmRepository(Repository[models.Algorithm]):
    def get(self, algorithm_id: int) -> models.Algorithm | None:
        return self.session.get(models.Algorithm, algorithm_id)

    def get_by_name(self, name: str) -> models.Algorithm | None:
        stmt = select(models.Algorithm).where(models.Algorithm.name == name)
        return self.session.scalar(stmt)

    def list_all(self) -> list[models.Algorithm]:
        stmt = select(models.Algorithm)
        return list(self.session.scalars(stmt))


@dataclass(frozen=True)
class KeyTypeRepository(Repository[models.KeyType]):
    def get(self, key_type_id: int) -> models.KeyType | None:
        return self.session.get(models.KeyType, key_type_id)

    def get_by_name(self, name: str) -> models.KeyType | None:
        stmt = select(models.KeyType).where(models.KeyType.name == name)
        return self.session.scalar(stmt)

    def list_all(self) -> list[models.KeyType]:
        stmt = select(models.KeyType)
        return list(self.session.scalars(stmt))


@dataclass(frozen=True)
class KeyUsageRepository(Repository[models.KeyUsage]):
    def get(self, usage_id: int) -> models.KeyUsage | None:
        return self.session.get(models.KeyUsage, usage_id)

    def get_by_name(self, name: str) -> models.KeyUsage | None:
        stmt = select(models.KeyUsage).where(models.KeyUsage.name == name)
        return self.session.scalar(stmt)

    def list_all(self) -> list[models.KeyUsage]:
        stmt = select(models.KeyUsage)
        return list(self.session.scalars(stmt))


@dataclass(frozen=True)
class CryptoProviderRepository(Repository[models.CryptoProvider]):
    def get(self, provider_id: int) -> models.CryptoProvider | None:
        return self.session.get(models.CryptoProvider, provider_id)

    def get_by_name(self, name: str) -> models.CryptoProvider | None:
        stmt = select(models.CryptoProvider).where(models.CryptoProvider.name == name)
        return self.session.scalar(stmt)

    def list_all(self) -> list[models.CryptoProvider]:
        stmt = select(models.CryptoProvider)
        return list(self.session.scalars(stmt))