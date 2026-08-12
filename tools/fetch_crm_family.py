"""Rebuild crm_family.json from the official CIDOC CRM declaration pages.

The SIG debates the whole CRM family, not only CRMbase, so the archive is full
of identifiers (F3, S4, SP6, A8 ...) that cidoc_crm_v7.1.3.xml does not define.
Without a list of them there is no way to tell a real extension identifier from
a model's hallucination.

Beyond the bare id/label/model/kind, each declaration page carries a scope
note, a URI, its subclass-of/superclass-of (classes) and its domain, range and
subproperty-of/superproperty-of (properties) -- everything a reader needs to
actually decide whether this id fits their case, not just that it exists. Only
FRBRoo lacks this: it comes from a PDF with no equivalent structure, so its
entries stay label-only.

This is a maintenance script, not part of the build: it needs network access and
the output is committed. Re-run it when an extension publishes a new version.

    uv run --with pypdf python tools/fetch_crm_family.py
"""

import html
import json
import re
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEST = PROJECT_ROOT / "sources" / "crm_family.json"
RETRIEVED = "2026-08-06"

# Each model publishes a "Classes & Properties Declarations" page whose current
# version is served from the unversioned /extensions/<model>/ URL.
SOURCES = {
    "CRMsci":     "https://cidoc-crm.org/extensions/crmsci/",
    "CRMgeo":     "https://cidoc-crm.org/extensions/crmgeo/",
    "CRMarchaeo": "https://cidoc-crm.org/extensions/crmarchaeo/",
    "CRMba":      "https://cidoc-crm.org/extensions/crmba/",
    "CRMtex":     "https://cidoc-crm.org/extensions/crmtex/",
    "CRMdig":     "https://cidoc-crm.org/extensions/crmdig/",
    "CRMinf":     "https://cidoc-crm.org/extensions/crminf/",
    "CRMact":     "https://cidoc-crm.org/extensions/crmact/",
    "LRMoo":      "https://cidoc-crm.org/extensions/lrmoo/",
    "PRESSoo":    "https://cidoc-crm.org/extensions/pressoo/",
}

# FRBRoo was superseded by LRMoo in 2021, but most of this archive predates that
# and uses FRBRoo ids heavily. No structured release survives on the CRM site,
# so its identifiers come from the official PDF.
FRBROO_PDF = "http://old.cidoc-crm.org/docs/frbr_oo/frbr_docs/FRBRoo_V2.4.pdf"

# CRMsoc has a version 0.1 page but publishes no declarations list; its ids are
# picked up from the archive by the prefix registry in lib/ontology.py.

_ENTITY = re.compile(r'<span class="(cls|prop)" id="([^"]+)">')
_LABEL = re.compile(r'<span class="(?:cls|prop)" id="[^"]+">(.*?)(?:<a |</span>)', re.S)
_URI = re.compile(
    r'<span class="cardLabel">URI[^<]*:</span>\s*</td>\s*<td>\s*'
    r'<span class="cardLabel">\s*<a href="([^"]+)"',
    re.S,
)
_TAG = re.compile(r"<[^>]+>")
_IDENT = re.compile(r"[A-Z]{1,4}-?[A-Z]?\d{1,3}")


def _clean(text: str) -> str:
    return " ".join(html.unescape(_TAG.sub("", text)).split())


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "crm-archive-search/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def _field_cell(block: str, label: str) -> str | None:
    """Raw HTML of the col2 cell under a declaration-table row labelled
    `label` ('Scope Note:', 'SubClass Of:', 'Domain:', ...), or None if this
    declaration has no such row at all -- distinct from a present-but-empty
    row (rendered as the literal text ' - '), which callers see as "".

    Every field on a declaration page follows this same two-row shape: a
    `cardLabel` header row, then a data row whose col2 cell holds the value
    -- prose for Scope Note, one `<a>id</a>` per related identifier for a
    relation field. One helper covers both because the site renders both the
    same way.
    """
    m = re.search(
        rf'<span class="cardLabel">{re.escape(label)}</span></td></tr>'
        r'<tr><td class="col1"/><td class="col2"[^>]*>(.*?)</td>',
        block, re.S,
    )
    return m.group(1) if m else None


def _field_ids(block: str, label: str) -> list[str]:
    """Identifiers linked from a relation field's cell.

    Each related identifier is an `<a>` whose link text IS the short id,
    whether it points elsewhere on this same page (`#S27`) or out to a
    CRMbase class by full URL -- so reading anchor text, not the href,
    handles both without caring which kind of link it is.
    """
    cell = _field_cell(block, label)
    return re.findall(r'<a href="[^"]*">([A-Za-z0-9]+)</a>', cell) if cell else []


def _field_text(block: str, label: str) -> str | None:
    """Cleaned prose of a text field's cell ('Scope Note:'), or None if
    absent -- never the literal placeholder ' - ' some pages render."""
    cell = _field_cell(block, label)
    cleaned = _clean(cell) if cell else ""
    return cleaned if cleaned and cleaned != "-" else None


