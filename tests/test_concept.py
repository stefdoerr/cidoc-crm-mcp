import json

import pytest

from lib.config import PROJECT_ROOT, STORES_DIR
from lib.ontology import (
    add_historical,
    ontology_skeleton,
    parse_ontology,
    property_closure,
)
from lib.retrieve import Retriever
from search import concept_chronology, format_concept


@pytest.fixture(scope="module")
def onto():
    o = parse_ontology(PROJECT_ROOT / "sources" / "cidoc_crm_v7.1.3.xml")
    add_historical(o, {"E84": 269})
    return o


@pytest.fixture(scope="module")
def closure(onto):
    return property_closure(onto)


def test_skeleton_covers_every_current_concept(onto):
    skel = ontology_skeleton(onto)
    assert len(skel) == 241  # 81 classes + 160 properties
    assert {s["kind"] for s in skel} == {"class", "property"}


def test_skeleton_excludes_historical_ids(onto):
    # v7.1.3 has no definition to serialize for them
    assert "E84" not in {s["id"] for s in ontology_skeleton(onto)}


def test_skeleton_carries_class_hierarchy_both_ways(onto):
    by_id = {s["id"]: s for s in ontology_skeleton(onto)}
    assert by_id["E22"]["parents"] == ["E19", "E24"]
    assert "E22" in by_id["E19"]["children"]


def test_skeleton_carries_property_hierarchy_both_ways(onto):
    """83 of 160 properties have a parent — the orientation tier must show it,
    or the agent picks candidates blind to the specificity Task 2b ranks by."""
    by_id = {s["id"]: s for s in ontology_skeleton(onto)}
    parented = [s for s in by_id.values()
                if s["kind"] == "property" and s["parents"]]
    assert len(parented) == 83
    # every declared parent must list the child back
    for prop in parented:
        for parent in prop["parents"]:
            assert prop["id"] in by_id[parent]["children"], f"{prop['id']} -> {parent}"


def test_first_sentence_does_not_cut_on_nonterminal_abbreviations(onto):
    """A bare (?<=[.!?])\\s cut 9 glosses mid-abbreviation; the uppercase guard
    fixes the ones that matter.

    Only NON-terminal abbreviations are asserted. `etc.` legitimately ends a
    sentence and does so 5 times here — E25 "…water channels, etc. In
    particular…", E54 "…RGB values, etc. An instance of…". Forbidding `etc.`
    would push those glosses past their real boundary into the next sentence,
    making the output worse, so it is deliberately excluded.
    """
    import re
    nonterminal = re.compile(r"\b(e\.g\.|i\.e\.|cf\.|Fig\.|No\.|vs\.)$")
    for s in ontology_skeleton(onto):
        assert not nonterminal.search(s["gloss"].strip()), s["id"]


def test_glosses_have_no_trailing_whitespace(onto):
    for s in ontology_skeleton(onto):
        assert s["gloss"] == s["gloss"].rstrip(), s["id"]


def test_skeleton_property_records_carry_domain_range_quantification(onto):
    by_id = {s["id"]: s for s in ontology_skeleton(onto)}
    p140 = by_id["P140"]
    assert p140["domain"] == "E13"
    assert p140["range"] == "E1"
    assert p140["quantification"] == "many to many (0,n:0,n)"


def test_skeleton_gloss_is_one_sentence_not_the_whole_scope_note(onto):
    by_id = {s["id"]: s for s in ontology_skeleton(onto)}
    gloss = by_id["E55"]["gloss"]
    assert gloss and len(gloss) < len(onto["classes"]["E55"]["scope_note"])


def test_skeleton_is_small_enough_to_read_whole(onto):
    """The load-bearing claim: it fits in context, so no retrieval is needed."""
    size = len(json.dumps(ontology_skeleton(onto)))
    assert size < 120_000, f"skeleton grew to {size} chars — recheck the no-retrieval decision"


def test_format_concept_lists_applicable_properties_both_directions(onto):
    entry = dict(onto["classes"]["E22"], bucket="classes")
    out = format_concept(entry, [], mentions=1576, onto=onto)
    # 0 properties declare domain E22 directly; 31 reach it by ancestry, 38 point at it.
    # Without the ancestry walk this section would be empty.
    assert "P1" in out
    assert "subject of" in out.lower()
    assert "point at" in out.lower()


