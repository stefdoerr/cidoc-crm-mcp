# Modelling report: the Houmuwu ding

Turtle file: `v2_houmuwu.ttl` (same directory).

## 1. Argumentation, for a CRM reviewer

### The object itself: E22 Human-Made Object

Chosen over E19 Physical Object (too generic — loses the "purposely created"
sense) and over any CRMarchaeo find-specific class (there isn't one; finds
are handled by an *event*, see below, not by re-classing the object). `crm_concept`
on E22 lists as a worked example "the Rosetta Stone" — an inscribed,
museum-held ancient artefact, which is close enough to this case to be
reassuring rather than decisive. E22's scope note also explicitly says the
class "includes all aggregates of objects made for functional purposes...
such as a set of chessmen," which is what let me model the four legs and the
two handles as their own E22 instances (aggregates-of-a-kind) rather than
inventing a part-class or leaving them unmodelled.

### Vessel type, not a subclass: P2 has_type

CRM has no class for "ding" or "fangding." The correct mechanism, confirmed
by E22's applicable-properties list, is `P2_has_type` pointing at an E55
Type node, which is what I did (`ex:Type_Ding`). Same treatment for the two
decorative motifs (taotie, kuilong) and the handle motif — they're typed,
not subclassed.

### Decoration: P56 bears_feature + E25, rejected P62 depicts

This was a real fork. `crm_concept P62` gives depicting examples that are
all about a real, nameable referent — a coin depicting Queen Elizabeth II, a
painting depicting the July Revolution — and its scope note says outright
that the property "does not pertain to inscriptions or any other
information encoding." Taotie and kuilong bands are cast reliefs, not a
picture of a specific real thing; they read more like the P56 example
itself ("32 mm scratch on silver cup 232") than like a depiction with a
subject. I used `P56_bears_feature` → `E25_Human-Made_Feature` (not the
plain E26 Physical Feature that P56's range formally names — E25 is the
correct human-made subclass of it and is what E22's own sibling list
offered), each typed via P2 to the specific motif. I treated the
tiger-and-human-head handle motif the same way for consistency, though it
is the more figural of the three and a reviewer could reasonably prefer P62
for it; I chose consistency of treatment across the whole decorative
programme over splitting the difference.

### The inscription: E34 Inscription, not a note or a Title

E34's scope note draws the line cleanly: it is "the underlying prototype,"
carried by the physical object via `P128_carries` (confirmed: domain E18 →
range E90, and E34 < E33 < E73 < E90, so the path is legal). I gave it
`P72_has_language` (E34 requires it — I used a plain "Chinese" E56 node,
since the article gives no more specific language claim than that) and
`P2_has_type` for "bronzeware script / jinwen." `P67_refers_to` links it to
Fu Jing (confirmed via `crm_connect(E34,E21)`, which resolves through E89
Propositional Object) — the article states this as settled fact ("This is
the temple name of Fu Jing"), so I did not hedge that particular link, only
the *reading* of the characters, which the article does hedge extensively
(see below).

### Naming history: three E13 Attribute Assignment events, not one static label

This is the part of the article that most rewards structure rather than a
flat description, and it is where I spent the most modelling effort. The
object has had (at least) two names — "Simuwu ding" and "Houmuwu ding" —
and the article narrates *who* proposed the change and *when*, with an
explicit note that the change was contested ("provoked much discussion").
`E13_Attribute_Assignment`'s scope note is written almost for this case: it
exists to record "whose opinion it was" and explicitly warns that "multiple
use of instances of E13... may possibly lead to a collection of
contradictory values" — which is exactly the situation with two live
appellations. I used:

- `ex:NamingAssign1946` — Zhang Feng, November 1946, assigning
  "Simuwu ding" (`P177_assigned_property_of_type crm:P1_is_identified_by`).
- `ex:ReadingProposal1977` — Li Xueqin, 1977, proposing the *hòu* reading of
  the first glyph (assigned property is `P190_has_symbolic_content` on the
  Inscription, not `P1` on the object — this is a proposed reading of a
  character, not yet a renaming of the object).
- `ex:RenamingAssign2011` — the National Museum of China, March 2011,
  assigning "Houmuwu ding," with `P17_was_motivated_by` pointing back at
  the 1977 proposal, so the causal chain (proposal → decades of debate →
  official adoption) is traceable in the graph, not just in prose.

I did *not* give Guo Moruo's "sī = sacrifice" etymology or Sun Ji's
horizontal-reflection argument their own dated E13 events. Guo Moruo's
contribution doesn't change the appellation (it's still "Simuwu"), only its
folk etymology, and the article gives him two different dates for
essentially the same claim ("after 1949" in one section, "1959" in
another) that I made no attempt to reconcile — I folded both into a note on
`NamingAssign1946` and flagged the discrepancy explicitly rather than
picking one. Sun Ji's argument has no date in the source at all, so it goes
into a note on `ReadingProposal1977` rather than getting a manufactured
E13 with an invented timespan. A reviewer could reasonably want these
promoted to full events if the underlying dates were ever pinned down; I
judged the added machinery wasn't earning its keep against two vague or
absent dates.

