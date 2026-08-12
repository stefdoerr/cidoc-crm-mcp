"""The CRM family extension models, and the vocabulary v7.1.3 retired.

`cidoc_crm_v7.1.3.xml` is CRMbase alone; the eleven family extensions
(CRMarchaeo, CRMsci, FRBRoo, ...) live in the scraped `crm_family.json`
collection, and this module is what folds their identifiers into an
ontology dict -- resolving an archive-mentioned id to a model by its prefix
when the collection itself does not declare it, and recording the ids the
archive still argues about that v7.1.3 has since dropped. Both additions
share the same shape (`add_extensions`/`add_historical` both write into
`onto`), which is why they sit together rather than with `sources.py`'s
other post-XML additions.
"""

import json
import re
from pathlib import Path

# The SIG debates the whole CIDOC CRM family, not only CRMbase, so the archive
# is full of identifiers that cidoc_crm_v7.1.3.xml does not define. The
# authoritative list of them is crm_family.json (see tools/fetch_crm_family.py).
#
# This prefix registry is the *fallback* for ids that list cannot cover: models
# renumber between versions, so the archive discusses SP5, S16 and AP14 which
# the current declarations have dropped, exactly as CRMbase dropped E84. Such an
# id is accepted only when its prefix belongs to a real model AND the archive
# actually uses it.
#
# Prefix shape alone is never enough: "TC46", "SC4" and "WG9" -- the ISO
# committee that standardises the CRM -- appear throughout this list and look
# just like class ids. Requiring prefix-then-digits rejects them, because "SC4"
# is not CRMsci's "S" followed by a number.
# Prefixes are DERIVED from the collection rather than written out by hand --
# hand-written ones were simply wrong (CRMtex properties are TXP, not TP; CRMact
# uses ACTE/ACTP; PRESSoo uses Y/Z). These three cannot be derived because no
# declaration page supplies them:
FAMILY_SUPPLEMENT: dict[str, tuple[str, str]] = {
    # CRMbase property-classes: PC14 reifies P14. The v7.1.3 XML omits them.
    "PC": ("CRMbase", "property"),
    # CRMsoc has a version 0.1 page but has never published declarations.
    "SO": ("CRMsoc", "class"),
    # IFLA LRM itself -- the conceptual model LRMoo formalises -- as opposed to
    # LRMoo, whose own identifiers are the F/R series.
    "LRM-E": ("LRM", "class"),
    "LRM-R": ("LRM", "property"),
    "LRM-P": ("LRM", "property"),
}

# An id resolved only by prefix must stay in range. Every family model numbers
# below 100; three-digit matches are things like the GUID fragment "A622" and
# the ship section "B347.6", not ontology classes.
MAX_FALLBACK_NUMBER = 99

_PREFIX = re.compile(r"([A-Z]+(?:-[A-Z])?)(\d{1,3})$")


def family_prefixes(family: dict[str, dict]) -> list[tuple[str, str, str]]:
    """(prefix, model, kind) for every prefix in the collection, longest first.

    Longest-first matters: SP6 must resolve to CRMgeo, not to CRMsci's S. Where
    two models share a prefix (F and R belong to both FRBRoo and LRMoo) the more
    frequent owner in the collection wins, which is only used for ids the
    collection does not itself declare.
    """
    owners: dict[str, dict[tuple[str, str], int]] = {}
    for ident, entry in family.items():
        match = _PREFIX.fullmatch(ident)
        if match:
            key = (entry["model"], entry["kind"])
            owners.setdefault(match.group(1), {})
            owners[match.group(1)][key] = owners[match.group(1)].get(key, 0) + 1
    resolved = {
        prefix: max(counts, key=lambda k: counts[k]) for prefix, counts in owners.items()
    }
    resolved.update(FAMILY_SUPPLEMENT)
    return sorted(
        ((prefix, model, kind) for prefix, (model, kind) in resolved.items()),
        key=lambda row: -len(row[0]),
    )


def family_of(ident: str, prefixes: list[tuple[str, str, str]]) -> tuple[str, str] | None:
    """Resolve an identifier to (model, kind), or None if no known prefix fits.

    The remainder after the prefix must be digits only, and in range. That rule
    is what separates real ids from the committee designators that share their
    shape: "SC4" is not CRMsci's "S" followed by a number, and "TC46" and "WG9"
    match no prefix at all.
    """
    ident = (ident or "").strip().upper().replace("LRM ", "LRM-")
    for prefix, model, kind in prefixes:
        rest = ident[len(prefix):]
        if ident.startswith(prefix) and rest.isdigit():
            return (model, kind) if int(rest) <= MAX_FALLBACK_NUMBER else None
    return None


