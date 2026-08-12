#!/usr/bin/env python3
"""Upload the built corpus to a Hugging Face dataset repo.

    uv run python tools/publish_corpus.py --repo stefdoerr/cidoc-crm-corpus
    uv run python tools/publish_corpus.py --repo ... --dry-run

`data/` and `stores/` are git-ignored: they are ~876MB of derived artifacts,
and the 143MB mailing-list mbox they come from is shipped out of band. So a
clone can build the ontology from the tracked sources in `sources/` and gets
the six ontology tools, and cannot build the archive at all -- no
`clean.jsonl`, so no FTS index, no vector store, and none of the six archive
tools. That is the half with no substitute: anyone can rebuild domain and
range checking from the published RDFS, and nobody else has the SIG's
argument indexed.

This publishes the derived artifacts so they can. `build.py fetch` is the
other end.

Uploaded as a folder rather than a tarball on purpose. It resumes, it syncs
incrementally when only part of the corpus is rebuilt, and it lets a fetcher
take 91MB of text and full-text indexes without the 824MB of
vectors -- which is
the whole difference between needing torch and not.

Requires authentication: `huggingface-cli login`, or HF_TOKEN in the
environment. Nothing here reads a credential from the repository.
"""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Exactly what the running server opens, and nothing else. `lib/retrieve.py`
# is the whole runtime and it reads six paths under data/ plus stores/; the
# first publish also carried data/minutes/, data/issue_pages/ and
# data/minutes_issues.json, which are build-time INPUTS that `build.py docs`
# chunks into documents.jsonl and that nothing opens afterwards.
#
# 93MB of 970 -- but 786 files of 901, so most of the upload time went on
# material a consumer cannot use. `crm_docs --kind minutes` and `--kind
# issue` still work: those chunks live in documents.jsonl.
#
# data/eval/ is absent because git already carries it (tracked precisely
# because it is not regenerable, so a second copy could drift), and
# data/ontology.json because it is rebuilt from tracked sources/ in seconds
# and a downloaded copy could silently shadow the inputs it derives from.
PAYLOAD = [
    "data/clean.jsonl",
    "data/documents.jsonl",
    "data/episodes.jsonl",
    "data/issues.json",
    "data/threads.json",
    "stores",
]

CARD = """\
---
license: other
task_categories: [text-retrieval]
language: [en]
tags: [cidoc-crm, cultural-heritage, ontology, mailing-list]
---

# CIDOC CRM SIG corpus — derived artifacts

The built corpus for [cidoc-crm-mcp](https://github.com/stefdoerr/cidoc-crm-mcp):
26 years of CIDOC CRM Special Interest Group mailing list, its issue
register and meeting minutes, cleaned, threaded, and indexed for BM25 and
vector search.

These are **derived artifacts**, not the source. They exist because the code
repository cannot carry them: ~876MB, git-ignored, rebuilt from a 143MB mbox
that is distributed separately.

## Fetching

    uv run python build.py fetch                 # everything
    uv run python build.py fetch --no-vectors    # 91MB, skips the vectors

Without the vectors you still get full-text search over the whole archive
and you do not need torch or an embedding model.

## Contents

| path | what |
|---|---|
| `data/clean.jsonl` | every message, cleaned, with extracted CRM identifiers |
| `data/threads.json` | messages grouped into threads |
| `data/documents.jsonl` | the specification, issue pages and minutes, chunked ready to search |
| `data/episodes.jsonl` | summarised decision episodes |
| `data/issues.json` | the SIG issue register |
| `stores/*/fts.sqlite3` | SQLite FTS5 indexes (BM25) |
| `stores/*/chroma.sqlite3` and friends | vector indexes |
| `stores/*/meta.json` | which embedding model built each store, and the sha256 of its source |

## Provenance

Each vector store records the embedding model it was built with and a
`source_sha256` of the input it was built from. `build.py fetch` checks
these, because a store embedded with one model and queried with another
returns confident nonsense.

## Licence

The mailing list is published by the CIDOC CRM SIG; posts remain their
authors'. This is a derived index redistributed for research use. Contact
the SIG for reuse beyond that.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--repo", required=True,
                        help="dataset repo id, e.g. you/cidoc-crm-corpus")
    parser.add_argument("--private", action="store_true",
                        help="create it private (default public)")
    parser.add_argument("--dry-run", action="store_true",
                        help="list what would be uploaded, and stop")
    args = parser.parse_args()

    missing = [p for p in PAYLOAD if not (ROOT / p).exists()]
    if missing:
        raise SystemExit(
            "not built yet, nothing to publish:\n  "
            + "\n  ".join(missing)
            + "\n\nRun the pipeline first (build.py clean/thread/docs/issues/index)."
        )

    total = 0
    for rel in PAYLOAD:
        path = ROOT / rel
        files = [path] if path.is_file() else [f for f in path.rglob("*") if f.is_file()]
        size = sum(f.stat().st_size for f in files)
        total += size
        print(f"  {size / 1048576:8.1f} MB  {len(files):5} file(s)  {rel}")
    print(f"  {total / 1048576:8.1f} MB  total")

    if args.dry_run:
        print("\n--dry-run: nothing uploaded.")
        return

    from huggingface_hub import HfApi

    api = HfApi()
    try:
        who = api.whoami()["name"]
    except Exception:
        raise SystemExit(
            "not authenticated. Run `huggingface-cli login`, or set HF_TOKEN."
        )
    print(f"\nuploading as {who} to {args.repo}")

    api.create_repo(args.repo, repo_type="dataset",
                    private=args.private, exist_ok=True)
    (ROOT / ".corpus-README.md").write_text(CARD, encoding="utf-8")
    api.upload_file(path_or_fileobj=str(ROOT / ".corpus-README.md"),
                    path_in_repo="README.md", repo_id=args.repo,
                    repo_type="dataset")
    (ROOT / ".corpus-README.md").unlink()

    for rel in PAYLOAD:
        path = ROOT / rel
        print(f"  uploading {rel} ...", flush=True)
        if path.is_file():
            api.upload_file(path_or_fileobj=str(path), path_in_repo=rel,
                            repo_id=args.repo, repo_type="dataset")
        else:
            api.upload_folder(folder_path=str(path), path_in_repo=rel,
                              repo_id=args.repo, repo_type="dataset")
    print(f"\ndone: https://huggingface.co/datasets/{args.repo}")


if __name__ == "__main__":
    main()