### Discovery: CRMsci S19 Encounter Event, not a bespoke "Discovery" class

This is the one place the tool's own documentation pointed me somewhere
specific, and I followed it up rather than take it on faith.
`crm_search("discovery class excavation encounter event archaeology")`
surfaced a 2013 SIG issue (`t0689`) proposing exactly the class I might
otherwise have invented — "add Activity subclass Discovery (Finding)" —
and Stephen Stead's reply in that thread is the reason it wasn't accepted:
"we do/try not to add classes to the model unless it forms an anchor for
some properties... What are the new properties that justify the proposed
new sub-class? The alternative is just to type an instance of E7 Activity."
The same search returned a 2014 message noting the find-event "found a new
home" in CRMsci as S19 Encounter Event, and a 2020 message (Robert
Sanderson, on Linked Art) stating flatly that "S19 and O19 were agreed upon
as the correct modelling constructs" for find events. So: `S19_Encounter_Event`,
linked to the object via `O19_encountered_object` and to the place via
`O21_encountered_at` — the CRMsci-specific properties built for exactly
this, in preference to the generic `P7_took_place_at` that S19 also
inherits (using both would be redundant).

### The vague "made after her death": P183, not an invented date

The article says the ding "was made after her death" and gives no date for
either the death or the casting. Rather than assign a guessed calendar
year to either event (which the brief explicitly rules out), I linked them
by relative order: `ex:FuJingDeath crm:P183_ends_before_the_start_of
ex:Production`. I found this by asking `crm_connect(E69, E12)` directly
rather than reaching for the property I half-remembered (P120 occurs
before/after) — which turned out to be exactly right to be suspicious of:
`crm_concept("P120")` reports it as **deprecated** in the current standard,
replaced by the P170-series fuzzy-boundary relations (P183 among them) after
a 2020 SIG vote. Using it from memory would have been a real error caught
only because I checked. Both `FuJingDeath` and `Production` are left
without their own timespans — that's a deliberate absence, not an oversight,
and completeness confirmed it as such (see part 2).

### The maker: E13 Attribute Assignment, not a direct P14

