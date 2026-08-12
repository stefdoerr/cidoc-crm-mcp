# The Bayeux Tapestry in CIDOC CRM — report

Turtle file: `v2_bayeux.ttl`, same directory.

## 1. The argumentation

### The object itself: E22 Human-Made Object, not E84 or E73

The tapestry is `crm:E22_Human-Made_Object`. `crm_concept('E22')` gives exactly
the fit: "persistent physical objects... that have physical boundaries that
separate them completely... from other objects" — a single 68-metre hanging,
however long, is one bounded artefact.

Two alternatives were live because the tapestry is famous for *carrying*
information (pictures, Latin captions), not just for being a textile:

- **E84 Information Carrier** — the obvious class for "a physical thing that
  carries information" — turns out not to exist any more. It is absent from
  `crm_list('CRMbase')` entirely, and `crm_concept('E22')`'s debate list shows
  why: thread t1054, "Deletion of E84 Information Carrier and redistribution
  of examples," 2018-01-04, decided. I did not read the thread itself (the
  absence from the current class list already answers the question I had),
  but I flag that I'm relying on the deletion record rather than the full
  discussion.
- **E73 Information Object** — rejected because it classes the *content*,
  not the *object*; it would put the tapestry's physical bulk, its linen and
  wool, its 68 metres, in the wrong ontological box. The content is instead
  reached from the object via `P62_depicts` and `P128_carries` (below),
  which is exactly the shortcut/expansion relationship `crm_concept('P62')`
  describes: P62 "is a shortcut of the more fully developed path... P65 shows
  visual item, E36 Visual Item, P138 represents." I used the shortcut rather
  than instantiating an intermediate E36 Visual Item, since the full path
  adds a node without adding information I could support from the article.

The nine **linen panels** are also `E22_Human-Made_Object` (each was
embroidered separately, then joined), linked with `P46_is_composed_of` and
counted with `P57_has_number_of_parts`. I did not instantiate all nine —
the article distinguishes them only by a length range and by the visible
seam at scene 13 — so one representative panel resource carries the
shared material/technique facts, and the note on it explains the seam
detail rather than reifying it as a separate `E26 Physical_Feature`. That is
a depth-vs-breadth call: nine near-identical resources would not have taught
a reader anything nine did not.

The 1941 **fragments** are `E19_Physical_Object`, not `E22`, on purpose: once
cut away, "fragments" is the article's own word, and E22's scope note
requires "physical boundaries that separate them completely... in an
objective way" — a torn-off scrap does not obviously clear that bar the way
the whole hanging does. This is one of the shakier calls in the model; a
reviewer could reasonably keep them at E22 too.

### Making: E12 Production, with the hedges pulled out into E13

