"""Questions about the hierarchy, once an ontology dict already exists.

Ancestors, the property closure, applicable/required/connecting
properties, the compact skeleton and full listing -- everything here walks
`sub_class_of`/`sub_property_of`/domain/range over a merged model view
(`_model_view` merges CRMbase with the family extensions) and answers a
question about *structure*: what is above this class, what can point at
it, how far. Nothing here parses a source or reads a file; it all takes an
already-built ontology dict as its first argument.
"""

import re

def ancestors(onto: dict, class_id: str) -> set[str]:
    """Every superclass of class_id, inclusive of class_id itself.

    Iterative with an explicit visited set: the CRM hierarchy is a DAG, not a
    tree (E22 subclasses both E19 and E24), so shared ancestors are reachable
    by several paths and a naive walk revisits them.
    """
    seen: set[str] = set()
    stack = [class_id]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        entry = onto["classes"].get(current)
        if entry:
            stack.extend(p for p in entry["sub_class_of"] if p)
    return seen


def resolve_property_id(onto: dict, pid: str) -> str | None:
    """Map an inverse-direction id to its base ('P10i' -> 'P10').

    Returns None if neither the given id nor its base (with trailing 'i'
    stripped) resolves, so a genuinely unknown id stays unknown. Only strips
    the 'i' when the base actually resolves — don't blindly rstrip to avoid
    corrupting a legitimately i-ending id.
    """
    if pid in onto["properties"]:
        return pid
    if pid.endswith("i"):
        base = pid[:-1]
        if base in onto["properties"]:
            return base
    return None


def _property_depth(onto: dict, pid: str, memo: dict | None = None, in_progress: set | None = None) -> int:
    """Distance to the top of the sub_property_of chain. Deeper = more specific.

    Computes longest path to root via recursive memoization. Handles cycles
    safely by marking in-progress nodes; re-entry from a cycle is treated as
    depth -1 so malformed cycles terminate gracefully rather than recursing
    infinitely. Resolves inverse-direction ids (e.g., 'P10i' -> 'P10').
    """
    if memo is None:
        memo = {}
    if in_progress is None:
        in_progress = set()

    # Resolve inverse-direction ids
    resolved_pid = resolve_property_id(onto, pid)
    if resolved_pid is None:
        # Unknown property: treat as leaf with depth 0
        return 0

    if resolved_pid in memo:
        return memo[resolved_pid]
    if resolved_pid in in_progress:
        # Cycle detected: treat re-entry as a dead end (depth -1)
        return -1

    in_progress.add(resolved_pid)
    entry = onto["properties"].get(resolved_pid)

    if not entry or not entry.get("sub_property_of"):
        # Leaf node: depth 0
        result = 0
    else:
        # Longest path through any parent (resolving inverse ids)
        parent_depths = [_property_depth(onto, parent, memo, in_progress) for parent in entry["sub_property_of"]]
        result = max(parent_depths, default=-1) + 1

    in_progress.discard(resolved_pid)
    memo[resolved_pid] = result
    return result


def property_closure(onto: dict) -> dict:
    """Applicable properties per class, both directions, most specific first.

    Computed at load and never written to data/ontology.json -- that artifact
    stays a faithful representation of the XML, and this is derived data.

    outgoing: properties whose domain is the class or any ancestor
              ("what can this class be the subject of")
    incoming: properties whose range is the class or any ancestor
              ("what can point at this class")

    Both matter. Measured on E22: 0 properties declare domain E22 directly,
    31 reach it through ancestry, and 38 more can point at it -- so the
    uncomputed version returns nothing at all.
    """
    # Compute depth for all properties with a shared memo for efficiency
    memo: dict[str, int] = {}
    depth = {pid: _property_depth(onto, pid, memo) for pid in onto["properties"]}
    # Most specific first, then by id so the order is deterministic.
    rank = lambda pid: (-depth[pid], pid)  # noqa: E731

    closure = {}
    for cid in onto["classes"]:
        family = ancestors(onto, cid)
        closure[cid] = {
            "outgoing": sorted(
                (p for p, e in onto["properties"].items() if e["domain"] in family),
                key=rank,
            ),
            "incoming": sorted(
                (p for p, e in onto["properties"].items() if e["range"] in family),
                key=rank,
            ),
        }
    return closure


