import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from klm.db.models import Base
from klm.db import models
from klm.db.repositories import CryptoOperationTypeRepository

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

def test_crypto_operation_type_repository_crud(session):
    repo = CryptoOperationTypeRepository(session)
    session.query(models.CryptoOperationType).delete()
    session.commit()
    obj = models.CryptoOperationType(name="encrypt")
    session.add(obj)
    session.commit()
    found = repo.get(obj.id)
    assert found is not None
    assert found.name == "encrypt"
    found_by_name = repo.get_by_name("encrypt")
    assert found_by_name.id == obj.id
    all_objs = repo.list_all()
    assert obj in all_objs
