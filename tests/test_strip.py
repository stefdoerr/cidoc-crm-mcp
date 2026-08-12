from lib.strip import quote_depth, strip_boilerplate, unquote_line

FOOTER = "Crm-sig mailing list"


def test_unquote_line_and_depth():
    assert unquote_line("> > hello") == "hello"
    assert unquote_line(">>hello") == "hello"
    assert unquote_line("hello") == "hello"
    assert quote_depth("> > hello") == 2
    assert quote_depth("hello") == 0


def test_rule1_removes_mailman_footer():
    lines = [
        "Real content.",
        "_______________________________________________",
        FOOTER,
        "Crm-sig@mailhost.ics.forth.gr",
        "http://lists.ics.forth.gr/mailman/listinfo/crm-sig",
        "More content.",
    ]
    kept, counts = strip_boilerplate(lines, FOOTER)
    assert counts["mailman_footer"] == 1
    assert "Real content." in kept and "More content." in kept
    assert not any(FOOTER in ln for ln in kept)


def test_rule1_removes_footer_nested_inside_quotes():
    # The reason rule 1 must run at every depth: 7,109 occurrences, most quoted.
    lines = [
        "> Real quoted content.",
        "> _______________________________________________",
        f"> {FOOTER}",
        "> Crm-sig@mailhost.ics.forth.gr",
        "> http://lists.ics.forth.gr/mailman/listinfo/crm-sig",
        "My reply.",
    ]
    kept, counts = strip_boilerplate(lines, FOOTER)
    assert counts["mailman_footer"] == 1
    assert "> Real quoted content." in kept
    assert not any(FOOTER in ln for ln in kept)


def test_rule1_removes_footer_at_multiple_depths_in_one_message():
    lines = [
        "Top.",
        "_______________________________________________",
        FOOTER,
        "> Quoted.",
        "> _______________________________________________",
        f"> {FOOTER}",
    ]
    _, counts = strip_boilerplate(lines, FOOTER)
    assert counts["mailman_footer"] == 2


def test_rule2_outlook_separator_drops_to_end():
    lines = [
        "My reply.",
        "________________________________________",
        "From: Someone <s@x.org>",
        "Sent: Monday",
        "Original body here.",
    ]
    kept, counts = strip_boilerplate(lines, FOOTER)
    assert counts["outlook_separator"] == 1
    assert kept == ["My reply."]


def test_rule3_original_message_drops_to_end():
    lines = ["My reply.", "-----Original Message-----", "From: x", "old body"]
    kept, counts = strip_boilerplate(lines, FOOTER)
    assert counts["original_message"] == 1
    assert kept == ["My reply."]


def test_rule3_matches_five_dash_variant():
    lines = ["Reply.", "----- Original Message -----", "old body"]
    _, counts = strip_boilerplate(lines, FOOTER)
    assert counts["original_message"] == 1


def test_rule4_rfc3676_signature_drops_to_end():
    lines = ["Body text.", "-- ", "Martin Doerr", "FORTH-ICS"]
    kept, counts = strip_boilerplate(lines, FOOTER)
    assert counts["signature"] == 1
    assert kept == ["Body text."]


def test_rule4_does_not_fire_on_bare_double_dash():
    # "--" without the trailing space is ordinary text (e.g. an em-dash line)
    lines = ["Body text.", "--", "still body"]
    kept, counts = strip_boilerplate(lines, FOOTER)
    assert counts["signature"] == 0
    assert "still body" in kept


def test_rule5_personal_sig_block_drops_to_end():
    lines = [
        "Body text.",
        "_______________________________________________",
        "Paula Goossens",
        "Koninklijke Bibliotheek",
    ]
    kept, counts = strip_boilerplate(lines, FOOTER)
    assert counts["sig_block"] == 1
    assert kept == ["Body text."]


def test_rule1_wins_over_rule5_for_the_same_underscore_line():
    lines = [
        "Body.",
        "_______________________________________________",
        FOOTER,
        "listinfo url",
        "After footer.",
    ]
    kept, counts = strip_boilerplate(lines, FOOTER)
    assert counts["mailman_footer"] == 1
    assert counts["sig_block"] == 0
    assert "After footer." in kept


def test_no_rule_fires_on_a_clean_message():
    lines = ["Dear all,", "", "The meeting is Thursday.", "", "Regards"]
    kept, counts = strip_boilerplate(lines, FOOTER)
    assert kept == lines
    assert sum(counts.values()) == 0


