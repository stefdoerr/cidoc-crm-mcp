import pytest

from lib.config import PROJECT_ROOT, load_config
from lib.expand import build_lexicon, expand_query
from lib.ontology import parse_ontology


@pytest.fixture(scope="module")
def lexicon():
    onto = parse_ontology(PROJECT_ROOT / "sources" / "cidoc_crm_v7.1.3.xml")
    cfg = load_config("crm-sig")
    return build_lexicon(onto, cfg["ontology"]["stop_labels"])


@pytest.fixture(scope="module")
def pattern():
    return load_config("crm-sig")["ontology"]["id_pattern"]


def test_id_expands_to_label(lexicon, pattern):
    assert "Type" in expand_query("what about E55", lexicon, pattern)


def test_stop_label_does_not_expand_to_id(lexicon, pattern):
    # The whole point of the guard: bare "type" must not drag in E55.
    assert "E55" not in expand_query("controlled vocabulary type", lexicon, pattern)


def test_multiword_label_expands_to_id(lexicon, pattern):
    assert "E22" in expand_query("what is a Human-Made Object", lexicon, pattern)


def test_multiword_label_match_is_case_insensitive(lexicon, pattern):
    assert "E22" in expand_query("human-made object rules", lexicon, pattern)


def test_property_id_expands_to_both_names(lexicon, pattern):
    added = expand_query("P140 semantics", lexicon, pattern)
    assert "assigned attribute to" in added
    assert "was attributed by" in added


def test_dotted_property_normalizes_to_base(lexicon, pattern):
    assert expand_query("P14.1 role", lexicon, pattern), "P14.1 should resolve via P14"


def test_unknown_id_expands_to_nothing(lexicon, pattern):
    assert expand_query("E999 nonsense", lexicon, pattern) == []


def test_added_terms_exclude_terms_already_in_query(lexicon, pattern):
    added = expand_query("E22 Human-Made Object", lexicon, pattern)
    assert "E22" not in added


def test_stop_label_still_available_in_id_to_label_direction(lexicon):
    assert lexicon["id_to_labels"]["E55"] == ["Type"]


# Fix Round 1: Word-boundary and span-claiming tests.
# These ensure substring matching (formation→information, move→removed)
# and overlapping label matches (activity inside curation activity) don't fire.


def test_formation_not_in_information(lexicon, pattern):
    # "formation" is a substring of "information" but shouldn't expand to E66.
    added = expand_query("information object", lexicon, pattern)
    assert "E66" not in added


def test_move_not_in_removed(lexicon, pattern):
    # "move" is a substring of "removed" but shouldn't expand to E9.
    added = expand_query("the item was removed", lexicon, pattern)
    assert "E9" not in added


def test_activity_not_inside_curation_activity(lexicon, pattern):
    # "activity" matches inside "curation activity", but shouldn't expand to E7
    # because "curation activity" (longer) claims the span first.
    added = expand_query("curation activity", lexicon, pattern)
    assert "E87" in added  # Curation Activity is correct.
    assert "E7" not in added  # Activity alone must not fire.


def test_word_boundary_matching_preserves_multiword_labels(lexicon, pattern):
    # Positive control: multiword labels still work.
    assert "E22" in expand_query("Human-Made Object", lexicon, pattern)
    # ID expansion still works.
    assert "Type" in expand_query("E55", lexicon, pattern)


def test_dotted_properties_expand_id_to_label_only():
    """A .N property contributes id->label, never label->id.

    Six of the sixteen are labelled "has type" (P3.1, P67.1, P69.1,
    P102.1, P139.1, P189.1). "has type" is also P2's direct name and maps
    to ['P2'] alone. Registering the six in label_to_ids would make
    expand_query("has type") inject seven terms, none of which appear as
    tokens in the FTS index -- messages are tagged with id_pattern, whose
    capture group discards the .N suffix.
    """
    import json
    from lib.config import PROJECT_ROOT, load_config

    onto = json.loads((PROJECT_ROOT / "data" / "ontology.json").read_text(encoding="utf-8"))
    cfg = load_config("crm-sig")
    lex = build_lexicon(onto, cfg["ontology"]["stop_labels"])

    assert lex["id_to_labels"]["P14.1"] == ["in the role of"]
    assert lex["label_to_ids"]["has type"] == ["P2"]      # unchanged
    assert "in the role of" not in lex["label_to_ids"]
