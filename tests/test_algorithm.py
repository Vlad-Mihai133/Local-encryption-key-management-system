import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from klm.db import models
from klm.db.models import Base
from klm.db.repositories import AlgorithmRepository, AlgorithmTypeRepository
import uuid

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

def test_algorithm_crud(session):
# Ccurata db inainte de test
    session.query(models.Algorithm).delete()
    session.query(models.AlgorithmType).delete()
    session.commit()
    type_repo = AlgorithmTypeRepository(session)
    algo_repo = AlgorithmRepository(session)
    # Create type
    at = models.AlgorithmType(name="symmetric")
    session.add(at)
    session.commit()
    # Create algorithm
    algo = models.Algorithm(name="AES", type_id=at.id, params={})
    session.add(algo)
    session.commit()
    assert algo.id is not None
    # Read
    found = algo_repo.get(algo.id)
    assert found is not None
    assert found.name == "AES"
    # Update
    found.name = "AES-updated"
    session.commit()
    found2 = algo_repo.get(algo.id)
    assert found2.name == "AES-updated"
    # Delete
    algo_repo.delete(found2)
    session.commit()
    assert algo_repo.get(algo.id) is None
