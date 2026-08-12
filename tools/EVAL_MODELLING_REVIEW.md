# Reviewing a modelling answer

You are checking whether advice produced by a constrained search system is
sound and honestly grounded. You have full access to everything it did not.

There is deliberately **no gold answer**. Several modellings of the same case
can be defensible, and grading against one preferred solution would mark good
alternatives wrong. Your question is not "does this match mine" but "is this
defensible, and is it supported by what it cites".

## You may read anything

```
uv run python search.py concept E36        # dossier: definition, siblings, FOL
uv run python search.py ontology           # all 241 classes and properties
uv run python search.py docs "<query>"     # the 7.3.2 reference model
uv run python search.py thread t0408       # any discussion, in full
uv run python tools/read_thread.py t0408   # the same, without the index
```

`data/ontology.json` and `data/documents.jsonl` are also open to you. Take the
time to actually check things rather than judging from impression.

## What to check, in order

1. **Does the modelling work?** Read the scope notes of every class and
   property proposed. Do the domain and range actually permit the way they are
   being used? A property applied outside its declared domain is simply wrong,
   however plausible the prose around it.

2. **Do the citations support the claims?** This is the part no automated
   check can do. Every cited identifier and thread has already been confirmed
   to *exist*; your job is whether it says what the answer implies. **Open the
   threads.** A real thread id attached to a claim it does not support is a
   more dangerous failure than an invented one, because it survives every
   mechanical check.

3. **Are the rejected alternatives rejected for real reasons?** The cases were
   built so that two or three modellings look plausible. An answer that
   dismisses a genuine alternative with a wrong reason is worse than one that
   admits the choice was close.

4. **Is the in-scope judgement right?** Some cases are deliberately outside
   what the CRM should be stretched to cover. Claiming a confident modelling
   for one of those is a serious error; so is refusing a case the model
   handles perfectly well.

5. **Is the confidence honest?** High confidence on a genuinely contested
   question is a defect even when the answer is defensible.

## Verdicts

- **`sound`** — the modelling works, the citations support it, the
  alternatives are properly handled. Need not be the only good answer.
- **`defensible_but_thin`** — nothing wrong, but the reasoning or the
  alternatives are underdone.
- **`flawed`** — a real error: a property outside its domain, a
  misidentified class, a wrong rejection.
- **`unsupported`** — the recommendation may be fine, but a cited source does
  not say what it is claimed to say. Record this even where the conclusion
  happens to be right.
- **`scope_error`** — in-scope judgement is wrong in either direction.

## Output

Write a JSON list to the path you are given, one object per case:

```json
[
  {
    "case_id": "archaeology-c1",
    "verdict": "sound | defensible_but_thin | flawed | unsupported | scope_error",
    "modelling_works": true,
    "citations_support_claims": true,
    "checked_threads": ["t0674"],
    "reasoning": "One or two sentences naming the specific thing you verified or found wrong.",
    "what_is_wrong": ["only if something is"]
  }
]
```

`checked_threads` records which sources you actually opened. Be strict: this
evaluation exists to find weaknesses, and a generous review produces a
flattering number that teaches nothing. Where you are torn, take the harsher
verdict and say why.
