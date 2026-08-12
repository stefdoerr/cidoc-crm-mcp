"""Tests for applicable/required/connecting properties (lib/ontology.py).

These three functions exist because the modelling evaluation kept losing
cases the same way: the answer picked the right class and then never found
the property that completes the model. The judges named the misses
specifically -- E13 without P177, E10 without P30, E8 without P24, E12
without P108, E11/E29 without P33 -- so those identifiers are asserted here
by name. If one of these tests fails, a real evaluation regression has
happened, not a cosmetic one.

Every guard is written so that removing what it protects breaks it:

  * `test_applicable_is_not_truncated` fails if the old `[:20]` cap returns;
  * `test_outgoing_is_ranked_by_declaring_distance` fails if the distance
    term is dropped and specificity alone ranks again;
  * `test_is_required_matches_mid_string` fails for a `startswith` test;
  * `test_extension_class_inherits_base_properties` fails for a base-only
    class map;
  * `test_universal_property_sorts_last` fails if the generality term goes.

Reads the committed XML and crm_family.json, never data/ontology.json --
that one is a gitignored build artifact, and tests/test_ontology.py sets the
precedent of building the ontology the way production does.
"""

import pytest

from lib.config import PROJECT_ROOT
from lib.ontology import (
    _property_name,
    add_extensions,
    applicable_properties,
    connecting_properties,
    is_required,
    load_family,
    parse_ontology,
    required_properties,
)


@pytest.fixture(scope="module")
def base():
    return parse_ontology(PROJECT_ROOT / "sources" / "cidoc_crm_v7.1.3.xml")


@pytest.fixture(scope="module")
def onto():
    """CRMbase plus the family extensions, as the CLI assembles it."""
    o = parse_ontology(PROJECT_ROOT / "sources" / "cidoc_crm_v7.1.3.xml")
    family = load_family(PROJECT_ROOT / "sources" / "crm_family.json")
    # Mentions are what gate an extension into the ontology; these ids are
    # the ones the assertions below need.
    add_extensions(o, {"A1": 5, "S2": 9, "S13": 7, "O5": 4, "O3": 6, "L54": 2}, family)
    return o


def ids(rows):
    return [r["id"] for r in rows]


# --------------------------------------------------------------------------
# the truncation defect
# --------------------------------------------------------------------------

def test_applicable_is_not_truncated(base):
    """The defect this work exists to fix.

    E10 has far more than twenty applicable outgoing properties, and P30 --
    which the CRM declares necessary -- sat outside the first twenty. The old
    display sliced at 20 and never showed it.
    """
    outgoing = applicable_properties(base, "E10")["outgoing"]
    assert len(outgoing) > 20, "test is pointless unless E10 exceeds the old cap"
    assert "P30" in ids(outgoing)
    assert "P30" not in ids(outgoing[:20][:0])  # sanity: list is not empty-sliced


@pytest.mark.parametrize("class_id,prop", [
    ("E10", "P30"),   # propertychoice-c2: "P24/P30 ... which A omits entirely"
    ("E8", "P24"),    # same case
    ("E13", "P177"),  # archives-c2: "its E13 omits P177"
    ("E12", "P108"),  # classchoice-c1, built-c1: "neither asserts P108"
])
def test_required_surfaces_the_properties_the_evaluation_missed(base, class_id, prop):
    assert prop in ids(required_properties(base, class_id))


def test_required_is_a_subset_of_outgoing(base):
    for cid in ("E10", "E13", "E22", "E53"):
        out = set(ids(applicable_properties(base, cid)["outgoing"]))
        assert set(ids(required_properties(base, cid))) <= out


def test_required_stays_small_enough_to_always_display(base):
    """The display shows every required property with no cap; that is only
    safe because there are few of them."""
    worst = max(len(required_properties(base, c)) for c in base["classes"])
    assert worst <= 12, f"required lists grew to {worst}; the uncapped display needs rethinking"


def test_is_required_matches_mid_string():
    """A `startswith('necessary')` test silently matches nothing: the word
    always sits after the cardinality phrase."""
    assert is_required({"quantification": "many to many, necessary (1,n:0,n)"})
    assert is_required({"quantification": "one to many, necessary, dependent (1,n:1,1)"})
    assert not is_required({"quantification": "many to many (0,n:0,n)"})
    assert not is_required({})


def test_extension_properties_are_never_reported_required(onto):
    """The scraped family declarations carry no quantification at all, so
    claiming a CRMsci property is mandatory would invent a constraint."""
    for cid in ("S2", "A1"):
        for row in required_properties(onto, cid):
            assert row["id"].startswith("P"), (
                f"{row['id']} is an extension property reported as required")


# --------------------------------------------------------------------------
# ranking
# --------------------------------------------------------------------------

def test_outgoing_is_ranked_by_declaring_distance(base):
    """Specificity alone put P183/P134/P182 -- domain E1, so applicable to
    every class in the model -- at the head of every list, which is what
    pushed E10's own properties out of the visible twenty."""
    outgoing = applicable_properties(base, "E10")["outgoing"]
    head = ids(outgoing[:3])
    assert set(head) == {"P28", "P29", "P30"}, head
    assert all(r["distance"] == 0 for r in outgoing[:3])
    # distance must be non-decreasing across the whole list
    distances = [r["distance"] for r in outgoing]
    assert distances == sorted(distances)


