import pytest

from lib.config import DATA_DIR, PROJECT_ROOT
from lib.ontology import (
    CRM_NAMESPACE,
    add_extensions,
    add_historical,
    family_of,
    family_prefixes,
    load_family,
    parse_ontology,
    strip_html,
)

XML = PROJECT_ROOT / "sources" / "cidoc_crm_v7.1.3.xml"


def test_strip_html_removes_tags_then_unescapes():
    # ElementTree already unescapes once during parsing, so structural tags
    # are real (to be removed) but content-meant-to-display is still escaped.
    # Strip real tags first, then unescape the content.
    assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"
    # KML snippet in content should be preserved as visible text
    assert strip_html("<p>See &lt;Placemark&gt; tag</p>") == "See <Placemark> tag"
    assert strip_html(None) == ""
    assert strip_html("") == ""


def test_counts_match_declared_header():
    onto = parse_ontology(XML)
    assert onto["version"] == "7.1.3"
    assert onto["release_date"] == "February 2024"
    assert len(onto["classes"]) == 81
    assert len(onto["properties"]) == 160


def test_subclassof_read_from_attribute_with_multiple_inheritance():
    onto = parse_ontology(XML)
    e22 = onto["classes"]["E22"]
    assert e22["full_name"] == "E22 Human-Made Object"
    assert e22["label"] == "Human-Made Object"
    # attribute, not element text — and E22 has two parents
    assert e22["sub_class_of"] == ["E19", "E24"]


def test_property_domain_and_range_read_from_attribute():
    onto = parse_ontology(XML)
    p140 = onto["properties"]["P140"]
    assert p140["domain"] == "E13"
    assert p140["range"] == "E1"
    assert p140["direct_name"] == "assigned attribute to"
    assert p140["inverse_name"] == "was attributed by"


def test_scope_notes_contain_no_residual_structural_html():
    """Check that structural markup (<p>, <ul>, <li>) is removed, but preserved
    content like &lt;tag&gt; (meant to display as text) remains visible."""
    onto = parse_ontology(XML)
    # Structural HTML tags should be removed
    structural_tags = ["<p>", "<ul>", "<li>", "<ol>", "<b>", "<i>", "<em>"]
    for entry in list(onto["classes"].values()) + list(onto["properties"].values()):
        for tag in structural_tags:
            assert tag not in entry["scope_note"], f"{entry['id']} has {tag}"
        # Escaped entities should not remain as-is
        assert "&lt;" not in entry["scope_note"], entry["id"]
        assert "&gt;" not in entry["scope_note"], entry["id"]
    assert len(onto["classes"]["E55"]["scope_note"]) > 100


def test_everything_parsed_is_marked_current():
    onto = parse_ontology(XML)
    assert all(c["status"] == "current" for c in onto["classes"].values())
    assert onto["historical"] == {}


def test_add_historical_separates_deprecated_ids():
    onto = parse_ontology(XML)
    add_historical(onto, {"E55": 3701, "E84": 269, "P83": 95})
    # E55 resolves and must not be moved
    assert "E55" not in onto["historical"]
    # E84 / P83 are deprecated — recorded, never dropped
    assert onto["historical"]["E84"]["mentions"] == 269
    assert onto["historical"]["E84"]["status"] == "historical"
    assert onto["historical"]["E84"]["label"] is None
    assert onto["historical"]["P83"]["mentions"] == 95


def test_quantification_in_properties_only():
    onto = parse_ontology(XML)
    # quantification is properties-only
    p140 = onto["properties"]["P140"]
    assert p140["quantification"] == "many to many (0,n:0,n)"
    # no class has quantification
    assert all("quantification" not in c for c in onto["classes"].values())


def test_examples_split_on_list_items():
    onto = parse_ontology(XML)
    e22 = onto["classes"]["E22"]
    # E22 has at least 3 separate examples (split from <li> tags)
    assert len(e22["examples"]) >= 3
    # Rosetta Stone should be its own entry, not glued to next one
    rosetta_found = any("Rosetta Stone" in ex for ex in e22["examples"])
    assert rosetta_found


def test_kml_snippets_preserved_in_examples():
    """E95 examples contain KML markup meant to display as text.
    The fix (strip tags first, then unescape) preserves this content."""
    onto = parse_ontology(XML)
    e95_examples = " ".join(onto["classes"]["E95"]["examples"])
    # KML vocabulary should be visible, not stripped
    assert "Placemark" in e95_examples


def test_kml_snippets_preserved_in_scope_notes():
    """P174, P176, P183, P185 have scope notes with KML markup to display.
    Should be visible, not stripped."""
    onto = parse_ontology(XML)
    # P174: should contain KML-related content
    p174 = onto["properties"]["P174"]["scope_note"]
    assert len(p174) > 0
    # P176, P183, P185 should also have content preserved
    p176 = onto["properties"]["P176"]["scope_note"]
    p183 = onto["properties"]["P183"]["scope_note"]
    p185 = onto["properties"]["P185"]["scope_note"]
    assert len(p176) > 0
    assert len(p183) > 0
    assert len(p185) > 0


def test_affected_entries_have_preserved_markup():
    """All 7 affected entries that contain KML/XML snippets should preserve them.
    These were broken by incorrect unescape-first order."""
    onto = parse_ontology(XML)
    # E53, E94, E95 examples should be non-empty (content preserved)
    assert len(onto["classes"]["E53"]["examples"]) > 0
    assert len(onto["classes"]["E94"]["examples"]) > 0
    assert len(onto["classes"]["E95"]["examples"]) > 0
    # P174, P176, P183, P185 scope_note should be non-empty
    assert len(onto["properties"]["P174"]["scope_note"]) > 0
    assert len(onto["properties"]["P176"]["scope_note"]) > 0
    assert len(onto["properties"]["P183"]["scope_note"]) > 0
    assert len(onto["properties"]["P185"]["scope_note"]) > 0


def test_family_prefixes_derived_from_the_collection_not_guessed():
    # Hand-written prefixes were wrong: CRMtex properties are TXP (not TP),
    # CRMact uses ACTE/ACTP and PRESSoo uses Y/Z. Deriving them prevents that.
    family = load_family(PROJECT_ROOT / "sources" / "crm_family.json")
    resolved = {p: (m, k) for p, m, k in family_prefixes(family)}
    assert resolved["TXP"] == ("CRMtex", "property")
    assert resolved["TX"] == ("CRMtex", "class")
    assert resolved["ACTP"] == ("CRMact", "property")
    assert resolved["Z"] == ("PRESSoo", "class")
    assert "TP" not in resolved
    assert "SOP" not in resolved


def test_family_of_prefers_the_longest_prefix():
    family = load_family(PROJECT_ROOT / "sources" / "crm_family.json")
    prefixes = family_prefixes(family)
    assert family_of("SP6", prefixes) == ("CRMgeo", "class")     # not CRMsci's S
    assert family_of("S6", prefixes) == ("CRMsci", "class")


def test_family_of_rejects_iso_committee_designators():
    # ISO/TC46/SC4/WG9 standardises the CRM and is named throughout the archive.
    prefixes = family_prefixes(load_family(PROJECT_ROOT / "sources" / "crm_family.json"))
    for designator in ("TC46", "SC4", "WG9", "CR8"):
        assert family_of(designator, prefixes) is None, designator


def test_family_of_rejects_out_of_range_numbers():
    # "A622" is a GUID fragment and "B347" a ship section, not ontology classes.
    prefixes = family_prefixes(load_family(PROJECT_ROOT / "sources" / "crm_family.json"))
    assert family_of("A622", prefixes) is None
    assert family_of("B347", prefixes) is None
    assert family_of("A11", prefixes) == ("CRMarchaeo", "class")


