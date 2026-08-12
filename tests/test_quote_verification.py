"""Quote verification: does a phrase actually occur in a source, and where.

The blind modelling-advice evaluation resolved 297 citations mechanically with
zero invented identifiers, and two were still wrong: a thread cited for a line
no participant in it wrote (t1022, misattributed to Christian-Emil, who never
posts there), and a phrase attributed to a thread that never uses that wording
(t0056, "replacing a part of an object"). A reviewer with full archive access
confirmed one of them anyway. Existence was checked; containment was not.

Most tests here build a Retriever with fabricated threads/messages/episodes/
documents -- set directly into the instance's __dict__, which pre-empts the
`cached_property` file read the same way accessing the property normally
would cache it, so these never touch data/ and never write to it either. The
"known failures" class at the bottom is the one place real corpus data is
read (find_quote needs no vector store, so this is as cheap as a `concept`
lookup, not a smoke-test-tier cost).
"""

import pytest

from lib.config import PROJECT_ROOT
from lib.retrieve import Retriever


def _fake_retriever(threads=None, by_hash=None, episodes=None, documents=None) -> Retriever:
    r = Retriever()
    r.__dict__["threads"] = threads or {}
    r.__dict__["by_hash"] = by_hash or {}
    r.__dict__["messages"] = {rec["message_id"]: rec for rec in (by_hash or {}).values()}
    r.__dict__["episodes"] = episodes or []
    r.__dict__["documents"] = documents or {}
    return r


@pytest.fixture
def retriever():
    threads = {"t9001": {"message_ids": ["h1", "h2", "h3"], "root": "h1", "subjects": []}}
    by_hash = {
        "h1": {
            "message_id": "<m1@x>", "from_name": "Alice", "date": "2020-01-01",
            "body": "Hello all, just an opening message about the agenda.",
        },
        "h2": {
            "message_id": "<m2@x>", "from_name": "Bob", "date": "2020-01-02",
            "body": (
                "Bob replies: the committee decided the property "
                "shouldn't be split across two records, since that "
                "would break provenance."
            ),
        },
        "h3": {
            "message_id": "<m3@x>", "from_name": "Carol", "date": "2020-01-03",
            "body": (
                "Carol's closing note: hard\nwrapped   text\n  with  "
                " irregular whitespace   should still\nmatch cleanly."
            ),
        },
    }
    episodes = [{
        "episode_id": "t9001-e1", "thread_id": "t9001", "message_ids": ["h2"],
        "topic": "property split", "outcome": "decided",
    }]
    documents = {
        "doc1#c1": {
            "chunk_id": "doc1#c1", "heading": "Some Section",
            "section_path": ["Some Section"], "cite": "Test Doc",
            "text": "The scope note says no property exists for this purpose in this model.",
        },
    }
    return _fake_retriever(threads, by_hash, episodes, documents)


# ---- found -----------------------------------------------------------------


def test_found_in_thread_reports_message_index_and_author(retriever):
    result = retriever.find_quote("t9001", "the committee decided the property")
    assert result["found"] is True
    assert result["source_kind"] == "thread"
    assert result["message_index"] == 2  # h2, 1-based
    assert result["author"] == "Bob"
    assert result["message_id"] == "<m2@x>"
    assert "the committee decided the property" in result["context"].lower()


def test_found_in_message_by_hash_id(retriever):
    result = retriever.find_quote("h1", "just an opening message")
    assert result["found"] is True
    assert result["source_kind"] == "message"
    assert result["author"] == "Alice"


def test_found_in_message_by_message_id_header(retriever):
    result = retriever.find_quote("<m1@x>", "just an opening message")
    assert result["found"] is True
    assert result["message_id"] == "<m1@x>"


def test_found_in_episode_reports_thread_relative_index(retriever):
    # The episode's own message_ids only carries h2, but the index reported
    # must be h2's position in the FULL thread (2 of 3) -- what
    # `search.py thread t9001` actually shows -- not a 1-of-1 index local to
    # the episode's own subset.
    result = retriever.find_quote("t9001-e1", "shouldn't be split")
    assert result["found"] is True
    assert result["source_kind"] == "episode"
    assert result["message_index"] == 2
    assert result["author"] == "Bob"
    assert result["thread_id"] == "t9001"


def test_found_in_document_chunk_reports_section_path(retriever):
    result = retriever.find_quote("doc1#c1", "no property exists for this purpose")
    assert result["found"] is True
    assert result["source_kind"] == "document"
    assert result["section_path"] == ["Some Section"]
    assert result["cite"] == "Test Doc"


