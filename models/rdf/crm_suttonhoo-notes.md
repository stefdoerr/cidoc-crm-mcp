# The Sutton Hoo helmet in CIDOC CRM — report

Turtle file: `v2_suttonhoo.ttl`, same directory. Validator: PASSED, both plain
and `completeness: true` runs, after one fix (below).

## 1. The argumentation

### The object itself: E22 Human-Made Object, not E19 or E24

`crm_concept('E22')` gives it directly, with the server's own worked example
("the Rosetta Stone (E22)") matching this case closely: a single, physically
bounded, purposely-made artefact. I rejected its superclasses: **E19 Physical
Object** doesn't require human manufacture (it would equally fit a pebble),
and **E24 Physical Human-Made Thing** is the shared parent of E22 and E25
Human-Made Feature and doesn't require the object to have "physical
boundaries that separate them completely... from other objects" — the
qualifier that actually distinguishes a discrete helmet from, say, a carved
mark. E22 is the narrowest class that fits, so I used it for the helmet and,
for the same reason, for every major part.

### Parts as E22, not as E26 Physical Feature via P56 bears feature

For the crest, dragon heads, eyebrows, nose-and-mouth piece, cheek guards,
neck guard and cap, I considered `P56 bears feature → E26 Physical Feature`
(the property CRM offers for things like scratches or tool-marks that don't
have independent identity) and rejected it: the article describes each of
these as separately cast or forged, then riveted or hinged onto the cap —
they have their own manufacture history and physical boundaries before
assembly, which is exactly E22's criterion, not E26's. I used
`P46_is_composed_of` from the helmet (and, for the two crest-terminal
dragon heads, from the crest) rather than `P56`.

One part deliberately withholds a material assertion: the **rear
crest-terminal dragon head** is described only as "made of another alloy...
mostly degraded into tin oxide" — the article never names the alloy, so
`Part_DragonHead_Rear` carries no `P45_consists_of` at all. `crm_validate_rdf
--completeness` flagged this as the one E22 instance out of eleven lacking
the property; I left it unfixed on purpose rather than guessing a material.

### What the helmet depicts: E36 Visual Item, and one deliberate non-statement

`crm_connect('E22','E1')` showed `P62 depicts`'s declared "full path" running
through `P65 shows visual item → E36 Visual Item → P138 represents → E1`,
confirming E36 is the class CRM itself expects at the far end of a depicts
relationship for a recognisable image. I used the `P62` shortcut directly
(rather than spelling out P65/P138) because I'm not modelling the individual
stamped panels as separate physical/visual-item pairs — only the five named
designs as conceptual images, each occurring several times from shared dies.