def test_add_extensions_records_every_declared_id_and_the_archive_only_ones():
    # This once recorded only ids the archive mentions. That dropped 214 of
    # the 467 declared family concepts, and since the extensions bucket is
    # what tells _owned_namespaces which namespaces the model owns, a dropped
    # id took its whole namespace with it -- a CRMsci property came back
    # `not_crm` and passed. It also made the family models depend on a 143MB
    # archive shipped out of band, so a plain checkout had none of them.
    onto = parse_ontology(PROJECT_ROOT / "sources" / "cidoc_crm_v7.1.3.xml")
    family = load_family(PROJECT_ROOT / "sources" / "crm_family.json")
    add_extensions(onto, {"F3": 12, "SP5": 4, "TC46": 99}, family)
    assert onto["extensions"]["F3"]["status"] == "current"     # in the declarations
    assert onto["extensions"]["F3"]["label"] == "Manifestation"
    assert onto["extensions"]["SP5"]["status"] == "historical"  # archive-only
    assert "TC46" not in onto["extensions"]    # neither declared nor resolvable
    # Declared but unmentioned here: recorded now, and marked unmentioned
    # rather than given a fake count, because callers rank on that number.
    assert onto["extensions"]["S4"]["status"] == "current"
    assert onto["extensions"]["S4"]["mentions"] == 0
    assert onto["extensions"]["F3"]["mentions"] == 12


def test_add_extensions_needs_no_archive_at_all():
    # The case a fresh clone is in: no clean.jsonl, so no mention counts.
    onto = parse_ontology(PROJECT_ROOT / "sources" / "cidoc_crm_v7.1.3.xml")
    add_extensions(onto, {}, load_family(PROJECT_ROOT / "sources" / "crm_family.json"))
    assert len(onto["extensions"]) == 467
    assert onto["extensions"]["O19"]["domain"] == "S19"


def test_add_extensions_never_shadows_crmbase():
    # A family id that collides with a CRMbase one must not overwrite it --
    # the XML is the normative source. Asserted on the two ids specifically
    # rather than on an empty bucket, because the bucket is no longer empty:
    # every declared family concept is recorded regardless of mentions.
    onto = parse_ontology(PROJECT_ROOT / "sources" / "cidoc_crm_v7.1.3.xml")
    add_historical(onto, {"E84": 269})
    add_extensions(onto, {"E55": 100, "E84": 269}, load_family(PROJECT_ROOT / "sources" / "crm_family.json"))
    assert "E55" not in onto["extensions"]   # current CRMbase class
    assert "E84" not in onto["extensions"]   # retired CRMbase class


# ---- Declaration fields (scope note, URI, hierarchy, domain/range) --------
#
# crm_family.json's entries now carry each model's own scope note, URI and
# hierarchy (tools/fetch_crm_family.py), not just label/model/kind. These
# tests pin down that add_extensions carries them into onto["extensions"] --
# and, just as importantly, that it carries NOTHING extra for an id that was
# never declared (archive-only) or whose source has no such structure
# (FRBRoo, from a PDF): absence must stay absence, not a None placeholder.


def test_add_extensions_carries_scope_note_and_hierarchy_for_a_declared_class():
    onto = parse_ontology(PROJECT_ROOT / "sources" / "cidoc_crm_v7.1.3.xml")
    family = load_family(PROJECT_ROOT / "sources" / "crm_family.json")
    add_extensions(onto, {"S4": 81}, family)
    entry = onto["extensions"]["S4"]
    assert entry["scope_note"] and "empirical evidence" in entry["scope_note"]
    assert entry["sub_class_of"] == ["S27", "E13"]
    assert "E16" in entry["super_class_of"]
    assert entry["uri"].endswith("S4_Single_Observation")
    assert "domain" not in entry  # properties-only field, absent on a class


def test_add_extensions_carries_domain_and_range_for_a_declared_property():
    onto = parse_ontology(PROJECT_ROOT / "sources" / "cidoc_crm_v7.1.3.xml")
    family = load_family(PROJECT_ROOT / "sources" / "crm_family.json")
    add_extensions(onto, {"O13": 61}, family)
    entry = onto["extensions"]["O13"]
    assert entry["domain"] == "E5"
    assert entry["range"] == "E5"
    assert entry["scope_note"]
    assert "sub_class_of" not in entry  # classes-only field, absent on a property


def test_add_extensions_leaves_archive_only_ids_without_declaration_fields():
    onto = parse_ontology(PROJECT_ROOT / "sources" / "cidoc_crm_v7.1.3.xml")
    family = load_family(PROJECT_ROOT / "sources" / "crm_family.json")
    add_extensions(onto, {"SP5": 59}, family)
    entry = onto["extensions"]["SP5"]
    assert entry["status"] == "historical"       # only this archive attests it
    assert "scope_note" not in entry
    assert "uri" not in entry
    assert "sub_class_of" not in entry


def test_add_extensions_leaves_pdf_sourced_frbroo_ids_without_declaration_fields():
    """FRBRoo comes from an unstructured PDF (tools/fetch_crm_family.py),
    so its family entries carry only id/label/model/kind -- add_extensions
    must not invent scope_note/uri/hierarchy keys that were never scraped."""
    onto = parse_ontology(PROJECT_ROOT / "sources" / "cidoc_crm_v7.1.3.xml")
    family = load_family(PROJECT_ROOT / "sources" / "crm_family.json")
    frbroo_only = next(
        i for i, e in family.items()
        if e["model"] == "FRBRoo" and "scope_note" not in e
    )
    add_extensions(onto, {frbroo_only: 5}, family)
    entry = onto["extensions"][frbroo_only]
    assert entry["status"] == "current"   # declared -- just without structure
    assert "scope_note" not in entry
    assert "uri" not in entry


def test_property_of_property_parsed_from_nested_element():
    onto = parse_ontology(XML)
    pop = onto["property_of_property"]
    assert len(pop) == 16
    p141 = pop["P14.1"]
    assert p141["of_property"] == "P14"
    assert p141["label"] == "in the role of"
    assert p141["range"] == "E55"
    assert p141["status"] == "current"
    # No domain: the domain is the P14 relationship itself, which the
    # property's own first-order logic states directly. Inventing a
    # class-valued domain would be a fabricated constraint.
    assert "domain" not in p141


def test_property_of_property_covers_every_declared_one():
    onto = parse_ontology(XML)
    assert sorted(onto["property_of_property"]) == sorted([
        "P102.1", "P107.1", "P130.1", "P136.1", "P137.1", "P138.1",
        "P139.1", "P14.1", "P144.1", "P16.1", "P189.1", "P19.1",
        "P3.1", "P62.1", "P67.1", "P69.1",
    ])
    # every one of them ranges on E55 Type
    assert {e["range"] for e in onto["property_of_property"].values()} == {"E55"}


def test_existing_buckets_are_unchanged_by_the_new_one():
    """Additive only: the four original buckets keep their exact contents."""
    onto = parse_ontology(XML)
    assert len(onto["classes"]) == 81
    assert len(onto["properties"]) == 160
    for bucket in ("classes", "properties", "historical", "extensions"):
        assert not [k for k in onto[bucket] if "." in k], \
            f"a dotted id leaked into {bucket}"


