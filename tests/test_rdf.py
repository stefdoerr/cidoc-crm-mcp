"""The RDF reader. `validate_link` is format-agnostic, so this only has to
produce the link records the XML reader already produces."""

import json

import pytest

from lib.config import DATA_DIR

TTL = """
@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .
@prefix crmsci: <http://www.cidoc-crm.org/extensions/crmsci/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<urn:obj> a crm:E22_Human-Made_Object ;
    crm:P108i_was_produced_by <urn:prod> ;
    crm:P3_has_note "a note" ;
    rdfs:label "an object" .

<urn:prod> a crm:E12_Production ;
    crm:P14_carried_out_by <urn:person> .

<urn:person> a crm:E21_Person .

<urn:untyped> crm:P3_has_note "no type on this subject" .
"""


def _onto():
    return json.loads((DATA_DIR / "ontology.json").read_text(encoding="utf-8"))


def _links(tmp_path, text, name="m.ttl"):
    from lib.ontology import crm_rdf_links

    f = tmp_path / name
    f.write_text(text, encoding="utf-8")
    return {l["name"]: l for l in crm_rdf_links(f, _onto())}


def test_reader_emits_the_same_record_shape_as_the_xml_reader(tmp_path):
    links = _links(tmp_path, TTL)
    p108 = links["P108i"]
    assert set(p108) >= {"subject", "name", "object", "path", "via_property"}
    assert p108["subject"] == "E22"
    assert p108["object"] == "E12"
    assert p108["via_property"] is None


def test_a_literal_object_has_no_object_class(tmp_path):
    links = _links(tmp_path, TTL)
    assert links["P3"]["object"] is None


def test_a_non_crm_predicate_is_reported_not_dropped(tmp_path):
    """An RDF file legitimately carries rdfs:label. Silently skipping an
    unrecognised predicate is indistinguishable from silently skipping a
    misspelled one."""
    from lib.ontology import crm_rdf_links

    f = tmp_path / "m.ttl"
    f.write_text(TTL, encoding="utf-8")
    names = [l["name"] for l in crm_rdf_links(f, _onto())]
    assert any(n.startswith("rdfs:label") or "label" in n for n in names)


def test_json_ld_parses_the_same_as_turtle(tmp_path):
    from lib.ontology import crm_rdf_links

    doc = {
        "@context": {"crm": "http://www.cidoc-crm.org/cidoc-crm/"},
        "@id": "urn:obj",
        "@type": "crm:E22_Human-Made_Object",
        "crm:P108i_was_produced_by": {
            "@id": "urn:prod", "@type": "crm:E12_Production"},
    }
    f = tmp_path / "m.jsonld"
    f.write_text(json.dumps(doc), encoding="utf-8")
    links = {l["name"]: l for l in crm_rdf_links(f, _onto())}
    assert links["P108i"]["subject"] == "E22"
    assert links["P108i"]["object"] == "E12"


def test_multiple_rdf_type_keeps_every_crm_type(tmp_path):
    """The CRM permits multiple instantiation and the modelling agents used
    it -- one segment typed both E19 and S13. Picking one arbitrarily would
    fail correct models."""
    text = """
@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .
@prefix crmsci: <http://www.cidoc-crm.org/extensions/crmsci/> .
<urn:s> a crm:E19_Physical_Object, crmsci:S13_Sample ;
    crm:P3_has_note "both" .
"""
    links = _links(tmp_path, text)
    assert set(links["P3"]["subject_types"]) == {"E19", "S13"}


def test_a_blank_node_is_reported_as_anonymous(tmp_path):
    """The blank node must be the SUBJECT of an emitted link, not only an
    object -- a fixture where it is only ever an object never exercises the
    `_:` path format at all, and mutating `where()` to drop that prefix left
    every assertion in this test passing regardless."""
    text = """
@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .
<urn:o> a crm:E22_Human-Made_Object ; crm:P108i_was_produced_by [
    a crm:E12_Production ; crm:P14_carried_out_by <urn:person> ] .
<urn:person> a crm:E21_Person .
"""
    links = _links(tmp_path, text)
    assert links["P108i"]["object"] == "E12"
    assert links["P14"]["subject"] == "E12"
    assert links["P14"]["path"].startswith("_:")


def test_an_untyped_subject_yields_no_subject_class(tmp_path):
    from lib.ontology import crm_rdf_links

    f = tmp_path / "m.ttl"
    f.write_text(TTL, encoding="utf-8")
    untyped = [l for l in crm_rdf_links(f, _onto())
               if l["path"].endswith("untyped")]
    assert untyped and untyped[0]["subject"] is None


def _report(tmp_path, text, name="m.ttl"):
    from lib.ontology import crm_rdf_links, validate_document

    f = tmp_path / name
    f.write_text(text, encoding="utf-8")
    return validate_document(_onto(), crm_rdf_links(f, _onto()))


def test_a_non_crm_predicate_gets_its_own_verdict(tmp_path):
    report = _report(tmp_path, TTL)
    v = [f for f in report["findings"] if f["verdict"] == "not_crm"]
    assert v, report["counts"]
    assert any("label" in f["detail"] for f in v)


def test_a_legal_triple_passes(tmp_path):
    report = _report(tmp_path, TTL)
    # TTL carries two P3 links -- one on the typed <urn:obj>, one on the
    # untyped <urn:untyped> -- and this test is about the legal one; the
    # untyped case is `unchecked` and has its own test below. Keying on
    # `name` alone without this filter lets the untyped finding overwrite
    # the typed one, since findings sort by (path, name) and "urn:obj" sorts
    # before "urn:untyped".
    by = {f["name"]: f["verdict"] for f in report["findings"]
          if f["verdict"] != "unchecked"}
    assert by["P108i"] == "ok"
    assert by["P14"] == "ok"
    assert by["P3"] == "ok_literal"


def test_the_wrong_direction_is_illegal(tmp_path):
    """P108 is E12 -> E24. An E22 cannot be its subject; P108i can."""
    bad = """
@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .
<urn:a> a crm:E22_Human-Made_Object ; crm:P108_has_produced <urn:b> .
<urn:b> a crm:E12_Production .
"""
    report = _report(tmp_path, bad)
    assert report["counts"].get("illegal") == 1


def test_a_link_passes_if_any_rdf_type_satisfies_the_domain(tmp_path):
    """O19 is declared on S19 Encounter Event. A subject typed both E7 and
    S19 satisfies it through S19, and the detail says which."""
    text = """
@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .
@prefix crmsci: <http://www.cidoc-crm.org/extensions/crmsci/> .
<urn:find> a crm:E7_Activity, crmsci:S19_Encounter_Event ;
    crmsci:O19_encountered_object <urn:thing> .
<urn:thing> a crm:E18_Physical_Thing .
"""
    report = _report(tmp_path, text)
    ok = [f for f in report["findings"] if f["name"] == "O19"]
    assert ok and ok[0]["verdict"] == "ok"
    assert "S19" in ok[0]["detail"]


