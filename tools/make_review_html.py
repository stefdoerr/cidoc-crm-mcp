#!/usr/bin/env python3
"""Build the standalone human review sheet for the modelling evaluation.

One self-contained HTML file, no network access, meant to be emailed to a
domain expert who has never seen this repository. It exists because every
automated verdict in this project has turned out to need calibrating against
a human, and there was no artefact a human could actually work through.

    uv run python tools/make_review_html.py                      # run 2
    uv run python tools/make_review_html.py --answers 'manswer-*.json' \
        --verdicts '' --out eval-review-run1.html                # run 1

Two things about this script are load-bearing rather than incidental.

**The verdicts it displays are blinded, and must be decoded before use.**
`mstrict2-*.json` records `verdict_A`/`verdict_B` against slots, not runs --
the reviewers were deliberately not told which answer came from which version
of the system. `mstrict2-blind-key.json` maps slot to run per case. Showing a
slot verdict without decoding it would attribute half the verdicts to the
wrong run, silently, and the numbers would still look plausible.

**The localStorage key is versioned with the answers.** A reviewer who
already worked through the previous sheet has verdicts saved in this browser
under the old key. Reusing that key would silently pre-fill their old
judgements against different answers, and the sheet would look completed
before it was read. Bumping `--storage-key` whenever the answers change is
what stops that, so it defaults to a value derived from the answer glob.
"""

import argparse
import functools
import html
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVAL = PROJECT_ROOT / "data" / "eval"

# Citation problems confirmed BY HAND for the run being published -- not the
# strict reviewer's opinion, which is shown separately and behind a toggle.
#
# Empty for run 2, and that is a finding rather than an oversight. Run 1 had
# two entries here (a quote attributed to t1022, which contains no such
# message, and one to t0056, which never uses the word). For run 2 all 88
# quoted spans were checked mechanically by tools/eval_quotes.py and the 27
# that are not verbatim were then read individually: every one is an elision,
# a truncation, or a compression of real text. None is an invention, so there
# is nothing to flag in red.
KNOWN_BAD: dict[str, str] = {}

IDENT = re.compile(r"\b((?:E|P)\d{1,3}(?:\.\d)?i?|t\d{4}(?:-e\d+)?|crm732#[\w.]+)\b")


