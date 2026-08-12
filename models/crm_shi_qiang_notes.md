# Shi Qiang pan — CIDOC CRM encoding: rationale

Model: `crm_shi_qiang.xml`. Subject: <https://en.wikipedia.org/wiki/Shi_Qiang_pan>.
Format references: `crm_amol_1.xml` and `crm_clayton1.xml`.
Everything asserted about the CRM below was checked with `search.py`
(`concept`, `validate`, `connect`, `ontology`, `docs`, `show`); the two example
files and the Wikipedia article were read directly, as the brief intends.

Counts: **31 distinct classes** (25 CRMbase, 1 CRMsci, 1 CRMtex, 4 CRMinf) and
**48 distinct properties** (42 CRMbase, 2 CRMsci, 4 CRMinf), written as 47
element names — `assigned` stands for both P42 and P141 and `falls_within` for
both P86 and P89, while P4 appears in both directions.

---

## 1. Conventions taken from the examples

Both examples use the same skeleton, and I kept it unchanged:

* root `<CRMset>`, one or more `<CRM_Entity>` children;
* the **first text node of an element is the instance label**, and its
  `<in_class>` child gives the class;
* **property element names are CRM property labels with spaces turned into
  underscores** (`is_identified_by`, `has_note`, `carried_out_by`), in either
  direction (`is_documented_in` is P70i);
* nesting is the link: a child element asserts *parent → property → child*;
* there is no cross-referencing mechanism, so **identity is the label string**.
  The findspot, the places, Scribe Qiang, the burial and the 1976 find each
  recur under an identical label so that they denote the same instance.

From amol I took the `has_dimension` → `has_type` / value / unit shape, and
amol's note vocabulary (`Statement`, `Description`, `Made Note`) — but *not*
amol's way of attaching it; see §2(e), which is the second place an example
turned out to be wrong.
From clayton I took the pattern of recording **determinations as events**
(`was_classified_by` → `E17 Type Assignment`, with the assigner and the date on
the assignment, not on the object) — that is the pattern that makes the
contested material in this article expressible at all.

### Where the two examples differ, and what I picked

| point | amol | clayton | what I did |
|---|---|---|---|
| identifiers | `is_identified_by` only | `is_identified_by` **and** `preferred_identifier_is` | `is_identified_by` (amol). `preferred_identifier_is` is not a CRM label; the article gives no accession number anyway, so nothing to prefer. |
| dimensions | `has_dimension` with `<value>`/`<unit>` children | no dimensions | amol's structure, but see §2 on `<value>`/`<unit>`. |
| dating | no dates at all | `at_most_within` on the event | neither: `has_time-span` → `E52` → `at_some_time_within` → `E61`, see §2. |
| sources | `is_documented_in` → `E31 Document` | `is_referred_to_by` → `E32 Authority Document` | `is_documented_in` → `E31 Document` throughout. The article's sources are scholarly publications documenting the object, not authority lists that the object's *appellation* appears in, which is what clayton's `is_referred_to_by` → `E32` is doing (it is hung off the plant name, not the specimen). |
| class naming | `E22: Man-Made Object`, `E55: Object Type` | `E55: Clayton Old Barcode Type`, `E52: Time Span` | exact current CRM names only (`E22: Human-Made Object`, `E55: Type`, `E52: Time-Span`). See §2. |

---

## 2. Where an example is wrong, and what I did instead

I ran the validator over both examples first, which is how these were found.

```
clayton: 656 links checked: 32 ambiguous, 25 illegal, 388 ok, 120 ok_literal, 91 unknown_name
amol:    637 links checked: 211 attached_to_property, 215 ok, 211 ok_literal
```

**(a) Three element names in clayton are not CRM property labels** (the 91
`unknown_name` links are these three, repeated across its 25 specimens):

| clayton writes | the CRM label is | id |
|---|---|---|
| `preferred_identifier_is` | `has preferred identifier` | P48 |
| `changed_ownership_by` | `changed ownership through` | P24i |
| `at_most_within` | `at some time within` | P82 |

None of them appears in my file. `at_most_within` is the tempting one, because
this object needs exactly that construct; I used `at_some_time_within` → `E61:
Time Primitive`. Note that clayton also puts the wrong class on it — it writes
`<at_most_within>1727<in_class>E52: Time Span</in_class>` — the range of P82 is
E61 Time Primitive, not another Time-Span.

