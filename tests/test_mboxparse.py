import email

from lib.mboxparse import (
    decode_header_value,
    decode_payload,
    extract_attachments,
    extract_body,
    html_to_text,
    parse_addresses,
    split_from,
)


def test_decode_declared_charsets():
    assert decode_payload("Grüße".encode("iso-8859-1"), "iso-8859-1") == "Grüße"
    assert decode_payload("Καλημέρα".encode("iso-8859-7"), "iso-8859-7") == "Καλημέρα"
    assert decode_payload("naïve".encode("windows-1252"), "windows-1252") == "naïve"
    assert decode_payload("héllo".encode("utf-8"), "utf-8") == "héllo"


def test_undeclared_charset_falls_back():
    # 3,816 parts in this corpus declare nothing
    assert decode_payload("plain ascii".encode("ascii"), None) == "plain ascii"
    assert decode_payload("héllo".encode("utf-8"), None) == "héllo"
    assert "�" not in decode_payload("naïve".encode("cp1252"), None)


def test_unknown_charset_does_not_raise():
    assert decode_payload(b"hello", "x-not-a-charset") == "hello"


def test_undecodable_bytes_are_replaced_not_raised():
    assert decode_payload(b"\xff\xfe\xfd bad", "utf-8")


def test_rfc2047_subject_decoding():
    raw = "=?windows-1251?q?frbroo_r10=27s_superproperty?="
    assert decode_header_value(raw) == "frbroo r10's superproperty"
    assert decode_header_value("=?utf-8?B?SGVsbG8gV29ybGQ=?=") == "Hello World"
    assert decode_header_value("plain subject") == "plain subject"
    assert decode_header_value(None) == ""


def test_malformed_encoded_word_does_not_raise():
    # Malformed base64 in encoded-word returns the raw header unchanged
    assert decode_header_value("=?utf-8?B?A?=") == "=?utf-8?B?A?="


def test_malformed_encoded_word_in_parse_addresses():
    # parse_addresses recovers the address even with undecodable display-name
    assert parse_addresses("=?utf-8?B?A?= <a@b.org>") == ["a@b.org"]


def test_malformed_encoded_word_in_split_from():
    # split_from recovers the address even with undecodable display-name
    name, addr = split_from("=?utf-8?B?A?= <a@b.org>")
    assert addr == "a@b.org"


def test_html_to_text():
    out = html_to_text("<html><body><p>Hello</p><p>World</p></body></html>")
    assert "Hello" in out and "World" in out
    assert "<" not in out


def test_html_to_text_drops_script_and_style():
    out = html_to_text("<style>p{color:red}</style><script>x=1</script><p>Keep</p>")
    assert "Keep" in out
    assert "color:red" not in out and "x=1" not in out


def test_extract_body_prefers_plain_over_html():
    msg = email.message_from_string(
        "MIME-Version: 1.0\n"
        'Content-Type: multipart/alternative; boundary="B"\n\n'
        "--B\nContent-Type: text/plain\n\nPLAIN VERSION\n"
        "--B\nContent-Type: text/html\n\n<p>HTML VERSION</p>\n"
        "--B--\n"
    )
    text, source = extract_body(msg)
    assert source == "plain"
    assert "PLAIN VERSION" in text


def test_extract_body_falls_back_to_html():
    msg = email.message_from_string(
        "MIME-Version: 1.0\nContent-Type: text/html\n\n<p>ONLY HTML</p>\n"
    )
    text, source = extract_body(msg)
    assert source == "html"
    assert "ONLY HTML" in text


def test_extract_attachments_metadata_only():
    msg = email.message_from_string(
        "MIME-Version: 1.0\n"
        'Content-Type: multipart/mixed; boundary="B"\n\n'
        "--B\nContent-Type: text/plain\n\nbody\n"
        "--B\nContent-Type: application/msword\n"
        'Content-Disposition: attachment; filename="issue.doc"\n\n'
        "PAYLOAD\n"
        "--B--\n"
    )
    atts = extract_attachments(msg)
    assert len(atts) == 1
    assert atts[0]["filename"] == "issue.doc"
    assert atts[0]["content_type"] == "application/msword"
    assert atts[0]["size"] > 0


def test_attachment_parts_are_not_used_as_body():
    msg = email.message_from_string(
        "MIME-Version: 1.0\n"
        'Content-Type: multipart/mixed; boundary="B"\n\n'
        "--B\nContent-Type: text/plain\n"
        'Content-Disposition: attachment; filename="notes.txt"\n\n'
        "ATTACHED TEXT\n"
        "--B--\n"
    )
    text, source = extract_body(msg)
    assert source == "none"
    assert "ATTACHED TEXT" not in text


def test_parse_addresses_and_split_from():
    assert parse_addresses("a@x.org, B <b@y.org>") == ["a@x.org", "b@y.org"]
    assert parse_addresses(None) == []
    assert split_from("Martin Doerr <martin@ics.forth.gr>") == (
        "Martin Doerr",
        "martin@ics.forth.gr",
    )
    assert split_from("bare@example.org") == ("", "bare@example.org")
