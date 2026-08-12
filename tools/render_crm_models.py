"""Render the CIDOC CRM example-format models as one inspectable page.

The format hides its own meaning: a property is an ELEMENT NAME, a class is
a string after a colon, and the relationship is the indentation. Reading it
raw means holding all three conventions in your head at once. This resolves
every identifier to its full name, keeps the nesting visible as structure,
and marks each validation finding at the node it belongs to rather than in a
separate report you have to cross-reference by hand.
"""
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Derived from this file's own location rather than hardcoded, so the tool
# runs from any checkout: tools/ sits one level below the repository root.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lib.ontology import (  # noqa: E402
    _model_view, crm_example_class_uses, crm_example_links,
    validate_class_labels, validate_document,
)

ONTO = json.loads((ROOT / "data" / "ontology.json").read_text(encoding="utf-8"))
CLASSES, PROPS = _model_view(ONTO)
POP = ONTO.get("property_of_property") or {}

MODELS = [
    ("crm_sutton_hoo", "Sutton Hoo helmet", "Anglo-Saxon, buried c. 625, excavated 1939"),
    ("crm_bayeux", "Bayeux Tapestry", "Embroidered hanging, 11th century"),
    ("crm_uffington", "Uffington White Horse", "Chalk hill figure, late Bronze Age"),
    ("crm_da_yu_ding", "Da Yu ding", "Western Zhou bronze cauldron, 11th century BC"),
    ("crm_houmuwu", "Houmuwu ding", "Shang bronze cauldron, c. 1200 BC"),
    ("crm_marquis_yi", "Bianzhong of Marquis Yi", "Set of 65 bronze bells, 433 BC"),
    ("crm_mao_gong", "Mao Gong ding", "Western Zhou bronze cauldron, late 9th century BC"),
    ("crm_shi_qiang", "Shi Qiang pan", "Western Zhou bronze basin, c. 900 BC"),
]

_IN_CLASS = re.compile(r"\s*([A-Za-z]+\d+(?:\.\d)?)\s*[:.]")


def class_name(cid):
    e = CLASSES.get(cid) or PROPS.get(cid) or POP.get(cid)
    if not e:
        return None
    return (e.get("label") or e.get("direct_name")
            or e.get("full_name") or "").strip() or None


def esc(s):
    return html.escape(s or "")


def build_tree(node, findings_by_path, labels_by_path, path, depth=0):
    """One <li> per property element, carrying its own findings."""
    out = []
    for child in node:
        if child.tag == "in_class":
            continue
        here = f"{path}/{child.tag}"
        ic = child.findtext("in_class")
        m = _IN_CLASS.match(ic) if ic else None
        cid = m.group(1) if m else None
        raw_label = ic[m.end():].strip() if (ic and m) else ""
        # the element's own literal text, before its children
        text = (child.text or "").strip()

        f = findings_by_path.get(here)
        lf = labels_by_path.get(here)
        cls = []
        badges = []
        if f and f["verdict"] not in ("ok", "ok_literal"):
            cls.append(f"flag-{f['verdict']}")
            badges.append((f["verdict"], f["detail"]))
        if lf:
            cls.append("flag-label")
            badges.append((lf["verdict"], lf["detail"]))
        resolved = (f or {}).get("detail") if (f or {}).get("verdict") in ("ok", "ok_literal") else None

        out.append(f'<li class="{" ".join(cls)}">')
        out.append('<div class="node">')
        out.append(f'<span class="prop">{esc(child.tag)}</span>')
        if resolved:
            out.append(f'<span class="pid">{esc(resolved)}</span>')
        if cid:
            nm = class_name(cid)
            out.append(f'<span class="cls" title="{esc(nm or "unresolved")}">'
                       f'<b>{esc(cid)}</b>{" " + esc(nm) if nm else ""}</span>')
            if raw_label and nm and raw_label.lower() != nm.lower():
                out.append(f'<span class="asnamed">document: “{esc(raw_label)}”</span>')
        if text:
            short = text if len(text) <= 240 else text[:240] + "…"
            out.append(f'<span class="lit">{esc(short)}</span>')
        out.append("</div>")
        for verdict, detail in badges:
            out.append(f'<div class="badge b-{verdict}">'
                       f'<b>{esc(verdict.replace("_", " "))}</b> {esc(detail)}</div>')
        kids = [c for c in child if c.tag != "in_class"]
        if kids:
            out.append("<ul>")
            out.append(build_tree(child, findings_by_path, labels_by_path, here, depth + 1))
            out.append("</ul>")
        out.append("</li>")
    return "".join(out)


