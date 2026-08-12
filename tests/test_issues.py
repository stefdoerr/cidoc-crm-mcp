"""Tests for lib/issues.py (linking the archive to the CIDOC CRM SIG issue register).

Two tiers, mirroring tests/test_ontology.py:
  * unit tests exercise the regex sieve and the grouping/ordering logic
    against small synthetic records, so the false-positive guards (digest
    banner, glued URL-slug digits, ordinal suffixes) can be pinned down
    precisely;
  * a couple of tests read the real, committed crm_issues.json (reference
    data, not a build artifact -- see tools/fetch_crm_issues.py) the same
    way test_ontology.py reads the real crm_family.json.

Deliberately never reads data/clean.jsonl or data/threads.json: those are
gitignored build artifacts that another pipeline stage can regenerate at any
time, and the constraint is that tests must not depend on -- or write to --
real project data.
"""

from lib.config import PROJECT_ROOT
from lib.issues import (
    build_issue_index,
    candidate_issue_numbers,
    issue_lookup,
    load_registry,
    mentions_by_message,
    validate_issue_ids,
)

REGISTER = PROJECT_ROOT / "sources" / "crm_issues.json"


def rec(mid, date, subject="", body="", thread_ids=None):
    return {"id": mid, "date": date, "subject": subject, "body": body}


# ---------------------------------------------------------------------------
# The real, committed register
# ---------------------------------------------------------------------------


def test_load_registry_reads_all_715_known_ids():
    registry = load_registry(REGISTER)
    assert len(registry) == 715
    assert all(isinstance(k, int) for k in registry)


def test_load_registry_issue_332_is_a_real_done_issue():
    # Anchors the fixture to a fact checked by hand against
    # https://cidoc-crm.org/Issue/ID-332-... : this is the issue the SIG
    # opened in 2017 and closed in 2022, spanning 10 threads in this archive.
    registry = load_registry(REGISTER)
    assert registry[332]["status"] == "Done"
    assert "S10" in registry[332]["title"]


# ---------------------------------------------------------------------------
# candidate_issue_numbers -- the regex sieve (guard #1)
# ---------------------------------------------------------------------------


def test_matches_common_citation_forms():
    assert candidate_issue_numbers("Issue 56,63,64") == {56}
    assert candidate_issue_numbers("[Crm-sig] Issue 332") == {332}
    assert candidate_issue_numbers("Re: [Crm-sig] Issue:530 Bias in the CRM") == {530}
    assert candidate_issue_numbers("issue: 56") == {56}
    assert candidate_issue_numbers("Issue #56") == {56}
    assert candidate_issue_numbers("ISSUE 240: Start/End vs Period") == {240}


def test_rejects_digits_glued_directly_onto_the_word():
    # The archive quotes firstmonday.org/issues/issue9_5/gill -- a URL slug,
    # not a citation. Without a mandatory separator this reads as "issue" + 9.
    assert candidate_issue_numbers("firstmonday.org/issues/issue9_5/gill") == set()


def test_rejects_mailman_digest_banner():
    # "Crm-sig Digest, Vol 58, Issue 6" numbers the mailing-list DIGEST, not a
    # SIG issue -- and 6 is coincidentally also a real issue id, so registry
    # validation alone cannot tell them apart. Measured on the real corpus:
    # 38 such banners, numbering 3-64, all real ids by coincidence.
    text = "Re: [Crm-sig] Crm-sig Digest, Vol 58, Issue 6 Hello all"
    assert candidate_issue_numbers(text) == set()


def test_digest_banner_does_not_swallow_a_real_citation_on_the_same_message():
    text = "Crm-sig Digest, Vol 58, Issue 6\n\nAs discussed in Issue 475, the scope note..."
    assert candidate_issue_numbers(text) == {475}


def test_rejects_ordinal_suffix():
    assert candidate_issue_numbers("described in issue 21st century terms") == set()
    assert candidate_issue_numbers("issue 43, 3rd draft") == {43}


def test_finds_multiple_distinct_citations_in_one_message():
    text = "Issue 475 relates to Issue 460 and to issue 332 as well."
    assert candidate_issue_numbers(text) == {475, 460, 332}


# ---------------------------------------------------------------------------
# validate_issue_ids -- registry membership (guard #2)
# ---------------------------------------------------------------------------


