# Answering an evaluation question

You are being given one question about the CIDOC CRM Special Interest Group
mailing list — a standards body that has debated the CIDOC CRM ontology since
1999. Answer it using the archive search system, and only that.

## Your only tool is `search.py`

```
uv run python search.py "<query>" -k 10                # hybrid message search
uv run python search.py "<query>" -k 10 --mode bm25    # lexical only
uv run python search.py "<query>" -k 10 --mode vector  # semantic only
uv run python search.py "<query>" --after 2015 --before 2018
uv run python search.py "<query>" --entity E55
uv run python search.py threads "<query>" -k 5         # episode summaries -> thread pointers
uv run python search.py concept E55                    # ontology entry + chronology
uv run python search.py ontology                       # the whole class/property skeleton
uv run python search.py thread <thread_id>             # read a whole thread
uv run python search.py show <message_id>              # read one message
```

The first search loads an embedding model and takes 6-12 seconds. That is
normal; be patient rather than giving up on a query.

## Forbidden — using any of these invalidates the result

- `tools/read_thread.py`
- Reading, grepping or opening `data/clean.jsonl`, `data/threads.json`,
  `data/episodes.jsonl`, `crm-sig.mbox`, or anything under `data/eval/`
- Any `grep`, `rg`, `awk`, `sed`, `cat`, `head`, `tail`, or Python that reads
  the corpus directly

The point of this exercise is to measure whether **the search system** can
find the answer. Reading the corpus directly measures nothing.

## Method

**Summaries route, they never answer.** `search.py threads` gives you topics
and thread pointers — treat those as leads, not as the answer. Open the actual
threads with `search.py thread <id>` and read the messages before asserting
anything. Same for `concept <id>`: its chronology is a list of places to look.

Search more than once. If your first query fails, try a different phrasing, a
different mode, a date filter, or an identifier you learned from an earlier
hit. Real use looks like several queries, not one.

## Honesty is the measurement

- If you cannot find the answer, say so. "Not found" is a **correct and
  valuable** result — it tells us the system failed on this question, which is
  precisely what the evaluation is for. A plausible guess is far worse than an
  admission, because it corrupts the score in the flattering direction.
- If the archive discusses the topic but never settles it, say that it was
  never settled. Do not manufacture a resolution.
- Answer only from what you actually read in retrieved messages. **Do not use
  your own background knowledge of CIDOC CRM.** If you know the answer from
  training but did not find it in the archive, that is a `not_found`.

## Output

Write your result as JSON to the path you are given:

```json
{
  "question_id": "<given to you>",
  "answer": "Your answer in your own words, or an explicit statement that you could not find it.",
  "found": true,
  "cited_threads": ["t0408"],
  "queries_run": [
    "search \"scope note E55 Type\" -k 10",
    "threads \"E55 Type scope note\" -k 5",
    "thread t0408"
  ],
  "confidence": "high | medium | low",
  "notes": "anything that went wrong, or a query you expected to work and didn't"
}
```

- `found` — `false` if you could not locate an answer. Be strict with yourself.
- `cited_threads` — the thread ids you actually read and drew the answer from.
- `queries_run` — every query you issued, in order, including failures. This is
  how we diagnose retrieval, so do not tidy it up.
