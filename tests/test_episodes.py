import json

import pytest

from lib.config import PROJECT_ROOT
from lib.episodes import (
    EPISODE_SCHEMA,
    MAX_THREADS_PER_SHARD,
    SHARD_CHAR_BUDGET,
    build_prompt,
    collect_shards,
    eligible_threads,
    episode_text,
    pack_shards,
    thread_members,
    validate_entities,
)
from lib.ontology import add_extensions, load_family, parse_ontology


@pytest.fixture(scope="module")
def onto():
    onto = parse_ontology(PROJECT_ROOT / "sources" / "cidoc_crm_v7.1.3.xml")
    family = load_family(PROJECT_ROOT / "sources" / "crm_family.json")
    # Mentions stand in for the archive scan: validate_entities only accepts
    # family ids the corpus actually uses.
    add_extensions(onto, {i: 5 for i in ["F39", "I8", "SP5", "A11", "O13", "LRM-E8"]}, family)
    return onto


def test_schema_returns_a_list_of_episodes():
    assert EPISODE_SCHEMA["type"] == "object"
    item = EPISODE_SCHEMA["properties"]["episodes"]["items"]
    for field in ("topic", "question", "outcome", "message_indexes", "entities"):
        assert field in item["properties"]
    assert item["properties"]["outcome"]["enum"] == [
        "decided", "unresolved", "informational"
    ]


def test_build_prompt_numbers_messages_for_reference():
    records = [
        {"date": "2011-03-02T09:14:00", "from_name": "Martin Doerr",
         "subject": "iso crm ballot", "body": "We should vote."},
        {"date": "2011-03-19T17:02:00", "from_name": "Christian-Emil Ore",
         "subject": "next meetings", "body": "When is the next meeting?"},
    ]
    prompt = build_prompt("t0042", records)
    assert "[0]" in prompt and "[1]" in prompt
    assert "Martin Doerr" in prompt
    assert "We should vote." in prompt


def test_eligible_threads_skips_singletons():
    threads = {
        "t1": {"message_ids": ["a"]},
        "t2": {"message_ids": ["b", "c"]},
        "t3": {"message_ids": ["d", "e", "f"]},
    }
    assert eligible_threads(threads, 2) == ["t2", "t3"]


def test_validate_entities_four_way_split(onto):
    onto = dict(onto)
    onto["historical"] = {"E84": {"id": "E84", "status": "historical",
                                  "mentions": 269, "label": None}}
    current, historical, extension, bogus = validate_entities(
        ["E55", "E84", "E999", "P140", "F39", "zzz"], onto
    )
    assert current == ["E55", "P140"]
    assert historical == ["E84"]      # deprecated: kept, never dropped
    assert extension == ["F39"]       # FRBRoo: real, just not in CRMbase
    assert bogus == ["E999", "zzz"]


def test_validate_entities_keeps_crm_family_extension_ids(onto):
    # These are debated on this list and must not be scored as hallucinations.
    _, _, extension, bogus = validate_entities(
        ["F39", "LRM-E8", "I8", "SP5", "A11", "O13"], onto
    )
    assert bogus == []
    assert set(extension) == {"F39", "LRM-E8", "I8", "SP5", "A11", "O13"}


def test_validate_entities_still_rejects_true_hallucinations(onto):
    # TC46/SC4/WG9 are the ISO committee that standardises the CRM: they have
    # the shape of class ids and appear all over this archive.
    _, _, extension, bogus = validate_entities(
        ["E9999", "banana", "TC46", "SC4", "WG9"], onto
    )
    assert extension == []
    assert len(bogus) == 5


def test_validate_entities_normalizes_inverse_and_dotted(onto):
    current, _, _, _ = validate_entities([" p25i ", "P14.1"], onto)
    assert "P25" in current and "P14" in current


def test_episode_text_concatenates_the_embedded_fields():
    ep = {
        "topic": "Whether E55 Type should permit E28",
        "question": "Does E55 admit conceptual objects?",
        "positions": [{"who": "Martin Doerr", "position": "No"}],
        "outcome": "decided",
        "outcome_detail": "Rejected in favour of P2.",
        "entities": ["E55", "E28"],
    }
    text = episode_text(ep)
    for fragment in ("E55 Type", "conceptual objects", "Martin Doerr", "Rejected"):
        assert fragment in text


def test_episode_text_survives_missing_optional_fields():
    assert episode_text({"topic": "T"}).strip()


def test_pack_shards_respects_the_character_budget():
    # Ten threads at 30k each: a thread-count-only packer would emit one shard.
    sizes = {f"t{i}": 30_000 for i in range(10)}
    shards = pack_shards(list(sizes), sizes)
    assert len(shards) > 1
    for shard in shards:
        assert sum(sizes[t] for t in shard) <= SHARD_CHAR_BUDGET


def test_pack_shards_respects_the_thread_cap_when_threads_are_tiny():
    sizes = {f"t{i}": 10 for i in range(MAX_THREADS_PER_SHARD * 3)}
    shards = pack_shards(list(sizes), sizes)
    assert all(len(s) <= MAX_THREADS_PER_SHARD for s in shards)
    assert len(shards) == 3