def test_validate_drops_numbers_the_register_never_assigned():
    registry = {1: {}, 56: {}, 332: {}}
    assert validate_issue_ids({1, 56, 332, 9999}, registry) == {1, 56, 332}


def test_validate_against_the_real_register_rejects_a_known_gap():
    # 201 is one of the 7 ids the SIG never assigned (ids run 1-722 but only
    # 715 exist) -- a number a looser implementation might accept on shape
    # alone.
    registry = load_registry(REGISTER)
    assert 201 not in registry
    assert validate_issue_ids({201, 332}, registry) == {332}


# ---------------------------------------------------------------------------
# mentions_by_message
# ---------------------------------------------------------------------------


def test_mentions_by_message_reads_subject_and_body():
    registry = {56: {}, 332: {}}
    records = [
        rec("m1", "2020-01-01", subject="[crm-sig] Issue 56", body="no number here"),
        rec("m2", "2020-01-02", subject="unrelated", body="see issue 332 for details"),
        rec("m3", "2020-01-03", subject="unrelated", body="no citation at all"),
    ]
    result = mentions_by_message(records, registry)
    assert result == {"m1": {56}, "m2": {332}}
    assert "m3" not in result


def test_mentions_by_message_drops_unregistered_numbers():
    registry = {56: {}}
    records = [rec("m1", "2020-01-01", body="issue 999 is not a real issue")]
    assert mentions_by_message(records, registry) == {}


# ---------------------------------------------------------------------------
# build_issue_index
# ---------------------------------------------------------------------------


def _threads(mapping):
    """{thread_id: [message_ids]} -> the shape build_issue_index expects."""
    return {tid: {"message_ids": mids} for tid, mids in mapping.items()}


def test_groups_mentions_of_the_same_issue_across_threads():
    registry = {332: {"title": "S10 properties", "status": "Done"}}
    records = [
        rec("a", "2017-03-01", body="Issue 332: opening the debate"),
        rec("b", "2021-06-01", body="Issue 332: e-vote passes"),
    ]
    threads = _threads({"t1": ["a"], "t2": ["b"]})
    issues = build_issue_index(records, threads, registry)
    assert issues["332"]["thread_count"] == 2
    assert {t["thread_id"] for t in issues["332"]["threads"]} == {"t1", "t2"}


def test_threads_are_ordered_by_first_mention_date():
    registry = {332: {}}
    records = [
        rec("a", "2021-06-01", body="issue 332 later"),
        rec("b", "2017-03-01", body="issue 332 earlier"),
    ]
    threads = _threads({"t_late": ["a"], "t_early": ["b"]})
    issues = build_issue_index(records, threads, registry)
    ordered = [t["thread_id"] for t in issues["332"]["threads"]]
    assert ordered == ["t_early", "t_late"]


def test_overall_first_and_last_mention_span_every_thread():
    registry = {332: {}}
    records = [
        rec("a", "2017-03-01", body="issue 332"),
        rec("b", "2019-01-01", body="issue 332"),
        rec("c", "2022-11-22", body="issue 332"),
    ]
    threads = _threads({"t1": ["a"], "t2": ["b"], "t3": ["c"]})
    issues = build_issue_index(records, threads, registry)
    assert issues["332"]["first_mention"] == "2017-03-01"
    assert issues["332"]["last_mention"] == "2022-11-22"


def test_only_discussed_issues_are_recorded():
    # The register has 715 ids; build_issue_index is a filter over what the
    # archive actually discusses, not a copy of the register (mirrors
    # lib.ontology.add_extensions).
    registry = {332: {}, 1: {}, 2: {}}
    records = [rec("a", "2020-01-01", body="issue 332")]
    threads = _threads({"t1": ["a"]})
    issues = build_issue_index(records, threads, registry)
    assert list(issues) == ["332"]


def test_carries_register_metadata_onto_the_issue_entry():
    registry = {
        460: {
            "title": "URI Management",
            "status": "Open",
            "url": "https://cidoc-crm.org/Issue/ID-460-uri-management",
            "working_group": "3",
            "closing_date": None,
            "family_model": ["CIDOC CRM"],
        }
    }
    records = [rec("a", "2020-01-01", body="Issue 460 needs a decision")]
    threads = _threads({"t1": ["a"]})
    issues = build_issue_index(records, threads, registry)
    entry = issues["460"]
    assert entry["title"] == "URI Management"
    assert entry["status"] == "Open"
    assert entry["family_model"] == ["CIDOC CRM"]


