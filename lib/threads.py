# lib/threads.py
"""Stage 2: thread reconstruction from three signals.

Threading is load-bearing here: the episode index summarizes whole threads, so
a bad thread means summarizing a conversation that never happened. Subject-only
matching produces a bogus 33-message "issue" thread that is several unrelated
debates glued together -- hence the time guard on signal 3. Quote overlap
(signal 2) shares the same guard for the same reason: two messages can quote
the same external document without ever replying to each other.
"""

import re
from datetime import datetime

from lib.strip import strip_boilerplate, unquote_line

_WS = re.compile(r"\s+")
_QUOTE_LINE = re.compile(r"^\s*>+")
_DEFAULT_FOOTER_MARKER = "mailing list"


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def _parse_date(value: str | None) -> datetime:
    if not value:
        return datetime.min
    try:
        return datetime.fromisoformat(value).replace(tzinfo=None)
    except ValueError:
        return datetime.min


def normalized_quote_spans(
    record: dict, footer_marker: str = _DEFAULT_FOOTER_MARKER
) -> list[str]:
    """Normalized text of each quoted region in body_raw, for overlap matching.

    Reads body_raw, not body. lib.quotes strips a substantial single-block
    top-posted quote out of `body` with no marker at all once the reply is
    long enough -- that's the de-duplication the whole pipeline exists for,
    but it means `body` is exactly the field guaranteed not to have what this
    signal needs (measured: only 48 of 1,948 no-In-Reply-To messages carry a
    "| "-marked quote in `body`, vs. 154 with a real ">"-quoted span in
    `body_raw`). body_raw still has every quote, at every depth.

    body_raw also still has the Mailman list footer recursing into that
    quoted text at every depth (see lib.strip's docstring) -- identical
    across thousands of messages, and long enough on its own, paired with a
    quoted signature block, to clear the overlap threshold and link
    unrelated messages. Reuse lib.strip.strip_boilerplate (rule 1 fires at
    any quote depth) before extracting quote lines, so the probe is judged
    on quoted CONTENT, not quoted boilerplate.
    """
    lines = strip_boilerplate(record.get("body_raw", "").splitlines(), footer_marker)[0]
    quoted = [unquote_line(ln).strip() for ln in lines if _QUOTE_LINE.match(ln)]
    quoted = [ln for ln in quoted if ln]
    if not quoted:
        return []
    return [_WS.sub(" ", " ".join(quoted)).strip().lower()]


def build_threads(
    records: list[dict],
    max_subject_gap_days: int = 30,
    min_overlap_chars: int = 200,
    footer_marker: str = _DEFAULT_FOOTER_MARKER,
) -> dict:
    by_msgid = {r["message_id"]: r for r in records}
    dates = {r["id"]: _parse_date(r.get("date")) for r in records}
    uf = _UnionFind()
    for r in records:
        uf.find(r["id"])

    # Signal 1 — References graph.
    for r in records:
        links = list(r.get("references") or [])
        if r.get("in_reply_to"):
            links.append(r["in_reply_to"])
        for ref in links:
            target = by_msgid.get(ref)
            if target:
                uf.union(r["id"], target["id"])

    ordered = sorted(records, key=lambda r: dates[r["id"]])

    # Signal 2 — quote overlap, for the ~1,950 messages with no In-Reply-To.
    # Free: stage 1 already located every quote span. Only ever links backward.
    # Compared raw-to-raw: the probe comes from body_raw (see
    # normalized_quote_spans), and the target text quoted verbatim in an
    # earlier message survives in that earlier message's own body_raw too --
    # `body` may have had its spacing altered by boilerplate stripping.
    #
    # Guarded by the same max_subject_gap_days window as signal 3: this
    # signal has an analogous failure mode from a different angle -- two
    # messages quoting the same external document (e.g. an official
    # CIDOC-CRM scope note) rather than actually replying to each other.
    # Measured on the real corpus: gaps among genuine quote-overlap links
    # cluster inside a month, then nothing at all until one outlier 3.6
    # years out, so the same 30-day threshold that guards signal 3 cleanly
    # separates real replies from that failure mode here too.
    norm_bodies = [
        (r["id"], dates[r["id"]], _WS.sub(" ", r.get("body_raw", "")).strip().lower())
        for r in ordered
    ]
    for r in ordered:
        if r.get("in_reply_to"):
            continue
        for span in normalized_quote_spans(r, footer_marker):
            if len(span) < min_overlap_chars:
                continue
            probe = span[:min_overlap_chars]
            for other_id, other_date, other_body in norm_bodies:
                if other_id == r["id"] or other_date >= dates[r["id"]]:
                    continue
                if (dates[r["id"]] - other_date).days > max_subject_gap_days:
                    continue
                if probe in other_body:
                    uf.union(r["id"], other_id)
                    break

    # Signal 3 — subject fallback, guarded by a time window.
    last_seen: dict[str, tuple[str, datetime]] = {}
    for r in ordered:
        key = r.get("subject_norm") or ""
        if not key:
            continue
        prev = last_seen.get(key)
        if prev and (dates[r["id"]] - prev[1]).days <= max_subject_gap_days:
            uf.union(r["id"], prev[0])
        last_seen[key] = (r["id"], dates[r["id"]])

    groups: dict[str, list[dict]] = {}
    for r in records:
        groups.setdefault(uf.find(r["id"]), []).append(r)

    ranked = sorted(groups.values(), key=lambda g: min(dates[m["id"]] for m in g))
    threads = {}
    for i, members in enumerate(ranked):
        members.sort(key=lambda m: dates[m["id"]])
        threads[f"t{i:04d}"] = {
            "message_ids": [m["id"] for m in members],
            "root": members[0]["id"],
            "subjects": [m.get("subject", "") for m in members],
        }
    return threads