def render_model(stem, title, subtitle):
    path = ROOT / "models" / f"{stem}.xml"
    if not path.exists():
        return None, None
    links = crm_example_links(path)
    report = validate_document(ONTO, links)
    labels = validate_class_labels(ONTO, crm_example_class_uses(path))
    # index findings by their path so each lands on its own node
    fbp = {f["path"]: f for f in report["findings"]}
    lbp = {}
    for lf in labels:
        lbp.setdefault(lf["path"].rstrip("/in_class") or lf["path"], lf)

    counts = report["counts"]
    root = ET.parse(path).getroot()
    records = []
    for rec in root.findall("CRM_Entity"):
        ic = rec.findtext("in_class")
        m = _IN_CLASS.match(ic) if ic else None
        cid = m.group(1) if m else None
        head = (rec.text or "").strip() or "(unnamed)"
        rpath = f"CRM_Entity[{cid}]"
        body = build_tree(rec, fbp, lbp, rpath)
        nm = class_name(cid) if cid else None
        records.append(
            f'<article class="record"><header class="rhead">'
            f'<span class="cls"><b>{esc(cid or "?")}</b>{" " + esc(nm) if nm else ""}</span>'
            f'<h3>{esc(head)}</h3></header><ul class="tree">{body}</ul></article>')

    def chip(k, v, kind):
        return f'<span class="chip c-{kind}"><b>{v}</b> {k}</span>'
    chips = [chip("ok", counts.get("ok", 0) + counts.get("ok_literal", 0), "ok")]
    for k, kind in (("ambiguous", "amb"), ("attached_to_property", "err"),
                    ("unknown_name", "err"),
                    ("illegal", "err"), ("malformed", "err")):
        if counts.get(k):
            chips.append(chip(k.replace("_", " "), counts[k], kind))
    if labels:
        chips.append(chip("label mismatch", len(labels), "note"))

    summary = {
        "stem": stem, "title": title, "links": report["links"],
        "counts": counts, "labels": len(labels),
        "records": len(records),
        "classes": len({l["subject"] for l in links if l["subject"]}
                       | {l["object"] for l in links if l["object"]}),
    }
    section = (
        f'<details class="model" id="{stem}">'
        f'<summary><span class="mt">{esc(title)}</span>'
        f'<span class="ms">{esc(subtitle)}</span>'
        f'<span class="chips">{"".join(chips)}</span></summary>'
        f'<div class="records">{"".join(records)}</div></details>')
    return section, summary


sections, summaries = [], []
for stem, title, subtitle in MODELS:
    sec, summ = render_model(stem, title, subtitle)
    if sec:
        sections.append(sec)
        summaries.append(summ)

rows = []
for s in summaries:
    c = s["counts"]
    flags = (c.get("unknown_name", 0) + c.get("illegal", 0)
             + c.get("attached_to_property", 0))
    state = "clean" if not flags and not s["labels"] else (
        "flagged" if flags else "noted")
    rows.append(
        f'<tr><td><a href="#{s["stem"]}">{esc(s["title"])}</a></td>'
        f'<td class="n">{s["records"]}</td><td class="n">{s["links"]}</td>'
        f'<td class="n">{s["classes"]}</td>'
        f'<td class="n">{c.get("ambiguous", 0) or "—"}</td>'
        f'<td class="n">{s["labels"] or "—"}</td>'
        f'<td><span class="state s-{state}">{state}</span></td></tr>')

total_links = sum(s["links"] for s in summaries)
total_amb = sum(s["counts"].get("ambiguous", 0) for s in summaries)
# attached_to_property is a defect like the other two -- the link is legal
# and the assertion it makes is false -- so the headline must count it, or a
# page showing 175 of them reports "0".
total_err = sum(s["counts"].get("unknown_name", 0) + s["counts"].get("illegal", 0)
                + s["counts"].get("attached_to_property", 0)
                for s in summaries)


