import json

import pytest

from lib.retrieve import Retriever, rrf_fuse


def test_single_ranking_preserves_order():
    assert [d for d, _ in rrf_fuse([["a", "b", "c"]])] == ["a", "b", "c"]


def test_document_ranked_by_both_retrievers_wins():
    # "b" is 2nd and 1st; "a" is 1st and 3rd. Agreement beats a single top hit.
    assert rrf_fuse([["a", "b", "c"], ["b", "c", "a"]])[0][0] == "b"


def test_scores_use_the_reciprocal_rank_formula():
    scored = dict(rrf_fuse([["a", "b"]], k=60))
    assert abs(scored["a"] - 1 / 61) < 1e-9
    assert abs(scored["b"] - 1 / 62) < 1e-9


def test_disjoint_rankings_are_unioned():
    assert len(rrf_fuse([["a"], ["b"], ["c"]])) == 3


def test_empty_input_is_empty():
    assert rrf_fuse([]) == []
    assert rrf_fuse([[], []]) == []


def test_results_are_sorted_best_first():
    fused = rrf_fuse([["a", "b", "c"], ["c", "b", "a"], ["b", "a", "c"]])
    assert fused == sorted(fused, key=lambda x: -x[1])


def test_k_dampens_the_advantage_of_rank_one():
    top_heavy = dict(rrf_fuse([["a", "b"]], k=1))
    flat = dict(rrf_fuse([["a", "b"]], k=1000))
    assert top_heavy["a"] / top_heavy["b"] > flat["a"] / flat["b"]


# ---- Retriever._chroma memoization --------------------------------------
#
# Retriever() itself is cheap: __init__ only computes paths, and every real
# load (ontology, messages, threads, Chroma) is a lazily-evaluated
# cached_property or happens inside _chroma(). These tests never touch the
# real embedding model or the real Chroma store -- they monkeypatch the two
# classes _chroma() imports and count constructions, so the mechanism is
# asserted directly rather than inferred from timing.


class _FakeEmbeddings:
    def __init__(self, **kwargs):
        pass


def _make_fake_chroma(calls: dict):
    class _FakeChroma:
        def __init__(self, **kwargs):
            calls["n"] += 1

        def similarity_search(self, query, k):
            return []

    return _FakeChroma


def _write_fake_store(store_dir):
    store_dir.mkdir(parents=True, exist_ok=True)
    (store_dir / "meta.json").write_text(
        json.dumps({"embedding_model": "fake-model", "normalize": True}),
        encoding="utf-8",
    )


