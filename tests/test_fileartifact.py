
import pytest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from klm.db.models import Base
from klm.db.repositories import FileArtifactRepository
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

def test_fileartifact_crud(session):
    repo = FileArtifactRepository(session)
    # Clean table
    session.query(models.FileArtifact).delete()
    session.query(models.File).delete()
    session.query(models.ArtifactType).delete()
    session.commit()

    # Insert lookup values
    file = models.File(
        name="testfile",
        original_name="test.txt",
        original_size_bytes=123,
        original_hash="hash"
    )
    session.add(file)
    atype = models.ArtifactType(name="encrypted")
    session.add(atype)
    session.commit()

    # Create
    artifact = models.FileArtifact(
        file_id=file.id,
        artifact_type_id=atype.id,
        path="/tmp/test.txt",
        size_bytes=123,
        hash="abc123"
    )
    repo.add(artifact)
    session.commit()

    assert artifact.id is not None

    # Read
    found = repo.get(artifact.id)
    assert found is not None
    assert found.path == "/tmp/test.txt"

    # Update
    repo.update_path(found, "/tmp/updated.txt")
    session.commit()
    refreshed = repo.get(artifact.id)
    assert refreshed.path == "/tmp/updated.txt"

    # Cleanup lookup values
    session.query(models.FileArtifact).delete()
    session.query(models.File).delete()
    session.query(models.ArtifactType).delete()
    session.commit()
    assert found.path == "/tmp/updated.txt"

    # Delete
    repo.delete(found)
    session.commit()
    assert repo.get(artifact.id) is None
