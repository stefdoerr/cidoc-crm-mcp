# cidoc-crm-mcp

CIDOC CRM as twelve tools an assistant can call, so a collection can be
converted to CRM and *checked* rather than trusted: settle the mapping
against the specification instead of from memory, write it with the
identifiers the standard actually uses, then validate the whole export —
every triple, not a sample. Measured on this build, a 10,000-object export
is 30,000 links checked in eight seconds.

The same tools answer the everyday questions one at a time — what does this
class mean, can this property join these two, is what I wrote legal — and
behind them sits 26 years of CRM-SIG mailing-list discussion for the ones the
specification does not settle.

Twelve tools in two layers. The ontology half answers from the normative
RDFS; the archive half quotes people arguing, including people who turned
out to be wrong, and its value is that it says who and when. The tools keep
the two apart rather than blending them into one confident answer.

**[docs/cidoc-crm-mcp-introduction.pdf](docs/cidoc-crm-mcp-introduction.pdf)**
is the place to start if you model in CIDOC CRM and have never had to care
what an MCP server is: eight pages on what this is, how you use it (your
assistant consults it; you do not), what is inside, and what not to trust it
for. Rebuild it with `uv run python tools/make_pdf.py docs/introduction.html`
after editing [docs/introduction.html](docs/introduction.html).

**[docs/how-it-works.html](docs/how-it-works.html)** is the guide: what each
of the twelve tools answers, a real question worked through, where the
material comes from, and what not to trust it for. It is a standalone page —
open it in a browser from a clone, as GitHub shows HTML as source rather
than rendering it.

## Run it

There is a hosted instance at `https://cidoc.stefdoerr.com/mcp`. It needs an
access token, sent out by mail; with one, connecting takes a line and nothing
is installed locally:

```
claude mcp add --transport http cidoc-crm https://cidoc.stefdoerr.com/mcp \
  --header "Authorization: Bearer YOUR_TOKEN_HERE"
```

The token is shared across everyone testing and is the only thing standing in
front of the archive, so keep it out of repositories, issues and screenshots.

To run your own instead — no token, because loopback is the protection:

```
docker run -d -p 127.0.0.1:8000:8000 ghcr.io/stefdoerr/cidoc-crm-mcp:latest
```

Then point a client at `http://127.0.0.1:8000/mcp` and nothing else — no
project path, no venv:

```json
{
  "mcpServers": {
    "cidoc-crm": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

In Claude Code, `claude mcp add --transport http cidoc-crm
http://127.0.0.1:8000/mcp` does the same thing.

**There is no authentication in it.** Keep the published port on loopback,
as above: anyone who can reach it can search the whole archive. Put a
reverse proxy with a token in front before that changes.

**The modelling prompt is a file, not a string in the source** — it is
advice, and advice gets better by being argued with. Mount a directory at
`/prompts` and any `model_an_object.md` in it wins. It is re-read on every
request, so an edit takes effect on the next call, with no restart and no
rebuild:

```
docker run -d -p 127.0.0.1:8000:8000 \
  -v "$PWD/prompts:/prompts:ro" ghcr.io/stefdoerr/cidoc-crm-mcp:latest
```

**Which corpus is inside.** The image carries data as well as code, and the
data is the part that silently changes what a search returns:

```
docker run --rm ghcr.io/stefdoerr/cidoc-crm-mcp:latest cat /app/corpus-provenance.json
```

## Development

Only needed to change the code. Using the tools needs nothing in this
section.

```
git clone https://github.com/stefdoerr/cidoc-crm-mcp
cd cidoc-crm-mcp
uv sync
uv run python build.py fetch      # ~876MB: the archive, its indexes, the vector stores
uv run python build.py ontology   # data/ontology.json, from the tracked RDF
uv run pytest -q
```

Fetch before building the ontology. The ontology stage folds in whatever the
corpus contributes and silently skips it when absent, so the other order
leaves material out until that stage is run again.

`data/` and `stores/` are git-ignored and come ready-built from [the corpus
dataset](https://huggingface.co/datasets/stefdoerr/cidoc-crm-corpus), not
from the 143MB mbox. For the archive without `torch` — BM25 over all 26
years, some 6GB less on disk — use `uv sync --no-dev` with `build.py fetch
--no-vectors`, and pass `mode: "bm25"` to the search tools.

Entry points: `build.py` builds, `search.py` is the same functionality as a
CLI, `mcp_server.py` is the server. Helper scripts live in `tools/` and are
listed in [tools/README.md](tools/README.md).

Against a checkout the server talks stdio, so a client needs a path rather
than a URL:

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

`docker compose up -d --build` builds the image from the checkout instead of
pulling it: ~1.4GB of wheels, the corpus and the model, and the better part
of an hour.

To publish an image, push a `v*` tag or run the *publish image* workflow and
give it a version; either produces `:x.y.z`, `:x.y` and `:latest` for amd64
and arm64. Note that a newly created GHCR package is private, and CI's smoke
test pulls with a token — so it passes while anonymous users still get a
403. After the first publish, make the package public once, by hand.