def test_format_concept_names_properties_rather_than_listing_bare_ids(onto):
    """The rendering defect that cost the evaluation real cases: the block
    printed at most twenty anonymous integers, so P177 -- 17th of 20 for E13
    and declared necessary -- carried no signal at all."""
    entry = dict(onto["classes"]["E13"], bucket="classes")
    out = format_concept(entry, [], mentions=0, onto=onto)
    assert "P177" in out
    assert "assigned property of type" in out, "property names are not rendered"
    assert "Required" in out, "the necessary-property block is missing"
    # the range must be shown too, or the reader cannot tell what it attaches to
    required_line = next(ln for ln in out.splitlines()
                         if "P177" in ln and "assigned property of type" in ln)
    assert "E55" in required_line


def test_format_concept_does_not_truncate_the_property_table(onto):
    """The display defect itself, guarded where it lived.

    P177 is a weak witness -- it sat 17th of 20 and would survive a
    reinstated cap. P30 is the real one: E10 has 47 applicable outgoing
    properties, P30 is declared necessary, and the old `[:20]` slice meant it
    was never printed at all. Every applicable property must reach the page.
    """
    from lib.ontology import applicable_properties

    entry = dict(onto["classes"]["E10"], bucket="classes")
    out = format_concept(entry, [], mentions=0, onto=onto)
    assert "P30" in out
    assert "transferred custody of" in out
    expected = applicable_properties(onto, "E10")
    assert len(expected["outgoing"]) > 20, "E10 must exceed the old cap for this to bite"
    for row in expected["outgoing"] + expected["incoming"]:
        assert row["id"] in out, f"{row['id']} was dropped from the rendered table"


def test_format_concept_shows_no_property_table_for_a_property(onto):
    """Properties do not have applicable properties; rendering one would be
    nonsense inherited from treating every concept as a class."""
    entry = dict(onto["properties"]["P14"], bucket="properties")
    out = format_concept(entry, [], mentions=0, onto=onto)
    assert "Applicable properties" not in out


def test_format_concept_survives_without_an_ontology(onto):
    """The parameter is optional; callers that pass nothing must not crash."""
    entry = dict(onto["classes"]["E22"], bucket="classes")
    out = format_concept(entry, [], mentions=0)
    assert "Applicable properties" not in out
    assert "E22" in out


def test_chronology_is_oldest_first_and_filtered():
    episodes = [
        {"episode_id": "t2-e1", "thread_id": "t2", "date_start": "2015-01-01",
         "topic": "later", "outcome": "decided", "entities": ["E55"]},
        {"episode_id": "t1-e1", "thread_id": "t1", "date_start": "2005-01-01",
         "topic": "earlier", "outcome": "unresolved", "entities": ["E55"]},
        {"episode_id": "t3-e1", "thread_id": "t3", "date_start": "2010-01-01",
         "topic": "other", "outcome": "decided", "entities": ["P140"]},
    ]
    chrono = concept_chronology(episodes, "E55")
    assert [e["episode_id"] for e in chrono] == ["t1-e1", "t2-e1"]


def test_chronology_includes_historical_entity_matches():
    episodes = [{"episode_id": "t1-e1", "thread_id": "t1", "date_start": "2009-01-01",
                 "topic": "removal", "outcome": "decided", "entities": [],
                 "entities_historical": ["E84"]}]
    assert len(concept_chronology(episodes, "E84")) == 1


def test_chronology_includes_extension_entity_matches():
    """135 episodes carry only a family id (FRBRoo, CRMsci, ...), never a core
    CRMbase one — without matching entities_extension their chronologies
    would be empty even though the episode is squarely about that concept."""
    episodes = [{"episode_id": "t1-e1", "thread_id": "t1", "date_start": "2012-01-01",
                 "topic": "F3 vs F5", "outcome": "decided", "entities": [],
                 "entities_historical": [], "entities_extension": ["F3"]}]
    assert len(concept_chronology(episodes, "F3")) == 1