def test_an_untyped_subject_is_unchecked_not_passed(tmp_path):
    report = _report(tmp_path, TTL)
    assert report["counts"].get("unchecked", 0) >= 1


XML_MODEL = "models/crm_marquis_yi.xml"


@pytest.mark.skipif(not (DATA_DIR.parent / XML_MODEL).exists(),
                    reason="the finished model is not in the working tree")
def test_both_readers_reach_the_same_verdicts(tmp_path):
    """The proof the checker is format-agnostic rather than two
    implementations agreeing by luck: express one finished model's links as
    Turtle and confirm every verdict matches.

    Scope, stated plainly rather than left implicit: `crm_marquis_yi.xml`'s
    97 checkable class-to-class links contain zero that are illegal, and
    zero with a name outside the model -- `validate --xml` on the file
    reports `{"ok": 97, "ok_literal": 28, "attached_to_property": 23}`, all
    at the property-of-property nesting the XML format cannot write, none
    of which round-trips here (see the `via_property` filter above). So this
    test can only show that RDF does not spuriously reject something the
    XML reader accepts -- it has no case in its universe where the XML
    reader calls something broken, and therefore cannot show RDF failing to
    flag a broken link the same way. The test below this one closes that
    gap: a small hand-built fixture carrying two actual defects, read by
    both readers, verdicts compared directly."""
    from lib.ontology import (_property_candidates, crm_example_links,
                              crm_rdf_links, validate_document)

    onto = _onto()
    xml_links = [l for l in crm_example_links(DATA_DIR.parent / XML_MODEL)
                 if l["subject"] and l["object"] and not l.get("via_property")]
    assert xml_links, "the model produced no checkable class-to-class links"

    lines = ["@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> ."]
    expected = []
    for n, link in enumerate(xml_links):
        cands = _property_candidates(onto, link["name"])
        if len(cands) != 1:
            continue            # ambiguous by label; the URI form has no
        pid, inverse = cands[0]  # equivalent, so it is not a round-trip case
        s, o = f"<urn:s{n}>", f"<urn:o{n}>"
        lines.append(f"{s} a crm:{link['subject']} ; "
                     f"crm:{pid}{'i' if inverse else ''} {o} .")
        lines.append(f"{o} a crm:{link['object']} .")
        expected.append((link["subject"], pid, inverse, link["object"]))
    assert expected, "nothing unambiguous to round-trip"

    ttl = tmp_path / "round.ttl"
    ttl.write_text("\n".join(lines), encoding="utf-8")
    report = validate_document(onto, crm_rdf_links(ttl, onto))

    # `crm_marquis_yi.xml` validates clean at the class-to-class-link level
    # this test operates on -- `validate --xml` on the whole file exits 1
    # (23 attached_to_property findings, a nesting the XML format cannot
    # avoid), but none of that 23 is a class-link and none of it round-trips
    # here, so the RDF expression of the class-links alone should be clean
    # too.
    assert report["counts"].get("illegal", 0) == 0, report["counts"]
    assert report["counts"].get("unknown_name", 0) == 0, report["counts"]
    assert report["counts"].get("not_crm", 0) == 0, report["counts"]
    assert report["counts"].get("ok", 0) == len(expected), report["counts"]


# `crm_marquis_yi.xml` has no illegal or unresolvable class-link in it, so
# the round-trip test above -- however faithfully it expresses the model --
# can only ever show RDF agreeing with XML on links that PASS. It has no
# way to show the readers agreeing (or disagreeing) on a link that FAILS,
# because its universe of outcomes never contained a failure. This fixture
# supplies the missing half: one small document, hand-built to carry two
# actual defects, written out in both formats and read by both readers, so
# the failing verdicts can be compared directly rather than assumed to
# track each other because the passing ones did.
_BROKEN_XML = """<?xml version="1.0"?>
<CRMset>
<CRM_Entity>x
  <in_class>E22: Human-Made Object</in_class>
  <has_produced>y
    <in_class>E12: Production</in_class>
  </has_produced>
  <changed_ownership_by>z
    <in_class>E8: Acquisition</in_class>
  </changed_ownership_by>
</CRM_Entity>
</CRMset>
"""

# Same two relationships, same classes, addressed by URI instead of by
# element name. `has_produced` becomes `P108_has_produced` (the correct
# forward form -- P108's domain is E12, range E24, so an E22 subject is
# wrong either way it is spelled); `changed_ownership_by` is not translated
# at all, because there is nothing to translate it TO -- it is not a CRM
# property under any spelling, which is the entire point of the fixture.
_BROKEN_TTL = """
@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .
<urn:x> a crm:E22_Human-Made_Object ;
    crm:P108_has_produced <urn:y> ;
    crm:changed_ownership_by <urn:z> .
<urn:y> a crm:E12_Production .
<urn:z> a crm:E8_Acquisition .
"""


