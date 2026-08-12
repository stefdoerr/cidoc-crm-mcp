#!/usr/bin/env python3
# build.py
"""Pipeline stage runner.

Usage:
    uv run python build.py ontology
    uv run python build.py clean [--audit N] [--limit N]
    uv run python build.py thread
    uv run python build.py index
    uv run python build.py docs
    uv run python build.py issues
"""

import argparse
import json
import random

from lib.config import DATA_DIR, PROJECT_ROOT, load_config
from lib.ontology import (add_extensions, add_family_rdfs, add_historical,
                          add_rdfs_additions, add_spec_additions, load_family,
                          parse_ontology)


def _load_ontology(cfg: dict) -> dict:
    return parse_ontology(PROJECT_ROOT / cfg["ontology"]["xml"])


def stage_ontology(cfg: dict) -> None:
    onto = _load_ontology(cfg)
    mentions: dict[str, int] = {}
    candidates: dict[str, int] = {}
    clean_path = DATA_DIR / "clean.jsonl"
    if clean_path.exists():
        import re

        pattern = re.compile(cfg["ontology"]["id_pattern"])
        # Deliberately broad: any uppercase prefix followed by digits. The
        # family collection and family_of() decide which candidates are real,
        # so the sieve need not be clever.
        family_pattern = re.compile(cfg["ontology"]["family_pattern"])
        with open(clean_path, encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                text = f"{rec.get('subject') or ''}\n{rec['body']}"
                for match in pattern.finditer(text):
                    ident = match.group(1)
                    mentions[ident] = mentions.get(ident, 0) + 1
                for match in family_pattern.finditer(text):
                    ident = match.group(1).upper()
                    candidates[ident] = candidates.get(ident, 0) + 1
        add_historical(onto, mentions)

    # Outside the clean.jsonl guard, unlike add_historical above. The family
    # declarations are a tracked file; the archive only supplies mention
    # counts and the handful of ids that appear in discussion but in no
    # declaration. Gating the whole call on the archive meant a checkout
    # without the out-of-band 143MB mbox got CRMbase and nothing else -- so
    # every CRMsci, CRMarchaeo and LRMoo term in a document validated as
    # `not_crm` and passed. `candidates` is empty in that case, which the
    # union inside add_extensions handles.
    family = (
        load_family(PROJECT_ROOT / cfg["ontology"]["family"])
        if cfg["ontology"].get("family")
        else {}
    )
    add_extensions(onto, candidates, family)

    # The declaration pages CRMact, CRMba, FRBRoo and PRESSoo were scraped
    # from carry no URI, so `_owned_namespaces` -- which is built from `uri`
    # fields -- did not know their namespaces existed, and a misspelling
    # under one came back `not_crm` and exited 0 while the same mistake in
    # CRMsci exited 1. Their own RDFS files carry the real URIs, and the
    # namespaces are not guessable: PRESSoo's is
    # http://www.iflastandards.info/fr/pressoo/, a different host and path
    # from LRMoo's http://iflastandards.info/ns/lrm/lrmoo/.
    rdfs_dir = PROJECT_ROOT / "sources" / "rdfs" / "extensions"
    if rdfs_dir.is_dir():
        report = add_family_rdfs(onto, sorted(rdfs_dir.iterdir()))
        filled = sum(r["uris_filled"] for r in report.values())
        gained = sorted(i for r in report.values() for i in r["added"])
        print(f"[ontology] family RDFS: {len(report)} models, "
              f"{filled} URI(s) filled in, {len(gained)} id(s) added"
              + (f": {' '.join(gained[:8])}"
                 + (" ..." if len(gained) > 8 else "") if gained else ""))

    # The declarations corpus is v7.3.2 and the XML is v7.1.3, so 7.3.2's
    # additions (E100, P199, P200) exist in one and not the other. Folded in
    # AFTER add_historical, which would otherwise have swept them into the
    # deprecated bucket and made `concept P200` report a new property as one
    # the standard removed.
    #
    # Read only if documents.jsonl is already built -- `docs` reads
    # ontology.json, so this stage cannot depend on that one running first.
    # Rebuilding `ontology` after `docs` completes the picture, and doing it
    # in the other order simply leaves these three out, exactly as the
    # clean.jsonl guard above leaves the mention counts out.
    docs_path = DATA_DIR / "documents.jsonl"
    if docs_path.exists():
        declarations = {}
        with open(docs_path, encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("kind") == "declaration" and rec.get("concept_id"):
                    declarations[rec["concept_id"]] = rec
        added = add_spec_additions(onto, declarations)
        if added:
            print(f"[ontology] {len(added)} concept(s) from the newer "
                  f"specification, absent from the XML: {' '.join(added)}")

    # The presentation XML synthesizes URIs from labels; real CRM RDF is
    # written against CIDOC's normative RDFS encoding, which carries
    # constructs the XML has no entry for at all -- P81a/P81b/P82a/P82b (a
    # fuzzy date boundary) and P90a/P90b (a fuzzy dimension bound), the
    # standard way essentially every real CRM dataset writes a time-span.
    # Folded in AFTER add_historical for the same reason the spec additions
    # above are: add_historical sweeps every archive-mentioned identifier
    # the XML does not define into the deprecated bucket, so anything
    # folded in before it would be reported as a concept the standard
    # removed instead of one it never had a presentation-format entry for.
    #
    # Unlike the spec additions above, this has no documents.jsonl
    # precondition -- the RDFS is vendored at the repository root
    # (cidoc_crm_v7.1.3.rdf) and is therefore always available, so it
    # always runs, independent of which stages have already built.
    rdfs_added = add_rdfs_additions(onto, PROJECT_ROOT / "sources" / "cidoc_crm_v7.1.3.rdf")
    if rdfs_added:
        print(f"[ontology] {len(rdfs_added)} identifier(s) from the "
              f"normative RDFS, absent from the XML: {' '.join(rdfs_added)}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / "ontology.json"
    out.write_text(json.dumps(onto, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[ontology] v{onto['version']}: {len(onto['classes'])} classes, "
          f"{len(onto['properties'])} properties, {len(onto['historical'])} historical, "
          f"{len(onto['property_of_property'])} property-of-property")
    if onto["extensions"]:
        declared = sum(1 for v in onto["extensions"].values() if v["status"] == "current")
        models = sorted({v["model"] for v in onto["extensions"].values()})
        print(f"[ontology] {len(onto['extensions'])} family ids "
              f"({declared} declared, {len(onto['extensions']) - declared} archive-only) "
              f"across {len(models)} models: {', '.join(models)}")
    print(f"[ontology] wrote {out}")


def stage_clean(cfg: dict, audit: int, limit: int | None) -> None:
    from lib.clean import run_clean

    onto = _load_ontology(cfg)
    stats = run_clean(cfg, onto, limit=limit)

    print(f"[clean] messages:    {stats['messages']:,}")
    print(f"[clean] duplicates:  {stats['duplicates_skipped']:,} skipped (same Message-ID)")
    print(f"[clean] raw chars:   {stats['raw_chars']:,}")
    print(f"[clean] clean chars: {stats['clean_chars']:,} "
          f"({stats['reduction_pct']:.1f}% reduction)")
    print("[clean] rules fired:")
    for rule, count in sorted(stats["counters"].items()):
        print(f"          {rule:22s} {count:>7,}")

    if audit:
        # Primary defence against a silently over-aggressive rule.
        records = [json.loads(ln) for ln in open(DATA_DIR / "clean.jsonl", encoding="utf-8")]
        rng = random.Random(0)  # deterministic sample so reruns are comparable
        for rec in rng.sample(records, min(audit, len(records))):
            print("\n" + "=" * 70)
            print(f"{rec['message_id']}  {rec['date']}  {rec['subject'][:60]}")
            print(f"rules: {  {k: v for k, v in rec['stripped'].items() if v} }")
            print("-" * 30, "RAW", "-" * 30)
            print(rec["body_raw"][:800])
            print("-" * 29, "CLEAN", "-" * 29)
            print(rec["body"][:800])


def stage_thread(cfg: dict) -> None:
    from lib.threads import build_threads

    records = [
        json.loads(line)
        for line in open(DATA_DIR / "clean.jsonl", encoding="utf-8")
    ]
    threads = build_threads(records, footer_marker=cfg["list_footer_marker"])
    out = DATA_DIR / "threads.json"
    out.write_text(json.dumps(threads, indent=2, ensure_ascii=False), encoding="utf-8")

    sizes = [len(t["message_ids"]) for t in threads.values()]
    singletons = sum(1 for s in sizes if s == 1)
    print(f"[thread] threads:    {len(threads):,}")
    print(f"[thread] singletons: {singletons:,}")
    print(f"[thread] multi:      {len(threads) - singletons:,}")
    print(f"[thread] largest:    {max(sizes)}")
    print(f"[thread] wrote {out}")


def stage_index(cfg: dict) -> None:
    from lib.index import build_message_index

    records = [json.loads(ln) for ln in open(DATA_DIR / "clean.jsonl", encoding="utf-8")]
    threads = json.loads((DATA_DIR / "threads.json").read_text(encoding="utf-8"))
    stats = build_message_index(cfg, records, threads)
    print(f"[index] documents: {stats['documents']:,}")
    print(f"[index] chunks:    {stats['chunks']:,}")
    print(f"[index] fts rows:  {stats['fts_rows']:,}")
    print(f"[index] store:     {stats['store']}")

    episodes_path = DATA_DIR / "episodes.jsonl"
    if episodes_path.exists():
        from lib.index import build_episode_index

        episodes = [json.loads(ln) for ln in open(episodes_path, encoding="utf-8")]
        ep_stats = build_episode_index(cfg, episodes)
        print(f"[index] episodes:  {ep_stats['episodes']:,}")
        print(f"[index] store:     {ep_stats['store']}")
    else:
        print("[index] no data/episodes.jsonl yet — skipping the episode index")

    documents_path = DATA_DIR / "documents.jsonl"
    if documents_path.exists():
        from lib.index import build_document_index

        doc_records = [json.loads(ln) for ln in open(documents_path, encoding="utf-8")]
        doc_stats = build_document_index(cfg, doc_records)
        print(f"[index] doc chunks: {doc_stats['chunks']:,}")
        print(f"[index] fts rows:   {doc_stats['fts_rows']:,}")
        print(f"[index] store:      {doc_stats['store']}")
    else:
        print("[index] no data/documents.jsonl yet — skipping the document index")


def stage_docs(cfg: dict) -> None:
    from lib.documents import build_documents
    from lib.issue_pages import (
        build_issue_chunks,
        build_mailing_list_paragraphs,
        load_cached_pages,
        parse_issue_pages,
    )
    from lib.issues import load_registry

    onto = json.loads((DATA_DIR / "ontology.json").read_text(encoding="utf-8"))
    records = build_documents(cfg, onto, PROJECT_ROOT)

    # Issue-page content (Task 20) joins the same documents.jsonl -- see
    # lib/issue_pages.py's module docstring. Optional: a build with no
    # cached pages (tools/fetch_issue_pages.py never run) still produces a
    # valid docs stage, just without `kind: "issue"` records.
    issue_stats = None
    pages_html = load_cached_pages()
    if pages_html:
        clean_path = DATA_DIR / "clean.jsonl"
        if clean_path.exists():
            clean_records = [json.loads(ln) for ln in open(clean_path, encoding="utf-8")]
        else:
            clean_records = []
        registry = load_registry(PROJECT_ROOT / "sources" / "crm_issues.json")
        parsed_by_id = parse_issue_pages(pages_html)
        mailing_list_paragraphs = build_mailing_list_paragraphs(clean_records)
        issue_records, issue_stats = build_issue_chunks(
            parsed_by_id, registry, mailing_list_paragraphs,
            cfg["ontology"]["id_pattern"], onto, cfg["chunk_size"], cfg["chunk_overlap"],
        )
        records.extend(issue_records)

    # SIG meeting minutes (data/minutes/, tools/fetch_minutes.py) join the
    # same documents.jsonl as `kind: "minutes"`. Optional in exactly the same
    # way the issue pages are: a build with no cached minutes still produces a
    # valid docs stage. `load_all` reports unreadable files rather than
    # skipping them -- see lib/minutes.py for the malformed .docx that made
    # that necessary.
    minutes_stats = None
    if (DATA_DIR / "minutes").exists():
        from lib.minutes import load_all as load_minutes

        minutes_stats = load_minutes(DATA_DIR / "minutes")
        records.extend(minutes_stats["chunks"])
        (DATA_DIR / "minutes_issues.json").write_text(
            json.dumps(minutes_stats["issue_links"], ensure_ascii=False, indent=1),
            encoding="utf-8")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / "documents.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    declarations = [r for r in records if r["kind"] == "declaration"]
    narrative = [r for r in records if r["kind"] == "narrative"]
    issue_chunks = [r for r in records if r["kind"] == "issue"]
    print(f"[docs] documents:        {len(cfg.get('documents') or []):,}")
    print(f"[docs] declarations:     {len(declarations):,}")
    print(f"[docs] narrative chunks: {len(narrative):,}")
    print(f"[docs] narrative chars:  {sum(len(r['text']) for r in narrative):,}")
    print(f"[docs] issue chunks:     {len(issue_chunks):,}")
    if minutes_stats is not None:
        minute_chunks = [r for r in records if r["kind"] == "minutes"]
        linked = {link["issue"] for link in minutes_stats["issue_links"]}
        print(f"[docs] minutes:          {minutes_stats['meetings']:,} meetings, "
              f"{len(minute_chunks):,} chunks, "
              f"{sum(len(r['text']) for r in minute_chunks):,} chars")
        print(f"[docs] minutes issues:   {len(minutes_stats['issue_links']):,} links "
              f"across {len(linked):,} issues")
        for bad in minutes_stats["unreadable"]:
            print(f"[docs] UNREADABLE minutes file: {bad['file']} — {bad['error']}")
        for group in minutes_stats["duplicates"]:
            print(f"[docs] duplicate meeting text: {', '.join(group)}")
    if issue_stats:
        kept, dropped = issue_stats["proposal_kept_chars"], issue_stats["proposal_dropped_chars"]
        total = kept + dropped
        pct = 100 * kept / total if total else 0.0
        print(f"[docs] issue pages:      {issue_stats['pages']:,} parsed, "
              f"{issue_stats['with_outcome']:,} with an outcome")
        print(f"[docs] proposal dedup:   {kept:,} chars kept, {dropped:,} chars dropped "
              f"({pct:.1f}% kept)")
        print(f"[docs] reference edges:  {issue_stats['reference_edges']:,}")
    print(f"[docs] wrote {out}")


def stage_issues(cfg: dict) -> None:
    from lib.issue_pages import load_cached_pages, parse_issue_pages
    from lib.issues import build_issue_index, load_registry

    records = [json.loads(ln) for ln in open(DATA_DIR / "clean.jsonl", encoding="utf-8")]
    threads = json.loads((DATA_DIR / "threads.json").read_text(encoding="utf-8"))
    registry = load_registry(PROJECT_ROOT / "sources" / "crm_issues.json")
    pages_html = load_cached_pages()
    parsed_by_id = parse_issue_pages(pages_html) if pages_html else {}
    minutes_path = DATA_DIR / "minutes_issues.json"
    minutes_links = (json.loads(minutes_path.read_text(encoding="utf-8"))
                     if minutes_path.exists() else [])

    issues = build_issue_index(records, threads, registry, parsed_by_id, minutes_links)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / "issues.json"
    out.write_text(json.dumps(issues, indent=2, ensure_ascii=False), encoding="utf-8")

    discussed = sum(1 for v in issues.values() if v["thread_count"] > 0)
    page_only = len(issues) - discussed
    multi = sum(1 for v in issues.values() if v["thread_count"] > 1)
    with_outcome = sum(1 for v in issues.values() if v.get("outcome"))
    reference_edges = sum(len(v.get("references") or []) for v in issues.values())
    threads_hit = {t["thread_id"] for v in issues.values() for t in v["threads"]}
    statuses: dict[str, int] = {}
    for v in issues.values():
        key = v["status"] or "(blank)"
        statuses[key] = statuses.get(key, 0) + 1

    minuted = sum(1 for v in issues.values() if v.get("meetings"))
    print(f"[issues] minuted:      {minuted:,} issues appear in the SIG minutes")
    print(f"[issues] register:     {len(registry):,} known issues")
    print(f"[issues] in this build: {len(issues):,} "
          f"({discussed:,} with archive discussion, {page_only:,} page-content only)")
    print(f"[issues] multi-thread: {multi:,}")
    print(f"[issues] threads carrying an issue number: {len(threads_hit):,}")
    print(f"[issues] with an outcome: {with_outcome:,}")
    print(f"[issues] reference edges: {reference_edges:,}")
    for status, count in sorted(statuses.items(), key=lambda kv: -kv[1]):
        print(f"[issues]   {status:10} {count:4}")
    print(f"[issues] wrote {out}")


def stage_episodes(cfg: dict, dump: bool, collect: bool) -> None:
    from lib.episodes import collect_shards, dump_prompts

    threads = json.loads((DATA_DIR / "threads.json").read_text(encoding="utf-8"))
    records = {}
    for line in open(DATA_DIR / "clean.jsonl", encoding="utf-8"):
        rec = json.loads(line)
        records[rec["id"]] = rec

    if dump:
        dump_prompts(threads, records, cfg["episodes"]["min_thread_size"])
        return
    if collect:
        onto = json.loads((DATA_DIR / "ontology.json").read_text(encoding="utf-8"))
        collect_shards(DATA_DIR / "prompts", threads, records, onto)
        return
    raise SystemExit("episodes: pass --dump or --collect")


def stage_fetch(cfg: dict, repo: str, vectors: bool) -> None:
    """Download the built corpus from a Hugging Face dataset repo.

    `data/` and `stores/` are git-ignored derived artifacts, ~876MB, built
    from a 143MB mbox that is distributed separately. Without them a clone
    has the six ontology tools and none of the six archive tools -- and the
    archive is the half with no substitute, since anyone can rebuild domain
    and range checking from the published RDFS and nobody else has the SIG's
    26 years of argument indexed.

    `--no-vectors` takes the full-text indexes and skips the vector stores:
    about 91MB instead of 876MB, BM25 search over the whole archive, and no
    need for torch or an embedding model at all. Hybrid and vector search
    need the rest.

    Verifies rather than trusts. Each store records the embedding model it
    was built with, and a store embedded with one model and queried with
    another returns confident nonsense rather than an error.
    """
    from huggingface_hub import snapshot_download

    patterns = ["data/**", "stores/**/fts.sqlite3", "stores/**/meta.json"]
    if vectors:
        patterns = ["data/**", "stores/**"]
    print(f"[fetch] {repo} -> {PROJECT_ROOT}"
          + ("" if vectors else "  (full-text indexes only, no vectors)"))
    snapshot_download(repo_id=repo, repo_type="dataset",
                      local_dir=str(PROJECT_ROOT),
                      allow_patterns=patterns)

    for meta_path in sorted((PROJECT_ROOT / "stores").glob("*/meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        print(f"[fetch] {meta_path.parent.name}: embedded with "
              f"{meta.get('embedding_model', '?')}")
    got = sorted(p.name for p in (PROJECT_ROOT / "data").glob("*.jsonl"))
    print(f"[fetch] data: {' '.join(got) or '(none)'}")
    # ontology.json is deliberately not published: it is rebuilt from the
    # tracked sources/ in seconds, and a downloaded copy could silently
    # shadow the inputs it is supposed to be derived from.
    if not (DATA_DIR / "ontology.json").exists():
        print("[fetch] next: uv run python build.py ontology")


def main() -> None:
    parser = argparse.ArgumentParser(description="Email archive pipeline")
    parser.add_argument(
        "stage",
        choices=["ontology", "clean", "thread", "index", "episodes", "docs",
                 "issues", "fetch"],
    )
    parser.add_argument("--archive", default="crm-sig")
    parser.add_argument("--audit", type=int, default=0, help="print N before/after diffs")
    parser.add_argument("--limit", type=int, default=None, help="process only N messages")
    parser.add_argument("--dump", action="store_true", help="episodes: write prompt shards")
    parser.add_argument("--collect", action="store_true", help="episodes: read result shards")
    parser.add_argument("--repo", default="stefdoerr/cidoc-crm-corpus",
                        help="fetch: the Hugging Face dataset repo to pull from")
    parser.add_argument("--no-vectors", action="store_true",
                        help="fetch: text and full-text indexes only, skipping "
                             "the 824MB of vectors (BM25 works; hybrid and "
                             "vector search do not)")
    args = parser.parse_args()

    cfg = load_config(args.archive)
    if args.stage == "fetch":
        stage_fetch(cfg, args.repo, vectors=not args.no_vectors)
    elif args.stage == "ontology":
        stage_ontology(cfg)
    elif args.stage == "clean":
        stage_clean(cfg, args.audit, args.limit)
    elif args.stage == "thread":
        stage_thread(cfg)
    elif args.stage == "episodes":
        stage_episodes(cfg, args.dump, args.collect)
    elif args.stage == "docs":
        stage_docs(cfg)
    elif args.stage == "issues":
        stage_issues(cfg)
    else:
        stage_index(cfg)


if __name__ == "__main__":
    main()