def test_format_concept_labels_the_definition_as_current(onto):
    entry = dict(onto["classes"]["E22"], bucket="classes")
    out = format_concept(entry, [], mentions=1576)
    assert "Human-Made Object" in out
    # E22 was "Man-Made Object" in 2005 — the version tag is what prevents
    # a reader from treating the modern label as contemporaneous.
    assert "v7.1.3" in out and "current" in out


def test_format_concept_shows_hierarchy_and_volume(onto):
    entry = dict(onto["classes"]["E22"], bucket="classes")
    out = format_concept(entry, [], mentions=1576)
    assert "E19" in out and "E24" in out  # both parents
    assert "1576" in out or "1,576" in out


# ---- "mentions" means two different things -------------------------------
#
# data/ontology.json's own count (surfaced here for the extensions bucket)
# is raw identifier occurrences across subject+body; every other bucket's
# `mentions` argument is a distinct-message count computed in main() by
# scanning each message's entity list. Both numbers are legitimate -- E84 is
# 113 raw occurrences and 52 messages -- so the label must say which one is
# on screen instead of calling both "mentions" with no qualifier.


def test_format_concept_labels_mentions_as_message_count_for_classes(onto):
    entry = dict(onto["classes"]["E22"], bucket="classes")
    out = format_concept(entry, [], mentions=1576)
    assert "messages whose entity list contains E22" in out
    assert "raw" not in out.lower()


def test_format_concept_labels_mentions_as_message_count_for_historical(onto):
    entry = dict(onto["historical"]["E84"], bucket="historical")
    out = format_concept(entry, [], mentions=52)
    assert "messages whose entity list contains E84" in out


def test_format_concept_labels_mentions_as_raw_occurrences_for_extensions(real_ontology):
    entry = dict(real_ontology["extensions"]["F3"], bucket="extensions")
    out = format_concept(entry, [], mentions=entry["mentions"])
    assert "raw F3 occurrences" in out
    assert "messages whose entity list" not in out


def test_format_concept_for_historical_id_says_why_there_is_no_definition(onto):
    entry = dict(onto["historical"]["E84"], bucket="historical")
    chrono = [{"episode_id": "t1-e1", "thread_id": "t1", "date_start": "2009-01-01",
               "topic": "Removing E84", "outcome": "decided"}]
    out = format_concept(entry, chrono, mentions=269)
    assert "E84" in out
    assert "no definition" in out.lower() or "deprecated" in out.lower()
    assert "t1" in out  # the chronology is the point for a historical id


def test_format_concept_renders_the_chronology(onto):
    entry = dict(onto["classes"]["E55"], bucket="classes")
    chrono = [{"episode_id": "t1-e1", "thread_id": "t1", "date_start": "2005-03-01",
               "topic": "Scope of E55", "outcome": "decided"}]
    out = format_concept(entry, chrono, mentions=3701)
    assert "Scope of E55" in out
    assert "2005-03-01" in out
    assert "t1" in out


# ---- Two extensions beyond the plan text --------------------------------
#
# data/ontology.json now has a fourth bucket, "extensions": 330 CRM-family
# ids (FRBRoo, CRMsci, CRMgeo, ...) that cidoc_crm_v7.1.3.xml never declared.
# concept must resolve them and format_concept must render them sensibly.
# No closure (property_closure is built over CRMbase's XML alone), but for a
# declared id -- one whose model's own declaration page is on file, scraped
# by tools/fetch_crm_family.py -- id/label/model/kind/status/mentions/
# chronology/scope_note/hierarchy/domain-range are all real and shown. An
# archive-only id (only this archive attests it; the model's current
# declarations dropped it) has none of the scraped fields, and must still
# render without crashing.


@pytest.fixture(scope="module")
def real_ontology():
    return json.loads((PROJECT_ROOT / "data" / "ontology.json").read_text(encoding="utf-8"))


