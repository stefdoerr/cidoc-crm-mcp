"""Rebuild crm_issues.json from the official CIDOC CRM SIG issue register.

The SIG's unit of decision is the numbered issue, not the mailing-list thread:
issues span years and many threads (issue 332 alone spans 10 threads in this
archive). https://cidoc-crm.org/issue_summary is the SIG's own register of
every issue it has ever opened, with the one field the archive cannot infer
by reading a thread -- authoritative Status (Done / Open / Proposed / On
going) straight from the SIG, rather than guessed from how a thread reads.

This is a maintenance script, not part of the build: it needs network access
and the output is committed. Re-run it periodically -- the register is live
(new issues open, open ones close) and does not version like a spec release.

    uv run python tools/fetch_crm_issues.py
"""

import html
import json
import re
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEST = PROJECT_ROOT / "sources" / "crm_issues.json"
RETRIEVED = "2026-08-06"

SOURCE = "https://cidoc-crm.org/issue_summary"
BASE = "https://cidoc-crm.org"

_TAG = re.compile(r"<[^>]+>")
_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_TABLE_START = '<table class="solo-table-all'
_ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
_TITLE_LINK = re.compile(r'<a href="([^"]+)"[^>]*>(.*?)</a>', re.S)


def _clean(text: str) -> str:
    return " ".join(html.unescape(_TAG.sub(" ", text)).split())


def _cell(row: str, header: str) -> str:
    """Inner HTML of the <td headers="{header}"> cell in one <tr>.

    Cells are matched by their `headers` attribute rather than position: the
    columns are fixed by header id in the markup, but whitespace around each
    cell varies, so this is more robust than splitting on <td> boundaries.
    """
    m = re.search(rf'headers="{header}"[^>]*>(.*?)</td>', row, re.S)
    return m.group(1) if m else ""


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "crm-archive-search/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_row(row: str) -> dict | None:
    """One issue-register row, or None for the header row (no numeric id)."""
    id_cell = _clean(_cell(row, "view-field-id-table-column"))
    if not id_cell.isdigit():
        return None

    title_cell = _cell(row, "view-title-table-column")
    link = _TITLE_LINK.search(title_cell)
    url = BASE + link.group(1) if link else None
    title = _clean(link.group(2)) if link else _clean(title_cell)

    working_group = _clean(_cell(row, "view-field-working-group-table-column")) or None
    status = _clean(_cell(row, "view-field-status-table-column")) or None
    closing = _DATE.search(_cell(row, "view-field-closing-date-table-column"))
    updated = _DATE.search(_cell(row, "view-changed-table-column"))
    family = _clean(_cell(row, "view-field-family-model-voc-table-column"))

    return {
        "id": int(id_cell),
        "title": title,
        "url": url,
        "working_group": working_group,
        "status": status,
        "closing_date": closing.group(1) if closing else None,
        "last_updated": updated.group(1) if updated else None,
        "family_model": [m.strip() for m in family.split(",") if m.strip()],
    }


def scrape_issues() -> dict[int, dict]:
    page = _get(SOURCE)
    start = page.index(_TABLE_START)
    end = page.index("</table>", start)
    table = page[start:end]

    entries: dict[int, dict] = {}
    for row in _ROW.findall(table):
        parsed = parse_row(row)
        if parsed:
            entries[parsed["id"]] = parsed
    return entries


def main() -> None:
    entries = scrape_issues()

    statuses: dict[str, int] = {}
    for entry in entries.values():
        key = entry["status"] or "(blank)"
        statuses[key] = statuses.get(key, 0) + 1
    for status, count in sorted(statuses.items(), key=lambda kv: -kv[1]):
        print(f"{status:10} {count:4}")

    DEST.write_text(
        json.dumps(
            {
                "description": (
                    "The official CIDOC CRM SIG issue register: every numbered "
                    "issue the SIG has opened, with its authoritative Status "
                    "(Done / Open / Proposed / On going) as the SIG itself "
                    "records it -- not inferred from how a mailing-list "
                    "thread reads."
                ),
                "source": SOURCE,
                "retrieved": RETRIEVED,
                "count": len(entries),
                "entries": {str(k): v for k, v in sorted(entries.items())},
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\ntotal {len(entries)} issues -> {DEST}")


if __name__ == "__main__":
    main()