def test_messages_absent_from_every_thread_are_skipped_not_fatal():
    # A message can be mentions_by_message()-eligible but missing from the
    # thread index (e.g. a deduplicated Message-ID). Must not KeyError.
    registry = {332: {}}
    records = [rec("orphan", "2020-01-01", body="issue 332")]
    threads = _threads({"t1": ["someone-else"]})
    issues = build_issue_index(records, threads, registry)
    assert issues == {}


# ---------------------------------------------------------------------------
# issue_lookup -- the wiring seam for a future CLI verb
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# build_issue_index with `pages` -- outcome/references from lib.issue_pages,
# and issues that have page content but no archive mentions at all.
# ---------------------------------------------------------------------------


def test_pages_argument_adds_outcome_and_references_to_a_discussed_issue():
    registry = {332: {"title": "S10 properties", "status": "Done"}}
    records = [rec("a", "2020-01-01", body="issue 332 discussion")]
    threads = _threads({"t1": ["a"]})
    pages = {332: {"outcome": "The SIG decided X.",
                   "references": [{"id": 449, "title": "How to write examples"}]}}
    issues = build_issue_index(records, threads, registry, pages)
    assert issues["332"]["outcome"] == "The SIG decided X."
    assert issues["332"]["references"] == [{"id": 449, "title": "How to write examples"}]
    assert issues["332"]["thread_count"] == 1  # archive discussion is untouched


def test_issue_with_page_content_but_no_archive_mention_still_appears():
    """issue 193 (P109 subp of P49) is never cited by number anywhere in
    this archive -- validated by hand against data/clean.jsonl -- but its
    own page has an outcome, and that is worth surfacing on its own."""
    registry = {193: {"title": "P109 subp of P49", "status": "Done"}}
    records = [rec("a", "2020-01-01", body="no citation of the issue number here")]
    threads = _threads({"t1": ["a"]})
    pages = {193: {"outcome": "The CRM-SIG decided that P109 is subproperty of P49."}}
    issues = build_issue_index(records, threads, registry, pages)
    assert issues["193"]["outcome"] == "The CRM-SIG decided that P109 is subproperty of P49."
    assert issues["193"]["thread_count"] == 0
    assert issues["193"]["threads"] == []


def test_issue_with_neither_mention_nor_page_content_is_absent():
    registry = {193: {"title": "x", "status": "Done"}}
    records = [rec("a", "2020-01-01", body="nothing relevant")]
    threads = _threads({"t1": ["a"]})
    issues = build_issue_index(records, threads, registry, pages={193: {}})
    assert "193" not in issues


def test_pages_argument_defaults_to_none_and_reproduces_old_behaviour():
    registry = {332: {"title": "x", "status": "Done"}}
    records = [rec("a", "2020-01-01", body="issue 332")]
    threads = _threads({"t1": ["a"]})
    without_pages = build_issue_index(records, threads, registry)
    with_empty_pages = build_issue_index(records, threads, registry, pages=None)
    assert without_pages["332"]["outcome"] is None
    assert without_pages["332"]["references"] == []
    assert without_pages == with_empty_pages


def test_outcome_is_none_for_an_open_issue_with_no_pages_data():
    """Must not imply a resolution when there isn't one."""
    registry = {482: {"title": "x", "status": "Open"}}
    records = [rec("a", "2020-01-01", body="issue 482")]
    threads = _threads({"t1": ["a"]})
    issues = build_issue_index(records, threads, registry, pages={482: {"outcome": None}})
    assert issues["482"]["outcome"] is None


def test_issue_lookup_returns_the_built_entry():
    data = {"332": {"id": 332, "status": "Done", "threads": []}}
    assert issue_lookup(data, 332) == data["332"]
    assert issue_lookup(data, "332") == data["332"]


def test_issue_lookup_returns_none_for_an_unknown_id():
    assert issue_lookup({"332": {}}, 999) is None


# --- the CLI surface -------------------------------------------------------

