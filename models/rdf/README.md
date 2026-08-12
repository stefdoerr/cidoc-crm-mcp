# Eight CRM models in Turtle, and when they were made

Each `crm_*.ttl` here was written by an agent that had **only the MCP server**
to answer questions about the CIDOC CRM — no access to `data/ontology.json`,
the vendored RDFS, `lib/`, `search.py`, or the XML models in `../`. The facts
came from a cached plain-text extract of the object's Wikipedia article. The
`-notes.md` beside each model is that agent's own report: what the server told
it that changed the model, what it wanted to ask and could not, and its blunt
assessment of the tools.

All eight validate clean:

    uv run python search.py validate --rdf models/rdf/crm_bayeux.ttl

Every `not_crm` finding in them is `rdfs:label` or `rdfs:comment`. None
invented a CRM predicate or mistyped a class.

## Provenance — these are snapshots, not current output

All eight were produced in one batch, from one brief, against the tree at
`7448db3`. That is deliberate: the previous set was three different tool
versions and could not be compared with itself.

One contamination to know about. At the time of this run, `crm_thread`'s
description illustrated itself with a worked example -- a 2013 SIG thread
deciding `S19 Encounter Event` for a find. `crm_maogong` chose `S19` for its
excavation and its notes say the description pointed it there, so that one
decision is not independent evidence. The description was corrected in
`f71a267` to state the principle and name no class, and a test now stops the
leak returning. The other seven models do not cite it.

They also predate `f71a267`'s second fix, which quieted the traceback rdflib
prints for a BCE date. `crm_maogong`'s notes describe removing a date
because of it -- the file validated fine either way; the traceback was
cosmetic.

**What this means in practice.** The Turtle is good: every file was
re-validated from its committed path after installation, all eight exit 0,
and every `not_crm` finding is `rdfs:label` or `rdfs:comment`. The notes are
a record of one day's tooling. Do not quote a call count or a tool complaint
from a `-notes.md` as a statement about the server today.

## What changed against the previous set

Same subjects, same cached articles, a server with the URI line, local names
in `crm_list`, the corrected incoming-property direction, and the archive
fixes:

    total CRM links   888
    total MCP calls   189, from 325 -- 42% fewer

Content is roughly flat and cost fell sharply where it was worst. The two
runs that had burned 69 and 85 calls looking identifiers up one at a time --
`crm_concept` per identifier, purely for spelling -- now use 18 and 27,
because `crm_list` prints the RDF local name for a whole model in one call.

## Sizes and shapes

| model | links | CRM links | classes | properties | MCP calls |
|---|---|---|---|---|---|
| `crm_bayeux` | 227 | 156 | 22 | 41 | 24 |
| `crm_dayuding` | 220 | 144 | 23 | 32 | 35 |
| `crm_uffington` | 186 | 126 | 16 | 30 | 18 |
| `crm_suttonhoo` | 152 | 104 | 15 | 28 | 25 |
| `crm_maogong` | 150 | 94 | 19 | 29 | 19 |
| `crm_houmuwu` | 144 | 96 | 18 | 33 | 24 |
| `crm_marquisyi` | 132 | 91 | 11 | 21 | 17 |
| `crm_shiqiang` | 122 | 77 | 19 | 30 | 27 |

`links` counts every triple the reader extracts, including `rdfs:label`;
`CRM links` counts only those whose predicate is a CRM property.

## What they are not

These were written from encyclopedia summaries, so their factual depth is
bounded by those articles — a museum record would support far more. The
open questions are modelling judgement, not legality: whether `E12
Production` is the right frame for cutting a chalk hill figure, whether a
burial deposition is better as CRMsci `S19 Encounter Event` or something in
CRMarchaeo. The validator has already answered everything it can answer.
