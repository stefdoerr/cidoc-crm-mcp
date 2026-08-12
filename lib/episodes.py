"""Episode segmentation: prompt preparation and result validation.

The summarization itself is performed by local subagents orchestrated outside
this module (see the Task 13 design note). This file never calls an LLM and
never imports `anthropic` -- it prepares prompts and validates what comes back.
"""

import json
import re
from pathlib import Path

from lib.config import DATA_DIR

# The archive writes the same identifier several ways, and a form this does not
# recognise is indistinguishable from a hallucination:
#   E33_Linguistic_Object   the RDFS class name
#   P14.1                   a property of a property
#   P25i                    the inverse direction
#   P81a / P81b / P120F     the older dual-direction notation (P81a alone
#                           occurs 54 times in this corpus)
# Keeping only the leading identifier handles every one of those spellings at
# once: the trailing i/a/b/F and the "_Linguistic_Object" tail are simply not
# captured. "LRM-E8" keeps its hyphen; "TC46" still resolves to nothing.
_LEADING_ID = re.compile(r"^([A-Z]{1,4}(?:-[A-Z])?\d{1,3})")

_OUTCOMES = ("decided", "unresolved", "informational")
_CONFIDENCES = ("high", "medium", "low")


def _canonical(raw: str) -> str | None:
    """The bare identifier inside `raw`, or None if there is no identifier in it."""
    ident = (raw or "").strip().upper().replace("LRM ", "LRM-")
    match = _LEADING_ID.match(re.sub(r"\.\d$", "", ident))
    return match.group(1) if match else None

# Shards are packed by character budget, not by thread count. Thread size is
# heavily skewed -- median 5k chars, p99 88k, max 182k -- so a fixed 24 threads
# per shard produced shards ranging from 30k to 572k chars. The budget caps how
# much any one subagent must read; the thread cap keeps it from having to hold
# too many independent items in mind at once. A thread larger than the budget
# cannot be split, so it gets a shard to itself.
SHARD_CHAR_BUDGET = 100_000
MAX_THREADS_PER_SHARD = 10

EPISODE_SCHEMA = {
    "type": "object",
    "properties": {
        "episodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "question": {"type": "string"},
                    "message_indexes": {"type": "array", "items": {"type": "integer"}},
                    "positions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "who": {"type": "string"},
                                "position": {"type": "string"},
                            },
                            "required": ["who", "position"],
                        },
                    },
                    "outcome": {
                        "type": "string",
                        "enum": ["decided", "unresolved", "informational"],
                    },
                    "outcome_detail": {"type": "string"},
                    "entities": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": [
                    "topic", "question", "message_indexes", "positions",
                    "outcome", "outcome_detail", "entities", "confidence",
                ],
            },
        }
    },
    "required": ["episodes"],
}

SYSTEM = """You are analysing threads from the CIDOC CRM Special Interest Group \
mailing list, a standards body that has debated the CIDOC CRM ontology since 1999.

Split each thread into EPISODES: topically coherent runs of messages. Most threads \
are a single episode. Split only when the conversation genuinely moves to a \
different subject -- a thread that drifts from an ISO ballot to scheduling the next \
meeting is two episodes. Do NOT split on subject-line variations that describe the \
same conversation ("4 new issues" and "4 new issues, Collection class" are one).

For each episode record what was asked, who argued what, and what was decided. Use \
"decided" only when the thread reaches a conclusion; "unresolved" when the debate \
trails off; "informational" for announcements and logistics.

In `entities`, list the CIDOC CRM class and property identifiers (E55, P140, ...) the \
episode is genuinely ABOUT -- not every identifier mentioned in passing. Lines \
beginning with "| " are quoted text from an earlier message, included for context: \
treat them as what someone else said, not as this author's assertion."""


def eligible_threads(threads: dict, min_size: int = 2) -> list[str]:
    return sorted(t for t, v in threads.items() if len(v["message_ids"]) >= min_size)


def thread_members(threads: dict, thread_id: str, records: dict[str, dict]) -> list[str]:
    """The message ids of a thread that actually exist in `records`, in order.

    Both sides of the round trip MUST derive their message list from this one
    function. The model refers to messages by their position in the prompt, so
    if `dump_prompts` skipped an absent message and `collect_shards` did not,
    every index past the gap would resolve to the wrong message -- silently,
    with no malformed input to catch.
    """
    return [m for m in threads[thread_id]["message_ids"] if m in records]


