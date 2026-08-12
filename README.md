# cidoc-crm-mcp

CIDOC CRM modelling tools: ontology lookup, model validation against four RDF
syntaxes plus the specification's own example XML, and 26 years of CRM-SIG
mailing-list discussion, over MCP. `search.py` is the same functionality as
a CLI; `mcp_server.py` is the long-lived, in-process form so an assistant
pays the ontology/embedding load cost once per session instead of once per
call.

## Layout

    build.py search.py mcp_server.py    the three entry points
    lib/ontology/                       the model: parsing, graph queries, URIs, validation
    lib/                                retrieval, indexing, corpus building
    sources/                            vendored upstream, tracked and never edited by hand
      cidoc_crm_v7.1.3.xml                the specification's presentation XML
      cidoc_crm_v7.1.3.rdf                CIDOC's normative RDFS encoding
      rdfs/extensions/                    the eleven family models' own RDFS
      crm_family.json crm_issues.json     scraped declarations and the issue register
      *.docx                              the 7.3.2 text and the Modelling Principles
    models/                             eight worked examples, with the notes from writing them
    prompts/                            the MCP prompts, as files -- editable without a rebuild
    data/                               generated, gitignored, except data/eval/
    tools/                              see tools/README.md
    Dockerfile docker-compose.yml       the everything-included image

`sources/` is upstream material: refreshed by the `tools/fetch_*.py` scripts
or by hand from cidoc-crm.org, and otherwise left alone. `models/` is output
this repository produced — the notes beside each model record what the
validator caught while it was being written, which is why they are tracked
next to it rather than thrown away.

## Install

### Docker: everything, always warm

```
docker run -d -p 127.0.0.1:8000:8000 ghcr.io/stefdoerr/cidoc-crm-mcp:latest
```

No clone, no build, no corpus fetch, no `uv`. Point a client at
`http://127.0.0.1:8000/mcp` and nothing else -- no project path, no venv.

One image with the ontology, the full archive, the FTS indexes, the vector
stores and the embedding model baked in: nothing to fetch, no volume, no
network at runtime. Measured on the published image:

