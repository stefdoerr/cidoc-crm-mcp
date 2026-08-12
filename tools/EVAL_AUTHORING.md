# Writing blind evaluation questions

You are writing questions to test a retrieval system over the CIDOC CRM
Special Interest Group mailing list — a standards body that has debated the
CIDOC CRM ontology since 1999.

**You must not use the retrieval system.** That is the whole point. If you
find a topic by searching for it, the search is guaranteed to find it again
and the question measures nothing.

## Forbidden

- `search.py` — any subcommand, for any reason
- `data/episodes.jsonl` — these are summaries the system itself generated;
  writing questions from them tests the system against its own output
- `stores/` — the indexes
- `tests/smoke_queries.yaml` — the existing retrieval cases
- Grepping `data/clean.jsonl` or `crm-sig.mbox` to hunt for a topic you already
  have in mind. Read threads; don't search them.

## Allowed — this is your only tool

```
uv run python tools/read_thread.py --list <FROM_YEAR> <TO_YEAR>
uv run python tools/read_thread.py <thread_id>
```

The `--list` form gives you an index of substantial threads in a period; the
second reads one in full. Browse the list, open threads that look substantive,
and write questions from what you actually read.

## What makes a good question here

Write what a **researcher or ontology modeller would genuinely ask** — not
trivia, and not a lookup that a single keyword would answer.

Strong question shapes:

- **Outcome** — "Was the proposal to X accepted, and what was the reasoning?"
- **Evolution** — "How did the treatment of X change between year A and B?"
- **Rationale** — "Why was X rejected in favour of Y?"
- **Disagreement** — "What were the competing positions on X, and who held them?"
- **Modelling advice** — "How did the SIG say one should model X?"
- **Deprecation** — "What happened to X and what replaced it?"

Avoid:

- Anything answerable by pasting one identifier into a keyword search
- Questions whose answer is a single date or name with no reasoning
- Questions that depend on wording only you saw ("in the third message,
  what did the author mean by 'this'")

**Include one question in your set whose honest answer is that the archive
never settled it.** A system that invents a resolution for an unresolved
debate is worse than one that says "they never agreed", and nothing else in
the suite tests that.

## Difficulty

Of your 4 questions: roughly 1 straightforward, 2 genuinely hard (multi-hop,
spanning several messages or threads), 1 unresolved-or-subtle.

## Output

Write `data/eval/authored-<SLICE>.json` — a JSON list of exactly 4 objects:

```json
[
  {
    "question": "Was the proposal to make E22 a subclass of E19 accepted, and why?",
    "gold_answer": "Two to four sentences answering it directly, in your own words, from what you read. State the actual outcome and the reasoning. If it was never resolved, say so plainly and say where it was left.",
    "key_facts": [
      "a specific checkable claim the answer must contain",
      "another one",
      "a third"
    ],
    "gold_threads": ["t0408", "t0412"],
    "difficulty": "easy | hard | unresolved",
    "why_this_is_hard": "one line: what makes this more than a keyword lookup"
  }
]
```

Rules for the fields:

- `gold_answer` — written from the messages you read, not from memory of CIDOC
  CRM in general. If the archive contradicts the published standard, follow the
  archive.
- `key_facts` — 2 to 4 atomic, checkable claims. These are what grading keys
  on, so make them specific ("E84 Information Carrier was deprecated in favour
  of E22 with P2 has type"), not vague ("they discussed deprecation").
- `gold_threads` — every thread id that genuinely supports the answer. This is
  also how retrieval is scored, so be complete and be accurate.
- Do not mention thread ids or message ids inside `question` or `gold_answer`.
  The question must be answerable by someone who has never seen the archive.

## Honesty

If your slice has nothing worth 4 good questions, write fewer and say so in
your report. A thin but honest set is worth more than four padded questions —
they become the benchmark, and a bad benchmark is worse than none.