# Guard tests: drop-to-end rules must not leave body empty
def test_rule3_guard_forward_only_original_message():
    # A forward that is *only* the Original Message block: guard should preserve it
    lines = ["-------- Original Message --------", "From: someone@example.com", "Subject: FYI", "Some content"]
    kept, counts = strip_boilerplate(lines, FOOTER)
    assert counts["original_message"] == 0  # guard prevented the drop
    assert kept == lines  # entire body kept


def test_rule3_normal_reply_with_original_message_still_drops():
    # A reply with real content followed by Original Message: drop should still work
    lines = ["My reply.", "Some thoughts.", "-------- Original Message --------", "From: x", "old body"]
    kept, counts = strip_boilerplate(lines, FOOTER)
    assert counts["original_message"] == 1  # drop still applied
    assert kept == ["My reply.", "Some thoughts."]


def test_rule2_guard_forward_only_outlook_separator():
    # A forward that is *only* Outlook separator and headers: guard should preserve it
    lines = ["________________________________________", "From: someone@example.com", "Subject: FYI", "body"]
    kept, counts = strip_boilerplate(lines, FOOTER)
    assert counts["outlook_separator"] == 0  # guard prevented the drop
    assert kept == lines


def test_rule2_normal_reply_with_outlook_separator_still_drops():
    # A reply with content followed by Outlook separator: drop should still work
    lines = ["My reply.", "________________________________________", "From: x", "Sent: Monday", "old body"]
    kept, counts = strip_boilerplate(lines, FOOTER)
    assert counts["outlook_separator"] == 1  # drop still applied
    assert kept == ["My reply."]


def test_rule5_guard_forward_only_sig_block():
    # A forward that is *only* underscore sig block: guard should preserve it
    lines = ["_______________________________________________", "Paula Goossens", "FORTH"]
    kept, counts = strip_boilerplate(lines, FOOTER)
    assert counts["sig_block"] == 0  # guard prevented the drop
    assert kept == lines


def test_rule5_normal_reply_with_sig_block_still_drops():
    # A reply with content followed by sig block: drop should still work
    lines = ["My reply.", "_______________________________________________", "Paula Goossens", "FORTH"]
    kept, counts = strip_boilerplate(lines, FOOTER)
    assert counts["sig_block"] == 1  # drop still applied
    assert kept == ["My reply."]


def test_signature_only_message_still_empties():
    # A message that is only a signature should still end up empty
    lines = ["-- ", "Martin Doerr", "FORTH-ICS"]
    kept, counts = strip_boilerplate(lines, FOOTER)
    assert counts["signature"] == 1  # signature rule still fires
    assert kept == []  # guard does not apply to rule 4


# Fix round 2: guard must not be fooled by preserved boilerplate
def test_double_nested_forward_innermost_content_survives():
    # Double-nested forward: marker1 + headers, then marker2 + real forwarded content.
    # Guard suppresses at marker1 (no content before it). Guard must not later be fooled
    # by the preserved marker1+headers when deciding about marker2.
    lines = [
        "-------- Original Message --------",
        "From: outer@example.com",
        "Subject: Outer",
        "-------- Original Message --------",
        "From: inner@example.com",
        "Subject: Inner",
        "This is the real forwarded content that must not be destroyed.",
    ]
    kept, counts = strip_boilerplate(lines, FOOTER)
    assert counts["original_message"] == 0  # both guards suppress, no drop
    assert "This is the real forwarded content" in "\n".join(kept)
    # The entire message survives because guards prevent both drops


def test_double_nested_with_genuine_prose_drops_at_first_marker():
    # Message with genuine prose, then two markers.
    # Guard should allow drop at first marker (prose before it).
    lines = [
        "My genuine reply with real content.",
        "-------- Original Message --------",
        "From: someone@example.com",
        "Subject: Original",
        "-------- Original Message --------",
        "From: inner@example.com",
        "More forwarded content",
    ]
    kept, counts = strip_boilerplate(lines, FOOTER)
    assert counts["original_message"] == 1  # drop happens at first marker
    assert kept == ["My genuine reply with real content."]


def test_rule1_wins_over_rule2_same_underscore_line():
    # Mailman footer (rule 1) should take priority over Outlook separator (rule 2)
    # when the same underscore line matches both patterns' initial detection.
    lines = [
        "Content before.",
        "_______________________________________________",
        FOOTER,
        "Crm-sig@mailhost.ics.forth.gr",
        "http://lists.ics.forth.gr/mailman/listinfo/crm-sig",
    ]
    kept, counts = strip_boilerplate(lines, FOOTER)
    # Rule 1 should fire (mailman footer takes priority)
    assert counts["mailman_footer"] == 1
    assert counts["outlook_separator"] == 0
    assert "Content before." in kept
    assert not any(FOOTER in ln for ln in kept)