def pack_shards(thread_ids: list[str], sizes: dict[str, int]) -> list[list[str]]:
    """Group threads into shards bounded by both character count and thread count."""
    shards: list[list[str]] = []
    current: list[str] = []
    total = 0
    for tid in thread_ids:
        size = sizes[tid]
        over_budget = total + size > SHARD_CHAR_BUDGET
        over_count = len(current) >= MAX_THREADS_PER_SHARD
        if current and (over_budget or over_count):
            shards.append(current)
            current, total = [], 0
        current.append(tid)
        total += size
    if current:
        shards.append(current)
    return shards


def build_prompt(thread_id: str, records: list[dict]) -> str:
    parts = [f"### Thread {thread_id} ({len(records)} messages)\n"]
    for i, rec in enumerate(records):
        parts.append(
            f"--- [{i}] {(rec.get('date') or '')[:10]} | "
            f"{rec.get('from_name') or rec.get('from_email')} | "
            f"{rec.get('subject')} ---\n{rec.get('body', '')}\n"
        )
    return "\n".join(parts)


def dump_prompts(threads: dict, records: dict[str, dict], min_size: int = 2) -> Path:
    """Write one prompt file per shard, packed by SHARD_CHAR_BUDGET.

    Shards exist so a subagent reads a file instead of receiving the thread text
    in its dispatch prompt, and so a failed shard can be re-run alone without
    redoing the rest.
    """
    out_dir = DATA_DIR / "prompts"
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob("shard-*.md"):
        f.unlink()

    ids = eligible_threads(threads, min_size)
    prompts = {
        tid: build_prompt(tid, [records[m] for m in thread_members(threads, tid, records)])
        for tid in ids
    }
    prompts = {tid: text for tid, text in prompts.items() if text.strip()}
    shards = pack_shards(list(prompts), {t: len(p) for t, p in prompts.items()})

    for n, shard_ids in enumerate(shards):
        body = "\n\n".join(prompts[tid] for tid in shard_ids)
        (out_dir / f"shard-{n:03d}.md").write_text(body, encoding="utf-8")

    largest = max((len(("\n\n".join(prompts[t] for t in s))) for s in shards), default=0)
    print(f"[episodes] {len(prompts)} threads -> {len(shards)} shards in {out_dir}")
    print(f"[episodes] largest shard: {largest:,} chars")
    return out_dir


def validate_entities(raw_ids, onto: dict):
    """Split model-extracted ids into current / historical / extension / bogus.

    Unknown ids are NOT dropped by default. 61 of them are legitimately
    deprecated CRMbase vocabulary whose removal this archive documents, and
    others belong to the CRM family extensions (FRBRoo, CRMsci, CRMinf, CRMgeo,
    CRMarchaeo, LRMoo ...) that this list also debates. Both categories are
    recognised from collections built at ontology time, not from a pattern:
    "TC46" and "SC4" have the shape of class ids but are the ISO committee.
    Only ids in no collection at all are treated as hallucinations. Normalizes
    the `.1` and inverse-`i` suffixes exactly as extraction does.

    The extension bucket is filtered to ids the archive actually mentions.
    It used to contain only those, so membership alone meant "this corpus
    discusses it"; now `add_extensions` records every declared family
    concept so that models can be validated against the whole family, and
    544 recorded ids include 214 the list has never once discussed. This
    function is asking a different question from the validator's -- not
    "does this identifier exist" but "could a message in THIS archive have
    been talking about it" -- and an id with no occurrences is a likelier
    extraction error than a genuine reference. `mentions` is what carries
    that distinction now.
    """
    buckets = {
        "current": (set(onto["classes"]) | set(onto["properties"]), set()),
        "historical": (set(onto.get("historical", {})), set()),
        "extension": ({i for i, e in (onto.get("extensions") or {}).items()
                       if e.get("mentions")}, set()),
    }
    bogus = set()
    for raw in raw_ids or []:
        ident = _canonical(raw)
        hit = ident and next(
            (b for b, (vocab, _) in buckets.items() if ident in vocab), None
        )
        if hit:
            buckets[hit][1].add(ident)
        else:
            bogus.add(raw)
    return (
        sorted(buckets["current"][1]),
        sorted(buckets["historical"][1]),
        sorted(buckets["extension"][1]),
        sorted(bogus, key=str),
    )


