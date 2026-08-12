from lib.quotes import apply_quote_rules, count_quote_blocks, is_attribution, is_quoted


def test_is_quoted():
    assert is_quoted("> quoted")
    assert is_quoted("  >> deep")
    assert is_quoted("| pipe quoted")
    assert not is_quoted("plain text")


def test_is_quoted_rejects_signature_box_drawing():
    # Pipe is used for signature box-drawing; reject when no content after or multiple pipes.
    # Only reject if: multiple pipes on line OR no content after pipe.
    assert is_quoted("| pipe quoted")  # genuine pipe quote with content
    assert is_quoted("|quoted")  # pipe with content (no space, still a quote)
    assert not is_quoted("| ")  # bare pipe with nothing after
    assert not is_quoted("|  Name  |  Val  |")  # multi-pipe table row (has second pipe)
    assert not is_quoted("                    |")  # lone border pipe (no content after)


def test_count_quote_blocks_ignores_blank_lines_between_quotes():
    assert count_quote_blocks(["plain", "more plain"]) == 0
    assert count_quote_blocks(["> a", "> b", "plain"]) == 1
    assert count_quote_blocks(["plain", "> a", "", "> b", "plain"]) == 1
    assert count_quote_blocks(["> a", "reply", "> b", "reply2"]) == 2
    assert count_quote_blocks(["> a", "r1", "> b", "r2", "> c", "r3"]) == 3


def test_is_attribution_multilingual():
    assert is_attribution("On Tue, Martin wrote:")
    assert is_attribution("El 3 de marzo, Juan escribió:")
    assert is_attribution("Il giorno 3 marzo, Marco ha scritto:")
    assert is_attribution("Le 3 mars, Pierre a écrit :")
    assert is_attribution("Am 03.03.2010 schrieb Hans:")
    assert is_attribution("Op 3 maart schreef Jan:")
    assert is_attribution("Martin writes:")
    assert not is_attribution("This is ordinary prose about writing.")


def test_rule6_strips_top_posted_quote():
    # Content must be >= 200 chars to avoid thin-reply guard
    long_reply = "My reply here with substantial content. " * 6  # ~240 chars
    lines = [long_reply, "", "On Tue, X wrote:", "> original", "> more original"]
    kept, spans, counts = apply_quote_rules(lines)
    assert counts["single_block_quote"] == 1
    assert counts["attribution"] == 1
    assert kept == [long_reply]
    assert spans == []


def test_rule6_strips_bottom_posted_quote():
    # The case the position-based rule silently missed (bottom-posting).
    # Content must be >= 200 chars to avoid thin-reply guard.
    long_reply = "My reply here with substantial content. " * 6  # ~240 chars
    lines = ["> original text", "> more original", "", long_reply]
    kept, spans, counts = apply_quote_rules(lines)
    assert counts["single_block_quote"] == 1
    assert kept == [long_reply]


def test_rule8_retains_interleaved_quotes_marked():
    lines = ["> point one", "I disagree.", "> point two", "That conflicts with P4."]
    kept, spans, counts = apply_quote_rules(lines)
    assert counts["interleaved_kept"] == 1
    assert counts["single_block_quote"] == 0
    body = "\n".join(kept)
    assert "I disagree." in body
    assert "That conflicts with P4." in body
    assert "| point one" in body      # retained, marked
    assert "| point two" in body
    assert spans, "retained quote spans must be recorded"


def test_no_quotes_message_untouched():
    lines = ["Dear all,", "", "The meeting is Thursday."]
    kept, spans, counts = apply_quote_rules(lines)
    assert kept == lines
    assert spans == []
    assert sum(counts.values()) == 0


def test_thin_reply_guard_retains_context():
    lines = ["> The scope note of E55 should be revised to permit E28.", "I agree."]
    kept, spans, counts = apply_quote_rules(lines, thin_reply_chars=200)
    body = "\n".join(kept)
    assert "I agree." in body
    assert "E55" in body, "a bare 'I agree' is unretrievable without its quote"
    assert counts["thin_reply_context"] == 1
    assert spans


def test_thin_reply_guard_caps_retained_context():
    quote = [f"> line {i}" for i in range(50)]
    kept, _, counts = apply_quote_rules(quote + ["ok"], thin_reply_chars=200, context_lines=15)
    assert counts["thin_reply_context"] == 1
    assert sum(1 for ln in kept if ln.startswith("| ")) == 15


def test_thin_reply_guard_does_not_fire_on_substantial_reply():
    lines = ["> short quote", "x" * 400]
    _, _, counts = apply_quote_rules(lines, thin_reply_chars=200)
    assert counts["thin_reply_context"] == 0


def test_signature_box_drawing_not_counted_as_quotes():
    # Signature box-drawing uses pipe characters but is not quotation.
    # A message that looks like it has 3 quote blocks (all box-drawing pipes)
    # should count as 0 blocks.
    lines = [
        "Some content here.",
        "|                    |",  # box border, not a quote
        "|    Signature Box    |",  # box content, not a quote
        "|                    |",  # box border, not a quote
    ]
    assert count_quote_blocks(lines) == 0
