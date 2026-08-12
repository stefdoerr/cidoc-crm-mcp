"""Identifiers as URIs: naming, namespaces, and resolving a URI back to one.

RDF addresses everything by URI, and a CRM URI is a derived thing --
`E22_Human-Made_Object`, `P108i_was_produced_by` -- built from an
identifier and its label. This module derives those names, tracks which
namespaces a model owns (so a foreign predicate can be told apart from a
misspelled CRM one), and builds the cached index that maps a URI's local
name back to (identifier, is_inverse). The two identity-keyed caches here
are module-level singletons -- several functions across the package call
`.drop()` on them, and they must stay the one instance every caller shares.
"""

import re

from .graph import _model_view

# ---- RDF names -------------------------------------------------------------
#
# RDF addresses everything by URI, and the CRM's URIs are its identifiers
# joined to their names: E22_Human-Made_Object, P108_has_produced,
# P108i_was_produced_by. Nothing in this repository stored those, because
# nothing needed them until a reader had to accept a document that uses them.
#
# CRMbase names are derived; the 330 family identifiers are not, because their
# entries already carry the real thing -- for example
# http://www.cidoc-crm.org/extensions/crmsci/S19_Encounter_Event. Deriving
# those instead would guess at eleven models' namespaces, and family_of
# already records what guessing at family shapes costs.

CRM_NAMESPACE = "http://www.cidoc-crm.org/cidoc-crm/"


def _namespace_of(uri: str) -> str:
    """Everything before the local name `resolve_uri` would read from `uri`.

    Mirrors resolve_uri's own parsing exactly -- split after the last '/',
    then after the last '#' -- so namespace membership and identifier
    extraction can never disagree about where one ends and the other
    begins. `local` is always a suffix of `raw` by construction (both
    rsplits only ever trim from the end), so slicing it off the tail is
    safe.
    """
    raw = (uri or "").strip()
    if not raw:
        return ""
    local = raw.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
    return raw[:len(raw) - len(local)] if local else raw


class _IdentityCache:
    """Memoize per ontology object, keyed on identity, bounded, leak-free."""

    def __init__(self, limit: int = 4) -> None:
        self._limit = limit
        self._entries: dict[int, tuple[dict, object]] = {}

    def get(self, onto: dict):
        hit = self._entries.get(id(onto))
        # `is` and not `==`: two equal-valued ontologies are still two
        # objects, and the point of the check is to catch a recycled address.
        return hit[1] if hit is not None and hit[0] is onto else None

    def put(self, onto: dict, value):
        if len(self._entries) >= self._limit:
            self._entries.pop(next(iter(self._entries)))
        self._entries[id(onto)] = (onto, value)
        return value

    def drop(self, onto: dict) -> None:
        self._entries.pop(id(onto), None)



# Same cache shape as _URI_INDEX_CACHE below, and for the same reason: built
# from every entry's `uri` field, needed once per unresolved predicate, and
# correct for as long as `onto` is the same object -- so keyed on id(onto)
# rather than recomputed per call.
_NAMESPACE_CACHE = _IdentityCache()


def _owned_namespaces(onto: dict) -> frozenset[str]:
    """Every namespace this model can natively name a term in.

    Not a hostname test against cidoc-crm.org: LRMoo, one of the family
    extensions this repository already merges in, lives at
    http://iflastandards.info/ns/lrm/lrmoo/, so a hostname check would
    treat a misspelled LRMoo property as foreign vocabulary rather than a
    misspelling -- the exact confusion this function exists to avoid.
    Built instead from the `uri` field recorded on every class, property,
    extension and property-of-property entry, unioned with CRM_NAMESPACE --
    the one namespace CRMbase entries derive rather than store, because
    they predate this repository needing to accept a document that
    addresses them by URI at all. Self-maintaining: add an extension to
    data/ontology.json and its namespace is already in this set, with no
    code change here.
    """
    cached = _NAMESPACE_CACHE.get(onto)
    if cached is not None:
        return cached

    namespaces = {CRM_NAMESPACE}
    for bucket in ("classes", "properties", "extensions", "property_of_property"):
        for entry in (onto.get(bucket) or {}).values():
            if isinstance(entry, dict) and entry.get("uri"):
                namespaces.add(_namespace_of(entry["uri"]))
    result = frozenset(namespaces)
    return _NAMESPACE_CACHE.put(onto, result)