`crm_concept('E12')` fits the embroidering without dispute. The two
substantive questions are *who* commissioned it and *who* made it, and the
article hedges both ("it is likely," "probably," "most probably"). Rather
than assert `P14_carried_out_by` on the Production event as flat fact, I used
`crm:E13_Attribute_Assignment` for each: one node attributing the
commissioning to Odo, one attributing the embroidery to an unnamed group of
women needleworkers. `crm_concept('E13')`'s own scope note is the
justification, almost verbatim: it exists precisely so "the maintaining team
is in general neutral to the validity of the... assertion, but registers
someone else's opinion." `crm_docs` on P140/P141 confirmed the exact shape —
P140 assigned_attribute_to the object, P141 assigned the value, P177
assigned_property_of_type the kind of claim — from its own worked example
("the Current Ownership Assessment... assigned attribute to Martin Doerr's
silver cup"). Each E13 node's note also records the rejected alternatives by
name (Queen Matilda and her ladies-in-waiting per French legend; Carola
Hicks's suggestion of Edith of Wessex) rather than giving them their own
contradictory E13 nodes — the scope note explicitly permits multiple
competing E13s, but with two live rival-person hypotheses and one clear
leading one, I judged that writing out the alternatives as text served a
reviewer better than tripling the RDF for claims the article itself doesn't
weigh evenly.

I made a different call for the **designer** (as opposed to maker):
Howard B. Clarke's case for Scolland, Abbot of St Augustine's, and Christine
Grainge's case for Lanfranc. These are each a single named scholar's
proposal, explicitly speculative in the article's own language ("has
proposed," "has argued"), with no comparably-weighted consensus behind
either the way the Odo commission has "20th-century scholarly analysis"
behind it. I recorded this dispute only as a note on the Production event,
with no E21 Person resource and no E13 for either name. This is the most
debatable editorial line in the whole model — I can defend not planting two
more contested-attribution nodes for two individually weak claims, but a
reviewer who thinks E13 exists for exactly this case, no matter how weak the
claim, would be right to push back.

### Dates given only vaguely

The article's headline claim is vague on purpose ("thought to date to the
11th century, within a few years of the battle"); the more specific "1070s"
belongs to the Odo hypothesis specifically. I formalised the Production
`E52_Time-Span` as 1070-01-01–1079-12-31 — a full decade turned into an
actual year range, which the article never does — and said so directly in
the time-span's own note, including that a cited historian's "possibly
completed by 1077" would narrow it further but is itself doubly hedged
("possibly," and tied to a dedication-date theory I don't otherwise assert),
so I left the wider decade rather than quietly adopting the tighter guess.
The two E13 attributions got a "20th century" time-span (1900–1999) on the
same reasoning — the article says only "scholarly analysis in the 20th
century," and I've converted a century name into an explicit boundary date
pair the same way.

### Finding: two different events, deliberately modelled two different ways

The article gives two things that could be called "finding," and they are
not the same kind of event, so I did not model them the same way:

1. The tapestry itself was **never lost**. It hung in Bayeux Cathedral
   annually from at least 1476 (per the earliest surviving inventory) through
   1728. What happened in 1729–1730 is that Bernard de Montfaucon traced an
   unidentified sketch back to it and published it — making it known to
   *scholarship*, not to anyone locally. I modelled both the 1476 inventory
   and Montfaucon's publication as `E31_Document`s that `P70_documents` the
   tapestry, with Montfaucon's creation event (`E65_Creation`,
   `P14_carried_out_by` him, dated 1729/1730) standing in for the
   "rediscovery." I deliberately did not reach for a Discovery/Excavation
   class: I called `crm_thread('t0689')`, a 2013 SIG proposal for exactly an
   `Exx Discovery (Finding)` subclass of E7 Activity for archaeological
   finds, and it was never ratified — it isn't in the current class list.
   Stephen Stead's advice in that same thread, when no dedicated class
   exists, was "the alternative is just to type an instance of E7 Activity."
   I went one step lighter than even that fallback, because the existing
   Creation/Document/P70 pattern already carries everything the article
   supports, without instantiating a generic Activity that would need its
   own invented `P2_has_type` label to mean anything.
2. The 1941–2023 fragments **were** genuinely lost — taken by a German
   "ancestral heritage" research team, whereabouts unknown for 82 years.
   This is the actual case the unratified Discovery proposal targeted, so I
   used Stephen Stead's fallback for real here: a plain `E7_Activity`, typed
   with a local `P2_has_type` "rediscovery," connected to the fragments via
   `P12_occurred_in_the_presence_of` rather than the proposal's own rejected
   draft property `Pxx_has_found` (never adopted) or `P16_used_specific_object`
   (wrong semantics — that property is for tools or materials consumed in an
   activity, per its own scope note, not for the thing an activity is about).
   Stead's 2013 comment that the range "should be E18 Physical Thing" and
   the property "should be a sub-property of P12 not P12i" is exactly what
   I followed, just without minting the new property he was arguing for.

### Ownership versus custody: one Acquisition, several Moves

The 1792 revolutionary confiscation is the only point where the article's
own language ("confiscated as public property") supports a change of legal
title, so it is the only `E8_Acquisition` in the model
(`crm_concept('E8')`'s scope note: transfers of legal ownership, as opposed
to `E10_Transfer_of_Custody`'s physical custody). Every later relocation —
to Paris in 1803, back to Bayeux in 1804, to the Louvre by the Gestapo in
1944, back to Bayeux in 1945, the 2025–2026 removal to London — is modelled
as `E9_Move`, and the two loans/returns of physical control (the fragments
in 2026, the whole tapestry to the British Museum in 2026–2027) as
`E10_Transfer_of_Custody`. The article's own words track this distinction
even where it doesn't say so explicitly: after 1792 it describes "the
council" disputing custody with "the cathedral," never ownership, and a loan
is definitionally custody without title. I did not model the failed 1944
Himmler order to move the tapestry to Berlin — the SS "attempted to take
possession... but by then the Louvre was again in French hands" — as a
second Move, because it never actually happened; it's recorded only as a
note on the Move that did.

### Two hedges I flagged as genuinely uncertain in the model text, not just in this report

- **Halley's Comet.** The tapestry depicts it (scene 32), and `P62_depicts`
  is happy to take an untyped E1 as its range. But I left the comet resource
  with no class more specific than `E1_CRM_Entity` on purpose, because
  `crm_thread('t0498')` — the CRM SIG's own "questionable Sunrise" debate —
  is an unresolved argument among the editors themselves about whether a
  natural phenomenon with no actor, no participant, and no interaction is an
  `E5_Event` at all, or a mere time-span, or a "situation" the CRM doesn't
  yet model ("we are touching the notion of situation we have avoided to
  model so far" — Martin Doerr, in that thread). A comet's apparition is the
  same case as a sunrise. Asserting `E5` would answer a question the model's
  own editors haven't answered.
- **The tapestry's "current location."** As of the article, the Bayeux
  museum is closed for renovation and the tapestry is on loan to the British
  Museum. I did not assert a single `P55_has_current_location`; I gave both
  Bayeux and London as `P53_has_former_or_current_location` and let the dated
  Move/Transfer-of-Custody events carry the actual sequence. This is the
  clearest place the model refuses to flatten an ambiguity the source itself
  leaves open.

### Things I'd flag to a reviewer as shaky, gathered in one place

- Fragments as E19 rather than E22 (above) — defensible, not obvious.
- `PartRemoval1941`'s place (Bayeux) is my inference from the surrounding
  timeline, not a stated fact — flagged in its own note.
- The designer dispute (Scolland/Lanfranc) left as text only, not as E13s —
  the single editorial call in this model I'm least sure a reviewer would
  agree with.
- `crm_validate_rdf`'s completeness pass, run at the end, turned up a
  residual list of "partly stated" properties I chose not to chase further:
  one linen panel without its own location (it's never separately located
  from the whole — a convention, not a gap), Montfaucon's creation event and
  the 1476 inventory's compiler each missing one of carried-out-by/took-
  place-at (the article genuinely doesn't say), and three E9 Moves with no
  named actor (nobody is named as having executed the 1804 or 1945 returns,
  or the 2025–26 removal to London). All of these are source gaps, not
  modelling oversights, and I've said so rather than inventing a "person or
  organisation unknown" filler.

## 2. The tools

**Final validator line:**
`Verdict: PASSED -- every link resolves within its declared domain and range, every rdf:type is a class this model declares, and every owl:inverseOf claim holds (the conditions \`search.py validate --rdf\` exits 0 on).`
(reached after two rounds of fixes — see below.)

**MCP calls made: 24**, all succeeded on the first attempt (nothing needed a
retry). Roughly:
- 1 × `--list`
- 8 × `crm_concept` (E22, E12, E13, P62, P14, E5, E8, E9)
- 1 × `crm_list('CRMbase')`, to get every RDF local name and hyphenation
  right in one call instead of one `crm_concept` per identifier
- 3 × `crm_search`, 3 × `crm_docs`, 1 × `crm_show`, 2 × `crm_thread`
  (t0689 Discovery/Finding proposal; t0498 "questionable Sunrise") — all
  spent chasing the modelling forks above (commissioning, uncertainty,
  discovery, P177 usage)
- 5 × `crm_validate_rdf` — two plain validations that each caught one real
  error (P4 on a non-temporal E31 Document; a P3 note on an untyped
  subject), one completeness pass that surfaced the "partly stated" list
  above, a round of fixes, then a final plain and a final completeness pass

The two validation failures were genuine modelling bugs of mine (attaching
`P4_has_time-span` directly to a Document instead of to a Creation event;
leaving a resource fully untyped when I still wanted to attach a note to
it), not tool problems — both were exactly what the tool is for.

**What I wanted to ask and couldn't:** whether CRM has a standard `E55_Type`
vocabulary term for roles like "commissioner" or "patron" the way, say,
place authorities exist elsewhere — `crm_concept('P14')`'s own example uses
"master craftsman" as a one-off illustration, not a controlled term, and
nothing in `--list` suggests CRM ships one. I don't think this is missing
functionality so much as the ontology's own design (E55 Type is
deliberately open external vocabulary), but I had no way to ask the server
"is there a canonical term for X" short of guessing labels myself, which is
what I ended up doing (`bt:CommissionerRoleType`, `bt:MakerRoleType`, both
local, both mine). I also didn't get to check whether CRM has any
loan-specific refinement of `E10_Transfer_of_Custody` distinct from a
permanent transfer — I used the plain class for both the fragment return and
the British Museum loan and didn't chase whether that's the idiom or whether
there's SIG discussion distinguishing the two.

**Blunt feedback on the tools:**
- `crm_list(model)` is all-or-nothing per model — I wanted spellings for
  about fifteen specific identifiers and got all 273 CRMbase rows (39KB,
  auto-persisted to a file by the harness because it didn't fit inline). It
  worked, but a `crm_list({"ids": [...]})` mode would have been a much
  smaller ask for a client trying to just confirm spelling for a known set.
- Every `crm_search`/`crm_docs`/`crm_show`/`crm_thread` call printed an
  unauthenticated-Hugging-Face-Hub warning block to the console before the
  actual result. Harmless, but noisy across a couple dozen calls, and it's
  not clear to a caller whether it means results are degraded.
- `crm_validate_rdf`'s plain-mode output repeats a full `NOT_CRM` block for
  every single `rdfs:label` triple individually (58 of them here) rather
  than summarising "N label triples skipped, not CRM properties" once. The
  completeness-mode output, by contrast, is genuinely well designed — the
  partly-stated/never-stated split with counts and "likeliest oversights
  first" ordering was exactly the right shape for the self-check the brief
  asked for, and did the real work of separating my genuine source gaps
  from modelling conventions.
- Nothing else was missing, wrong, or confusing that I ran into; `crm_concept`,
  `crm_connect`'s domain/range info surfaced through `crm_list` and
  `crm_concept` together, and the thread/search/docs tools all did what
  their descriptions promised.
