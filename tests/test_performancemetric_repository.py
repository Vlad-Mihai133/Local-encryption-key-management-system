import pytest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from klm.db.models import Base
from klm.db import models
from klm.db.repositories import PerformanceMetricRepository

@pytest.fixture(scope="module")
def engine():
    engine = create_engine("postgresql+psycopg://postgres:anaaremere@localhost:5432/klm", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)

@pytest.fixture
def session(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_performance_metric_repository_crud(session):
    repo = PerformanceMetricRepository(session)
    session.query(models.PerformanceMetric).delete()
    session.query(models.PerformanceMetricType).delete()
    session.query(models.CryptoOperation).delete()
    session.query(models.CryptoProvider).delete()
    session.query(models.CryptoOperationType).delete()
    session.query(models.AlgorithmVariant).delete()
    session.query(models.Algorithm).delete()
    session.query(models.AlgorithmType).delete()
    session.query(models.ResultType).delete()
    session.commit()

    # Insert lookup values
    metric_type = models.PerformanceMetricType(name="latency")
    session.add(metric_type)
    op_type = models.CryptoOperationType(name="encrypt")
    session.add(op_type)
    alg_type = models.AlgorithmType(name="block")
    session.add(alg_type)
    session.commit()
    alg = models.Algorithm(name="AES", type_id=alg_type.id, params={})
    session.add(alg)
    session.commit()
    variant = models.AlgorithmVariant(algorithm_id=alg.id, name="AES-256-GCM", params={})
    session.add(variant)
    provider = models.CryptoProvider(name="OpenSSL")
    session.add(provider)
    result_type = models.ResultType(name="success")
    session.add(result_type)
    session.commit()
    operation = models.CryptoOperation(
        operation_type_id=op_type.id,
        file_id=None,
        input_artifact_id=None,
        output_artifact_id=None,
        provider_id=provider.id,
        algorithm_variant_id=variant.id,
        key_id=None,
        params={},
        ended_at=None,
        result_type_id=result_type.id,
        error_code=None,
        error_message=None
    )
    session.add(operation)
    session.commit()

    obj = models.PerformanceMetric(
        operation_id=operation.id,
        metric_type_id=metric_type.id,
        value=1.23,
        unit="ms"
    )
    session.add(obj)
    session.commit()
    found = repo.get(obj.id)
    assert found is not None
    all_objs = repo.list_all()
    assert obj in all_objs
    repo.delete(obj)
    session.commit()
    assert repo.get(obj.id) is None
