"""Link the archive to the official CIDOC CRM SIG issue register.

We thread by reply-chain and subject (lib/threads.py), but the SIG's unit of
decision is the numbered ISSUE, not the thread: a debate opened in one thread
in 2017 can be settled by e-vote in an unrelated-looking thread in 2021. This
module finds every place in the archive an issue number is genuinely
mentioned and groups those mentions by issue, so a question like "was issue
332 ever resolved?" can be answered from the register's own Status field
(Done / Open / Proposed / On going) plus the full, date-ordered list of
threads that discussed it -- instead of from how any single thread reads.

False positives are the central risk, and registry validation ALONE does not
remove it: issue numbers run 1-722, so almost any small integer mentioned
near the word "issue" is coincidentally a real id even when the prose is not
actually citing an issue ("harmonization issues\n23/10 CIDOC-CRM..." -- a
schedule date, not issue 23; "issue 43, 3rd draft" -- an ordinal, not a
second issue). Two independent guards handle this, mirroring how
lib/ontology.family_of validates identifier PREFIXES against a real
collection rather than trusting shape alone:

  1. The regex (ISSUE_PATTERN) requires "issue"/"issues" to be immediately
     adjacent to the number -- same line, only whitespace or a single ":"/"#"
     between them, and the number must not be followed by an ordinal suffix.
     This is what keeps the schedule-date and "3rd draft" cases out; letting
     the gap be looser (as a first attempt did) also pulled in numbers from
     unrelated CRM ids like "issue: P140" reading "140" as an issue.
  2. `validate_issue_ids` then keeps only numbers that are one of the
     register's 715 known ids (crm_issues.json) -- exactly the family_of
     pattern: a candidate is real only when a real, independently-sourced
     collection says so, not because it merely looks like one.

Measured on this corpus with every guard in place: 311 distinct issue
numbers are mentioned, 126 of them across more than one thread, spanning 454
threads in total, and issue 332 -- checked by hand against the register --
lands in exactly 10 threads.
"""

import json
import re
from pathlib import Path

# "Issue 56,63,64", "Issue 4, scope notes", "issue 69", "ISSUE 347",
# "Issue #56", "issue: 56" all match. The gap between the word and the digits
# is [ \t]* (no newline) plus at most one ":" or "#", which is what excludes
# "issues\n23/10" (a date on the next line) and "issue: P140" (a CRM id, not
# a bare number) -- both matched, and both wrong, when the gap allowed
# arbitrary characters.
#
# The trailing negative lookahead excludes ordinal readings ("issue 43,
# 3rd draft" must not yield 3): digits directly followed by st/nd/rd/th are
# not issue numbers.
#
# Multi-issue lists ("Issue 268 and 269", "issues 252,248,...") are common
# enough (~35 instances) that dropping them isn't quite free, but only the
# FIRST number in such a list is captured. Extending the pattern to also
# capture ", 63, 64" continuations was tried and rejected: it is exactly what
# turned "issue 43, 3rd draft" into a false "issue 3", because a naive
# continuation can't tell "3" the next list item from "3" the start of an
# ordinal without repeating the same lookahead per item, and the added
# surface area was not worth it for a minority pattern. Undercounting a
# 35-instance minority is a safe trade against re-opening that hole.
#  (?!\d) pins the digit run to its full length before the ordinal check
# runs. Without it, "21st" can match as "2" + "1st": \d{1,4} backtracks from
# "21" down to "2" to dodge the ordinal lookahead, and "2" is not itself
# followed by "st" -- it's followed by "1st", so the (over-eager) shorter
# match slips through. (?!\d) rejects that shorter match outright (a digit
# immediately follows "2"), which is what forces the engine to fail the
# whole "issue 21st" occurrence rather than mis-read it as issue 2.
_NUM = r"\d{1,4}(?!\d)(?!\s*(?:st|nd|rd|th)\b)"
# The word and the number must be separated by real whitespace and/or a
# single ":"/"#" -- never nothing at all. Without that, "issue9_5" (the
# archive quotes firstmonday.org/issues/issue9_5/gill, a URL slug) reads as
# "issue" + "9". Every genuine citation found in this archive -- "Issue 56",
# "Issue:530", "issue: 56", "Issue #56" -- keeps at least one such
# character; only the URL-slug accident glues the digits straight onto the
# word.
ISSUE_PATTERN = re.compile(
    rf"\bissues?(?:[ \t]+[:#]?[ \t]*|[:#][ \t]*)({_NUM})", re.I
)

# Mailman's own digest banner -- "Crm-sig Digest, Vol 58, Issue 6" -- numbers
# the DIGEST, not a SIG issue, but is otherwise indistinguishable from a real
# citation to the regex above (measured: 38 instances, numbers 3-64, every
# one a small integer that also happens to be a real SIG issue id, which is
# exactly the collision registry validation cannot catch on its own -- see
# module docstring). Stripped before the sieve runs so its "Issue N" never
# reaches ISSUE_PATTERN at all.
_DIGEST_BANNER = re.compile(r"\bdigest,?\s*vol\.?\s*\d+,?\s*issue\s*\d+", re.I)