def _model_view(onto: dict) -> tuple[dict, dict]:
    """CRMbase and the family extensions as one class map and one property map.

    The extensions bucket mixes both kinds in a single dict; a property-like
    entry is the one carrying a `domain`. Splitting on that rather than on the
    identifier's letter is deliberate -- `family_of` already proved that shape
    alone is not authority, and CRMsci's O-properties, CRMarchaeo's AP-
    properties and FRBRoo's R-properties share no naming rule.

    Merging matters because the hierarchy genuinely crosses models: CRMarchaeo
    declares `A1 sub_class_of [S1, S4, E12, E64]`, so an A1 inherits CRMbase
    properties through E12, and a base-only walk would report none of them.
    Base wins any id collision -- the XML is the normative source.
    """
    classes = dict(onto.get("classes") or {})
    properties = dict(onto.get("properties") or {})
    for ident, entry in (onto.get("extensions") or {}).items():
        if not isinstance(entry, dict):
            continue
        target = properties if entry.get("domain") else classes
        target.setdefault(ident, entry)
    return classes, properties


def _ancestors_in(classes: dict, class_id: str) -> set[str]:
    """`ancestors` over an arbitrary class map -- see that function for why the
    visited set is required (the hierarchy is a DAG, not a tree)."""
    seen: set[str] = set()
    stack = [class_id]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        entry = classes.get(current)
        if entry:
            stack.extend(p for p in (entry.get("sub_class_of") or []) if p)
    return seen


def _distance_to(classes: dict, class_id: str, targets: set[str]) -> dict[str, int]:
    """Hops from `class_id` up to each of its ancestors, breadth-first.

    This is what makes the applicable-property list usable. Ranking purely by
    property specificity puts P183/P134/P182 -- deep sub-properties whose
    domain is E1 -- at the head for every class in the model, so the twenty
    slots the display used to allow were spent on properties that apply to
    literally everything, and `P30 transferred custody of` (domain E10 exactly,
    and declared necessary) never appeared for E10 at all.

    Distance 0 means the property is declared on this very class.
    """
    dist = {class_id: 0}
    frontier = [class_id]
    step = 0
    while frontier:
        step += 1
        nxt = []
        for cid in frontier:
            entry = classes.get(cid)
            for parent in (entry.get("sub_class_of") or []) if entry else []:
                if parent and parent not in dist:
                    dist[parent] = step
                    nxt.append(parent)
        frontier = nxt
    return {t: dist.get(t, 10**6) for t in targets}


def _property_name(entry: dict, inverse: bool = False) -> str:
    """Readable name for a property from either source.

    CRMbase properties parsed from the XML carry `direct_name`/`inverse_name`;
    the scraped family declarations carry only a combined `label` ("removed
    (was removed by)"). Falling through to `label` is what stops every
    extension property rendering as a bare number -- which is the exact defect
    being fixed here, so reintroducing it for CRMsci would be a poor joke.
    """
    if inverse:
        return entry.get("inverse_name") or entry.get("direct_name") \
            or entry.get("label") or ""
    return entry.get("direct_name") or entry.get("label") or ""


def is_required(entry: dict) -> bool:
    """True when the CRM declares this property `necessary` on its domain.

    The quantification string reads "many to many, necessary (1,n:0,n)" -- the
    word sits mid-string, never at the start, so a `startswith` test silently
    matches nothing. 62 of 271 properties carry it.

    Extension properties are never required here: the scraped family
    declarations carry domain and range but no quantification at all (measured:
    0 of 111), so claiming otherwise would invent a constraint.
    """
    return "necessary" in str(entry.get("quantification") or "")


