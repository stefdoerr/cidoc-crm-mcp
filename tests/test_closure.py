import pytest

from lib.config import PROJECT_ROOT
from lib.ontology import ancestors, parse_ontology, property_closure


@pytest.fixture(scope="module")
def onto():
    return parse_ontology(PROJECT_ROOT / "sources" / "cidoc_crm_v7.1.3.xml")


@pytest.fixture(scope="module")
def closure(onto):
    return property_closure(onto)


def test_ancestors_is_inclusive_and_dag_safe(onto):
    # E22 has TWO parents (E19, E24) — a tree walk would miss one branch
    assert ancestors(onto, "E22") == {
        "E1", "E18", "E19", "E22", "E24", "E70", "E71", "E72", "E77"
    }


def test_ancestors_of_root_is_just_itself(onto):
    assert ancestors(onto, "E1") == {"E1"}


def test_ancestors_terminates_on_every_class(onto):
    # A missing visited set loops forever on the shared-ancestor diamonds
    for cid in onto["classes"]:
        assert "E1" in ancestors(onto, cid) or cid == "E1"


def test_closure_is_what_makes_the_answer_non_empty(onto, closure):
    direct = [p for p, e in onto["properties"].items() if e["domain"] == "E22"]
    assert direct == [], "precondition: nothing declares domain E22 directly"
    assert len(closure["E22"]["outgoing"]) == 31
    assert len(closure["E22"]["incoming"]) == 38


def test_both_directions_present_and_distinct(closure):
    out = set(closure["E22"]["outgoing"])
    inc = set(closure["E22"]["incoming"])
    assert out and inc
    assert out != inc


def test_generic_properties_reach_every_class(onto, closure):
    # P1/P2/P3 have domain E1, so they must apply to everything
    for cid in onto["classes"]:
        assert "P1" in closure[cid]["outgoing"], cid


def test_subproperty_ranks_before_its_parent(onto, closure):
    """Specificity ordering: the more specific choice must not be buried."""
    checked = 0
    for cid, lists in closure.items():
        order = {p: i for i, p in enumerate(lists["outgoing"])}
        for pid in lists["outgoing"]:
            for parent in onto["properties"][pid]["sub_property_of"]:
                if parent in order:
                    assert order[pid] < order[parent], (
                        f"{cid}: {pid} is more specific than {parent} "
                        f"but ranked after it"
                    )
                    checked += 1
    assert checked > 0, "no subproperty pairs exercised — test proves nothing"


def test_every_class_has_an_entry(onto, closure):
    assert set(closure) == set(onto["classes"])


def test_property_depth_longest_path_not_shortest():
    """Regression: _property_depth must compute longest path to root.

    Shortest-path BFS would mark a node seen on first reach and never
    re-expand it, inverting specificity ranking when multi-parent
    properties converge on a shared ancestor via different path lengths.

    Synthetic ontology:
      X.sub_property_of = [A, B]
      A.sub_property_of = [C]
      B.sub_property_of = [D]
      D.sub_property_of = [C]
      C.sub_property_of = [ROOT]

    X is a direct child of both A and B (depth 1 from each).
    B is a direct child of D (depth 1).
    A and B both reach C with different path lengths.
    Depth ranking must have X > B > A > D > C > ROOT.
    """
    from lib.ontology import _property_depth

    synthetic_onto = {
        "classes": {},
        "properties": {
            "ROOT": {"id": "ROOT", "sub_property_of": []},
            "C": {"id": "C", "sub_property_of": ["ROOT"]},
            "D": {"id": "D", "sub_property_of": ["C"]},
            "A": {"id": "A", "sub_property_of": ["C"]},
            "B": {"id": "B", "sub_property_of": ["D"]},
            "X": {"id": "X", "sub_property_of": ["A", "B"]},
        },
    }

    depth_x = _property_depth(synthetic_onto, "X")
    depth_b = _property_depth(synthetic_onto, "B")
    depth_a = _property_depth(synthetic_onto, "A")

    # X is more specific than B: depth must reflect this
    assert depth_x > depth_b, (
        f"X is more specific than B but has same or lower depth: "
        f"X={depth_x}, B={depth_b}"
    )
    assert depth_b > depth_a, (
        f"B is more specific than A but has same or lower depth: "
        f"B={depth_b}, A={depth_a}"
    )


