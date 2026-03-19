import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from klm.db.models import Base
from klm.db import models
from klm.db.repositories import ArtifactTypeRepository

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

def test_artifact_type_repository_crud(session):
    repo = ArtifactTypeRepository(session)
    session.query(models.ArtifactType).delete()
    session.commit()
    obj = models.ArtifactType(name="cert")
    session.add(obj)
    session.commit()
    found = repo.get(obj.id)
    assert found is not None
    assert found.name == "cert"
    found_by_name = repo.get_by_name("cert")
    assert found_by_name.id == obj.id
    all_objs = repo.list_all()
    assert obj in all_objs