def applicable_properties(onto: dict, class_id: str) -> dict[str, list[dict]]:
    """Every property this class can be the subject or object of, ranked.

    Returns {"outgoing": [...], "incoming": [...]}, each entry a dict with
    `id`, `name`, `other` (the class at the far end), `via` (the ancestor whose
    declaration brings it in, or the class itself), `distance` and `required`.

    Ordered by how close the declaring class is -- properties declared on this
    class first, then a parent, then a grandparent -- and only then by property
    specificity. `property_closure` sorts by specificity alone and is left
    unchanged: it predates this and other callers rely on its shape.
    """
    classes, properties = _model_view(onto)
    family = _ancestors_in(classes, class_id)
    dist = _distance_to(classes, class_id, family)
    memo: dict[str, int] = {}

    def collect(side: str, other: str) -> list[dict]:
        rows = []
        for pid, entry in properties.items():
            anchor = entry.get(side)
            if anchor not in family:
                continue
            rows.append({
                "id": pid,
                # `id` stays the bare identifier: the sort looks its depth up
                # by it and callers key on it. `inverse` says which direction
                # this row is read in, which is the part a reader writing RDF
                # needs -- an incoming row's NAME is already the inverse
                # reading, and printing that beside a forward identifier says
                # E22 --P108--> E12, which is backwards and illegal.
                "inverse": side == "range",
                "name": _property_name(entry, inverse=side == "range"),
                "other": entry.get(other),
                "via": anchor,
                "distance": dist.get(anchor, 10**6),
                "required": side == "domain" and is_required(entry),
            })
        rows.sort(key=lambda r: (r["distance"],
                                 -_property_depth(onto, r["id"], memo),
                                 r["id"]))
        return rows

    return {"outgoing": collect("domain", "range"),
            "incoming": collect("range", "domain")}


def required_properties(onto: dict, class_id: str) -> list[dict]:
    """The applicable outgoing properties the CRM declares `necessary`.

    Small enough to always show in full -- measured across CRMbase: median 3
    per class, maximum 10 -- which is the point. These are the ones an instance
    is expected to carry, and the evaluation lost cases to exactly this gap:
    E13 without P177, E10 without P30, E8 without P24, E12 without P108.
    """
    return [r for r in applicable_properties(onto, class_id)["outgoing"]
            if r["required"]]


def connecting_properties(onto: dict, subject: str, obj: str) -> list[dict]:
    """Properties that can link an instance of `subject` to one of `obj`.

    A property connects them when its domain admits the subject and its range
    admits the object -- "admits" meaning the class itself or any ancestor,
    since a property declared on E7 applies to an E12.

    This is the query the search interface could not previously express. An
    answerer had to already know the identifier to look it up, so a model that
    had correctly picked E11 and E29 still had no way to discover that P33
    joins them, and the strict review recorded that miss repeatedly.
    """
    classes, properties = _model_view(onto)
    dom_family = _ancestors_in(classes, subject)
    rng_family = _ancestors_in(classes, obj)
    dom_dist = _distance_to(classes, subject, dom_family)
    rng_dist = _distance_to(classes, obj, rng_family)
    memo: dict[str, int] = {}
    rows = [
        {
            "id": pid,
            "name": _property_name(entry),
            "domain": entry.get("domain"),
            "range": entry.get("range"),
            "required": is_required(entry),
            "exact": entry.get("domain") == subject and entry.get("range") == obj,
            # How far up BOTH hierarchies the declaration sits. A property
            # declared on exactly this pair scores 0. Without this term the
            # ranking is by property specificity alone, and CRMdig's
            # `L54 is same as` (E1 -> E1, so it joins any two classes in the
            # model) surfaced above P12 and P15 in every single query.
            "generality": dom_dist.get(entry.get("domain"), 10**6)
                          + rng_dist.get(entry.get("range"), 10**6),
        }
        for pid, entry in properties.items()
        if entry.get("domain") in dom_family and entry.get("range") in rng_family
    ]
    rows.sort(key=lambda r: (r["generality"],
                             -_property_depth(onto, r["id"], memo),
                             r["id"]))
    return rows