| | |
|---|---|
| pull | ~1.3GB (≈2.8GB unpacked) |
| ready | ~21s from `docker run` to healthy |
| first search | already warm -- `--warm` loads all three vector stores before the port opens |
| warm query | 0.1-0.2s over HTTP |
| memory | ~1.0GB warm (0.52GB process, the rest page cache for the mmap'd indexes) |

`torch` is the CPU wheel. The default PyPI build on linux/amd64 is the CUDA
one and drags in 3.4GB of `nvidia/*` and `triton` for a container with no
GPU; nothing is lost by dropping it, because CPU vector search measures
50-90ms warm.

**Improving the prompt without rebuilding.** `prompts/model_an_object.md` is
the modelling prompt, and it is a file rather than a string in the source
for this reason. Mount a directory at `/prompts` and any
`model_an_object.md` in it wins; it is re-read on every request, so an edit
takes effect on the next call with no restart and no rebuild:

```
docker run -d -p 127.0.0.1:8000:8000 \
  -v "$PWD/prompts:/prompts:ro" ghcr.io/stefdoerr/cidoc-crm-mcp:latest
```

**What corpus is inside.** This image carries data as well as code, and the
data is the part that silently changes what a search returns:

```
docker run --rm ghcr.io/stefdoerr/cidoc-crm-mcp:latest cat /app/corpus-provenance.json
```

**There is no authentication.** Bind the published port to loopback, as
above. Put a reverse proxy with a token in front before exposing it.

To build it yourself instead -- `docker compose up -d --build`. That
downloads ~1.4GB of wheels, the 876MB corpus and the model, and takes the
better part of an hour.

### Or locally

```
uv sync --no-dev
```

Core only: `pyyaml`, `rdflib`, `mcp`, `huggingface_hub`. Enough to look up a
concept, validate a model, run the MCP server's ontology tools, and fetch
the archive for full-text search -- no `torch`, no `langchain`.

```
uv sync --no-dev --extra archive
```

Adds *vector* retrieval over the SIG archive (`langchain-*`,
`sentence-transformers`, `transformers`, `anthropic`). Only needed for
hybrid and vector search; BM25 over the whole archive works without it.

Plain `uv sync`, with no flags, also works but installs more than either
command above: `dev` is uv's default dependency group, and this project's
`dev` group deliberately pulls in both `archive` and `ingest` plus
`pytest`/`pytest-asyncio`, so that `uv run pytest -q` always has everything
the suite needs. Pass `--no-dev` on later `uv run` invocations too, or the
first one quietly re-syncs the dev group and its extras back in.

## Build the ontology

```
uv run python build.py ontology
```

Required before first use: `data/` is gitignored, and the ontology tools
read `data/ontology.json`, which this generates from the vendored RDF/XML
(`sources/cidoc_crm_v7.1.3.xml`, `sources/cidoc_crm_v7.1.3.rdf`,
`sources/rdfs/extensions/`) and the family identifier collection
(`sources/crm_family.json`), all tracked in the repo.

The stage also reads `data/clean.jsonl` and `data/documents.jsonl` if they
are already on disk and silently skips them if not, which makes order
matter: fetch the archive first (next section) and build the ontology
after, and everything the corpus contributes is folded in; the other way
round leaves it out until this stage is re-run.

## The archive half

`data/` and `stores/` are git-ignored: ~876MB of derived artifacts, built
from a 143MB mailing-list mbox distributed separately. Without them you have
the six ontology tools and none of the six archive tools. Fetch them from
[the dataset repo](https://huggingface.co/datasets/stefdoerr/cidoc-crm-corpus).

There are two ways to have the archive, and they differ by about 6GB.

### Full text search only — no torch

```
uv sync --no-dev
uv run --no-dev python build.py fetch --no-vectors
uv run --no-dev python build.py ontology
```

BM25 over all 26 years, and all twelve MCP tools register. Verified from a
clean clone: 46 packages, no torch, 95MB fetched, first search answers in
about a second.

`crm_search` and `crm_docs` take a `mode` argument. The default is `hybrid`,
which needs vectors, so pass `mode: "bm25"`. If you forget, the error says
so rather than reporting a missing Python module:

    vector search needs the `archive` extra, which is not installed:
    uv sync --extra archive. To search without it, pass mode="bm25" --
    BM25 covers the whole archive and needs no embedding model.

### With vector search

```
uv sync --no-dev --extra archive
uv run --no-dev python build.py fetch
uv run --no-dev python build.py ontology
```

Then, on the first vector or hybrid query only, an embedding model is
downloaded automatically.

What that costs, measured rather than estimated:

| | |
|---|---|
| packages | 141, of which `torch` alone is 1.1GB |
| virtualenv on disk | ~5.2GB |
| corpus fetched | 876MB (`data/` 56MB, `stores/` 824MB) |
| embedding model, downloaded on first query | 288MB, cached in `~/.cache/huggingface` |
| first query | ~12s while the model loads |
| every query after | ~0.02s |
| resident memory once loaded | ~1.9GB |

Roughly 6GB of disk and a few minutes of setup, in exchange for semantic
search. The model is not chosen by you: each store records the model it was
embedded with in `stores/*/meta.json`, and querying with a different one
returns confident nonsense, so the fetched store decides it.

### Which to pick

BM25 is genuinely good on this corpus, because CRM discussion is full of
exact identifiers — `P2`, `E55`, `S19` — and that is what BM25 matches best
and an embedding model handles worst (it splits `E55` into a semantically
empty `E` and `55`). The vectors earn their place on conceptual questions
where the wording differs from the query, which is why the default is
hybrid: the two are fused, not alternatives.

Start with `--no-vectors`. Adding them later is `uv sync --no-dev --extra
archive` and `build.py fetch` again; nothing already fetched is
re-downloaded.

### Publishing a rebuilt corpus

`tools/publish_corpus.py` uploads to a Hugging Face dataset repo
(`huggingface-cli login` first, `--dry-run` to see what would go).

## As an MCP server

```json
{
  "mcpServers": {
    "cidoc-crm": {
      "command": "uv",
      "args": ["run", "python", "mcp_server.py"],
      "cwd": "/path/to/cidoc-crm-mcp"
    }
  }
}
```

Talks JSON-RPC over stdio; every diagnostic (which layer registered, which
file was missing) goes to stderr, never stdout.

## Two tool layers

**Ontology layer** -- `crm_concept`, `crm_list`, `crm_connect`,
`crm_validate_link`, `crm_validate_rdf`, `crm_validate_xml`. Always
registered. Needs only `data/ontology.json`, so it works after the build
step above with the core install alone.

**Archive layer** -- `crm_search`, `crm_show`, `crm_thread`, `crm_docs`,
`crm_quote`, `crm_issue`. Needs `data/clean.jsonl`, `data/threads.json` and
`data/documents.jsonl`, built from the 143MB CRM-SIG mailing-list archive
(`crm-sig.mbox`), which is shipped out of band and is not in this repo;
`build.py fetch` delivers all three ready-made.
Without that data these six tools simply do not appear in the tool list --
not advertised and failing, just absent -- and the server names the first
missing file on stderr at startup.

## Scope: the ontology knows what was on disk when it was built

`historical` (deprecated ids the current specification no longer defines,
known only because the archive debated their removal) and the three 7.3.2
spec-only additions (`E100`, `P199`, `P200`, present in the 7.3.2
declarations but not yet in the 7.1.3 XML) both come from the corpus: the
historical bucket is mined from `data/clean.jsonl`, the spec additions
read from `data/documents.jsonl`. Both files arrive with `build.py fetch`;
the mbox and the 7.3.2 docx are needed only to rebuild them from source,
via `build.py clean` and `build.py docs`.

Running only `build.py ontology`, with nothing fetched, therefore gets
CRMbase (82 classes, 166 properties) plus the 7 identifiers only the
normative RDFS declares (`P81a`/`P81b`/`P82a`/`P82b`, `P90a`/`P90b`,
`E33_E41`) plus the 533 declared family-model identifiers across
CRMarchaeo, CRMdig, CRMinf, CRMsci, CRMtex, CRMgeo, CRMact, CRMba, FRBRoo,
LRMoo and PRESSoo -- and not the 59 historical ids or the 77 archive-only
family identifiers (real, SIG-discussed, but never formally declared).
Fetching first and building after, as the steps above do, carries all of
them: parity with the maintainer's build needs no mbox. An ontology built
before the corpus arrived stays a strict subset until `build.py ontology`
is re-run.