**(b) clayton uses a property outside its declared domain.** `took_place_at`
(P7, domain E4 Period) is nested under `transferred_title_to`, i.e. hung on the
`E39 Actor` rather than on the `E8 Acquisition`:

```
ILLEGAL took_place_at  E39 -> E53  ...changed_ownership_by/transferred_title_to/took_place_at
        E39 is not a E4
```

Where I needed a place for an event I hung it on the event (`encountered_at`
on the `S19`, `moved_to` on the `E9`), and where I needed a place for an actor
I used the property meant for that, `has_current_or_former_residence` (P74,
domain E39), for the museum.

**(c) Both examples put local vocabulary into the class name.** amol writes
`E55: Object Type` and `E55: Dimension Type`; clayton writes `E55: Clayton Old
Barcode Type`, `E42: Object Identifier`, `E:55 Type Type` (two of clayton's are
so malformed that no identifier can be read from them). The validator reports
every one of these as `LABEL_MISMATCH`. The local vocabulary belongs in the
instance label, which is the text node, not in the class name. My file uses the
exact current names throughout and produces no `LABEL_MISMATCH`.

**(d) amol's `<value>` and `<unit>` are not CRM labels either.** The validator
does not flag them — it lists them under "structural elements skipped", along
with `CRM_Entity` and `in_class` — so they are tolerated by the format rather
than wrong. But they are also therefore *unchecked*. I used `has_value` (P90 →
`E60: Number`) and `has_unit` (P91 → `E58: Measurement Unit`) instead, keeping
amol's surrounding `has_dimension`/`has_type` shape. The brief's rule for a
label that does not resolve is to follow the standard, and the reward is that
the four dimension values in this file are validated rather than skipped.

**(e) amol's typed-note idiom is a property-of-property, and this format cannot
write it.** amol types every note by nesting `has_type` inside `has_note`:

```xml
<has_note>Toys; Transport
  <has_type>Subject<in_class>E55: Type</in_class></has_type>
</has_note>
```

I copied that idiom, and the validator rejected all 34 instances of it:

```
ATTACHED_TO_PROPERTY has_type
    E22 -> E55   at CRM_Entity[E22]/has_note/has_type
    nested inside 'has_note', which carries a literal -- this qualifies that
    property, not E22; the CRM wants a property-of-property and the format cannot
```

The reading is right and the point is subtle. `P3.1 has type` is a property
**of P3**, not of P3's subject. Because nesting in this format means
*parent → property → child*, the encoding above literally asserts *the object
`P2 has type` "Subject"* — it types the pan as a Subject, which is false. All
211 of amol's notes are wrong in this way; it is the single largest defect in
either example, and I reproduced it before the validator caught it. The fix the
validator recommends is to fold the qualifier into the literal, so every note
in this file now reads `<has_note>[Statement] …</has_note>` with no child
element. The note vocabulary is preserved, in the only place the format has
room for it.

---

## 3. The modelling choices that were actually difficult

**The inscription is two things, and the CRM insists on the distinction.**
`concept E34` says the class "is not intended to describe the idiosyncratic
characteristics of an individual physical embodiment of an inscription, but the
underlying prototype", and `concept E25` gives "the carved letters on the
Rosetta Stone" as its own example. So the *cast characters on the interior* and
the *text* are separate instances: a physical feature borne by the vessel
(`bears_feature`, P56) which `carries` (P128) an `E34 Inscription`. Character
and line counts are dimensions of the physical text; language, referents,
component passages and the translation hang off the E34.

For the physical text I used **`TX1 Written Text` (CRMtex)** rather than plain
`E25`. TX1 is declared a subclass of E25, so nothing about the surrounding
links changes; it earns its place because the article makes the writing itself
a primary subject (284 characters, eighteen lines, transcriptions, a
translation, difficulty "graphically and lexically"). This is the only CRMtex
identifier used. I did **not** reach for `TX6 Transliteration` for Shirakawa's
transcription — TX6 is an *activity* with `P94 has created` and `P14 carried
out by` marked necessary, and the article describes no activity, only that the
fullest treatment is in a named book.

