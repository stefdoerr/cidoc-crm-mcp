# Writing the reference answer for a modelling case

You are establishing what a well-informed CIDOC CRM modeller would advise for a
given documentation case. Your answer becomes the standard another, more
constrained system is graded against, so it needs to be right, not fast.

## You have full access — use it

Unlike the system being tested, you may read anything:

```
uv run python search.py concept E36            # dossier: definition, siblings, FOL, citations
uv run python search.py ontology               # all 241 classes and properties
uv run python search.py docs "<query>"         # the 7.3.2 reference model
uv run python search.py "<query>"              # the mailing list
uv run python search.py threads "<query>"      # episode summaries
uv run python search.py thread t0408           # a whole discussion
uv run python tools/read_thread.py t0408       # the same, without the index
```

You may also read `data/ontology.json`, `data/documents.jsonl`, and the
specification itself. Take as long as you need. Check the siblings of any class
you propose — if you cannot say why the neighbours are wrong, you have not
finished.

## What a good reference answer contains

1. **A recommendation.** The specific classes and properties, and how they fit
   together for this case. Be concrete: name the pattern, not just the classes.
2. **The reasoning.** Why these, grounded in scope notes, hierarchy or the
   modelling principles.
3. **The alternatives you rejected, and why.** This is the most valuable part.
   A case is only interesting because two or three modellings look plausible;
   the reference answer must say which and what rules them out.
4. **Citations.** Every substantive claim traceable to something real — an
   identifier, a section of the reference model, or a mailing-list thread.

## Honesty constraints

- **If the CRM genuinely cannot express this, say so.** Some cases are
  deliberately out of scope. "Use an extension" or "this belongs outside the
  model" is a correct reference answer where it is true, and inventing a
  forced class assignment would poison the grading for that case.
- **If the archive contradicts the specification, note both.** Do not silently
  prefer one.
- **If you are unsure between two modellings, say that too**, and record what
  would settle it. A reference answer that pretends to certainty it does not
  have will mark a correct hedge as wrong.
- Do not invent identifiers. Every E/P you name must exist — check it.

## Output

Write to the path you are given:

```json
{
  "case_id": "<given to you>",
  "recommendation": "The modelling, concretely, in a few sentences.",
  "key_points": [
    "an atomic, checkable claim the answer must contain",
    "another"
  ],
  "rejected_alternatives": [
    {"option": "E31 Document", "why_not": "its scope note requires ..."}
  ],
  "citations": ["E36", "P65", "Modelling principles > Minimality", "t0408"],
  "in_scope": true,
  "confidence": "high | medium | low",
  "notes": "anything that surprised you, or that the sources disagree on"
}
```

`key_points` is what grading keys on: 2 to 4 atomic claims, each specific
enough to check ("the physical carrier is E22 and the image content is E36,
linked by P65"), never vague ("use appropriate classes").

Set `in_scope` to `false` where the honest answer is that the CRM should not be
stretched to cover this.