# uri_index walks ~590 merged entries through a regex per name, measured at
# ~1.17ms -- cheap once, but the RDF reader calls resolve_uri once per triple
# and once per rdf:type lookup, so a 2,000-triple model would rebuild it
# thousands of times for the same answer. Keyed on id(onto), not on onto's
# value: onto is a large nested dict, so it is unhashable outright, and even
# a value-based key (a hash of the whole structure) would cost more to
# compute than just rebuilding the index -- while identity is free.
#
# Identity alone is NOT safe, though, and the earlier claim here that it was
# -- "every caller holds one long-lived parsed ontology" -- was false of the
# test suite the moment it was written: several helpers build a fresh dict
# per call. CPython reuses the address of a freed object, so alternating two
# ontologies returns the index of an already-collected one, silently, with no
# error and the wrong verdicts. Reproduced on the eleventh iteration.
#
# `_IdentityCache` closes it by keeping a strong reference to the ontology
# beside its cached value: an object that is still referenced cannot be freed,
# so its address cannot be handed to a different object while the entry
# lives. It is bounded because that reference would otherwise pin every
# ontology ever built -- a real leak in a long-running server that reloads
# the model. Eviction is safe precisely because the reference goes with the
# entry: a later object reusing a recycled address finds no entry and
# rebuilds.
_URI_INDEX_CACHE = _IdentityCache()


def _local_name(ident: str, entry: dict, inverse: bool = False) -> str | None:
    """`E22_Human-Made_Object`, `P108i_was_produced_by`, or None.

    Spaces become underscores; a hyphen inside a word is part of the word and
    stays, which is why P4 is `P4_has_time-span` and not `P4_has_time_span`.

    CRMbase properties carry `direct_name`/`inverse_name` split already; the
    111 family-extension properties carry ONE combined `label` -- O19's is
    "encountered object (was object encountered through)". Reading only the
    split fields left O19's inverse name absent (no `inverse_name` key exists
    to read) and its forward name ending in the literal parenthesised inverse
    text -- `O19_encountered_object_(was_object_encountered_through)`, parens
    and all -- so a real CRMsci triple resolved forward only by luck, via the
    unrelated `uri` field's last segment, and never resolved in the inverse
    direction at all. Splitting the combined label on its last "(" is the
    same rule `_property_candidates`'s `names_of` already applies going the
    other direction (name -> id); this is name derivation, so it has to agree.
    """
    direct, inv = entry.get("direct_name"), entry.get("inverse_name")
    if not direct and not inv:
        label = (entry.get("label") or "").strip()
        if label.endswith(")") and "(" in label:
            cut = label.rindex("(")
            direct, inv = label[:cut].strip(), label[cut + 1:-1].strip()
        else:
            direct = label or None
    name = inv if inverse else direct
    if not name:
        return None
    return f"{ident}{'i' if inverse else ''}_" + re.sub(r"\s+", "_", name.strip())


def uri_index(onto: dict) -> dict[str, tuple[str, bool]]:
    """{lower-cased local name: (identifier, is_inverse)} for everything.

    Keyed on the local name rather than the full URI so one index serves all
    three shapes a document may use -- a full URI, a `crm:` prefixed name, or
    a bare local name -- since only the last segment differs between them.

    Cached by id(onto): see _URI_INDEX_CACHE.
    """
    cached = _URI_INDEX_CACHE.get(onto)
    if cached is not None:
        return cached

    classes, properties = _model_view(onto)
    index: dict[str, tuple[str, bool]] = {}

    def put(name: str | None, ident: str, inverse: bool) -> None:
        if name:
            index.setdefault(name.lower(), (ident, inverse))

    for cid, entry in classes.items():
        put(_local_name(cid, entry), cid, False)
        put(cid, cid, False)                       # the bare identifier alone
        if entry.get("uri"):
            put(entry["uri"].rsplit("/", 1)[-1], cid, False)
    for pid, entry in properties.items():
        put(_local_name(pid, entry), pid, False)
        put(_local_name(pid, entry, inverse=True), pid, True)
        put(pid, pid, False)
        put(f"{pid}i", pid, True)
        if entry.get("uri"):
            put(entry["uri"].rsplit("/", 1)[-1], pid, False)
    for pid, entry in (onto.get("property_of_property") or {}).items():
        put(_local_name(pid, entry), pid, False)
        put(pid, pid, False)
    return _URI_INDEX_CACHE.put(onto, index)


def resolve_uri(onto: dict, uri: str) -> tuple[str | None, bool]:
    """(identifier, is_inverse) for a full URI, a `crm:` name, or a bare one.

    Returns (None, False) for anything outside the model -- `rdfs:label`, a
    Dublin Core term, an application's own vocabulary. That is a real answer,
    not a failure: an RDF document legitimately carries predicates the CRM
    says nothing about, and the caller reports them rather than rejecting the
    file.
    """
    raw = (uri or "").strip()
    if not raw:
        return None, False
    local = raw.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
    if ":" in local and not local.startswith("http"):
        local = local.split(":", 1)[1]
    return uri_index(onto).get(local.lower(), (None, False))
