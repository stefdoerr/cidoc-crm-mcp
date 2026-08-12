# Ranking three modelling answers, blind

You are given one modelling case and three answers to it, labelled only
**A**, **B** and **C**. You do not know which system or which run produced
any of them, and the labels were shuffled independently for this case. Rank
them.

There is deliberately **no gold answer**. Several modellings of the same
case can be defensible. Your question is not "which matches mine" but
"which of these three is the modelling the CIDOC CRM actually prescribes,
and which is furthest from it".

## You may read anything

```
uv run python search.py concept E36        # dossier: definition, siblings, FOL, applicable properties
uv run python search.py ontology           # all 241 classes and properties
uv run python search.py docs "<query>"     # the 7.3.2 reference model
uv run python search.py connect E11 E29    # which properties join two classes
uv run python search.py thread t0408       # any discussion, in full
uv run python tools/read_thread.py t0408   # the same, without the index
```

`data/ontology.json` and `data/documents.jsonl` are open to you. Check
things rather than judging from impression.

## How to compare

Work through these in order. Earlier items outrank later ones.

1. **Is each proposed property legal?** Read its declared domain and range.
   A property applied outside them is an error, however plausible the prose.
2. **Does each proposed class survive its own scope note, including what
   the note excludes?** Scope notes redirect: E11's points at E81, E73's at
   E31 and E33. A redirected case left in the general class is wrong.
3. **Is the class specific enough?** The CRM expects the most specific
   applicable term. Correct-but-too-general is a defect.
4. **Do the citations support the claims?** Every cited id has already been
   confirmed to *exist*; your job is whether it says what the answer implies.
   Open the threads. A real thread attached to a claim it does not support
   is more dangerous than an invented one, because it survives every
   mechanical check.
5. **Are the rejected alternatives rejected for real reasons?** These cases
   were built so two or three modellings look plausible. Dismissing a
   genuine alternative with a wrong reason is worse than admitting the
   choice was close.

## Judge length and breadth honestly, in both directions

These answers may differ in how many classes they propose. **More is not
better and not worse on its own.** Two distinct failures are possible and
you must be able to name which one you are seeing:

- **Padding.** A class is listed that the case does not need, so that the
  answer has another rival to dismiss, or to look thorough. Symptoms: the
  class appears in `classes_proposed` but does no work in the prose; or it
  is generic infrastructure (a Time-Span, a Type, an Appellation) named
  where the case never asked how time or naming is recorded.
- **Under-specification.** A class the case genuinely requires is absent, so
  the reader cannot instantiate the model. Symptom: the prose relies on an
  entity it never types.

For each answer, state the count and say whether you found padding,
under-specification, or neither. An answer with more classes that are all
load-bearing beats one with fewer that omits a required class. An answer
with more classes where some are decoration loses to a tighter one.

## Out of scope is a real answer

Some of these cases genuinely fall outside what the CRM represents, and
some questions the SIG never settled. `in_scope: false`, or "the model does
not determine this", is the correct answer where that is true, and an
answer manufacturing false certainty is worse than one admitting the limit.
You may only credit that conclusion with evidence — name the thread or the
scope note.

## Do not reward effort

`queries_run` earns nothing. A long answer citing many threads that gets
the modelling wrong ranks below a short one that gets it right.

## Output

Write JSON to the path you are given:

```json
{
  "case_id": "<given to you>",
  "ranking": ["<best label>", "<middle label>", "<worst label>"],
  "per_answer": [
    {"label": "A",
     "class_count": 0,
     "breadth": "padding | under-specified | neither",
     "illegal_properties": ["<property id, with why>"],
     "scope_note_violations": ["<class id, with why>"],
     "unsupported_citations": ["<id, with what it actually says>"],
     "verdict": "one or two sentences"}
  ],
  "decisive_difference": "What actually separated first from last. If they are near-indistinguishable, say so plainly.",
  "confident": true,
  "notes": "anything that made this hard"
}
```

- `ranking` must contain exactly the three labels, no ties. If you genuinely
  cannot separate two, order them and say so in `decisive_difference` — a
  forced order plus an explicit "these two were indistinguishable" is more
  useful than a tie, because it lets the tie be counted.
- `confident`: `false` if your ranking would plausibly come out differently
  on a re-read. Say so; it is not a failing. This field is used to measure
  the ranking's own reliability, and an inflated `true` corrupts that.
