"""Quote-block classification (spec rules 6-8) plus the thin-reply guard.

Rules 6 and 8 discriminate on BLOCK COUNT, not position. Keying rule 6 on
"quoted lines after the last content line" silently fails on bottom-posting,
where the quote precedes the reply -- and bottom-posting is common in this
corpus's era. Block count is also what the corpus measurement established:
2,255 single-block messages (strippable) vs 552 interleaved (load-bearing).

Pipe character `|` is a quote marker in some mail clients, but also used for
signature box-drawing. Discriminate: | counts as quote only if no second |
appears on the line AND actual content follows it. This eliminates false
positives from table rows and box borders while preserving genuine | quotes.
"""

import re

# Quote detection: > is always a quote; | only if no second | on line and has content after.
_QUOTED = re.compile(r"^\s*(>|\|(?!.*\|)(?=\s*\S))")
_MARK = "| "

_ATTRIBUTION = re.compile(
    r"(wrote:|writes:|schrieb:?|escribi[oó]:?|ha scritto:?|a écrit|schreef|"
    r"-{2,}\s*Original Message)",
    re.I,
)


def is_quoted(line: str) -> bool:
    return bool(_QUOTED.match(line))


def is_attribution(line: str) -> bool:
    """True for the attribution line that introduces a quote block."""
    text = line.strip()
    if not text or len(text) > 200:
        return False
    if not _ATTRIBUTION.search(text):
        return False
    # "wrote:" style attributions end at the colon; prose about writing doesn't.
    return text.endswith(":") or bool(re.search(r"-{2,}\s*Original Message", text, re.I))


def count_quote_blocks(lines: list[str]) -> int:
    """Number of maximal runs of quoted lines, ignoring blank separators."""
    seq = [is_quoted(ln) for ln in lines if ln.strip()]
    return sum(1 for i, q in enumerate(seq) if q and (i == 0 or not seq[i - 1]))


def _strip_text(lines: list[str]) -> str:
    return "".join(ln.strip() for ln in lines)


def apply_quote_rules(
    lines: list[str],
    thin_reply_chars: int = 200,
    context_lines: int = 15,
) -> tuple[list[str], list[tuple[int, int]], dict[str, int]]:
    """Apply rules 6-8 plus the thin-reply guard.

    Returns (kept_lines, quote_spans, counters). quote_spans index into
    kept_lines and mark retained (marked) quoted regions.
    """
    counts = {
        "single_block_quote": 0,
        "interleaved_kept": 0,
        "attribution": 0,
        "thin_reply_context": 0,
    }
    blocks = count_quote_blocks(lines)

    if blocks == 0:
        return list(lines), [], counts

    if blocks >= 2:
        # Rule 8 — interleaved: retain every quoted line, marked.
        counts["interleaved_kept"] = 1
        kept: list[str] = []
        spans: list[tuple[int, int]] = []
        run_start = None
        for line in lines:
            if is_quoted(line):
                if run_start is None:
                    run_start = len(kept)
                kept.append(_MARK + _QUOTED.sub("", line).strip())
            else:
                if run_start is not None:
                    spans.append((run_start, len(kept) - 1))
                    run_start = None
                if is_attribution(line):
                    counts["attribution"] += 1
                    continue
                kept.append(line)
        if run_start is not None:
            spans.append((run_start, len(kept) - 1))
        return kept, spans, counts

    # Rule 6 — exactly one contiguous quote block: top- OR bottom-posted.
    counts["single_block_quote"] = 1
    content, quoted = [], []
    for line in lines:
        if is_quoted(line):
            quoted.append(_QUOTED.sub("", line).strip())
        elif is_attribution(line):
            counts["attribution"] += 1
        else:
            content.append(line)

    # Trim blank padding left behind by the removed block.
    while content and not content[0].strip():
        content.pop(0)
    while content and not content[-1].strip():
        content.pop()

    if len(_strip_text(content)) >= thin_reply_chars:
        return content, [], counts

    # Thin-reply guard: "I agree" is unretrievable and unsummarizable alone.
    counts["thin_reply_context"] = 1
    context = [_MARK + q for q in quoted[:context_lines] if q or True][:context_lines]
    kept = context + ([""] if context and content else []) + content
    spans = [(0, len(context) - 1)] if context else []
    return kept, spans, counts
