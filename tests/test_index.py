import json

import pytest
import torch

import lib.index as index_mod
from lib.index import chunk_records, write_meta


def make(mid, body, **kw):
    base = {
        "id": mid, "message_id": f"<{mid}>", "date": "2011-03-02T09:14:00",
        "from_email": "martin@ics.forth.gr", "from_name": "Martin Doerr",
        "subject": "scope note", "body": body, "entities": ["E55"],
        "entities_quoted": [], "entities_historical": [],
    }
    base.update(kw)
    return base


def test_short_message_yields_one_chunk():
    chunks = chunk_records([make("a", "short body")], {"a": "t0"}, 2000, 200)
    assert len(chunks) == 1
    assert chunks[0]["chunk_id"] == "a#0"
    assert chunks[0]["text"] == "short body"


def test_long_message_splits_into_several_chunks():
    chunks = chunk_records([make("a", "word " * 2000)], {"a": "t0"}, 2000, 200)
    assert len(chunks) > 1
    assert [c["chunk_id"] for c in chunks] == [f"a#{i}" for i in range(len(chunks))]


def test_metadata_is_carried_onto_every_chunk():
    chunks = chunk_records([make("a", "word " * 2000)], {"a": "t7"}, 2000, 200)
    for chunk in chunks:
        assert chunk["thread_id"] == "t7"
        assert chunk["message_id"] == "<a>"
        assert chunk["year"] == 2011
        assert chunk["from_email"] == "martin@ics.forth.gr"
        assert chunk["entities"] == "E55"


def test_entities_flattened_to_string_for_chroma_and_fts():
    chunks = chunk_records(
        [make("a", "body", entities=["E55", "P2"])], {"a": "t0"}, 2000, 200
    )
    assert chunks[0]["entities"] == "E55 P2"


def test_empty_body_is_skipped():
    assert chunk_records([make("a", "   ")], {"a": "t0"}, 2000, 200) == []


def test_missing_date_does_not_crash():
    chunks = chunk_records([make("a", "body", date=None)], {"a": "t0"}, 2000, 200)
    assert chunks[0]["year"] == 0


def test_write_meta_records_the_model_binding(tmp_path):
    meta = write_meta(
        tmp_path, "crm-sig", "desc", "Alibaba-NLP/gte-modernbert-base",
        source_path=None, ontology_version="7.1.3",
    )
    on_disk = json.loads((tmp_path / "meta.json").read_text())
    assert on_disk == meta
    assert on_disk["embedding_model"] == "Alibaba-NLP/gte-modernbert-base"
    assert on_disk["normalize"] is True
    assert on_disk["ontology_version"] == "7.1.3"
    assert on_disk["built_at"]


def test_write_meta_hashes_the_source_when_present(tmp_path):
    src = tmp_path / "src.mbox"
    src.write_bytes(b"hello")
    meta = write_meta(tmp_path, "n", "d", "m", source_path=src, ontology_version="7.1.3")
    assert len(meta["source_sha256"]) == 64


class _FakeInner:
    """Stand-in for HuggingFaceEmbeddings: OOMs above `threshold`, else succeeds."""

    def __init__(self, device, batch_size, threshold):
        self.device = device
        self.batch_size = batch_size
        self.threshold = threshold

    def embed_documents(self, texts):
        if self.device == "cuda" and self.batch_size > self.threshold:
            raise torch.OutOfMemoryError(f"simulated OOM at bs={self.batch_size}")
        return [[0.1, 0.2] for _ in texts]

    def embed_query(self, text):
        # Encodes which device/batch_size built this instance so tests can
        # tell whether embed_query is using a degraded config or not.
        return [1.0 if self.device == "cpu" else 0.0, float(self.batch_size)]


class _AlwaysOom:
    def embed_documents(self, texts):
        raise torch.OutOfMemoryError("simulated OOM regardless of device")

    def embed_query(self, text):
        raise torch.OutOfMemoryError("simulated OOM regardless of device")


