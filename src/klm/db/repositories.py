from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models


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


@dataclass(frozen=True)
class FileRepository(Repository[models.File]):
    def get(self, file_id: uuid.UUID) -> models.File | None:
        return self.session.get(models.File, file_id)

    def add(self, file: models.File) -> None:
        self.session.add(file)


@dataclass(frozen=True)
class CryptoOperationRepository(Repository[models.CryptoOperation]):
    def get(self, operation_id: uuid.UUID) -> models.CryptoOperation | None:
        return self.session.get(models.CryptoOperation, operation_id)

    def add(self, operation: models.CryptoOperation) -> None:
        self.session.add(operation)


@dataclass(frozen=True)
class PerformanceMetricRepository(Repository[models.PerformanceMetric]):
    def add(self, metric: models.PerformanceMetric) -> None:
        self.session.add(metric)