def test_readers_agree_on_a_reversed_link_and_on_an_unmodeled_property_name(
        tmp_path):
    """The comparison the round-trip test above cannot make: two links that
    both readers must call broken, checked verdict-for-verdict rather than
    each reader in isolation.

    `has_produced` / `P108_has_produced` is the wrong direction (P108's
    domain is E12 Production, range E24; an E22 Human-Made Object cannot be
    its subject) and BOTH readers call it `illegal`, with the identical
    domain/range explanation -- genuine agreement, not two implementations
    that happen to use the same word.

    `changed_ownership_by` is not a CRM property under any spelling -- it is
    the real error from the published Clayton example, also covered (via
    the XML reader alone) by
    `test_document_check_catches_a_name_that_is_not_a_property` in
    test_ontology.py. When this test was first written, the two readers
    DIVERGED here: XML called it `unknown_name`, RDF called it `not_crm`,
    because `validate_document`'s `not_crm` guard fired for every
    unresolved RDF predicate regardless of namespace -- `crm_rdf_links`
    always sets `predicate_uri`, so that guard always intercepted the link
    before `unknown_name`'s own check (`"no property matches"`) ever ran.
    `not_crm` does not fail `--rdf`'s exit code where `unknown_name` DOES
    fail `--xml`'s, so the practical effect was real: this exact mistake
    exited 1 as XML and 0 as RDF.

    Fixed in `validate_document` by teaching that guard to check NAMESPACE:
    a predicate whose namespace the model owns (CRM_NAMESPACE, or an
    extension's own, both read from `data/ontology.json`'s `uri` fields --
    see `_owned_namespaces`) is asserting, by its own URI, to be one of that
    model's terms, so failing to resolve there is `unknown_name`, same as
    XML; a predicate in a namespace the model does not own -- rdfs, Dublin
    Core, an application's own vocabulary -- stays `not_crm`, because a CRM
    validator never had standing to reject those. Now both readers agree,
    exactly, on both relationships -- see
    `test_unresolved_predicates_are_sorted_by_namespace_not_by_name` below
    for the namespace rule on its own, and
    `test_the_cli_exits_the_same_way_on_the_same_misspelling_in_both_formats`
    for the user-visible exit-code consequence this closes.
    """
    from lib.ontology import crm_example_links, crm_rdf_links, validate_document

    onto = _onto()

    xml_path = tmp_path / "broken.xml"
    xml_path.write_text(_BROKEN_XML, encoding="utf-8")
    xml_report = validate_document(onto, crm_example_links(xml_path))
    xml_by_name = {f["name"]: f for f in xml_report["findings"]}

    ttl_path = tmp_path / "broken.ttl"
    ttl_path.write_text(_BROKEN_TTL, encoding="utf-8")
    rdf_report = validate_document(onto, crm_rdf_links(ttl_path, onto))
    # the RDF reader names a resolved link by its property id, not the
    # element/label text, so "has_produced" and "P108" are the same link
    # under the two readers' own naming, and the unresolved predicate is
    # named by its full URI rather than the local text that was written
    rdf_by_name = {f["name"]: f for f in rdf_report["findings"]}
    rdf_by_name.update({f["name"].rsplit("/", 1)[-1]: f
                        for f in rdf_report["findings"]})

    # Neither reader may PASS either link -- the weakest form of agreement,
    # and the one the review first asked to see checked mechanically.
    for f in (xml_by_name["has_produced"], xml_by_name["changed_ownership_by"],
             rdf_by_name["P108"], rdf_by_name["changed_ownership_by"]):
        assert f["verdict"] not in ("ok", "ok_literal"), f

    # The reversed-direction link: genuine, exact agreement -- true from the
    # first version of this test, unaffected by the namespace fix.
    assert xml_by_name["has_produced"]["verdict"] == "illegal"
    assert rdf_by_name["P108"]["verdict"] == "illegal"
    assert (xml_by_name["has_produced"]["detail"]
           == rdf_by_name["P108"]["detail"]), \
        "same domain/range reasoning was expected to produce the same text"

    # The unmodeled-name link: was a confirmed divergence, now a confirmed
    # agreement. Pinned to the exact current verdicts, not loosened to
    # "both non-ok", so that either reader changing this behaviour is a
    # deliberate decision and not a silent side effect of something else.
    assert xml_by_name["changed_ownership_by"]["verdict"] == "unknown_name"
    assert rdf_by_name["changed_ownership_by"]["verdict"] == "unknown_name"


# The rule fix round 2 implemented: NAMESPACE, not resemblance. A predicate
# whose namespace the model owns (CRM_NAMESPACE or one of the family
# extensions' own, both read from data/ontology.json's `uri` fields -- see
# `_owned_namespaces` in lib/ontology.py) is asserting, by its own URI, to
# be one of that model's terms; failing to resolve there is `unknown_name`.
# A predicate in any other namespace is legitimately outside the CRM's
# authority and stays `not_crm`. `lrmoo:` is included deliberately, not
# just a cidoc-crm.org case: LRMoo is a family extension at
# http://iflastandards.info/ns/lrm/lrmoo/, so a test that only exercised
# CRMbase would not catch a derivation that quietly missed the extensions
# (say, one hardcoded to the cidoc-crm.org hostname).
_NAMESPACE_CASES = [
    pytest.param("crm:was_produced_by", "unknown_name",
                id="real_label_missing_its_P108i_prefix"),
    pytest.param("crm:P999_not_a_property", "unknown_name",
                id="plausible_but_nonexistent_identifier"),
    pytest.param("lrmoo:R1_gaga", "unknown_name",
                id="misspelling_in_an_extension_namespace"),
    pytest.param("rdfs:label", "not_crm",
                id="real_predicate_the_crm_does_not_own"),
    pytest.param("ex:completely_unrelated", "not_crm",
                id="application_vocabulary_the_crm_has_never_heard_of"),
]


@pytest.mark.parametrize("predicate,expected", _NAMESPACE_CASES)
def test_unresolved_predicates_are_sorted_by_namespace_not_by_name(
        tmp_path, predicate, expected):
    """No fuzzy matching, no edit distance, no guessing what a misspelling
    was reaching for -- only "whose namespace is this." Each case here is a
    predicate `resolve_uri` cannot place, differing only in which namespace
    it claims."""
    from lib.ontology import crm_rdf_links, validate_document

    ttl = f"""
@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .
@prefix lrmoo: <http://iflastandards.info/ns/lrm/lrmoo/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex: <http://example.org/> .
<urn:a> a crm:E22_Human-Made_Object ; {predicate} <urn:b> .
<urn:b> a crm:E12_Production .
"""
    f = tmp_path / "ns.ttl"
    f.write_text(ttl, encoding="utf-8")
    report = validate_document(_onto(), crm_rdf_links(f, _onto()))
    assert report["counts"] == {expected: 1}, report["counts"]
    # not_crm and unknown_name alike report the predicate; neither is a
    # silent drop, whichever bucket a given namespace lands it in
    assert report["findings"][0]["detail"]


def test_the_cli_exits_the_same_way_on_the_same_misspelling_in_both_formats(
        tmp_path):
    """The user-visible form of the bug this fix round closes. Before it,
    `validate --xml` already exited 1 on `changed_ownership_by` (the real
    Clayton example error) while `validate --rdf` exited 0 on the identical
    mistake, because `not_crm` never fails and the RDF reader could not
    reach `unknown_name` for a predicate in a namespace it owns. Runs the
    actual CLI as a user would type it, in a subprocess, rather than only
    the report dict `validate_document` returns -- the exit code is
    assembled in search.py's argument handling, not in lib/ontology.py, and
    a test that never runs search.py cannot see that assembly regress."""
    import subprocess
    import sys

    from lib.config import PROJECT_ROOT

    xml_path = tmp_path / "m.xml"
    xml_path.write_text("""<?xml version="1.0"?>
<CRMset>
<CRM_Entity>x
  <in_class>E22: Human-Made Object</in_class>
  <changed_ownership_by>z
    <in_class>E8: Acquisition</in_class>
  </changed_ownership_by>
</CRM_Entity>
</CRMset>
""", encoding="utf-8")
    ttl_path = tmp_path / "m.ttl"
    ttl_path.write_text("""
@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .
<urn:x> a crm:E22_Human-Made_Object ; crm:changed_ownership_by <urn:z> .
<urn:z> a crm:E8_Acquisition .
""", encoding="utf-8")

    xml_run = subprocess.run(
        [sys.executable, "search.py", "validate", "--xml", str(xml_path)],
        cwd=PROJECT_ROOT, capture_output=True, text=True)
    rdf_run = subprocess.run(
        [sys.executable, "search.py", "validate", "--rdf", str(ttl_path)],
        cwd=PROJECT_ROOT, capture_output=True, text=True)

    assert xml_run.returncode == 1, xml_run.stdout + xml_run.stderr
    assert rdf_run.returncode == 1, rdf_run.stdout + rdf_run.stderr
    assert "unknown_name" in xml_run.stdout
    assert "unknown_name" in rdf_run.stdout