def _entity_blocks(page: str) -> list[tuple[str, str, str]]:
    """(kind, ident, block) for every declaration on a Classes & Properties
    page. A block runs from one declaration's opening `<span class="cls"|
    "prop">` to the next such span, or to the end of the page.

    Boundary-based, not a whitelist of expected fields inside it: the same
    lesson data/documents.jsonl's parser encodes (see the corpus spec) --
    a field this scrape doesn't yet know about is absorbed into the block
    rather than silently dropped or corrupting the split.
    """
    starts = [(m.start(), m.group(1), m.group(2)) for m in _ENTITY.finditer(page)]
    return [
        (kind, ident, page[pos : starts[i + 1][0] if i + 1 < len(starts) else len(page)])
        for i, (pos, kind, ident) in enumerate(starts)
    ]


def scrape_declarations() -> tuple[dict, dict]:
    entries: dict[str, dict] = {}
    models: dict[str, dict] = {}
    for model, url in SOURCES.items():
        page = _get(url).decode("utf-8", errors="replace")
        version = re.search(r"version:?\s*([0-9]+\.[0-9]+(?:\.[0-9]+)?)", page, re.I)
        count = 0
        for kind, ident, block in _entity_blocks(page):
            ident = ident.strip().upper()
            if not _IDENT.fullmatch(ident):
                continue
            label_match = _LABEL.match(block)
            # The declaration text repeats the id: "S1 Matter Removal".
            label = re.sub(
                rf"^{re.escape(ident)}\s+", "",
                _clean(label_match.group(1)) if label_match else "",
                flags=re.I,
            )
            uri_match = _URI.search(block)
            entry = {
                "id": ident,
                "label": label or None,
                "model": model,
                "kind": "class" if kind == "cls" else "property",
                "uri": uri_match.group(1) if uri_match else None,
                "scope_note": _field_text(block, "Scope Note:"),
            }
            if kind == "cls":
                entry["sub_class_of"] = _field_ids(block, "SubClass Of:")
                entry["super_class_of"] = _field_ids(block, "SuperClass Of:")
            else:
                domain = _field_ids(block, "Domain:")
                rng = _field_ids(block, "Range:")
                entry["domain"] = domain[0] if domain else None
                entry["range"] = rng[0] if rng else None
                entry["sub_property_of"] = _field_ids(block, "SubProperty Of:")
                entry["super_property_of"] = _field_ids(block, "SuperProperty Of:")
            entries[ident] = entry
            count += 1
        models[model] = {
            "source": url,
            "version": version.group(1) if version else None,
            "entries": count,
        }
        print(f"{model:11} v{models[model]['version'] or '?':7} {count:4} declarations")
    return entries, models


def scrape_frbroo(entries: dict) -> int:
    from pypdf import PdfReader   # only this script needs it
    import io

    reader = PdfReader(io.BytesIO(_get(FRBROO_PDF)))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    # Declarations read "F1 Work" / "R1 is logical successor of". The same id
    # recurs throughout the prose, so take the most frequent reading.
    seen: dict[str, dict[str, int]] = {}
    for match in re.finditer(r"\b([FR]\d{1,3})\s+([A-Za-z][A-Za-z0-9 ,'\-/()]{2,60})", text):
        label = " ".join(match.group(2).split())
        seen.setdefault(match.group(1), {})
        seen[match.group(1)][label] = seen[match.group(1)].get(label, 0) + 1
    added = 0
    for ident, labels in seen.items():
        if ident in entries:      # LRMoo's F1-F5 keep the newer definition
            continue
        entries[ident] = {
            "id": ident,
            "label": max(labels, key=labels.get),
            "model": "FRBRoo",
            "kind": "class" if ident.startswith("F") else "property",
        }
        added += 1
    print(f"{'FRBRoo':11} v2.4     {added:4} declarations (ids not already in LRMoo)")
    return added


def main() -> None:
    entries, models = scrape_declarations()
    added = scrape_frbroo(entries)
    models["FRBRoo"] = {"source": FRBROO_PDF, "version": "2.4", "entries": added}

    DEST.write_text(
        json.dumps(
            {
                "description": (
                    "Identifiers of the CIDOC CRM family extension models, compiled "
                    "from the official Classes & Properties Declarations -- scope "
                    "note, URI, subclass-of/superclass-of (classes) or domain/range "
                    "and subproperty-of/superproperty-of (properties) alongside the "
                    "label/model/kind. FRBRoo (PDF-sourced) is label-only. CRMbase "
                    "(E/P) is not included -- it comes from cidoc_crm_v7.1.3.xml."
                ),
                "retrieved": RETRIEVED,
                "models": models,
                "entries": dict(sorted(entries.items())),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\ntotal {len(entries)} identifiers across {len(models)} models -> {DEST}")


if __name__ == "__main__":
    main()
