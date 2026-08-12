"""Hover titles on identifiers in the review page.

A reader sees "E12" and "P108i" in dense prose and in chips. The identifier
alone tells them nothing -- the same defect the concept dossier fixes on the
CLI side, where `P177` sat 17th in a list of anonymous integers for E13 and
was missed. The page now carries the full name in a `title`, so hovering
answers without leaving the page.
"""

import re

from tools.make_review_html import ident_names, ident_title, marked


def test_class_and_property_titles_carry_the_full_name():
    assert ident_title("E12") == "E12 Production"
    assert ident_title("P108").startswith("P108 has produced")


def test_inverse_direction_gets_the_inverse_name_not_the_forward_one():
    """P108i is the same property read the other way, and the reader is
    looking at the inverse label. Showing "has produced" for "was produced
    by" would be a wrong tooltip, which is worse than none."""
    title = ident_title("P108i")
    assert "was produced by" in title
    assert "inverse of P108" in title


def test_property_of_property_names_its_parent():
    """P14.1 is meaningless without P14."""
    title = ident_title("P14.1")
    assert "in the role of" in title
    assert "P14" in title


def test_historical_identifier_says_it_is_deprecated_not_unknown():
    assert "deprecated" in ident_title("E84")


def test_extension_identifier_carries_its_model():
    assert "CRMsci" in ident_title("S13")
    assert "CRMarchaeo" in ident_title("A2")


def test_document_chunk_id_resolves_through_to_the_concept():
    assert ident_title("crm732#E12").startswith("E12 Production")
    assert "narrative" in ident_title("crm732#s0042")


def test_unknown_identifiers_get_no_title_rather_than_a_guess():
    """A missing tooltip is invisible; a wrong one is a lie."""
    assert ident_title("E99999") == ""
    assert ident_title("t0408") == ""      # threads are not ontology concepts


def test_marked_emits_a_title_only_where_one_is_known():
    out = marked("Use E12 with P108i, per t0408.")
    assert '<code title="E12 Production">E12</code>' in out
    assert '<code>t0408</code>' in out     # no title, no empty attribute


def test_marked_escapes_the_title_it_injects():
    """`text` is escaped before substitution but the title is not; it comes
    from scope-note names that contain quotes and ampersands. An unescaped
    title would break out of the attribute."""
    for ident, title in ident_names().items():
        if '"' in title or "&" in title or "<" in title:
            out = marked(ident)
            assert '&quot;' in out or '&amp;' in out or '&lt;' in out, ident
            break


def test_marked_still_escapes_the_body_text():
    out = marked('a "quoted" & <tagged> phrase')
    assert "&quot;" in out and "&amp;" in out and "&lt;" in out
    assert "<tagged>" not in out


def test_every_title_is_attribute_safe():
    """No title may contain a raw double quote once escaped into the page."""
    for ident in ("E12", "P108", "P108i", "P14.1", "E84", "S13"):
        out = marked(ident)
        # exactly one opening quote and one closing quote around the title
        assert re.fullmatch(r'<code title="[^"]*">[^<]+</code>', out), out


def test_the_lookup_covers_all_five_ontology_buckets():
    names = ident_names()
    assert len(names) > 500
    for ident in ("E12", "P108", "P14.1", "E84", "S13"):
        assert ident in names, ident


def test_extension_identifiers_are_marked_and_titled():
    """IDENT matched only the E/P shape, so A2, S19, I5 and AP18 rendered as
    plain text with no tooltip -- and run6 answers propose 23 distinct
    extension classes."""
    out = marked("A2 with S13 and AP18")
    assert 'title="A2 Stratigraphic Volume Unit (CRMarchaeo)"' in out
    assert "CRMsci" in out
    assert out.count("<code") == 3


def test_committee_designators_are_not_mistaken_for_identifiers():
    """lib.ontology records that "TC46", "SC4" and "WG9" -- the ISO committee
    that standardises the CRM -- appear throughout the archive and look just
    like class ids. Matching known ids literally is what keeps them out."""
    out = marked("ISO TC46 SC4 WG9 discussed this")
    assert "<code" not in out


def test_longest_match_wins_so_dotted_and_inverse_ids_survive():
    assert '>P14.1</code>' in marked("P14.1")
    assert '>P108i</code>' in marked("P108i")
    # and P14 alone is still matched, not swallowed
    assert '>P14</code>' in marked("P14 alone")


def test_concepts_new_in_7_3_2_still_get_a_name():
    """data/ontology.json is built from the v7.1.3 XML, which never carried
    E100, P199 or P200. An answer citing one is correct, so it must not be the
    only identifier on the page without a name. The 7.3.2 declarations supply
    it."""
    assert ident_title("E100").startswith("E100 Audio Item")
    assert "7.3.2" in ident_title("E100")
    assert "P199" in ident_title("P199")


def test_the_xml_still_wins_where_it_has_an_entry():
    """The declaration harvest uses setdefault, so it fills gaps rather than
    overriding v7.1.3 -- E12's title must stay the XML's full_name, with no
    version suffix appended."""
    assert ident_title("E12") == "E12 Production"