def test_completeness_is_not_a_failure_and_not_shown_unasked(tmp_path):
    # The specification says quantifiers are "for semantic clarification
    # only" and that all properties should be implemented as optional. A
    # missing necessary property therefore cannot fail the check, and must
    # not crowd out the findings that do.
    import subprocess
    import sys

    from lib.config import PROJECT_ROOT

    ttl = ('@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .\n'
           '<urn:p> a crm:E12_Production ; crm:P4_has_time-span <urn:t> .\n'
           '<urn:t> a crm:E52_Time-Span .\n')
    f = tmp_path / "m.ttl"
    f.write_text(ttl, encoding="utf-8")

    plain = subprocess.run([sys.executable, "search.py", "validate", "--rdf",
                            str(f)], cwd=PROJECT_ROOT, capture_output=True,
                           text=True)
    assert plain.returncode == 0
    assert "P108" not in plain.stdout

    asked = subprocess.run([sys.executable, "search.py", "validate", "--rdf",
                            str(f), "--completeness"], cwd=PROJECT_ROOT,
                           capture_output=True, text=True)
    assert asked.returncode == 0          # still not a failure
    assert "P108" in asked.stdout


# ---- owl:inverseOf claims ---------------------------------------------------
#
# An RDF document can ASSERT what a property's inverse is
# (P108i_was_produced_by owl:inverseOf P108_has_produced). Nothing read those
# assertions before crm_inverse_claims existed, so a document could state a
# flatly false inverse -- P108i inverseOf P14_carried_out_by -- and pass every
# other check. The rule needs no judgement: correct iff both sides resolve to
# the same identifier with opposite direction flags, exactly what resolve_uri
# already returns.


def _claims(tmp_path, text, name="m.ttl"):
    from lib.ontology import crm_inverse_claims

    f = tmp_path / name
    f.write_text(text, encoding="utf-8")
    return crm_inverse_claims(f, _onto())


_INV = """
@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .
@prefix crmsci: <http://www.cidoc-crm.org/extensions/crmsci/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix ex: <http://example.org/> .

crm:P108i_was_produced_by owl:inverseOf crm:P108_has_produced .
crmsci:O19i_was_object_encountered_through owl:inverseOf crmsci:O19_encountered_object .
crm:P108i_was_produced_by owl:inverseOf crm:P14_carried_out_by .
crm:P108_has_produced owl:inverseOf crm:P108_has_produced .
crm:E22_Human-Made_Object owl:inverseOf crm:P108_has_produced .
ex:madeBy owl:inverseOf crm:P108_has_produced .
ex:a owl:inverseOf ex:b .
"""


def test_a_true_inverse_claim_is_ok(tmp_path):
    by = {(c["subject"], c["object"]): c for c in _claims(tmp_path, _INV)}
    good = by[("http://www.cidoc-crm.org/cidoc-crm/P108i_was_produced_by",
               "http://www.cidoc-crm.org/cidoc-crm/P108_has_produced")]
    assert good["verdict"] == "ok"


def test_a_true_inverse_claim_is_ok_for_a_family_property(tmp_path):
    # The family entries carry ONE combined label -- "encountered object (was
    # object encountered through)" -- which is what broke the first draft of
    # the RDF reader. An inverse claim over a family property exercises the
    # same seam from the other side.
    by = {(c["subject"], c["object"]): c for c in _claims(tmp_path, _INV)}
    base = "http://www.cidoc-crm.org/extensions/crmsci/"
    good = by[(base + "O19i_was_object_encountered_through",
               base + "O19_encountered_object")]
    assert good["verdict"] == "ok"


def test_two_different_properties_are_contradicted(tmp_path):
    by = {(c["subject"], c["object"]): c for c in _claims(tmp_path, _INV)}
    bad = by[("http://www.cidoc-crm.org/cidoc-crm/P108i_was_produced_by",
              "http://www.cidoc-crm.org/cidoc-crm/P14_carried_out_by")]
    assert bad["verdict"] == "contradicted"
    assert "P108" in bad["detail"] and "P14" in bad["detail"]


def test_the_same_direction_twice_is_contradicted(tmp_path):
    # P108 inverseOf P108 resolves to one identifier with the SAME direction
    # flag on both sides. Same id is not enough; the directions must differ.
    by = {(c["subject"], c["object"]): c for c in _claims(tmp_path, _INV)}
    bad = by[("http://www.cidoc-crm.org/cidoc-crm/P108_has_produced",
              "http://www.cidoc-crm.org/cidoc-crm/P108_has_produced")]
    assert bad["verdict"] == "contradicted"


def test_a_class_has_no_inverse(tmp_path):
    by = {(c["subject"], c["object"]): c for c in _claims(tmp_path, _INV)}
    bad = by[("http://www.cidoc-crm.org/cidoc-crm/E22_Human-Made_Object",
              "http://www.cidoc-crm.org/cidoc-crm/P108_has_produced")]
    assert bad["verdict"] == "not_invertible"
    assert "E22" in bad["detail"]


def test_a_foreign_predicate_against_a_crm_one_is_a_bridge(tmp_path):
    by = {(c["subject"], c["object"]): c for c in _claims(tmp_path, _INV)}
    claim = by[("http://example.org/madeBy",
                "http://www.cidoc-crm.org/cidoc-crm/P108_has_produced")]
    assert claim["verdict"] == "bridge"


def test_two_foreign_predicates_are_nobodys_business(tmp_path):
    by = {(c["subject"], c["object"]): c for c in _claims(tmp_path, _INV)}
    assert by[("http://example.org/a", "http://example.org/b")]["verdict"] \
        == "foreign"


def test_inverse_claims_are_not_also_reported_as_links(tmp_path):
    # An owl:inverseOf triple is a statement ABOUT the vocabulary, not an
    # instance link. Left in the link stream it lands as `not_crm` on the
    # predicate plus `unchecked` on an untyped subject -- two findings that
    # tell the reader nothing, for a triple that IS checked, elsewhere.
    from lib.ontology import crm_rdf_links

    f = tmp_path / "m.ttl"
    f.write_text(_INV, encoding="utf-8")
    assert crm_rdf_links(f, _onto()) == []


def test_a_document_with_no_inverse_claims_yields_none(tmp_path):
    assert _claims(tmp_path, TTL) == []


