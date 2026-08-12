# tools/

Scripts that build the corpus, exercise the server, and score the
evaluations. None of them is imported by `lib/`, `search.py` or
`mcp_server.py` — they are run by hand.

This file exists because several of these look abandoned and are not. A
reviewer reading the directory concluded that four of the `eval_*.py`
scripts were "orphaned post-processors from the retrieval-eval era" and
suggested pruning them. They are in fact the only readers of the evaluation
data in `data/eval/`, which `.gitignore` deliberately tracks — everything
else under `data/` is generated and ignored — on the grounds recorded there:

> the questions were written by readers who were blind to the search system,
> and regenerating them would produce a different benchmark, so scores would
> stop being comparable across runs.

Deleting the scripts would leave ~250 tracked, non-regenerable files with
nothing able to read them. The problem was that nothing said so. So: what
each script is for, and what it reads.

## Calling the server

| script | what it does |
|---|---|
| `mcp_call.py` | One call to the MCP server over stdio, printed. `--list` shows every tool and its parameters. The quickest way to see whether the archive layer registered on a given checkout. |

## Building the corpus

Each fetches something from `cidoc-crm.org` into a tracked JSON file that
`build.py` then consumes. Run when the upstream source changes, not on every
build — they hit the network.

| script | writes |
|---|---|
| `fetch_crm_family.py` | `sources/crm_family.json` — the family extension declarations |
| `fetch_crm_issues.py` | `sources/crm_issues.json` — the SIG issue register |
| `fetch_issue_pages.py` | `data/issue_pages/` — one page per issue |
| `fetch_minutes.py` | `data/minutes/` — SIG meeting minutes |

## Reading and rendering

| script | reads |
|---|---|
| `read_thread.py` | a mailing-list thread, for reading outside the CLI |
| `render_crm_models.py` | the tracked `models/crm_*.xml` → `crm_models_review.html` (git-ignored; regenerate rather than commit) |
| `make_review_html.py` | the modelling evaluation → a standalone human review sheet |

## Scoring an evaluation

These are the ones that look orphaned. Each reads tracked files under
`data/eval/`; the counts are what was there when this file was written.

| script | reads | tracked |
|---|---|---|
| `eval_report.py` | `authored-*.json`, `answer-*.json`, `judged-*.json` | 44 |
| `eval_run6_report.py` | `manswer6a-*.json`, `manswer6b-*.json` | 36 |
| `eval_rank_report.py` | `mrank6-*.json` and a blind key | 18 |
| `eval_novelty.py` | `modelling_cases.json`, plus `documents.jsonl` and `clean.jsonl` | — |
| `eval_citations.py` | an answer's citations, checked against the corpus | — |
| `eval_quotes.py` | an answer's quotations, checked against the real sources | — |
| `eval_domains.py` | a produced answer's property/class pairings | — |
| `eval_siblings.py` | whether an answer engaged with the nearest rival class | — |

`eval_run6_report.py` names a specific run and is the most one-off of them,
but run 6 is exactly the paired-sampling run whose results are quoted in the
project's notes about the evaluation noise floor, and its inputs are
tracked. `eval_novelty.py` is not a post-processor at all: it screens
candidate modelling cases against the corpus they are meant to test, which
is the check that was skipped — twice — when cases turned out to be worked
examples already present in the specification.

The `EVAL_*.md` and `RATIONALE_*.md` files beside them are the briefs the
evaluations were run with. They are prompts, not documentation, and are
tracked so a past run can be reproduced or its wording audited.
