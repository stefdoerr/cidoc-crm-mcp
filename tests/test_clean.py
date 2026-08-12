import email
import json
import mailbox

import pytest

import lib.clean as clean_mod
from lib.clean import clean_message, extract_entities, normalize_subject, run_clean
from lib.config import PROJECT_ROOT, load_config
from lib.ontology import parse_ontology

PATTERN = r"\b([EP]\d{1,3})(?:\.\d)?\b"


@pytest.fixture(scope="module")
def onto():
    return parse_ontology(PROJECT_ROOT / "sources" / "cidoc_crm_v7.1.3.xml")


@pytest.fixture(scope="module")
def cfg():
    return load_config("crm-sig")


def test_extract_entities_splits_current_from_historical(onto):
    current, historical = extract_entities("E55 and E84 and P140", PATTERN, onto)
    assert current == ["E55", "P140"]
    assert historical == ["E84"]  # deprecated, recorded not dropped


def test_extract_entities_normalizes_dotted_property(onto):
    current, _ = extract_entities("see P14.1 in the model", PATTERN, onto)
    assert "P14" in current


def test_extract_entities_dedupes_and_sorts(onto):
    current, _ = extract_entities("E55 E55 E22 E55", PATTERN, onto)
    assert current == ["E22", "E55"]


def test_normalize_subject():
    assert normalize_subject("[crm-sig] Re: New issue") == "new issue"
    assert normalize_subject("Re: Re: Fwd: Topic") == "topic"
    assert normalize_subject("Topic (was: Other)") == "topic"
    assert normalize_subject(None) == ""


def test_clean_message_full_record(cfg, onto):
    raw = (
        "Message-ID: <abc@example.org>\n"
        "Date: Tue, 19 Jun 2001 16:50:03 +0300\n"
        "From: Martin Doerr <martin@ics.forth.gr>\n"
        "To: crm-sig@ics.forth.gr\n"
        "Subject: [crm-sig] Re: scope note of E55\n"
        "In-Reply-To: <prev@example.org>\n"
        "Content-Type: text/plain; charset=utf-8\n"
        "\n"
        "I think E55 should permit E84 instances.\n"
        "\n"
        "-- \n"
        "Martin Doerr\n"
    )
    rec = clean_message(email.message_from_string(raw), 0, cfg, onto)

    assert rec["message_id"] == "<abc@example.org>"
    assert rec["mbox_index"] == 0
    assert len(rec["id"]) == 16
    assert rec["from_name"] == "Martin Doerr"
    assert rec["from_email"] == "martin@ics.forth.gr"
    assert rec["to"] == ["crm-sig@ics.forth.gr"]
    assert rec["subject"] == "[crm-sig] Re: scope note of E55"
    assert rec["subject_norm"] == "scope note of e55"
    assert rec["in_reply_to"] == "<prev@example.org>"
    assert rec["date"].startswith("2001-06-19T16:50:03")

    assert "E55 should permit" in rec["body"]
    assert "Martin Doerr" not in rec["body"]          # signature stripped
    assert "Martin Doerr" in rec["body_raw"]          # raw retained for audit
    assert rec["stripped"]["signature"] == 1
    assert rec["entities"] == ["E55"]
    assert rec["entities_historical"] == ["E84"]
    assert rec["n_chars"] == len(rec["body"])


def test_clean_message_decodes_rfc2047_subject(cfg, onto):
    raw = (
        "Message-ID: <x@y>\n"
        "From: a@b.org\n"
        "Subject: =?windows-1251?q?frbroo_r10=27s_superproperty?=\n"
        "\n"
        "body\n"
    )
    rec = clean_message(email.message_from_string(raw), 0, cfg, onto)
    assert rec["subject"] == "frbroo r10's superproperty"
    assert "=?" not in rec["subject_norm"]


def test_clean_message_tags_quoted_entities_separately(cfg, onto):
    raw = (
        "Message-ID: <q@y>\nFrom: a@b.org\nSubject: t\n\n"
        "> E22 is the issue\n"
        "I disagree.\n"
        "> and E41 too\n"
        "So does P2.\n"
    )
    rec = clean_message(email.message_from_string(raw), 0, cfg, onto)
    # Interleaved: quotes retained, but attributed to entities_quoted
    assert "P2" in rec["entities"]
    assert "E22" in rec["entities_quoted"]