# ---- fix round 1: `not_invertible` has two distinct causes -----------------
#
# The verdict table names two things that have no inverse -- "a CRM class,
# or a property-of-property" -- but the first draft's detail text named both
# causes on every not_invertible claim regardless of which one actually
# applied ("a class and a property-of-property both have none"). A class
# named where a property belongs is a category error; P14.1 is a subtler
# mistake, because a property-of-property's domain is the relationship it
# qualifies, not a class, so an inverse (a property read the other
# direction) is not merely absent for it, the concept does not apply at all
# -- the same fact `validate_link` reports as "not_a_class_link: its domain
# is the property P14, not a class". This fixture is separate from `_INV`
# (untouched, verbatim from the brief) so as not to alter a fixture already
# pinned by other tests.

_INV_POP = """
@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .

crm:P14.1 owl:inverseOf crm:P14_carried_out_by .
crm:E22_Human-Made_Object owl:inverseOf crm:P14.1 .
"""


def test_a_property_of_property_has_no_inverse(tmp_path):
    by = {(c["subject"], c["object"]): c for c in _claims(tmp_path, _INV_POP)}
    bad = by[("http://www.cidoc-crm.org/cidoc-crm/P14.1",
              "http://www.cidoc-crm.org/cidoc-crm/P14_carried_out_by")]
    assert bad["verdict"] == "not_invertible"
    assert "P14.1" in bad["detail"]
    # The property-of-property's OWN domain (the P14 relationship it
    # qualifies) is why it has no inverse -- not "it is a class", which is a
    # different mistake with a different fix.
    assert "not a class" in bad["detail"]
    assert "property-of-property" in bad["detail"]
    assert "P14" in bad["detail"]


def test_not_invertible_names_each_sides_own_cause(tmp_path):
    # One claim, one class side (E22) and one property-of-property side
    # (P14.1) -- the case the original message collapsed by naming both
    # possible causes on every claim. The fix must say which cause applies
    # to which identifier, not repeat one generic sentence.
    by = {(c["subject"], c["object"]): c for c in _claims(tmp_path, _INV_POP)}
    bad = by[("http://www.cidoc-crm.org/cidoc-crm/E22_Human-Made_Object",
              "http://www.cidoc-crm.org/cidoc-crm/P14.1")]
    assert bad["verdict"] == "not_invertible"
    assert "E22" in bad["detail"] and "P14.1" in bad["detail"]
    # The two per-identifier clauses must actually differ -- proof the
    # detail is not one flat sentence naming both categories regardless of
    # which side hit which one.
    e22_clause = next(c for c in bad["detail"].split("; ") if "E22" in c)
    pop_clause = next(c for c in bad["detail"].split("; ") if "P14.1" in c)
    assert e22_clause != pop_clause
    assert "class" in e22_clause.lower()
    assert "property-of-property" in pop_clause.lower() or "P14" in pop_clause


# ---- fix round 1: a document with ONLY owl:inverseOf claims -----------------
#
# crm_rdf_links now silently drops every owl:inverseOf triple, and that is
# only legitimate because crm_inverse_claims checks the same triples and the
# CLI reports both. A document whose ONLY content is owl:inverseOf claims --
# no instance links at all -- is the case where a broken pairing would be a
# TOTAL, invisible drop: crm_rdf_links alone would report zero links and zero
# problems on a file that asserts something flatly false about the model.
# This pins the CLI path end to end, the way a reader would actually run it,
# rather than only the two library functions in isolation.


def test_the_cli_reports_a_claims_only_document_with_no_instance_links(tmp_path):
    import subprocess
    import sys

    from lib.config import PROJECT_ROOT

    ttl_path = tmp_path / "claims_only.ttl"
    ttl_path.write_text("""
@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .

crm:P108i_was_produced_by owl:inverseOf crm:P14_carried_out_by .
""", encoding="utf-8")

    run = subprocess.run(
        [sys.executable, "search.py", "validate", "--rdf", str(ttl_path)],
        cwd=PROJECT_ROOT, capture_output=True, text=True)

    # The false claim must be visible and must fail the check -- a silent
    # drop here would print "0 links checked" and exit 0, indistinguishable
    # from an empty, harmless file.
    assert run.returncode == 1, run.stdout + run.stderr
    assert "0 links checked" in run.stdout
    assert "CONTRADICTED" in run.stdout
    assert "P108i_was_produced_by" in run.stdout
    assert "P14_carried_out_by" in run.stdout

    json_run = subprocess.run(
        [sys.executable, "search.py", "validate", "--rdf", str(ttl_path), "--json"],
        cwd=PROJECT_ROOT, capture_output=True, text=True)
    report = json.loads(json_run.stdout)
    assert report["findings"] == []          # the claim triple is not a link
    assert len(report["inverse_claims"]) == 1
    assert report["inverse_claims"][0]["verdict"] == "contradicted"


# ---- Step 6a: structural elements are an XML-format concept ----------------
#
# validate_document unconditionally fills "structural_elements_skipped" with
# the four XML example-format element names (CRM_Entity/in_class/unit/value)
# regardless of which reader produced the links it is validating -- confirmed
# by hand: `validate --rdf` on a clean Turtle file, before this fix, printed
# `structural_elements_skipped": ["CRM_Entity", "in_class", "unit", "value"]`
# in its own --json output, for a document that has none of those elements at
# all. format_document_validation is not allowed to fix that by asking
# validate_document for the truth (Task 5's brief forbids editing that
# function), so search.py's own --rdf branch must blank the key itself --
# exactly the way it already blanks `class_labels` for the same reason -- and
# the formatter must treat an empty list the same as an absent key.


def test_structural_elements_line_is_absent_from_an_rdf_report_but_present_on_an_xml_one(
        tmp_path):
    from lib.ontology import crm_example_links, crm_rdf_links, validate_document
    from search import format_document_validation

    onto = _onto()

    ttl_path = tmp_path / "clean.ttl"
    ttl_path.write_text(TTL, encoding="utf-8")
    rdf_report = validate_document(onto, crm_rdf_links(ttl_path, onto))
    # what search.py's own --rdf branch does to this key, verified below by
    # running the actual CLI as a subprocess
    rdf_report["structural_elements_skipped"] = []
    assert "structural elements skipped" not in format_document_validation(rdf_report)

    xml_path = tmp_path / "clean.xml"
    xml_path.write_text("""<?xml version="1.0"?>
<CRMset>
<CRM_Entity>x
  <in_class>E22: Human-Made Object</in_class>
  <has_produced>y
    <in_class>E12: Production</in_class>
  </has_produced>
</CRM_Entity>
</CRMset>
""", encoding="utf-8")
    xml_report = validate_document(onto, crm_example_links(xml_path))
    assert "structural elements skipped" in format_document_validation(xml_report)