def test_format_issue_leads_with_the_register_status():
    """The status is the thing the archive alone cannot tell you: a debate
    settled years later in another thread reads locally as one that trails
    off. It goes first, and is labelled as the register's, not a summary."""
    from search import format_issue

    out = format_issue({
        "id": 332, "title": "Properties of S10", "status": "Done",
        "closing_date": "2019-06-13", "family_model": ["CRMsci"],
        "url": "https://cidoc-crm.org/Issue/ID-332-x",
        "thread_count": 2, "first_mention": "2017-09-20T12:00:00+03:00",
        "last_mention": "2022-11-22T14:00:00+02:00",
        "threads": [
            {"thread_id": "t1028", "first_mention": "2017-09-20T12:00:00+03:00",
             "last_mention": "2017-09-20T21:00:00+03:00", "mentions": 8},
            {"thread_id": "t1661", "first_mention": "2022-11-22T14:00:00+02:00",
             "last_mention": "2022-11-22T14:00:00+02:00", "mentions": 1},
        ],
    })
    assert "Done" in out
    assert out.index("Status:") < out.index("t1028"), "status must precede the threads"
    assert "2017-09-20" in out and "2022-11-22" in out, "the span is the point"
    assert "t1028" in out and "t1661" in out
    assert "search.py thread t1028" in out, "must route to the messages"
    assert "not a summary of the debate" in out


def test_format_issue_survives_a_bare_entry():
    from search import format_issue

    out = format_issue({"id": 7, "title": "x", "status": "Open", "threads": []})
    assert "Issue 7" in out and "Open" in out


def test_format_issue_shows_outcome_when_present():
    from search import format_issue

    out = format_issue({
        "id": 193, "title": "P109 subp of P49", "status": "Done", "threads": [],
        "outcome": "The CRM-SIG decided that P109 is subproperty of P49.",
    })
    assert "The CRM-SIG decided that P109 is subproperty of P49." in out
    assert out.index("Status:") < out.index("CRM-SIG decided")


def test_format_issue_omits_outcome_section_when_absent():
    """Deliverable's explicit requirement: an Open issue must not imply a
    resolution just because the rendering code has an Outcome section."""
    from search import format_issue

    out = format_issue({"id": 482, "title": "x", "status": "Open", "threads": [],
                         "outcome": None})
    assert "Outcome" not in out


def test_format_issue_lists_references_with_a_way_to_follow_each():
    from search import format_issue

    out = format_issue({
        "id": 332, "title": "x", "status": "Done", "threads": [],
        "references": [{"id": 449, "title": "How to write examples"}],
    })
    assert "449" in out and "How to write examples" in out
    assert "search.py issue 449" in out


def test_format_issue_omits_references_section_when_none():
    from search import format_issue

    out = format_issue({"id": 7, "title": "x", "status": "Open", "threads": []})
    assert "References" not in out


def test_format_issue_says_nothing_rather_than_a_span_of_question_marks():
    """403 of 715 issues have a page but are never cited by number on the
    list. Rendering their (absent) date span produced
    "?????????? .. ??????????"; absence of discussion is a real fact about
    the archive and should be stated."""
    from search import format_issue

    out = format_issue({"id": 193, "title": "P109 subp of P49", "status": "Done",
                        "outcome": "The CRM-SIG decided ...", "thread_count": 0,
                        "threads": []})
    assert "?????" not in out
    assert "No mailing-list thread cites this issue" in out
    assert "The CRM-SIG decided" in out


class TestMeetingOrdering:
    """Meetings attached to an issue are claimed to be oldest first. Sorting
    the raw strings satisfies nothing: "15/1/2018" precedes "9/10/2017"
    lexicographically, which put the 40th SIG meeting ahead of the 39th on
    issue 295."""

    def test_numeric_dates_are_day_first_and_chronological(self):
        from lib.issues import meeting_sort_key
        assert meeting_sort_key("9/10/2017") < meeting_sort_key("15/1/2018")

    def test_mixed_formats_sort_together(self):
        from lib.issues import meeting_sort_key
        dates = ["27 - 30 November, 2018", "9-10th December 2004",
                 "15/9/2008", "1997", "9/10/2017"]
        assert sorted(dates, key=meeting_sort_key) == [
            "1997", "9-10th December 2004", "15/9/2008",
            "9/10/2017", "27 - 30 November, 2018"]

    def test_undated_meetings_go_last_not_first(self):
        from lib.issues import meeting_sort_key
        assert meeting_sort_key(None) > meeting_sort_key("27 - 30 November, 2018")
        assert meeting_sort_key("no date here") > meeting_sort_key("1997")
