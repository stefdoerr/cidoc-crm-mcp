# Answering "why is the model like this?"

This is not the modelling-advice task. Nobody is asking which class to use for
their collection. They are asking **why the CIDOC CRM has the shape it has** --
why a class exists, why one was refused, why an identifier was deprecated, why
a range is narrower than it could be.

The answer is a piece of history, and it has to be sourced like one. The SIG
argued these questions out over twenty-six years on a mailing list and recorded
the outcomes in a numbered issue register. Both are searchable here. An answer
that reasons from the current scope note alone has explained nothing: the scope
note is the *result*, and the question is what produced it.

The audience is a **non-expert reader of a paper**. They do not know the CRM.
Write so that someone who has never seen an E-number can follow why the
decision made sense, then let the identifiers and citations carry the proof.

## Your only tool is `search.py`

```
uv run python search.py issues "<query>"          # the SIG's decision register
uv run python search.py issue <n>                 # one issue: status, outcome, threads
uv run python search.py concept <id>              # definition, siblings, applicable properties
uv run python search.py connect <A> <B>           # properties that can join two classes
uv run python search.py docs "<query>"            # the 7.3.2 reference model
uv run python search.py docs "<query>" --kind narrative     # modelling-principle prose
uv run python search.py "<query>"                 # the mailing list
uv run python search.py threads "<query>"         # episode summaries -> thread pointers
uv run python search.py thread <thread_id>        # read a whole discussion
uv run python search.py quote <id> "<phrase>"     # does <id> actually contain this phrase?
```

Do not read the mbox, the docx, the XML or any file under `data/` directly.
The point of the exercise is what this interface can support.

A deprecated identifier still resolves: `concept E84` returns the archive
record for an id the current standard no longer defines. That is the intended
path for a "why was X removed" question.

## What a good answer contains

1. **The decision, in one sentence a non-expert can read.**
2. **The problem it solved.** What went wrong without it, or what breaks if you
   do the obvious alternative. This is the part that makes the paper readable.
3. **A concrete real-world example** -- an actual object, document, place or
   measurement, ideally one the SIG itself used while arguing. Invented
   examples are allowed only if you say they are invented.
4. **The evidence**: issue numbers with their status and outcome, thread ids,
   and specification sections. Quote sparingly and only after `search.py quote`
   returns FOUND.

## The two failure modes that matter

**Inventing a rationale that sounds right.** The commonest defect in this
corpus is a fluent explanation attached to a source that does not say it. If
the archive does not explain why, the answer is "the register records the
decision but not the reasoning" -- which is a real, publishable finding.

**Promoting one person's post to a SIG position.** A message from any single
participant, however senior, is that person's argument. A decision is what the
register records as resolved, naming the meeting. Say which one you have. If a
thread trails off with no resolution, say so and give the issue's status.

## Output

Write JSON to the path you are given:

```json
{
  "question_id": "...",
  "question": "the question as asked",
  "short_answer": "2-3 sentences, non-expert readable, no jargon beyond the id itself",
  "explanation": "the full argument, 150-400 words, written for the paper's reader",
  "real_world_example": "a concrete case; say if you invented it",
  "decision_status": "settled | partly settled | unresolved | not recorded",
  "issues": [{"id": 123, "title": "...", "status": "Done", "outcome": "what the SIG concluded"}],
  "threads": ["t0123"],
  "citations": [{"id": "t0123", "quote": "verified with search.py quote"}],
  "caveats": "what the archive does NOT establish, and anything you inferred rather than found",
  "queries_run": ["..."]
}
```

## The minutes

`docs --kind minutes` reaches 70 SIG meetings, 1995-2026, and this is usually
the best source for a "why" question. The register records *that* an issue was
closed at a named meeting; the mailing list argues towards it; the minutes are
the room deciding. They carry the criteria and the votes -- "we should
deprecate E84 information carrier in CRM since it is a class without
properties" is a line from the 38th meeting, not from any scope note.

`search.py issue <n>` now lists the meetings that took the issue up, each with
the chunk id to quote from. 603 of the 715 issues appear in the minutes, and
**314 of those are cited by no mailing-list thread at all** -- for those, the
minutes are the only surviving discussion, and an answer that reports "the
archive does not explain why" without checking them is wrong.

Seven issue numbers are gaps in today's register (113, 114, 119, 201, 217,
540, 641) and at least two of them were real agenda items once. `issue 113`
says so rather than rendering a blank.
