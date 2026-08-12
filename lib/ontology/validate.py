"""Is one link legal? Naming a property, then checking domain and range.

A single triple -- subject class, property (by id, inverse id, dotted
property-of-property, or ambiguous label), object class -- checked against
the merged model view. `_property_candidates` is the naming half (a label
like "contains" resolves to several real properties) and `validate_link` is
the checking half; they are one idea and stay together rather than
splitting the resolver from its only caller.
"""

import re

from .graph import _ancestors_in, _model_view, _property_name, is_required
from .uris import resolve_uri


def _label_key(text: str) -> str:
    """A property name reduced to what spelling cannot change.

    Underscores are how the published example format writes the spaces, and
    hyphens survive inside words ("has time-span"), so both fold to the same
    separator. One definition, because the resolver now compares names in two
    places and two copies of a normalisation rule drift.
    """
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")

# ---- link validation ------------------------------------------------------
#
# "Is this triple legal?" is decidable from domain, range and the class
# hierarchy, and until now nothing exposed it. An agent writing a model had to
# read a declaration per property and check by eye, or -- as one did -- write
# its own script against data/ontology.json. The second option disappears
# behind an MCP wrapper, which has no filesystem and no shell, so the check
# has to live in the tool.
#
# The hard part is not the check, it is naming the property. A label does not
# identify one: "consists of" is P5, P9 or P45, "contains" is P10, P86, P89 or
# P172, and 14 labels are shared in total. The published CIDOC CRM example
# encodings use labels as XML element names, so a file written in that format
# is genuinely ambiguous and can only be read back with the surrounding
# classes in hand. Hence: resolve every candidate, test each, and report what
# survives instead of picking one.


