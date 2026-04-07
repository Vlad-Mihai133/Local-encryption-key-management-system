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


# Repos pt fiecare model, incluzand modelele lookup.
# Pt entitatile cu date fixe, avem doar get_by_id, get_by_name, list_all.

@dataclass(frozen=True)
class KeyTypeRepository(Repository[models.KeyType]):
    def get(self, key_type_id: uuid.UUID) -> models.KeyType | None:
        return self.session.get(models.KeyType, key_type_id)

    def get_by_name(self, name: str) -> models.KeyType | None:
        stmt = select(models.KeyType).where(models.KeyType.name == name)
        return self.session.scalar(stmt)

    def list_all(self) -> list[models.KeyType]:
        stmt = select(models.KeyType).order_by(models.KeyType.created_at.desc())
        return list(self.session.scalars(stmt))

    
@dataclass(frozen=True)
class KeyUsageRepository(Repository[models.KeyUsage]):
    def get(self, usage_id: uuid.UUID) -> models.KeyUsage | None:
        return self.session.get(models.KeyUsage, usage_id)

    def get_by_name(self, name: str) -> models.KeyUsage | None:
        stmt = select(models.KeyUsage).where(models.KeyUsage.name == name)
        return self.session.scalar(stmt)

    def list_all(self) -> list[models.KeyUsage]:
        stmt = select(models.KeyUsage).order_by(models.KeyUsage.created_at.desc())
        return list(self.session.scalars(stmt))

@dataclass(frozen=True)
class AlgorithmTypeRepository(Repository[models.AlgorithmType]):
    def get(self, algorithm_type_id: uuid.UUID) -> models.AlgorithmType | None:
        return self.session.get(models.AlgorithmType, algorithm_type_id)

    def get_by_name(self, name: str) -> models.AlgorithmType | None:
        stmt = select(models.AlgorithmType).where(models.AlgorithmType.name == name)
        return self.session.scalar(stmt)

    def list_all(self) -> list[models.AlgorithmType]:
        stmt = select(models.AlgorithmType).order_by(models.AlgorithmType.created_at.desc())
        return list(self.session.scalars(stmt))
    
@dataclass(frozen=True)
class ArtifactTypeRepository(Repository[models.ArtifactType]):
    def get(self, artifact_type_id: uuid.UUID) -> models.ArtifactType | None:
        return self.session.get(models.ArtifactType, artifact_type_id)

    def get_by_name(self, name: str) -> models.ArtifactType | None:
        stmt = select(models.ArtifactType).where(models.ArtifactType.name == name)
        return self.session.scalar(stmt)

    def list_all(self) -> list[models.ArtifactType]:
        stmt = select(models.ArtifactType).order_by(models.ArtifactType.created_at.desc())
        return list(self.session.scalars(stmt))
    
@dataclass(frozen=True)
class CryptoOperationTypeRepository(Repository[models.CryptoOperationType]):
    def get(self, operation_type_id: uuid.UUID) -> models.CryptoOperationType | None:
        return self.session.get(models.CryptoOperationType, operation_type_id)

    def get_by_name(self, name: str) -> models.CryptoOperationType | None:
        stmt = select(models.CryptoOperationType).where(models.CryptoOperationType.name == name)
        return self.session.scalar(stmt)

    def list_all(self) -> list[models.CryptoOperationType]:
        stmt = select(models.CryptoOperationType).order_by(models.CryptoOperationType.created_at.desc())
        return list(self.session.scalars(stmt))

@dataclass(frozen=True)
class ResultTypeRepository(Repository[models.ResultType]):
    def get(self, result_type_id: uuid.UUID) -> models.ResultType | None:
        return self.session.get(models.ResultType, result_type_id)

    def get_by_name(self, name: str) -> models.ResultType | None:
        stmt = select(models.ResultType).where(models.ResultType.name == name)
        return self.session.scalar(stmt)

    def list_all(self) -> list[models.ResultType]:
        stmt = select(models.ResultType).order_by(models.ResultType.created_at.desc())
        return list(self.session.scalars(stmt))

@dataclass(frozen=True)
class PerformanceMetricTypeRepository(Repository[models.PerformanceMetricType]):
    def get(self, metric_type_id: uuid.UUID) -> models.PerformanceMetricType | None:
        return self.session.get(models.PerformanceMetricType, metric_type_id)

    def get_by_name(self, name: str) -> models.PerformanceMetricType | None:
        stmt = select(models.PerformanceMetricType).where(models.PerformanceMetricType.name == name)
        return self.session.scalar(stmt)

    def list_all(self) -> list[models.PerformanceMetricType]:
        stmt = select(models.PerformanceMetricType).order_by(models.PerformanceMetricType.created_at.desc())
        return list(self.session.scalars(stmt))
    


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
    def list_by_algorithm_variant(self, algorithm_variant_id: uuid.UUID) -> list[models.Key]:
        stmt = select(models.Key).where(models.Key.algorithm_id == algorithm_variant_id)
        return list(self.session.scalars(stmt))
    #pentru file_encryption, signing
    def list_by_usage(self, usage_id: int) -> list[models.Key]:
        stmt = select(models.Key).where(models.Key.usage_id == usage_id)
        return list(self.session.scalars(stmt))
    
    #CRUD minim
    def delete(self, key: models.Key) -> None:
        self.session.delete(key)