def test_format_concept_for_declared_extension_shows_model_and_label(real_ontology):
    entry = dict(real_ontology["extensions"]["F3"], bucket="extensions")
    assert entry["label"] == "Manifestation"
    assert entry["status"] == "current"
    out = format_concept(entry, [], mentions=entry["mentions"])
    assert "F3" in out
    assert "Manifestation" in out
    assert "LRMoo" in out
    # honesty: the attribution header, not a body sentence, is what carries
    # this now -- Model:/Status: makes it unambiguous the id belongs to
    # LRMoo's own declarations, not the CRMbase XML.
    assert "Model:  LRMoo" in out
    assert "None" not in out


def test_format_concept_for_declared_extension_shows_a_real_scope_note_and_hierarchy(real_ontology):
    """The whole point of this task: a declared extension id used to be a
    dead end ('its definition lives in CRMsci's own specification'). It must
    now carry the same kind of material the CRMbase branch shows -- a real
    scope note plus its subclass/superclass hierarchy -- scraped from the
    model's own declaration page (see tools/fetch_crm_family.py)."""
    entry = dict(real_ontology["extensions"]["S4"], bucket="extensions")
    out = format_concept(entry, [], mentions=entry["mentions"])
    assert "Subclass of:      S27, E13" in out
    assert "Superclass of:    E16" in out
    assert "URI:" in out and "S4_Single_Observation" in out
    # the actual scope note prose, not the old dead-end sentence
    assert "empirical evidence" in out
    assert "belongs to CRMsci, not CRMbase" not in out


def test_format_concept_for_declared_extension_property_shows_domain_and_range(real_ontology):
    """Properties carry domain/range instead of subclass/superclass -- CRMsci
    O13 is CRMbase's own worked example in the task spec."""
    entry = dict(real_ontology["extensions"]["O13"], bucket="extensions")
    out = format_concept(entry, [], mentions=entry["mentions"])
    assert "Domain -> Range:  E5 -> E5" in out
    assert "triggered" in out.lower()


def test_format_concept_for_archive_only_extension_has_no_label_and_does_not_crash(real_ontology):
    # Pick a real archive-only extension id: known only to this archive, not
    # to the model's current declarations, so label is None.
    archive_only = next(
        (eid, e) for eid, e in real_ontology["extensions"].items()
        if e["status"] == "historical" and e.get("label") is None
    )
    ident, expected = archive_only
    entry = dict(expected, bucket="extensions")
    assert "scope_note" not in entry  # nothing was ever declared for this id
    out = format_concept(entry, [], mentions=entry["mentions"])
    assert ident in out
    assert "None" not in out  # a None label must not print the string "None"
    assert entry["model"] in out
    # the fallback sentence still explains the gap honestly
    assert "no scope note is on file" in out


def test_format_concept_crmbase_branch_unaffected_by_extensions_dossier(onto):
    """The extensions branch grew a full dossier (Model:/Status: header, URI,
    hierarchy); the CRMbase branch must render exactly as it always has --
    no bleed-through of extensions-only labels into a classes/properties
    entry."""
    entry = dict(onto["classes"]["E22"], bucket="classes")
    out = format_concept(entry, [], mentions=1576)
    assert "Model:" not in out
    assert "Status: current —" not in out
    assert "E19" in out and "E24" in out  # its own hierarchy, unaffected
    assert "v7.1.3 (current)" in out  # CRMbase's own version tag, unchanged


def test_format_concept_warns_against_inferring_outcomes_from_current_state(onto):
    """The blind eval's dominant failure: reading the standard's present state
    as evidence of what a past debate decided, in both directions."""
    entry = dict(onto["classes"]["E55"], bucket="classes")
    chrono = [{"episode_id": "t1-e1", "thread_id": "t1", "date_start": "2005-03-01",
               "topic": "Scope of E55", "outcome": "decided"}]
    out = format_concept(entry, chrono, mentions=3701)
    assert "CURRENT standard" in out
    assert "not a record of any past decision" in out
    # An outcome tag is one summariser's reading, not a verified fact.
    assert "not a verified fact" in out


