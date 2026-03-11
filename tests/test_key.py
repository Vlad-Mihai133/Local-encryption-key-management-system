
import pytest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from klm.db.models import Base
from klm.db.repositories import KeyRepository
from klm.db import models

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

def test_key_crud(session):
    repo = KeyRepository(session)
    session.query(models.Key).delete()
    session.query(models.AlgorithmVariant).delete()
    session.query(models.Algorithm).delete()
    session.query(models.KeyType).delete()
    session.query(models.KeyUsage).delete()
    session.query(models.AlgorithmType).delete()
    session.commit()

    # Insert lookup values
    kt = models.KeyType(name="symmetric")
    session.add(kt)
    alg_type = models.AlgorithmType(name="block")
    session.add(alg_type)
    session.commit()
    alg = models.Algorithm(name="AES", type_id=alg_type.id, params={})
    session.add(alg)
    session.commit()
    variant = models.AlgorithmVariant(algorithm_id=alg.id, name="AES-256-GCM", params={})
    session.add(variant)
    usage = models.KeyUsage(name="file_encryption")
    session.add(usage)
    session.commit()

    # Create
    key = models.Key(
        name="testkey",
        type_id=kt.id,
        algorithm_id=variant.id,
        status="active",
        usage_id=usage.id,
        encrypted_material=b"abc",
        material_format="raw",
        encryption_scheme="app-level",
        encryption_params={},
    )
    repo.add(key)
    session.commit()

    assert key.id is not None

    # Read
    found = repo.get(key.id)
    assert found is not None
    assert found.name == "testkey"

    # Update
    found.name = "updatedkey"
    session.commit()
    found2 = repo.get(key.id)
    assert found2.name == "updatedkey"

    # Delete
    repo.delete(found2)
    session.commit()
    deleted = repo.get(key.id)
    assert deleted is None

    # Cleanup lookup values (FK-safe order)
    session.query(models.Key).delete()
    session.query(models.AlgorithmVariant).delete()
    session.query(models.Algorithm).delete()
    session.query(models.KeyType).delete()
    session.query(models.KeyUsage).delete()
    session.query(models.AlgorithmType).delete()
    session.commit()

    # Delete
    repo.delete(found2)
    session.commit()
    assert repo.get(key.id) is None
