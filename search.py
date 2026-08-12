#!/usr/bin/env python3
# search.py
"""Query CLI over the archive indexes.

Output is compact text with stable IDs: the agent reads a hit, then calls
`thread` or `show` to expand -- the same motion as grep-then-read.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from lib.retrieve import Retriever


def _day(date: str | None) -> str:
    return (date or "")[:10] or "?" * 10


def format_hits(hits: list[dict]) -> str:
    if not hits:
        return "No results."
    lines = []
    for i, h in enumerate(hits, 1):
        entities = f"  [{' '.join(h['entities'][:6])}]" if h.get("entities") else ""
        lines.append(
            f"{i:2d}. {_day(h['date'])}  {h['from_name'][:24]:24s}  {h['subject'][:52]}"
        )
        lines.append(f"    {h['message_id']}  thread={h['thread_id']}{entities}")
        snippet = " ".join((h.get("snippet") or "").split())
        lines.append(f"    {snippet[:160]}")
        lines.append("")
    return "\n".join(lines)


def format_message(rec: dict, raw: bool = False) -> str:
    lines = [
        f"Message-ID: {rec['message_id']}",
        f"Date:       {rec.get('date') or '(unknown)'}",
        f"From:       {rec.get('from_name')} <{rec.get('from_email')}>",
        f"Subject:    {rec.get('subject')}",
    ]
    if rec.get("entities"):
        lines.append(f"Entities:   {' '.join(rec['entities'])}")
    if rec.get("entities_historical"):
        lines.append(f"Historical: {' '.join(rec['entities_historical'])}")
    for att in rec.get("attachments") or []:
        lines.append(f"Attachment: {att['filename']} ({att['content_type']}, {att['size']}b)")
    lines.append("")
    lines.append(rec["body_raw"] if raw else rec["body"])
    return "\n".join(lines)


def format_episodes(episodes: list[dict]) -> str:
    if not episodes:
        return "No results."
    lines = []
    for i, ep in enumerate(episodes, 1):
        # Extension ids are indexed alongside core ones, so they are shown
        # alongside them too -- an episode about FRBRoo F3 would otherwise
        # display no entities at all.
        entities = " ".join(
            (ep.get("entities") or [])
            + (ep.get("entities_historical") or [])
            + (ep.get("entities_extension") or [])
        )
        # The date span is part of the routing decision, not decoration: this
        # archive spans 26 years and a 2001 debate is rarely the same question
        # as a 2020 one.
        start, end = _day(ep.get("date_start")), _day(ep.get("date_end"))
        span = start if start == end else f"{start}..{end}"
        lines.append(f"{i:2d}. [{ep.get('outcome', '?')}] {ep.get('topic', '')}")
        lines.append(f"    {span}")
        if ep.get("outcome_detail"):
            lines.append(f"    {ep['outcome_detail'][:200]}")
        if entities:
            lines.append(f"    entities: {entities}")
        # Summaries route, they never answer.
        lines.append(f"    read the messages: search.py thread {ep['thread_id']}")
        lines.append("")
    return "\n".join(lines)


def format_documents(hits: list[dict]) -> str:
    """Render reference-document hits with unmissable provenance.

    A narrative hit leads with its bracketed section path (a definitions
    and modelling-rules document, so ~300 chars of snippet beats the message
    formatter's ~160); a declaration hit leads with its heading instead --
    that heading already carries the concept id (`E55 Type`, `P2 has type
    (is type of)`), so there is no separate bracketed path to show. Every
    hit shows its `cite` string and its extracted concepts, so a reader can
    pivot straight to `search.py concept <id>`.
    """
    if not hits:
        return "No results."
    lines = []
    for i, h in enumerate(hits, 1):
        cite = h.get("cite", "")
        if h.get("kind") == "declaration":
            label = h.get("heading") or h.get("concept_id") or "?"
        else:
            path = " > ".join(h.get("section_path") or [])
            label = f"[{path or h.get('heading', '')}]"
        lines.append(f"{i:2d}. {label}    {cite}")
        snippet = " ".join((h.get("text") or "").split())
        lines.append(f'    "{snippet[:300]}"')
        seen: set[str] = set()
        concepts = []
        for c in (h.get("entities") or []) + (h.get("entities_historical") or []):
            if c not in seen:
                seen.add(c)
                concepts.append(c)
        if concepts:
            lines.append(f"    concepts: {' '.join(concepts)}")
        # The chunk id, spelled as the command that consumes it. Without this
        # the reader can see a passage and have no way to name it: `quote`
        # needs `crm732#E12`, and all this block used to show was "E12
        # Production". Measured over 433 quote calls in one evaluation run,
        # 64 (15%) passed an invented id -- `E12`, `decl:E12`, `crm:E12`,
        # `E12_Production` -- and every one of them failed. The minutes ids
        # in that same run were almost all correct, because format_issue
        # already prints them this way (see the meetings block below).
        lines.append(f'    verify a quote: search.py quote {h.get("chunk_id", "?")} "..."')
        lines.append("")
    return "\n".join(lines)


def format_quote_result(result: dict) -> str:
    """Render `Retriever.find_quote`'s structured result -- the CLI surface
    an answering agent uses to check itself before asserting a quote.

    Leads with FOUND/NOT FOUND in the first two lines so a caller scripting
    against this (or just skimming) never has to parse prose to get the
    verdict; everything after that is where and why.
    """
    kind = result.get("source_kind")
    lines = [f"Source: {result['source_id']}" + (f" ({kind})" if kind else "")]
    if kind is None:
        lines.append("UNKNOWN SOURCE")
        lines.append(f"  {result.get('error', '')}")
        return "\n".join(lines)

    if result["found"]:
        lines.append("FOUND")
        if kind in ("thread", "episode"):
            where = f"message [{result.get('message_index')}]  {result.get('author')}  {result.get('message_id')}"
            if kind == "episode":
                where += f"  (thread {result.get('thread_id')})"
            lines.append(f"  {where}")
        elif kind == "message":
            lines.append(f"  author: {result.get('author')}  {result.get('message_id')}")
        elif kind == "document":
            path = " > ".join(result.get("section_path") or []) or result.get("heading") or ""
            lines.append(f"  [{path}]  {result.get('cite') or ''}")
        lines.append(f'  "{result["context"]}"')
    else:
        lines.append("NOT FOUND")
        closest = result.get("closest")
        if not closest:
            lines.append("  no similar text found in this source either.")
        else:
            score_pct = f"{closest['score'] * 100:.0f}%"
            if kind in ("thread", "episode"):
                lines.append(
                    f"  closest match ({score_pct} of the phrase, contiguous): "
                    f"message [{closest.get('message_index')}]  {closest.get('author')}"
                )
            else:
                lines.append(f"  closest match ({score_pct} of the phrase, contiguous):")
            lines.append(f'  "{closest["excerpt"]}"')
    return "\n".join(lines)


def format_issue(issue: dict) -> str:
    """One SIG issue: the register's verdict, then the debate in date order.

    The status line comes first because it is the thing the archive alone
    cannot tell you. A blind evaluation scored 1/8 on "was this ever
    resolved?", with answers reporting that a thread "trails off" -- which it
    does, because the resolution usually arrives years later in a different
    thread under the same issue number.

    `outcome` (the SIG's own statement of the resolution, scraped from its
    issue page -- see lib.issue_pages) renders right under Status when
    present, and is silently omitted otherwise: an Open issue has none, and
    showing nothing here must never read as "nothing was decided" being
    itself a finding -- it means the page has no outcome text, full stop.
    `references` (that page's own curated cross-reference list) renders
    after the threads, each with the `issue` verb that reaches it directly.
    Neither key is guaranteed to exist on an issue built before Task 20, so
    both are read with `.get`.
    """
    span = f"{_day(issue.get('first_mention'))} .. {_day(issue.get('last_mention'))}"
    lines = [
        f"Issue {issue['id']}  {issue.get('title') or ''}",
        "",
    ]
    # The published register has seven gaps (113, 114, 119, 201, 217, 540,
    # 641) and the minutes discuss at least two of them by number -- "Issue
    # 113: Right and Legal Object" was on the agenda at Chios in 2002. Those
    # issue numbers existed and were later dropped or renumbered, so the
    # minutes are their only surviving record. Rendering a blank Status for
    # them would read as "not yet decided"; the truth is that the register no
    # longer lists the issue at all.
    if not issue.get("status") and not issue.get("title"):
        lines.append(
            "Status:   not listed in the current register — this number is one of "
            "its gaps.\n          The record below is what the archive still holds.")
    else:
        lines.append(
            f"Status:   {issue.get('status') or '?'}"
            + (f"   (closed {_day(issue['closing_date'])})"
               if issue.get("closing_date") else ""))
    if issue.get("family_model"):
        lines.append(f"Model:    {', '.join(issue['family_model'])}")
    if issue.get("url"):
        lines.append(f"Register: {issue['url']}")
    if issue.get("outcome"):
        lines += ["", "Outcome (the SIG's own statement of the resolution):",
                  f"  {issue['outcome']}"]
    # 403 of the 715 issues have a page but were never cited by number on the
    # list. Printing a date span for those rendered as "?????????? .. ??????????";
    # absence of discussion is a fact about the archive, so say it.
    if issue.get("thread_count"):
        lines += ["", f"Discussed across {issue['thread_count']} thread(s), {span}:"]
    elif issue.get("status") or issue.get("title"):
        lines += ["", "No mailing-list thread cites this issue by number.",
                  "The record above is the register's; there is no archive debate to read."]
    else:
        # A register gap: there is no entry above to refer back to, so the
        # older wording ("the record above is the register's") described
        # something that is not on the screen.
        lines += ["", "No mailing-list thread cites this issue by number, and the",
                  "register no longer lists it. The minutes below are all that survives."]
    for t in issue.get("threads") or []:
        when = _day(t.get("first_mention"))
        cites = t.get("mentions", 0)
        lines.append(f"  {when}  {t['thread_id']}   {cites} mention(s)")
        lines.append(f"       search.py thread {t['thread_id']}")
    # The meetings that took the issue up. This is the closest thing the
    # corpus has to a record of the decision being made: the register states
    # that an issue was closed at a named meeting, the mailing list argues
    # towards it, and the minutes are the room. An issue with no thread often
    # still has minutes -- that combination is why this block is not folded
    # into the thread list above.
    meetings = issue.get("meetings") or []
    if meetings:
        lines += ["", f"Taken up at {len(meetings)} SIG meeting(s):"]
        for meeting in meetings:
            when = meeting.get("date") or "date not parsed"
            lines.append(f"  {when}  {meeting.get('title', '')[:70]}")
            lines.append(f"       {meeting.get('heading', '')[:74]}")
            if meeting.get("chunk_id"):
                lines.append(f"       search.py quote {meeting['chunk_id']} \"...\"")
            else:
                lines.append("       (agenda item recorded with no discussion text)")

    if issue.get("references"):
        lines += ["", "References (this issue's own cross-references, per the SIG's page):"]
        for ref in issue["references"]:
            lines.append(f"  Issue {ref['id']}  {ref.get('title', '')}")
            lines.append(f"       search.py issue {ref['id']}")
    # The register records an outcome; it does not record the argument. Only
    # the messages carry that, so the status must not be read as a summary.
    lines += ["", "The status above is the register's, not a summary of the debate.",
              "Read the threads for the reasoning."]
    return "\n".join(lines)


def concept_chronology(episodes: list[dict], ident: str) -> list[dict]:
    """Episodes touching this concept, oldest first.

    Matches entities, entities_historical AND entities_extension: 135 episodes
    carry only a family id (FRBRoo, CRMsci, ...), never a core CRMbase one, so
    without the third field their chronologies would be empty.
    """
    matched = [
        ep for ep in episodes
        if ident in (ep.get("entities") or [])
        or ident in (ep.get("entities_historical") or [])
        or ident in (ep.get("entities_extension") or [])
    ]
    return sorted(matched, key=lambda e: e.get("date_start") or "")


def _format_siblings(entry: dict, siblings: list[dict], cap: int = 10) -> list[str]:
    """The discrimination aid: what `entry` is chosen ALONGSIDE, not just
    what it is. Historical and extension buckets have no hierarchy to draw
    siblings from and render nothing here -- that's correct, not a gap.
    """
    bucket = entry.get("bucket")
    if bucket not in ("classes", "properties"):
        return []
    noun, noun_pl = ("subclass", "subclasses") if bucket == "classes" else \
        ("subproperty", "subproperties")
    parents = entry.get("sub_class_of" if bucket == "classes" else "sub_property_of") or []
    if not parents:
        return [f"Siblings: none -- {entry['id']} has no parent, so nothing else "
                "shares its level to discriminate against."]
    if not siblings:
        return [f"Siblings: none -- {entry['id']} is the only {noun} of "
                f"{', '.join(parents)}."]
    lines = [f"Siblings (other {noun_pl} of {', '.join(parents)}):"]
    for s in siblings[:cap]:
        lines.append(f"  {s['id']:6s} {s['label']:24s} -- {s['gloss']}")
    if len(siblings) > cap:
        lines.append(f"  ... and {len(siblings) - cap} more (not shown).")
    return lines


def _format_declaration(entry: dict, declaration: dict | None) -> list[str]:
    """First-order logic and full path, from the 7.3.2 declaration -- the
    formal constraint (often the sharpest discriminator between siblings)
    and, for a shortcut property, what it stands for.

    Tagged as 7.3.2 because that is where these are read from; everything
    else in this dossier is v7.1.3. The full path exists only in 7.3.2. The
    logic exists in both, and 7.3.2 is preferred for the reasons
    `Retriever.get_declaration` records.

    A concept can legitimately have no declaration (E38 is deprecated and
    7.3.2 dropped it entirely); that renders nothing here, not an error.
    """
    if entry.get("bucket") not in ("classes", "properties") or not declaration:
        return []
    fol = declaration.get("fol") or []
    full_path = declaration.get("full_path") or []
    if not fol and not full_path:
        return []
    lines = ["From CIDOC CRM v7.3.2 (not in the v7.1.3 XML above):"]
    if fol:
        lines.append("  In first-order logic:")
        lines += [f"    {ln}" for ln in fol]
    if full_path:
        lines.append("  Full path (what this shortcut stands for):")
        lines += [f"    {ln}" for ln in full_path]
    return lines


def _format_concept_narratives(ident: str, narratives: list[dict], cap: int = 3) -> list[str]:
    """Reference-document passages that mention this concept, most specific
    first, each with its section_path so it can be cited directly."""
    if not narratives:
        return [f"No CIDOC CRM v7.3.2 narrative passages mention {ident} directly."]
    lines = [f"Reference-document passages mentioning {ident} (CIDOC CRM v7.3.2):"]
    for rec in narratives[:cap]:
        path = " > ".join(rec.get("section_path") or []) or rec.get("heading", "")
        snippet = " ".join((rec.get("text") or "").split())
        lines.append(f"  [{path}]")
        lines.append(f'    "{snippet[:240]}"')
    if len(narratives) > cap:
        lines.append(
            f"  ... and {len(narratives) - cap} more mention(s) in the reference "
            "document (not shown)."
        )
    return lines


def _is_class_like(entry: dict) -> bool:
    """True when applicable-property tables mean anything for this entry.

    Properties do not have applicable properties, and a historical id has no
    declaration to derive them from. Extension entries are judged by whether
    they carry a `domain` (the same test lib.ontology._model_view uses to sort
    the extensions bucket into classes and properties) rather than by their
    letter, because the family models share no naming rule.
    """
    if entry.get("bucket") == "property_of_property":
        return False
    if entry.get("bucket") == "historical":
        return False
    if entry.get("bucket") == "extensions":
        return not entry.get("domain")
    return entry.get("bucket") == "classes" or "domain" not in entry


def _format_applicable(entry: dict, onto: dict | None) -> list[str]:
    """The properties this class can carry, in full and named.

    This block used to print two rows of at most twenty bare identifiers,
    ranked by property specificity alone. Both halves of that were wrong and
    the modelling evaluation paid for it:

      * the cap dropped real answers. E10 has 47 applicable outgoing
        properties; `P30 transferred custody of` -- which the CRM declares
        *necessary* -- sat outside the first twenty and was never shown at
        all. Same for P24 on E8 and P4 on every event class. So nothing is
        capped here. The largest class in the model renders 97 rows (~6KB),
        which is smaller than many of the scope notes printed above it.
      * ranking by specificity put P183/P134/P182 -- deep sub-properties whose
        domain is E1, applying to every class in the model -- at the head of
        every list. Ordering by how close the declaring class is puts P28/P29/
        P30 first for E10, which is what the reader came for.

    Names and ranges are printed because "P177" alone told the reader nothing:
    it appeared 17th of 20 anonymous integers for E13 and was missed.
    """
    if onto is None or not _is_class_like(entry):
        return []
    from lib.ontology import applicable_properties

    table = applicable_properties(onto, entry["id"])
    outgoing, incoming = table["outgoing"], table["incoming"]
    if not outgoing and not incoming:
        return []

    # An incoming row is this class seen from the far end, so its NAME is
    # already the inverse reading -- and printing that beside the forward
    # identifier said `P108  was produced by  E12`, which reads as
    # E22 --P108--> E12. That is backwards, and the validator rejects it. The
    # identifier written for an inverse reading carries the `i`.
    #
    # Only where an inverse genuinely exists. A literal-valued property has
    # no direction to read back: P82a's range is E61, so it appears in E61's
    # incoming list, and `P82ai` is a name the validator refuses -- the same
    # phantom the inverse-shorthand guard removes on the reading side.
    # Printing it here would hand a reader the identifier that guard exists
    # to reject, so those rows say so instead.
    from lib.ontology import _local_name, _model_view

    _, _props = _model_view(onto)

    def directed(r: dict) -> tuple[str, str]:
        if not r.get("inverse"):
            return r["id"], ""
        declared = _props.get(r["id"])
        if declared and _local_name(r["id"], declared, inverse=True):
            return f"{r['id']}i", ""
        return r["id"], "  (no inverse form; write it from the other end)"

    def row(r: dict, mark_required: bool = True) -> str:
        flag = "!" if (mark_required and r["required"]) else " "
        ident, note = directed(r)
        name = (r["name"] or "")[:34]
        return f"  {flag} {ident:7}{name:36} {r['other'] or ''}{note}".rstrip()

    lines = ["", f"Applicable properties — {len(outgoing)} outgoing, "
                 f"{len(incoming)} incoming"]

    required = [r for r in outgoing if r["required"]]
    if required:
        lines += ["", f"  Required — the CRM quantifies these as \"necessary\" "
                      f"on {entry['id']} or a parent:"]
        lines += [row(r, mark_required=False) for r in required]

    if outgoing:
        lines += ["", "  It can be the subject of "
                      "(declared closest to this class first; ! = required):"]
        lines += [row(r) for r in outgoing]
    if incoming:
        lines += ["", "  Things can point at it:"]
        lines += [row(r, mark_required=False) for r in incoming]
    return lines


def format_concept(entry: dict, chronology: list[dict], mentions: int,
                   onto: dict | None = None, siblings: list[dict] | None = None,
                   declaration: dict | None = None,
                   narratives: list[dict] | None = None) -> str:
    lines = []
    bucket = entry.get("bucket")
    if bucket == "historical":
        lines += [
            f"{entry['id']}  —  no definition in v7.1.3 (deprecated vocabulary)",
            "",
            "CIDOC CRM v7.1.3 no longer defines this identifier. The archive below",
            "is the only surviving record of what it meant and why it was removed.",
        ]
    elif bucket == "extensions":
        # Applicable properties DO now appear for family classes: the
        # hierarchy crosses models (CRMarchaeo declares A1 a subclass of E12),
        # so an extension class genuinely inherits CRMbase properties and the
        # merged walk in lib.ontology finds them.
        # Everything else now matches the CRMbase branch below in shape: scope
        # note, hierarchy, domain/range -- scraped from the model's own
        # declaration page (tools/fetch_crm_family.py), not v7.1.3.xml, hence
        # attribution stays front and center instead of being folded away.
        label = entry.get("label")
        model = entry.get("model") or "?"
        kind = entry.get("kind") or "?"
        status = entry.get("status", "current")
        header = f"{entry['id']}  {label}" if label else f"{entry['id']}  (no label recorded)"
        lines.append(header)
        lines.append(f"Model:  {model} ({kind})")
        if status == "current":
            lines.append(f"Status: current — {model}'s own declarations still carry this id.")
        else:
            lines.append(
                f"Status: historical — only this archive attests {entry['id']}; "
                f"{model}'s current declarations no longer carry it."
            )
        if entry.get("uri"):
            lines.append(f"URI:    {entry['uri']}")
        lines.append("")
        if entry.get("sub_class_of"):
            lines.append(f"Subclass of:      {', '.join(entry['sub_class_of'])}")
        if entry.get("super_class_of"):
            lines.append(f"Superclass of:    {', '.join(entry['super_class_of'])}")
        if entry.get("sub_property_of"):
            lines.append(f"Subproperty of:   {', '.join(entry['sub_property_of'])}")
        if entry.get("super_property_of"):
            lines.append(f"Superproperty of: {', '.join(entry['super_property_of'])}")
        if entry.get("domain") or entry.get("range"):
            lines.append(f"Domain -> Range:  {entry.get('domain')} -> {entry.get('range')}")
        if entry.get("scope_note"):
            lines.append("")
            lines.append(entry["scope_note"])
        else:
            lines.append("")
            lines.append(
                f"{entry['id']} belongs to {model}, not CRMbase: no scope note is on "
                f"file here -- see {model}'s own specification for its definition."
            )
    elif bucket == "property_of_property":
        parent = entry.get("of_property") or "?"
        lines += [
            f"{entry['id']}  {entry.get('label') or '(no label recorded)'}"
            f"   [v7.1.3 (current)]",
            "",
            f"A property of the property {parent}, not a property of a class:",
            f"it qualifies the {parent} relationship itself rather than either",
            "of the things that relationship connects.",
            "",
            f"Range:  {entry.get('range') or '?'}",
            f"Of:     {parent}",
            "",
            f"Its domain is the {parent} relationship, which is why none is",
            f"recorded here. See `search.py concept {parent}` for the",
            "relationship it qualifies, and its scope note and examples.",
            "",
            # The archive's entity index is built with id_pattern, whose
            # capture group drops the .N suffix, so "P14.1" in a message is
            # recorded as "P14". A count here would always be 0 and would
            # read as "never discussed", which is not what it would mean.
            f"Mentions are not tracked separately for {entry['id']}: the",
            f"archive's entity index records {parent}. Use",
            f"`search.py concept {parent}` for the discussion.",
        ]
    else:
        # Most entries come from cidoc_crm_v7.1.3.xml, but a few are declared
        # only by the newer specification (E100, P199, P200). Saying v7.1.3
        # for those would misattribute a scope note the reader may be
        # comparing against a genuine v7.1.3 one.
        version = entry.get("source") or "v7.1.3"
        lines.append(f"{entry.get('full_name', entry['id'])}   [{version} (current)]")
        lines.append("")
        # The URI, for a reader who is about to write RDF. Family entries have
        # printed theirs all along because they carry a stored `uri`; CRMbase
        # derives its own and so printed none, which meant a modeller working
        # in pure CRMbase never saw a single URI from any tool and had to
        # invent the spelling. Measured, not supposed: of four agents asked to
        # write Turtle using only this server, the one that got the convention
        # from the tools got it from a CRMsci class whose card happened to
        # show a URI, then confirmed by validating a throwaway file; the two
        # that used no family classes never saw one at all.
        #
        # The rule is not guessable from a label -- spaces become underscores
        # but hyphens survive inside words, so "has time-span" is
        # P4_has_time-span and not P4_has_time_span. `_local_name` is what
        # `uri_index` is built from, so this prints the spelling the validator
        # will actually accept rather than a second guess at it.
        if onto is not None:
            from lib.ontology import CRM_NAMESPACE, _local_name, _model_view

            classes, properties = _model_view(onto)
            declared = classes.get(entry["id"]) or properties.get(entry["id"])
            local = _local_name(entry["id"], declared) if declared else None
            if local:
                lines.append(f"URI:            {CRM_NAMESPACE}{local}")
                inverse = _local_name(entry["id"], declared, inverse=True)
                if inverse:
                    lines.append(f"  inverse:      {CRM_NAMESPACE}{inverse}")
                lines.append("")
        if entry.get("sub_class_of"):
            lines.append(f"Subclass of:    {', '.join(entry['sub_class_of'])}")
        if entry.get("sub_property_of"):
            lines.append(f"Subproperty of: {', '.join(entry['sub_property_of'])}")
        if entry.get("domain") or entry.get("range"):
            lines.append(f"Domain -> Range: {entry.get('domain')} -> {entry.get('range')}")
        if entry.get("quantification"):
            lines.append(f"Quantification: {entry['quantification']}")
        if entry.get("scope_note"):
            lines.append("")
            lines.append(entry["scope_note"])
        for example in entry.get("examples") or []:
            lines.append(f"  e.g. {example}")

    # A label the reader typed matched more than one concept. get_concept
    # answers with the first and carries the rest here; saying nothing would
    # make `concept "consists of"` a confidently wrong answer, since it
    # returns P5 Condition State when the reader almost certainly means P45.
    if entry.get("also_matches"):
        others = " ".join(entry["also_matches"])
        lines += [
            "",
            f'NOTE: "{entry.get("matched_label")}" also names {others}.',
            f"      Shown above is {entry['id']}. A property label does not identify",
            "      a property -- 14 of them are shared. Ask by identifier, or use",
            f'      `search.py validate <subject> "{entry.get("matched_label")}" <object>`',
            "      to see which reading your two classes actually permit.",
        ]

    siblings_lines = _format_siblings(entry, siblings or [])
    if siblings_lines:
        lines.append("")
        lines += siblings_lines

    declaration_lines = _format_declaration(entry, declaration)
    if declaration_lines:
        lines.append("")
        lines += declaration_lines

    lines += _format_applicable(entry, onto)

    lines.append("")
    lines += _format_concept_narratives(entry["id"], narratives or [])

    # "Mentions" is ambiguous on its own: data/ontology.json's own count (used
    # below for the extensions bucket) is raw identifier occurrences across
    # subject+body, while every other bucket here is a distinct-message count
    # (built in main(), by scanning each message's already-deduplicated entity
    # list). Both are legitimate and neither is changed here -- only the label
    # says which one is on screen, so "113 raw mentions" and "52 messages" for
    # the same id (E84) are not mistaken for a contradiction.
    if bucket != "property_of_property":
        if bucket == "extensions":
            mentions_label = f"Mentions in the archive (raw {entry['id']} occurrences, subject+body)"
        else:
            mentions_label = f"Mentions in the archive (messages whose entity list contains {entry['id']})"
        lines += ["", f"{mentions_label}: {mentions:,}", ""]

    # A blind evaluation found this to be the system's main way of being
    # confidently wrong. Readers inferred a thread's outcome from the state of
    # the standard -- "P107.1 exists in v7.1.3, so the SIG must have adopted it
    # in that debate" -- and, in the other direction, from an episode's outcome
    # tag -- "tagged unresolved, so nothing was decided". Neither follows. The
    # current standard is the sum of 26 years of changes and says nothing about
    # any one debate, and an outcome tag is a summariser's reading of one run of
    # messages. Only the messages settle it, so the caveat sits right where the
    # bad inference gets made.
    lines += [
        "Above is the CURRENT standard, not a record of any past decision. Whether",
        "an identifier exists today does not establish what was decided in any",
        "particular debate below -- read the messages to find that out.",
        "",
    ]

    if chronology:
        lines.append(f"Debated in {len(chronology)} episodes, oldest first "
                     "([outcome] is a summary's reading, not a verified fact):")
        for ep in chronology:
            lines.append(
                f"  {(ep.get('date_start') or '?')[:10]}  "
                f"[{ep.get('outcome', '?')}]  {ep.get('topic', '')[:70]}"
            )
            lines.append(f"       search.py thread {ep['thread_id']}")
    else:
        lines.append("No episodes reference this concept.")

    return "\n".join(lines)


def format_thread(records: list[dict]) -> str:
    if not records:
        return "No such thread."
    out = []
    for i, rec in enumerate(records, 1):
        out.append(f"[{i}] {_day(rec.get('date'))}  {rec.get('from_name')}  "
                   f"{rec.get('subject')}")
        out.append(f"    {rec['message_id']}")
        out.append("")
        out.append(rec.get("body", ""))
        out.append("-" * 70)
    return "\n".join(out)


def format_validation(result: dict) -> str:
    """Render one link check.

    Always prints every candidate reading, not just the winning one. A
    property label does not identify a property -- "consists of" is P5, P9 or
    P45 -- so showing only the survivor would hide that the caller's own file
    is ambiguous and that a different pair of classes would resolve it
    differently.
    """
    head = f"{result['subject']} --{result['property']}--> {result['object'] or '?'}"
    lines = [head]
    if result.get("error"):
        return "\n".join([head, f"  ERROR: {result['error']}"])

    for c in result["candidates"]:
        if c["legal"] is None:
            mark = "n/a"
        else:
            mark = "LEGAL" if c["legal"] else "no"
        name = f"  {mark:6} {c['id']:8}"
        lines.append(f"{name} {c.get('name', '')[:34]:36}{c.get('direction', '')}")
        lines.append(f"         {c['reason']}")
        if c.get("required"):
            lines.append("         (the CRM quantifies this as necessary on its domain)")

    if result.get("ambiguous"):
        lines += ["", f"AMBIGUOUS: {' and '.join(result['ambiguous'])} are both legal "
                      "here.", "Name the identifier rather than the label."]
    elif result["resolved"]:
        lines += ["", f"Use {result['resolved']}."]
    elif not result["legal"]:
        lines += ["", "No reading of this link is legal. In the CRM that usually means",
                  "the relationship runs through an event -- try `connect` on the two",
                  "classes to see what does join them."]
    return "\n".join(lines)


def format_document_chunk(rec: dict) -> str:
    """One reference-document chunk, in full.

    `docs` deliberately shows a snippet -- it is a result page, and 20 hits
    at 2,000 characters each is not a result page. But nothing printed the
    whole thing, so the snippet was not a preview of something reachable, it
    was the ceiling. This is the `show` that `thread` already is for
    messages.
    """
    lines = [f"Chunk:    {rec.get('chunk_id')}",
             f"Kind:     {rec.get('kind')}",
             f"Source:   {rec.get('cite') or rec.get('doc_id') or '?'}"]
    path = " > ".join(rec.get("section_path") or [])
    if path:
        lines.append(f"Section:  {path}")
    if rec.get("heading"):
        lines.append(f"Heading:  {rec['heading']}")
    if rec.get("concept_id"):
        lines.append(f"Concept:  {rec['concept_id']}   "
                     f"(search.py concept {rec['concept_id']})")
    concepts = (rec.get("entities") or []) + (rec.get("entities_historical") or [])
    if concepts:
        lines.append(f"Mentions: {' '.join(dict.fromkeys(concepts))}")
    lines += ["", rec.get("text") or ""]
    return "\n".join(lines)


def format_document_validation(report: dict) -> str:
    """Render a whole-document check.

    Leads with the counts, then lists only the failures. An unresolved NAME
    is reported separately from an illegal link, because they call for
    different fixes: one is a property used where the CRM forbids it, the
    other is not a property at all.

    The structural elements skipped are named. Silently passing over an
    element this format uses for something other than a property would be
    indistinguishable, from the reader's side, from silently passing over a
    misspelling -- and the misspelling is what this exists to catch.
    """
    c = report["counts"]
    # `or "none"` used to sit at the end of this expression, where precedence
    # applied it to the whole concatenation -- always truthy, so the fallback
    # was unreachable and a claims-only document printed a bare
    # "0 links checked: " with a trailing colon and nothing after it.
    counted = ", ".join(f"{v} {k}" for k, v in sorted(c.items())) or "none"
    lines = [f"{report['links']} links checked: {counted}"]
    # These four names (CRM_Entity/in_class/unit/value) are elements of the
    # house XML example format; RDF has no structural elements to skip at
    # all. validate_document always fills this key regardless of which
    # reader produced the links -- so search.py's --rdf branch blanks it to
    # an empty list rather than let a fact about the XML format leak into an
    # RDF report -- and an absent key from any future caller reads the same
    # way. Printing it unconditionally here would say something untrue about
    # what an RDF document had skipped, on a format that skips nothing.
    if report.get("structural_elements_skipped"):
        lines.append(f"structural elements skipped: "
                     f"{' '.join(report['structural_elements_skipped'])}")
    # ok_literal is a pass, not a finding: a property whose range is a
    # literal (P3 has note) has no nested record to read a class from, and
    # its domain was checked all the same.
    # Class-label findings come first: they are about what the document
    # CALLS things, which no amount of link checking looks at. Both published
    # examples carry retired labels, so a document copied from them is wrong
    # in a way every other check passes over.
    for f in report.get("class_labels") or []:
        lines.append(f"  {f['verdict'].upper():14} {f['raw']}")
        lines.append(f"      {f['detail']}   at {f['path'] or '(root)'}")
    # owl:inverseOf claims come next -- after what the document calls things,
    # before whether its links are legal -- because a false claim about the
    # vocabulary invalidates every link that uses it. `ok` claims are not
    # printed individually (their count is in the header); the rest name the
    # exact pair asserted and why it does not hold.
    claims = report.get("inverse_claims") or []
    if claims:
        counts = Counter(c["verdict"] for c in claims)
        lines.append(f"{len(claims)} owl:inverseOf claims: "
                     + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))
        for c in claims:
            if c["verdict"] != "ok":
                lines.append(f"  {c['verdict'].upper():14} "
                             f"{c['subject']} inverseOf {c['object']}")
                lines.append(f"      {c['detail']}")
    bad = [f for f in report["findings"]
           if f["verdict"] not in ("ok", "ok_literal")]
    if any(f["verdict"] == "attached_to_property" for f in bad):
        lines.append("")
        lines.append("ATTACHED_TO_PROPERTY: a property nested inside a "
                     "literal-valued one, which")
        lines.append("the CRM models with a property-of-property and this "
                     "format cannot write. As")
        lines.append("encoded it asserts something else and untrue. Fold the "
                     "value into the text of")
        lines.append("the property it qualifies, or drop it.")
    if any(f["verdict"] == "ambiguous" for f in bad):
        lines.append("")
        lines.append("AMBIGUOUS links are legal but underdetermined. This format "
                     "writes property")
        lines.append("labels as element names, so the file cannot say which of "
                     "them it means --")
        lines.append("record the intent in your notes; there is nothing to fix "
                     "in the document.")
    # A false inverseOf claim belongs in this all-clear gate too: it is
    # already named above, but a document with no other findings and no
    # class-label problems would otherwise close on "every link resolves...
    # and every class is named as the model names it" -- true of the links,
    # and silent about the one thing on screen that is actually wrong. Found
    # by hand: a file carrying nothing but `P108i owl:inverseOf P14` (0 links,
    # since the claim triple itself is skipped from the link stream) prints
    # exactly that all-clear sentence directly under a CONTRADICTED line,
    # while search.py's own exit code -- driven by the same "wrong" test --
    # disagrees with it and exits 1.
    wrong_claims = [c for c in claims
                   if c["verdict"] in ("contradicted", "not_invertible")]
    if not bad and not (report.get("class_labels") or []) and not wrong_claims:
        lines.append("\nEvery link resolves to a real property and stays inside "
                     "its declared domain and range, and every class is named "
                     "as the model names it.")
    else:
        lines.append("")
        for f in bad:
            lines.append(f"  {f['verdict'].upper():14} {f['name']}")
            # `name` is the resolved CRM property (P108i), never the raw
            # predicate -- it has to be, because validate_document can only
            # check a property it can look up by name, and the header above IS
            # that lookup. A bridged predicate (Task 6) makes this a problem for
            # the reader rather than the checker: `ex:madeBy` bridged to P108
            # resolves and is checked as `P108i`, but the string "P108i" does
            # not occur anywhere in the document, so a reader cannot find what
            # to fix from this line alone. `predicate_uri` already carries what
            # was actually written, on every finding (see crm_rdf_links) -- it
            # is just never shown.
            #
            # Printed only when it is genuinely informative, not on every
            # finding: an ORDINARY CRM predicate's own URI is built (see
            # _local_name) so its local segment always STARTS WITH its resolved
            # id -- P108i_was_produced_by starts with P108i -- so that relation
            # alone tells a native CRM URI from a bridged, foreign one (whose
            # local segment shares no such relationship with what it resolved
            # to) without adding a line to every finding in every RDF report.
            # The XML reader never sets `predicate_uri` at all, so this never
            # fires there either.
            raw = f.get("predicate_uri")
            if raw and raw != f["name"]:
                local = raw.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
                if not local.lower().startswith(f["name"].lower()):
                    lines.append(f"      written in the document as {raw}, "
                                 f"checked as CRM property {f['name']}")
            lines.append(f"      {f['subject']} -> {f['object']}   at {f['path']}")
            lines.append(f"      {f['detail'][:150]}")
    # Opt-in (`--completeness`) and always last, after every failure above --
    # never the reverse, because a reader who saw this first, and only this,
    # could mistake "the model expects more" for a verdict on what is here,
    # which is not what it is. `report["completeness"]` is absent unless the
    # flag was passed, so a plain `validate` run -- which is every run before
    # this feature existed, and every one of the 691 tests that predate it --
    # never reaches this branch and this function's output for them is
    # unchanged, byte for byte.
    completeness = report.get("completeness") or []
    if completeness:
        lines.append("")
        lines.append("NOT STATED -- not errors. The specification calls "
                     "quantifiers \"semantic clarification")
        lines.append("only\" and says every property \"should be implemented "
                     "as optional\" (crm732#s0037);")
        lines.append("a missing property below is guidance, and did not "
                     "affect the verdict above.")
        # Ordered by the section's own thesis instead of alphabetically.
        # The header tells the reader that 1-of-9 is likely an oversight and
        # 9-of-9 likely a modelling convention -- and then, sorted by class
        # id, buried the first among the second. Measured on crm_bayeux.xml:
        # 135 rows, of which 99 are wholly absent and 36 partial, so the
        # signal was 27% of a wall of text with nothing to separate it.
        #
        # Partial rows first, rarest omission at the top, because a property
        # nine instances out of ten already carry is the one worth looking
        # at. Nothing is dropped -- the wholly-absent rows follow.
        partial = sorted((c for c in completeness if c["missing"] < c["instances"]),
                         key=lambda c: (c["missing"] / c["instances"],
                                        c["class_id"], c["property_id"]))
        absent = [c for c in completeness if c["missing"] >= c["instances"]]
        if partial:
            lines.append("")
            lines.append("  Partly stated -- some instances carry it, these "
                         "do not. Likeliest oversights first:")
            for c in partial:
                # Spelled "N of M lack it", not "N/M". The bare ratio was read
                # as a coverage score by a careful reader, who then reported a
                # bug when adding an assertion moved 3/6 to 2/6 -- correct
                # behaviour (one fewer instance lacks it) that looks like a
                # regression if the number is taken to mean coverage. The
                # column heading said "missing" and that was not enough.
                pct = round(100 * c["missing"] / c["instances"])
                lines.append(f"    {c['class_id']:6} {c['property_id']:6} "
                             f"{c['property_name'][:34]:34} "
                             f"{c['missing']:>4} of {c['instances']:<4} lack it"
                             f" {pct:>4}%")
        if absent:
            # Collapsed by property, because that is the shape of the fact.
            # P10, P12, P160 and P161 each recurred at n/n across fourteen
            # event classes on crm_bayeux -- one decision about temporal
            # projections, printed fifty-six times. Grouping restates it once
            # and keeps every class that expects it on the line.
            by_property: dict[str, list[dict]] = {}
            for c in absent:
                by_property.setdefault(c["property_id"], []).append(c)
            lines.append("")
            lines.append("  Never stated -- no instance of any class below "
                         "carries these. Usually a")
            lines.append("  modelling convention rather than an omission, "
                         "one fact per property:")
            for pid, rows in sorted(
                    by_property.items(),
                    key=lambda kv: (-sum(r["instances"] for r in kv[1]), kv[0])):
                classes = " ".join(sorted(r["class_id"] for r in rows))
                total = sum(r["instances"] for r in rows)
                lines.append(f"    {pid:6} {rows[0]['property_name'][:38]:38} "
                             f"{total:>4} instances across {len(rows)} class"
                             f"{'es' if len(rows) > 1 else ''}")
                lines.append(f"           {classes}")
    return "\n".join(lines)


def format_ontology(rows: list[dict], onto: dict | None = None) -> str:
    """The whole model, one line per identifier, nothing hidden.

    Three columns changed from the CRMbase-only version this replaces.

    `source` names the model an identifier belongs to, so CRMbase stays
    distinguishable now that the family extensions and the historical
    vocabulary are listed beside it. Without it a reader cannot tell a
    normative class from one belonging to CRMsci or from one the standard
    dropped years ago.

    Properties show BOTH directions, `direct (inverse)`, matching the header
    `concept <id>` already prints. The inverse was in the data all along and
    only the text renderer dropped it -- and it is not decoration: the
    published CIDOC CRM example encodings use property labels as XML element
    names in whichever direction the nesting runs, so `is documented in` is
    the only usable form of P70 half the time.

    Names are never truncated. Roughly 8% of rows overrun the column and push
    the rest of the line right; that is deliberate. A clipped identifier or a
    clipped property label is one a reader cannot copy, and the whole point
    of this listing is that its contents can be used without looking anywhere
    else. Only the gloss, which is orientation and not payload, is cut.
    """
    lines = []
    # The name column carries the RDF local name where one exists, not the
    # prose label -- `E22_Human-Made_Object` rather than `Human-Made Object`.
    # It reads the same and it can be pasted into a document.
    #
    # Measured, which is why this changed: eight agents wrote Turtle using
    # only this server, and one spent about forty of its sixty-nine calls on
    # `crm_concept` "purely to get exact RDF-safe local names", one per
    # identifier, because `crm_concept` was the only tool that showed a URI
    # and it shows exactly one. Cohort throughput halved, 4.0 links per call
    # to 1.9. This listing already prints every identifier; printing the
    # spelling beside it turns N calls into one.
    #
    # Derived, never rebuilt from the label here: the rule keeps a hyphen
    # inside a word but turns a space into an underscore, so `has time-span`
    # is `P4_has_time-span`, and the family entries hide their inverse inside
    # a combined label. `_local_name` is what `uri_index` is built from, so
    # what prints is what the validator will accept.
    # The namespaces, once at the top, because a local name is only half of
    # a URI and the other half is not guessable either: PRESSoo lives at
    # http://www.iflastandards.info/fr/pressoo/ and LRMoo at
    # http://iflastandards.info/ns/lrm/lrmoo/ -- a different host and a
    # different path, down to the `www.`.
    namespaces: dict[str, str] = {}
    local_of = {}
    if onto is not None:
        from lib.ontology import _local_name, _model_view

        classes, properties = _model_view(onto)
        pop = onto.get("property_of_property") or {}
        for ident in {r["id"] for r in rows}:
            entry = classes.get(ident) or properties.get(ident) or pop.get(ident)
            if entry:
                local_of[ident] = (_local_name(ident, entry),
                                   _local_name(ident, entry, inverse=True))
        from lib.ontology import CRM_NAMESPACE, _namespace_of

        for row in rows:
            if row["source"] in namespaces:
                continue
            entry = (classes.get(row["id"]) or properties.get(row["id"])
                     or pop.get(row["id"]) or {})
            if entry.get("uri"):
                namespaces[row["source"]] = _namespace_of(entry["uri"])
            elif row["source"] == "CRMbase":
                namespaces[row["source"]] = CRM_NAMESPACE
    for s in rows:
        if s["kind"] == "class":
            rel = f"< {' '.join(s['parents'])}" if s["parents"] else "(root)"
        else:
            rel = f"{s['domain'] or '--'} -> {s['range'] or '--'}"
        forward, inverse = local_of.get(s["id"], (None, None))
        if forward:
            name = f"{forward} ({inverse})" if inverse else forward
        else:
            # Historical ids have no label to build one from, and no URI: the
            # standard dropped them. Falling back to the prose label keeps the
            # row informative instead of blank.
            name = s["label"] or "(no label recorded)"
            if s["kind"] == "property" and s.get("inverse"):
                name = f"{name} ({s['inverse']})"
        lines.append(f"{s['source']:11s} {s['id']:7s} {name:52s} "
                     f"{rel:22s} {s['gloss'][:52]}".rstrip())
    if namespaces:
        head = ["Namespaces (the name column is the local part; prepend these):"]
        head += [f"  {model:11s} {ns}" for model, ns in sorted(namespaces.items())]
        head.append("")
        lines = head + lines
    return "\n".join(lines)


def format_connect(subject: str, obj: str,
                   forward: list[dict], backward: list[dict],
                   full_paths: dict[str, list[str]] | None = None) -> str:
    """Which properties can join two classes, in both directions.

    The query the interface could not previously express. Every other verb
    starts from an identifier you already have; this one starts from the two
    ends of a relationship you are trying to express and finds the property in
    between. The strict review kept recording the same miss -- an answer with
    the right classes and no way to discover the property joining them -- and
    P33 (E11 -> E29), P43 (E70 -> E54), P10 (E92 -> E92), P156 (E18 -> E53)
    and P14 (E7 -> E39) were all found by exactly this test.

    An empty result is a real answer, not a failure, and says so: no property
    links an E20 Biological Object directly to an S13 Sample because CRMsci
    routes that through the S2 Sample Taking event.

    Where a property is a shortcut, the CRM declares what it stands for --
    "Full path:" in the 7.3.2 declaration, with the mediating class named.
    25 of 244 declarations carry one. Those are the authored two-hop
    patterns; computing paths instead was measured and rejected, because
    175 of 300 classes are viable intermediates for every pair.
    """
    full_paths = full_paths or {}

    def block(title: str, rows: list[dict]) -> list[str]:
        if not rows:
            return [title, "  (none declared)"]
        out = [title]
        for r in rows:
            flag = "!" if r["required"] else " "
            exact = "" if not r["exact"] else "   <- declared on exactly this pair"
            out.append(f"  {flag} {r['id']:6}{(r['name'] or '')[:34]:36}"
                       f"{r['domain']} -> {r['range']}{exact}")
            for line in full_paths.get(r["id"], []):
                out.append(f"      Full path: {line}")
        return out

    lines = [f"Properties joining {subject} and {obj}", ""]
    lines += block(f"{subject} -> {obj}:", forward)
    # A class connected to itself has one direction, not two: the backward
    # query is the same query, and printing it again doubled the output of
    # `connect E21 E21` for no information.
    if subject != obj:
        lines += [""]
        lines += block(f"{obj} -> {subject}:", backward)
    if not forward and not backward:
        lines += [
            "",
            "No property connects these two directly. In the CRM that usually",
            "means the link runs through an event: look for a class that can",
            "point at both, e.g. `search.py concept " + subject + "` and read",
            "the 'Things can point at it' table for a shared event class.",
        ]
    else:
        lines += ["", "! = the CRM quantifies this property as \"necessary\" on its domain."]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Search the CRM-SIG archive")
    parser.add_argument(
        "query",
        help="query text, or a subcommand: show | thread | threads | docs | concept | connect | ontology | quote | issue | issues",
    )
    parser.add_argument("target", nargs="?",
                        help="id/query, when query is show/thread/threads/docs/quote/issue/connect")
    parser.add_argument("phrase", nargs="?",
                        help='the quoted phrase, when query is "quote"; '
                             'the second class, when query is "connect"')
    parser.add_argument("obj", nargs="?",
                        help='the object class, when query is "validate"')
    parser.add_argument("-k", type=int, default=10)
    parser.add_argument("--mode", choices=["hybrid", "vector", "bm25"], default="hybrid")
    parser.add_argument("--no-expand", action="store_true")
    parser.add_argument("--from", dest="from_email")
    parser.add_argument("--after", type=int)
    parser.add_argument("--before", type=int)
    parser.add_argument("--entity")
    parser.add_argument(
        "--kind", choices=["declaration", "narrative", "issue", "minutes",
                           "principles"],
        help="docs: restrict to declarations, narrative guidance, issue pages, "
             "SIG meeting minutes, or the Conceptual Modelling Principles",
    )
    parser.add_argument(
        "--model",
        help="ontology: list one model only (CRMbase, CRMsci, CRMarchaeo, "
             "historical, ...). Omit to list every identifier.",
    )
    parser.add_argument(
        "--xml",
        help="validate: a document in the published CIDOC CRM example format; "
             "checks every element name AS WRITTEN, not a transcription of it",
    )
    parser.add_argument(
        "--rdf",
        help="validate: a CRM model in Turtle, RDF/XML, N-Triples or JSON-LD; "
             "format inferred from the extension",
    )
    parser.add_argument(
        "--file",
        help="validate: a JSON list of [subject, property, object] triples",
    )
    parser.add_argument(
        "--completeness", action="store_true",
        help="validate --xml/--rdf: also report what the model expects an "
             "instance to carry that this document never states. Guidance, "
             "not a verdict -- never fails the check and is silent unless "
             "asked for; see format_document_validation.",
    )
    parser.add_argument("--raw", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--archive", default="crm-sig")
    args = parser.parse_args()

    r = Retriever(args.archive)

    if args.query == "show" and args.target:
        rec = r.get_message(args.target)
        if rec is None and args.target in r.documents:
            # A document chunk, not a message. `docs` prints a 300-character
            # snippet of chunks that run to 2,000 and beyond, and nothing
            # else would print the rest: an agent could find a passage, read
            # a sixth of it, and have no way to reach the remainder except
            # guessing phrases for `quote`. One did exactly that, and
            # reconstructed a modelling principle by repeated probing --
            # which only works if you can already guess the wording.
            doc = r.documents[args.target]
            print(json.dumps(doc, ensure_ascii=False, indent=2) if args.json
                  else format_document_chunk(doc))
            return
        if rec is None:
            raise SystemExit(
                f"No such message or document chunk: {args.target}\n"
                "(document chunk ids look like crm732#E12 or crm732#s0071 "
                "and are printed by `docs`)")
        print(json.dumps(rec, ensure_ascii=False, indent=2) if args.json
              else format_message(rec, raw=args.raw))
        return

    if args.query == "validate":
        from lib.ontology import validate_link

        # One triple, or a file of them. A model is checked as a whole or not
        # at all: an agent that must issue one call per link will check the
        # links it already doubts and skip the rest, which is the opposite of
        # what a validator is for.
        if args.xml:
            from lib.ontology import (crm_example_class_uses, crm_example_links,
                                      validate_class_labels, validate_document)

            xml_links = crm_example_links(args.xml)
            report = validate_document(r.ontology, xml_links)
            report["class_labels"] = validate_class_labels(
                r.ontology, crm_example_class_uses(args.xml))
            # Opt-in and computed from the same links already read above --
            # never from a fresh parse, and never touching `report["counts"]`
            # or `report["class_labels"]`, which is what the exit-code
            # expression below reads. See document_completeness's docstring
            # for why a missing `necessary` property is guidance and not a
            # failure: the CRM calls its quantifiers "semantic clarification
            # only" (crm732#s0037) and asks that every property be
            # implemented as optional.
            if args.completeness:
                from lib.ontology import document_completeness

                report["completeness"] = document_completeness(
                    r.ontology, xml_links)
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                print(format_document_validation(report))
            raise SystemExit(0 if not (report["counts"].get("unknown_name", 0)
                                       or report["counts"].get("illegal", 0)
                                       or report["counts"].get("unknown_class", 0)
                                       or report["counts"].get("malformed", 0)
                                       # unlike ambiguity, this one is
                                       # actionable: the assertion is false
                                       # and dropping it is a real fix
                                       or report["counts"].get("attached_to_property", 0)
                                       or any(f["verdict"] != "label_mismatch"
                                              for f in report["class_labels"]))
                             else 1)

        if args.rdf:
            from lib.ontology import (crm_inverse_claims, crm_rdf_class_uses,
                                      crm_rdf_links, validate_document)

            # RDF addresses everything by URI, so three of the XML format's
            # defects cannot occur here at all: a property label cannot be
            # ambiguous (the URI names one property), a property-of-property
            # is its own explicit triple rather than smuggled in by nesting
            # (no `attached_to_property`), and a class arrives as an
            # `rdf:type` rather than prose after a colon (no `malformed`
            # class label to parse). Conversely `not_crm` is RDF-only: the
            # XML reader only ever emits element names the format itself
            # defines, so there is no equivalent of an rdfs:label predicate
            # to name and pass over. The two exit-code rules are kept
            # separate, and deliberately so, rather than unified into one
            # that happens to cover both today.
            # Claims computed first and handed to the reader as `aliases`:
            # this is what lets a document's own `bridge` claim (Task 6) --
            # already checked true by crm_inverse_claims, never an unchecked
            # one -- get its predicate read as the CRM property it names,
            # so `validate --rdf` honours bridges with no flag of its own.
            claims = crm_inverse_claims(args.rdf, r.ontology)
            rdf_links = crm_rdf_links(args.rdf, r.ontology, aliases=claims)
            report = validate_document(r.ontology, rdf_links)
            # RDF has no prose class labels -- a class arrives as an
            # rdf:type URI. But blanking the key on that reasoning left
            # NOTHING checking the rdf:type: crm_rdf_links keeps the types
            # that resolve and drops the rest, so a subject whose only type
            # was misspelled looked untyped, its links landed `unchecked`,
            # and the document exited 0 having reported nothing about the
            # one error an LLM is likeliest to make. Same slot, same
            # renderer, class URIs instead of class labels.
            report["class_labels"] = crm_rdf_class_uses(args.rdf, r.ontology)
            # validate_document always fills this with the four XML
            # example-format element names (CRM_Entity/in_class/unit/value),
            # because it has no way to know which reader produced the links
            # it was handed. RDF has no structural elements to skip at all,
            # so -- exactly as with class_labels above -- this branch blanks
            # the key rather than letting a fact about the XML format leak
            # into an RDF report.
            report["structural_elements_skipped"] = []
            report["inverse_claims"] = claims
            # Same opt-in guidance as the --xml branch, from the same
            # `rdf_links` already read above -- see document_completeness's
            # docstring (crm732#s0037) for why this never touches
            # `report["counts"]` and cannot affect the exit code below.
            if args.completeness:
                from lib.ontology import document_completeness

                report["completeness"] = document_completeness(
                    r.ontology, rdf_links)
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                print(format_document_validation(report))
            # `not_crm` and `unchecked` do not fail: a document may carry
            # vocabulary the CRM says nothing about, and an untyped subject is
            # unexamined rather than wrong. A false owl:inverseOf claim DOES
            # fail: `contradicted` and `not_invertible` are both a document
            # asserting something the CRM does not say, the same standing as
            # an illegal link -- and Task 6 needs this checked before it can
            # honour `bridge` claims for predicate aliasing without letting a
            # document define its way out of any other error.
            claims = report["inverse_claims"]
            wrong = [c for c in claims
                     if c["verdict"] in ("contradicted", "not_invertible")]
            # `not_a_class_link` fails here and not under --xml, and the
            # difference is the point. It means a property-of-property was
            # used as if it joined two classes. The house XML format has no
            # way to write one, so reporting it there names a limitation of
            # the format that the author cannot fix. RDF can write one --
            # it is an ordinary triple -- so in RDF the same finding is a
            # plain modelling error with a fix available, and a check that
            # exits 0 on it is not checking. It was omitted from this rule
            # only because the verdict predates the rule.
            # Class findings are not in `counts` -- that counts link verdicts,
            # and an rdf:type is not a link. Counted separately rather than
            # folded in, so the two halves of a triple stay distinguishable
            # in the report. `not_crm` is excluded on the same reasoning it
            # is for predicates: a foreign type is not ours to reject.
            bad_types = [f for f in report["class_labels"]
                         if f["verdict"] in ("unknown_class", "not_a_class")]
            raise SystemExit(1 if (report["counts"].get("illegal", 0)
                                   or report["counts"].get("unknown_name", 0)
                                   or report["counts"].get("unknown_class", 0)
                                   or report["counts"].get("not_a_class_link", 0)
                                   or bad_types
                                   or wrong)
                             else 0)

        if args.file:
            raw = json.loads(Path(args.file).read_text(encoding="utf-8"))
            triples = [t if isinstance(t, (list, tuple))
                       else (t.get("subject"), t.get("property"), t.get("object"))
                       for t in raw]
        elif args.target and args.phrase:
            triples = [(args.target, args.phrase, args.obj)]
        else:
            raise SystemExit(
                'validate needs either "<subject> <property> <object>" '
                "or --file <triples.json>")

        results = [validate_link(r.ontology, *(list(t) + [None])[:3]) for t in triples]
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            print("\n\n".join(format_validation(x) for x in results))
            bad = [x for x in results if not x["legal"]]
            if len(results) > 1:
                print(f"\n{len(results) - len(bad)}/{len(results)} links legal.")
        raise SystemExit(1 if any(not x["legal"] for x in results) else 0)

    if args.query == "connect" and args.target and args.phrase:
        from lib.ontology import connecting_properties

        subject, obj = args.target.upper(), args.phrase.upper()
        for ident in (subject, obj):
            if r.get_concept(ident) is None:
                raise SystemExit(f"No such concept: {ident}")
        forward = connecting_properties(r.ontology, subject, obj)
        backward = connecting_properties(r.ontology, obj, subject)
        # The CRM's own expansion of a shortcut, where it declares one.
        # get_declaration returns None for a concept with no 7.3.2
        # declaration, which is not an error -- E38 is deprecated and 7.3.2
        # dropped it entirely.
        full_paths = {}
        for row in forward + backward:
            declaration = r.get_declaration(row["id"])
            if declaration and declaration.get("full_path"):
                full_paths[row["id"]] = declaration["full_path"]
        if args.json:
            print(json.dumps({"subject": subject, "object": obj,
                              "forward": forward, "backward": backward,
                              "full_paths": full_paths},
                             ensure_ascii=False, indent=2))
        else:
            print(format_connect(subject, obj, forward, backward,
                                 full_paths=full_paths))
        return

    if args.query == "thread" and args.target:
        records = r.get_thread(args.target)
        print(json.dumps(records, ensure_ascii=False, indent=2) if args.json
              else format_thread(records))
        return

    if args.query == "threads" and args.target:
        episodes = r.search_episodes(args.target, top_k=args.k)
        print(json.dumps(episodes, ensure_ascii=False, indent=2) if args.json
              else format_episodes(episodes))
        return

    if args.query == "docs" and args.target:
        # kind=None defaults to the reference model in search_documents
        # itself, so the CLI adds no default of its own.
        docs = r.search_documents(args.target, top_k=args.k, mode=args.mode, kind=args.kind)
        print(json.dumps(docs, ensure_ascii=False, indent=2) if args.json
              else format_documents(docs))
        return

    if args.query == "issues" and args.target:
        docs = r.search_documents(args.target, top_k=args.k, mode=args.mode, kind="issue")
        print(json.dumps(docs, ensure_ascii=False, indent=2) if args.json
              else format_documents(docs))
        return

    if args.query == "issue" and args.target:
        issue = r.get_issue(args.target)
        if issue is None:
            raise SystemExit(
                f"No SIG issue {args.target} is known here. The register holds "
                f"715 issues; {len(r.issues):,} have archive discussion or "
                "recorded page content (outcome/background/proposals) in this build."
            )
        print(json.dumps(issue, ensure_ascii=False, indent=2) if args.json
              else format_issue(issue))
        return

    if args.query == "quote" and args.target and args.phrase:
        result = r.find_quote(args.target, args.phrase)
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json
              else format_quote_result(result))
        return

    # Subcommand words shadow legitimate queries, and in an archive ABOUT an
    # ontology someone will certainly search for "ontology". `search.py search
    # "<text>"` forces query interpretation for any word that collides.
    if args.query == "search" and args.target:
        args.query = args.target
        args.target = None

    if args.query == "ontology" and not args.target:
        from lib.ontology import full_listing

        listing = full_listing(r.ontology)
        if args.model:
            wanted = args.model.lower()
            listing = [s for s in listing if s["source"].lower() == wanted]
            if not listing:
                models = sorted({s["source"] for s in full_listing(r.ontology)})
                raise SystemExit(
                    f"No model named {args.model!r}. Known: {', '.join(models)}")
        if args.json:
            print(json.dumps(listing, ensure_ascii=False, indent=2))
        else:
            print(format_ontology(listing, onto=r.ontology))
        return

    if args.query == "concept" and args.target:
        from lib.ontology import applicable_properties

        entry = r.get_concept(args.target)
        if entry is None:
            hint = ""
            if "." in args.target:
                hint = ("\n(This looks like a property of a property. If "
                        "data/ontology.json predates the propertyOfProperty "
                        "parser, rebuild it: uv run python build.py ontology)")
            raise SystemExit(f"No such concept: {args.target}{hint}")
        chrono = concept_chronology(r.episodes, entry["id"])
        if entry.get("bucket") == "extensions":
            # Messages are never tagged with entities_extension (only
            # episodes are) so there is nothing to recount here; the
            # mention count ontology.json already carries IS the count.
            mentions = entry.get("mentions", 0)
        elif entry.get("bucket") == "property_of_property":
            # Never counted: format_concept explains why on screen.
            mentions = 0
        else:
            mentions = sum(
                1 for rec in r.messages.values()
                if entry["id"] in rec.get("entities", []) + rec.get("entities_historical", [])
            )
        siblings = r.concept_siblings(entry["id"])
        declaration = r.get_declaration(entry["id"])
        narratives = r.concept_narratives(entry["id"])
        if args.json:
            applicable = (applicable_properties(r.ontology, entry["id"])
                          if _is_class_like(entry) else None)
            print(json.dumps(
                {"concept": entry, "chronology": chrono, "mentions": mentions,
                 "applicable": applicable,
                 "required": [p for p in (applicable or {}).get("outgoing", [])
                              if p["required"]],
                 "siblings": siblings,
                 "declaration": declaration, "narratives": narratives},
                ensure_ascii=False, indent=2))
        else:
            print(format_concept(entry, chrono, mentions, r.ontology,
                                  siblings, declaration, narratives))
        return

    hits = r.search(
        args.query, top_k=args.k, mode=args.mode, expand=not args.no_expand,
        from_email=args.from_email, after=args.after, before=args.before,
        entity=args.entity,
    )
    print(json.dumps(hits, ensure_ascii=False, indent=2) if args.json
          else format_hits(hits))


if __name__ == "__main__":
    main()