I attached the composite "man joined by a dragon's head" visage to the whole
helmet (`Motif_Visage`), not to any one part, since it's the article's own
framing and is formed jointly by the eyebrows, nose piece and third dragon
head. I did **not** assert that the helmet depicts Odin anywhere: the
eyebrow asymmetry (gold-foil backing present on one side only) is read by
some scholarship as an allusion to the one-eyed god, but the article itself
calls this only a "possible allusion." Flattening that into `P62_depicts →
Odin` would assert what the source hedges, so the Odin reading lives only in
`P3_has_note` prose on the eyebrows part and on the rider/warrior motif. I
also deliberately did not model "Design 3" (seven fragments, "too small and
ambiguous... to allow reconstruction") as depicting anything — the article
itself doesn't know what it shows, so the model doesn't guess either.

### Production: no maker, no place, and a date built from two hedges

No person or workshop is named as maker or commissioner anywhere in the
article, so `Production` carries no `P14_carried_out_by`. More interesting:
I also omitted `P7_took_place_at`. The article states — without resolving
it — two live theories: an Anglo-Saxon origin (its default classification
throughout) and a rival reading, from the closeness of the Valsgärde 7 and
Gamla Uppsala parallels, that it "was made in Sweden, not Anglo-Saxon
England." Asserting either place would take a side the source doesn't take.

The date is the shakiest thing in the file, and I want to flag it plainly
rather than let it look authoritative. The article gives two separate,
non-equivalent numbers: (a) the helmet was "likely around 100 years old when
buried" (the heirloom hypothesis), and (b) the burial is traditionally dated
c. 620–625, with a better-evidenced numismatic terminus post quem of 613–635
from coin-fineness analysis. I did **not** fold (b)'s coin-based figure into
the production date — that figure dates the coin deposit, not the helmet.
Instead I built `TimeSpan_Production`'s bounds (`P82a`/`P82b`: 500–625) by
doing (a)'s arithmetic against the traditional burial date myself, and said
so in `P79_beginning_is_qualified_by`: this range is the model author's
inference, not a number the article states. This is the clearest case in the
file of the brief's "say so plainly and separately" instruction.

### Discovery: S19 Encounter Event, not E7 Activity

CRM base has no dedicated "discovery" class. `crm_concept('S19')` (CRMsci,
used as a CRMarchaeo superclass) fits precisely: "an Actor encounters an
instance of E18 Physical Thing... this observation produces knowledge about
the existence of the respective thing... we would talk about discovery." I
used its own properties, `O19_encountered_object` and `O21_encountered_at`,
rather than the generic `E7 Activity` + free-text note, because S19 carries
the "this is how we found out it exists" semantics that a plain Activity
doesn't.

I did **not** assert `P14_carried_out_by` C. W. Phillips on the encounter
event. The article says the discovery "was recorded in the diary of C. W.
Phillips" — that tells us who documented it, not who excavated it. I kept
those apart: a separate `E31 Document` (his diary) `P70_documents` the
encounter event, and the event itself has no named performer.

### Ownership, part 1: Edith Pretty's title, with no "from" party

`crm_concept('E8')` states plainly that E8 Acquisition permits "acquisition
from an unknown source" and that recording a donor is optional. Edith
Pretty's title to the finds didn't transfer from anyone — under the common
law the article quotes at length, items with only marginal gold or silver
became the outright property of the landowner once the coroner's inquest
ruled them not treasure trove. So `Acquisition_Pretty` has
`P22_transferred_title_to` her and no `P23_transferred_title_from`.

I modelled the inquest's ruling itself as an `E13 Attribute Assignment`
(`InquestAssignment1939`), not as a second `E7 Activity` of some ad-hoc
"legal proceeding" type: what a 14-person jury actually did on 14 August
1939 was assert a property (ownership status) of the finds, which is E13's
scope note almost verbatim ("the actions of making assertions about one
property of an object... e.g. the person and date when a condition
statement was made"). `Acquisition_Pretty` then cites that assignment via
`P17_was_motivated_by`.

### Ownership, part 2: the donation, dated as an interval

Pretty donated "within days" of the 14 August inquest — no exact date given.
I bounded `TimeSpan_Donation` between the inquest (14 August) and 25 August
(the day after excavation closed and everything was shipped out, so donation
of the shipped items can't postdate that), and used `P79`/`P80` to say in
words that the lower bound is the article's own vague phrase and the upper
bound is my inference from a different sentence, not a date attached to the
donation in the source.

### Rædwald: recorded as a hypothesis, not as an owner

This is the central hedge in the article and the one I spent the most
tool-time on. Rædwald is "the preferred candidate... by no means
conclusive"; elsewhere the article says arguments for him have been "made
with more vigour than persuasiveness," and quotes former British Museum
director David M. Wilson: "the little word *may* should be brought into any
identification of Rædwald... it may or even might be Sigeberht... or his
illegitimate brother... or any other great man of East Anglia from 610 to
650." Asserting `P51_has_former_or_current_owner` or `P52_has_current_owner`
between the helmet and Rædwald would flatten a live, decades-old scholarly
dispute into a database fact.

I searched the SIG archive for how CRM handles this generally
(`crm_search`, then `crm_thread('t1035')`, "ISSUE: Belief values",
2017-10-03). Martin Doerr raised exactly this kind of case ("probably author
of") and proposed a new certainty-value construct; Robert Sanderson replied
that the Getty had "dealt with this situation by using AttributeAssignment,"
explicitly including "workshop of"/"style of" attributions. Doerr's own
follow-up in the same thread says using E13 this way "confuses agency of
belief" and floats a different "PC" construct instead — and the thread
doesn't resolve. So the idiom I used (`E13 Attribute Assignment`, with
`P140_assigned_attribute_to` the helmet, `P141_assigned` Rædwald, and the
full quoted hedge in `P3_has_note`) is the SIG's own most-cited answer to
this exact problem, but I want to be honest that it is not a settled one —
a stricter reviewer could reasonably ask for a quantified certainty value
instead, and CRM itself doesn't yet have a stable way to give one.

### Dimensions: naming the measurement, not just the number

`crm_concept('E54')` warns that "simple terms such as 'diameter' or 'length'
are normally insufficient" and recommends a qualified type instead. I typed
the weight dimension as "weight" (plain, matches the source: "an estimated
2.5 kg") but typed the crest measurement as "surviving length (front to
back)" rather than just "length," because the article separately disputes
how much of the reconstructed crest is original fabric versus restorer's
plaster — "surviving" carries that distinction; "length" would silently
imply the reconstructed total.

### Current custody and location

British Museum as `E74 Group` holds both `P52_has_current_owner` and
`P50_has_current_keeper` (ownership and physical custody happen to coincide
here, but CRM keeps them as separate properties on principle, and I kept
them separate rather than collapsing them). `P55_has_current_location`
points at Room 41, modelled as its own `E53 Place` falling within the museum
building — a second, smaller "beyond the text" addition alongside naming
England for Sutton Hoo, both flagged in the file's own `P3_has_note`s.

### What I deliberately left out, and why

- **The two reconstructions** (Maryon, 1945–46; Williams, 1970–71) and the
  shattering event that necessitated them. These are extensively documented
  in the article, and a CRM reviewer will likely ask why there's no
  `E11 Modification` for either. My reasoning: the brief's coverage list
  asks for the object's making, finding, and ownership/movement history —
  conservation/restoration history is a different (and genuinely large)
  category, and depth-over-breadth argued for finishing the requested
  categories well rather than adding a third. I'd model this next if asked
  to extend the file.
- **The other grave goods** (buckle, shoulder-clasps, whetstone/sceptre,
  spoons, the ship itself) — real objects from the same burial, but not
  *this* object, and out of a single-object brief.
- **The Royal Armouries replica** — related and interesting (P130 shows
  features of would be the right property), but not the artefact in
  question.
- **A named maker/workshop** — the article never supplies one; inventing
  one to fill `P14_carried_out_by` on the production event would be exactly
  the kind of unsupported guess the brief warns against.

## 2. The tools

**Final validator line:**
`Verdict: PASSED -- every link resolves within its declared domain and range, every rdf:type is a class this model declares, and every owl:inverseOf claim holds (the conditions `search.py validate --rdf` exits 0 on).`
(Identical wording on both the plain and `completeness: true` runs, before
*and* after the one real fix below — the "PASSED" verdict itself never
changed; what changed was the completeness report underneath it.)

**One genuine bug the completeness pass caught:** my first draft used
`ex:Place_Room41` as the helmet's `P55_has_current_location` but never
declared that URI as an `E53_Place` individual anywhere in the file — a
plain authoring slip, not a modelling choice. The completeness diff didn't
even show it as a gap (an undeclared node isn't counted against any class),
but re-reading my own file caught it. Fixed by declaring
`Place_Room41_BritishMuseum` properly and nesting it under a new
`Place_BritishMuseumBuilding` via `P89_falls_within`. Everything else the
completeness pass listed (the rear dragon head's material, the Rædwald
hypothesis's missing time-span, the top-level places' missing outer
`P89`) I judged to be either a deliberate hedge or a reasonable scope
boundary, not an oversight, and left alone — explained above.

**MCP calls: 25**, roughly: 1 `--list`; 3 `crm_list` (CRMbase, CRMarchaeo,
CRMsci) to get exact spellings and namespaces cheaply instead of one
`crm_concept` per identifier; 9 `crm_concept` (S19, E22, E8, E12, E13, E52,
P70, E54, E57, E31, E60 — one extra to nail down E60/P90's literal
convention); 2 `crm_connect` (E22↔E1 for depicts's full path, E8↔E13 for
whether an acquisition can be motivated by an attribute assignment); 1
`crm_docs` (P90/E60 literal-value convention) plus 1 more (uncertain
attribution) that I later found the sharper answer to via search/thread; 1
`crm_search` and 1 `crm_thread` (t1035, "Belief values") for the
Rædwald-hedge idiom; 4 `crm_validate_rdf` (plain + completeness, before and
after the fix). No call failed; none needed a retry.

**What I wanted to ask and couldn't:** whether there's a CRM-blessed way to
attach a *quantified* certainty value to an attribute assignment (Doerr's
"PC"/belief-value proposal in t1035 was still open as of that thread, and
the archive lists later, still-`[unresolved]`-tagged threads on the same
topic — e.g. "Guidelines for representing uncertainty in CRM data" and
"Modeling comparative measurements without precise values" — that I didn't
have budget to read in full). If the SIG has since settled that, it isn't
surfaced anywhere I found it, and I'd genuinely like to know, since the
Rædwald hedge is exactly the case it would improve.

**Blunt feedback on the tools:**
- `crm_list` without a `model` argument returning ~130KB "many clients will
  truncate" is a real trap for a first-time user; the tool's own
  self-description warns about it, which is good, but I'd rather it just
  refused and told me to pick a model than let me find out by truncation.
- `crm_search` and `crm_docs` print an unauthenticated-Hugging-Face-Hub
  warning block on every call (visible in raw output, stripped from this
  report). Harmless, but noisy enough that I grep-filtered it out of every
  call after the first — a wrapped tool shouldn't be leaking a third
  party's rate-limit nag into its output.
- The completeness report's "1 of 2 lack it" style counts are only legible
  once you go count your own instances by hand; a report that named *which*
  instance(s) lacked the property (the way the plain-mode NOT_CRM listing
  names each offending triple) would have saved me the cross-check.
- Nothing else was missing or wrong that I ran into: `crm_connect`'s
  domain/range-plus-full-path answer and `crm_concept`'s scope notes were
  exactly what was needed, every time, to settle a class choice without
  guessing.
