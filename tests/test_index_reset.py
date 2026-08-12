"""Reset must actually empty the collection — checked without the embedding model."""
import chromadb
import pytest

from lib.index import _COLLECTION, reset_collection, verify_collection


def _seed(path):
    client = chromadb.PersistentClient(path=str(path))
    col = client.get_or_create_collection(_COLLECTION)
    col.add(ids=["a", "b"], embeddings=[[0.1, 0.2], [0.3, 0.4]],
            metadatas=[{"chunk_id": "a"}, {"chunk_id": "b"}])
    return client


def test_reset_collection_empties_an_existing_store(tmp_path):
    client = _seed(tmp_path)
    assert client.get_collection(_COLLECTION).count() == 2
    reset_collection(tmp_path)
    client = chromadb.PersistentClient(path=str(tmp_path))
    assert _COLLECTION not in [c.name for c in client.list_collections()]


def test_reset_collection_is_a_noop_on_a_fresh_dir(tmp_path):
    reset_collection(tmp_path)          # must not raise


def test_verify_collection_accepts_a_complete_store(tmp_path):
    _seed(tmp_path)
    verify_collection(tmp_path, 2)          # must not raise


def test_verify_collection_rejects_a_truncated_store(tmp_path):
    """The failure mode that shipped twice: a build interrupted on a Chroma
    batch boundary leaves a plausible count, a complete FTS table and a valid
    meta.json, so nothing downstream notices it is querying a fraction of the
    corpus."""
    _seed(tmp_path)
    with pytest.raises(RuntimeError, match="holds 2 of 8,855"):
        verify_collection(tmp_path, 8855)
