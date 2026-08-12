"""Fetch every CIDOC CRM SIG issue page's raw HTML from the URLs already in
crm_issues.json -- never construct a URL from a title; the slugs are not
derivable (abbreviations, punctuation, issues retitled after opening) and a
guessed one 404s.

This is a maintenance script, not part of the build: it needs network access
and its output (data/issue_pages/*.html) is a cache, not a committed
artifact -- data/ is gitignored, same as data/clean.jsonl. Safe to re-run at
any time: a page already on disk is skipped unless --force says otherwise,
so an interrupted run resumes where it left off instead of re-downloading
everything, and a routine re-run only re-fetches pages that are new to the
register.

Rate-limited by a fixed delay between requests (default 0.4s) -- this is
someone's server, not a CDN, and 715 pages at any real concurrency would be
indistinguishable from a scrape attack.

    uv run python tools/fetch_issue_pages.py
    uv run python tools/fetch_issue_pages.py --limit 20      # smoke test
    uv run python tools/fetch_issue_pages.py --force          # re-fetch all
"""

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

# Self-contained, like tools/fetch_crm_issues.py and tools/fetch_crm_family.py
# beside it: a script under tools/ is not run as part of the `lib` package
# (its own directory, not the project root, is what ends up on sys.path), so
# it defines its own paths rather than importing lib.config/lib.issues.
# CACHE_DIR must still match lib.issue_pages.ISSUE_PAGES_DIR exactly -- that
# module is what reads this cache back at build time.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REGISTER = PROJECT_ROOT / "sources" / "crm_issues.json"
CACHE_DIR = PROJECT_ROOT / "data" / "issue_pages"
DELAY_SECONDS = 0.4


def load_registry_urls(path: str | Path) -> dict[int, str]:
    """{issue id: page url}, from crm_issues.json's `entries` map."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))["entries"]
    return {int(k): v["url"] for k, v in raw.items()}


def _get(url: str, timeout: int = 60) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "crm-archive-search/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_all(
    urls: dict[int, str],
    cache_dir: Path,
    force: bool = False,
    limit: int | None = None,
    delay: float = DELAY_SECONDS,
) -> dict:
    """Fetch every id's page into `cache_dir`, one file per id.

    Skips an id already cached unless `force`, so re-running after a
    partial or interrupted run costs nothing for the pages it already has.
    A fetch failure (network error, timeout, missing URL) is logged and
    counted, never fatal -- one bad id must not abort the other 714.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    ids = sorted(urls)
    if limit is not None:
        ids = ids[:limit]

    fetched = skipped = failed = 0
    for iid in ids:
        dest = cache_dir / f"{iid}.html"
        if dest.exists() and not force:
            skipped += 1
            continue
        url = urls.get(iid)
        if not url:
            failed += 1
            print(f"[fetch] issue {iid}: no URL in the register, skipping")
            continue
        try:
            page_html = _get(url)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            failed += 1
            print(f"[fetch] issue {iid}: {exc}")
            continue
        dest.write_text(page_html, encoding="utf-8")
        fetched += 1
        if fetched % 50 == 0:
            print(f"[fetch] {fetched} fetched, {skipped} skipped, {failed} failed so far")
        time.sleep(delay)

    return {"fetched": fetched, "skipped": skipped, "failed": failed, "total": len(ids)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-fetch pages already cached")
    parser.add_argument(
        "--limit", type=int, default=None, help="fetch only the first N ids (smoke test)"
    )
    parser.add_argument("--delay", type=float, default=DELAY_SECONDS)
    args = parser.parse_args()

    urls = load_registry_urls(REGISTER)
    stats = fetch_all(urls, CACHE_DIR, force=args.force, limit=args.limit, delay=args.delay)
    print(
        f"[fetch] fetched {stats['fetched']}, skipped {stats['skipped']} (already cached), "
        f"failed {stats['failed']}, of {stats['total']} known issues"
    )
    print(f"[fetch] cache: {CACHE_DIR}")


if __name__ == "__main__":
    main()
