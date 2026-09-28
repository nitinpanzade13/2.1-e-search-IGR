import os
import hashlib
import tempfile
import pytest
from app.scraper.storage.artifact_store import ArtifactStore
from app.scraper.domain.exceptions import ArtifactStorageError

@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d

@pytest.fixture
def store(temp_dir):
    return ArtifactStore(base_dir=temp_dir)

def test_save_raw_bytes_successfully(store, temp_dir):
    body = b"<html>Test bytes</html>"
    artifact_id = store.save("test_art_1", body)
    
    assert artifact_id == "test_art_1"
    storage_path = os.path.join(temp_dir, "test_art_1.html")
    assert os.path.exists(storage_path)
    
    # Verify file contents are byte-for-byte identical
    with open(storage_path, "rb") as f:
        assert f.read() == body

def test_save_empty_bytes(store, temp_dir):
    body = b""
    artifact_id = store.save("test_empty", body)
    storage_path = os.path.join(temp_dir, "test_empty.html")
    assert os.path.getsize(storage_path) == 0

def test_creates_missing_directories(temp_dir):
    deep_dir = os.path.join(temp_dir, "deep", "nested", "dir")
    deep_store = ArtifactStore(base_dir=deep_dir)
    
    body = b"test"
    artifact_id = deep_store.save("test_deep", body)
    storage_path = os.path.join(deep_dir, "test_deep.html")
    assert os.path.exists(storage_path)

def test_repeated_saves_do_not_corrupt(store, temp_dir):
    body1 = b"first"
    body2 = b"second"
    
    # Save first time
    artifact_id = store.save("test_overwrite", body1)
    storage_path = os.path.join(temp_dir, f"{artifact_id}.html")
    with open(storage_path, "rb") as f:
        assert f.read() == body1
        
    # Save second time
    store.save("test_overwrite", body2)
    with open(storage_path, "rb") as f:
        assert f.read() == body2

def test_empty_artifact_id(store):
    artifact_id = store.save("", b"body")
    import uuid
    # Should auto-generate a valid UUID string
    assert uuid.UUID(artifact_id)
    
def test_filesystem_failure_raises_domain_error():
    # Provide an invalid path (e.g. root directory on Windows without permissions)
    # Wait, testing filesystem errors reliably across platforms is tricky. 
    # We can mock os.makedirs to raise OSError.
    from unittest import mock
    with mock.patch("os.makedirs", side_effect=OSError("Disk full")):
        store = ArtifactStore(base_dir="storage/raw")
        with pytest.raises(ArtifactStorageError) as exc:
            store.save("test", b"body")
        assert "Failed to save artifact" in str(exc.value)
def test_artifact_id_path_traversal(store):
    with pytest.raises(ArtifactStorageError):
        store.save("../escape", b"body")
    with pytest.raises(ArtifactStorageError):
        store.save("../../escape", b"body")
    with pytest.raises(ArtifactStorageError):
        store.save("/absolute/path", b"body")
    with pytest.raises(ArtifactStorageError):
        store.save("C:\\path", b"body")