def test_match_preserves_original_casing_in_context(retriever):
    result = retriever.find_quote("t9001", "committee decided")
    assert result["found"] is True
    assert "committee decided" in result["context"]  # not e.g. all-caps or all-lower


# ---- not found ---------------------------------------------------------


def test_not_found_reports_closest_with_message_index_and_score(retriever):
    result = retriever.find_quote("t9001", "no property for transferring a right")
    assert result["found"] is False
    assert result["closest"] is not None
    assert 0.0 <= result["closest"]["score"] <= 1.0
    assert result["closest"]["message_index"] in (1, 2, 3)
    assert result["closest"]["author"] in ("Alice", "Bob", "Carol")


def test_not_found_does_not_fuzzy_match_a_paraphrase(retriever):
    """The phrase means roughly the same thing as Bob's message but is not
    the wording he used -- this must fail, or the check stops meaning
    anything (a paraphrase would pass a judge too)."""
    result = retriever.find_quote(
        "t9001", "the group agreed the record should not be divided in two"
    )
    assert result["found"] is False


def test_not_found_in_a_single_message(retriever):
    result = retriever.find_quote("h1", "something never said here")
    assert result["found"] is False
    assert result["source_kind"] == "message"


def test_not_found_in_a_document_chunk(retriever):
    result = retriever.find_quote("doc1#c1", "a phrase this chunk does not contain")
    assert result["found"] is False
    assert result["source_kind"] == "document"


# ---- normalisation: typographic quotes and hard-wrapped lines -------------


def test_normalizes_typographic_apostrophe(retriever):
    # Source (h2) has a straight apostrophe; the phrase as given here uses a
    # curly one, exactly as a quote copied out of rendered prose would.
    result = retriever.find_quote("t9001", "shouldn’t be split across two records")
    assert result["found"] is True


def test_normalizes_curly_double_quotes(retriever):
    r = _fake_retriever(by_hash={
        "h9": {"message_id": "<m9@x>", "from_name": "Dana", "date": "2021-01-01",
               "body": 'Dana wrote: the term "passive activity" was rejected.'},
    })
    result = r.find_quote("h9", "the term “passive activity” was rejected")
    assert result["found"] is True


def test_normalizes_hard_wrapped_lines_and_irregular_whitespace(retriever):
    result = retriever.find_quote(
        "t9001", "hard wrapped text with irregular whitespace should still match cleanly"
    )
    assert result["found"] is True
    assert result["author"] == "Carol"


def test_case_insensitive(retriever):
    result = retriever.find_quote("t9001", "THE COMMITTEE DECIDED THE PROPERTY")
    assert result["found"] is True


# ---- unknown source id ------------------------------------------------


def test_unknown_source_id_reports_error_not_a_crash(retriever):
    result = retriever.find_quote("t9999", "anything")
    assert result["found"] is False
    assert result["source_kind"] is None
    assert "t9999" in result["error"]


def test_unknown_source_id_that_looks_like_no_id_at_all(retriever):
    result = retriever.find_quote("not-a-real-id-shape", "anything")
    assert result["found"] is False
    assert result["source_kind"] is None


def test_empty_phrase_raises(retriever):
    with pytest.raises(ValueError):
        retriever.find_quote("t9001", "")


# ---- the two known failures, against the real archive ---------------------
#
# find_quote reads data/threads.json, clean.jsonl, episodes.jsonl and
# documents.jsonl -- the same local files `concept` already reads -- and
# never touches Chroma, so unlike tests/test_smoke_retrieval.py's gate this
# needs no built vector store. These are regression tests for the exact
# failures the tool exists to catch, not synthetic examples.


@pytest.fixture(scope="module")
def real_retriever():
    return Retriever()


class TestKnownFailures:
    def test_t1022_never_says_no_property_for_transferring_a_right(self, real_retriever):
        """t1022 ('Passive Activities' -- Sanderson, Beretta, Bruseker) was
        cited for this line under Christian-Emil's name. He never posts in
        this thread, and the thread never says this either."""
        result = real_retriever.find_quote(
            "t1022", "no property for transferring a right"
        )
        assert result["found"] is False
        if result["closest"]:
            assert result["closest"]["author"] in (
                "Robert Sanderson", "Francesco Beretta", "George Bruseker",
            )

    def test_t0056_never_says_replacing_a_part_of_an_object(self, real_retriever):
        """t0056 (Doerr's 2002 Part Addition/Removal proposal) is topically
        right but contains no form of the word 'replace'."""
        result = real_retriever.find_quote(
            "t0056", "replacing a part of an object"
        )
        assert result["found"] is False

    def test_a_genuine_phrase_is_found_with_correct_index_and_author(self, real_retriever):
        """Independently verified with `tools/read_thread.py t1022`: message
        [1] (0-based there, 2 here -- both mean the second message) is
        Francesco Beretta."""
        result = real_retriever.find_quote("t1022", "personal property is abolished")
        assert result["found"] is True
        assert result["message_index"] == 2
        assert result["author"] == "Francesco Beretta"


