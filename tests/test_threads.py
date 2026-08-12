# tests/test_threads.py
from lib.threads import build_threads


def rec(mid, date, subject_norm="topic", in_reply_to=None, refs=None, body="", body_raw=None):
    return {
        "id": mid, "message_id": f"<{mid}>", "date": date,
        "subject": subject_norm, "subject_norm": subject_norm,
        "in_reply_to": f"<{in_reply_to}>" if in_reply_to else None,
        "references": [f"<{r}>" for r in (refs or [])],
        "body": body, "body_raw": body_raw if body_raw is not None else body,
        "quote_spans": [],
    }


def test_references_graph_groups_a_thread():
    threads = build_threads([
        rec("a", "2010-01-01T10:00:00"),
        rec("b", "2010-01-01T11:00:00", in_reply_to="a"),
        rec("c", "2010-01-01T12:00:00", refs=["a", "b"]),
    ])
    assert len(threads) == 1
    tid = next(iter(threads))
    assert threads[tid]["message_ids"] == ["a", "b", "c"]
    assert threads[tid]["root"] == "a"


def test_singletons_each_get_their_own_thread():
    threads = build_threads([
        rec("a", "2010-01-01T10:00:00", subject_norm="alpha"),
        rec("b", "2015-06-06T10:00:00", subject_norm="beta"),
    ])
    assert len(threads) == 2


def test_subject_fallback_links_within_the_time_window():
    threads = build_threads([
        rec("a", "2010-01-01T10:00:00", subject_norm="same topic"),
        rec("b", "2010-01-20T10:00:00", subject_norm="same topic"),
    ])
    assert len(threads) == 1


def test_subject_fallback_refuses_outside_the_time_window():
    # Without this guard, subject-only matching glues several unrelated
    # conversations into one bogus 33-message "issue" thread.
    threads = build_threads([
        rec("a", "2010-01-01T10:00:00", subject_norm="issue"),
        rec("b", "2012-01-01T10:00:00", subject_norm="issue"),
    ])
    assert len(threads) == 2


def test_quote_overlap_links_messages_lacking_in_reply_to():
    # body_raw uses ">" quote markers, the real convention -- "| " markers
    # only ever appear in the cleaned `body` field, which signal 2 no longer
    # reads (see test_quote_overlap_reads_body_raw_when_body_has_no_marker).
    original = "The scope note of E55 must be revised because the current wording " \
               "conflicts with the definition given for E28 Conceptual Object here."
    quoted_raw = "> " + original + "\n> I disagree with that."
    threads = build_threads([
        rec("a", "2003-01-01T10:00:00", subject_norm="alpha", body=original, body_raw=original),
        rec("b", "2003-01-02T10:00:00", subject_norm="beta",
            body="I disagree with that.", body_raw=quoted_raw),
    ], min_overlap_chars=50)
    assert len(threads) == 1


def test_quote_overlap_ignores_short_incidental_matches():
    threads = build_threads([
        rec("a", "2003-01-01T10:00:00", subject_norm="alpha", body="Thanks.", body_raw="Thanks."),
        rec("b", "2003-01-02T10:00:00", subject_norm="beta", body="ok",
            body_raw="> Thanks.\nok"),
    ], min_overlap_chars=200)
    assert len(threads) == 2


def test_quote_overlap_never_links_backwards_in_time():
    # Gap kept inside the 30-day guard so this test isolates directionality,
    # not the distance guard covered separately below.
    text = "x" * 300
    threads = build_threads([
        rec("later", "2003-01-15T10:00:00", subject_norm="a", body="reply",
            body_raw="> " + text),
        rec("earlier", "2003-01-01T10:00:00", subject_norm="b", body=text, body_raw=text),
    ], min_overlap_chars=50)
    tid = next(iter(threads))
    assert threads[tid]["message_ids"][0] == "earlier"


def test_quote_overlap_refuses_outside_the_time_window():
    # Signal 2 has the same failure mode as signal 3, from a different
    # direction: two messages can quote the same external document (e.g. an
    # official CIDOC-CRM scope note) without ever being a reply to each
    # other. Measured on the real corpus: gaps among genuine quote-overlap
    # links cluster inside a month, then nothing at all until one outlier
    # 3.6 years out -- so this guard uses the same 30-day window as signal 3.
    text = "x" * 300
    threads = build_threads([
        rec("earlier", "2003-01-01T10:00:00", subject_norm="a", body=text, body_raw=text),
        rec("later", "2004-02-05T10:00:00", subject_norm="b", body_raw="> " + text),
    ], min_overlap_chars=50)
    assert len(threads) == 2


def test_quote_overlap_links_within_the_time_window():
    # The inverse of the guard test above -- proves the guard narrows signal
    # 2 rather than disabling it outright.
    text = "x" * 300
    threads = build_threads([
        rec("earlier", "2003-01-01T10:00:00", subject_norm="a", body=text, body_raw=text),
        rec("later", "2003-01-11T10:00:00", subject_norm="b", body_raw="> " + text),
    ], min_overlap_chars=50)
    assert len(threads) == 1


def test_quote_overlap_reads_body_raw_when_body_has_no_marker():
    # This is the case the pre-fix code could not see: lib.quotes strips a
    # substantial single-block top-posted quote out of `body` entirely, with
    # no "| " marker left behind -- that's the de-duplication the pipeline
    # exists for. body_raw still has the quote verbatim, as a ">"-quoted
    # block. Signal 2 must read body_raw, not body, to recover this link.
    original = "The scope note of E55 must be revised because the current wording " \
               "conflicts with the definition given for E28 Conceptual Object here."
    quoted_raw = "\n".join("> " + line for line in original.splitlines())
    threads = build_threads([
        rec("a", "2003-01-01T10:00:00", subject_norm="alpha", body=original, body_raw=original),
        rec("b", "2003-01-02T10:00:00", subject_norm="beta",
            body="I disagree with that.",  # cleaned body: quote fully stripped, no marker
            body_raw=quoted_raw + "\nI disagree with that."),
    ], min_overlap_chars=50)
    assert len(threads) == 1


def test_thread_ids_are_stable_and_sorted_by_first_message():
    threads = build_threads([
        rec("late", "2020-01-01T10:00:00", subject_norm="z"),
        rec("early", "2001-01-01T10:00:00", subject_norm="a"),
    ])
    assert threads["t0000"]["message_ids"] == ["early"]
    assert threads["t0001"]["message_ids"] == ["late"]


def test_subjects_are_collected_per_thread():
    threads = build_threads([
        rec("a", "2010-01-01T10:00:00", subject_norm="4 new issues"),
        rec("b", "2010-01-02T10:00:00", subject_norm="4 new issues, collection class",
            in_reply_to="a"),
    ])
    tid = next(iter(threads))
    assert len(threads[tid]["subjects"]) == 2
