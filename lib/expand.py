"""Bidirectional ontology lexicon and query expansion.

Closes the gap where BM25 is too literal (finds `E55`, misses "controlled
vocabularies") and embeddings are too vague (`E55` tokenizes to a semantically
empty `E` + `55`, landing near the unrelated E52 and E41).
"""

import re


def build_lexicon(onto: dict, stop_labels: list[str]) -> dict:
    """Build id<->label maps, excluding common-English single-word labels
    from the label->id direction only."""
    stop = {s.strip().lower() for s in stop_labels}
    id_to_labels: dict[str, list[str]] = {}
    label_to_ids: dict[str, list[str]] = {}

    def register(ident: str, labels: list[str]) -> None:
        clean = [lbl for lbl in labels if lbl]
        if not clean:
            return
        id_to_labels[ident] = clean
        for lbl in clean:
            key = lbl.lower()
            # Single-word common-English labels are dropped from label->id.
            # Multiword labels ("Human-Made Object") are specific enough to keep.
            if " " not in key and key in stop:
                continue
            label_to_ids.setdefault(key, []).append(ident)

    for cid, entry in onto["classes"].items():
        register(cid, [entry["label"]])
    for pid, entry in onto["properties"].items():
        register(pid, [entry["direct_name"], entry["inverse_name"]])

    # Properties of properties (P14.1 "in the role of") contribute id->label
    # only. Six of the sixteen are labelled "has type", which is also P2's
    # direct name; adding them to label_to_ids would make a query mentioning
    # "has type" expand to seven identifiers, none of which appear as tokens
    # in the FTS index -- messages are tagged with id_pattern, whose capture
    # group discards the .N suffix. So the label->id direction is all cost.
    for pid, entry in (onto.get("property_of_property") or {}).items():
        if entry.get("label"):
            id_to_labels[pid] = [entry["label"]]

    return {"id_to_labels": id_to_labels, "label_to_ids": label_to_ids}


def expand_query(query: str, lexicon: dict, id_pattern: str) -> list[str]:
    """Return terms to add to the query. Never returns terms already present."""
    present = query.lower()
    added: list[str] = []
    claimed_spans: list[tuple[int, int]] = []  # (start, end) of matched labels

    def push(term: str) -> None:
        term_lower = term.lower()
        if term_lower not in present and term_lower not in [a.lower() for a in added]:
            added.append(term)

    def _overlaps_claimed(start: int, end: int) -> bool:
        """Check if a span overlaps with any already-claimed span."""
        for cs, ce in claimed_spans:
            if not (end <= cs or start >= ce):  # not disjoint => overlaps
                return True
        return False

    # id -> label. The `.1` suffix (P14.1) normalizes to its base property.
    for match in re.finditer(id_pattern, query):
        base = match.group(1)
        for label in lexicon["id_to_labels"].get(base, []):
            push(label)

    # label -> id, longest labels first so "Human-Made Object" wins over "Object".
    # Span claiming prevents shorter labels from matching inside longer matched labels:
    # without it, "activity" in "curation activity" would match after "curation activity"
    # did, adding both E87 and E7. The sort alone doesn't prevent this.
    for label in sorted(lexicon["label_to_ids"], key=len, reverse=True):
        match = re.search(r"\b" + re.escape(label) + r"\b", present)
        if match:
            # Only expand if this label's span doesn't fall inside an already-claimed span.
            if not _overlaps_claimed(match.start(), match.end()):
                claimed_spans.append((match.start(), match.end()))
                for ident in lexicon["label_to_ids"][label]:
                    push(ident)

    return added
