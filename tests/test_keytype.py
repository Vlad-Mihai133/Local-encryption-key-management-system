import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, clear_mappers
from klm.db import models
from klm.db.models import Base
from klm.db.repositories import KeyTypeRepository
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


def test_keytype_crud(session):
# curata tabela inainte de test
    session.query(models.KeyType).delete()
    session.commit()
    repo = KeyTypeRepository(session)
    # Create
    kt = models.KeyType(name="symmetric")
    session.add(kt)
    session.commit()
    assert kt.id is not None
    # Read
    found = repo.get(kt.id)
    assert found is not None
    assert found.name == "symmetric"
    # Update
    found.name = "symmetric-updated"
    session.commit()
    found2 = repo.get(kt.id)
    assert found2.name == "symmetric-updated"
    # Delete
    repo.delete(found2)
    session.commit()
    assert repo.get(kt.id) is None
