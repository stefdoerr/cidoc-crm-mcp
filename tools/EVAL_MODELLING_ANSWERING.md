# Answering a modelling case

Someone has a real documentation problem and needs to know which CIDOC CRM
classes and properties to use, and why. Answer them using the archive search
system, and only that.

## Your only tool is `search.py`

```
uv run python search.py ontology                  # every identifier, one line each: CRMbase,
                                                  #   the family models, and the historical ids
uv run python search.py ontology --model CRMsci   # one model only
uv run python search.py concept E90               # dossier: definition, siblings, FOL, citations
uv run python search.py connect E90 E62           # which properties can join these two classes?
uv run python search.py validate E90 <property> E62   # is this link legal? (accepts a label)
uv run python search.py docs "<query>"            # the 7.3.2 reference model
uv run python search.py docs "<query>" --kind narrative     # modelling guidance prose
uv run python search.py docs "<query>" --kind declaration   # class/property definitions
uv run python search.py docs "<query>" --kind minutes       # 70 SIG meeting minutes, 1995-2026
uv run python search.py "<query>"                 # the mailing list
uv run python search.py threads "<query>"         # episode summaries -> thread pointers
uv run python search.py thread <thread_id>        # read a whole discussion
uv run python search.py quote <id> "<phrase>"     # does <id> actually contain this phrase?
uv run python search.py issue <n>                 # a SIG issue: official status, outcome, threads
uv run python search.py issues "<query>"          # search the SIG's decision record
```

Four of these are worth knowing about in detail.

`connect <A> <B>` is for when you have the two ends of a relationship and need
the property in between. It reads the declared domain and range, following the
class hierarchy, so a property declared on a parent is offered for its
subclasses. An empty result is a real answer: in the CRM it usually means the
link runs through an event rather than directly.

`concept <id>` lists **every** applicable property, named, with its range, and
marks the ones the CRM quantifies as `necessary`. Do not skip the `Required`
block — those are the properties an instance of that class is expected to
carry. It also shows the **siblings** block, which is what you are choosing
between; see the section below.

`concept <id>` covers the CRM **family** models as well as CRMbase, with real
scope notes and domain/range. If a case looks like it wants an extension,
inspect one rather than guessing.

`issue <n>` and `issues` reach the SIG's own decision register: 715 numbered
issues, 588 carrying an `outcome` that names the meeting which closed them. A
mailing-list thread often trails off because the resolution landed years later
under the same issue number. `docs` searches the specification; `issues`
searches the decision record; `--kind minutes` searches the meetings
themselves, which is usually where the reasoning is.

The first call loads an embedding model and takes 6-12 seconds. That is normal.

## Forbidden — using any of these invalidates the result

- `tools/read_thread.py`
- Reading, grepping or opening `data/`, `stores/`, `crm-sig.mbox`,
  `cidoc_crm_version_7.3.2.docx`, `cidoc_crm_v7.1.3.xml`, `crm_family.json`
- Any `grep`, `rg`, `cat`, `head`, `sed`, `awk` or Python that reads the
  corpus directly

The point is to measure whether **the search system** puts enough in front of
you to reason well. Reading the sources directly measures nothing.

## Method

The CRM is deliberately abstract. Whatever concrete objects your case is
about, the model will not name them — enumerating concrete cases is exactly
what its Minimality principle forbids. **Mapping the case onto the
abstractions is your job.** Do not expect a search for the literal objects to
return the answer.

A workable approach:

1. `ontology` to see the whole space, and narrow to candidates yourself.
2. `concept <id>` on each candidate. Read the **siblings** block — it shows
   what you are choosing between, which is usually where the answer is.
3. `docs --kind narrative` for the modelling principles bearing on the choice.
4. The mailing list, the issue register and the minutes for cases where the
   SIG argued this exact boundary.

## Required: weigh the nearest rival to every class you propose

**For each class in `classes_proposed`, name at least one of its siblings and
say why you did not use it.** The siblings block of `concept <id>` is where
you find them: the other subclasses of the same parent. Record each one in
`siblings_considered`.

One sibling per proposed class, not all of them — some classes have a dozen or
more, and a line on each is padding rather than thought. Pick the one a
knowledgeable reader would ask about. If you genuinely think no sibling is a
plausible rival, name the closest and say exactly that.

A class with no siblings is exempt, and so is any extension class whose
parents are not in the indexed hierarchy.

## Honesty is the measurement

- **Some of these cases are deliberately out of scope.** If the honest answer
  is that the CRM should not be stretched to cover this, say so. A confident
  class assignment for something the model does not represent is worse than
  admitting the limit.
- **Cite only what you actually saw.** Every identifier, thread id and section
  path in your answer is checked mechanically against the real corpus. An
  invented citation is recorded as fabrication, which is worse than having no
  citation.
- **If you quote someone, verify the quote before you write it down.** A
  citation to a real thread is not enough: a real thread can still be cited
  for a line nobody in it ever wrote, or for wording it never uses. Before
  putting a quoted phrase in an answer, run:

  ```
  uv run python search.py quote <source id> "<the exact phrase>"
  ```

  **Copy the source id from the output you are quoting; do not construct
  one.** A thread listing gives you `thread=<id>`, and every `docs`, `issues`
  and `issue` hit prints the exact `search.py quote ...` command for that
  passage. Passing a bare concept id where a document chunk id is wanted
  always fails, and the failure is silent in the sense that it tells you the
  source is unknown rather than that the phrase is absent.

  It reports FOUND, with the message index and author so you can attribute it
  correctly, or NOT FOUND, with the closest thing actually present so you can
  tell whether you misremembered the wording or the source. If it says NOT
  FOUND, do not paraphrase and retry hoping it slips through — find the real
  wording, quote something shorter that does check out, or drop the quotation
  marks and describe the position in your own words. UNKNOWN SOURCE is a
  different result from NOT FOUND: it means the id was wrong, so fix the id
  and run it again rather than abandoning the quotation.
- **Do not answer from your own CIDOC CRM knowledge.** If you know something
  from training but did not find it through the tools, either find it or leave
  it out. That is what is being measured.
- If you cannot reach an answer, say so. "Not found" is a valuable result.

## Output

Write your result as JSON to the path you are given:

```json
{
  "case_id": "<given to you>",
  "answer": "Your recommendation and reasoning, in your own words.",
  "classes_proposed": ["<the classes you recommend>"],
  "properties_proposed": ["<the properties you recommend>"],
  "rejected_alternatives": [
    {"option": "<a class you considered>", "why_not": "what rules it out"}
  ],
  "siblings_considered": [
    {"of": "<a class you proposed>", "sibling": "<one of its siblings>",
     "why_not": "what rules the sibling out for this case"}
  ],
  "citations": ["<an identifier you inspected>", "Modelling principles > Minimality",
                "t0408", {"id": "t0408", "quote": "a phrase you verified with quote"}],
  "in_scope": true,
  "queries_run": ["ontology", "concept <id>", "docs \"<query>\"", "connect <A> <B>"],
  "confidence": "high | medium | low",
  "notes": "anything the tools made hard"
}
```

- `in_scope`: `false` if the honest answer is that this is outside the model.
- `citations`: only things you actually saw in tool output. Plain strings are
  checked for existence; use the `{"id": ..., "quote": ...}` form for any
  citation that includes a direct quotation, so containment gets checked too —
  but only after `search.py quote` has already returned FOUND.
- `queries_run`: every query in order, including the ones that failed. Do not
  tidy it up.
- `siblings_considered`: one entry per class in `classes_proposed` that has
  siblings. Checked mechanically; an entry naming a class that is not actually
  a sibling does not count.