@functools.lru_cache(maxsize=1)
def ident_names() -> dict[str, str]:
    """{identifier: human-readable name}, for hover titles.

    A reader of this page sees "E12" and "P108i" in dense prose and chips.
    The identifier alone is exactly the failure the concept dossier already
    fixes on the CLI side: an anonymous integer tells you nothing, and P177
    went unnoticed for E13 while sitting 17th in a list of them.

    Covers all five ontology buckets:
      * classes and properties get their `full_name` ("E12 Production"),
        which already carries the id, so the title reads as a complete label
      * the inverse direction (P108i) gets the inverse name, because that is
        what the reader is being shown -- "is produced by", not "has produced"
      * property-of-property ids (P14.1) name their parent, since the id is
        meaningless without it
      * historical ids say so, rather than appearing to be unknown
      * extension ids carry their model, because "S13" alone does not say
        CRMsci

    Absent ids simply get no title. A missing tooltip is invisible; a wrong
    one is a lie, so nothing is guessed here.
    """
    path = PROJECT_ROOT / "data" / "ontology.json"
    if not path.exists():
        return {}
    onto = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, str] = {}

    # A handful of entries are declared only by the newer specification
    # (E100, P199, P200): 7.3.2 added them and the v7.1.3 XML never carried
    # them. They now live in `classes`/`properties` like everything else and
    # would otherwise be indistinguishable, so the source rides along in the
    # title -- a reader comparing two scope notes should be able to see that
    # one of them comes from a different document.
    def titled(ident: str, e: dict) -> str:
        name = e.get("full_name") or ident
        source = e.get("source")
        return f"{name} ({source})" if source else name

    for cid, e in (onto.get("classes") or {}).items():
        out[cid] = titled(cid, e)
    for pid, e in (onto.get("properties") or {}).items():
        out[pid] = titled(pid, e)
        inverse = e.get("inverse_name")
        if inverse:
            # P108i is not P108: it is the same property read the other way,
            # and the reader is looking at the inverse label.
            out[f"{pid}i"] = f"{pid}i {inverse} (inverse of {pid})"
    for pid, e in (onto.get("property_of_property") or {}).items():
        parent = e.get("of_property") or "?"
        rng = e.get("range")
        out[pid] = (f"{pid} {e.get('label') or ''} — a property of {parent}"
                    + (f", range {rng}" if rng else ""))
    for cid, e in (onto.get("historical") or {}).items():
        out.setdefault(cid, f"{cid} — not defined in v7.1.3 (deprecated vocabulary)")
    for cid, e in (onto.get("extensions") or {}).items():
        model = e.get("model") or "?"
        label = e.get("label")
        out.setdefault(cid, f"{cid} {label} ({model})" if label else f"{cid} ({model})")

    # data/ontology.json is built from the v7.1.3 XML, and 7.3.2 adds three
    # concepts it has never carried -- E100 Audio Item, P199 and P200. An
    # answer citing one of those is right, so it must not be the only
    # identifier on the page with no name. The 7.3.2 declarations carry the
    # full name in their heading; `setdefault` means the XML still wins
    # wherever it has an entry.
    docs = PROJECT_ROOT / "data" / "documents.jsonl"
    if docs.exists():
        with open(docs, encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                cid, heading = rec.get("concept_id"), rec.get("heading")
                if rec.get("kind") == "declaration" and cid and heading:
                    out.setdefault(cid, f"{heading} (CIDOC CRM v7.3.2)")
    return out


def ident_title(ident: str) -> str:
    """Title text for one identifier, or "" when nothing is known.

    `crm732#E12` resolves through to E12: the chunk is that concept's
    declaration, so the concept's name is the useful thing to show.
    """
    names = ident_names()
    if ident in names:
        return names[ident]
    if ident.startswith("crm732#"):
        inner = ident.split("#", 1)[1]
        if inner in names:
            return f"{names[inner]} — declaration, CIDOC CRM v7.3.2"
        if inner.startswith("s"):
            return "narrative passage, CIDOC CRM v7.3.2"
    return ""


@functools.lru_cache(maxsize=1)
def ident_re() -> "re.Pattern[str]":
    """Identifier pattern, built from the ids that actually exist.

    `IDENT` matches only the E/P shape, so every family identifier -- A2, S19,
    I5, AP18, R80 -- went unmarked and untitled, and run6 answers propose 23
    distinct extension classes. Widening the *shape* is the wrong fix and
    lib.ontology already records why: "TC46", "SC4" and "WG9" -- the ISO
    committee that standardises the CRM -- appear throughout the archive and
    look exactly like class ids.

    So the known ids are matched literally, longest first so P14.1 wins over
    P14 and P108i over P108. That set has already been filtered by
    `family_of`, which is where the committee-designator problem was solved;
    reusing it means this page cannot reintroduce the bug.

    The generic E/P shape stays as a trailing fallback, so an id this build's
    ontology does not carry still renders as a reference, exactly as before --
    just without a title.
    """
    known = sorted(ident_names(), key=len, reverse=True)
    parts = [re.escape(k) for k in known]
    parts += [r"crm732#[\w.]+", r"t\d{4}(?:-e\d+)?", r"(?:E|P)\d{1,3}(?:\.\d)?i?"]
    return re.compile(r"\b(" + "|".join(parts) + r")\b")


def marked(text: str) -> str:
    """Escape, then set identifiers in the mono face so they read as references.

    Identifiers that resolve also carry a `title`, so hovering gives the full
    name. A plain attribute rather than a scripted tooltip: this page is a
    single self-contained file that has to work from the filesystem, and the
    native tooltip needs nothing.
    """
    def wrap(m: re.Match) -> str:
        ident = m.group(1)
        title = ident_title(ident)
        if not title:
            return f"<code>{ident}</code>"
        # `text` was escaped before substitution, but `title` comes straight
        # from the ontology and has not been -- scope-note names contain
        # quotes and ampersands.
        return f'<code title="{html.escape(title, quote=True)}">{ident}</code>'

    return ident_re().sub(wrap, html.escape(text or ""))


def paras(text: str) -> str:
    chunks = [c.strip() for c in re.split(r"\n\s*\n", (text or "").strip()) if c.strip()]
    return "".join(f"<p>{marked(c)}</p>" for c in chunks) or "<p class='none'>—</p>"


def chips(items, cls="chip"):
    if not items:
        return "<span class='none'>none</span>"
    return "".join(f"<span class='{cls}'>{marked(str(i))}</span>" for i in items)


def citation_label(c) -> str:
    """Citations are strings or {"id", "quote"} objects; show the identifier."""
    if isinstance(c, dict):
        return str(c.get("id") or c.get("source") or "?")
    return str(c)


def load(answer_glob: str, verdict_glob: str, key_path: Path):
    cases = {c["case_id"]: c
             for c in json.loads((EVAL / "modelling_cases.json").read_text())}

    answers = {}
    for p in sorted(EVAL.glob(answer_glob)):
        a = json.loads(p.read_text())
        answers[a["case_id"]] = a

    # Decode the blinded slots back to runs; see the module docstring.
    key = json.loads(key_path.read_text()) if key_path.exists() else {}
    verdicts = {}
    for p in sorted(EVAL.glob(verdict_glob)) if verdict_glob else []:
        # The key lives beside the verdicts and matches the same glob; it is
        # the decoder, not a verdict.
        if p == key_path:
            continue
        raw = json.loads(p.read_text())
        for r in (raw if isinstance(raw, list) else [raw]):
            cid = r["case_id"]
            if "verdict_A" in r:
                slots = key.get(cid)
                if not slots:
                    raise SystemExit(
                        f"{p.name} is blinded but {cid} is missing from "
                        f"{key_path.name}; refusing to guess which slot is which")
                slot = "A" if slots["A"] == "run2" else "B"
                verdicts[cid] = {
                    "verdict": r[f"verdict_{slot}"],
                    "constraint_checked": r.get("constraint_decided_it"),
                    "better_modelling": r.get("better_modelling"),
                    "reasoning": r.get("reasoning"),
                }
            else:
                verdicts[cid] = r
    return cases, answers, verdicts


def record(cid, case, ans, verdict, n, total):
    bad = KNOWN_BAD.get(cid)
    rejected = ans.get("rejected_alternatives") or []
    rej_html = "".join(
        f"<li><span class='opt'>{marked(str(r.get('option', '?')))}</span>"
        f"<span class='why'>{marked(str(r.get('why_not', '')))}</span></li>"
        for r in rejected if isinstance(r, dict)
    ) or "<li class='none'>none offered</li>"

    scope = "outside the model" if ans.get("in_scope") is False else "within the model"
    scope_cls = "out" if ans.get("in_scope") is False else "in"

    machine = ""
    if verdict:
        rows = "".join(
            f"<div class='mrow'><dt>{html.escape(lbl)}</dt>"
            f"<dd>{marked(str(verdict.get(k)))}</dd></div>"
            for lbl, k in (("Constraint checked", "constraint_checked"),
                           ("Better modelling", "better_modelling"),
                           ("Reasoning", "reasoning"))
            if verdict.get(k)
        )
        v = html.escape(str(verdict.get("verdict", "?")))
        machine = (f"<div class='machine'><h4>Automated strict pass"
                   f"<span class='mv mv-{v}'>{v}</span></h4><dl>{rows}</dl></div>")

    flag = (f"<div class='flag'><strong>Citation problem confirmed by hand.</strong> "
            f"{marked(bad)}</div>") if bad else ""

    citations = [citation_label(c) for c in (ans.get("citations") or [])]
    queries = ans.get("queries_run") or []

    return f"""
<article class="record" id="{cid}">
  <header class="rhead">
    <div class="rid"><span class="seq">{n} / {total}</span><code>{cid}</code></div>
    <span class="kind">{html.escape(case.get('kind', ''))}</span>
  </header>

  <div class="field"><span class="lab">Situation</span><div class="val">{paras(case['case'])}</div></div>
  <div class="field"><span class="lab">Question</span><div class="val q">{paras(case['question'])}</div></div>
  <div class="field"><span class="lab">Why it is hard</span><div class="val hard">{paras(case.get('why_hard', ''))}</div></div>

  <div class="rule"><span>the model&rsquo;s answer</span></div>
  {flag}

  <div class="badges">
    <span class="badge b-{scope_cls}">{scope}</span>
    <span class="badge b-conf">confidence: {html.escape(str(ans.get('confidence', '?')))}</span>
  </div>

  <div class="field"><span class="lab">Recommendation</span><div class="val">{paras(ans.get('answer', ''))}</div></div>
  <div class="field"><span class="lab">Classes</span><div class="val">{chips(ans.get('classes_proposed'))}</div></div>
  <div class="field"><span class="lab">Properties</span><div class="val">{chips(ans.get('properties_proposed'))}</div></div>
  <div class="field"><span class="lab">Rejected</span><div class="val"><ul class="rejected">{rej_html}</ul></div></div>
  <div class="field"><span class="lab">Cited</span><div class="val">{chips(citations, 'chip cite')}</div></div>

  <details class="extra"><summary>Queries the model ran ({len(queries)})</summary>
    <ol class="queries">{''.join(f'<li><code>{html.escape(str(q))}</code></li>' for q in queries)}</ol>
  </details>

  <details class="extra machines"><summary>Machine assessment &mdash; unreliable, read after you decide</summary>
    <p class="caveat">Graded blind, without knowing which system version produced the answer.
    The same rubric once scored an earlier round of answers 17 of 24 &ldquo;correct&rdquo;; re-run
    blind, it scored those same answers 2 of 24. Treat this as another opinion, not as evidence.</p>
    {machine}
  </details>

  <div class="rule"><span>your verdict</span></div>
  <fieldset class="judge" data-case="{cid}">
    <legend class="sr-only">Verdict for {cid}</legend>
    <div class="opts">
      {''.join(f'''<label><input type="radio" name="v-{cid}" value="{v}"><span>{v}</span></label>'''
               for v in ("correct", "suboptimal", "wrong", "unsupported", "unsure"))}
    </div>
    <label class="notes-l"><span class="lab">Notes</span>
      <textarea rows="2" placeholder="What is wrong, or what the right modelling is"></textarea></label>
  </fieldset>
</article>"""


def main():
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--answers", default="manswer2-*.json",
                    help="glob under data/eval for the answers to review")
    ap.add_argument("--verdicts", default="mstrict2-*.json",
                    help="glob for machine verdicts; empty string to omit them")
    ap.add_argument("--key", default="mstrict2-blind-key.json",
                    help="slot->run map for blinded verdicts (see module docstring)")
    ap.add_argument("--out", default="eval-review.html")
    ap.add_argument("--storage-key", default=None,
                    help="localStorage key; defaults to one derived from --answers "
                         "so a change of answers cannot inherit stale verdicts")
    args = ap.parse_args()

    cases, answers, verdicts = load(args.answers, args.verdicts, EVAL / args.key)
    if not answers:
        raise SystemExit(f"no answers matched {args.answers!r} under {EVAL}")

    ids = [c for c in sorted(cases) if c in answers]
    missing = sorted(set(cases) - set(ids))
    total = len(ids)

    records = "".join(
        record(cid, cases[cid], answers[cid], verdicts.get(cid), n, total)
        for n, cid in enumerate(ids, 1)
    )
    nav = "".join(
        f'<li><a href="#{cid}" data-nav="{cid}"><span class="dot"></span>'
        f'<code>{cid}</code><em>{html.escape(cases[cid].get("kind", ""))}</em></a></li>'
        for cid in ids
    )

    n_cites = sum(len(answers[c].get("citations") or []) for c in ids)
    storage_key = args.storage_key or (
        "crm-modelling-review-" + re.sub(r"[^a-z0-9]+", "-", args.answers.lower()).strip("-"))

    out = PROJECT_ROOT / args.out
    out.write_text(TEMPLATE.format(records=records, nav=nav, total=total,
                                   n_cites=n_cites, storage_key=storage_key),
                   encoding="utf-8")
    size = out.stat().st_size
    print(f"wrote {out.name} — {total} cases, {n_cites} citations, {size:,} bytes")
    print(f"  localStorage key: {storage_key}")
    if missing:
        print(f"  no answer for: {', '.join(missing)}")


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CIDOC CRM modelling evaluation &mdash; review sheet</title>
<style>
:root {{
  --ground:#F3F5F3; --surface:#FFFFFF; --ink:#171D1B; --muted:#5C6864; --faint:#8A9691;
  --rule:#DAE0DC; --accent:#17605A; --accent-soft:#E3EDEB; --flag:#9A3B2C; --flag-soft:#F7E8E4;
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Georgia,serif;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
}}
@media (prefers-color-scheme:dark) {{
  :root {{ --ground:#101413; --surface:#171C1B; --ink:#E6EBE8; --muted:#9AA6A2; --faint:#6E7A76;
    --rule:#29332F; --accent:#63B5AD; --accent-soft:#16302D; --flag:#D98673; --flag-soft:#2E1A16; }}
}}
:root[data-theme="dark"] {{ --ground:#101413; --surface:#171C1B; --ink:#E6EBE8; --muted:#9AA6A2;
  --faint:#6E7A76; --rule:#29332F; --accent:#63B5AD; --accent-soft:#16302D; --flag:#D98673; --flag-soft:#2E1A16; }}
:root[data-theme="light"] {{ --ground:#F3F5F3; --surface:#FFFFFF; --ink:#171D1B; --muted:#5C6864;
  --faint:#8A9691; --rule:#DAE0DC; --accent:#17605A; --accent-soft:#E3EDEB; --flag:#9A3B2C; --flag-soft:#F7E8E4; }}

* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--ground); color:var(--ink); font-family:var(--serif);
  font-size:17px; line-height:1.62; overflow-wrap:break-word; }}
code, .chip, .queries li {{ overflow-wrap:anywhere; }}
code {{ font-family:var(--mono); font-size:.86em; color:var(--accent);
  background:var(--accent-soft); padding:.08em .32em; border-radius:2px; }}
/* An identifier whose full name is known is hoverable. Marked so the reader
   can tell which ones will answer, instead of hovering hopefully over all of
   them -- an affordance nobody can see is not an affordance. Dotted rather
   than solid so it does not read as a link: there is nowhere to click. */
code[title] {{ cursor:help; text-decoration:underline dotted currentColor;
  text-underline-offset:.18em; text-decoration-thickness:from-font; }}
@media (hover:none) {{
  /* Touch devices have no hover and will not show a title, so the hint would
     be a promise the page cannot keep. */
  code[title] {{ text-decoration:none; cursor:auto; }}
}}
.sr-only {{ position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); }}

.wrap {{ display:grid; grid-template-columns:264px minmax(0,1fr); gap:0; align-items:start; }}
@media (max-width:900px) {{ .wrap {{ grid-template-columns:1fr; }} .rail {{ position:static !important; height:auto !important; }} }}

.rail {{ position:sticky; top:0; height:100vh; overflow-y:auto; border-right:1px solid var(--rule);
  background:var(--surface); padding:22px 16px 40px; }}
.rail h1 {{ font-size:15px; line-height:1.35; margin:0 0 4px; text-wrap:balance; }}
.rail .sub {{ font-family:var(--sans); font-size:11.5px; color:var(--muted); margin:0 0 16px; }}
.progress {{ font-family:var(--sans); font-size:11px; text-transform:uppercase; letter-spacing:.09em;
  color:var(--muted); border-top:1px solid var(--rule); border-bottom:1px solid var(--rule);
  padding:9px 0; margin-bottom:14px; display:flex; justify-content:space-between; }}
.progress b {{ color:var(--accent); font-variant-numeric:tabular-nums; }}
.rail ul {{ list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:1px; }}
.rail a {{ display:grid; grid-template-columns:9px 1fr; gap:7px; align-items:baseline;
  text-decoration:none; color:var(--ink); padding:5px 6px; border-radius:3px; }}
.rail a:hover {{ background:var(--accent-soft); }}
.rail a code {{ background:none; padding:0; font-size:11.5px; color:inherit; }}
.rail a em {{ display:block; grid-column:2; font-family:var(--sans); font-style:normal;
  font-size:10.5px; color:var(--faint); }}
.dot {{ width:7px; height:7px; border-radius:50%; border:1.5px solid var(--rule); margin-top:5px; }}
.rail a.done .dot {{ background:var(--accent); border-color:var(--accent); }}
.actions {{ display:flex; gap:6px; margin-top:18px; }}
button {{ font-family:var(--sans); font-size:11.5px; padding:6px 10px; border:1px solid var(--rule);
  background:var(--surface); color:var(--ink); border-radius:3px; cursor:pointer; }}
button:hover {{ border-color:var(--accent); color:var(--accent); }}
button:focus-visible, a:focus-visible, input:focus-visible, textarea:focus-visible {{
  outline:2px solid var(--accent); outline-offset:2px; }}
#export.pending {{ border-color:var(--flag); color:var(--flag); font-weight:600; }}
.savestate {{ font-family:var(--sans); font-size:10.5px; color:var(--faint); margin-top:8px; }}
.savestate.pending {{ color:var(--flag); }}

main {{ padding:44px 40px 120px; max-width:78ch; }}
@media (max-width:900px) {{ main {{ padding:28px 20px 80px; }} }}
.intro {{ border-bottom:2px solid var(--ink); padding-bottom:26px; margin-bottom:10px; }}
.intro h2 {{ font-size:30px; line-height:1.18; margin:0 0 12px; text-wrap:balance; letter-spacing:-.012em; }}
.intro p {{ margin:0 0 11px; color:var(--muted); }}
.intro strong {{ color:var(--ink); }}
.note {{ background:var(--accent-soft); border-left:3px solid var(--accent); padding:13px 16px;
  margin:16px 0 0; font-size:15px; }}
.note p {{ margin:0 0 8px; color:var(--ink); }}
.note p:last-child {{ margin:0; }}
.howto {{ font-size:15px; color:var(--muted); border-top:1px solid var(--rule);
  margin-top:18px; padding-top:14px; }}
.howto strong {{ color:var(--ink); }}

.record {{ border-bottom:1px solid var(--rule); padding:40px 0 34px; }}
.rhead {{ display:flex; justify-content:space-between; align-items:baseline; gap:14px; margin-bottom:20px; }}
.rid {{ display:flex; align-items:baseline; gap:10px; }}
.seq {{ font-family:var(--sans); font-size:11px; letter-spacing:.09em; color:var(--faint);
  font-variant-numeric:tabular-nums; }}
.rid code {{ font-size:13px; }}
.kind {{ font-family:var(--sans); font-size:10.5px; text-transform:uppercase; letter-spacing:.1em;
  color:var(--muted); border:1px solid var(--rule); padding:3px 8px; border-radius:2px; }}

.field {{ display:grid; grid-template-columns:112px minmax(0,1fr); gap:18px; margin-bottom:15px; }}
@media (max-width:640px) {{ .field {{ grid-template-columns:1fr; gap:3px; }} }}
.lab {{ font-family:var(--sans); font-size:10.5px; text-transform:uppercase; letter-spacing:.1em;
  color:var(--faint); padding-top:5px; }}
.val p {{ margin:0 0 9px; }} .val p:last-child {{ margin:0; }}
.val.q p {{ font-size:19px; line-height:1.5; }}
.val.hard p {{ color:var(--muted); font-size:15.5px; }}
.none {{ color:var(--faint); font-style:italic; }}

.rule {{ display:flex; align-items:center; gap:12px; margin:28px 0 18px; }}
.rule::before, .rule::after {{ content:""; height:1px; background:var(--rule); flex:1; }}
.rule span {{ font-family:var(--sans); font-size:10px; text-transform:uppercase; letter-spacing:.16em;
  color:var(--faint); }}

.badges {{ display:flex; gap:7px; margin-bottom:15px; flex-wrap:wrap; }}
.badge {{ font-family:var(--sans); font-size:11px; padding:3px 9px; border-radius:2px;
  border:1px solid var(--rule); color:var(--muted); }}
.badge.b-out {{ border-color:var(--flag); color:var(--flag); background:var(--flag-soft); }}
.chip {{ display:inline-block; font-family:var(--mono); font-size:12.5px; padding:2px 7px;
  margin:0 4px 4px 0; border-radius:2px; background:var(--accent-soft); color:var(--accent); }}
.chip.cite {{ background:none; border:1px solid var(--rule); color:var(--muted); }}
.chip code, .chip.cite code {{ background:none; padding:0; color:inherit; }}

/* The "option" is prose, not an identifier: median 63 chars, max 161, and 46 of
   59 run past 40. An auto-width first column with nowrap blew out to the full
   sentence and crushed the reason into a one-word ribbon, so these stack. */
ul.rejected {{ list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:11px; }}
ul.rejected li {{ display:block; border-left:2px solid var(--rule); padding-left:12px; }}
.opt {{ display:block; color:var(--flag); font-size:15.5px; line-height:1.5; }}
.why {{ display:block; color:var(--muted); font-size:15.5px; line-height:1.55; margin-top:2px; }}
.why::before {{ content:"why not: "; font-family:var(--sans); font-size:10.5px;
  text-transform:uppercase; letter-spacing:.09em; color:var(--faint); }}

.flag {{ background:var(--flag-soft); border-left:3px solid var(--flag); padding:12px 15px;
  margin-bottom:16px; font-size:15px; }}
.flag strong {{ color:var(--flag); }}

details.extra {{ margin-top:14px; }}
details.extra summary {{ font-family:var(--sans); font-size:11.5px; color:var(--muted);
  cursor:pointer; padding:5px 0; }}
details.extra summary:hover {{ color:var(--accent); }}
.queries {{ margin:6px 0 0; padding-left:22px; color:var(--muted); font-size:14px; }}
.queries code {{ background:none; padding:0; color:var(--muted); }}
.caveat {{ font-size:14px; color:var(--flag); margin:6px 0 12px; }}
.machine {{ border-left:2px solid var(--rule); padding-left:14px; margin-bottom:14px; }}
.machine h4 {{ font-family:var(--sans); font-size:11.5px; margin:0 0 6px; display:flex;
  align-items:center; gap:8px; color:var(--muted); font-weight:600; }}
.mv {{ font-family:var(--mono); font-size:11px; padding:1px 6px; border-radius:2px;
  background:var(--accent-soft); color:var(--accent); }}
.mv-wrong, .mv-unsupported, .mv-flawed, .mv-scope_error {{ background:var(--flag-soft); color:var(--flag); }}
.machine dl {{ margin:0; }}
.mrow {{ display:grid; grid-template-columns:120px minmax(0,1fr); gap:12px; margin-bottom:5px; }}
.mrow dt {{ font-family:var(--sans); font-size:10.5px; text-transform:uppercase; letter-spacing:.08em;
  color:var(--faint); }}
.mrow dd {{ margin:0; font-size:14.5px; color:var(--muted); }}

.judge {{ border:1px solid var(--rule); border-radius:4px; padding:14px 16px; margin:0;
  background:var(--surface); }}
.judge.answered {{ border-color:var(--accent); }}
.opts {{ display:flex; gap:6px; flex-wrap:wrap; margin-bottom:11px; }}
.opts label {{ position:relative; }}
.opts input {{ position:absolute; opacity:0; width:0; height:0; }}
.opts span {{ display:inline-block; font-family:var(--sans); font-size:12px; padding:5px 12px;
  border:1px solid var(--rule); border-radius:14px; cursor:pointer; color:var(--muted); }}
.opts input:checked + span {{ background:var(--accent); border-color:var(--accent); color:var(--surface); }}
.opts input:focus-visible + span {{ outline:2px solid var(--accent); outline-offset:2px; }}
.notes-l {{ display:grid; grid-template-columns:112px minmax(0,1fr); gap:18px; align-items:start; }}
@media (max-width:640px) {{ .notes-l {{ grid-template-columns:1fr; gap:3px; }} }}
textarea {{ width:100%; font-family:var(--serif); font-size:15px; padding:8px 10px;
  border:1px solid var(--rule); border-radius:3px; background:var(--ground); color:var(--ink);
  resize:vertical; }}

.nostore {{ background:var(--flag-soft); color:var(--flag); border-bottom:1px solid var(--flag);
  padding:10px 18px; font-family:var(--sans); font-size:13px; }}
.nostore strong {{ font-weight:600; }}
@media print {{
  .rail, .actions, .judge .opts input {{ display:none; }}
  .wrap {{ grid-template-columns:1fr; }}
  details.extra {{ display:none; }}
  .record {{ page-break-inside:avoid; }}
}}
@media (prefers-reduced-motion:reduce) {{ * {{ animation:none !important; transition:none !important; }} }}
</style>
</head>
<body>
<div id="nostore" class="nostore" hidden>Your browser is not saving progress for this file.
Use <strong>Export JSON</strong> before closing, or your verdicts will be lost.</div>

<div class="wrap">
<nav class="rail">
  <h1>Modelling evaluation</h1>
  <p class="sub">CIDOC CRM &mdash; human review</p>
  <div class="progress"><span>judged</span><span><b id="done">0</b> / {total}</span></div>
  <ul>{nav}</ul>
  <div class="actions">
    <button id="export">Export JSON</button>
    <button id="clear">Clear</button>
  </div>
  <p class="savestate" id="savestate"></p>
</nav>

<main>
  <div class="intro">
    <h2>Twenty-four modelling cases, and what the search system advised</h2>
    <p>Each case is a real documentation problem written by someone who had never seen the
    CIDOC CRM corpus. They were screened so that no case restates an example already in the
    specification or the mailing list. The answers below were produced using only the archive
    search tools.</p>
    <p><strong>There is no expected answer.</strong> A reference answer was deliberately not
    written: you are the authority here. Read the case, read the advice, and judge whether it is
    what the CRM actually prescribes.</p>
    <div class="note">
      <p><strong>What has been checked already, and what has not.</strong> All {n_cites}
      citations were resolved mechanically &mdash; every thread, issue and specification section
      cited is real. Quotations in the prose were checked too: most appear verbatim in a source,
      and every one that did not was read by hand and turned out to be an elision or a shortened
      paraphrase of real text rather than an invention.</p>
      <p>None of that says the advice is <em>right</em>. A citation can resolve, and the quote can
      be accurate, and the modelling can still be wrong. That judgement is the part only you can
      make, and it is the reason this sheet exists.</p>
      <p><strong>The machine verdicts are hidden behind a toggle on purpose.</strong> The same
      automated rubric scored an earlier round of answers 17 of 24 &ldquo;correct&rdquo;; re-run
      blind against the same answers, it scored them 2 of 24. Please reach your own verdict before
      opening one.</p>
    </div>
    <p class="howto"><strong>How to use this.</strong> Work down the list on the left; your
    verdicts and notes save in this browser as you go. When you are done, press
    <strong>Export JSON</strong> and send the downloaded file back &mdash; that is the only way
    your verdicts reach anyone. Nothing is uploaded; this page is a single file with no
    network access.</p>
  </div>
  {records}
</main>
</div>

<script>
(function () {{
  // Versioned with the answers: a reviewer who worked through an earlier
  // sheet must not have those verdicts pre-filled against different answers.
  var KEY = "{storage_key}";
  var store = {{}}, usable = false;
  try {{
    localStorage.setItem(KEY + "-probe", "1");
    localStorage.removeItem(KEY + "-probe");
    usable = true;
    store = JSON.parse(localStorage.getItem(KEY) || "{{}}");
  }} catch (e) {{ store = {{}}; }}
  if (!usable) document.getElementById("nostore").hidden = false;

  var sets = Array.prototype.slice.call(document.querySelectorAll(".judge"));
  var exported = false;   // has the CURRENT state been written to a file?

  function count() {{
    return sets.filter(function (fs) {{
      var s = store[fs.dataset.case];
      return !!(s && s.verdict);
    }}).length;
  }}

  function paint() {{
    var n = count();
    sets.forEach(function (fs) {{
      var id = fs.dataset.case, saved = store[id];
      var answered = !!(saved && saved.verdict);
      fs.classList.toggle("answered", answered);
      var link = document.querySelector('[data-nav="' + id + '"]');
      if (link) link.classList.toggle("done", answered);
    }});
    document.getElementById("done").textContent = n;

    // The one path where work actually vanishes is verdicts entered but never
    // exported, so say so plainly rather than relying on the unload dialog,
    // which browsers render as generic text the reviewer cannot act on.
    var pending = n > 0 && !exported;
    document.getElementById("export").classList.toggle("pending", pending);
    var s = document.getElementById("savestate");
    s.classList.toggle("pending", pending);
    s.textContent = n === 0 ? ""
      : pending ? "Not yet exported \\u2014 press Export JSON before you finish."
                : "Exported. Send the downloaded file back.";
  }}

  sets.forEach(function (fs) {{
    var id = fs.dataset.case;
    var saved = store[id] || {{}};
    if (saved.verdict) {{
      var r = fs.querySelector('input[value="' + saved.verdict + '"]');
      if (r) r.checked = true;
    }}
    var ta = fs.querySelector("textarea");
    if (saved.notes) ta.value = saved.notes;

    fs.addEventListener("change", function (e) {{
      if (e.target.type !== "radio") return;
      store[id] = store[id] || {{}};
      store[id].verdict = e.target.value;
      exported = false;
      save();
    }});
    ta.addEventListener("input", function () {{
      store[id] = store[id] || {{}};
      store[id].notes = ta.value;
      exported = false;
      save();
    }});
  }});

  var t;
  function save() {{
    clearTimeout(t);
    t = setTimeout(function () {{
      try {{ localStorage.setItem(KEY, JSON.stringify(store)); }} catch (e) {{}}
      paint();
    }}, 120);
  }}

  window.addEventListener("beforeunload", function (e) {{
    if (count() === 0 || exported) return;
    e.preventDefault();
    e.returnValue = "";   // required for the prompt to show in some browsers
    return "";
  }});

  document.getElementById("export").addEventListener("click", function () {{
    var rows = sets.map(function (fs) {{
      var id = fs.dataset.case, s = store[id] || {{}};
      return {{ case_id: id, verdict: s.verdict || null, notes: s.notes || "" }};
    }});
    var blob = new Blob([JSON.stringify(rows, null, 2)], {{ type: "application/json" }});
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "human-verdicts.json";
    a.click();
    URL.revokeObjectURL(a.href);
    exported = true;
    paint();
  }});

  document.getElementById("clear").addEventListener("click", function () {{
    if (!confirm("Clear all verdicts and notes on this device?")) return;
    store = {{}};
    exported = true;   // nothing left to lose
    try {{ localStorage.removeItem(KEY); }} catch (e) {{}}
    sets.forEach(function (fs) {{
      fs.querySelectorAll("input").forEach(function (i) {{ i.checked = false; }});
      fs.querySelector("textarea").value = "";
    }});
    paint();
  }});

  paint();
}})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
