"""Boilerplate removal (spec rules 1-5).

Rule 1 is the highest-value rule in the corpus: the Mailman footer appears
7,109 times across 5,402 messages and recurses into quoted text as threads
deepen, so it must be detected at every quote depth rather than only at depth 0.
"""

import re

_QUOTE_PREFIX = re.compile(r"^(\s*[>|]+)+\s?")
_QUOTE_MARK = re.compile(r"[>|]")
_UNDERSCORES = re.compile(r"^_{20,}\s*$")
_ORIGINAL_MSG = re.compile(r"^\s*-{2,}\s*Original Message\s*-{2,}\s*$", re.I)
_SIG_SEP = re.compile(r"^-- $")
_HEADER_LINE = re.compile(r"^\s*(From|Sent|To|Cc|Subject|Date)\s*:", re.I)

_COUNTER_KEYS = (
    "mailman_footer",
    "outlook_separator",
    "original_message",
    "signature",
    "sig_block",
)


def unquote_line(line: str) -> str:
    """Strip leading quote markers at any depth."""
    return _QUOTE_PREFIX.sub("", line)


def quote_depth(line: str) -> int:
    prefix = _QUOTE_PREFIX.match(line)
    return len(_QUOTE_MARK.findall(prefix.group(0))) if prefix else 0


def _lookahead_has(lines: list[str], start: int, window: int, predicate) -> bool:
    for j in range(start, min(start + window + 1, len(lines))):
        text = unquote_line(lines[j]).strip()
        if not text:
            continue
        if predicate(text):
            return True
    return False


def strip_boilerplate(lines: list[str], footer_marker: str) -> tuple[list[str], dict[str, int]]:
    """Apply rules 1-5. Returns (kept_lines, counters).

    Guard: drop-to-end rules (2, 3, 5) will not leave body empty.
    If dropping would result in empty content, the rule is not applied.

    To prevent guard from being fooled by preserved boilerplate from earlier
    suppressions, we track the index in `kept` up to which content is genuine
    (i.e., before the first suppressed guard).
    """
    counts = dict.fromkeys(_COUNTER_KEYS, 0)
    kept: list[str] = []
    i = 0
    n = len(lines)
    genuine_content_index = None  # tracks where genuine content ends

    def has_genuine_content() -> bool:
        """Check if kept has content before any suppressed guard."""
        if genuine_content_index is None:
            # No guard suppressed yet; check if kept has any content
            return kept and any(l.strip() for l in kept)
        else:
            # Guard was suppressed; only count content before that suppression
            return any(l.strip() for l in kept[:genuine_content_index])

    while i < n:
        line = lines[i]
        bare = unquote_line(line).strip()
        depth = quote_depth(line)

        if _UNDERSCORES.match(bare):
            # Rule 1 — Mailman footer, at ANY quote depth.
            if _lookahead_has(lines, i + 1, 3, lambda t: footer_marker.lower() in t.lower()):
                counts["mailman_footer"] += 1
                i += 1
                # Consume the footer block: same-depth lines until a blank or
                # a line that is clearly new content.
                while i < n:
                    nxt = unquote_line(lines[i]).strip()
                    if not nxt or quote_depth(lines[i]) != depth:
                        break
                    consumed = (
                        footer_marker.lower() in nxt.lower()
                        or "@" in nxt
                        or nxt.lower().startswith("http")
                        or _UNDERSCORES.match(nxt)
                    )
                    if not consumed:
                        break
                    i += 1
                continue

            # Rules 2 and 5 apply to unquoted separators only.
            if depth == 0:
                if _lookahead_has(lines, i + 1, 3, lambda t: bool(_HEADER_LINE.match(t))):
                    # Rule 2: would drop to end, apply guard
                    if has_genuine_content():
                        counts["outlook_separator"] += 1
                        break  # drop to end
                    else:
                        # Guard suppresses drop; mark the suppression point
                        if genuine_content_index is None:
                            genuine_content_index = len(kept)
                else:
                    # Rule 5: would drop to end, apply guard
                    if has_genuine_content():
                        counts["sig_block"] += 1
                        break  # drop to end
                    else:
                        # Guard suppresses drop; mark the suppression point
                        if genuine_content_index is None:
                            genuine_content_index = len(kept)

        if _ORIGINAL_MSG.match(bare):
            # Rule 3: would drop to end, apply guard
            if has_genuine_content():
                counts["original_message"] += 1
                break  # drop to end
            else:
                # Guard suppresses drop; mark the suppression point
                if genuine_content_index is None:
                    genuine_content_index = len(kept)

        if _SIG_SEP.match(line):
            # Rule 4: signature — NO GUARD, always drop (signature-only messages should be empty)
            counts["signature"] += 1
            break

        kept.append(line)
        i += 1

    return kept, counts