def test_record_is_json_serializable(cfg, onto):
    raw = "Message-ID: <j@y>\nFrom: a@b.org\nSubject: t\n\nbody\n"
    rec = clean_message(email.message_from_string(raw), 0, cfg, onto)
    json.loads(json.dumps(rec, ensure_ascii=False))


def test_cleaned_body_is_subsequence_of_raw(cfg, onto):
    raw = (
        "Message-ID: <s@y>\nFrom: a@b.org\nSubject: t\n\n"
        "Kept line.\n-- \nsig line\n"
    )
    rec = clean_message(email.message_from_string(raw), 0, cfg, onto)
    for line in rec["body"].splitlines():
        if line.strip():
            assert line.strip() in rec["body_raw"]


def _build_mbox(path, raw_messages: list[str]):
    box = mailbox.mbox(str(path))
    for raw in raw_messages:
        box.add(email.message_from_string(raw))
    box.flush()
    box.close()


def test_run_clean_dedupes_identical_message_id(tmp_path, monkeypatch, cfg, onto):
    # Two byte-identical messages under the same Message-ID -- a mailing-list
    # delivery-loop duplicate, not two distinct messages that happen to agree.
    raw = "Message-ID: <dup@example.org>\nFrom: a@b.org\nSubject: t\n\nsame body\n"
    mbox_path = tmp_path / "dup.mbox"
    _build_mbox(mbox_path, [raw, raw])

    monkeypatch.setattr(clean_mod, "DATA_DIR", tmp_path)
    stats = run_clean({**cfg, "mbox": str(mbox_path)}, onto)

    assert stats["messages"] == 1
    assert stats["duplicates_skipped"] == 1
    records = [json.loads(ln) for ln in open(tmp_path / "clean.jsonl", encoding="utf-8")]
    assert len(records) == 1


def test_run_clean_keeps_same_body_different_message_id(tmp_path, monkeypatch, cfg, onto):
    # Same body, different Message-IDs ("+1" replies): both are real, distinct
    # messages -- dedup must key on message_id, not on body content.
    raws = [
        "Message-ID: <one@example.org>\nFrom: a@b.org\nSubject: t\n\n+1\n",
        "Message-ID: <two@example.org>\nFrom: a@b.org\nSubject: t\n\n+1\n",
    ]
    mbox_path = tmp_path / "same_body.mbox"
    _build_mbox(mbox_path, raws)

    monkeypatch.setattr(clean_mod, "DATA_DIR", tmp_path)
    stats = run_clean({**cfg, "mbox": str(mbox_path)}, onto)

    assert stats["messages"] == 2
    assert stats["duplicates_skipped"] == 0
    records = [json.loads(ln) for ln in open(tmp_path / "clean.jsonl", encoding="utf-8")]
    assert len(records) == 2


def test_clean_message_entities_from_subject_only(cfg, onto):
    # A subject naming an issue's id, with the body carrying no identifiers
    # of its own (e.g. the discussion sits in a quote that got stripped).
    raw = (
        "Message-ID: <subj@y>\nFrom: a@b.org\n"
        "Subject: Re: [crm-sig] NEW ISSUE Ordinal Property for E55 Type\n\n"
        "I don't have anything to add here.\n"
    )
    rec = clean_message(email.message_from_string(raw), 0, cfg, onto)
    assert rec["entities"] == ["E55"]
    assert rec["entities_quoted"] == []
    assert rec["entities_historical"] == []


def test_clean_message_historical_entity_from_subject_only(cfg, onto):
    # A historical (deprecated) id named only in the subject still belongs
    # in entities_historical, exactly as it would from the body.
    raw = (
        "Message-ID: <hist@y>\nFrom: a@b.org\n"
        "Subject: Retiring E84 Information Carrier\n\n"
        "No identifiers in the body at all.\n"
    )
    rec = clean_message(email.message_from_string(raw), 0, cfg, onto)
    assert rec["entities_historical"] == ["E84"]
    assert "E84" not in rec["entities"]


def test_clean_message_merges_subject_and_body_entities_without_duplication(cfg, onto):
    raw = (
        "Message-ID: <merge@y>\nFrom: a@b.org\n"
        "Subject: Re: scope note of E55\n\n"
        "E55 should permit P140 as well.\n"
    )
    rec = clean_message(email.message_from_string(raw), 0, cfg, onto)
    assert rec["entities"] == ["E55", "P140"]