CSS = """
:root{
  --ground:#E9EAE5; --surface:#F4F5F1; --sunk:#DEE1D9;
  --ink:#191C19; --muted:#5E6560; --hair:#C9CDC4;
  --accent:#2E6B58; --accent-soft:#DBE7E1;
  --amb:#96631A; --amb-soft:#F1E6D2;
  --note:#4F6478; --note-soft:#DEE5EB;
  --err:#8E3527; --err-soft:#F1DBD5;
  --serif:ui-serif,"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
  --mono:ui-monospace,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --ground:#14170F; --surface:#1B1F18; --sunk:#0E1109;
    --ink:#E3E7DC; --muted:#949C8D; --hair:#2D332A;
    --accent:#82BCA3; --accent-soft:#1D2A23;
    --amb:#D3A057; --amb-soft:#2C2416;
    --note:#8FA8BF; --note-soft:#1A222A;
    --err:#D98A78; --err-soft:#2E1A16;
  }
}
:root[data-theme="dark"]{
  --ground:#14170F; --surface:#1B1F18; --sunk:#0E1109;
  --ink:#E3E7DC; --muted:#949C8D; --hair:#2D332A;
  --accent:#82BCA3; --accent-soft:#1D2A23;
  --amb:#D3A057; --amb-soft:#2C2416;
  --note:#8FA8BF; --note-soft:#1A222A;
  --err:#D98A78; --err-soft:#2E1A16;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);
  font-family:var(--serif);line-height:1.55;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto;padding:3rem 1.5rem 6rem}
header.page{border-bottom:2px solid var(--ink);padding-bottom:1.25rem;margin-bottom:2rem}
h1{font-size:clamp(1.7rem,3.2vw,2.5rem);line-height:1.15;margin:0 0 .4rem;
  text-wrap:balance;font-weight:600;letter-spacing:-.01em}
.sub{color:var(--muted);margin:0;max-width:62ch}
.totals{display:flex;flex-wrap:wrap;gap:1.75rem;margin-top:1.5rem;
  font-family:var(--mono);font-size:.8rem}
.totals div{display:flex;flex-direction:column;gap:.15rem}
.totals b{font-size:1.5rem;font-weight:600;font-variant-numeric:tabular-nums;
  line-height:1}
.totals span{color:var(--muted);text-transform:uppercase;letter-spacing:.08em;
  font-size:.66rem}
.board{width:100%;border-collapse:collapse;margin:0 0 2.5rem;
  font-family:var(--mono);font-size:.82rem}
.board th{text-align:left;font-weight:500;color:var(--muted);
  text-transform:uppercase;letter-spacing:.07em;font-size:.66rem;
  padding:.5rem .7rem;border-bottom:1px solid var(--hair)}
.board td{padding:.55rem .7rem;border-bottom:1px solid var(--hair)}
.board td.n{text-align:right;font-variant-numeric:tabular-nums}
.board a{color:var(--ink);text-decoration:none;border-bottom:1px solid var(--accent)}
.board a:hover{color:var(--accent)}
.state{font-size:.68rem;text-transform:uppercase;letter-spacing:.07em;
  padding:.15rem .45rem;border-radius:2px}
.s-clean{color:var(--accent);background:var(--accent-soft)}
.s-noted{color:var(--note);background:var(--note-soft)}
.s-flagged{color:var(--amb);background:var(--amb-soft)}
details.model{border:1px solid var(--hair);background:var(--surface);
  margin-bottom:.85rem;border-radius:3px}
details.model[open]{border-color:var(--accent)}
summary{cursor:pointer;padding:1rem 1.1rem;display:flex;flex-wrap:wrap;
  align-items:baseline;gap:.5rem 1rem;list-style:none}
summary::-webkit-details-marker{display:none}
summary::before{content:"▸";color:var(--accent);font-family:var(--mono);
  margin-right:.2rem}
details[open] summary::before{content:"▾"}
summary:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.mt{font-size:1.12rem;font-weight:600}
.ms{color:var(--muted);font-size:.86rem;flex:1 1 14rem}
.chips{display:flex;gap:.35rem;flex-wrap:wrap}
.chip{font-family:var(--mono);font-size:.68rem;padding:.15rem .45rem;
  border-radius:2px;white-space:nowrap}
.chip b{font-variant-numeric:tabular-nums}
.c-ok{color:var(--accent);background:var(--accent-soft)}
.c-amb{color:var(--amb);background:var(--amb-soft)}
.c-err{color:var(--err);background:var(--err-soft)}
.c-note{color:var(--note);background:var(--note-soft)}
.records{padding:0 1.1rem 1.4rem}
.record{border-top:1px solid var(--hair);padding-top:1.1rem;margin-top:1.1rem}
.rhead{display:flex;flex-wrap:wrap;align-items:baseline;gap:.6rem;
  margin-bottom:.6rem}
.rhead h3{margin:0;font-size:1rem;font-weight:600}
ul.tree,ul.tree ul{list-style:none;margin:0;padding:0}
ul.tree ul{margin-left:.62rem;padding-left:.9rem;border-left:1px solid var(--hair)}
ul.tree li{padding:.1rem 0}
.node{display:flex;flex-wrap:wrap;align-items:baseline;gap:.42rem;
  font-family:var(--mono);font-size:.78rem;padding:.1rem 0}
.prop{color:var(--accent);font-weight:600}
.pid{color:var(--muted);font-size:.7rem}
.cls{background:var(--sunk);padding:.05rem .35rem;border-radius:2px;
  font-size:.72rem}
.cls b{font-weight:600}
.asnamed{color:var(--note);font-size:.7rem;font-style:italic}
.lit{font-family:var(--serif);font-size:.86rem;color:var(--ink);
  flex:1 1 22rem;min-width:0}
li.flag-ambiguous>.node,li.flag-unknown_name>.node,
li.flag-illegal>.node,li.flag-label>.node{
  margin-left:-.55rem;padding-left:.45rem;border-left:3px solid var(--hair)}
li.flag-ambiguous>.node{border-left-color:var(--amb)}
li.flag-label>.node{border-left-color:var(--note)}
li.flag-unknown_name>.node,li.flag-illegal>.node{border-left-color:var(--err)}
.badge{font-family:var(--mono);font-size:.68rem;margin:.15rem 0 .35rem .45rem;
  padding:.28rem .5rem;border-radius:2px;max-width:70ch}
.badge b{text-transform:uppercase;letter-spacing:.05em}
.b-ambiguous{color:var(--amb);background:var(--amb-soft)}
.b-label_mismatch{color:var(--note);background:var(--note-soft)}
.b-unknown_name,.b-illegal,.b-malformed,.b-unknown_class{
  color:var(--err);background:var(--err-soft)}
.legend{font-family:var(--mono);font-size:.72rem;color:var(--muted);
  display:flex;flex-wrap:wrap;gap:1rem;margin:0 0 2rem}
.legend i{font-style:normal;border-left:3px solid;padding-left:.4rem}
footer{margin-top:3rem;padding-top:1.25rem;border-top:1px solid var(--hair);
  color:var(--muted);font-size:.82rem;max-width:64ch}
@media (max-width:640px){ .lit{flex-basis:100%} .wrap{padding:2rem 1rem 4rem} }
"""

