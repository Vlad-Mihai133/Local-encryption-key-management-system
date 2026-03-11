import pytest
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import sessionmaker
from klm.db import models
from klm.db.models import Base
from klm.db.repositories import KeyTypeRepository, KeyRepository
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

def test_keytype_unique_constraint(session):
    # curata tabela inainte de test
    session.query(models.KeyType).delete()
    session.commit()
    repo = KeyTypeRepository(session)
    kt1 = models.KeyType(name="symmetric")
    session.add(kt1)
    session.commit()
    kt2 = models.KeyType(name="symmetric")
    session.add(kt2)
    with pytest.raises(exc.IntegrityError):
        session.commit()
        session.rollback()