**The taotie: P138, not P199 and not P62.** `concept P199` ("represents
instance of type") says in terms that it is for when "the identity of the thing
depicted is unknown or unrecorded, but is clearly a particular thing of that
type", and that if the visual item "directly depicts the concept of the E55
Type rather than an instance of a thing of that type, then this should be
represented using E36 Visual Item P138 represents E55 Type". Its worked example
contrasts a photograph of a particular hoopoe (P199) with an Egyptian relief
showing "intentionally typical rather than individual characteristics" (P138).
A cast taotie mask is the second case, so: `E25` feature → `shows_visual_item`
(P65) → `E36` → `represents` (P138) → `E55 Type` "taotie". P62 depicts is
wrong for the same reason — there is no individual being depicted.

**The handles are features, not parts.** `concept E22` requires "physical
boundaries that separate them completely in an objective way from other
objects"; `concept E26` says features have "no natural borders that separate
them completely in an objective way from the carrier objects" and offers "the
head of a contiguous marble statue" as a feature. Handles cast in one piece
with the basin fail E22's test and pass E26's, so they are `E25 Human-Made
Feature` reached by `bears_feature`, not `E22` parts reached by P46. I minted
**two** instances, "handle A" and "handle B", so that the cardinality the
article states is in the data rather than only in prose; a note on handle A
says the letters are arbitrary and that nothing distinguishes them. (See §6 —
the CRM has no way to say "two of these" without individuating them.)

**Dating: three statements, no contradiction, and no silent merge.** The
article gives (i) "the end of the 10th century BCE" in the lead, (ii) "c. 908
BCE" in the infobox, and (iii) "cast sometime during the reign of King Gong of
Zhou (r. c. 915–900 BCE)", the reign dates cited to Shaughnessy 1999 p. 25.
`concept P82` says the property records a **maximum** extent and that "if
different sources of evidence justify different maximum extents without
contradicting each other, the resulting intersection of all these extents will
be the best estimate". So I gave the production's time-span two `falls_within`
(P86) parents — the reign, and the tenth century — each with its own P82, and
left the intersection to be computed rather than writing it out. The
qualifications on the circa go in `beginning_is_qualified_by` /
`end_is_qualified_by` (P79/P80), which `concept P79` describes as exactly the
place for "scholarly or scientific opinions and justifications about the
certainty, precision, sources". The infobox's "c. 908 BCE" is the odd one out —
it is more precise than anything the article sources — so it is recorded as a
separate `E13 Attribute Assignment` (`assigned` → the E52, `assigned_property_of_type`
→ "P4 has time-span") with a note saying no source and no author is given for
it. It is not merged into the main bracket and it is not thrown away.

**"Cast for Qiang", and who "the caster" is.** The article says the vessel "was
cast … for a member of the Wei clan, whose name was Qiang", and then twice
calls Qiang "the caster". There is no CRM property for "made for" or
"commissioned by"; searching the mailing list and the issue register for
commissioning/patron turned up nothing normative, and issue 170 shows the SIG
settling on `P14 carried out by … in the role of …` for exactly this kind of
qualified participation. So the production is `carried_out_by` Qiang, with a
note stating that this is the patron sense of "caster" and that the
bronze-worker is not named. I would have preferred `P14.1 in the role of` —
see §5, the format cannot carry it.

**Burial and find: ordered, not dated.** The article dates neither the burial
("some time later") nor anything but the year of the find (1976). Rather than
invent time-spans I used the temporal-order properties, which state exactly
what the article states and nothing more:

```
E12 casting  --ends_before_or_with_the_start_of (P182)-->  E9 burial
E9  burial   --ends_before_the_start_of        (P183)-->  S19 unearthing (1976)
```

**The find is an `S19 Encounter Event` (CRMsci).** CRMbase has no class for
finding a thing; the nearest CRMbase construction, an `E7 Activity` with `P12
occurred in the presence of`, does not say the object was *found*. `concept
S19` is written for this: "an Actor encounters an instance of E18 Physical
Thing … This knowledge may be new to the group of people the actor belongs to.
In that case, we would talk about discovery", and it names the archaeological
in-situ case explicitly. `O19 encountered object` and `O21 encountered at`
carry the object and the findspot. I did **not** use `A9 Archaeological
Excavation` (CRMarchaeo) or `A7 Embedding`: the article says only "unearthed",
names no excavator, no project and no stratigraphy, and A9 would assert a
coordinated, officially directed excavation that the article does not describe.

**Disagreement needs CRMinf, because CRMbase can assign but cannot deny.** Two
points in the article are contested, and in both the interesting content is a
*denial*:

* Shaughnessy 1991 and Durrant 2001 call the inscription "the first conscious
  attempt in China to write history"; Falkenhausen 1993 disputes it.
* The inscription claims King Zhao "tamed Chu and Jing"; Kern 2009 records
  that the campaign was defeated and the king killed.

`E17 Type Assignment` — clayton's device, and the obvious first choice — can
only record that somebody *did* assign a type. There is no negative form of
P42, and stacking a second, contrary type assignment would misrepresent
Falkenhausen, who does not propose a rival label so much as reject this one.
`concept I2` (CRMinf Belief) is built for the case: "the notion that the
associated I4 Proposition Set is to have a particular I6 Belief Value by a
particular E39 Actor", and `concept I6` names TRUE / FALSE / UNKNOWN as the
minimum value set. So the first dispute is one shared
`I17 One-Proposition Set` — a top-level entity, since its subject is the
proposition and not the pan — carrying three `I2 Belief` instances via
`is_subject_of` (J4i), two holding TRUE and one FALSE, each dated and each
`was_concluded_by` (J2i) an `I1 Argumentation` `carried_out_by` the scholar and
`is_documented_in` the publication. The second dispute uses `J27` in the
inverse (`has_a_meaning_belief`) directly from the passage to Kern's belief:
`concept J27` defines it as a shortcut from a Belief to "an E73 Information
Object that expresses the believed propositions", which is precisely what the
passage is, so no separate proposition set is needed there.

**The 2002 listing.** Modelled twice over, because it is two facts: an act
(`E17 Type Assignment` dated 2002, assigning the type "cultural relic forbidden
to be exhibited abroad", documented in the wenbao.net page, with a note that
the article names no listing body) and a standing consequence (`E30 Right`,
"prohibition on exhibiting the Shi Qiang pan abroad", reached by `is_subject_to`
P104). `concept E30` covers "legal privileges concerning material and
immaterial things"; a prohibition is a stretch of "privilege", but E30 is the
only class the CRM offers here and P104's domain E72 Legal Object is squarely
the right subject.

**Narrated events are not asserted as events.** The inscription tells of the
high ancestor's migration and of the Zhou conquest. Modelling that migration as
an `E9 Move` would assert it happened. Instead the referents (the ancestor, the
grandfather, the father, the kings, the Zhou conquest as an `E5 Event`) are
attached with `refers_to` (P67), and the narrative content sits in
`has_symbolic_content` (P190) and typed notes on `E33` component passages
reached by `has_component` (P148). The only thing the model asserts about the
inscription's content is that the inscription says it.

---

## 4. `validate --xml` output, and every finding accounted for

```
$ uv run python search.py validate --xml crm_shi_qiang.xml
188 links checked: 1 ambiguous, 146 ok, 41 ok_literal
structural elements skipped: CRM_Entity in_class unit value

AMBIGUOUS links are legal but underdetermined. This format writes property
labels as element names, so the file cannot say which of them it means --
record the intent in your notes; there is nothing to fix in the document.

  AMBIGUOUS      assigned
      E17 -> E55   at CRM_Entity[E22]/was_classified_by/assigned
      P42 or P141 both fit; the element name cannot distinguish them
```

No `illegal`, no `unknown_name`, no `label_mismatch`, no `malformed`,
no `not_a_class_link`, no `attached_to_property`.

An earlier revision of this file reported `222 links checked: 1 ambiguous, 34
attached_to_property, 146 ok, 41 ok_literal`. The 34 were the typed notes
copied from amol, described in §2(e); folding the type into the note text
removed all 34 links and the finding with them. The remaining counts are
unchanged, which is the check that nothing else moved.

**The one ambiguous link.** Both `P42 assigned` (E17 → E55) and `P141 assigned`
(E13 → E1) carry the label "assigned", and since E17 is a subclass of E13 and
E55 a subclass of E1, both fit at that position. **The intent is P42**, the
specific Type Assignment property. It cannot be disambiguated in this format —
the inverse labels collide too ("was assigned by" for both) — so there is
nothing to change in the file. Two mitigations are in the document anyway: the
assignment is classed `E17: Type Assignment`, whose only reason to exist is
P42, and the same element name used inside the `E13` dating assignment resolves
cleanly to P141 there because its range is `E52`, not `E55`. Clayton hits the
identical collision: all 32 of its ambiguous links are its 32 `assigned`
elements.

**On the two remaining "skipped" names**, `unit` and `value`: they are listed by
the validator but do not occur in my file (see §2(d)).

I also validated the two published examples themselves, and every individual
link type in the model, with `search.py validate <domain> <prop> <range>`,
before writing it — roughly fifty checks. Two probe files were used to
establish that the format tolerates hyphenated labels (`has_time-span`),
non-`E` model prefixes in `in_class` (`S19:`, `TX1:`, `I17:`), and inverse
labels from the extensions (`was_object_encountered_through`).

---

## 5. What the format cannot carry

* **`.1` properties.** Nesting `in_the_role_of` under `carried_out_by` is
  rejected — `NOT_A_CLASS_LINK … its domain is the property P14, not a class` —
  and rightly so, since the element-nesting grammar only expresses class-to-class
  links. So `P14.1 in the role of`, `P139.1 has type` (which would have marked
  the pinyin form as a romanisation) and `P62.1 mode of depiction` are all
  unreachable — and so, as §2(e) sets out, is `P3.1 has type`, which amol uses
  on every one of its notes. There is **no** `.1` property this format can
  carry. Where one mattered I folded the qualifier into the literal text
  (`[Statement] …`) or wrote it out as prose in the note, and said so.
* **No identifiers or references.** Every re-mention of an instance is a
  repeated label string; a typo silently splits an entity in two. The findspot,
  Fufeng County, Baoji, Shaanxi, Scribe Qiang, the burial, the 1976 find and
  Shaughnessy 1991 each appear more than once and were checked for exact
  string identity.
* **Encoding.** Both examples declare ISO-8859-1. This file declares UTF-8
  because the object's name, the clan graph 𢼸 and 饕餮 require it.

## 6. What the CRM itself does not cover well

* **Cardinality of features.** There is no way to say "the vessel has two
  handles" other than to mint two instances. `P57 has number of parts` is
  domain E19 and is about the parts of the object, not about how many of a
  given feature it bears.
* **Aggregates that are neither collections nor functional sets.** The article
  says the pan was buried "along with over 100 other vessels belonging to the
  family". `E78 Curated Holding` requires assembly and maintenance "for a
  specific purpose and audience, and according to a particular collection
  development plan"; `E22`'s aggregate clause requires that the aggregate be
  "made for functional purposes". A hoard as excavated is neither. I recorded
  the co-deposit as a note on the burial and minted no entity, rather than
  assert either reading.
* **"Made for" / commissioned by.** No property, and the workaround (`P14` +
  `P14.1`) is precisely the one this file format cannot express.
* **Reigns.** Nothing in the model addresses regnal periods; `docs` returned no
  guidance when asked. King Gong's reign is an `E4 Period` carrying the
  `E52 Time-Span`, and the king is linked to it only through the inscription's
  `refers_to`. A `P14`-style link from a reign to its ruler would need the
  reign to be an `E7 Activity`, which overstates "reign" as an action.
* **Denial.** Recorded above: CRMbase's assignment classes have no negative
  form. This is a real gap that CRMinf fills, at the cost of a second model.

## 7. Tool findings

* `concept J26` returns "No such concept", yet J26 is named inside `concept
  J27`'s own scope note as the property J27 shortcuts. The CRMinf index carries
  only J1–J5, J7, J24, J27; the class index likewise shows CRMsoc entirely as
  "(no label recorded) — archive-attested only". The extension coverage is
  partial, and a user following a scope note's cross-reference will hit a wall.
* `docs "how to model the excavation and discovery of an object, findspot"`
  returned nothing about excavation or findspots — its top hits were the
  spatial-relations figure, the extensions section and E26. The same for
  reigns, and for commissioning. `ontology --model CRMsci` / `--model
  CRMarchaeo`, which lists every identifier with one line of scope note, is
  what actually found `S19 Encounter Event`; the semantic search over the
  reference text did not. For "which class covers X" questions the flat listing
  beat the search.
* `validate --xml` on the *published examples* was the single most useful call
  in the whole exercise: it located all three bad names, the domain violation
  and the class-name drift in a few seconds, and it is what stopped
  `at_most_within` from being copied into this file. The one defect it did not
  catch on the first pass was amol's typed notes; `attached_to_property` arrived
  in the tool partway through this run and caught them, which is a fair
  illustration of the point — reading the example carefully had not caught it,
  and neither had I.
* `show <chunk_id>` and `concept <id>` were reliable throughout; every class and
  property identifier used here was checked with `concept` or `validate` rather
  than recalled.

---

## 8. Scope: what the article does not support, modelled as nothing

The brief fixes seven headings. Where the article gives no basis, the record
below is the whole of my treatment — nothing is asserted in the XML.

1. **Object.** *Condition* — the article says nothing about the vessel's
   state of preservation, completeness, corrosion or damage. No `E3 Condition
   State`, no `P44`. *Identifier* — no accession or inventory number is given
   for the Baoji Bronzeware Museum (the only catalogue number in the article,
   1993.048.001, belongs to the Calgary **replica** and is out of scope).
   *Weight* — not given; only height and diameter.
2. **Making.** *Place of production* — never stated. The vessel was found in
   Fufeng County but the article does not say it was cast there, and I did not
   put `P7 took place at` on the production. *The artisan* — not named; only
   Qiang, the patron. *Technique beyond "cast"* — the article says the vessel
   and its decoration were cast and no more; no piece-mould or lost-wax claim
   is made here. *Contested attribution* — there is none: no rival maker,
   owner-dedicatee or workshop is proposed. The only contested point about the
   making is the dating, which is modelled.
3. **Depicts / decoration.** Fully modelled: taotie exterior, inscription
   interior, the three quoted royal passages, the family section. The article
   quotes no more of the text than that.
4. **Deposition and rediscovery.** Burial and find are modelled. *Excavation*
   — the article records no excavation, excavator, project or date beyond the
   year; no `A9`, no `A1`, no stratigraphy. *Findspot precision* — nothing
   below "Fufeng County, Baoji, Shaanxi"; the findspot instance carries no
   coordinates and no `E27 Site`.
5. **Ownership and custody.** *No transfer of title is recorded anywhere in the
   article* — not from Qiang, not to the state, not to the museum. There is no
   `E8 Acquisition` in this file and no `P52 has current owner`, because "kept
   at" is a statement about custody, not ownership. *No transfer of custody
   event* either: the article gives the museum but no date and no transferor,
   so the state (`P50 has current keeper`, `P55 has current location`) is
   asserted and the event is not. `connect E22 E39` confirms this is what the
   shortcut is for: it gives P50's full path as *E18 → P30i transferred through
   → E10 Transfer of Custody → P29 custody received by → E39*, so P50 is
   precisely the form to use when the transfer event itself is unrecorded.
   `P105 right held by` is absent for the same reason — the article names no
   holder of the prohibition. The 2002 listing and the resulting prohibition
   are modelled, as is the burial.
6. **Reconstruction, restoration, alteration.** **The article records none** —
   no repair, no reconstruction, no later addition or removal, and nothing
   reversed or superseded. There is no `E11 Modification`, `E79 Part Addition`,
   `E80 Part Removal` or `E81 Transformation` in this file, and none should be
   inferred from the vessel's age.
7. **Sources for contested points.** Modelled: Shaughnessy 1991, Durrant 2001,
   Falkenhausen 1993 (the historiography dispute); Kern 2009 (the King Zhao
   claim); Shaughnessy 1999 (the regnal chronology); Shirakawa 1962, CUHK 2001,
   the 1994 *Collected Shang and Zhou Bronze Inscriptions*, Khayutina 2021 and
   the Columbia translation (the text itself); the wenbao.net page (the 2002
   listing); the Wikipedia article itself, once, on the object.

Deliberately excluded per the brief: the Calgary Chinese Cultural Centre
Museum replica; the reception of the inscription as literature beyond the
contested characterisation itself, which is in scope because it is *the*
disputed claim of the article and item 7 requires its sources.

One judgement call worth a reviewer's eye: I treated "the first conscious
attempt in China to write history" as a contested statement **about the
inscription** rather than as reception, and modelled it. If it reads as
reception, the three `I2 Belief` instances and the `I17` proposition set in the
second `CRM_Entity` are the part to remove; nothing else depends on them.
