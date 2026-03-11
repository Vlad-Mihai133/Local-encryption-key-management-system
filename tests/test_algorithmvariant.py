
import pytest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from klm.db.models import Base
from klm.db.repositories import AlgorithmVariantRepository
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

def test_algorithmvariant_crud(session):
    repo = AlgorithmVariantRepository(session)
    session.query(models.AlgorithmVariant).delete()
    session.query(models.Algorithm).delete()
    session.query(models.AlgorithmType).delete()
    session.commit()

    # Insert lookup value
    alg_type = models.AlgorithmType(name="block")
    session.add(alg_type)
    session.commit()
    alg = models.Algorithm(name="AES", type_id=alg_type.id, params={})
    session.add(alg)
    session.commit()

    # Create
    variant = models.AlgorithmVariant(
        algorithm_id=alg.id,
        name="AES-256-GCM",
        params={},
    )
    repo.add(variant)
    session.commit()

    assert variant.id is not None

    # Read
    found = repo.get(variant.id)
    assert found is not None
    assert found.name == "AES-256-GCM"

    # Update
    found.name = "AES-256-CBC"
    repo.update(found)
    session.commit()
    updated = repo.get(variant.id)
    assert updated.name == "AES-256-CBC"

    # Delete
    repo.delete(updated)
    session.commit()
    deleted = repo.get(variant.id)
    assert deleted is None

    # Cleanup lookup values (FK-safe order)
    session.query(models.AlgorithmVariant).delete()
    session.query(models.Algorithm).delete()
    session.query(models.AlgorithmType).delete()
    session.commit()
    session.commit()
    assert repo.get(variant.id) is None
