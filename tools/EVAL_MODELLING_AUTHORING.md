# Writing modelling cases

You are writing test cases for a system whose job is to help someone choose the
right CIDOC CRM classes and properties for their own documentation problem, and
to ground that advice in citable sources.

A case is a **realistic documentation scenario**, not a question about the CRM.
"What is E55 Type?" is a lookup. "We hold three impressions of the same
engraving, printed from the same plate at different dates, and one was
retouched by the artist afterwards — how do we record that?" is a modelling
case.

## You must not look at the corpus

Do not read, search, grep or open any of these:

- `search.py` — any subcommand
- `cidoc_crm_version_7.3.2.docx`, `cidoc_crm_v7.1.3.xml`, `crm_family.json`
- `data/` — anything in it, including `clean.jsonl`, `documents.jsonl`,
  `episodes.jsonl`, `ontology.json`, and everything under `data/eval/`
- `stores/`
- `tools/read_thread.py`

Write from your own knowledge of cultural-heritage documentation. You may use
what you know about CIDOC CRM to judge whether a case is *answerable*, but the
case itself must come from the domain, not from the model's own text.

## Novelty is the point

The corpus contains the CRM specification and 26 years of mailing-list debate.
Both are full of worked examples. A case that restates one of those measures
nothing — the system would be reciting, not reasoning.

So **avoid canonical CIDOC CRM textbook examples**. Do not build a case around
famous objects or scenarios that a standards document would reach for as an
illustration: celebrated sculptures with multiple casts, well-known logos,
named historic warships, famous paintings, the Rosetta Stone, and so on. If an
example feels like something an ontology tutorial would use, it probably is.

Invent ordinary, specific, plausible situations instead. Regional museums,
municipal archives, university collections, field archaeology, natural history,
folk-life collections, sound archives, technical heritage. Concrete but not
famous.

Every case will be screened mechanically against the corpus. Cases whose
distinctive terms already appear there will be rejected, so specificity that is
genuinely yours is what survives.

## What makes a case good

- **A real choice.** The scenario should admit two or three defensible
  modellings, and the interesting part is which one fits and why. If there is
  one obvious class and no alternative, the case is too easy.
- **Answerable from the model.** The CRM must actually be able to express it.
  Do not invent scenarios needing an extension that does not exist.
- **Specific enough to model.** "How do we record provenance?" is too vague.
  Name the objects, the events, the actors and what is uncertain.
- **A stated difficulty.** Say in one line what makes it more than a lookup —
  the sibling classes it sits between, the shortcut-versus-full-path question,
  the temporal or identity subtlety.

Vary the shape across your set. Useful kinds:

| kind | what it tests |
|---|---|
| class choice | discriminating between sibling classes |
| property choice | picking the right relation, and its direction |
| shortcut vs full path | whether the abbreviated property is adequate |
| identity | when two records are one thing, or one record is two |
| uncertainty | attribution, dating or provenance that is disputed |
| out of scope | the CRM deliberately does **not** model this |

**Include one case that the CRM should not be stretched to cover.** A system
that always produces a confident class assignment is dangerous, and nothing
else in the set tests whether it will say "this belongs in an extension" or
"this is outside the model's scope".

## Output

Write `data/eval/modelling-<SLICE>.json` — a JSON list of exactly 3 objects:

```json
[
  {
    "case": "Two to five sentences describing the situation concretely, in the words of the person who has the problem. No CRM identifiers. No jargon from the model.",
    "question": "The specific thing they need decided, phrased as a question.",
    "kind": "class choice | property choice | shortcut vs full path | identity | uncertainty | out of scope",
    "why_hard": "One line: what the real choice is, and what makes it more than a lookup.",
    "distinctive_terms": ["engraving", "retouched plate", "impression"]
  }
]
```

`distinctive_terms` is what the novelty screen uses. List the 3-6 concrete
nouns and phrases that make your case what it is — objects, materials,
activities. Not CRM vocabulary, not generic words like "museum" or "object".

**Do not include a suggested answer or any E/P identifiers anywhere.** The
reference answer is written separately by someone with full access to the
sources; if you supply one from memory it will be wrong in ways that are hard
to detect and it will corrupt the grading.
