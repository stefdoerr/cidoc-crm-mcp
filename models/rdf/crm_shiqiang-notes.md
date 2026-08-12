# Modelling report: the Shi Qiang pan

Turtle file: `v2_shiqiang.ttl`. Every class/property identifier below was confirmed
against the MCP server before use; nothing in this file was typed from memory of
CIDOC CRM.

## 1. Argumentation

### The object itself: E22 Human-Made Object

`crm_list` for CRMbase shows no vessel-specific class anywhere in the base
model — the closest candidates are all generic (E19 Physical Object, E22
Human-Made Object, E24 Physical Human-Made Thing). `crm_docs` on vessel-form
questions is explicitly documented as domain-agnostic ("a subject-matter
query about grave goods or ship burials finds nothing, and that absence is
itself an answer"), so I didn't spend a call confirming that a "pan" class
doesn't exist — I took the tool's own stated scope at face value. E22 Human-
Made Object is the correct generic fit (a single, purposely-made, bounded
physical object), and I put the vessel-form itself ("pan") in a free-text
`P2_has_type`, flagged in the file as my own typing rather than a linked
authority term — I have no Getty AAT/thesaurus tool available to verify it
against a controlled vocabulary.

### Handles: a part (P46/E19), not a feature (E25) — and not two of them

This was a real fork. `crm_concept("P56")` (bears feature) gives the worked
example "Silver cup bears feature 32 mm scratch on silver cup" — every
example under E25 Human-Made Feature (`crm_concept("E25")`: scratches,
carved letters on the Rosetta Stone, artificial water channels) is a
surface-level mark, not a projecting, load-bearing appendage. A handle on a
one-piece bronze casting is structurally more like a part than a surface
marking, so I used `P46_is_composed_of` (E19 Physical Object) for the
handles and reserved `P56_bears_feature`/E25 for the taotie motif, which
*is* a cast-in surface design — the Rosetta Stone example is almost exactly
this case.

Separately: should the two handles be two instances or one? The article
never distinguishes them (no asymmetry, no individual decoration
mentioned), so instantiating "Handle 1" and "Handle 2" as separate
anonymous individuals would be manufacturing a distinction the source
doesn't support. I modelled one collective part instance with a note
stating there are two. This follows a design principle Martin Doerr (the
CRM's own editor) stated explicitly in a 2014 thread I read in full
(`crm_thread("t0809")`, "A hoard as crm:E78_Collection?"): "We should only
use a more specific class[/instance split], if we expect the respective
additional properties to be relevant for querying... the less classes we
use, the more effective the queries." Nothing here needs the two handles
addressed separately, so I didn't split them.

### The making: E12 Production, and how "cast … for Qiang" was framed

The article says the pan "was cast … for a member of the Wei clan …
whose name was Qiang," and later calls him "the caster." This is
ambiguous: is Qiang the artisan, or the person for whom (i.e. the patron
who commissioned) the casting was done? Chinese bronze scholarship's
convention is the latter — the named "caster" of a ritual bronze is
normally its dedicatee/commissioner, not the foundry worker — and nothing
in the article suggests Qiang personally worked bronze.

I checked this against the server rather than assume it. `crm_search` for
"commissioned patron production" surfaced a 2012 thread
(`crm_thread("t0634")`, subject line in the archive's own episode index:
"Mapping payers to man-made objects" — status "decided") where a
CRM-SIG member asked exactly this question ("a possible payer …
Auftraggeber, for any object of art") and got this answer from Vladimir
Alexiev:

    <obj> a E22_Man-Made_Object; P108i_was_produced_by <obj/production>.
    <obj/production> a E12_Production; P17_was_motivated_by <person>.

i.e. commissioning is expressed as `P17_was_motivated_by` on the
**Production event**, not as `P14_carried_out_by` on the object (which
would assert Qiang was the executing artisan — a claim the source does not
make and Chinese-bronze convention argues against). I followed that
pattern exactly: `obj:Production P17_was_motivated_by obj:Qiang`, and left
`P14_carried_out_by` empty since no artisan is named. I flagged the "for
whom, not necessarily by whose hand" reading explicitly in a note on the
Production node, since a reviewer who reads "the caster" literally could
reasonably object to not using P14.

### The finding: S19 Encounter Event, not a CRMarchaeo class

I expected the 1976 unearthing to live in CRMarchaeo (the archaeology
extension) and called `crm_list("CRMarchaeo")` first — it turned out to
contain almost nothing but stratigraphic-unit machinery (A1–A10) and no
"find" or "discovery" class at all; the class the tool's own `crm_thread`
description names for exactly this situation, S19 Encounter Event, actually
lives in CRMsci, which I only found by then calling `crm_list("CRMsci")`.
Its scope note (`crm_concept("S19")`) settled it on the merits too: "In
Archaeology, there is a particular interest if an object is found 'in
situ' … The surrounding matter with the relative position of the object in
it … may be recorded to enable inferences about the history of the
object" — a direct match for a bronze recovered from a sealed hoard. I used
the dedicated CRMsci properties `O19_encountered_object` and
`O21_encountered_at` rather than the inherited generic `P7_took_place_at`,
since they're the more specific path the model itself declares for this
class.

### The burial: E9 Move, and deliberately *not* an E78 Collection for the hoard

"Buried along with over 100 other vessels" raises two questions: what
class for the burial act, and what to do about the other 100+ vessels.

For the act itself, E9 Move's scope note (`crm_concept("E9")`) is generic —
"changes of the physical location of … E19 Physical Object" — with
examples (London Bridge's relocation, a travelling exhibition) that are all
mundane transport, not concealment. I used it anyway because burial is,
structurally, exactly a location change, and no thread I found proposes
anything more specific for ancient caching/hoarding of objects. This is
the one choice in this file I'd call "plausible but not SIG-blessed" —
flagging it as such rather than presenting it as settled.

For the other vessels: I deliberately did **not** create an E78 Collection
(or any other) entity to represent "the hoard" as a single thing. I read
the entire 2014 SIG thread on exactly this question
(`crm_thread("t0809")`, "A hoard as crm:E78_Collection?"). A modeller
proposed E78 Collection for a coin hoard; Christian-Emil Ore objected that
E78's scope note requires "a particular collection development plan,"
which a buried hoard doesn't obviously have; Martin Doerr then closed the
question with the "has type: Hoard" / minimal-class principle quoted
above, and a proposal for a dedicated "Fx Assemblage" class was explicitly
rejected as unnecessary. Since the other 100+ vessels are out of scope for
this file anyway (the brief is about one object), I only asserted this
pan's own `P25_moved`/`P26_moved_to`, with a note naming the context, and
built nothing to represent the hoard as an entity in its own right.

### Ownership vs custody: keeper, not owner

The article says the pan "is kept at" the Baoji Bronzeware Museum — it
never says who *owns* it. CRM keeps these separate: `P51/P52` (owner) vs
`P49/P50` (keeper). I used `P50_has_current_keeper`, whose own worked
example in `crm_concept("P50")` — "The paintings from the Iveagh Bequest
has current keeper The National Gallery" — is the same shape of fact
(custody, stated plainly, without a claim about title). Using P52 here
would have asserted a legal fact ("the museum owns it") the source never
states; a state museum holding a listed national treasure is not
automatically its legal owner in every jurisdiction, so I didn't collapse
the two.

### The museum, and the clan, as E74 Group — not a deprecated E40 Legal Body

I checked `crm_concept("E40")` on reflex, expecting "Legal Body" for an
institution, and got back "no definition in v7.1.3 (deprecated
vocabulary)" with the migration instruction "E40 Legal Body | use E74
Group." E74's own scope note (`crm_concept("E74")`) then supplied the
exact precedent twice over: its own example list includes "the National
Museum of Denmark" (confirming E74 for the museum) and states outright
that "married couples and other concepts of family are regarded as
particular examples of E74 Group" (confirming E74 for the Wei clan). Both
uses in this file are therefore directly attested by the class's own
examples, not just an inference from "E74 is the most general Actor
subclass that isn't E21 Person."

### Personal/place names: plain E41 Appellation, not E82

For the same reason I didn't reach for E38 Image or E44 Place Appellation,
I checked whether E82 Actor Appellation still exists before using it for
Qiang's name — `crm_concept("E82")` returned the same "deprecated
vocabulary" pattern as E40. I used plain `E41_Appellation` throughout
(Qiang, the Wei clan, the pan itself) rather than any of the retired
E82/E44 subclasses.

### The replica: P130_shows_features_of, and "displayed" treated differently from "kept"

"A replica is displayed in the Calgary Chinese Cultural Centre Museum" is
a second E22 instance, related to the original but not a part of its
provenance chain. `crm_concept("P130")` describes exactly this
relationship — "generalises the notions of 'copy of' and 'similar to' …
the domain expresses the derivative … the range the source" — and a 2011
thread I found on modelling commercial replicas
(`crm_thread("t0596")`) confirms P130 as the property CRM-SIG itself
reaches for in replica cases, there layered under a full FRBRoo
publication-event chain for *mass-produced* commercial replicas. I judged
that machinery disproportionate to one clause in one sentence about one
replica with no stated date or maker, and used bare
`P130_shows_features_of` with a note explaining the omission, rather than
inventing an F24/F32 chain the source gives no material to fill in. I also
dropped `P130.1_kind_of_similarity` (which would state whether the
similarity is directional) — the CRMbase list shows the PC-style
reification classes that would carry such a qualifier cleanly in RDF
(`PC0`, `PC1`, `PC2`, `PC14`) are all "archive-attested only; no current
declaration" in this server's v7.1.3, so asserting the qualifier would mean
inventing a reification pattern the ontology doesn't currently supply.

For the replica's location I used `P55_has_current_location` (a Place)
rather than `P50_has_current_keeper` (an Actor), unlike the original. This
is deliberate: "kept at" (original) reads as custody; "displayed in"
(replica) reads as presence without a custody claim — a temporary loan
would still be "displayed" but might not make the venue a "keeper." A
reviewer could reasonably collapse this distinction back to P50 for
symmetry; I chose not to.

### Vague and conflicting dates

The article gives two dates for the casting at different granularities:
"end of the 10th century BCE" (lead) and "the reign of King Gong of Zhou
(r. c. 915 – 900 BCE)" (body) — both already hedged with "c." in the
source. I used `P82a_begin_of_the_begin`/`P82b_end_of_the_end` (the
loosest CRM bound pair) rather than `P81a/P81b` (the tightest), precisely
because the article itself doesn't commit to precision inside that range —
using the tight pair would have asserted more confidence than the source
has. **This is the clearest place in the file where I went beyond the
article**: converting "915–900 BCE" into `xsd:gYear` literals `-0914`/
`-0899` requires picking a sign convention (astronomical year numbering,
where 1 BCE = 0000), which the article never states or needs. A reviewer
should treat that conversion as my formalization, not the source's claim.
I used the same bound-pair style for the burial's span (bracketed between
the casting and 1976, since the article only says "some time later") and
for the plain, unhedged years 1976 and 2002, where there's no real
uncertainty to preserve.

### The one place I chose to add historical-consensus content rather than flatten it: King Zhao

The article states, as a fact about the article's own subject rather than
a hedge, that the inscription's claim ("tamed Chu and Jing") contradicts
what actually happened (King Zhao's campaign was defeated and he was
killed) — and explicitly uses this as evidence of the inscription's
"positive spin." This felt like the single most important nuance in the
whole source to preserve, since it's the article's thesis about why the
inscription matters. I modelled King Zhao's campaign as its own `E7
Activity` (`P14_carried_out_by` King Zhao, per the completeness check —
see below) carrying a note with both the inscription's claim and the
article's correction side by side, rather than picking one. I considered
building a proper two-sided epistemic structure (a claim asserted by the
inscription vs. a fact asserted by the article, as CRMinf's belief/
argumentation classes are meant for) and rejected it: I did not load
CRMinf from the server, so I have no server-confirmed classes for it, and
building one from memory would be exactly the kind of unverified
CRM knowledge the brief rules out. A plain `P3_has_note` carrying both
sides in prose is a smaller claim than a first-class "disputed" property
would be, and I'd rather under-claim here than invent a structure I
haven't checked.

### What I did not model, and why

- **The 100+ other buried vessels** — out of scope for a single-object
  file, and (per the E78 thread above) not something CRM wants reified as
  a group anyway without a stated curator/plan.
- **Modern scholarship** (Shirakawa's *Complete Explanations*, Shaughnessy's
  translation) — this is the bibliographic apparatus about the object, not
  the object's own history of making/finding/owning that the brief asks
  for; adding it would mean modelling E31 Document / E7 translation
  activities for citations the article itself only lists under "External
  links."
- **A country node for Fufeng/Baoji/Shaanxi or for the Calgary museum** —
  the brief's own example of an unsupported addition. The province
  "Shaanxi" and the museum's Place node are left with no
  `P89_falls_within` parent; I could have added "China"/"Canada" from
  general knowledge, but chose the more conservative gap over an inference
  the article never makes. (`crm_validate_rdf --completeness` flags both
  as bare P89 chains — see below — and I left them as-is on purpose.)
- **The replica's material, maker, and date** — the article states none of
  these, so `P45_consists_of` etc. are absent on `obj:Replica` even though
  they're present on the original; the completeness check flags this
  asymmetry too, and it's a real gap in the *source*, not in the model.

## 2. The tools

**Final validator result:**
`Verdict: PASSED -- every link resolves within its declared domain and range, every rdf:type is a class this model declares, and every owl:inverseOf claim holds`
(confirmed on both the plain run and the `completeness: true` run, after two
fixes — see below).

**MCP calls: 27 total.** Roughly: 1 `--list`; 4 `crm_list` (CRMbase, CRMarchaeo
twice — once inline, once re-run to a file because the first response looked
like it might be truncated; it wasn't, so that second call was a wasted
check — and CRMsci, where S19 actually turned out to live); 11 `crm_concept`
(E40, E9, S19, P130, E82, E33_E41, E74, P50, E25, P56, E12); 2 `crm_search`
(hoard/burial, commission/patron); 3 `crm_thread` (t0596 replicas, t0634
commissioning, t0809 hoards); 2 `crm_connect` (S19→E22, E12→E21); 4
`crm_validate_rdf` (plain + completeness, twice, before and after fixing two
gaps the completeness pass turned up: switching King Zhao from
`P11_had_participant` to the more specific `P14_carried_out_by`, and
promoting "Qiang's father/grandfather" out of a prose note into their own
`E21_Person`/`P152_has_parent` nodes).

**Wanted to ask and couldn't:** whether there's any SIG guidance specifically
on ritual-bronze inscriptions praising a monarch's deeds inaccurately (i.e.
whether CRM has ever discussed eulogy-vs-fact as a modelling problem
outside the CRMinf belief/argumentation extension) — `crm_search` on
"eulogy" / "positive spin" / "propaganda inscription" returned nothing
useful, and I didn't want to guess CRMinf's class names without loading
that model, so I left it as a plain note instead of a probably-wrong
CRMinf triple.

**Blunt feedback on the tools:**
- `crm_list("CRMarchaeo")` was a genuine trap: it's the model whose name
  matches "archaeology," but the class the tool's own `crm_thread`
  docstring recommends for exactly this scenario (S19 Encounter Event)
  isn't in it — it's in CRMsci. A one-line pointer in CRMarchaeo's own
  listing ("see also CRMsci for find/observation events") would have saved
  a call.
- `crm_concept` on a deprecated identifier (E40, E82) is genuinely good —
  the migration-instruction table it surfaces is exactly what's needed and
  I used it verbatim twice.
- `crm_thread`'s episode-index one-line summaries (in the `crm_concept`
  "Debated in N episodes" lists) are useful for triage but their
  `[decided]`/`[unresolved]` tags are for the *episode*, not necessarily
  for the specific sub-question inside it — t0634 is tagged `[decided]` in
  the E12 index but the "decision" is really one confident reply from one
  SIG member (Vladimir Alexiev) answering another member's question, not a
  ratified SIG resolution. I've cited it as "a SIG member's answer,
  unopposed on the thread," not as CRM law, and a reviewer should read it
  the same way.
- No complaints about `crm_validate_rdf`: the `NOT_CRM` noise for
  `rdfs:label` on every single node is expected and harmless, but it does
  mean the actually useful signal (a real domain/range violation) is
  visually buried in ~40 lines of "rdfs:label is not a CRM property" per
  run. A `--quiet`/`--errors-only` flag would make the output much faster
  to scan.