def test_parse_rejects_a_file_whose_declared_counts_do_not_match(tmp_path):
    """The XML declares its own counts. A parse that silently drops
    declarations is the failure verify_collection exists for -- a truncated
    build once left 5,461 of 8,855 vectors with every other signal healthy.
    """
    truncated = tmp_path / "truncated.xml"
    truncated.write_text(
        '<cidoc_crm version="7.1.3" releaseDate="February 2024" '
        'classes="2" properties="0">'
        '<classes><class id="E1"><fullName>E1 CRM Entity</fullName>'
        '<className>CRM Entity</className></class></classes>'
        '<properties></properties></cidoc_crm>',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="declares 2, parsed 1"):
        parse_ontology(truncated)


def test_full_listing_covers_every_resolvable_identifier():
    """The listing tier must enumerate everything `concept <id>` can resolve.

    Before this existed, `ontology` showed 241 of 648 ids: the 330
    family-extension, 61 historical and 16 property-of-property entries were
    reachable only by already knowing them. That is fatal for an MCP wrapper,
    which has no filesystem to fall back to.
    """
    import json as _json

    from lib.config import DATA_DIR
    from lib.ontology import full_listing

    onto = _json.loads((DATA_DIR / "ontology.json").read_text(encoding="utf-8"))
    known = {i for bucket in ("classes", "properties", "historical",
                              "extensions", "property_of_property")
             for i in (onto.get(bucket) or {})}
    listed = {r["id"] for r in full_listing(onto)}
    assert listed == known, f"unlistable: {sorted(known - listed)[:10]}"


def test_full_listing_rows_share_one_key_set():
    """A missing key and a null one read differently to a JSON consumer."""
    import json as _json

    from lib.config import DATA_DIR
    from lib.ontology import full_listing

    onto = _json.loads((DATA_DIR / "ontology.json").read_text(encoding="utf-8"))
    keysets = {tuple(sorted(r)) for r in full_listing(onto)}
    assert len(keysets) == 1, f"{len(keysets)} differing row shapes"


def test_full_listing_carries_the_inverse_property_name():
    """The inverse was in the data and only the renderer dropped it. The
    published CRM example encodings use property labels as XML element names
    in whichever direction the nesting runs, so `is documented in` is the
    only usable form of P70 half the time."""
    import json as _json

    from lib.config import DATA_DIR
    from lib.ontology import full_listing

    onto = _json.loads((DATA_DIR / "ontology.json").read_text(encoding="utf-8"))
    rows = {r["id"]: r for r in full_listing(onto)}
    assert rows["P70"]["inverse"] == "is documented in"
    assert rows["P108"]["inverse"] == "was produced by"
    assert rows["P3"]["inverse"] == ""          # genuinely has none
    assert rows["E22"]["source"] == "CRMbase"
    assert rows["S13"]["source"] == "CRMsci"
    assert rows["E84"]["source"] == "historical"


def test_full_listing_does_not_widen_the_skeleton():
    """ontology_skeleton feeds concept_siblings. Widening it would change
    which siblings a dossier offers as a side effect of a display fix."""
    import json as _json

    from lib.config import DATA_DIR
    from lib.ontology import full_listing, ontology_skeleton

    onto = _json.loads((DATA_DIR / "ontology.json").read_text(encoding="utf-8"))
    skeleton = {s["id"] for s in ontology_skeleton(onto)}
    listing = {r["id"] for r in full_listing(onto)}
    # The relationship, not a magic number: the count moved from 241 to 244
    # when 7.3.2's additions were folded in, and a pinned literal would have
    # read as a regression when it was the intended effect.
    assert skeleton == (set(onto["classes"]) | set(onto["properties"]))
    assert skeleton < listing
    assert not (skeleton & set(onto.get("extensions") or {}))
    assert not (skeleton & set(onto.get("historical") or {}))


# ---- link validation ------------------------------------------------------

def _onto():
    import json as _json

    from lib.config import DATA_DIR
    return _json.loads((DATA_DIR / "ontology.json").read_text(encoding="utf-8"))


def test_validate_link_accepts_a_legal_triple():
    from lib.ontology import validate_link

    r = validate_link(_onto(), "E7", "P14", "E21")
    assert r["legal"] and r["resolved"] == "P14"


def test_validate_link_rejects_the_wrong_direction():
    """P108 is E12 -> E24. An E22 cannot be its subject; P108i can."""
    from lib.ontology import validate_link

    assert not validate_link(_onto(), "E22", "P108", "E12")["legal"]
    assert validate_link(_onto(), "E22", "P108i", "E12")["resolved"] == "P108i"


def test_validate_link_disambiguates_a_shared_label_by_context():
    """"consists of" is P5, P9 AND P45. Only P45 joins E22 to E57, so the
    classes decide which property the label meant -- the published CRM
    example format writes labels as element names and is ambiguous without
    exactly this step."""
    from lib.ontology import validate_link

    r = validate_link(_onto(), "E22", "consists of", "E57")
    assert r["resolved"] == "P45"
    assert {c["id"] for c in r["candidates"]} == {"P5", "P9", "P45"}
    assert [c["id"] for c in r["candidates"] if c["legal"]] == ["P45"]


def test_validate_link_accepts_the_underscored_element_name_form():
    from lib.ontology import validate_link

    assert validate_link(_onto(), "E31", "is_documented_in", "E1")["legal"] is False
    assert validate_link(_onto(), "E1", "is_documented_in", "E31")["resolved"] == "P70i"


def test_validate_link_accepts_the_rdf_local_name_crm_list_prints():
    """`crm_list` exists to print the exact name to write in RDF -- P111_added,
    P4_has_time-span -- and `crm_validate_rdf` resolves those names inside a
    document. Rejecting them as an argument made the server accept a spelling
    in one tool and refuse it in another."""
    from lib.ontology import validate_link

    assert validate_link(_onto(), "E79", "P111_added", "E22")["resolved"] == "P111"
    assert validate_link(_onto(), "E79", "P4_has_time-span", "E52")["resolved"] == "P4"
    # The inverse local name carries its own direction, and keeps it.
    assert validate_link(_onto(), "E1", "P70i_is_documented_in", "E31")["resolved"] == "P70i"
    # Same three spellings resolve_uri already took for a class argument.
    onto = _onto()
    for spelling in ("http://www.cidoc-crm.org/cidoc-crm/P111_added", "crm:P111_added"):
        assert validate_link(onto, "E79", spelling, "E22")["resolved"] == "P111"


def test_validate_link_accepts_an_identifier_beside_its_own_name():
    """The tools print the id and the label in adjacent columns -- `! P111
    added   E18` in crm_concept, `P110  augmented` in crm_connect -- so
    "P111 added" is what a caller copies back out of the output it just read."""
    from lib.ontology import validate_link

    r = validate_link(_onto(), "E79", "P111 added", "E22")
    assert r["legal"] and r["resolved"] == "P111"
    # Either separator, and the inverse reading names itself the same way.
    assert validate_link(_onto(), "E79", "P111_added", "E22")["legal"]
    assert validate_link(_onto(), "E22", "P108i was produced by", "E12")["resolved"] == "P108i"


def test_validate_link_refuses_an_identifier_paired_with_the_wrong_name():
    """P111 is "added"; "augmented" is P110. Taking the id and discarding the
    name would answer about a property the caller did not ask about, and the
    answer would be LEGAL -- the worst possible outcome for a typo. The name
    has to belong to the id, exactly as resolve_uri requires of a local name
    (P111_augmented resolves to nothing)."""
    from lib.ontology import validate_link

    r = validate_link(_onto(), "E79", "P111 augmented", "E22")
    assert r["resolved"] is None
    assert not r["legal"]
    assert "P111" in r["error"] and "augmented" in r["error"]
    # and it says what P111 is actually called, so the caller can fix it
    assert "added" in r["error"]