def test_pack_shards_gives_an_oversized_thread_its_own_shard():
    sizes = {"small": 100, "huge": SHARD_CHAR_BUDGET * 2, "after": 100}
    shards = pack_shards(list(sizes), sizes)
    assert ["huge"] in shards


def test_pack_shards_loses_no_threads():
    sizes = {f"t{i}": (i * 7919) % 60_000 for i in range(200)}
    shards = pack_shards(list(sizes), sizes)
    assert [t for s in shards for t in s] == list(sizes)


def test_thread_members_is_the_shared_index_basis():
    # A message referenced by the thread but absent from records must be
    # dropped identically on both sides, or episode indexes misattribute.
    threads = {"t1": {"message_ids": ["a", "ghost", "c"]}}
    records = {"a": {}, "c": {}}
    assert thread_members(threads, "t1", records) == ["a", "c"]


def test_validate_entities_accepts_rdfs_class_names(onto):
    # The archive writes ids in RDFS form too; the same identifier must resolve.
    current, _, _, bogus = validate_entities(
        ["E33_Linguistic_Object", "P190_has_symbolic_content", "E1_CRM_Entity"], onto
    )
    assert bogus == []
    assert set(current) == {"E33", "P190", "E1"}


def test_validate_entities_accepts_the_old_dual_direction_notation(onto):
    # P81a/P81b/P120F are how this list wrote directions for years -- P81a
    # alone occurs 54 times in the corpus.
    current, _, _, bogus = validate_entities(["P81a", "P81b", "P82a", "P57F"], onto)
    assert bogus == []
    assert set(current) == {"P81", "P82", "P57"}


def test_validate_entities_strips_inverse_from_deprecated_ids(onto):
    # P87 is deprecated, so an inverse-stripper that only consults the current
    # vocabulary rejects P87i as a hallucination.
    onto = dict(onto)
    onto["historical"] = {"P87": {"id": "P87", "status": "historical",
                                  "mentions": 12, "label": None}}
    _, historical, _, bogus = validate_entities(["P87i"], onto)
    assert bogus == []
    assert historical == ["P87"]


def test_validate_entities_rejects_ids_absent_from_the_archive(onto):
    # SP1, SP8, O11 and E102 have zero occurrences in this corpus: real-looking
    # shapes, but invented here.
    _, _, extension, bogus = validate_entities(["SP1", "SP8", "O11", "E102"], onto)
    assert extension == []
    assert len(bogus) == 4


def test_collect_shards_coerces_out_of_enum_values(tmp_path, onto):
    # Nothing enforces the schema on the way in, and a real run returned
    # outcome "proposal". Downstream filters match these values exactly, so a
    # stray one is invisible rather than noisy.
    threads = {"t1": {"message_ids": ["a", "b"]}}
    records = {"a": {"date": "2011-01-01", "from_name": "X"},
               "b": {"date": "2011-01-02", "from_name": "Y"}}
    shard_dir = tmp_path / "prompts"
    shard_dir.mkdir()
    (shard_dir / "result-000.json").write_text(json.dumps({
        "t1": {"episodes": [{
            "topic": "T", "question": "Q", "message_indexes": [0, 1],
            "positions": [], "outcome": "proposal", "outcome_detail": "",
            "entities": [], "confidence": "certain",
        }]}
    }))
    episodes = collect_shards(shard_dir, threads, records, onto)
    assert episodes[0]["outcome"] == "informational"
    assert episodes[0]["confidence"] == "medium"


def test_collect_shards_survives_a_malformed_shard(tmp_path, onto):
    shard_dir = tmp_path / "prompts"
    shard_dir.mkdir()
    (shard_dir / "result-000.json").write_text("{ this is not json")
    assert collect_shards(shard_dir, {}, {}, onto) == []


def test_collect_shards_writes_beside_its_input_not_into_data(tmp_path, onto):
    # Regression: collect_shards read from shard_dir but wrote to a hardcoded
    # DATA_DIR/episodes.jsonl, so these very tests truncated the real corpus.
    from lib.config import DATA_DIR

    real = DATA_DIR / "episodes.jsonl"
    before = real.read_bytes() if real.exists() else None
    shard_dir = tmp_path / "prompts"        # mirrors data/prompts
    shard_dir.mkdir()
    (shard_dir / "result-000.json").write_text(json.dumps({
        "t1": {"episodes": [{
            "topic": "T", "question": "Q", "message_indexes": [0],
            "positions": [], "outcome": "decided", "outcome_detail": "",
            "entities": [], "confidence": "high",
        }]}
    }))
    collect_shards(shard_dir, {"t1": {"message_ids": ["a"]}},
                   {"a": {"date": "2011-01-01", "from_name": "X"}}, onto)
    assert (tmp_path / "episodes.jsonl").exists()
    after = real.read_bytes() if real.exists() else None
    assert after == before, "collect_shards must not touch the real corpus"