# ---- Task 19: siblings, 7.3.2 FOL/full path, narrative passages -----------
#
# The discrimination material -- what a reader chooses BETWEEN, the formal
# constraint that is often the sharpest tie-breaker, and citable modelling
# guidance from the reference document. format_concept's rendering is tested
# here on hand-built inputs (no Retriever needed); the Retriever helpers that
# produce those inputs from real data are tested further down, gated on a
# built store the same way tests/test_smoke_retrieval.py is.


def test_format_concept_shows_siblings_with_glosses(onto):
    entry = dict(onto["classes"]["E22"], bucket="classes")
    siblings = [
        {"id": "E20", "label": "Biological Object",
         "gloss": "This class comprises individual physical objects that are living things."},
        {"id": "E25", "label": "Human-Made Feature",
         "gloss": "This class comprises physical features that are purposely created by human activity."},
    ]
    out = format_concept(entry, [], mentions=1576, siblings=siblings)
    assert "Siblings" in out
    assert "subclasses of E19, E24" in out
    assert "E20" in out and "Biological Object" in out
    assert "E25" in out and "Human-Made Feature" in out


def test_format_concept_says_no_siblings_for_root_class(onto):
    """E1 has no parent, so there is nothing else at its level to
    discriminate against -- an explicit statement, not a silent omission."""
    entry = dict(onto["classes"]["E1"], bucket="classes")
    out = format_concept(entry, [], mentions=185, siblings=[])
    assert "no parent" in out.lower()


def test_format_concept_says_only_child_when_siblings_empty_but_parent_exists():
    """A concept can have a declared parent yet be that parent's sole child
    (20 of 241 do). Distinct from the root case: this reader should learn
    it's the only one, not that there was no parent to check."""
    entry = {"id": "E37", "bucket": "classes", "sub_class_of": ["E36"],
              "full_name": "E37 Mark"}
    out = format_concept(entry, [], mentions=0, siblings=[])
    assert "only" in out.lower()
    assert "E36" in out


def test_format_concept_caps_siblings_and_reports_elided_count():
    entry = {"id": "E65", "bucket": "classes", "sub_class_of": ["E7"],
              "full_name": "E65 Creation"}
    siblings = [
        {"id": f"E9{n}", "label": f"Sibling {n}", "gloss": f"Gloss {n}."}
        for n in range(13)
    ]
    out = format_concept(entry, [], mentions=0, siblings=siblings)
    assert "more (not shown)" in out
    assert "3 more" in out  # cap is 10, so 13 - 10 = 3 elided


def test_format_concept_omits_siblings_section_for_historical_and_extensions(real_ontology):
    hist_entry = dict(real_ontology["historical"]["E84"], bucket="historical")
    out = format_concept(hist_entry, [], mentions=52, siblings=[])
    assert "Siblings" not in out


def test_format_concept_labels_fol_and_full_path_as_v732(onto):
    entry = dict(onto["properties"]["P62"], bucket="properties")
    declaration = {
        "fol": ["P62(x,y) ⇒ E24(x)", "P62(x,y) ⇒ E1(y)"],
        "full_path": [
            "E24 Physical Human-Made Thing. P65 shows visual item (is shown by): "
            "E36 Visual Item. P138 represents (has representation): E1 CRM Entity"
        ],
        "cite": "CIDOC CRM v7.3.2",
    }
    out = format_concept(entry, [], mentions=65, declaration=declaration)
    assert "v7.3.2" in out
    assert "not in the v7.1.3 XML" in out
    assert "P62(x,y) ⇒ E24(x)" in out
    assert "Full path" in out and "shows visual item" in out


def test_format_concept_omits_declaration_section_when_none(onto):
    """E38 is deprecated and 7.3.2 dropped its declaration entirely -- a
    missing declaration must render nothing here, not an error, and must
    never claim v7.3.2 material that doesn't exist."""
    entry = dict(onto["classes"]["E22"], bucket="classes")
    out = format_concept(entry, [], mentions=1576, declaration=None)
    assert "From CIDOC CRM v7.3.2" not in out
    assert "not in the v7.1.3 XML" not in out