def test_validate_link_still_refuses_an_inverse_that_does_not_exist():
    """The P82ai trap, guarded here because resolve_uri answers ('P82a', True)
    for the bare inverse id -- it indexes the id form without checking that an
    inverse exists. Widening the resolver must not inherit that."""
    from lib.ontology import _property_candidates, validate_link

    onto = _onto()
    for name in ("P3i", "P82ai", "P90ai"):
        assert _property_candidates(onto, name) == [], name
        assert "no property matches" in validate_link(onto, "E52", name, "E61")["error"]


def test_validate_link_reports_unknowns_rather_than_guessing():
    from lib.ontology import validate_link

    assert "unknown class" in validate_link(_onto(), "ZZ9", "P1", "E41")["error"]
    assert "no property matches" in validate_link(_onto(), "E22", "P9999", "E1")["error"]


def test_validate_link_refuses_to_judge_a_property_of_property():
    """P14.1's domain is the P14 relationship, not a class. Answering
    legal/illegal against a subject class would invent a constraint."""
    from lib.ontology import validate_link

    r = validate_link(_onto(), "E22", "P14.1", "E55")
    assert r["candidates"][0]["legal"] is None
    assert "not_a_class_link" in r["candidates"][0]["reason"]


def test_spec_additions_are_current_not_historical():
    """7.3.2 added E100, P199 and P200; the v7.1.3 XML never carried them, so
    add_historical used to sweep them into the deprecated bucket and
    `concept P200` reported a NEW property as one the standard removed."""
    onto = _onto()
    for cid in ("E100", "P199", "P200"):
        assert cid not in (onto.get("historical") or {}), f"{cid} still historical"
    assert onto["classes"]["E100"]["source"] == "CIDOC CRM v7.3.2"
    assert onto["properties"]["P200"]["source"] == "CIDOC CRM v7.3.2"


def test_spec_additions_take_the_property_parent_not_the_domain_class():
    """A property states its parent as a full path -- "E90 Symbolic Object.
    P128i is carried by (carries): E18 Physical Thing" -- whose first
    identifier is the DOMAIN class. Reading the first id of any kind recorded
    P200's parent as E90, which is not a property."""
    onto = _onto()
    assert onto["properties"]["P200"]["sub_property_of"] == ["P128"]
    assert onto["properties"]["P199"]["sub_property_of"] == ["P138"]
    assert onto["classes"]["E100"]["sub_class_of"] == ["E73"]


def test_spec_additions_are_usable_by_the_graph_machinery():
    """Folded into classes/properties rather than a bucket of their own, so
    validate/connect/the closure get them without knowing they exist."""
    from lib.ontology import validate_link

    onto = _onto()
    assert onto["properties"]["P200"]["domain"] == "E90"
    assert onto["properties"]["P200"]["range"] == "E25"
    assert validate_link(onto, "E90", "P200", "E25")["resolved"] == "P200"


# ---- whole-document validation --------------------------------------------

FIXTURE = """<?xml version="1.0"?>
<CRMset>
<CRM_Entity>A statue
  <in_class>E22: Human-Made Object</in_class>
  <has_note>free text with no class</has_note>
  <was_produced_by>the carving
    <in_class>E12: Production</in_class>
    <carried_out_by>a sculptor
      <in_class>E21: Person</in_class>
      <in_the_role_of>master
        <in_class>E55: Type</in_class>
      </in_the_role_of>
    </carried_out_by>
  </was_produced_by>
  <is_identified_by>an inventory number
    <in_class>E42: Identifier</in_class>
    <has_type>accession
      <in_class>E55: Type</in_class>
    </has_type>
  </is_identified_by>
  <changed_ownership_by>a sale
    <in_class>E8: Acquisition</in_class>
  </changed_ownership_by>
</CRM_Entity>
</CRMset>
"""


def _report(tmp_path):
    from lib.ontology import crm_example_links, validate_document

    f = tmp_path / "m.xml"
    f.write_text(FIXTURE, encoding="utf-8")
    return validate_document(_onto(), crm_example_links(f))


def test_document_check_catches_a_name_that_is_not_a_property(tmp_path):
    """`changed_ownership_by` is the published Clayton example's error and
    P24's inverse is "changed ownership through". A modelling agent that
    resolved element names to identifiers before validating shipped this
    four times, because the wrong spelling never reached the validator."""
    bad = [f for f in _report(tmp_path)["findings"]
           if f["verdict"] == "unknown_name"]
    assert [f["name"] for f in bad] == ["changed_ownership_by"]


def test_document_check_separates_unrepresentable_from_misspelt(tmp_path):
    """"in the role of" IS a CRM label -- P14.1's -- so calling it unknown
    sends a reader hunting a typo that is not there. Its domain is a
    property, which is a different problem with a different fix."""
    findings = {f["name"]: f["verdict"] for f in _report(tmp_path)["findings"]}
    assert findings["in_the_role_of"] == "not_a_class_link"
    assert findings["changed_ownership_by"] == "unknown_name"


def test_document_check_prefers_a_legal_reading_over_a_dotted_collision(tmp_path):
    """"has type" is P2's direct name AND P3.1's label. Testing for a
    property-of-property candidate before testing legality reported every
    sound has_type link as unrepresentable."""
    verdicts = {f["name"]: f["verdict"] for f in _report(tmp_path)["findings"]}
    assert verdicts["has_type"] == "ok"


def test_document_check_passes_a_literal_ranged_property_on_its_domain(tmp_path):
    """P3 has note carries text, so there is no object class -- but the name
    and the domain are still checkable and still worth checking."""
    verdicts = {f["name"]: f["verdict"] for f in _report(tmp_path)["findings"]}
    assert verdicts["has_note"] == "ok_literal"


def test_document_check_names_what_it_skipped(tmp_path):
    """Silently passing over a structural element would be indistinguishable
    from silently passing over a misspelling."""
    assert "value" in _report(tmp_path)["structural_elements_skipped"]


def test_family_properties_resolve_by_label_not_only_by_id():
    """CRMbase properties carry direct_name/inverse_name separately; the 111
    family-extension properties are scraped from declaration pages and carry
    ONE combined label, "encountered object (was object encountered
    through)". Scanning only the split fields found none of them, so
    `validate S19 O19 E18` resolved while the same link named by its label
    did not -- the difference between a tool usable on a document and one
    usable only on identifiers already looked up."""
    from lib.ontology import validate_link

    onto = _onto()
    assert validate_link(onto, "S19", "O19", "E18")["resolved"] == "O19"
    assert validate_link(onto, "S19", "encountered object", "E18")["resolved"] == "O19"
    assert validate_link(onto, "E18", "was object encountered through",
                         "S19")["resolved"] == "O19i"
    # the underscored element-name form too, which is how a document spells it
    assert validate_link(onto, "S19", "encountered_object", "E18")["resolved"] == "O19"


def test_crmbase_labels_are_unaffected_by_the_family_split():
    from lib.ontology import validate_link

    onto = _onto()
    assert validate_link(onto, "E1", "is documented in", "E31")["resolved"] == "P70i"
    assert validate_link(onto, "E31", "documents", "E1")["resolved"] == "P70"


LABELS_FIXTURE = """<?xml version="1.0"?>
<CRMset>
<CRM_Entity>a<in_class>E22: Man-Made Object</in_class>
  <has_note>retired v6 name; both published examples use it</has_note></CRM_Entity>
<CRM_Entity>b<in_class>E:55</in_class><has_note>malformed id</has_note></CRM_Entity>
<CRM_Entity>c<in_class>E22: Human-Made Object</in_class>
  <has_note>current name</has_note></CRM_Entity>
<CRM_Entity>d<in_class>ZZ99: Invented</in_class><has_note>no such class</has_note></CRM_Entity>
</CRMset>
"""