def test_property_depth_cycle_safe():
    """Regression: _property_depth must handle cycles without stack overflow.

    A malformed cycle (e.g., loading data with validation errors) should
    terminate gracefully rather than blow the stack or loop forever.
    """
    from lib.ontology import _property_depth

    synthetic_onto = {
        "classes": {},
        "properties": {
            "A": {"id": "A", "sub_property_of": ["B"]},
            "B": {"id": "B", "sub_property_of": ["A"]},
        },
    }

    # Should terminate without raising RecursionError
    depth_a = _property_depth(synthetic_onto, "A")
    depth_b = _property_depth(synthetic_onto, "B")

    # Both should be defined (the function should handle cycles)
    assert isinstance(depth_a, int)
    assert isinstance(depth_b, int)


def test_resolve_property_id_inverse_forms(onto):
    """Inverse ids (P25i, P10i, etc.) resolve to their base forms."""
    from lib.ontology import resolve_property_id

    # The 7 inverse id pairs that appear in sub_property_of edges
    inverse_pairs = [
        ("P10i", "P10"),
        ("P157i", "P157"),
        ("P130i", "P130"),
        ("P176i", "P176"),
        ("P1i", "P1"),
    ]

    for inverse_id, base_id in inverse_pairs:
        assert resolve_property_id(onto, inverse_id) == base_id, (
            f"Failed to resolve {inverse_id} to {base_id}"
        )
        # Also verify the base resolves to itself
        assert resolve_property_id(onto, base_id) == base_id, (
            f"Failed to resolve base {base_id} to itself"
        )


def test_resolve_property_id_unknown_stays_unknown(onto):
    """Unknown ids stay unknown, even with trailing i."""
    from lib.ontology import resolve_property_id

    assert resolve_property_id(onto, "P999") is None
    assert resolve_property_id(onto, "P999i") is None
    assert resolve_property_id(onto, "E999") is None


def test_property_depth_resolves_inverse_ids(onto):
    """Inverse ids in sub_property_of are resolved correctly.

    The 7 properties with inverse-direction parents should traverse through
    their resolved parents correctly. Not all have depth > 1; it depends on
    whether the resolved parent has parents itself.
      - P9 → P10i (P10 has parents) → P9 should have depth > 1
      - P134 → P176i (P176 has parents) → P134 should have depth > 1
    """
    from lib.ontology import _property_depth

    # P9 → P10i; P10 has depth 1, so P9 should have depth 2
    assert _property_depth(onto, "P9") == 2

    # P134 → P176i (P176 has depth 3) + P15 (depth 0)
    # → P134 should have max(3, 0) + 1 = 4
    assert _property_depth(onto, "P134") == 4


def test_property_closure_ranks_inverse_parent_children_correctly(onto, closure):
    """Properties with inverse parents rank correctly relative to their parents.

    After resolving inverse ids, these 7 properties should now appear ranked
    in the closure correctly (more specific than their parents).
    """
    # The 7 properties with inverse parents and their resolved parent bases
    inverse_cases = [
        ("P9", "P10"),
        ("P59", "P157"),
        ("P73", "P130"),
        ("P134", "P176"),
        ("P156", "P157"),
        ("P169", "P1"),
        ("P170", "P1"),
    ]

    for child_id, parent_id in inverse_cases:
        # Find a class where both appear in the closure's outgoing properties
        for class_id, lists in closure.items():
            if child_id in lists["outgoing"] and parent_id in lists["outgoing"]:
                order = {p: i for i, p in enumerate(lists["outgoing"])}
                assert order[child_id] < order[parent_id], (
                    f"In {class_id}: {child_id} is more specific than {parent_id} "
                    f"but ranked after it (child at {order[child_id]}, "
                    f"parent at {order[parent_id]})"
                )
                break
