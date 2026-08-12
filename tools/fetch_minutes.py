#!/usr/bin/env python3
"""Fetch the CIDOC CRM SIG meeting minutes from cidoc-crm.org/minutes.

The minutes are where issues are actually closed. The register (crm_issues.json)
records *that* issue 295 deleted E84 at Cologne in January 2018; the minutes for
that meeting record the argument. Nothing else in this corpus carries that.

The index lists 116 files for 71 distinct filename stems, because most meetings
are published twice -- the same minutes as both .docx and .pdf. Downloading both
is pure waste, so one format is chosen per stem: docx, then pdf, then doc.
All three are readable (see lib/minutes.py; the legacy .doc files need the Word
97 piece table, but 12 meetings exist in no other format, and they are the early
ones where E27, E84 and P39 were settled).

**Duplicate meetings are NOT detected from filenames, and must not be.** The
obvious rule -- parse the meeting number out of the name and merge collisions --
is wrong here, and quietly destroys content. `Meeting10_Minutes.doc` is the
*10th FRBR/CRM Harmonization* meeting, Edinburgh, July 2007, which was also the
15th CRM SIG. `10th_crm_meeting_minutes.pdf` is the *10th CRM SIG*, Nuremberg,
December 2004. Two numbering series run through these filenames and they
collide. Number-based merging would have dropped one of those meetings
entirely. Cross-stem duplicates are therefore settled after extraction, by
comparing the text itself -- see lib.minutes.duplicate_groups.

Filename stems are still normalised for the one case that is safe: Drupal's
upload-collision suffixes (`_0`, `_1`, ` (1)`) name the same file re-uploaded,
not a different meeting.

This is a maintenance script, not part of the build: it needs network access and
data/minutes/ is a cache, not a committed artifact. A file already on disk is
skipped unless --force, so an interrupted run resumes.

    uv run python tools/fetch_minutes.py --dry-run    # list what would be taken
    uv run python tools/fetch_minutes.py
    uv run python tools/fetch_minutes.py --limit 5    # smoke test
"""

import argparse
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Must match lib.minutes.MINUTES_DIR -- that module reads this cache back.
CACHE_DIR = PROJECT_ROOT / "data" / "minutes"
INDEX_URL = "https://cidoc-crm.org/minutes"
BASE = "https://cidoc-crm.org"
DELAY_SECONDS = 0.5

# Best text first. docx and doc are the authored formats and keep paragraph
# structure; a PDF of the same minutes reproduces page furniture (headers,
# page numbers) as inline text. doc ranks last only because it needs the
# piece-table reader, not because it extracts worse.
FORMAT_PREFERENCE = ("docx", "pdf", "doc")

_LINK = re.compile(r'<a\b[^>]*href="([^"]+\.(?:pdf|docx|doc))"[^>]*>(.*?)</a>', re.I | re.S)
_TAGS = re.compile(r"<[^>]+>")
# Drupal appends these when a filename already exists; same document, not a
# different meeting. Anything else in the stem is left alone.
_UPLOAD_SUFFIX = re.compile(r"(?:[ _]\(\d+\)|_\d+)$")


def parse_index(page_html: str) -> list[dict]:
    """Every minutes link on the index page, with its anchor text."""
    out = []
    for href, label in _LINK.findall(page_html):
        href = html.unescape(href)
        out.append({
            "url": urllib.parse.urljoin(BASE, href),
            "path": urllib.parse.unquote(href),
            "ext": href.rsplit(".", 1)[1].lower(),
            "label": html.unescape(_TAGS.sub("", label)).strip(),
        })
    return out


def normalised_stem(path: str) -> str:
    """Filename without extension or Drupal's upload-collision suffix."""
    name = path.rsplit("/", 1)[-1]
    stem = re.sub(r"\.(pdf|docx|doc)$", "", name, flags=re.I)
    return _UPLOAD_SUFFIX.sub("", stem).strip()


def choose_one_per_stem(links: list[dict]) -> list[dict]:
    """One file per stem, best available format.

    This is the only dedup done before downloading, and it is the safe one:
    two files whose names differ solely by extension are the same minutes in
    two renderings. Meeting-level duplicates are left to the text comparison
    after extraction -- see the module docstring for why guessing from
    filenames is not an option.
    """
    by_stem: dict[str, list[dict]] = {}
    for link in links:
        by_stem.setdefault(normalised_stem(link["path"]), []).append(link)

    chosen = []
    for stem, group in sorted(by_stem.items()):
        rank = {fmt: i for i, fmt in enumerate(FORMAT_PREFERENCE)}
        pick = min(group, key=lambda c: (rank.get(c["ext"], 99), c["path"]))
        pick = dict(pick)
        pick["stem"] = stem
        pick["skipped_formats"] = sorted({c["ext"] for c in group} - {pick["ext"]})
        chosen.append(pick)
    return chosen


def local_name(entry: dict) -> str:
    """Cache filename: the stem, made filesystem-safe, plus the real extension."""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", entry["stem"]).strip("_") or "minutes"
    return f"{safe}.{entry['ext']}"


def _get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "crm-archive-search/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_all(entries: list[dict], cache_dir: Path, force: bool = False,
              limit: int | None = None, delay: float = DELAY_SECONDS) -> dict:
    cache_dir.mkdir(parents=True, exist_ok=True)
    written, skipped, failed = [], [], []
    for entry in entries[:limit]:
        target = cache_dir / local_name(entry)
        if target.exists() and not force:
            skipped.append(target.name)
            continue
        try:
            payload = _get(entry["url"])
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            failed.append({"url": entry["url"], "error": str(exc)})
            continue
        target.write_bytes(payload)
        written.append({"name": target.name, "bytes": len(payload)})
        time.sleep(delay)
    return {"written": written, "skipped": skipped, "failed": failed}


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--delay", type=float, default=DELAY_SECONDS)
    args = ap.parse_args()

    page = _get(INDEX_URL).decode("utf-8", errors="replace")
    links = parse_index(page)
    entries = choose_one_per_stem(links)

    by_ext: dict[str, int] = {}
    for e in entries:
        by_ext[e["ext"]] = by_ext.get(e["ext"], 0) + 1
    saved = len(links) - len(entries)
    print(f"index lists {len(links)} files for {len(entries)} distinct meetings "
          f"({saved} duplicate renderings not downloaded)")
    print("  taking: " + ", ".join(f"{n} {ext}" for ext, n in sorted(by_ext.items())))

    if args.dry_run:
        for e in entries:
            skipped = f"  [also available as {', '.join(e['skipped_formats'])}]" \
                if e["skipped_formats"] else ""
            print(f"  {e['ext']:4} {local_name(e)}{skipped}")
        return

    result = fetch_all(entries, CACHE_DIR, force=args.force,
                       limit=args.limit, delay=args.delay)
    total = sum(w["bytes"] for w in result["written"])
    print(f"\ndownloaded {len(result['written'])} files ({total:,} bytes), "
          f"{len(result['skipped'])} already cached, {len(result['failed'])} failed")
    for f in result["failed"]:
        print(f"  FAILED {f['url']}: {f['error']}")
    (CACHE_DIR / "index.json").write_text(
        json.dumps({"source": INDEX_URL, "entries": entries}, indent=1, ensure_ascii=False),
        encoding="utf-8")


if __name__ == "__main__":
    main()