def _first_sentence(text: str, cap: int = 200) -> str:
    """First sentence of a scope note — the selection-tier gloss.

    Full prose is what drowns the signal when discriminating between siblings;
    the caller fetches the whole scope note only for the few survivors.

    Requires an uppercase letter after the break so abbreviations don't end the
    sentence: a bare `(?<=[.!?])\\s` cuts 9 of the 241 glosses mid-"e.g." /
    "i.e." / "cf.", and a fragment is a bad orientation signal at the tier that
    replaces retrieval. Slices at match.start(), not start()+1, so no trailing
    space survives (that bug affected 219 of 241).
    """
    stripped = (text or "").strip()
    match = re.search(r"(?<=[.!?])\s+(?=[A-Z])", stripped)
    return stripped[: match.start()].rstrip() if match else stripped[:cap].rstrip()


def ontology_skeleton(onto: dict) -> list[dict]:
    """Every current concept, compact enough to hand over whole.

    This REPLACES a vector store. 241 concepts is not a scale problem, and
    similarity search cannot discriminate between sibling classes -- which is
    exactly what "which class should I use" requires. Historical ids are
    excluded because v7.1.3 has no definition to serialize for them.
    """
    # The PROPERTY graph is a DAG too, not just the class graph: 83 of 160
    # properties have at least one parent, chains run 5 deep, and 7 have
    # multiple parents (P16 P52 P99 P108 P134 P156 P182). Task 2b's specificity
    # ranking exists because subproperties are usually the right modelling
    # choice -- so the orientation tier has to expose that structure, or the
    # agent picks candidates blind to it and the ranking only helps after the
    # choice is already made.
    # 7 of those declarations name the PARENT by its inverse-direction id
    # (P9 is subPropertyOf "P10i", not "P10" -- P59/P73/P134/P156/P169/P170 do
    # the same). There is no "P10i" key in onto["properties"]; the entry lives
    # under "P10". Left unresolved, children keys the child under a ghost id
    # that never matches a real property, and the parent's record shows no
    # child at all -- resolve_property_id is what the rest of this module
    # already uses for exactly this quirk (see _property_depth).
    def _resolved_parents(sub_property_of: list[str]) -> list[str]:
        return [resolve_property_id(onto, p) or p for p in sub_property_of]

    children: dict[str, list[str]] = {}
    for cid, entry in onto["classes"].items():
        for parent in entry["sub_class_of"]:
            children.setdefault(parent, []).append(cid)
    for pid, entry in onto["properties"].items():
        for parent in _resolved_parents(entry["sub_property_of"]):
            children.setdefault(parent, []).append(pid)

    out: list[dict] = []
    for cid, entry in onto["classes"].items():
        out.append(
            {
                "id": cid,
                "kind": "class",
                "label": entry["label"],
                "parents": entry["sub_class_of"],
                "children": sorted(children.get(cid, [])),
                "gloss": _first_sentence(entry["scope_note"]),
            }
        )
    for pid, entry in onto["properties"].items():
        out.append(
            {
                "id": pid,
                "kind": "property",
                "label": entry["direct_name"],
                "inverse": entry["inverse_name"],
                "parents": _resolved_parents(entry["sub_property_of"]),
                "children": sorted(children.get(pid, [])),
                "domain": entry["domain"],
                "range": entry["range"],
                "quantification": entry.get("quantification", ""),
                "gloss": _first_sentence(entry["scope_note"]),
            }
        )
    return out


# The listing tier is deliberately NOT ontology_skeleton widened. That function
# feeds concept_siblings (via Retriever._concept_skeleton), so adding the
# extension models to it would silently change which siblings a concept dossier
# offers -- a behaviour change to the answering tool, arrived at as a side
# effect of a display fix. This is a separate reader with its own contract.
_SORT_ID = re.compile(r"^([A-Za-z-]+)(\d+)(?:\.(\d+))?$")