BODY = """<div class="wrap">
<header class="page">
<h1>Six museum objects, encoded and checked</h1>
<p class="sub">Each model was written by an agent working only through the archive
search tool, in the XML form of the two published CIDOC CRM examples. That format
hides its own meaning: the property is the element name, the class is a string
after a colon, and the relationship is the indentation. Here every identifier is
resolved and every validation finding sits on the node it belongs to.</p>
<div class="totals">
<div><b>__MODELS__</b><span>models</span></div>
<div><b>__LINKS__</b><span>links checked</span></div>
<div><b>__ERR__</b><span>false or unresolvable</span></div>
<div><b>__AMB__</b><span>ambiguous</span></div>
</div>
</header>

<table class="board">
<thead><tr><th>model</th><th class="n">records</th><th class="n">links</th>
<th class="n">classes</th><th class="n">ambig.</th><th class="n">attached</th><th class="n">label</th>
<th>state</th></tr></thead>
<tbody>__ROWS__</tbody>
</table>

<p class="legend">
<i style="border-color:var(--err)">illegal, unknown name, or attached to a property — a real defect</i>
<i style="border-color:var(--amb)">ambiguous — legal, but the format cannot say which property</i>
<i style="border-color:var(--note)">label mismatch — a retired class name, or a role qualifier</i>
</p>

__SECTIONS__

<footer>Validation by <code>search.py validate --xml</code>, which resolves each
element name against the CIDOC CRM v7.1.3 ontology plus the family extension
models and checks both ends of every link against the declared domain and range.
Literal values are truncated at 240 characters; nothing else is abridged.</footer>
</div>"""

body = (BODY.replace("__MODELS__", str(len(summaries)))
            .replace("__LINKS__", f"{total_links:,}")
            .replace("__ERR__", str(total_err))
            .replace("__AMB__", str(total_amb))
            .replace("__ROWS__", "".join(rows))
            .replace("__SECTIONS__", "".join(sections)))

out = ROOT / "crm_models_review.html"
out.write_text(f"<title>Six CIDOC CRM models, checked</title>\n"
               f"<style>{CSS}</style>\n{body}\n", encoding="utf-8")
print(f"wrote {out} — {out.stat().st_size:,} bytes, {len(summaries)} models, "
      f"{total_links:,} links, {total_err} errors, {total_amb} ambiguous")