class TestSpaceBeforePunctuation:
    """A stray space before a full stop is a typo in the source, not a
    difference in wording, and it is pervasive here: 21% of messages and 38%
    of document chunks contain one. Anyone quoting such a sentence writes it
    correctly, so without this normalisation an accurate citation is reported
    as fabricated -- which is what happened to two verbatim sentences from
    t0872 whose source reads "instances of this class ." mid-sentence.
    """

    def test_quote_matches_across_a_space_before_a_full_stop(self, real_retriever):
        result = real_retriever.find_quote(
            "t0872",
            "E31 Document is a subclass of E73 Information Object as shown "
            "below. There is an aspect of intentionality connected to "
            "instances of this class.",
        )
        assert result["found"] is True

    def test_the_source_really_does_have_the_stray_space(self, real_retriever):
        """Guards the guard: if the corpus is ever recleaned and the space
        disappears, the test above stops testing anything and should be
        retired rather than left passing for the wrong reason."""
        msg = real_retriever.get_message("f085ce7f92b303df")
        assert "instances of this class ." in msg["body"]

    def test_normalisation_still_rejects_a_paraphrase(self, real_retriever):
        """The loosening must not reach past whitespace: same claim, different
        words, must still fail."""
        result = real_retriever.find_quote(
            "t0872",
            "E31 Document is a subtype of E73 Information Object as displayed below",
        )
        assert result["found"] is False

    def test_normalisation_does_not_relocate_a_quote(self, real_retriever):
        """Real wording, wrong source, must still fail -- the other half of
        what the check is for."""
        phrase = "E31 seems to be an epistemic rather than an ontological category"
        assert real_retriever.find_quote("t1842", phrase)["found"] is False
        assert real_retriever.find_quote(
            "issue707#background-s0000", phrase)["found"] is True


class TestElidedQuotations:
    """"A ... B" is ordinary quoting, and the house style asks answers to
    quote sparingly, so the careful answer is the one most likely to elide.
    Without elision support an accurate citation of the Monterey 2002 minutes
    -- both halves verbatim -- was reported as fabricated.
    """

    ELIDED = ("Report of the 3rd joined meeting of the CIDOC Special Interest "
              "Group and ISO/TC46/SC4/WG9 ... Venue: Asilomar Conference "
              "Centre, Monterey Peninsula, CA, USA")
    CHUNK = "minutes:3rd_crm_meeting_minutes#s000"

    @pytest.mark.skipif(
        not (PROJECT_ROOT / "data" / "minutes").exists(),
        reason="data/minutes/ not fetched")
    def test_elided_quote_is_found(self, real_retriever):
        assert real_retriever.find_quote(self.CHUNK, self.ELIDED)["found"] is True

    @pytest.mark.skipif(
        not (PROJECT_ROOT / "data" / "minutes").exists(),
        reason="data/minutes/ not fetched")
    def test_elision_must_not_reorder_the_source(self, real_retriever):
        """The load-bearing restriction. "A ... B" must not match a text where
        B precedes A: that quotation would misrepresent what was said, and an
        any-order check would bless it."""
        reversed_quote = ("Venue: Asilomar Conference Centre, Monterey "
                          "Peninsula, CA, USA ... Report of the 3rd joined "
                          "meeting of the CIDOC Special Interest Group")
        assert real_retriever.find_quote(self.CHUNK, reversed_quote)["found"] is False

    @pytest.mark.skipif(
        not (PROJECT_ROOT / "data" / "minutes").exists(),
        reason="data/minutes/ not fetched")
    def test_one_real_half_does_not_carry_an_invented_half(self, real_retriever):
        half_invented = ("Report of the 3rd joined meeting of the CIDOC "
                         "Special Interest Group ... the committee voted "
                         "unanimously to abolish the class")
        assert real_retriever.find_quote(self.CHUNK, half_invented)["found"] is False

    def test_short_fragments_are_not_treated_as_an_elision(self):
        """"E31 ... E73" is two identifiers, not a quotation; letting it match
        would make almost any phrase verifiable against almost any source."""
        from lib.retrieve import _find_in_text
        text = "E31 Document is a subclass of E73 Information Object as shown below."
        assert _find_in_text(text, "E31 ... E73") is None
