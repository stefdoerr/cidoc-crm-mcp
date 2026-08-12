"""Stage 1: mbox -> data/clean.jsonl.

body_raw is retained alongside body because stripping is heuristic across 26
years and every mail client of the era. A bad rule then becomes a re-run of
stage 1 rather than a re-parse of a 143MB mbox.
"""

import hashlib
import json
import mailbox
import re
from collections import Counter
from email.utils import parsedate_to_datetime

from lib.config import DATA_DIR, PROJECT_ROOT
from lib.mboxparse import (
    decode_header_value,
    extract_attachments,
    extract_body,
    parse_addresses,
    split_from,
)
from lib.quotes import apply_quote_rules
from lib.strip import strip_boilerplate

_LIST_TAG = re.compile(r"\[crm-sig\]\s*", re.I)
_WAS = re.compile(r"\(was:.*?\)", re.I | re.S)
_REPLY = re.compile(r"^\s*((re|fwd|aw|fw|sv|vs|antw)\s*:\s*)+", re.I)
_WS = re.compile(r"\s+")
_MSGID = re.compile(r"<[^>]+>")


def normalize_subject(subject: str | None) -> str:
    s = _WAS.sub("", _LIST_TAG.sub("", decode_header_value(subject)))
    return _WS.sub(" ", _REPLY.sub("", s.strip())).strip().lower()


def _hash_id(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def extract_entities(text: str, id_pattern: str, onto: dict) -> tuple[list[str], list[str]]:
    """Split E##/P## mentions into current (resolves against v7.1.3) and historical.

    Both CRM suffixes normalize to the base id:
      * `.1` on properties-of-properties (P14.1 -> P14)
      * `i` on the inverse reading (P25i moved by -> P25)

    The inverse form is not cosmetic. A pattern without the optional `i` matches
    *nothing* on "P25i" -- \\b cannot sit between "5" and "i" -- so 661 mentions
    disappear rather than being misfiled, and P25 reads as 10 mentions when it
    actually has 153. That inverts the volume signal for exactly the properties
    people argue about in reverse.
    """
    known = set(onto["classes"]) | set(onto["properties"])
    current, historical = set(), set()
    for match in re.finditer(id_pattern, text):
        base = match.group(1)
        (current if base in known else historical).add(base)
    return sorted(current), sorted(historical)


def _iso_date(msg) -> str | None:
    try:
        return parsedate_to_datetime(msg.get("Date", "")).isoformat()
    except (TypeError, ValueError):
        return None


def clean_message(msg, index: int, cfg: dict, onto: dict) -> dict:
    raw_body, _source = extract_body(msg)
    lines = raw_body.splitlines()

    after_boiler, boiler_counts = strip_boilerplate(lines, cfg["list_footer_marker"])
    kept, spans, quote_counts = apply_quote_rules(after_boiler)
    body = "\n".join(kept).strip()

    pattern = cfg["ontology"]["id_pattern"]
    quoted_text = "\n".join(ln for ln in kept if ln.startswith("| "))
    own_text = "\n".join(ln for ln in kept if not ln.startswith("| "))
    subject = decode_header_value(msg.get("Subject"))
    entities_body, hist_body = extract_entities(own_text, pattern, onto)
    entities_quoted, hist_quoted = extract_entities(quoted_text, pattern, onto)
    entities_subject, hist_subject = extract_entities(subject, pattern, onto)

    # Subject-line ids fold into `entities`, not `entities_quoted`. Even on a
    # `Re:` subject inherited from the message being replied to, the subject
    # names the thread's own declared topic -- structurally the author's (or
    # thread's) assertion of aboutness, not another author's prose re-quoted
    # into this message. That reading holds even when the identifying
    # discussion itself lives only in a quoted block this message stripped:
    # a thread titled "NEW ISSUE ... E55" is about E55 regardless of where
    # the word last appeared verbatim.
    entities = sorted(set(entities_body) | set(entities_subject))
    entities_historical = sorted(set(hist_body) | set(hist_quoted) | set(hist_subject))

    message_id = (msg.get("Message-ID") or f"__no_id_{index}").strip()
    name, addr = split_from(msg.get("From"))
    refs = _MSGID.findall(msg.get("References") or "")

    return {
        "id": _hash_id(message_id),
        "message_id": message_id,
        "mbox_index": index,
        "date": _iso_date(msg),
        "from_name": name,
        "from_email": addr,
        "to": parse_addresses(msg.get("To")),
        "cc": parse_addresses(msg.get("Cc")),
        "subject": subject,
        "subject_norm": normalize_subject(msg.get("Subject")),
        "in_reply_to": (msg.get("In-Reply-To") or "").strip() or None,
        "references": refs,
        "body": body,
        "body_raw": raw_body,
        "quote_spans": [list(s) for s in spans],
        "entities": entities,
        "entities_quoted": entities_quoted,
        "entities_historical": entities_historical,
        "stripped": {**boiler_counts, **quote_counts},
        "attachments": extract_attachments(msg),
        "n_chars": len(body),
    }


def run_clean(cfg: dict, onto: dict, limit: int | None = None) -> dict:
    """Write data/clean.jsonl, deduplicating on message_id.

    Delivery loops on a 26-year mailing list resend the identical message
    under the identical Message-ID; two such records would carry the same
    `id = sha1(message_id)[:16]`, so a downstream `chunk_id = f"{id}#{i}"`
    collides and the duplicate is indexed (and retrieval-weighted) twice.
    Keyed on message_id rather than body content: two different messages can
    legitimately share a body ("+1"), and collapsing those would be real
    data loss. Messages with no Message-ID header get the synthetic,
    index-qualified `__no_id_{index}` fallback, which is unique per message
    by construction and so never collides with itself.
    """
    mbox = mailbox.mbox(str(PROJECT_ROOT / cfg["mbox"]))
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / "clean.jsonl"

    totals: Counter = Counter()
    raw_chars = clean_chars = messages = duplicates = 0
    seen_ids: set[str] = set()

    with open(out_path, "w", encoding="utf-8") as f:
        for index, msg in enumerate(mbox):
            if limit is not None and index >= limit:
                break
            rec = clean_message(msg, index, cfg, onto)
            if rec["message_id"] in seen_ids:
                duplicates += 1
                continue
            seen_ids.add(rec["message_id"])
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            totals.update(rec["stripped"])
            raw_chars += len(rec["body_raw"])
            clean_chars += rec["n_chars"]
            messages += 1

    return {
        "messages": messages,
        "duplicates_skipped": duplicates,
        "raw_chars": raw_chars,
        "clean_chars": clean_chars,
        "reduction_pct": 100 * (1 - clean_chars / raw_chars) if raw_chars else 0.0,
        "counters": dict(totals),
        "output": str(out_path),
    }