def load_family(path) -> dict[str, dict]:
    """Load the compiled CRM family identifier collection."""
    return json.loads(Path(path).read_text(encoding="utf-8"))["entries"]


# The rest of a declared entry (see tools/fetch_crm_family.py): scope note and
# URI for every kind, hierarchy for classes, domain/range/hierarchy for
# properties. Carried through only `if f in declared`, never forced to None --
# FRBRoo entries (PDF-sourced, no declaration cards) have none of these keys
# at all, and an archive-only id with no `declared` record has no entry to
# read them from in the first place. Absence stays absence, all the way to
# data/ontology.json, exactly as the corpus spec asks for FRBRoo.
_DECLARATION_FIELDS = (
    "uri", "scope_note", "sub_class_of", "super_class_of",
    "domain", "range", "sub_property_of", "super_property_of",
)


def add_extensions(onto: dict, mentions: dict[str, int], family: dict[str, dict]) -> dict:
    """Record the CRM family extension identifiers: every declared one, plus
    the ones only the archive knows about.

    These are real and worth both retrieving on and validating against --
    FRBRoo F3, CRMsci S4, CRMgeo SP6 -- but cidoc_crm_v7.1.3.xml does not
    define them, so without this they are indistinguishable from a model's
    hallucination.

    An id is `current` when the official declarations carry it and
    `historical` when only the archive does, mirroring how CRMbase ids are
    treated. An id that is neither declared nor resolvable to a family model
    is not recorded at all.

    This once took only the ids the archive mentions, on the reasoning that
    the collection is a filter on this corpus rather than a copy of eleven
    ontologies. That was right while the only job was searching the mailing
    list, and wrong once the job included validating models people write.
    The archive mentions 253 of the 467 declared family concepts, so the
    filter silently dropped 214 real identifiers -- and because the
    extensions bucket is also what tells `_owned_namespaces` which
    namespaces the model owns, a dropped id did not merely fail to resolve:
    its whole namespace looked foreign, so `crmsci:O19_encountered_object`
    was reported `not_crm` and passed with exit 0. Worse than rejecting it,
    because the document looked checked.

    It also made the build depend on a 143MB mailing-list archive shipped
    out of band. A clone with only the tracked files got CRMbase and
    nothing else, which is not a defensible thing to publish.

    `mentions` stays the archive count and is 0 for a declared id the
    archive never discusses -- callers rank on it, so it has to keep
    meaning "how much the SIG argued about this", not "does this exist".
    """
    known = set(onto["classes"]) | set(onto["properties"]) | set(onto["historical"])
    prefixes = family_prefixes(family)
    # Union, so a declared id lands whether or not the archive mentions it and
    # an archive-only id still lands on its own. Sorted for a deterministic
    # build: data/ontology.json is diffed by hand when it is regenerated.
    for ident in sorted(set(mentions) | set(family)):
        if ident in known:
            continue
        count = mentions.get(ident, 0)
        declared = family.get(ident)
        resolved = family_of(ident, prefixes)
        if declared is not None:
            model, kind = declared["model"], declared["kind"]
        elif resolved is not None:
            model, kind = resolved
        else:
            continue
        entry = {
            "id": ident,
            "status": "current" if declared else "historical",
            "label": declared["label"] if declared else None,
            "model": model,
            "kind": kind,
            "mentions": count,
        }
        if declared:
            for field in _DECLARATION_FIELDS:
                if field in declared:
                    entry[field] = declared[field]
        onto["extensions"][ident] = entry
    return onto


def add_historical(onto: dict, mentions: dict[str, int]) -> dict:
    """Record archive-observed ids that v7.1.3 no longer defines.

    These are the deprecated classes and properties whose removal the archive
    itself debated (E84 Information Carrier, E46 Section Definition, ...).
    They carry no definition because v7.1.3 genuinely has none — the archive is
    the only surviving documentation of what they meant.
    """
    known = set(onto["classes"]) | set(onto["properties"])
    for ident, count in mentions.items():
        if ident in known:
            continue
        onto["historical"][ident] = {
            "id": ident,
            "status": "historical",
            "mentions": count,
            "label": None,
        }
    return onto