def _property_candidates(onto: dict, prop: str) -> list[tuple[str, bool]]:
    """(property id, is_inverse) for every reading of `prop`.

    Accepts an id (`P108`), an inverse id (`P108i`), a dotted
    property-of-property (`P14.1`), or a label in either direction
    (`has produced`, `was produced by`, `has_produced`).
    """
    _, properties = _model_view(onto)
    raw = (prop or "").strip()
    ident = raw.upper()

    # Case-insensitive lookup that still returns the REAL key. Every id
    # this codebase parsed from the XML is uppercase-only, so `.upper()`
    # was a no-op for them and matching on `ident` directly was equivalent
    # to matching on the real key. P81a/P81b/P82a/P82b/P90a/P90b (folded in
    # by add_rdfs_additions) break that equivalence: their trailing letter
    # is a genuine part of the CIDOC identifier, not a casing choice, so
    # `"P82a".upper()` is "P82A" -- a string that is not a key in
    # `properties` at all. Folding the dict through its own uppercase once
    # keeps every existing id's lookup identical (upper(k) == k for all of
    # them) while making "p82a", "P82A" and "P82a" all resolve to the one
    # real key, the same tolerance every all-uppercase id already had.
    by_upper = {k.upper(): k for k in properties}

    def names_of(entry: dict) -> list[tuple[str, bool]]:
        """(name, is_inverse) for a property, from either storage shape.

        CRMbase properties parsed from the XML carry `direct_name` and
        `inverse_name` separately. The 111 family-extension properties are
        scraped from declaration pages and carry ONE combined `label`,
        "encountered object (was object encountered through)", so a scan of
        the split fields alone found none of them and every family property
        was unreachable by name -- `validate S19 O19 E18` resolved while
        `validate S19 "<its label>" E53` did not, which is the difference
        between a tool an agent can use on a document and one it can only
        use on identifiers it has already looked up.
        """
        direct, inverse = entry.get("direct_name"), entry.get("inverse_name")
        if direct or inverse:
            return [(n, inv) for n, inv in ((direct, False), (inverse, True)) if n]
        label = (entry.get("label") or "").strip()
        if not label:
            return []
        if label.endswith(")") and "(" in label:
            cut = label.rindex("(")
            return [(label[:cut].strip(), False), (label[cut + 1:-1].strip(), True)]
        return [(label, False)]

    if ident in (onto.get("property_of_property") or {}):
        return [(ident, False)]
    if ident in by_upper:
        return [(by_upper[ident], False)]
    if ident.endswith("I") and ident[:-1] in by_upper:
        # Only when an inverse actually exists. The trailing "i" is CRM
        # shorthand for "this property, read backwards", and stripping it
        # blindly invented one for every property that has no inverse to
        # read: P82ai, P3i, P57i, P90ai all resolved. The damage was not
        # that they resolved but WHAT they resolved to -- a reading whose
        # domain and range are the real property's swapped, so a document
        # writing crm:P82ai_... was told `illegal, E52 is not a E61`
        # instead of the truth, which is that no such property exists.
        # Wrong advice about a real property beats no advice, but it loses
        # to correct advice about a name that is not one.
        #
        # A property has an inverse iff `names_of` yields an inverse name:
        # it reads the split CRMbase fields and the combined family label
        # alike, so O19 -- whose inverse hides inside "encountered object
        # (was object encountered through)" -- is correctly kept.
        inverse_of = by_upper[ident[:-1]]
        if any(inv for _, inv in names_of(properties[inverse_of])):
            return [(inverse_of, True)]

    def as_bare_id(token: str) -> tuple[str, bool] | None:
        """(id, is_inverse) for one identifier token, under the guard above.

        Same rule as the two branches before this, applied to a token taken
        from the middle of a longer string rather than to the whole argument.
        """
        up = token.upper()
        if up in by_upper:
            return (by_upper[up], False)
        if up.endswith("I") and up[:-1] in by_upper:
            base = by_upper[up[:-1]]
            if any(inv for _, inv in names_of(properties[base])):
                return (base, True)
        return None

    # A full URI, a `crm:`-prefixed name, or the RDF local name: `P111_added`,
    # `P4_has_time-span`, `P4i_is_time-span_of`. `crm_list` exists to print
    # that column and `validate_document` reads those names out of a file, so
    # refusing them here made one server accept a spelling in one tool and
    # reject it in another. `resolve_uri` is the index for these forms and is
    # strict about them -- `P111_augmented` and the stale `E22_Man-Made_Object`
    # both resolve to nothing -- so it decides them here too, rather than a
    # second parser of the same names drifting from it.
    #
    # Its one laxness has to be re-guarded. It answers ('P82a', True) for a
    # bare `P82ai`, indexing the id form without asking whether an inverse
    # exists, which is the reading the branch above deliberately refuses; so
    # the same guard applies to what it returns, not just to what this
    # function parses itself.
    uri_id, uri_inverse = resolve_uri(onto, raw)
    if uri_id and uri_id in properties and (
            not uri_inverse or any(inv for _, inv in names_of(properties[uri_id]))):
        return [(uri_id, uri_inverse)]

    # An identifier beside its own name: "P111 added". Every listing in this
    # codebase prints a property as that pair -- `! P111  added  E18` from
    # `crm_concept`, `P110  augmented` from `crm_connect`, `LEGAL  P111
    # added` from this very check -- so a caller who reads one output and
    # types it into the next input is copying, not erring.
    #
    # The name must be the one that id carries, and in the direction the id
    # gives. Taking the id and discarding the rest would answer LEGAL about
    # P111 for "P111 augmented", which is a typo for P110 -- a confident
    # answer to a question nobody asked, and the one outcome worse than the
    # refusal it replaces.
    head, _, tail = raw.replace("_", " ").partition(" ")
    if tail:
        paired = as_bare_id(head)
        if paired:
            pid, want_inverse = paired
            for name, inverse in names_of(properties[pid]):
                if inverse == want_inverse and _label_key(name) == _label_key(tail):
                    return [(pid, inverse)]

    # label, in either direction
    key = _label_key(raw)
    out: list[tuple[str, bool]] = []


    # Property-of-property labels count. "in the role of" IS a CRM label --
    # P14.1's -- and reporting it as no property at all sends a reader
    # hunting a typo that is not there. It resolves, and validate_link then
    # says the accurate thing: its domain is a property, so a class link is
    # the wrong question for it.
    for pid, entry in (onto.get("property_of_property") or {}).items():
        label = entry.get("label") or ""
        if label and _label_key(label) == key:
            out.append((pid, False))
    for pid, entry in properties.items():
        for name, inverse in names_of(entry):
            if _label_key(name) == key:
                out.append((pid, inverse))
    return out


