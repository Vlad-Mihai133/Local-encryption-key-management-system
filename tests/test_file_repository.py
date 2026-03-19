import pytest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from klm.db.models import Base
from klm.db import models
from klm.db.repositories import FileRepository

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

def test_file_repository_crud(session):
    repo = FileRepository(session)
    session.query(models.File).delete()
    session.commit()
    obj = models.File(
        name="testfile",
        original_name="test.txt",
        original_size_bytes=123,
        original_hash="hash"
    )
    session.add(obj)
    session.commit()
    found = repo.get(obj.id)
    assert found is not None
    assert found.name == "testfile"
    all_objs = repo.list_all()
    assert obj in all_objs
    repo.delete(obj)
    session.commit()
    assert repo.get(obj.id) is None
