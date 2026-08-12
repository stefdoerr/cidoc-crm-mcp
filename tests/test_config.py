from lib.config import load_config, PROJECT_ROOT, DATA_DIR, STORES_DIR


def test_loads_crm_sig_archive():
    cfg = load_config("crm-sig")
    assert cfg["mbox"] == "crm-sig.mbox"
    assert cfg["embedding_model"] == "Alibaba-NLP/gte-modernbert-base"
    assert cfg["chunk_size"] == 2000
    assert cfg["chunk_overlap"] == 200
    assert cfg["list_footer_marker"] == "Crm-sig mailing list"


def test_ontology_defaults_present():
    cfg = load_config("crm-sig")
    onto = cfg["ontology"]
    assert onto["xml"] == "sources/cidoc_crm_v7.1.3.xml"
    assert "Type" in onto["stop_labels"]
    assert onto["id_pattern"]


def test_episode_defaults_present():
    cfg = load_config("crm-sig")
    assert cfg["episodes"]["min_thread_size"] == 2


def test_unknown_archive_raises():
    import pytest
    with pytest.raises(KeyError):
        load_config("nope")


def test_paths_are_absolute():
    assert PROJECT_ROOT.is_absolute()
    assert DATA_DIR == PROJECT_ROOT / "data"
    assert STORES_DIR == PROJECT_ROOT / "stores"


def test_pick_device_returns_a_valid_torch_device():
    from lib.config import pick_device
    assert pick_device() in ("cuda", "cpu")


def test_the_publish_payload_excludes_what_git_already_carries():
    """data/eval/ and data/ontology.json must not be published.

    They are excluded for opposite reasons and both matter. data/eval/ is
    tracked in git precisely because it is NOT regenerable -- the questions
    were written by readers blind to the search system -- so it travels with
    the code and a second copy could drift from it. data/ontology.json is
    the reverse: rebuilt from tracked sources/ in seconds, so a downloaded
    copy could silently shadow the inputs it is supposed to be derived from,
    which is the failure the whole sources/ split exists to prevent.
    """
    import importlib.util
    import sys

    from lib.config import PROJECT_ROOT

    spec = importlib.util.spec_from_file_location(
        "publish_corpus", PROJECT_ROOT / "tools" / "publish_corpus.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["publish_corpus"] = module
    spec.loader.exec_module(module)

    payload = module.PAYLOAD
    assert not any("eval" in p for p in payload), payload
    assert not any("ontology.json" in p for p in payload), payload
    # And it must carry the things the archive layer actually gates on.
    for needed in ("data/clean.jsonl", "data/threads.json",
                   "data/documents.jsonl", "stores"):
        assert needed in payload, needed


def test_the_publish_payload_is_only_what_the_runtime_opens():
    """No build-time inputs.

    The first publish carried data/minutes/, data/issue_pages/ and
    data/minutes_issues.json -- 93MB, and 786 of 901 files, so most of the
    upload was material a consumer cannot use. They are inputs that
    `build.py docs` chunks into documents.jsonl; nothing opens them
    afterwards, and `crm_docs --kind minutes` still works because those
    chunks are in documents.jsonl.

    Pinned against lib/retrieve.py, which is the whole runtime: every
    data/ path in the payload must be one it actually reads.
    """
    import importlib.util
    import re
    import sys

    from lib.config import PROJECT_ROOT

    spec = importlib.util.spec_from_file_location(
        "publish_corpus", PROJECT_ROOT / "tools" / "publish_corpus.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["publish_corpus"] = module
    spec.loader.exec_module(module)

    runtime = (PROJECT_ROOT / "lib" / "retrieve.py").read_text(encoding="utf-8")
    opened = set(re.findall(r'DATA_DIR / "([^"]+)"', runtime))
    for entry in module.PAYLOAD:
        if not entry.startswith("data/"):
            continue
        assert entry.removeprefix("data/") in opened, (
            f"{entry} is published but lib/retrieve.py never opens it")