def _unmatched_property_error(onto: dict, prop: str) -> str:
    """Why nothing matched, for the one case where the caller is one token from
    right: an identifier paired with a name that is not its own.

    Keeps the "no property matches" opening, which `validate_document` reads to
    classify a finding as `unknown_name` rather than an unknown class.
    """
    base = f"no property matches {prop!r}"
    _, properties = _model_view(onto)
    by_upper = {k.upper(): k for k in properties}
    head, _, tail = (prop or "").strip().replace("_", " ").partition(" ")
    if not tail:
        return base
    up = head.upper()
    pid = by_upper.get(up) or (by_upper.get(up[:-1]) if up.endswith("I") else None)
    if pid is None:
        return base
    entry = properties[pid]
    direct, inverse = entry.get("direct_name"), entry.get("inverse_name")
    if not (direct or inverse):
        # A family-extension property carries one combined label instead.
        direct = (entry.get("label") or "").strip() or None
    if not direct and not inverse:
        return base
    called = f"{pid} is {direct!r}" if direct else f"{pid} reversed is {inverse!r}"
    if direct and inverse:
        called += f" (reversed, {inverse!r})"
    return f"{base} -- {called}; the name has to be the one that identifier carries"


def validate_link(onto: dict, subject: str, prop: str, obj: str | None = None) -> dict:
    """Can `prop` join an instance of `subject` to one of `obj`?

    Returns every reading of `prop` with a verdict for each, rather than a
    single boolean: where the name is ambiguous, one reading may be legal and
    another not, and collapsing that to True would hide which property the
    caller actually has to write down.

    `obj` may be omitted to check only that the subject can carry the
    property at all.

    A property-of-property (`P14.1`) is reported as `not_a_class_link`
    instead of being forced into a verdict: its domain is the parent
    relationship, not a class, so a subject class is the wrong question and
    answering it either way would invent a constraint.
    """
    classes, properties = _model_view(onto)
    subject, obj = subject.strip().upper(), (obj or "").strip().upper() or None

    result: dict = {"subject": subject, "property": prop, "object": obj,
                    "candidates": [], "legal": False, "resolved": None}

    unknown = [c for c in (subject, obj) if c and c not in classes]
    if unknown:
        result["error"] = f"unknown class {', '.join(unknown)}"
        return result

    candidates = _property_candidates(onto, prop)
    if not candidates:
        result["error"] = _unmatched_property_error(onto, prop)
        return result

    subj_family = _ancestors_in(classes, subject)
    obj_family = _ancestors_in(classes, obj) if obj else None

    for pid, inverse in candidates:
        if pid in (onto.get("property_of_property") or {}):
            result["candidates"].append({
                "id": pid, "direction": "->", "legal": None,
                "reason": "not_a_class_link: its domain is the property "
                          f"{onto['property_of_property'][pid].get('of_property')}, "
                          "not a class",
            })
            continue
        entry = properties[pid]
        needs_subj = entry.get("range") if inverse else entry.get("domain")
        needs_obj = entry.get("domain") if inverse else entry.get("range")
        subj_ok = (needs_subj is None) or (needs_subj in subj_family)
        obj_ok = obj_family is None or needs_obj is None or needs_obj in obj_family
        why = []
        if not subj_ok:
            why.append(f"{subject} is not a {needs_subj}")
        if not obj_ok:
            why.append(f"{obj} is not a {needs_obj}")
        result["candidates"].append({
            "id": pid + ("i" if inverse else ""),
            "name": _property_name(entry, inverse=inverse),
            "direction": f"{needs_subj} -> {needs_obj}",
            "legal": subj_ok and obj_ok,
            "required": is_required(entry) and not inverse,
            "reason": "; ".join(why) or "domain and range both admit these classes",
        })

    legal = [c for c in result["candidates"] if c["legal"]]
    result["legal"] = bool(legal)
    result["resolved"] = legal[0]["id"] if len(legal) == 1 else None
    if len(legal) > 1:
        result["ambiguous"] = [c["id"] for c in legal]
    return result
