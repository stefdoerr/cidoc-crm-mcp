from lib.index import episode_chunks
from search import format_episodes

EP = {
    "episode_id": "t0042-e1", "thread_id": "t0042",
    "message_ids": ["a", "b"],
    "topic": "Whether E55 Type should permit E28 Conceptual Object",
    "question": "Does E55 admit conceptual objects?",
    "positions": [{"who": "Martin Doerr", "position": "No, use P2."}],
    "outcome": "decided", "outcome_detail": "Rejected in favour of P2.",
    "entities": ["E55", "E28"], "entities_historical": [], "confidence": "high",
}


def test_episode_chunks_carry_routing_metadata():
    chunks = episode_chunks([EP])
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk["episode_id"] == "t0042-e1"
    assert chunk["thread_id"] == "t0042"
    assert chunk["outcome"] == "decided"
    assert chunk["entities"] == "E55 E28"
    assert "E55 Type" in chunk["text"]
    assert "Rejected in favour" in chunk["text"]


def test_episode_chunks_skips_empty_episodes():
    assert episode_chunks([{"episode_id": "x", "thread_id": "t", "topic": "",
                            "question": "", "positions": [], "outcome": "",
                            "outcome_detail": "", "entities": []}]) == []


def test_format_episodes_makes_the_pointer_obvious():
    out = format_episodes([EP])
    assert "t0042" in out
    assert "decided" in out
    assert "E55 Type" in out
    # Summaries route; they must direct the reader to the real messages.
    assert "thread t0042" in out


def test_format_episodes_empty():
    assert "No results" in format_episodes([])


SPANNING = dict(
    EP,
    episode_id="t0900-e1", thread_id="t0900",
    date_start="2011-03-02T09:14:00", date_end="2011-04-18T17:02:00",
    entities=["E55"], entities_extension=["F3", "SP6"],
)


def test_format_episodes_shows_the_date_span():
    # 26 years of archive: when a debate happened is part of routing to it.
    out = format_episodes([SPANNING])
    assert "2011-03-02" in out
    assert "2011-04-18" in out


def test_format_episodes_collapses_a_single_day_span():
    out = format_episodes([dict(SPANNING, date_end="2011-03-02T23:00:00")])
    assert "2011-03-02.." not in out
    assert "2011-03-02" in out


def test_format_episodes_shows_extension_entities():
    # These are indexed, so they must be visible; otherwise an episode about
    # FRBRoo F3 renders with no entities at all.
    out = format_episodes([SPANNING])
    assert "F3" in out and "SP6" in out


def test_episode_chunks_index_extension_entities():
    chunk = episode_chunks([SPANNING])[0]
    assert "F3" in chunk["entities"] and "SP6" in chunk["entities"]
    assert "E55" in chunk["entities"]