def test_format_concept_shows_narrative_passages_with_citable_section_path(onto):
    entry = dict(onto["classes"]["E22"], bucket="classes")
    narratives = [
        {"section_path": ["Modelling principles", "Minimality"],
         "text": "Only concepts with a demonstrated general use are declared explicit classes."},
    ]
    out = format_concept(entry, [], mentions=1576, narratives=narratives)
    assert "Modelling principles > Minimality" in out
    assert "demonstrated general use" in out


def test_format_concept_reports_no_narrative_passages_when_none(onto):
    entry = dict(onto["classes"]["E22"], bucket="classes")
    out = format_concept(entry, [], mentions=1576, narratives=[])
    assert "No CIDOC CRM v7.3.2 narrative passages mention" in out


def test_format_concept_caps_narratives_and_reports_elided_count(onto):
    entry = dict(onto["classes"]["E1"], bucket="classes")
    narratives = [
        {"section_path": ["Section", f"Sub {n}"], "text": f"Passage {n}."}
        for n in range(5)
    ]
    out = format_concept(entry, [], mentions=0, narratives=narratives)
    assert "2 more" in out  # cap is 3, so 5 - 3 = 2 elided


# ---- get_concept survives a stale (four-bucket) data/ontology.json --------
#
# data/ is gitignored and rebuilt by `uv run python build.py ontology`.
# "property_of_property" is a fifth bucket added after four already
# existed; anyone who pulls this branch without rebuilding still has a
# four-bucket artifact on disk. get_concept() used to index onto[bucket]
# directly, so the loop's last iteration raised KeyError on every miss --
# confirmed against a stale copy: E22 (found before reaching the fifth
# bucket) worked, but P14.1, a label lookup ("Type"), and an unknown id
# (ZZ999) all crashed instead of returning None. Retriever() is cheap to
# construct (see tests/test_retrieve.py); injecting into __dict__ bypasses
# the `ontology` cached_property the same way tests/test_eval_citations.py
# does, so this needs no built store.

_STALE_FOUR_BUCKET_ONTOLOGY = {
    "classes": {}, "properties": {}, "historical": {}, "extensions": {},
}


def _stale_retriever():
    r = Retriever()
    r.__dict__["ontology"] = _STALE_FOUR_BUCKET_ONTOLOGY
    return r


@pytest.mark.parametrize("target", ["P14.1", "Type", "ZZ999"])
def test_get_concept_returns_none_not_keyerror_on_a_stale_four_bucket_ontology(target):
    assert _stale_retriever().get_concept(target) is None


# ---- Retriever helpers backing the above -----------------------------------
#
# get_declaration, concept_siblings and concept_narratives read data/
# documents.jsonl and data/ontology.json directly and need no vector store,
# but Retriever() is gated on a built store regardless, matching
# tests/test_smoke_retrieval.py's policy for constructing one at all.

retriever_built = pytest.mark.skipif(
    not (STORES_DIR / "crm-sig" / "meta.json").exists(),
    reason="index not built; run `uv run python build.py index` first",
)


@pytest.fixture(scope="module")
def dossier_retriever():
    from lib.retrieve import Retriever

    return Retriever("crm-sig")