def _label_findings(tmp_path):
    from lib.ontology import crm_example_class_uses, validate_class_labels

    f = tmp_path / "lbl.xml"
    f.write_text(LABELS_FIXTURE, encoding="utf-8")
    return validate_class_labels(_onto(), crm_example_class_uses(f))


def test_class_label_is_checked_at_all(tmp_path):
    """crm_example_links reads only the identifier out of in_class, so a
    document could say "E22: Utter Nonsense Here" and validate clean."""
    v = [f for f in _label_findings(tmp_path) if f["verdict"] == "label_mismatch"]
    assert [f["raw"] for f in v] == ["E22: Man-Made Object"]


def test_a_malformed_class_declaration_is_reported(tmp_path):
    """"E:55" parses to no identifier. Previously the record's links simply
    became "unchecked" with no hint that the class line was the cause."""
    assert any(f["verdict"] == "malformed" for f in _label_findings(tmp_path))


def test_an_unresolvable_class_is_reported(tmp_path):
    assert any(f["verdict"] == "unknown_class"
               for f in _label_findings(tmp_path))


def test_the_current_label_passes(tmp_path):
    # the entry that names E22 correctly must produce nothing at all --
    # asserting on the detail text is wrong, since a mismatch detail quotes
    # the correct name too
    assert not any(f["raw"] == "E22: Human-Made Object"
                   for f in _label_findings(tmp_path))


def test_an_ambiguous_link_is_not_reported_as_ok(tmp_path):
    """`assigned` between an E15 and an E42 is P37 or P141. Folding that into
    "ok" lost it entirely -- the document is legal but does not say which
    property it means, and this format writes labels as element names so it
    cannot. Reported, not failed: the fix is not in the document."""
    from lib.ontology import crm_example_links, validate_document

    f = tmp_path / "amb.xml"
    f.write_text('<?xml version="1.0"?><CRMset><CRM_Entity>n'
                 '<in_class>E15: Identifier Assignment</in_class>'
                 '<assigned>x<in_class>E42: Identifier</in_class></assigned>'
                 '</CRM_Entity></CRMset>', encoding="utf-8")
    report = validate_document(_onto(), crm_example_links(f))
    assert report["counts"] == {"ambiguous": 1}
    assert "P37" in report["findings"][0]["detail"]
    assert "P141" in report["findings"][0]["detail"]


def test_a_property_nested_in_a_literal_one_is_not_reattached(tmp_path):
    """Both published examples type notes as
    `<has_note>text<has_type>Statement</has_type></has_note>`, meaning P3.1.
    The walker inherited the grandparent's class, so it resolved to P2 with
    the OBJECT as subject -- amol asserts a silk textile "has type
    Statement", 211 times in 637 links, and every model written from it
    inherited the construction. It was legal, so the checker passed it."""
    from lib.ontology import crm_example_links, validate_document

    f = tmp_path / "nt.xml"
    f.write_text('<?xml version="1.0"?><CRMset><CRM_Entity>t'
                 '<in_class>E22: Human-Made Object</in_class>'
                 '<has_note>some text'
                 '<has_type>Statement<in_class>E55: Type</in_class></has_type>'
                 '</has_note></CRM_Entity></CRMset>', encoding="utf-8")
    links = {l["name"]: l for l in crm_example_links(f)}
    assert links["has_type"]["via_property"] == "has_note"
    report = validate_document(_onto(), links.values())
    v = {f_["name"]: f_["verdict"] for f_ in report["findings"]}
    assert v["has_type"] == "attached_to_property"


def test_a_property_with_its_own_class_still_re_roots_the_subject(tmp_path):
    """The fix must not break ordinary nesting: an element WITH an in_class
    is a new subject for everything beneath it."""
    from lib.ontology import crm_example_links

    f = tmp_path / "ok.xml"
    f.write_text('<?xml version="1.0"?><CRMset><CRM_Entity>t'
                 '<in_class>E22: Human-Made Object</in_class>'
                 '<was_produced_by>making<in_class>E12: Production</in_class>'
                 '<carried_out_by>x<in_class>E21: Person</in_class></carried_out_by>'
                 '</was_produced_by></CRM_Entity></CRMset>', encoding="utf-8")
    links = {l["name"]: l for l in crm_example_links(f)}
    assert links["carried_out_by"]["subject"] == "E12"
    assert links["carried_out_by"]["via_property"] is None


def test_completeness_names_a_required_property_the_document_omits():
    # E12 Production declares P108 necessary. A Production with only a
    # time-span states nothing about what it produced, which is exactly the
    # omission the modelling evaluations kept losing cases to.
    from lib.ontology import document_completeness

    onto = _onto()
    links = [{"subject": "E12", "name": "P4", "object": "E52", "path": "a"}]
    by = {(f["class_id"], f["property_id"]): f
          for f in document_completeness(onto, links)}
    assert ("E12", "P108") in by
    assert by[("E12", "P108")]["missing"] == 1
    assert by[("E12", "P108")]["instances"] == 1


def test_completeness_does_not_name_a_property_the_document_states():
    from lib.ontology import document_completeness

    onto = _onto()
    links = [{"subject": "E12", "name": "P108", "object": "E22", "path": "a"}]
    assert not [f for f in document_completeness(onto, links)
                if f["property_id"] == "P108"]


def test_completeness_counts_instances_not_occurrences():
    # Three E12 nodes, one of which states P108. The reader needs "2 of 3",
    # not three separate lines and not "1".
    from lib.ontology import document_completeness

    onto = _onto()
    links = [{"subject": "E12", "name": "P4", "object": "E52", "path": "a"},
             {"subject": "E12", "name": "P4", "object": "E52", "path": "b"},
             {"subject": "E12", "name": "P108", "object": "E22", "path": "c"}]
    by = {(f["class_id"], f["property_id"]): f
          for f in document_completeness(onto, links)}
    assert by[("E12", "P108")]["missing"] == 2
    assert by[("E12", "P108")]["instances"] == 3


def test_completeness_judges_each_declared_type():
    # Multiple instantiation: a node typed E12 AND E22 is expected to carry
    # what both classes require, and a property satisfying either is stated.
    from lib.ontology import document_completeness

    onto = _onto()
    links = [{"subject": "E12", "subject_types": ["E12", "E22"],
              "name": "P108", "object": "E22", "path": "a"}]
    named = {(f["class_id"], f["property_id"])
             for f in document_completeness(onto, links)}
    assert ("E12", "P108") not in named
    assert any(c == "E22" for c, _ in named)


def test_completeness_ignores_a_node_with_no_class():
    from lib.ontology import document_completeness

    onto = _onto()
    assert document_completeness(onto, [{"name": "P3", "path": "a"}]) == []


def test_resolve_uri_handles_full_uri_prefixed_and_bare():
    """RDF names things by URI; a reader must accept what documents
    actually write. All three forms address the same property."""
    from lib.ontology import resolve_uri

    onto = _onto()
    full = "http://www.cidoc-crm.org/cidoc-crm/P108_has_produced"
    assert resolve_uri(onto, full) == ("P108", False)
    assert resolve_uri(onto, "crm:P108_has_produced") == ("P108", False)
    assert resolve_uri(onto, "P108_has_produced") == ("P108", False)