def episode_text(ep: dict) -> str:
    positions = " ".join(
        f"{p.get('who')}: {p.get('position')}" for p in ep.get("positions") or []
    )
    return "\n".join(
        filter(None, [
            ep.get("topic", ""), ep.get("question", ""), positions,
            ep.get("outcome_detail", ""), " ".join(ep.get("entities") or []),
        ])
    ).strip()


def collect_shards(shard_dir: Path, threads: dict, records: dict[str, dict],
                   onto: dict, out_path: Path | None = None) -> list[dict]:
    """Read subagent result shards, validate, and flatten to episode records.

    Parses defensively: a malformed shard or thread is reported and skipped,
    never fatal. Without the Batches API there is no schema enforcement on the
    way in, so this is the only line of defence.

    Writes beside `shard_dir` by default rather than to a fixed path under
    DATA_DIR. The output has to follow the input: when it did not, a unit test
    passing a tmp_path for `shard_dir` still truncated the real
    data/episodes.jsonl -- 883 episodes produced by 111 subagents -- because
    only the read end honoured the argument.
    """
    episodes, errors, hallucinated, extensions = [], [], 0, 0
    coerced = 0

    def enum(value, allowed, default):
        """Force a field back inside its declared enum.

        The schema is advisory here -- nothing enforces it on the way in -- so a
        subagent can and does return an outcome like "proposal". Downstream
        filters query these values exactly, and a stray one is invisible: it
        simply never matches.
        """
        nonlocal coerced
        if value in allowed:
            return value
        coerced += 1
        return default

    for shard in sorted(Path(shard_dir).glob("result-*.json")):
        try:
            payload = json.loads(shard.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{shard.name}: unparseable ({exc})")
            continue

        for thread_id, result in payload.items():
            if thread_id not in threads:
                errors.append(f"{shard.name}: unknown thread {thread_id}")
                continue
            member_ids = thread_members(threads, thread_id, records)
            for n, ep in enumerate(result.get("episodes", []), start=1):
                current, hist, ext, bogus = validate_entities(ep.get("entities"), onto)
                hallucinated += len(bogus)
                extensions += len(ext)
                idx = [i for i in ep.get("message_indexes") or []
                       if 0 <= i < len(member_ids)]
                msg_ids = [member_ids[i] for i in idx] or member_ids
                members = [records[m] for m in msg_ids if m in records]
                dates = sorted(m["date"] for m in members if m.get("date"))
                episodes.append({
                    "episode_id": f"{thread_id}-e{n}",
                    "thread_id": thread_id,
                    "message_ids": msg_ids,
                    "date_start": dates[0] if dates else None,
                    "date_end": dates[-1] if dates else None,
                    "participants": sorted(
                        {m.get("from_name") or m.get("from_email", "") for m in members}
                        - {""}
                    ),
                    "topic": ep.get("topic", ""),
                    "question": ep.get("question", ""),
                    "positions": ep.get("positions") or [],
                    "outcome": enum(
                        ep.get("outcome"), _OUTCOMES, "informational"
                    ),
                    "outcome_detail": ep.get("outcome_detail", ""),
                    "entities": current,
                    "entities_historical": hist,
                    "entities_extension": ext,
                    "confidence": enum(
                        ep.get("confidence"), _CONFIDENCES, "medium"
                    ),
                })

    covered = {e["thread_id"] for e in episodes}
    missing = [t for t in eligible_threads(threads) if t not in covered]
    print(f"[episodes] {len(episodes)} episodes from {len(covered)} threads")
    print(f"[episodes] {extensions} CRM-extension ids kept, "
          f"{hallucinated} hallucinated ids discarded")
    if coerced:
        print(f"[episodes] {coerced} out-of-enum field(s) coerced to a default")
    if missing:
        print(f"[episodes] {len(missing)} threads MISSING — re-run those shards: "
              f"{missing[:8]}{'...' if len(missing) > 8 else ''}")
    for e in errors:
        print(f"[episodes] ERROR {e}")

    out = out_path or Path(shard_dir).parent / "episodes.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for ep in episodes:
            f.write(json.dumps(ep, ensure_ascii=False) + "\n")
    print(f"[episodes] wrote {out}")
    return episodes
