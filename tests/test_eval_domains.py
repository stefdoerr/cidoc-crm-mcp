"""tools/eval_domains.py: a property recommended without the class that
carries it is an incomplete recommendation.

The rule is domain-only. Checking ranges was measured and rejected: 133
flags across the same 116 answers, dominated by E39 Actor (51), E52
Time-Span (21) and E55 Type (10) -- classes nobody lists as a modelling
decision because they are plumbing.
"""

import json

import pytest

from lib.config import PROJECT_ROOT
from tools.eval_domains import check, resolve, satisfied_classes

ONTO = json.loads((PROJECT_ROOT / "data" / "ontology.json").read_text(encoding="utf-8"))
EVAL_DIR = PROJECT_ROOT / "data" / "eval"


def _answer(classes, properties):
    return {"case_id": "t", "classes_proposed": classes,
            "properties_proposed": properties}


def test_domain_satisfied_by_a_directly_proposed_class():
    # P108 has produced is declared E12 Production -> E24.
    result = check(_answer(["E12", "E22"], ["P108"]), ONTO)
    assert result["findings"] == []


def test_domain_satisfied_through_an_ancestor():
    # P14 carried out by is declared on E7 Activity; E12 Production is an
    # E7, so proposing E12 satisfies it.
    result = check(_answer(["E12"], ["P14"]), ONTO)
    assert result["findings"] == []


def test_domain_unsatisfied_is_a_finding():
    # P13 destroyed is declared on E6 Destruction, which is not proposed
    # nor an ancestor of anything proposed. This is manswer4a-technical-c1.
    result = check(_answer(["E22", "E79", "E12"], ["P13"]), ONTO)
    assert len(result["findings"]) == 1
    f = result["findings"][0]
    assert f["property"] == "P13"
    assert f["needs"] == "E6"
    assert f["kind"] == "domain"


def test_range_is_never_checked():
    # P4 has time-span ranges on E52. Proposing P4 with no E52 must NOT
    # be a finding -- that was 21 false alarms across the corpus.
    result = check(_answer(["E7"], ["P4"]), ONTO)
    assert result["findings"] == []


def test_extension_property_checked_against_extension_class():
    # CRMsci O3 sampled from is declared on S2 Sample Taking.
    assert check(_answer(["S2"], ["O3"]), ONTO)["findings"] == []
    bad = check(_answer(["E20"], ["O3"]), ONTO)["findings"]
    assert len(bad) == 1 and bad[0]["needs"] == "S2"


def test_inverse_direction_swaps_which_end_must_be_satisfied():
    # P108 has produced is E12 -> E24, so P108i is produced by attaches to
    # the E24 end. E22 Human-Made Object is an E24, so proposing E22
    # satisfies it -- this exercises the inverse path AND the ancestor walk
    # at once. Proposing only the E12 must NOT satisfy the inverse form.
    assert check(_answer(["E22"], ["P108i"]), ONTO)["findings"] == []
    bad = check(_answer(["E12"], ["P108i"]), ONTO)["findings"]
    assert len(bad) == 1 and bad[0]["needs"] == "E24"


def test_dotted_property_with_its_base_proposed_passes():
    assert check(_answer(["E7"], ["P14", "P14.1"]), ONTO)["findings"] == []


def test_dotted_property_without_its_base_is_a_finding():
    result = check(_answer(["E7"], ["P14.1"]), ONTO)
    assert len(result["findings"]) == 1
    f = result["findings"][0]
    assert f["property"] == "P14.1"
    assert f["kind"] == "dotted"
    assert f["needs"] == "P14"


def test_dotted_rule_canonicalizes_the_inverse_form_before_matching():
    """P14i is P14's inverse form. An answer that names P14i has named P14
    just as much as one that writes "P14" plainly -- but proposed_props
    holds raw uppercased strings, so the dotted rule's membership test
    ("is the base in the list the answer proposed") used to compare P14.1's
    base "P14" against the literal string "P14i" and miss. Confirmed by
    hand: ["P14i", "P14.1"] was flagged as missing P14 while ["P14",
    "P14.1"] correctly was not. The class proposed (E39) satisfies P14i's
    own domain check (the inverse direction's declared RANGE), isolating
    this assertion to the dotted rule alone.
    """
    result = check(_answer(["E39"], ["P14i", "P14.1"]), ONTO)
    assert [f for f in result["findings"] if f["kind"] == "dotted"] == []


