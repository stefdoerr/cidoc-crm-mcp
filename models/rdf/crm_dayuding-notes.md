# Da Yu ding: modelling report

Source: the cached Wikipedia extract at `pages/Da_Yu_ding.txt`. Turtle file:
`v2_dayuding.ttl`. All CRM facts below were obtained from the MCP server
(`crm_concept`, `crm_connect`, `crm_list`, `crm_thread`, `crm_validate_rdf`);
none from the vendored ontology files or the archive search tool.

## 1. Argumentation

### The object and its class

`dayuding:DaYuDing` is `E22_Human-Made_Object`. This one had no real
alternative once the server confirmed `E22`'s scope note ("persistent
physical objects... purposely created by human activity... with physical
boundaries") over its siblings `E20_Biological_Object` and
`E25_Human-Made_Feature` — a cast bronze vessel is plainly the former, not
a feature of something else.

### Parts: body and legs, not a fixed leg count

I split the ding into two `E19_Physical_Object` parts (`Body`, `Legs`),
joined to the whole with `P46_is_composed_of`. I considered typing the
parts `E22_Human-Made_Object` like the whole, and rejected it: `E22` is for
things with their own "physical boundaries" and, implicitly, their own
production history; the legs and body were cast as one piece, with no
production event of their own, so `E19_Physical_Object` (the generic
material-object class `P46`'s range actually asks for) is the more honest
fit — it says "this is a distinguishable material part" without also
claiming "this was separately made."

I did **not** assert a leg count. The article contradicts itself in the
same paragraph: "The tripod is round, with three legs..." and then "its
four legs are engraved with animal face patterns." I flagged this
verbatim in an `rdfs:comment` on `dayuding:Legs` rather than picking a
number — silently resolving it would misrepresent what the source
actually says.

### Decoration: features with a type, not "depicts"

The taotie and animal-face patterns are `E25_Human-Made_Feature`, attached
with `P56_bears_feature` (confirmed by `crm_connect(E22, E25)`, which
returns exactly this property for an `E19`-typed subject). I rejected
`P62_depicts`: that property's range is `E1_CRM_Entity` and is meant for
figurative representation of some *identifiable subject* (a person, a
place, an event); a taotie pattern is a stylised, conventional motif, not
a picture of a specific referent the article names. Typing the feature
with `P2_has_type → E55_Type("taotie pattern")` records what kind of
decoration it is without overclaiming what it depicts.

### The inscription: one resource, not two

My first draft modelled the inscription as an `E34_Inscription` that
`P128_carries` a separate `E33_Linguistic_Object` holding the text.
`crm_validate_rdf` rejected it: `P128`'s domain is `E18_Physical_Thing`,
and `E34` is not physical — its own scope note says it is "not... the
physical embodiment... but the underlying prototype." I had the direction
backwards. The fix, and the more defensible model: `E34_Inscription` is
already a subclass of `E33_Linguistic_Object` by declaration, so one
resource double-typed as both carries all the content (text, language,
`P67_refers_to` the named people) without inventing a link CRM doesn't
provide. `crm_connect(E22, E34)` had told me the *ding itself*
`P128_carries` the inscription — that's the one carrying relationship
that actually exists, and it's now the only one in the file.

`P67_refers_to` points at King Kang, Yu, and Nan Gong — the inscription's
own named subjects, per the article's four-part summary of its content
(the moral history of Shang's fall, the charge to Yu, his appointment and
the inventory of 1,726 slaves, and Yu's own dedication). I did not try to
model the inventory's slave count as a separate `E54_Dimension`: that
would invent a formal structure (whose dimension, of what, measured how)
the article's one summary sentence doesn't support — a plain note carries
it more honestly.

### Production: who, and the King Kang hedge

`E12_Production` with `P108_has_produced` the ding and `P14_carried_out_by`
Yu — taken at face value from "Yu himself recording that he made this
tripod... for his deceased grandfather." I flag, but do not resolve, that
this is likely a patron speaking in the conventional first person of a
dedicatory bronze inscription rather than the literal caster; I looked for
a CRM way to qualify this (`P14.1_in_the_role_of`, confirmed via
`crm_concept('P14')`), but `crm_list('CRMbase')` shows the `.1`
qualifier-properties have no current RDF class declaration in this version
(`PC0`/`PC1`/`PC2`/`PC14` are listed explicitly as "archive-attested only;
no current declaration"). Rather than invent an RDF encoding for a
construct the server itself says isn't currently declared, I left `P14`
unqualified and put the caveat in a note.

The date is more interesting. The article separates two claims: the ding
"is **attributed to** King Kang of Zhou," on the strength of the Xiao Yu
ding (found alongside it) and stylistic comparison — versus the ding's own
inscription directly stating "his 23rd Year," which the article itself
converts to 997 BC. I considered reifying the King Kang attribution as an
`E13_Attribute_Assignment` (`P140_assigned_attribute_to` the Production,
`P141_assigned` King Kang, `P177_assigned_property_of_type`) — this is
exactly what `E13` is for. I rejected it: `crm_concept('E13')` shows
`P14_carried_out_by` and `P4_has_time-span` as required on the assignment
activity itself, and the article names neither *who* made this attribution
nor *when* — instantiating `E13` here would create an activity node with
its own required properties unfillable, which is worse than a plain note.
This judgement call is grounded in a real SIG position, not just mine: in
thread `t1263` ("Guidelines for representing uncertainty," Issue 349,
2019), Martin Doerr himself calls `E13` "computationally heavy" reification
and says the SIG still had no generic, lightweight uncertainty mechanism —
confirming CRM genuinely has no clean, ready-made way to tag "this claim
is attributed, not stated" short of a note.

I did add one thing the article doesn't literally assert: a `P86_falls_within`
link from the 997 BC production time-span to a separate "Western Zhou
dynasty, 1046–771 BC" period, because the article gives both figures
itself (as a broad classification up front, and a precise inscribed date
later) and the containment is simply true of both. I did **not** convert
either BC range into typed `xsd:date` literals with astronomical year
numbering (year *N* BC = −(*N*−1)) after `crm_validate_rdf` demonstrated
its underlying date parser can't parse negative years at all (see §2) —
plain-text `P3_has_note` carries these two dates instead. I did use
`xsd:date` literals for every CE date (1875, 1890, 1896, 1937, 1951, 1959,
2004), where the parser has no such problem.

I omitted `P7_took_place_at` on the Production entirely. The article gives
a find-place (Li Village) but never a place of manufacture, and those are
not the same claim — conflating them would be an invention the brief
specifically warns against.

### Finding: S19 Encounter Event, not a bespoke Discovery class

For "unearthed... in the Daoguang era," I used `crmsci:S19_Encounter_Event`
with `O19_encountered_object` and `O21_encountered_at`. I did not invent a
generic `E7_Activity` subtype myself, and I checked whether CRMbase itself
ever added one: `crm_thread('t0689')`, a 2013 SIG proposal to add exactly
such a class ("Discovery/Finding"), was never adopted — Stephen Stead's
objection stands in the record ("we do/try not to add classes... unless it
forms an anchor for some properties... What are the new properties that
justify the proposed new sub-class?"). CRMsci's later `S19_Encounter_Event`
is the SIG's actual, adopted answer to this need, which is why I used it
rather than typing a bare `E7_Activity` with a `P2_has_type` string. I left
`P14_carried_out_by` off the encounter: the article names no excavator, and
the era-only date ("Daoguang era, 1821–1851") is carried honestly as a
30-year bound rather than invented as a specific year.

### Ownership chain: acquisitions vs. custody, and where I stopped short

Each change of hands is its own `E8_Acquisition` (title) or
`E10_Transfer_of_Custody` (possession/administration only), per CRM's own
declared split between the two (`E8`'s scope note: "the CIDOC CRM therefore
models legal ownership... and physical custody... separately"). Concretely:

- **Song's first acquisition**: no `P23_transferred_title_from` — the
  article names no prior owner, and `E8`'s own scope note explicitly
  allows "the acquisition from an unknown source."
- **Zhou's expropriation and Song's recovery**: straightforward `E8`s,
  typed with my own `E55_Type` values ("expropriation," "recovery") since
  CRM doesn't standardise transaction-type vocabulary.
- **Yuan's purchase**: I found a real chronological problem here and did
  not paper over it. The article gives Song Jinjian's dates as
  1821–1863, then has him selling the ding to Yuan Baoheng "before winter
  1873" — ten years after the death date the same article gives him. I
  reproduced both figures as stated and flagged the contradiction in a
  note rather than silently assuming, say, that heirs conducted the sale.
- **The price**: `crm_connect('E8', 'E97')` returns only
  `P17_was_motivated_by` as a legal link between an Acquisition and a
  Monetary Amount — and that pairing turns out to be contested territory
  in the SIG itself. Thread `t0826` ("Money, money, money...", 2015) shows
  Dan Matei proposing `P16_used_specific_object`, Stephen Stead rejecting
  it as wrong ("unless you want to refer to a particular coin or note"),
  and Martin Doerr conceding the whole question of linking acquisitions to
  payment amounts was still an open, unresolved SIG issue. I used
  `P17_was_motivated_by` because it's the only thing `crm_connect` offers,
  not because I believe it's semantically right, and I say so in the note.
- **"Yuan may have sent it to Zuo"**: modelled as `E10_Transfer_of_Custody`
  (possession only), specifically because that is the weaker of the two
  possible claims ("did custody move" is a smaller claim than "did title
  move"), and the article's own hedge ("may have") is about the physical
  handover, not about whether Zuo eventually held the object (he plainly
  did — he later gifted it). CRM's own SIG record (again `t1263`) confirms
  there is no dedicated confidence/uncertainty property to attach to a
  whole event, so the hedge lives in the note, not in a formal qualifier.
- **Zuo's 1875 gift to Pan Zuyin**: I asserted `P23_transferred_title_from`
  Zuo even though the article never narrates an event where Zuo acquired
  title — only that he "may have" received custody from Yuan. I inferred
  it from the fact that a person cannot give away, as a treasured gift,
  something they don't hold title to. This is a logical inference beyond
  the literal text, and I labelled it as such, distinct from the
  custody-only hedge above it.
- **Pan Zunian's 1890 inheritance**: the article says only that Pan Zunian
  "inherited the family property" after giving Pan Zuyin's dates
  (1830–1890); it never re-names the ding at this step, nor gives this
  event a date. Both the ding's inclusion and the 1890 date are my
  inferences from context, flagged as such.
- **The 1890–1951 gap**: the article introduces Pan Dayu, who donates the
  ding in 1951, without ever stating her relationship to Pan Zunian or how
  the ding passed to her after his 1925 death. I left this gap open — no
  event bridges it — rather than assume the (historically well-known, but
  not article-stated) fact that she was his daughter. This is probably the
  single largest, cleanest gap in the whole chain, and worth a reviewer's
  attention.
- **1959, Shanghai → National Museum of China**: modelled as
  `E10_Transfer_of_Custody`, not `E8_Acquisition`. The article's own word
  is "transferred," with no language of sale or gift between these two
  state institutions, so custody is the more conservative reading. One
  consequence I want to flag explicitly rather than let a reviewer
  discover it unassisted: because I never asserted a post-1951 `E8`, the
  file's last stated *title*-holder remains the Shanghai Museum, even
  though the National Museum of China has held *custody* since 1959. That
  split is a faithful reflection of what the article actually commits to,
  not an oversight.
- **2004 loan back to Shanghai**: another `E10`, with no return event,
  because the article never says when the loan ended.

I deliberately did **not** assert `P50_has_current_keeper` /
`P52_has_current_owner` anywhere, even though the article plainly states
the ding "is on display in the National Museum of China" today. These are
declared shortcuts over "the most recent" `E10`/`E8` event, and CRM-SIG
Issue 616 (thread `t1673`, 2022) is a live proposal from the CRM's own
editors to deprecate exactly these three properties, on the grounds that
"current" breaks the append-only, accumulate-history assumption of a CRM
knowledge base and "needs external curation." Given that discussion, and
given the ambiguity above about who currently holds *title* versus
*custody*, I chose to let "current" be a derived query over the dated
event chain rather than an assertion that would need to be revised by hand
every time the object moves again.

### Scope boundaries I held to on purpose

Three related facts I chose not to promote to full CRM entities, each
flagged where it comes up rather than silently omitted:

- **The Xiao Yu ding** (the basis for the King Kang attribution) — a note
  on the Production, not a first-class object, because the brief scopes
  this file to one object.
- **The Da Ke ding** (the article's other Pan-family tripod, present in
  five of the same events — the move, the burial, the 1951 donation, the
  2004 reunion) — noted on each shared event, never given its own `P25`,
  `P24`, or `P30` link, for the same reason.
- **Beijing and Suzhou never get a country.** By contrast, I *did*
  decompose "Li Village, Jingdang Township, Qishan County, Shaanxi" into a
  full `P89_falls_within` chain, because the article gives every level of
  that chain explicitly. I stopped at the province (Shaanxi) and did not
  add "China" to it, or to Beijing or Suzhou — this is deliberately the
  same situation the brief's own example names ("naming a city's
  country"), kept unresolved on purpose so a reviewer can see exactly
  where the model stops following the source.

## 2. The tools

**Final validator output:**
`Verdict: PASSED -- every link resolves within its declared domain and
range, every rdf:type is a class this model declares, and every
owl:inverseOf claim holds` (220 links checked: 76 not_crm [rdfs:label/
comment, expected], 91 ok, 53 ok_literal). The completeness pass (with
`completeness: true`) also ends `PASSED`; its "partly stated"/"never
stated" lists were reviewed line by line and are addressed above (Li
Village's place hierarchy, the war's start date, and two inferred
`P7`/`P27` places were added as genuine fixes; everything else left blank
is either a real gap in the source or, per the tool's own framing, "usually
a modelling convention rather than an omission" — e.g. `P196_defines`,
`P152_has_parent`, `P81`/`P82` on every `E52`, which are formal FOL
closure artefacts on essentially every temporal entity, not per-instance
oversights).

**MCP calls: 35 total** — 1 `--list`; ~19 `crm_concept` lookups (classes
and a couple of properties); 3 `crm_connect` pair checks; 2 `crm_list`
pulls (CRMbase and CRMsci, each replacing what would have been dozens of
individual spelling lookups); 5 `crm_thread` reads (the Discovery-class
proposal, the money debate, the uncertainty guidelines, the current-state
shortcut deprecation); and 5 `crm_validate_rdf` runs (two failures caught
and fixed, three clean passes including two completeness runs).

**What I wanted and couldn't get:** a direct answer on whether an
`E19_Physical_Object` sub-part of a single-cast bronze (my Body/Legs
split) is actually the SIG-intended reading, versus just typing the whole
object's features without reifying parts at all — `crm_docs` on "parts of
a physical object without production events" returned nothing specific
enough to cite, so that judgement call in §1 rests on my own reading of
`P46`'s declared range rather than a located discussion.

**Blunt tool feedback:**
- `crm_validate_rdf`'s date-literal handling is a real gap, not a nitpick:
  the underlying parser can't parse negative-year `xsd:date` (`"-0996-01-01"`),
  yet `E54_Dimension`'s own scope note gives "the calibrated C14 date for
  the Shroud of Turin [AD1262-1312]" as a worked CRM example — CRM
  explicitly expects to date things before year 1, and this tool's
  validation path can't currently round-trip that without silently
  dropping the value and emitting a raw Python traceback to stderr. For an
  ancient-object modelling task this is not an edge case.
- The `.1` qualifier properties (`P14.1`, `P177`, etc.) are documented as
  "a property of P14" in `crm_list`, but there's no guidance anywhere I
  found on how to actually write one in RDF/Turtle now that `PC0`/`PC14`
  are marked "archive-attested only; no current declaration" — a modeller
  is left to guess whether to skip it (what I did) or reify it by hand.
- Everything else worked as described; `crm_connect` and `crm_list` in
  particular did exactly what their descriptions promised and saved real
  time over calling `crm_concept` one identifier at a time.
