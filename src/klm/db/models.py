from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class KeyType(Base):
    __tablename__ = "key_types"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class KeyUsage(Base):
    __tablename__ = "key_usages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class AlgorithmType(Base):
    __tablename__ = "algorithm_types"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class ArtifactType(Base):
    __tablename__ = "artifact_types"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class CryptoOperationType(Base):
    __tablename__ = "crypto_operation_types"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class ResultType(Base):
    __tablename__ = "result_types"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class PerformanceMetricType(Base):
    __tablename__ = "performance_metric_types"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class Algorithm(Base):
    __tablename__ = "algorithms"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("algorithm_types.id", ondelete="RESTRICT"),
        nullable=False,
    )
    params: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )

    type: Mapped[AlgorithmType] = relationship("AlgorithmType")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class CryptoProvider(Base):
    __tablename__ = "crypto_providers"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_crypto_providers_name_version"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str | None] = mapped_column(Text, nullable=True)
    runtime_info: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class AlgorithmVariant(Base):
    __tablename__ = "algorithm_variants"
    __table_args__ = (UniqueConstraint("algorithm_id", "name", name="uq_algorithm_variants_algorithm_id_name"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    algorithm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("algorithms.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    algorithm: Mapped[Algorithm] = relationship("Algorithm")


class Key(Base):
    __tablename__ = "keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("key_types.id", ondelete="RESTRICT"),
        nullable=False,
    )
    algorithm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("algorithm_variants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="active", server_default=text("'active'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    usage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("key_usages.id", ondelete="RESTRICT"),
        nullable=False,
    )

    encrypted_material: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    material_format: Mapped[str] = mapped_column(
        Text, nullable=False, default="raw", server_default=text("'raw'")
    )
    encryption_scheme: Mapped[str] = mapped_column(
        Text, nullable=False, default="app-level", server_default=text("'app-level'")
    )
    encryption_params: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )

    type: Mapped[KeyType] = relationship("KeyType")
    usage: Mapped[KeyUsage] = relationship("KeyUsage")
    algorithm: Mapped[AlgorithmVariant] = relationship("AlgorithmVariant")


class File(Base):
    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    original_name: Mapped[str] = mapped_column(Text, nullable=False)
    original_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    original_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    artifacts: Mapped[list[FileArtifact]] = relationship(
        "FileArtifact",
        back_populates="file",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class FileArtifact(Base):
    __tablename__ = "file_artifacts"
    __table_args__ = (
        UniqueConstraint("file_id", "artifact_type_id", "path", name="uq_file_artifacts_file_type_path"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
    )
    artifact_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifact_types.id", ondelete="RESTRICT"),
        nullable=False,
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    file: Mapped[File] = relationship("File", back_populates="artifacts")
    artifact_type: Mapped[ArtifactType] = relationship("ArtifactType")


class CryptoOperation(Base):
    __tablename__ = "crypto_operations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )

    operation_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crypto_operation_types.id", ondelete="RESTRICT"),
        nullable=False,
    )

    file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="SET NULL"),
        nullable=True,
    )

    input_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("file_artifacts.id", ondelete="SET NULL"),
        nullable=True,
    )
    output_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("file_artifacts.id", ondelete="SET NULL"),
        nullable=True,
    )

    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crypto_providers.id", ondelete="RESTRICT"),
        nullable=False,
    )

    algorithm_variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("algorithm_variants.id", ondelete="RESTRICT"),
        nullable=False,
    )

    key_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("keys.id", ondelete="SET NULL"),
        nullable=True,
    )

    params: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    result_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("result_types.id", ondelete="RESTRICT"),
        nullable=False,
    )
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    operation_type: Mapped[CryptoOperationType] = relationship("CryptoOperationType")
    file: Mapped[File | None] = relationship("File")
    input_artifact: Mapped[FileArtifact | None] = relationship("FileArtifact", foreign_keys=[input_artifact_id])
    output_artifact: Mapped[FileArtifact | None] = relationship("FileArtifact", foreign_keys=[output_artifact_id])
    provider: Mapped[CryptoProvider] = relationship("CryptoProvider")
    algorithm_variant: Mapped[AlgorithmVariant] = relationship("AlgorithmVariant")
    key: Mapped[Key | None] = relationship("Key")
    result_type: Mapped[ResultType] = relationship("ResultType")

    performance_metrics: Mapped[list[PerformanceMetric]] = relationship(
        "PerformanceMetric",
        back_populates="operation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class PerformanceMetric(Base):
    __tablename__ = "performance_metrics"
    __table_args__ = (UniqueConstraint("operation_id", "metric_type_id", name="uq_perf_metrics_operation_metric_type"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    operation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crypto_operations.id", ondelete="CASCADE"),
        nullable=False,
    )
    metric_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("performance_metric_types.id", ondelete="RESTRICT"),
        nullable=False,
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    operation: Mapped[CryptoOperation] = relationship("CryptoOperation", back_populates="performance_metrics")
    metric_type: Mapped[PerformanceMetricType] = relationship("PerformanceMetricType")