def test_the_cli_omits_structural_elements_for_rdf_and_keeps_it_for_xml(tmp_path):
    """The wiring, not just the formatter: runs the real CLI, the way Step
    6a's hand check does, so a regression in search.py's own --rdf branch
    (forgetting to blank the key) would be caught here even if the formatter
    test above still passed."""
    import subprocess
    import sys

    from lib.config import PROJECT_ROOT

    ttl_path = tmp_path / "clean.ttl"
    ttl_path.write_text(TTL, encoding="utf-8")
    rdf_run = subprocess.run(
        [sys.executable, "search.py", "validate", "--rdf", str(ttl_path)],
        cwd=PROJECT_ROOT, capture_output=True, text=True)
    assert "structural elements skipped" not in rdf_run.stdout, rdf_run.stdout

    xml_path = tmp_path / "clean.xml"
    xml_path.write_text("""<?xml version="1.0"?>
<CRMset>
<CRM_Entity>x
  <in_class>E22: Human-Made Object</in_class>
  <has_produced>y
    <in_class>E12: Production</in_class>
  </has_produced>
</CRM_Entity>
</CRMset>
""", encoding="utf-8")
    xml_run = subprocess.run(
        [sys.executable, "search.py", "validate", "--xml", str(xml_path)],
        cwd=PROJECT_ROOT, capture_output=True, text=True)
    assert "structural elements skipped" in xml_run.stdout, xml_run.stdout


# ---- Task 6: honouring a checked owl:inverseOf bridge -----------------------
#
# crm_inverse_claims (Task 5) reads and verifies owl:inverseOf triples but
# does nothing with the verdicts -- a bridge claim, proven true, still left
# its predicate landing as `not_crm` and unchecked. This is the payoff: a
# `bridge` claim tells the reader how the document means its own predicate,
# and honouring it gets that predicate the same domain/range check every CRM
# property gets. Only `bridge` -- a `contradicted` claim is false and
# honouring an unchecked claim would let a document define its way out of
# any error by declaring one.
#
# The two bridges below invert in opposite directions on purpose. P108 has
# domain E12 Production and range E24 Physical Human-Made Thing, so:
#   * `ex:madeBy inverseOf P108_has_produced` (a forward name) makes
#     `ex:madeBy` mean P108 INVERSE -- domain E24, range E12. E22 -> E12 is
#     legal because an E22 is an E24.
#   * `ex:produced inverseOf P108i_was_produced_by` (an inverse name) makes
#     `ex:produced` mean P108 FORWARD -- domain E12, range E24. E12 -> E22 is
#     legal for the same reason.

_BRIDGE = """
@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix ex: <http://example.org/> .

ex:madeBy owl:inverseOf crm:P108_has_produced .
ex:produced owl:inverseOf crm:P108i_was_produced_by .

<urn:obj> a crm:E22_Human-Made_Object ;
    ex:madeBy <urn:prod> .

<urn:prod> a crm:E12_Production ;
    ex:produced <urn:other> .

<urn:other> a crm:E22_Human-Made_Object .
"""


def test_a_bridged_predicate_is_checked_like_a_crm_one(tmp_path):
    from lib.ontology import (crm_inverse_claims, crm_rdf_links,
                              validate_document)

    f = tmp_path / "m.ttl"
    f.write_text(_BRIDGE, encoding="utf-8")
    onto = _onto()
    claims = crm_inverse_claims(f, onto)
    links = crm_rdf_links(f, onto, aliases=claims)
    report = validate_document(onto, links)
    # Keyed on `predicate_uri`, not `name`: honouring the bridge is what lets
    # `name` become the resolved CRM identifier (P108i / P108) instead of
    # `not_crm`'s raw-URI fallback -- that's the whole point (see Task 6's
    # brief and the `detail` field below), and it is also what the hand
    # check in the report is told to look for ("the finding names the CRM
    # property it was bridged to"). `predicate_uri` is untouched by aliasing
    # and still holds the document's own predicate, which is what these
    # assertions need to look a specific link up by.
    by = {l["predicate_uri"]: l for l in report["findings"]}

    assert by["http://example.org/madeBy"]["verdict"] == "ok"
    assert by["http://example.org/madeBy"]["name"] == "P108i"
    assert by["http://example.org/produced"]["verdict"] == "ok"
    assert by["http://example.org/produced"]["name"] == "P108"
    assert report["counts"].get("not_crm", 0) == 0


def test_a_bridged_predicate_used_backwards_is_illegal(tmp_path):
    # Fix round 1: the original version of this test retyped urn:prod to
    # E52_Time-Span and asserted `illegal == 2`, but that fails on the
    # SUBJECT domain of both links regardless of which way the direction
    # inversion runs -- flip `not inverse` to `inverse` in the alias_map
    # construction and this fixture still reports 2 illegal, so it was
    # coverage in name only.
    #
    # This version is built so the CORRECT inversion and the WRONG one give
    # DIFFERENT verdicts, so the assertion can only pass if the inversion is
    # actually right. `ex:madeBy inverseOf P108_has_produced` (a forward
    # name) means P108 INVERSE: domain E24 Physical Human-Made Thing, range
    # E12 Production (data/ontology.json: P108 domain=E12, range=E24). E12's
    # own parents are E11 and E63 -- not E24, and E24's are E18 and E71 --
    # not E12, confirmed by reading data/ontology.json directly rather than
    # assuming it, so the two classes below cannot pass by ancestry the
    # wrong way could not tell apart from the right one:
    #   * correct (P108 inverse): needs subject E24, object E12. An E12
    #     Production subject is not an E24, so `ex:madeBy` from an E12 to an
    #     E22 is ILLEGAL.
    #   * backwards (P108 forward): needs subject E12, object E24. The same
    #     triple's subject IS an E12 (exact) and its object E22 IS an E24
    #     (E22's parents are E19 and E24), so it would be LEGAL.
    # A mutation that drops the inversion therefore flips this fixture's
    # verdict from illegal to ok, where the old fixture's did not move.
    from lib.ontology import (crm_inverse_claims, crm_rdf_links,
                              validate_document)

    text = """
@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix ex: <http://example.org/> .

ex:madeBy owl:inverseOf crm:P108_has_produced .

<urn:prod> a crm:E12_Production ;
    ex:madeBy <urn:obj> .

<urn:obj> a crm:E22_Human-Made_Object .
"""
    f = tmp_path / "m.ttl"
    f.write_text(text, encoding="utf-8")
    onto = _onto()
    links = crm_rdf_links(f, onto, aliases=crm_inverse_claims(f, onto))
    report = validate_document(onto, links)
    assert report["counts"].get("illegal", 0) == 1
    assert report["counts"].get("ok", 0) == 0