def _sort_key(row: dict) -> tuple:
    """CRMbase first, then model name; classes before properties; then id
    numerically, so E9 precedes E10 rather than following E1."""
    match = _SORT_ID.match(row["id"])
    prefix, number, dot = match.groups() if match else (row["id"], "0", None)
    return (
        0 if row["source"] == "CRMbase" else (2 if row["source"] == "historical" else 1),
        row["source"],
        0 if row["kind"] == "class" else 1,
        prefix,
        int(number),
        int(dot or 0),
    )


def full_listing(onto: dict) -> list[dict]:
    """Every identifier the system knows, in one enumerable list.

    `ontology_skeleton` covers CRMbase only -- 241 of the 648 ids this corpus
    can resolve. The other 407 (330 family-extension, 61 historical, 16
    property-of-property) were reachable by `concept <id>` and by nothing
    else, so an agent could use them only if it already knew they existed.
    That is the same failure as a search result that omits the id needed to
    act on it: the tool holds the answer and does not offer it.

    It matters most for a wrapper with no filesystem underneath it. A local
    reader who cannot list CRMsci can open the XML; an MCP client cannot, and
    for it "undiscoverable" and "absent" are the same thing.

    Historical ids are included even though v7.1.3 has no definition to
    serialize for them, because the useful fact about E84 is precisely that
    it is dead. An agent that sees it marked historical will not propose it;
    an agent that cannot see it at all may, and find out afterwards.

    Extension rows are thin by nature -- 122 of 219 family classes have no
    recorded parent, because FRBRoo is PDF-sourced with no declaration card
    to scrape a hierarchy from. Absence is rendered as absence, never guessed.
    """
    # One key set for every row. ontology_skeleton emits different keys for
    # classes and properties (a class has no domain), which is fine for a
    # renderer that switches on `kind` and a trap for anything consuming the
    # JSON, where a missing key and a null one mean different things to a
    # careless reader. Every row carries every field; absent data is null.
    fields = ("id", "kind", "source", "label", "inverse", "parents",
              "children", "domain", "range", "gloss")

    def row(**kw) -> dict:
        base: dict = {k: None for k in fields}
        base.update({"parents": [], "children": [], "label": "",
                     "inverse": "", "gloss": ""})
        base.update(kw)
        return {k: base[k] for k in fields}

    rows: list[dict] = []
    for entry in ontology_skeleton(onto):
        rows.append(row(**{k: v for k, v in entry.items() if k in fields},
                        source="CRMbase"))

    for ident, entry in (onto.get("property_of_property") or {}).items():
        rows.append(row(**{
            "id": ident, "kind": "property", "source": "CRMbase",
            "label": entry.get("label") or "", "inverse": "",
            "parents": [entry["of_property"]] if entry.get("of_property") else [],
            "children": [], "domain": None, "range": entry.get("range"),
            "gloss": f"a property of {entry.get('of_property')}",
        }))

    for ident, entry in (onto.get("extensions") or {}).items():
        # `domain` is what separates a family property from a family class:
        # the models share no naming rule, so the identifier's letter cannot
        # be trusted (see _model_view).
        is_property = bool(entry.get("domain"))
        rows.append(row(**{
            "id": ident,
            "kind": "property" if is_property else "class",
            "source": entry.get("model") or "?",
            "label": entry.get("label") or "",
            "inverse": "",
            "parents": entry.get("sub_property_of" if is_property else "sub_class_of") or [],
            "children": [],
            "domain": entry.get("domain"),
            "range": entry.get("range"),
            "gloss": _first_sentence(entry.get("scope_note") or "")
                     or ("archive-attested only; no current declaration"
                         if entry.get("status") != "current" else ""),
        }))

    for ident, entry in (onto.get("historical") or {}).items():
        rows.append(row(**{
            "id": ident, "kind": "class", "source": "historical",
            "label": entry.get("label") or "", "inverse": "",
            "parents": [], "children": [], "domain": None, "range": None,
            "gloss": f"no definition in v7.1.3; {entry.get('mentions', 0)} archive mentions",
        }))

    rows.sort(key=_sort_key)
    return rows
