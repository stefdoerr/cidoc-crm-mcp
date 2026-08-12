"""MIME part selection, charset decoding, and RFC 2047 header decoding.

The corpus spans 26 years and every mail client of the era: 3,816 parts declare
no charset at all, eight distinct charsets appear, and subjects arrive as raw
encoded-words.
"""

from email.header import decode_header, make_header
from email.utils import getaddresses
from html.parser import HTMLParser

_FALLBACKS = ("utf-8", "cp1252", "latin-1")
_SKIP_TAGS = {"script", "style", "head"}


def decode_payload(raw: bytes, charset: str | None) -> str:
    """Decode bytes using the declared charset, then a fallback chain."""
    if charset:
        try:
            return raw.decode(charset)
        except (LookupError, UnicodeDecodeError):
            pass
    for enc in _FALLBACKS[:-1]:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    # latin-1 maps every byte, so this never raises.
    return raw.decode("latin-1", "replace")


def decode_header_value(value: str | None) -> str:
    """Decode RFC 2047 encoded-words into plain text."""
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except Exception:
        # Catch all exceptions: the contract is to return a string always.
        # decode_header and make_header can raise UnicodeDecodeError, LookupError,
        # ValueError, HeaderParseError, or other stdlib exceptions on any
        # 1999-era malformed input. Enumerating them is fragile; broad is robust.
        return value.strip()


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip += 1
        elif tag in ("p", "br", "div", "tr", "li"):
            self.parts.append("\n")
        elif tag in ("td", "th"):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    lines = ["".join(parser.parts).replace("\r", "")]
    return "\n".join(ln.strip() for ln in lines[0].splitlines()).strip()


def _part_text(part) -> str | None:
    try:
        raw = part.get_payload(decode=True)
    except Exception:
        return None
    if not raw:
        return None
    try:
        charset = part.get_content_charset()
    except Exception:
        charset = None
    return decode_payload(raw, charset)


def extract_body(msg) -> tuple[str, str]:
    """Return (text, source) preferring text/plain, falling back to text/html.

    Parts carrying a filename are attachments and are never used as the body.
    """
    parts = list(msg.walk()) if msg.is_multipart() else [msg]
    html_text = None
    for part in parts:
        try:
            if part.get_filename():
                continue
            ctype = part.get_content_type()
        except Exception:
            continue
        if ctype == "text/plain":
            text = _part_text(part)
            if text is not None:
                return text, "plain"
        elif ctype == "text/html" and html_text is None:
            raw = _part_text(part)
            if raw is not None:
                html_text = html_to_text(raw)
    if html_text:
        return html_text, "html"
    return "", "none"


def extract_attachments(msg) -> list[dict]:
    parts = list(msg.walk()) if msg.is_multipart() else [msg]
    out = []
    for part in parts:
        try:
            filename = part.get_filename()
            if not filename:
                continue
            content_type = part.get_content_type()
        except Exception:
            continue
        try:
            payload = part.get_payload(decode=True) or b""
        except Exception:
            payload = b""
        out.append(
            {
                "filename": decode_header_value(filename),
                "content_type": content_type,
                "size": len(payload),
            }
        )
    return out


def parse_addresses(value: str | None) -> list[str]:
    if not value:
        return []
    return [addr.lower() for _, addr in getaddresses([decode_header_value(value)]) if addr]


def split_from(value: str | None) -> tuple[str, str]:
    if not value:
        return "", ""
    pairs = getaddresses([decode_header_value(value)])
    if not pairs:
        return "", ""
    name, addr = pairs[0]
    return name.strip().strip('"'), addr.lower()