@retriever_built
class TestConceptDossierHelpers:
    @pytest.fixture
    def retriever(self, dossier_retriever):
        return dossier_retriever

    def test_get_declaration_extracts_fol_and_full_path_for_a_shortcut(self, retriever):
        decl = retriever.get_declaration("P62")
        assert decl is not None
        assert any("E24(x)" in ln for ln in decl["fol"])
        assert decl["full_path"] and "E36 Visual Item" in decl["full_path"][0]

    def test_get_declaration_is_none_for_a_deprecated_id_not_in_732(self, retriever):
        """E38 is deprecated and absent from 7.3.2. None must not raise, and
        must not be confused with the concept not existing."""
        assert retriever.get_declaration("E38") is None

    def test_get_declaration_is_none_for_an_unknown_id(self, retriever):
        assert retriever.get_declaration("Q999") is None

    def test_concept_siblings_excludes_self_and_includes_true_siblings(self, retriever):
        siblings = retriever.concept_siblings("E36")
        ids = {s["id"] for s in siblings}
        assert "E36" not in ids
        assert {"E29", "E31", "E33"} <= ids  # E73's other subclasses

    def test_concept_siblings_empty_for_root_class(self, retriever):
        assert retriever.concept_siblings("E1") == []

    def test_concept_siblings_empty_for_a_parentless_property(self, retriever):
        assert retriever.concept_siblings("P62") == []

    def test_concept_siblings_empty_for_historical_and_extension_ids(self, retriever):
        assert retriever.concept_siblings("E84") == []
        assert retriever.concept_siblings("F3") == []

    def test_concept_narratives_ranks_by_specificity_ascending(self, retriever):
        narratives = retriever.concept_narratives("E1")
        assert narratives
        counts = [
            len(n.get("entities") or []) + len(n.get("entities_historical") or [])
            for n in narratives
        ]
        assert counts == sorted(counts)

    def test_concept_narratives_every_hit_actually_carries_the_id(self, retriever):
        for n in retriever.concept_narratives("E73"):
            assert "E73" in (n.get("entities") or []) + (n.get("entities_historical") or [])

    def test_concept_narratives_empty_for_id_with_no_mentions(self, retriever):
        # F3 is a real, current extension id, but the reference document's
        # narrative sections never happen to name it.
        assert retriever.concept_narratives("F3") == []


def _sib(i, label):
    return {"id": i, "label": label, "gloss": f"gloss for {label}", "kind": "class"}


def test_sibling_elision_is_stated_not_silent(onto):
    """The cap bites for only 2 of 81 classes (E65, E66 at 12 siblings), so it
    stays -- but a reader must not mistake a truncated list for the whole set
    of things they are choosing between."""
    entry = dict(onto["classes"]["E55"], bucket="classes")
    many = [_sib(f"E{900 + n}", f"Sib{n}") for n in range(14)]
    out = format_concept(entry, [], mentions=1, siblings=many)
    assert "and 4 more" in out, out[:400]


def test_no_sibling_elision_notice_when_all_fit(onto):
    entry = dict(onto["classes"]["E55"], bucket="classes")
    out = format_concept(entry, [], mentions=1, siblings=[_sib("E900", "Sib")])
    assert "more (not shown)" not in out


def test_withheld_reference_passages_are_counted(onto):
    """22 concepts have more than the 3 passages shown -- E2 has 13, E55 has
    10. Showing 3 of 13 without saying so lets a reader believe they have seen
    everything the specification says about the concept."""
    entry = dict(onto["classes"]["E55"], bucket="classes")
    narratives = [
        {"section_path": ["Part", f"Section {n}"], "text": f"passage {n} about E55"}
        for n in range(9)
    ]
    out = format_concept(entry, [], mentions=1, narratives=narratives)
    assert "6 more" in out, out[-600:]


def test_incoming_rows_print_the_identifier_you_must_actually_write(onto):
    # An incoming row is the class seen from the far end, so its NAME is the
    # inverse reading. Printed beside the forward identifier it said
    # "P108  was produced by  E12", which reads as E22 --P108--> E12: exactly
    # backwards, and rejected by the validator. An agent modelling from this
    # listing reported it as actively misleading.
    import search

    text = search.format_concept(onto["classes"]["E22"], [], 0, onto=onto)
    tail = text.split("Things can point at it:", 1)[1]
    assert "P108i  was produced by" in tail
    # The forward direction must not have gained an i.
    head = text.split("Things can point at it:", 1)[0]
    assert "P65i" not in head


def test_an_incoming_property_with_no_inverse_is_not_given_a_phantom_one(onto):
    # P82a is literal-valued: its range is E61, so it appears in E61's
    # incoming list, but "P82ai" is a name the validator refuses. Printing it
    # would hand the reader the very identifier the inverse-shorthand guard
    # exists to reject.
    import search

    text = search.format_concept(onto["classes"]["E61"], [], 0, onto=onto)
    assert "P82ai" not in text
    assert "no inverse form" in text


def test_applicable_rows_say_which_direction_they_are_read_in(onto):
    from lib.ontology import applicable_properties

    table = applicable_properties(onto, "E22")
    assert all(r["inverse"] is True for r in table["incoming"])
    assert all(r["inverse"] is False for r in table["outgoing"])