def candidate_issue_numbers(text: str) -> set[int]:
    """Numbers that LOOK like issue references in free text.

    Deliberately just the regex sieve -- validate_issue_ids is what decides
    which of these are real, exactly as lib.ontology's family_pattern is a
    deliberately loose sieve that family_of narrows down.
    """
    text = _DIGEST_BANNER.sub(" ", text)
    return {int(m.group(1)) for m in ISSUE_PATTERN.finditer(text)}


def load_registry(path: str | Path) -> dict[int, dict]:
    """Load crm_issues.json (see tools/fetch_crm_issues.py) as {int id: entry}.

    JSON object keys are always strings; every caller in this module wants to
    index by the number it just parsed out of prose, so keys are coerced to
    int once, here, rather than at every call site.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))["entries"]
    return {int(k): v for k, v in raw.items()}


def validate_issue_ids(candidates: set[int], registry: dict[int, dict]) -> set[int]:
    """Keep only numbers that are genuine SIG issue ids -- guard #2 (see module docstring).

    A number surviving the regex is not yet trustworthy: registry membership
    is the authoritative check, the same role crm_family.json plays for
    ontology identifiers. A candidate absent from the register (its number is
    simply not one the SIG ever assigned) is silently dropped, never guessed
    at -- there are only 715 of these and no interpolation is defensible.
    """
    return {n for n in candidates if n in registry}


def mentions_by_message(
    records: list[dict], registry: dict[int, dict]
) -> dict[str, set[int]]:
    """{message id: {issue numbers it genuinely references}}, guards applied.

    Reads `subject` and `body`, not `body_raw`: the subject line is where a
    large share of real issue citations live ("[crm-sig] Issue 332 ...") and
    repeats identically across every message in a thread, which is a
    correct signal here, not noise -- every message that carries the subject
    genuinely is part of the issue's discussion. `body` (not `body_raw`) is
    used so a quoted "issue 56" from someone else's message still counts:
    unlike thread reconstruction, attributing a passing mention to the wrong
    author doesn't matter here, only whether the thread discussed the issue.
    """
    out: dict[str, set[int]] = {}
    for r in records:
        text = f"{r.get('subject') or ''}\n{r.get('body', '')}"
        valid = validate_issue_ids(candidate_issue_numbers(text), registry)
        if valid:
            out[r["id"]] = valid
    return out


def _has_page_content(page: dict) -> bool:
    """True if `page` (one entry of lib.issue_pages.parse_issue_pages'
    output) has anything worth surfacing on its own, independent of whether
    the archive ever cites the issue by number.

    This is what lets issue 193 show up in `search.py issue 193` even though
    this archive never once writes "issue 193" -- it argues about P109 and
    P49 without ever naming the issue that settled it. The SIG's own page
    still has an outcome to report, and that is worth showing regardless of
    what lib.issues' mention-detection sieve (see module docstring) found.
    """
    return bool(
        page.get("outcome")
        or page.get("background")
        or page.get("current_proposal_paragraphs")
        or page.get("old_proposal_paragraphs")
        or page.get("references")
    )


_MONTHS = {m: i for i, m in enumerate(
    ("january february march april may june july august september october "
     "november december").split(), start=1)}
_YEAR = re.compile(r"\b(19[89]\d|20[0-5]\d)\b")
_NUMERIC_DATE = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](19|20)(\d{2})\b")
_DAY = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\b")


def meeting_sort_key(date: str | None) -> tuple:
    """Best-effort (year, month, day) so meetings order chronologically.

    Sorting the strings directly is wrong and looks right: "15/1/2018" sorts
    before "9/10/2017" because "1" < "9", which put the 40th meeting ahead of
    the 39th. The minutes carry at least four date shapes and no common
    template, so this parses what it can and sends the unparseable to the end
    rather than interleaving them at an arbitrary point.

    Numeric dates read day-first: these are European meetings and the archive
    writes 9/10/2017 for the October meeting.
    """
    if not date:
        return (1, 9999, 99, 99)
    numeric = _NUMERIC_DATE.search(date)
    if numeric:
        day, month, century, rest = numeric.groups()
        return (0, int(century + rest), int(month), int(day))
    year_match = _YEAR.search(date)
    if not year_match:
        return (1, 9999, 99, 99)
    year = int(year_match.group(1))
    lowered = date.lower()
    month = next((n for name, n in _MONTHS.items() if name in lowered), 99)
    # The day is the first number that is not the year -- "27 - 30 November,
    # 2018" starts on the 27th.
    day = 99
    for candidate in _DAY.findall(date):
        if int(candidate) != year % 100 and 1 <= int(candidate) <= 31:
            day = int(candidate)
            break
    return (0, year, month, day)


def _meetings_by_issue(links: list[dict] | None) -> dict[int, list[dict]]:
    """{issue id: meetings that took it up}, oldest first where dates parse.

    `links` is lib.minutes.issue_links' output, joined here rather than in
    that module so the minutes stay a document corpus and this module stays
    the one place an issue's record is assembled.
    """
    out: dict[int, list[dict]] = {}
    for link in links or []:
        out.setdefault(int(link["issue"]), []).append({
            "doc_id": link.get("doc_id"),
            "title": link.get("title"),
            "date": link.get("date"),
            "heading": link.get("heading"),
            "chunk_id": link.get("chunk_id"),
        })
    for rows in out.values():
        rows.sort(key=lambda r: meeting_sort_key(r.get("date")))
    return out


def build_issue_index(
    records: list[dict],
    threads: dict,
    registry: dict[int, dict],
    pages: dict[int, dict] | None = None,
    minutes_links: list[dict] | None = None,
) -> dict[str, dict]:
    """{issue id (str) -> register status/title + its threads in date order}.

    An issue is recorded here if EITHER the archive actually discusses it
    (mirroring lib.ontology.add_extensions -- a filter over the corpus, not
    a copy of the register's 715 rows) OR `pages` (lib.issue_pages'
    per-issue parse of the SIG's own page, keyed by id) has content for it
    -- see `_has_page_content`. An issue with neither is absent, same as
    before `pages` existed; passing no `pages` argument reproduces the
    original archive-only behaviour exactly, which is what every test
    written before this parameter existed still relies on.

    Each thread entry carries first_mention / last_mention (the date range,
    within that thread, that the issue number was raised) so a caller can
    tell a thread that opened the issue from one that only closed it in
    passing. An issue present only via `pages` (no archive mentions at all)
    gets `threads: []`, `thread_count: 0` -- correctly, since the archive
    genuinely never cites it by number, not a bug to work around.

    `outcome` (str | None) and `references` (the SIG's own curated
    cross-reference list, `[{"id", "title"}, ...]`) come straight from
    `pages` when present. Both are the SIG's statement about the issue,
    never the archive's -- see lib.issue_pages' module docstring for why
    `outcome` in particular is the point of this task.

    This is the seam a future `issues` CLI verb wires to: `issue_lookup`
    below does the actual per-issue read: threads are already sorted here,
    once, at build time, not on every lookup.
    """
    pages = pages or {}
    meetings = _meetings_by_issue(minutes_links)
    msg_issues = mentions_by_message(records, registry)
    msg_date = {r["id"]: r.get("date") for r in records}
    msg_thread = {
        mid: tid for tid, t in threads.items() for mid in t["message_ids"]
    }

    per_issue: dict[int, dict[str, dict]] = {}
    for mid, issue_ids in msg_issues.items():
        tid = msg_thread.get(mid)
        if tid is None:      # message deduplicated out of every thread
            continue
        date = msg_date.get(mid)
        for iid in issue_ids:
            bucket = per_issue.setdefault(iid, {})
            entry = bucket.setdefault(
                tid, {"thread_id": tid, "first_mention": date,
                      "last_mention": date, "mentions": 0}
            )
            entry["mentions"] += 1
            if date and (not entry["first_mention"] or date < entry["first_mention"]):
                entry["first_mention"] = date
            if date and (not entry["last_mention"] or date > entry["last_mention"]):
                entry["last_mention"] = date

    # An issue also earns a record if a meeting minuted it, even when no
    # thread cites it and its page is empty: the minutes are then the only
    # surviving account of it being taken up at all.
    all_ids = (set(per_issue)
               | {iid for iid, p in pages.items() if _has_page_content(p)}
               | set(meetings))

    issues: dict[str, dict] = {}
    for iid in all_ids:
        reg = registry.get(iid, {})
        thread_map = per_issue.get(iid, {})
        thread_list = sorted(
            thread_map.values(), key=lambda t: t["first_mention"] or ""
        )
        mention_dates = [t["first_mention"] for t in thread_list if t["first_mention"]]
        page = pages.get(iid) or {}
        issues[str(iid)] = {
            "id": iid,
            "title": reg.get("title"),
            "status": reg.get("status"),
            "url": reg.get("url"),
            "working_group": reg.get("working_group"),
            "closing_date": reg.get("closing_date"),
            "family_model": reg.get("family_model", []),
            "outcome": page.get("outcome"),
            "references": page.get("references", []),
            "meetings": meetings.get(iid, []),
            "thread_count": len(thread_list),
            "threads": thread_list,
            "first_mention": min(mention_dates, default=None),
            "last_mention": max(mention_dates, default=None),
        }
    return issues


def issue_lookup(data: dict[str, dict], issue_id: int | str) -> dict | None:
    """One issue: its register status plus its threads in date order, or None.

    The intended wiring seam for a future `issues <id>` CLI verb -- a plain
    dict lookup, because build_issue_index already did the grouping and
    sorting once at build time rather than on every query.
    """
    return data.get(str(issue_id))