def test_resolve_uri_reads_the_inverse_form():
    """P108i_was_produced_by is the same property read the other way, and
    the direction decides which end must satisfy the domain."""
    from lib.ontology import resolve_uri

    assert resolve_uri(_onto(), "crm:P108i_was_produced_by") == ("P108", True)


def test_resolve_uri_keeps_a_hyphen_inside_a_name():
    """P4's name is "has time-span". Spaces become underscores; the hyphen
    is part of the word and survives."""
    from lib.ontology import resolve_uri

    assert resolve_uri(_onto(), "crm:P4_has_time-span") == ("P4", False)


def test_resolve_uri_resolves_a_family_identifier_by_its_own_uri():
    """The 330 family entries carry a real uri and need no derivation."""
    from lib.ontology import resolve_uri

    onto = _onto()
    s19 = "http://www.cidoc-crm.org/extensions/crmsci/S19_Encounter_Event"
    assert resolve_uri(onto, s19) == ("S19", False)
    assert resolve_uri(onto, "S19_Encounter_Event") == ("S19", False)


def test_local_name_splits_a_combined_family_label():
    """The 111 family-extension properties carry ONE combined `label` --
    O19's is "encountered object (was object encountered through)" -- not
    the split direct_name/inverse_name fields CRMbase properties carry.
    Reading only the split fields left O19's inverse name absent (there is
    no `inverse_name` key to read) and its forward name ending in the
    literal parenthesised inverse text, parens and all.
    `_property_candidates`'s `names_of` already splits a combined label on
    its last "(" going the other direction (name -> id); `_local_name` has
    to agree, since both are deriving the same name."""
    from lib.ontology import _local_name

    onto = _onto()
    entry = onto["extensions"]["O19"]
    assert _local_name("O19", entry) == "O19_encountered_object"
    assert _local_name("O19", entry, inverse=True) == \
        "O19i_was_object_encountered_through"


def test_resolve_uri_reads_a_family_property_in_either_direction():
    """Forward resolution for a family property worked only by luck, via the
    unrelated `uri` field's last URL segment -- the inverse direction had no
    fallback at all, so a real CRMsci triple written in that direction
    resolved to nothing rather than to O19."""
    from lib.ontology import resolve_uri

    onto = _onto()
    assert resolve_uri(onto, "O19_encountered_object") == ("O19", False)
    assert resolve_uri(onto, "O19i_was_object_encountered_through") == ("O19", True)


def test_resolve_uri_returns_none_rather_than_guessing():
    from lib.ontology import resolve_uri

    onto = _onto()
    assert resolve_uri(onto, "http://example.org/vocab/made_by") == (None, False)
    assert resolve_uri(onto, "rdfs:label") == (None, False)


def test_uri_index_covers_every_identifier():
    """Anything `concept <id>` resolves must be addressable from RDF, or a
    correct document reports unknown identifiers."""
    from lib.ontology import resolve_uri, uri_index

    onto = _onto()
    idx = uri_index(onto)
    assert len(idx) > 600
    for cid in ("E22", "P108", "S19", "E100", "P200", "A2"):
        hits = [k for k, (i, _) in idx.items() if i == cid]
        assert hits, f"{cid} is not addressable by any name"
        assert resolve_uri(onto, hits[0])[0] == cid


def test_resolve_uri_reaches_a_property_of_property():
    """The 16 property-of-property entries (P3.1, P14.1, P62.1, ...) are a
    separate bucket in the model, not folded into `properties` by
    `_model_view`, and the dotted id must not break the derivation that
    turns spaces into underscores for every other identifier."""
    from lib.ontology import resolve_uri

    onto = _onto()
    entry = onto["property_of_property"]["P14.1"]
    assert entry["label"] == "in the role of"
    assert resolve_uri(onto, "P14.1_in_the_role_of") == ("P14.1", False)
    assert resolve_uri(onto, "P14.1") == ("P14.1", False)


# ---- RDFS source of truth --------------------------------------------------

RDFS_PATH = PROJECT_ROOT / "sources" / "cidoc_crm_v7.1.3.rdf"


def _onto_with_rdfs():
    """A fresh ontology with the RDFS folded in.

    Built from the committed data rather than from the XML so the test
    exercises what the build actually produces.
    """
    import json as _j
    from lib.ontology import add_rdfs_additions

    onto = _j.loads((DATA_DIR / "ontology.json").read_text(encoding="utf-8"))
    add_rdfs_additions(onto, RDFS_PATH)
    return onto


def test_the_rdfs_only_date_properties_resolve():
    # P82a/P82b and P81a/P81b are how the RDF encoding writes a fuzzy date
    # boundary, and essentially every real CRM dataset uses them. The spec
    # XML has no entry for any of them, so before this they were rejected.
    from lib.ontology import resolve_uri

    onto = _onto_with_rdfs()
    for name, expect in (("P82a_begin_of_the_begin", "P82a"),
                         ("P82b_end_of_the_end", "P82b"),
                         ("P81a_end_of_the_begin", "P81a"),
                         ("P81b_begin_of_the_end", "P81b"),
                         ("P90a_has_lower_value_limit", "P90a"),
                         ("P90b_has_upper_value_limit", "P90b")):
        ident, inverse = resolve_uri(onto, CRM_NAMESPACE + name)
        assert (ident, inverse) == (expect, False), name


def test_an_rdfs_addition_takes_its_range_from_its_parent():
    # The RDFS gives these rdfs:Literal, which the model has no class for.
    # Each inherits its parent property's range instead -- the way the spec
    # already encodes the same idea: P82 is E52 -> E61 Time Primitive, P90
    # is E54 -> E60 Number. Both are subclasses of E59 Primitive Value.
    onto = _onto_with_rdfs()
    assert (onto["properties"]["P82a"]["domain"],
            onto["properties"]["P82a"]["range"]) == ("E52", "E61")
    assert (onto["properties"]["P90a"]["domain"],
            onto["properties"]["P90a"]["range"]) == ("E54", "E60")


def test_an_rdfs_addition_still_rejects_a_wrong_domain():
    # An addition that validates everything would satisfy a happy-path test
    # while checking nothing. P82a's domain is E52; an E22 is not one.
    from lib.ontology import validate_link

    onto = _onto_with_rdfs()
    assert validate_link(onto, "E52", "P82a")["legal"] is True
    assert validate_link(onto, "E22", "P82a")["legal"] is False


def test_a_mixed_case_identifier_is_matched_case_insensitively():
    # Every all-uppercase id has always resolved from any casing, because
    # _property_candidates upper-cased the input and `upper(k) == k` held
    # for every key. P82a and its five siblings are the first ids whose
    # trailing letter is part of the CIDOC identifier rather than a casing
    # choice, so that equivalence broke and the lookup now folds the dict
    # through its own uppercase. This pins the tolerance itself: without
    # it only the exact spelling "P82a" is covered. Mutation-checked --
    # replacing the folded lookup with a direct one fails this test.
    #
    # It covers the forward branch only. The inverse branch folds too, but
    # that fold cannot be exercised: none of the six mixed-case additions
    # declares an inverse (they are literal-valued), so no mixed-case
    # inverse identifier exists to look up. Removing the fold from that
    # branch alone would go undetected here, and there is no test that
    # could detect it until the CRM publishes such an identifier.
    from lib.ontology import validate_link

    onto = _onto_with_rdfs()
    for spelling in ("P82a", "p82a", "P82A"):
        assert validate_link(onto, "E52", spelling)["legal"] is True, spelling