def test_unresolvable_identifier_is_reported_not_dropped():
    result = check(_answer(["E22"], ["P9999"]), ONTO)
    assert len(result["findings"]) == 1
    assert result["findings"][0]["kind"] == "unknown"


def test_orphan_class_annotates_the_finding_rather_than_suppressing_it():
    """122 of 219 extension classes have no recorded parent (FRBRoo 49,
    CRMdig 22) because FRBRoo is PDF-sourced with no declaration card. Such
    a class satisfies only itself, so a finding involving one may be a
    family-data gap. Annotate; never suppress -- silent suppression is the
    failure class HANDOFF records for the [:20] cap.
    """
    onto = {**ONTO, "classes": dict(ONTO["classes"]),
            "extensions": {**ONTO["extensions"],
                           "Z99": {"id": "Z99", "model": "Fake", "kind": "class"}}}
    result = check(_answer(["Z99"], ["P13"]), onto)
    assert len(result["findings"]) == 1
    assert result["findings"][0]["orphans"] == ["Z99"]


def test_satisfied_classes_includes_ancestors():
    sat = satisfied_classes(ONTO, ["E12"])
    assert "E12" in sat and "E7" in sat and "E1" in sat


def test_resolve_handles_plain_inverse_and_dotted():
    assert resolve(ONTO, "P14") == ("P14", "plain")
    assert resolve(ONTO, "P108i") == ("P108", "inverse")
    assert resolve(ONTO, "P14.1") == ("P14.1", "dotted")
    assert resolve(ONTO, "P9999") == (None, "unknown")


@pytest.mark.skipif(not EVAL_DIR.exists(), reason="data/eval not present")
def test_corpus_baseline_is_pinned():
    """The nine verified findings, and nothing else. Pinned so the count
    cannot drift unnoticed. All four dotted properties in the corpus
    (P107.1 once, P14.1 three times) already name their base, so the dotted
    rule contributes zero -- it is a guard against a future error, not a
    detector of a present one.
    """
    # Scoped to the runs whose findings were hand-verified one by one. A bare
    # manswer*.json glob grows with every new evaluation run, and pinning
    # unverified findings would destroy the point of the pin -- the list is
    # evidence, not a snapshot of whatever the code currently emits. A new run
    # earns its own baseline after its findings are checked by hand; run6, for
    # instance, reports 3 (archives-c3 P170, intangible-c3 P75, and
    # naturalhistory-c3 P200, which is unresolvable because P199/P200/E100 are
    # new in 7.3.2 and data/ontology.json is built from v7.1.3).
    VERIFIED_RUNS = ("manswer-", "manswer2-", "manswer3-", "manswer4a-", "manswer4b-")
    findings = []
    for path in sorted(p for p in EVAL_DIR.glob("manswer*.json")
                       if p.name.startswith(VERIFIED_RUNS)):
        answer = json.loads(path.read_text(encoding="utf-8"))
        for f in check(answer, ONTO)["findings"]:
            findings.append((path.stem, f["property"], f["kind"], f["needs"]))

    assert [f for f in findings if f[2] == "domain"] == [
        ("manswer-archives-c1", "P49", "domain", "E18"),
        ("manswer-archives-c1", "P50", "domain", "E18"),
        ("manswer-built-c1", "P70", "domain", "E31"),
        ("manswer2-naturalhistory-c1", "P112", "domain", "E80"),
        ("manswer2-naturalhistory-c1", "P113", "domain", "E80"),
        ("manswer3-naturalhistory-c2", "P70", "domain", "E31"),
        ("manswer4a-archaeology-c3", "P156", "domain", "E18"),
        ("manswer4a-built-c2", "P53", "domain", "E18"),
        ("manswer4a-technical-c1", "P13", "domain", "E6"),
    ]
    assert [f for f in findings if f[2] == "dotted"] == []
    assert [f for f in findings if f[2] == "unknown"] == []