def test_links_without_aliases_are_still_not_crm(tmp_path):
    # The default must leave every existing caller exactly as it was: without
    # the aliases the same two predicates are foreign, exactly as before.
    from lib.ontology import crm_rdf_links, validate_document

    f = tmp_path / "m.ttl"
    f.write_text(_BRIDGE, encoding="utf-8")
    onto = _onto()
    report = validate_document(onto, crm_rdf_links(f, onto))
    assert report["counts"].get("not_crm", 0) == 2
    assert report["counts"].get("ok", 0) == 0


def test_a_contradicted_claim_beside_a_bridge_disturbs_nothing(tmp_path):
    # Only `bridge` claims are honoured. A document carrying a false claim
    # must still get its legitimate bridge checked, and the false claim must
    # not be quietly swallowed by the alias pass -- it is a reported failure.
    from lib.ontology import (crm_inverse_claims, crm_rdf_links,
                              validate_document)

    text = _BRIDGE + ("crm:P108i_was_produced_by owl:inverseOf "
                      "crm:P14_carried_out_by .\n")
    f = tmp_path / "m.ttl"
    f.write_text(text, encoding="utf-8")
    onto = _onto()
    claims = crm_inverse_claims(f, onto)
    assert any(c["verdict"] == "contradicted" for c in claims)
    report = validate_document(onto, crm_rdf_links(f, onto, aliases=claims))
    # See the comment in test_a_bridged_predicate_is_checked_like_a_crm_one:
    # `predicate_uri`, not `name`, is the field that still holds the
    # document's own predicate once the bridge has resolved `name` to P108i.
    by = {l["predicate_uri"]: l for l in report["findings"]}
    assert by["http://example.org/madeBy"]["verdict"] == "ok"
    assert report["counts"].get("illegal", 0) == 0


# ---- Fix round 1: a bridged finding must name what the document wrote -----
#
# `name` on a bridged finding is the resolved CRM property (P108i), not
# `ex:madeBy` -- validate_document can only check a property it can look up
# by name, and that lookup IS the resolved id, so `name` has no other honest
# value to hold. But a reader with the document open cannot find "P108i"
# anywhere in it to fix. `predicate_uri` already carries the raw predicate on
# every finding; format_document_validation now surfaces it for exactly the
# case where it differs from an ordinary CRM URI's own naming convention
# (see the comment beside the fix in search.py), and stays silent on an
# ordinary CRM finding, where printing the full URI beside the short id on
# every single line would be pure clutter.


def test_a_bridged_illegal_finding_names_what_the_document_wrote(tmp_path):
    from lib.ontology import (crm_inverse_claims, crm_rdf_links,
                              validate_document)
    from search import format_document_validation

    f = tmp_path / "m.ttl"
    f.write_text(_BRIDGE.replace("<urn:prod> a crm:E12_Production",
                                 "<urn:prod> a crm:E52_Time-Span"),
                 encoding="utf-8")
    onto = _onto()
    claims = crm_inverse_claims(f, onto)
    report = validate_document(onto, crm_rdf_links(f, onto, aliases=claims))
    report["class_labels"] = []
    report["structural_elements_skipped"] = []
    report["inverse_claims"] = claims
    text = format_document_validation(report)

    # The raw string a reader would actually search their file for.
    assert "http://example.org/madeBy" in text
    # And the resolved CRM property it was checked as, still shown as the
    # verdict's own header -- both present, neither replacing the other.
    assert "P108i" in text


# ---- the defect report: the standard way to write a date -------------------
#
# `data/ontology.json` is parsed from the presentation XML alone, which has
# no entry for P81a/P81b/P82a/P82b (a fuzzy date boundary) or P90a/P90b (a
# fuzzy dimension bound) -- Task 1's `add_rdfs_additions` exists to fold
# those in from the normative RDFS, and this task wires it into the build.
# Until `data/ontology.json` is rebuilt with that call in place, these two
# tests fail: the point of this file is to prove they stop failing once it
# is.

_DATES = """
@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<urn:span> a crm:E52_Time-Span ;
    crm:P82a_begin_of_the_begin "0600-01-01"^^xsd:date ;
    crm:P82b_end_of_the_end     "0650-12-31"^^xsd:date ;
    crm:P81a_end_of_the_begin   "0610-01-01"^^xsd:date ;
    crm:P81b_begin_of_the_end   "0640-12-31"^^xsd:date .

<urn:dim> a crm:E54_Dimension ;
    crm:P90a_has_lower_value_limit "10"^^xsd:integer ;
    crm:P90b_has_upper_value_limit "20"^^xsd:integer .
"""


def test_the_standard_way_to_write_a_date_validates(tmp_path):
    # The defect this whole change exists for: every real CRM dataset
    # writes time-spans with P82a/P82b, and the validator rejected them.
    from lib.ontology import crm_rdf_links, validate_document

    f = tmp_path / "d.ttl"
    f.write_text(_DATES, encoding="utf-8")
    report = validate_document(_onto(), crm_rdf_links(f, _onto()))
    assert report["counts"].get("unknown_name", 0) == 0
    assert report["counts"].get("ok_literal", 0) == 6


def test_a_date_property_on_the_wrong_class_is_still_illegal(tmp_path):
    # Accepting the identifier must not mean accepting it anywhere.
    from lib.ontology import crm_rdf_links, validate_document

    f = tmp_path / "d.ttl"
    f.write_text(_DATES.replace("crm:E52_Time-Span",
                                "crm:E22_Human-Made_Object"),
                 encoding="utf-8")
    report = validate_document(_onto(), crm_rdf_links(f, _onto()))
    assert report["counts"].get("illegal", 0) == 4


def test_an_ordinary_crm_finding_does_not_gain_a_redundant_uri_line(tmp_path):
    # The condition guarding the new line must stay quiet for a predicate
    # addressed by its own native CRM URI: name ("P108") and predicate_uri
    # (".../P108_has_produced") legitimately differ on every RDF finding,
    # and printing the full URI beside the short id there would clutter
    # every single line of every RDF report, not just the bridged ones.
    from lib.ontology import crm_rdf_links, validate_document
    from search import format_document_validation

    bad = """
@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .
<urn:a> a crm:E22_Human-Made_Object ; crm:P108_has_produced <urn:b> .
<urn:b> a crm:E12_Production .
"""
    f = tmp_path / "m.ttl"
    f.write_text(bad, encoding="utf-8")
    onto = _onto()
    report = validate_document(onto, crm_rdf_links(f, onto))
    report["class_labels"] = []
    report["structural_elements_skipped"] = []
    report["inverse_claims"] = []
    text = format_document_validation(report)

    assert report["counts"].get("illegal", 0) == 1
    assert "written in the document as" not in text
    assert "P108_has_produced" not in text


_TYPES = """
@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .
@prefix crmsci: <http://www.cidoc-crm.org/extensions/crmsci/> .
@prefix ex: <http://example.org/> .

<urn:e> a crmsci:S4_Observation ; crmsci:O19_encountered_object <urn:o> .
<urn:o> a crm:E22_Human_Made_Object .
<urn:z> a ex:Widget ; crm:P3_has_note "foreign type" .
<urn:q> a crm:P108_has_produced ; crm:P3_has_note "typed as a property" .
"""


