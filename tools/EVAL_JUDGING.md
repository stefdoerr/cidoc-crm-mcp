# Judging evaluation answers

You are grading answers produced by an archive search system against gold
answers written independently by someone who read the source threads directly.

You will be given, for each question: the question, the gold answer, the gold
`key_facts`, and the produced answer. **You do not get the archive.** Judge
only whether the produced answer is consistent with the gold.

## Verdicts

- **`correct`** — every gold key fact is present or clearly entailed, and
  nothing material contradicts the gold.
- **`partial`** — some key facts present, others missing; nothing contradicts
  the gold. An answer that gets the direction right but omits the reasoning is
  `partial`, not `correct`.
- **`wrong`** — contradicts the gold, or misses the substance of the question.
- **`not_found`** — the system said it could not find the answer. This is an
  honest failure and must be scored separately from `wrong`, never merged
  with it.
- **`hallucinated`** — the answer is confident and specific but contradicts the
  gold, or asserts specifics the gold does not support. **This is the most
  important verdict to get right.** A system that fabricates a plausible
  resolution is more dangerous than one that finds nothing, because the reader
  cannot tell the difference without already knowing the answer.

## Rules

1. **Wording does not matter; substance does.** Different phrasing, ordering,
   or level of detail is fine. Do not reward an answer for echoing the gold's
   vocabulary.

2. **Do not use your own CIDOC CRM knowledge.** If you happen to know the
   produced answer is true of the real ontology but the gold says the archive
   concluded otherwise, the gold wins — the question is what *this archive*
   records, and the archive sometimes contradicts the published standard.

3. **"Never resolved" is a real answer.** If the gold says the debate was left
   open and the produced answer invents a resolution, that is `hallucinated`,
   not `partial`. If the gold says it was resolved and the produced answer says
   it was left open, that is `wrong`.

4. **Judge the answer, not the effort.** A long answer citing many threads that
   misses the key facts is `partial` or `wrong`. Running many queries earns
   nothing.

5. **Be strict.** This evaluation exists to find weaknesses. Grading generously
   produces a flattering number and tells us nothing. When genuinely torn
   between two verdicts, choose the harsher one and say why in `reasoning`.

## Output

Write a JSON list to the path you are given, one object per question:

```json
[
  {
    "question_id": "2009-2011-q1",
    "verdict": "correct | partial | wrong | not_found | hallucinated",
    "facts_hit": 2,
    "facts_total": 3,
    "reasoning": "One or two sentences. Name the specific fact that was missing, contradicted or invented.",
    "missing_or_wrong": ["the key fact that was absent or contradicted"]
  }
]
```

Include every question you were given, in the order given.