def test_chroma_is_cached_per_store_dir(tmp_path, monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr("langchain_chroma.Chroma", _make_fake_chroma(calls))
    monkeypatch.setattr("langchain_huggingface.HuggingFaceEmbeddings", _FakeEmbeddings)

    store_a = tmp_path / "a"
    store_b = tmp_path / "b"
    _write_fake_store(store_a)
    _write_fake_store(store_b)

    r = Retriever()
    first = r._chroma(store_a)
    second = r._chroma(store_a)  # same dir: must reuse, not rebuild
    third = r._chroma(store_b)  # different dir: must build separately

    assert first is second
    assert first is not third
    assert calls["n"] == 2  # one build for store_a, one for store_b


def test_repeated_vector_search_does_not_reload_the_store(tmp_path, monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr("langchain_chroma.Chroma", _make_fake_chroma(calls))
    monkeypatch.setattr("langchain_huggingface.HuggingFaceEmbeddings", _FakeEmbeddings)

    store_dir = tmp_path / "store"
    _write_fake_store(store_dir)

    r = Retriever()
    r.store_dir = store_dir

    r.search("hello", mode="vector", expand=False)
    r.search("world", mode="vector", expand=False)

    assert calls["n"] == 1


def test_search_rejects_unknown_mode():
    r = Retriever()
    with pytest.raises(ValueError, match="vectors"):
        r.search("hello", mode="vectors")


# ---- one embedding model, shared across stores ---------------------------
#
# The three stores (messages, episodes, docs) are built with the same model,
# and each used to construct its own copy of it: measured at 1.34GB resident
# and 24s to load all three, against 0.52GB and 9.5s once they share. What
# must NOT be shared is a model across stores that disagree about which model
# they were built with -- that binding comes from each store's own meta.json
# and is what stops query-time and build-time from drifting, so the second
# test here is the load-bearing one.


def _make_counting_embeddings(seen: list):
    class _CountingEmbeddings:
        def __init__(self, **kwargs):
            seen.append(kwargs.get("model_name"))

    return _CountingEmbeddings


def test_stores_sharing_a_model_build_one_embedder(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr("langchain_chroma.Chroma", _make_fake_chroma({"n": 0}))
    monkeypatch.setattr("langchain_huggingface.HuggingFaceEmbeddings",
                        _make_counting_embeddings(seen))

    store_a, store_b = tmp_path / "a", tmp_path / "b"
    _write_fake_store(store_a)
    _write_fake_store(store_b)

    r = Retriever()
    r._chroma(store_a)
    r._chroma(store_b)

    assert seen == ["fake-model"]  # built once, reused for the second store


def test_stores_with_different_models_do_not_share_an_embedder(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr("langchain_chroma.Chroma", _make_fake_chroma({"n": 0}))
    monkeypatch.setattr("langchain_huggingface.HuggingFaceEmbeddings",
                        _make_counting_embeddings(seen))

    store_a, store_b = tmp_path / "a", tmp_path / "b"
    _write_fake_store(store_a)
    _write_fake_store(store_b)
    (store_b / "meta.json").write_text(
        json.dumps({"embedding_model": "other-model", "normalize": True}),
        encoding="utf-8",
    )

    r = Retriever()
    r._chroma(store_a)
    r._chroma(store_b)

    # Querying a store with the wrong model returns confident nonsense rather
    # than an error, so the cache must key on the model, not just be a cache.
    assert seen == ["fake-model", "other-model"]


# ---- warm() --------------------------------------------------------------


def _write_fake_store_with_vectors(store_dir):
    _write_fake_store(store_dir)
    (store_dir / "chroma.sqlite3").write_bytes(b"")


def test_warm_loads_every_store_that_has_vectors(tmp_path, monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr("langchain_chroma.Chroma", _make_fake_chroma(calls))
    monkeypatch.setattr("langchain_huggingface.HuggingFaceEmbeddings", _FakeEmbeddings)

    r = Retriever()
    r.store_dir = tmp_path / "crm-sig"
    r.episode_store_dir = tmp_path / "crm-sig-episodes"
    r.document_store_dir = tmp_path / "crm-sig-docs"
    for d in (r.store_dir, r.episode_store_dir, r.document_store_dir):
        _write_fake_store_with_vectors(d)

    loaded = r.warm()

    assert loaded == ["crm-sig", "crm-sig-episodes", "crm-sig-docs"]
    assert calls["n"] == 3
    # And warming is what makes the first search free, not merely eager.
    r.search("hello", mode="vector", expand=False)
    assert calls["n"] == 3


def test_warm_skips_stores_fetched_without_vectors(tmp_path, monkeypatch):
    # `build.py fetch --no-vectors` leaves meta.json (it is how the model
    # binding is checked) and fts.sqlite3, but no chroma.sqlite3. Warming
    # such a deployment must be a no-op, not a crash: BM25-only is supported.
    calls = {"n": 0}
    monkeypatch.setattr("langchain_chroma.Chroma", _make_fake_chroma(calls))
    monkeypatch.setattr("langchain_huggingface.HuggingFaceEmbeddings", _FakeEmbeddings)

    r = Retriever()
    r.store_dir = tmp_path / "crm-sig"
    r.episode_store_dir = tmp_path / "crm-sig-episodes"
    r.document_store_dir = tmp_path / "crm-sig-docs"
    _write_fake_store(r.store_dir)                       # meta.json only
    _write_fake_store_with_vectors(r.episode_store_dir)  # vectors present
    # document store absent entirely

    assert r.warm() == ["crm-sig-episodes"]
    assert calls["n"] == 1


# ---- messages/by_hash tolerate a missing archive -------------------------
#
# data/clean.jsonl is the cleaned mbox: 143MB, gitignored, shipped out of
# band. A fresh clone -- which is exactly the environment this repository
# is published for -- has no such file. `episodes` and `documents` already
# return empty in that case; `messages` opened the path unguarded and raised
# FileNotFoundError, which `concept` surfaced as a bare traceback because it
# reaches `messages` (via `by_hash`) to count how often the archive mentions
# an identifier. Reproduced with `uv run python search.py concept E22` in a
# real clone (see task-1-report.md).


def test_messages_is_empty_when_the_archive_is_absent(tmp_path, monkeypatch):
    import lib.retrieve as R

    monkeypatch.setattr(R, "DATA_DIR", tmp_path)
    assert R.Retriever().messages == {}
    assert R.Retriever().by_hash == {}


# ---- threads/thread_of tolerate a missing archive -------------------------
#
# The same bug as `messages` above, found while verifying Task 1
# (task-1-report.md): `threads` opened data/threads.json unguarded, so
# `search.py thread <id>` -- which reaches it via `get_thread` -- died on a
# bare FileNotFoundError traceback in a fresh clone, the one environment
# this repository is published for. `messages`, `episodes` and `documents`
# already return empty in that case; this brings `threads` in line with
# them, the same fix, same shape, one property later.


def test_threads_is_empty_when_the_archive_is_absent(tmp_path, monkeypatch):
    import lib.retrieve as R

    monkeypatch.setattr(R, "DATA_DIR", tmp_path)
    assert R.Retriever().threads == {}
    # thread_of is `{m: t for t, v in self.threads.items() for m in
    # v["message_ids"]}` -- derived from threads, not read from disk itself
    # -- so it needs no guard of its own; verified here rather than assumed,
    # the same way Task 1's report verified by_hash.
    assert R.Retriever().thread_of == {}


# ---- filtered search widens the candidate pool --------------------------
#
# from_email/after/before/entity filters run over the fused candidate list,
# which is capped at top_k*3 per retriever. A filter whose matches don't
# happen to land inside that window used to starve silently: "scope note" +
# after=2024 returned 1 hit out of 312 real candidates in the corpus. That
# starvation is a property of real ranking order on real data -- a fake
# retriever with a handful of docs can't reproduce "the true matches rank
# outside the top 30" -- so these run against the real crm-sig store.
#
# Retriever() is cheap to construct (see above); only the first search here
# pays the ~11s Chroma + embedding-model load, and Fix Round 1's
# per-store_dir cache means the other two tests in this module reuse it.


@pytest.fixture(scope="module")
def real_retriever():
    return Retriever()


def test_narrow_after_filter_still_fills_a_full_page(real_retriever):
    results = real_retriever.search("scope note", top_k=10, after=2024)
    assert len(results) == 10
    for r in results:
        assert int((r["date"] or "0")[:4]) >= 2024


def test_every_returned_hit_satisfies_the_entity_filter(real_retriever):
    results = real_retriever.search("issue", top_k=10, entity="E84")
    assert len(results) > 0
    for r in results:
        rec = real_retriever.by_hash[r["chunk_id"].split("#")[0]]
        assert "E84" in (rec.get("entities", []) + rec.get("entities_historical", []))


def test_widen_loop_terminates_when_the_filter_has_no_matches(real_retriever):
    # The archive runs through 2026 (see meta.json); nothing satisfies
    # after=2027. If widening weren't capped at the corpus ceiling, this
    # would spin forever trying to fill a page that can't exist.
    results = real_retriever.search("scope note", top_k=1000, after=2027)
    assert results == []


def test_rrf_fuse_weights_scale_a_ranking_contribution():
    bm25 = ["a", "b"]
    vector = ["b", "a"]
    # Equal weights: rank-1 in each, so the tie breaks on the second position.
    assert rrf_fuse([bm25, vector])[0][0] == "a"
    # Doubling the vector ranking flips it to that retriever's pick.
    assert rrf_fuse([bm25, vector], weights=[1.0, 2.0])[0][0] == "b"


def test_rrf_fuse_defaults_to_equal_weights():
    a = rrf_fuse([["x", "y"], ["y", "x"]])
    b = rrf_fuse([["x", "y"], ["y", "x"]], weights=[1.0, 1.0])
    assert a == b


def test_rrf_fuse_rejects_a_weight_count_mismatch():
    with pytest.raises(ValueError, match="2 weights for 1 rankings"):
        rrf_fuse([["a"]], weights=[1.0, 1.0])


class TestVectorWeighting:
    """BM25 earns an even vote only when the query gives it something exact to
    match. `search_documents` established this; `search` fused evenly for far
    longer, which is what buried thread t0426."""

    def test_identifier_query_keeps_the_fusion_even(self):
        from lib.retrieve import vector_weight_for
        for q in ("E22 scope note", "what does P70 document", "compare E31 and E73"):
            assert vector_weight_for(q) == 1.0

    def test_query_with_no_identifier_favours_the_dense_ranking(self):
        from lib.retrieve import vector_weight_for
        for q in ("teacher student relationship", "how do I model a photograph",
                  "asymmetric relations between people"):
            assert vector_weight_for(q) == 2.0

    def test_a_bare_number_is_not_an_identifier(self):
        from lib.retrieve import vector_weight_for
        assert vector_weight_for("issue 332 resolution") == 2.0


def test_vector_search_without_the_extra_says_what_to_do(tmp_path, monkeypatch):
    """A fetch with --no-vectors leaves BM25 working and hybrid not.

    That is a supported configuration, not a broken one, so the failure has
    to name both remedies. It used to surface as "No module named
    'langchain_chroma'", which tells a user neither what is wrong nor that
    passing mode="bm25" would work right now.
    """
    import lib.retrieve as R

    store = tmp_path / "crm-sig"
    store.mkdir(parents=True)
    r = R.Retriever()
    with pytest.raises(RuntimeError) as excinfo:
        r._chroma(store)
    message = str(excinfo.value)
    assert "bm25" in message
    # Either remedy is acceptable depending on which is missing here; both
    # are one line and the message must carry the one that applies.
    assert "--extra archive" in message or "build.py fetch" in message