def test_oom_fallback_halves_batch_size_until_it_fits(monkeypatch, capsys):
    monkeypatch.setattr(
        index_mod, "_build_embeddings",
        lambda model, device, batch_size: _FakeInner(device, batch_size, threshold=2),
    )
    emb = index_mod._OomSafeEmbeddings("model", "cuda", 16)
    result = emb.embed_documents(["a", "b"])
    assert result == [[0.1, 0.2], [0.1, 0.2]]
    out = capsys.readouterr().out
    # 16 -> 8 -> 4 -> 2 (2 is the first size <= threshold, so it succeeds there)
    assert "retrying at device=cuda batch_size=8" in out
    assert "retrying at device=cuda batch_size=4" in out
    assert "retrying at device=cuda batch_size=2" in out


def test_oom_fallback_drops_to_cpu_when_batch_size_one_still_ooms(monkeypatch, capsys):
    monkeypatch.setattr(
        index_mod, "_build_embeddings",
        lambda model, device, batch_size: _FakeInner(device, batch_size, threshold=-1),
    )
    emb = index_mod._OomSafeEmbeddings("model", "cuda", 1)
    result = emb.embed_documents(["a"])
    assert result == [[0.1, 0.2]]
    out = capsys.readouterr().out
    assert "falling back to device=cpu batch_size=16" in out


def test_oom_on_cpu_reraises_instead_of_looping_forever(monkeypatch):
    monkeypatch.setattr(
        index_mod, "_build_embeddings",
        lambda model, device, batch_size: _AlwaysOom(),
    )
    emb = index_mod._OomSafeEmbeddings("model", "cpu", 16)
    with pytest.raises(torch.OutOfMemoryError):
        emb.embed_documents(["a"])


def test_fallback_persists_to_the_next_call_on_the_same_instance(monkeypatch, capsys):
    """Chroma's local client caps batches at 5,461, so a build with more
    chunks than that calls embed_documents more than once on the same
    _OomSafeEmbeddings instance. A degradation in the first call must stick
    for the second -- it must not reset to the original device/batch_size
    and re-attempt CUDA from scratch."""
    monkeypatch.setattr(
        index_mod, "_build_embeddings",
        lambda model, device, batch_size: _FakeInner(device, batch_size, threshold=-1),
    )
    emb = index_mod._OomSafeEmbeddings("model", "cuda", 1)

    emb.embed_documents(["a"])  # cuda batch_size=1 always OOMs -> falls back to cpu
    assert emb.device == "cpu"
    assert emb.batch_size == 16

    capsys.readouterr()  # discard first call's output
    result = emb.embed_documents(["b"])
    assert result == [[0.1, 0.2]]
    out = capsys.readouterr().out
    assert out == ""  # no OOM, no retry message -- it went straight to cpu
    assert emb.device == "cpu"
    assert emb.batch_size == 16


def test_embed_query_uses_the_degraded_config_after_a_fallback(monkeypatch):
    monkeypatch.setattr(
        index_mod, "_build_embeddings",
        lambda model, device, batch_size: _FakeInner(device, batch_size, threshold=-1),
    )
    emb = index_mod._OomSafeEmbeddings("model", "cuda", 1)
    emb.embed_documents(["a"])  # forces fallback to cpu, batch_size=16

    # Pre-fix, embed_query used self._inner unconditionally, which was never
    # reassigned by embed_documents, so this would still report cuda.
    assert emb.embed_query("hello") == [1.0, 16.0]


def test_old_embedder_is_released_before_the_replacement_is_built(monkeypatch):
    """torch.cuda.empty_cache() only reclaims memory from tensors with no
    remaining Python references. If self._inner (or the loop-local `inner`)
    still points at the OOM'd model when _build_embeddings is called for the
    replacement, nothing was freed and a second model loads alongside the
    first."""
    box = {}
    seen_inner_at_rebuild = []

    def fake_build(model, device, batch_size):
        if "emb" in box:
            seen_inner_at_rebuild.append(box["emb"]._inner)
        return _FakeInner(device, batch_size, threshold=-1)

    monkeypatch.setattr(index_mod, "_build_embeddings", fake_build)
    emb = index_mod._OomSafeEmbeddings("model", "cuda", 1)
    box["emb"] = emb

    emb.embed_documents(["a"])  # one fallback: cuda bs=1 -> cpu bs=16

    assert seen_inner_at_rebuild == [None]
