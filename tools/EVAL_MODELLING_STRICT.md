# Strict pass: is this modelling actually correct?

A first review pass already looked at these answers and asked whether they were
defensible. That framing was too soft, and this pass exists to correct it.

**The CIDOC CRM is strict.** Scope notes state what a class comprises and what
it excludes. Properties declare a domain and a range, and applying one outside
them is not a stylistic difference, it is an error. The first-order-logic
clauses are constraints, not commentary. For most modelling problems there is a
right answer and the model determines it.

So your default question is **not** "could someone argue for this". It is:

> Is this the modelling the CIDOC CRM actually prescribes for this case, and if
> not, what does it prescribe instead?

## Try to break it

Work adversarially. For each answer:

1. **Check every property against its declared domain and range.** Read them in
   `search.py concept <id>`. If a proposed property connects two things it is
   not declared to connect, the answer is wrong, no matter how well argued.
2. **Check every class against its scope note, including what it excludes.**
   Scope notes routinely redirect: E11's points at E81, E73's points at E31 and
   E33. A redirected case put in the general class is wrong.
3. **Check the FOL.** Where a clause exists it is decisive and often sharper
   than the prose.
4. **Look for a more specific class or property.** The CRM expects the most
   specific applicable term. A correct-but-too-general answer is a defect.
5. **Then try to find the better modelling yourself**, and compare.

## The one legitimate exception

Some questions the SIG genuinely never settled — the archive contains
multi-year debates that end unresolved. For those, "the model does not
determine this" is the correct answer, and an answer that manufactures false
certainty is wrong.

But you may only reach that conclusion **with evidence**: name the thread where
it was left open. Absence of a settled answer is a claim about the archive, and
it has to be shown, not assumed. Do not use "contested" as a way to avoid
judging.

## Verdicts

- **`correct`** — this is what the CRM prescribes. You tried to find a better
  modelling and could not.
- **`suboptimal`** — not wrong, but a more specific or more direct construct
  exists. Name it.
- **`wrong`** — a property outside its domain or range, a class whose scope
  note excludes this case, an FOL violation, or a misidentified relationship.
  Name the violated constraint exactly.
- **`unsupported`** — a cited source does not say what the answer claims.
  Record this even when the conclusion is right.
- **`contested`** — the CRM genuinely does not determine this, **and you can
  cite the thread that shows the SIG left it open**.

## Output

Write a JSON list to the path you are given:

```json
[
  {
    "case_id": "archaeology-c1",
    "verdict": "correct | suboptimal | wrong | unsupported | contested",
    "constraint_checked": "P53 domain E18/E19 -> range E53; the answer applies it to E22, which is a subclass of E19, so it holds",
    "better_modelling": "only if one exists -- state it concretely",
    "evidence": ["E53", "t0674"],
    "reasoning": "One or two sentences. Name the constraint, not an impression."
  }
]
```

Be harsh. The first pass was lenient by construction; if you agree with
everything it said, this pass has added nothing. Where you are torn between two
verdicts, take the harsher one and say why.