@dataclass(frozen=True)#
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
        # NOTE: models.File does not store filesystem paths.
        # The path is stored on models.FileArtifact.path.
        stmt = (
            select(models.File)
            .join(models.FileArtifact, models.FileArtifact.file_id == models.File.id)
            .where(models.FileArtifact.path == path)
            .order_by(models.File.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(stmt)
    #sterg file
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

    def list_by_provider(self, provider_id: uuid.UUID) -> list[models.CryptoOperation]:
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


@dataclass(frozen=True)
class AlgorithmRepository(Repository[models.Algorithm]):
    def add(self, algorithm: models.Algorithm) -> None:
        self.session.add(algorithm) 
    def update(self, algorithm: models.Algorithm) -> None:
        self.session.merge(algorithm)
    def get(self, algorithm_id: uuid.UUID) -> models.Algorithm | None:
        return self.session.get(models.Algorithm, algorithm_id)

    def get_by_name(self, name: str) -> models.Algorithm | None:
        stmt = select(models.Algorithm).where(models.Algorithm.name == name)
        return self.session.scalar(stmt)

    def list_all(self) -> list[models.Algorithm]:
        stmt = select(models.Algorithm).order_by(models.Algorithm.created_at.desc())
        return list(self.session.scalars(stmt))
    def update_algorithm(self, key: models.Key, new_algorithm_id: uuid.UUID) -> None:
        """Update key.algorithm_id.

        NOTE: `keys.algorithm_id` references `algorithm_variants.id` (not `algorithms.id`).
        This method keeps the original public name but treats `new_algorithm_id` as an
        AlgorithmVariant id.
        """
        variant = self.session.get(models.AlgorithmVariant, new_algorithm_id)
        if not variant:
            raise ValueError("algorithm_id trebuie sa fie un AlgorithmVariant.id valid.")
        if variant.algorithm and variant.algorithm.name.lower() not in ("aes", "rsa"):
            raise ValueError(
                "algorithm_id trebuie sa fie pentru un algoritm cu numele 'AES' sau 'RSA' (case-insensitive)."
            )
        key.algorithm_id = variant.id
        self.session.commit()
    def delete(self, algorithm: models.Algorithm) -> None:
        self.session.delete(algorithm)

@dataclass(frozen=True)
class CryptoProviderRepository(Repository[models.CryptoProvider]):
    def add(self, provider: models.CryptoProvider) -> None:
        self.session.add(provider)
    def get(self, provider_id: uuid.UUID) -> models.CryptoProvider | None:
        return self.session.get(models.CryptoProvider, provider_id)

    def get_by_name(self, name: str) -> models.CryptoProvider | None:
        stmt = select(models.CryptoProvider).where(models.CryptoProvider.name == name)
        return self.session.scalar(stmt)

    def list_all(self) -> list[models.CryptoProvider]:
        stmt = select(models.CryptoProvider).order_by(models.CryptoProvider.created_at.desc())
        return list(self.session.scalars(stmt))
    def update(self, provider: models.CryptoProvider) -> None:
        self.session.merge(provider)
    def delete(self, provider: models.CryptoProvider) -> None:
        self.session.delete(provider)   
    

@dataclass(frozen=True)
class FileArtifactRepository(Repository[models.FileArtifact]):

    def get(self, artifact_id: uuid.UUID) -> models.FileArtifact | None:
        return self.session.get(models.FileArtifact, artifact_id)

    def add(self, artifact: models.FileArtifact) -> None:
        self.session.add(artifact)

    def get_by_file_type_path(
        self,
        file_id: uuid.UUID,
        artifact_type_id: uuid.UUID,
        path: str,
    ) -> models.FileArtifact | None:
        stmt = select(models.FileArtifact).where(
            models.FileArtifact.file_id == file_id,
            models.FileArtifact.artifact_type_id == artifact_type_id,
            models.FileArtifact.path == path,
        )
        return self.session.scalar(stmt)
    
    def update(self, artifact: models.FileArtifact) -> None:
        self.session.merge(artifact)
    def update_path(self, artifact: models.FileArtifact, new_path: str) -> None:
        artifact.path = new_path
        self.session.commit()

    def list_all(self) -> list[models.FileArtifact]:
        stmt = select(models.FileArtifact)
        return list(self.session.scalars(stmt))

    def delete(self, artifact: models.FileArtifact) -> None:
        self.session.delete(artifact)

@dataclass(frozen=True)
class AlgorithmVariantRepository(Repository[models.AlgorithmVariant]):
    def add(self, variant: models.AlgorithmVariant) -> None:
        self.session.add(variant)
    def update(self, variant: models.AlgorithmVariant) -> None:
        self.session.merge(variant)
    def get(self, variant_id: uuid.UUID) -> models.AlgorithmVariant | None:
        return self.session.get(models.AlgorithmVariant, variant_id)

    def get_by_name(self, name: str, algorithm_id: uuid.UUID) -> models.AlgorithmVariant | None:
        stmt = select(models.AlgorithmVariant).where(
            models.AlgorithmVariant.name == name,
            models.AlgorithmVariant.algorithm_id == algorithm_id
        )
        return self.session.scalar(stmt)

    def list_all(self) -> list[models.AlgorithmVariant]:
        stmt = select(models.AlgorithmVariant).order_by(models.AlgorithmVariant.created_at.desc())
        return list(self.session.scalars(stmt))
    def delete(self, variant: models.AlgorithmVariant) -> None:
        self.session.delete(variant)