The article hedges this explicitly ("presumably by her son, Zu Geng of
Shang"). I did not assert `P14_carried_out_by Zu_Geng` directly on the
Production event, because that would flatten "presumably" into a plain
fact. Instead I used a fourth `E13_Attribute_Assignment`
(`P177_assigned_property_of_type crm:P14_carried_out_by`) recording the
*claim* that he carried it out, and I left that assignment's own `P14`
(who is doing the presuming) unstated, because the article attributes the
presumption to nobody in particular — it's stated in the passive voice.
This is the single hedge in the model I'd flag hardest to a reviewer:
it's a correct use of the mechanism, but it produces an attribute
assignment with an unnamed assigner, which is a slightly unusual shape and
worth a second look.

### Fu Jing's tomb: deliberately left out

Tomb 260 at Yinxu, where Fu Jing was later buried (found in 1959, looted),
is mentioned in the "Owner" section but the article never connects it to
the ding's own find-history — the ding was unearthed separately, in
Wuguan Village. I left it as a one-line note on the Fu Jing resource rather
than modelling a burial/looting event chain, because pulling it into the
object's own provenance graph would imply a link the source doesn't state.

### Beyond the source, flagged plainly

- I decomposed "Wuguan Village, Anyang, Henan" into three `E53_Place`
  instances chained by `P89_falls_within` (Wuguan Village < Anyang < Henan).
  This is a straightforward formalisation of what's already an explicit
  administrative sequence in the source sentence, not an invention.
- I did **not** add "China" as a country for either the find-place or the
  National Museum, and did not add "Beijing" for the museum. Both are true
  and well-known, but the article never says them, and the brief's own
  example of overreach ("naming a city's country") is precisely this
  shape of addition.
- Plain years/months ("1939," "November 1946," "1977," "March 2011") are
  formalised as `E52_Time-Span` with `P82a`/`P82b` outer bounds spanning the
  full year or month — a mechanical widening, not a guess at a narrower
  date the source doesn't give.
- The current-keeper fact (National Museum of China) is inferred from the
  sentence about the 2011 renovation and renaming display, not stated as
  "the ding is held at..." verbatim. I judged this a fair reading, but it
  is an inference, not a quotation, and I did not build any transfer-of-
  custody event around it because the source gives no date or prior keeper
  for such a transfer.

## 2. The tools

**Final validator output:** `144 links checked: 48 not_crm, 60 ok, 36
ok_literal` — `Verdict: PASSED` (all `not_crm` entries are `rdfs:label`,
explicitly not a CRM property, not an error). Completeness pass ran clean
too, no errors, only "not stated" guidance; the two genuinely-fixable gaps
it surfaced (missing `P53_has_former_or_current_location` for the find-spot,
and an unstated `P89` place hierarchy) were both fixed from the article
itself, no invention required. Everything else in the completeness report
(P10/P12/P160/P161/P7 on almost every event; P92/P93 alongside P108/P100;
P177 on the E17 event) I judged to be modelling convention — CRM's
"necessary" properties on temporal entities are close to universally
unpopulated in practical models, and the ones with dedicated subproperties
(P41/P42 for E17) don't also need the generic P177.

**MCP calls made:** 24. 1 `--list`; 14 `crm_concept` (E22, E12, E13, S19,
P120, E69, E34, P62, P56, E54, E41, E17, E52, P89); 2 `crm_connect`
(E69↔E12 for the death/production ordering, E34↔E21 for the inscription's
referent); 2 `crm_list` (CRMbase, CRMsci, for exact RDF local names); 1
`crm_search` (discovery/excavation modelling); 1 `crm_thread` (t0689, the
2013 Discovery-class debate); 3 `crm_validate_rdf` (initial pass,
completeness pass, re-check after the two fixes). All 24 succeeded on the
first try; none needed a retry.

**Wanted to ask and couldn't:** whether P62 vs P56 has ever actually been
argued out for cast relief ornament specifically (taotie/kuilong are a
named East Asian motif type, and I'd have liked a SIG precedent for exactly
this shape of decision rather than reasoning it out from the general scope
notes). `crm_docs` says flatly that domain-specific queries like this find
nothing because the spec is domain-agnostic — which is a fair, honest
answer, but it meant I had to make the P56-vs-P62 call on general
principle rather than precedent.

**Blunt notes on the tools:** `crm_list` without a `model` argument warns
it will return ~130KB and get truncated by many clients — good that it
warns, but it would be more useful if it just told you which models exist
in one line rather than making you discover the model names (`CRMbase`,
`CRMsci`, `CRMarchaeo`, ...) by trial. `crm_connect` output repeats the
*entire* applicable-properties list for both classes even when only a
handful of properties actually connect them meaningfully (e.g. `E69↔E12`
came back with ~20 Allen-relation properties before the one I wanted); a
"most specific / most likely" flag would cut a lot of scanning. Otherwise
the tools did what they said, and the self-description from `--list` was
enough to plan the whole session without ever needing the files the brief
walled off.