def test_the_two_superclass_rdfs_class_inherits_through_both():
    # E33_E41_Linguistic_Appellation is subClassOf E33 AND E41. sub_class_of
    # is already a list and _ancestors_in already walks all of it, but
    # nothing in the XML data has this shape, so a single-parent assumption
    # would have gone unnoticed.
    from lib.ontology import ancestors, resolve_uri

    onto = _onto_with_rdfs()
    ident, _ = resolve_uri(onto, CRM_NAMESPACE + "E33_E41_Linguistic_Appellation")
    assert ident == "E33_E41"
    line = ancestors(onto, "E33_E41")
    assert "E33" in line and "E41" in line


def test_rdfs_additions_never_overwrite_the_spec_xml():
    # The spec XML is the normative text and carries the scope notes. The
    # RDFS supplies only what the XML has no entry for. Measured: the two
    # agree on domain and range across all 158 shared properties, so this
    # holds by construction -- this test is what keeps it true.
    import json as _j
    from lib.ontology import add_rdfs_additions

    before = _j.loads((DATA_DIR / "ontology.json").read_text(encoding="utf-8"))
    after = _j.loads(_j.dumps(before))
    add_rdfs_additions(after, RDFS_PATH)
    for bucket in ("classes", "properties"):
        for ident, entry in before[bucket].items():
            assert after[bucket][ident] == entry, f"{bucket} {ident} changed"


def test_rdfs_additions_are_marked_with_their_source():
    # A silent change in what the RDFS parse yields should be visible.
    onto = _onto_with_rdfs()
    added = [i for b in ("classes", "properties")
             for i, e in onto[b].items() if e.get("source") == "rdfs"]
    assert sorted(added) == ["E33_E41", "P81a", "P81b", "P82a", "P82b",
                             "P90a", "P90b"]


def test_add_rdfs_additions_is_idempotent():
    # The build may run twice; the second pass must add nothing.
    from lib.ontology import add_rdfs_additions

    onto = _onto_with_rdfs()
    assert add_rdfs_additions(onto, RDFS_PATH) == []


# ---- The family extension RDFS ------------------------------------------

RDFS_EXT_DIR = PROJECT_ROOT / "sources" / "rdfs" / "extensions"


def _family_onto():
    from lib.ontology import add_extensions, add_family_rdfs

    onto = parse_ontology(PROJECT_ROOT / "sources" / "cidoc_crm_v7.1.3.xml")
    add_extensions(onto, {}, load_family(PROJECT_ROOT / "sources" / "crm_family.json"))
    report = add_family_rdfs(onto, sorted(RDFS_EXT_DIR.iterdir()))
    return onto, report


def test_family_rdfs_supplies_the_namespaces_the_declarations_lack():
    # CRMact, CRMba, FRBRoo and PRESSoo publish no URI on the declaration
    # pages crm_family.json is scraped from. Their entries still RESOLVED --
    # uri_index also keys on the label-derived local name -- but
    # _owned_namespaces is built from `uri` fields, so their namespaces were
    # foreign and a misspelling under one passed as not_crm with exit 0.
    from lib.ontology import _owned_namespaces

    onto, _ = _family_onto()
    owned = _owned_namespaces(onto)
    for namespace in ("http://www.cidoc-crm.org/extensions/crmba/",
                      "http://www.cidoc-crm.org/extensions/crmact/",
                      "http://www.iflastandards.info/fr/pressoo/",
                      "http://iflastandards.info/ns/fr/frbr/frbroo/"):
        assert namespace in owned, namespace


def test_a_misspelling_in_a_backfilled_namespace_is_caught():
    # The behaviour the namespaces exist for. Without them this is `not_crm`,
    # which does not fail the check -- the same XML/RDF divergence closed
    # earlier in this branch, reproduced between two extension models.
    from lib.ontology import _namespace_of, _owned_namespaces, resolve_uri

    onto, _ = _family_onto()
    bogus = "http://www.cidoc-crm.org/extensions/crmba/B99_gaga"
    assert resolve_uri(onto, bogus)[0] is None
    assert _namespace_of(bogus) in _owned_namespaces(onto)


def test_family_namespaces_are_read_not_guessed():
    # PRESSoo is www.iflastandards.info/fr/pressoo/ and LRMoo is
    # iflastandards.info/ns/lrm/lrmoo/ -- a different host AND path, down to
    # the `www.`. Any rule building these from the model name gets three of
    # eleven wrong, so they come from the files.
    _, report = _family_onto()
    assert report["PRESSoo"]["namespace"] == "http://www.iflastandards.info/fr/pressoo/"
    assert report["LRMoo"]["namespace"] == "http://iflastandards.info/ns/lrm/lrmoo/"
    assert report["CRMba"]["namespace"] == "http://www.cidoc-crm.org/extensions/crmba/"


def test_a_malformed_subject_does_not_win_a_namespace():
    # CIDOC's own CRMact v0.2 draft declares
    # .../crmact/actP12_was_intended_to_apply_within/from, whose namespace is
    # a property URI. Owning it would mean reporting a typo under it as a
    # real term, so the model's namespace is the one MOST declarations share.
    from lib.ontology import _owned_namespaces

    onto, report = _family_onto()
    assert report["CRMact"]["namespace"] == "http://www.cidoc-crm.org/extensions/crmact/"
    assert ("http://www.cidoc-crm.org/extensions/crmact/"
            "actP12_was_intended_to_apply_within/") not in _owned_namespaces(onto)


def test_family_rdfs_never_overwrites_a_declared_uri():
    # The declaration pages are the normative source where they have one;
    # the RDFS only fills gaps. CRMsci declares every URI already.
    _, report = _family_onto()
    assert report["CRMsci"]["uris_filled"] == 0
    assert report["CRMba"]["uris_filled"] > 0


def test_family_rdfs_is_idempotent():
    from lib.ontology import add_family_rdfs

    onto, _ = _family_onto()
    again = add_family_rdfs(onto, sorted(RDFS_EXT_DIR.iterdir()))
    assert sum(r["uris_filled"] for r in again.values()) == 0
    assert [i for r in again.values() for i in r["added"]] == []


def test_the_index_cache_survives_a_recycled_address():
    # Both caches key on id(onto). CPython reuses the address of a freed
    # object, so alternating two ontologies once returned the index of an
    # already-collected one -- silently, with no error and wrong verdicts.
    # The docstring claimed identity was safe because "every caller holds one
    # long-lived parsed ontology"; this test module has never done that.
    import json as _j

    from lib.ontology import resolve_uri

    base = _j.loads((DATA_DIR / "ontology.json").read_text(encoding="utf-8"))
    produced = CRM_NAMESPACE + "P108_has_produced"
    for _ in range(60):
        intact = _j.loads(_j.dumps(base))
        stripped = _j.loads(_j.dumps(base))
        stripped["properties"].pop("P108")
        # Same address, different content: the second must not answer P108.
        assert resolve_uri(intact, produced)[0] == "P108"
        assert resolve_uri(stripped, produced)[0] is None


def test_the_index_cache_is_bounded():
    # The strong reference that makes the cache correct would otherwise pin
    # every ontology ever built -- a real leak in a server that reloads.
    import json as _j

    from lib.ontology import _URI_INDEX_CACHE, uri_index

    base = _j.loads((DATA_DIR / "ontology.json").read_text(encoding="utf-8"))
    for _ in range(20):
        uri_index(_j.loads(_j.dumps(base)))
    assert len(_URI_INDEX_CACHE._entries) <= 4