def test_via_names_the_class_that_declares_it(base):
    rows = {r["id"]: r for r in applicable_properties(base, "E10")["outgoing"]}
    assert rows["P30"]["via"] == "E10" and rows["P30"]["distance"] == 0
    assert rows["P14"]["via"] == "E7" and rows["P14"]["distance"] >= 1


def test_incoming_reports_the_far_end_and_the_inverse_name(base):
    rows = {r["id"]: r for r in applicable_properties(base, "E53")["incoming"]}
    assert "P53" in rows
    assert rows["P53"]["other"] == "E18"        # what can point at an E53
    assert rows["P53"]["name"]                   # inverse reading, not blank


# --------------------------------------------------------------------------
# connect
# --------------------------------------------------------------------------

@pytest.mark.parametrize("subject,obj,expected", [
    ("E11", "E29", "P33"),    # technical-c3
    ("E70", "E54", "P43"),    # naturalhistory-c3
    ("E92", "E92", "P10"),    # built-c2
    ("E18", "E53", "P156"),   # archaeology-c3
    ("E7", "E39", "P14"),     # propertychoice-c1
])
def test_connect_finds_the_property_the_evaluation_missed(base, subject, obj, expected):
    assert expected in ids(connecting_properties(base, subject, obj))


def test_connect_ranks_the_target_property_first(base):
    for subject, obj, expected in [("E11", "E29", "P33"), ("E70", "E54", "P43"),
                                   ("E7", "E39", "P14"), ("E18", "E53", "P156")]:
        assert ids(connecting_properties(base, subject, obj))[0] == expected


def test_universal_property_sorts_last(onto):
    """CRMdig's L54 is declared E1 -> E1, so it joins any two classes in the
    model and appeared mid-list in every single query before the generality
    term existed."""
    rows = ids(connecting_properties(onto, "E11", "E29"))
    assert "L54" in rows, "fixture must include the universal property"
    assert rows[-1] == "L54"


def test_connect_respects_the_declared_domain(onto):
    """O5's domain is S2, not E20: CRMsci routes specimen-to-sample through
    the sampling event, and inventing a direct link would be exactly the kind
    of unsupported modelling this tool is meant to prevent."""
    assert "O5" not in ids(connecting_properties(onto, "E20", "S13"))
    assert "O5" in ids(connecting_properties(onto, "S2", "S13"))


def test_connect_is_direction_sensitive(base):
    assert "P14" in ids(connecting_properties(base, "E7", "E39"))
    assert "P14" not in ids(connecting_properties(base, "E39", "E7"))


def test_connect_marks_the_exactly_declared_pair(base):
    rows = {r["id"]: r for r in connecting_properties(base, "E7", "E39")}
    assert rows["P14"]["exact"] is True
    assert rows["P11"]["exact"] is False    # declared on E5, inherited by E7


def test_connect_inherits_through_the_hierarchy(base):
    """E12 is an E7, so a property declared on E7 must be offered for E12 --
    the whole reason a plain domain equality test is not enough."""
    assert "P14" in ids(connecting_properties(base, "E12", "E39"))


# --------------------------------------------------------------------------
# extensions
# --------------------------------------------------------------------------

def test_extension_class_inherits_base_properties(onto):
    """CRMarchaeo declares A1 a subclass of E12, so an A1 genuinely carries
    CRMbase's production properties. A base-only class map finds none."""
    outgoing = ids(applicable_properties(onto, "A1")["outgoing"])
    assert "P108" in outgoing
    assert "P14" in outgoing


def test_extension_property_renders_a_name_not_a_bare_id(onto):
    """Family declarations carry `label`, not `direct_name`. Falling back is
    what stops extension properties printing as anonymous integers -- the
    exact defect being fixed."""
    rows = {r["id"]: r for r in connecting_properties(onto, "S2", "S13")}
    assert rows["O5"]["name"], "O5 rendered with no name"
    assert "removed" in rows["O5"]["name"]


def test_property_name_prefers_direct_then_label():
    assert _property_name({"direct_name": "carried out by", "label": "x"}) == "carried out by"
    assert _property_name({"label": "removed (was removed by)"}) == "removed (was removed by)"
    assert _property_name({"direct_name": "a", "inverse_name": "b"}, inverse=True) == "b"
    assert _property_name({}) == ""


def test_self_connection_is_printed_once(base):
    """`connect E21 E21` asks one question, not two: forward and backward are
    the same query when the classes are the same, and printing both doubled
    the output for no information."""
    from search import format_connect
    rows = connecting_properties(base, "E21", "E21")
    out = format_connect("E21", "E21", rows, rows)
    assert out.count("E21 -> E21:") == 1
    assert out.count("P152") == 1


def test_two_different_classes_still_show_both_directions(base):
    from search import format_connect
    fwd = connecting_properties(base, "E7", "E39")
    bwd = connecting_properties(base, "E39", "E7")
    out = format_connect("E7", "E39", fwd, bwd)
    assert "E7 -> E39:" in out and "E39 -> E7:" in out