def _class_uses(tmp_path, text, name="t.ttl"):
    from lib.ontology import crm_rdf_class_uses

    f = tmp_path / name
    f.write_text(text, encoding="utf-8")
    return {u["raw"].rsplit("/", 1)[-1]: u for u in crm_rdf_class_uses(f, _onto())}


def test_a_stale_class_name_does_not_vanish(tmp_path):
    # CRMsci v3.2 renamed S4 Observation to S4 Single Observation. A subject
    # whose only type is the stale name looked UNTYPED, because crm_rdf_links
    # keeps the types that resolve and drops the rest, so its links landed
    # `unchecked` and the document exited 0 having said nothing about it.
    # This is the likeliest error an LLM makes: outdated training data.
    by = _class_uses(tmp_path, _TYPES)
    assert by["S4_Observation"]["verdict"] == "unknown_class"
    assert by["S4_Observation"]["path"] == "urn:e"


def test_a_misspelled_class_on_the_object_end_does_not_vanish(tmp_path):
    # An underscore where the CRM writes a hyphen. The link read None -> None
    # and passed -- the object end had exactly the same hole as the subject.
    by = _class_uses(tmp_path, _TYPES)
    assert by["E22_Human_Made_Object"]["verdict"] == "unknown_class"


def test_a_property_used_as_a_type_is_named_as_such(tmp_path):
    # `a crm:P108_has_produced` resolves, so "unknown" would be false. It is
    # the wrong KIND of thing, and that is a different fix.
    by = _class_uses(tmp_path, _TYPES)
    assert by["P108_has_produced"]["verdict"] == "not_a_class"
    assert "property, not a class" in by["P108_has_produced"]["detail"]


def test_a_foreign_type_is_reported_but_does_not_fail(tmp_path):
    # Same standing rdfs:label gets as a predicate: named, never dropped,
    # not a failure.
    by = _class_uses(tmp_path, _TYPES)
    assert by["Widget"]["verdict"] == "not_crm"


def test_a_document_whose_types_all_resolve_yields_nothing(tmp_path):
    assert _class_uses(tmp_path, TTL) == {}


def test_the_cli_fails_on_an_unresolvable_rdf_type(tmp_path):
    # The whole point: this exited 0 before, reporting nothing.
    import subprocess
    import sys

    from lib.config import PROJECT_ROOT

    f = tmp_path / "t.ttl"
    f.write_text(_TYPES, encoding="utf-8")
    r = subprocess.run([sys.executable, "search.py", "validate", "--rdf", str(f)],
                       cwd=PROJECT_ROOT, capture_output=True, text=True)
    assert r.returncode == 1, r.stdout
    assert "UNKNOWN_CLASS" in r.stdout
    assert "S4_Observation" in r.stdout


def _completeness_section(model="models/crm_bayeux.xml"):
    import subprocess
    import sys

    from lib.config import PROJECT_ROOT

    r = subprocess.run([sys.executable, "search.py", "validate", "--xml",
                        model, "--completeness"],
                       cwd=PROJECT_ROOT, capture_output=True, text=True)
    body = r.stdout.split("NOT STATED", 1)[1]
    return [ln for ln in body.splitlines() if ln.strip()]


def test_completeness_puts_the_likeliest_oversights_first():
    # The section states that 1-of-9 is probably an oversight and 9-of-9
    # probably a convention, then used to sort by class id and bury the
    # first among the second. On crm_bayeux that was 36 partial rows
    # scattered through 99 wholly-absent ones. The order now follows the
    # rule the header states.
    lines = _completeness_section()
    partial = [ln for ln in lines if ln.strip().startswith(("E", "S"))
               and "%" in ln]
    fractions = [int(ln.rsplit("%", 1)[0].split()[-1]) for ln in partial]
    assert fractions == sorted(fractions)
    assert fractions[0] <= 20          # the rarest omission leads


def test_completeness_collapses_a_property_absent_from_every_class():
    # P10, P12, P160 and P161 each recurred at n/n across fourteen event
    # classes -- one decision about temporal projections printed 56 times.
    # Grouped, each is stated once and still names every class.
    lines = _completeness_section()
    tail = "\n".join(lines[[i for i, ln in enumerate(lines)
                            if "Never stated" in ln][0]:])
    assert tail.count("P160") == 1
    assert "across 14 classes" in tail
    assert "S19" in tail               # every class is still named


def test_completeness_still_reports_every_pair_it_found():
    # Reordering and grouping must not drop anything: the same
    # (class, property) pairs appear, in a different arrangement.
    import json as _j

    from lib.config import DATA_DIR, PROJECT_ROOT
    from lib.ontology import crm_example_links, document_completeness

    onto = _j.loads((DATA_DIR / "ontology.json").read_text(encoding="utf-8"))
    rows = document_completeness(
        onto, crm_example_links(PROJECT_ROOT / "models" / "crm_bayeux.xml"))
    text = "\n".join(_completeness_section())
    for r in rows:
        assert r["property_id"] in text, r
        assert r["class_id"] in text, r


def test_a_bce_date_validates_quietly(tmp_path, capfd):
    # "-0900-01-01"^^xsd:date is legal Turtle and the obvious way to date a
    # Western Zhou bronze. Python's date type cannot hold it, so rdflib logs
    # a full traceback and then keeps the literal as a string -- which is all
    # this reader needs, since the checker never uses a literal's typed
    # value. The document validates. But 21 lines of traceback do not read as
    # "fine": an agent modelling the Mao Gong ding saw one and edited a
    # correct file to remove the date.
    from lib.ontology import crm_rdf_links, validate_document

    f = tmp_path / "bce.ttl"
    f.write_text(
        '@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .\n'
        '@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n'
        '<urn:s> a crm:E52_Time-Span ;\n'
        '    crm:P82a_begin_of_the_begin "-0900-01-01"^^xsd:date .\n',
        encoding="utf-8")
    capfd.readouterr()
    report = validate_document(_onto(), crm_rdf_links(f, _onto()))
    err = capfd.readouterr().err
    assert report["counts"].get("ok_literal") == 1
    assert report["counts"].get("illegal", 0) == 0
    assert "Traceback" not in err, err[:300]


def test_a_genuine_syntax_error_still_raises(tmp_path):
    # Quieting the converter must not swallow a real parse failure.
    from lib.ontology import crm_rdf_links

    f = tmp_path / "broken.ttl"
    f.write_text("@prefix crm: <http://example.org/> .\n<urn:a> crm:p ;;;\n",
                 encoding="utf-8")
    with pytest.raises(Exception):
        crm_rdf_links(f, _onto())