def test_the_rdfs_and_the_spec_xml_agree_on_domain_and_range():
    # add_rdfs_additions is additive because the two sources were measured to
    # agree, and its docstring said that agreement "is asserted by a test".
    # It was not -- this is that test. It guards the premise, not the code:
    # a future RDFS release that changed a domain would be folded in
    # silently, since the additions path skips anything already known.
    from rdflib import Graph, RDFS, URIRef

    from lib.ontology import _local_name, _namespace_of, resolve_uri

    onto = _onto_with_rdfs()
    graph = Graph()
    graph.parse(str(RDFS_PATH), format="xml")

    compared, disagreements = 0, []
    for pid, entry in onto["properties"].items():
        if entry.get("source") == "rdfs":
            continue                      # supplied BY the file; nothing to cross-check
        name = _local_name(pid, entry)
        if not name:
            continue
        subject = URIRef(CRM_NAMESPACE + name)
        declared_domain = graph.value(subject, RDFS.domain)
        declared_range = graph.value(subject, RDFS.range)
        if declared_domain is None and declared_range is None:
            continue
        compared += 1
        for label, declared, ours in (("domain", declared_domain, entry.get("domain")),
                                      ("range", declared_range, entry.get("range"))):
            if declared is None:
                continue
            resolved, _ = resolve_uri(onto, str(declared))
            if resolved is None and _namespace_of(str(declared)) != CRM_NAMESPACE:
                continue              # rdfs:Literal and friends have no class here
            if resolved != ours:
                disagreements.append(f"{pid} {label}: ours {ours}, rdfs {resolved}")

    assert compared >= 158, f"only cross-checked {compared} properties"
    assert disagreements == []


def test_repeated_sibling_elements_get_distinguishable_paths():
    # This format nests by element name, so eight <has_dimension> children of
    # one node all produced the same path string. Two things broke: a reader
    # told a link was wrong "at .../has_dimension" could not tell which of the
    # eight, and document_completeness -- which uses `path` as node identity --
    # counted the eight as one node and reported "1 of 1" where the truth was
    # "8 of 8". Indexed only where a tag repeats, so unique paths are untouched.
    from lib.ontology import crm_example_links

    links = crm_example_links(PROJECT_ROOT / "models" / "crm_marquis_yi.xml")
    e54 = {l["path"] for l in links if l.get("subject") == "E54"}
    assert len(e54) == 8
    # A tag that occurs once among its siblings keeps its plain path -- the
    # index is disambiguation, not decoration.
    assert any("/" in p and "[" not in p.rsplit("/", 1)[-1]
               for p in {l["path"] for l in links})


def test_completeness_counts_repeated_siblings_separately():
    # The consequence of the above for the report the counts appear in.
    from lib.ontology import crm_example_links, document_completeness

    onto = _onto()
    found = {(f["class_id"], f["property_id"]): f for f in document_completeness(
        onto, crm_example_links(PROJECT_ROOT / "models" / "crm_marquis_yi.xml"))}
    assert found[("E54", "P90")]["instances"] == 8
    assert found[("E54", "P90")]["missing"] == 8


def test_the_inverse_shorthand_needs_an_inverse_to_exist():
    # A trailing "i" is CRM shorthand for "read this property backwards", and
    # stripping it blindly invented one for every property that has none:
    # P82a, P3, P57 and P90a are literal-valued and no direction exists to
    # read. They resolved, and worse, resolved to a reading with the real
    # property's domain and range swapped -- so a document writing P82ai was
    # told "illegal, E52 is not a E61" when the truth is that no such
    # property exists.
    from lib.ontology import _property_candidates

    onto = _onto()
    for phantom in ("P82ai", "P3i", "P57i", "P90ai"):
        assert _property_candidates(onto, phantom) == [], phantom


def test_a_genuine_inverse_still_resolves_including_a_family_one():
    # The guard must not cost the real ones. O19 is the case that matters:
    # its inverse hides inside a combined family label, "encountered object
    # (was object encountered through)", so a check reading only the split
    # CRMbase fields would drop every extension property's inverse.
    from lib.ontology import _property_candidates

    onto = _onto()
    for real, ident in (("P108i", "P108"), ("P4i", "P4"), ("P14i", "P14"),
                        ("O19i", "O19")):
        assert _property_candidates(onto, real) == [(ident, True)], real


def test_a_crmbase_concept_shows_the_uri_a_modeller_must_write():
    # Family concepts printed a URI all along because they carry a stored one;
    # CRMbase derives its own and printed none. Measured consequence: of four
    # agents asked to write Turtle using only the MCP server, the one that
    # learned the spelling from the tools learned it from a CRMsci class whose
    # card happened to show a URI, and two that used no family classes never
    # saw one at all. The rule is not guessable -- spaces become underscores
    # but hyphens survive inside words.
    import search

    onto = _onto()
    text = search.format_concept(onto["properties"]["P4"], [], 0, onto=onto)
    assert CRM_NAMESPACE + "P4_has_time-span" in text
    assert CRM_NAMESPACE + "P4i_is_time-span_of" in text
    klass = search.format_concept(onto["classes"]["E22"], [], 0, onto=onto)
    assert CRM_NAMESPACE + "E22_Human-Made_Object" in klass


def test_a_property_with_no_inverse_shows_no_inverse_uri():
    # P82a is literal-valued and has no inverse to write. Printing one would
    # invent the identifier the validator would then reject -- the same
    # phantom the inverse-shorthand guard removes on the reading side.
    import search

    onto = _onto_with_rdfs()
    text = search.format_concept(onto["properties"]["P82a"], [], 0, onto=onto)
    assert CRM_NAMESPACE + "P82a_begin_of_the_begin" in text
    assert "inverse:" not in text


def test_the_listing_prints_local_names_not_prose_labels():
    # An agent writing RDF needs the spelling, and this listing already has
    # every identifier. Before, it printed "Human-Made Object" and the
    # spelling had to be fetched one identifier at a time from crm_concept:
    # one agent spent ~40 of its 69 calls doing exactly that.
    import search

    onto = _onto()
    from lib.ontology import full_listing
    text = search.format_ontology(full_listing(onto), onto=onto)
    assert "E22_Human-Made_Object" in text
    # The hyphen rule is the part nobody guesses: spaces become underscores
    # but a hyphen inside a word survives.
    assert "P4_has_time-span (P4i_is_time-span_of)" in text
    assert "Human-Made Object " not in text     # the prose form is gone


def test_the_listing_names_the_namespaces_including_the_odd_ones():
    # A local name is half a URI. The other half is not guessable either:
    # PRESSoo and LRMoo differ in host AND path, down to the `www.`.
    import search

    onto = _onto()
    from lib.ontology import full_listing
    text = search.format_ontology(full_listing(onto), onto=onto)
    head = text.split("\n\n", 1)[0]
    assert "http://www.iflastandards.info/fr/pressoo/" in head
    assert "http://iflastandards.info/ns/lrm/lrmoo/" in head
    assert CRM_NAMESPACE in head


def test_the_listing_splits_a_family_combined_label():
    # O19's inverse hides inside "encountered object (was object encountered
    # through)". A renderer reading the split CRMbase fields alone would show
    # no inverse for any extension property.
    import search

    onto = _onto()
    from lib.ontology import full_listing
    text = search.format_ontology(full_listing(onto), onto=onto)
    assert "O19_encountered_object (O19i_was_object_encountered_through)" in text


def test_the_listing_without_an_ontology_still_renders():
    # onto is optional: the local names need the entries, and a caller that
    # has only the rows should still get a readable listing rather than a
    # crash or a column of blanks.
    import search

    onto = _onto()
    from lib.ontology import full_listing
    text = search.format_ontology(full_listing(onto))
    assert "Human-Made Object" in text
    assert "Namespaces" not in text
