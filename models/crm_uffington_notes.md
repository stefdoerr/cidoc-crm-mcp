# Uffington White Horse in CIDOC CRM — modelling notes

Model: `crm_uffington.xml`.
Subject: <https://en.wikipedia.org/wiki/Uffington_White_Horse> (read as wikitext,
so that the infobox and the reference apparatus were visible as article content).
Format references: `crm_amol_1.xml`, `crm_clayton1.xml`.
Everything asserted about the CRM below came through `search.py`.

32 distinct classes, 50 distinct properties.

---

## 1. Conventions taken from the two examples

Both examples share a form that I have kept exactly:

- `<CRMset>` root, an XML declaration, and the `crm.xsl` stylesheet PI. I kept the
  PI even though the stylesheet is not distributed with either example; it is part
  of the published form. I changed the declared encoding from ISO-8859-1 to UTF-8,
  because the model contains no ISO-8859-1-only characters and UTF-8 is the safer
  default for a file that will be read by tools neither example anticipated.
- Instances are `<CRM_Entity>` elements whose **text content is the instance
  label**, and the label *is* the identity: repeating a label elsewhere in the
  document refers to the same instance. Clayton relies on this heavily (its
  `Flora Virginica` appears 25 times), and so does this model — sources, actors
  and places are written out at each point of use rather than cross-referenced.
  I therefore had to disambiguate labels by hand, e.g. `Whitehorse Hill (site)`
  (E27) versus `Whitehorse Hill (place)` (E53).
- The class is given by a child `<in_class>Exx: Label</in_class>`.
- Properties are elements named after the CRM property label with spaces replaced
  by underscores; inverse labels are used freely (`is_documented_in`,
  `was_classified_by`, `is_referred_to_by`), and the property element's text is
  the target instance's label. Nesting continues to arbitrary depth.

### Where the two examples disagree, and what I chose

| Point | amol | clayton | Taken here |
|---|---|---|---|
| Typed notes | `<has_note>` carries a nested `<has_type>` — `Statement`, `Description`, `Marks`, `Made Note`, `Subject` | bare `<has_note>` | **amol.** The typed note is the only way this format can distinguish a description from a source note from a record of what the article does *not* say, and this model leans on that distinction. Vocabulary used: `Description`, `Statement`, `Contested reading`, `Absence in source`, `Source note`, `Modelling note`. |
| Dimensions | `<has_dimension>` with non-CRM `<value>` and `<unit>` children | absent | **Neither, quite** — see §2. |
| Events | absent | `changed_ownership_by` / `was_classified_by` with nested actor, place and date | **clayton**, corrected — see §2. |
| Label placement | label on the same line as the opening tag | label on its own line | amol's, purely cosmetic. |
| Role qualifiers on `in_class` | `E55: Object Type`, `E55: Dimension Type` | `E55: Clayton Barcode Type`, `E55: Acquisition Type` | **Both agree**, so kept — see §4. |

One convention I took from clayton and used more than it does: clayton records a
*determination* (`E17 Type Assignment`, with `carried_out_by`, `assigned` and a
date) rather than only its outcome, while still asserting the outcome directly
via `has_type`. That is the CRM's own shortcut doctrine (the E13 scope note: "All
properties assigned in such an action can also be seen as directly relating the
respective pair of items"), and it is how every contested point in this article
is handled here.

---

## 2. Where an example is wrong, and what I did instead

I ran `validate --xml` on both published examples before writing anything.
`crm_amol_1.xml` is clean. `crm_clayton1.xml` reports
`656 links checked: 25 illegal, 420 ok, 120 ok_literal, 91 unknown_name`.

Four distinct defects, all of them in clayton, all avoided here:

1. **`changed_ownership_by` is not a CRM property label** (25 occurrences). The
   intended property is P24 *transferred title of*, whose inverse label is
   **`changed ownership through`**. Where I needed it I would have written
   `changed_ownership_through`; in the event this article records no acquisition
   (§5), so the element does not appear.
2. **`preferred_identifier_is` is not a CRM property label** (25 occurrences).
   P48 is *has preferred identifier (is preferred identifier of)*; the correct
   element from the object's side is `has_preferred_identifier`. I verified it
   validates, then chose not to use it anyway — see the NHLE number conflict in §5.
3. **`at_most_within` is not a CRM property label** (41 occurrences). Clayton uses
   it for outer bounds ("at most within 1727" for a collection no later than
   1727), which is P82 **`at_some_time_within`** (E52 → E61). That is what this
   model uses throughout, with P81 `ongoing_throughout` for the one inner bound
   the article supports (the scouring tradition, 1755–1857).
4. **`took_place_at` used outside its domain** (25 occurrences, all 25 of the
   `illegal` findings). Clayton nests P7 *took place at* under
   `transferred_title_to`, so it hangs off an E39 Actor; P7's domain is E4 Period.
   In this model `took_place_at` and `took_place_on_or_within` hang off the event
   itself.

Two further clayton defects that the validator does not flag but that a reader
should not copy: malformed class ids (`E:55 Type Type` — the colon is misplaced,
and `in_class` is skipped structurally so nothing catches it), and empty
`<assigned>` elements in the BM000098053 determination.

**Amol's `<value>` and `<unit>`.** These are not CRM property labels either;
the validator whitelists them as *structural* elements and skips them, so amol
passes clean while encoding its dimension values in nothing at all. P90 *has
value* (E54 → E60) and P91 *has unit* (E54 → E58) exist and validate. I used
`has_value` and `has_unit` and dropped `<value>`/`<unit>` rather than write both
and assert each measurement twice. This is the one place where I have not
followed the only published guidance on the point.

**E22 Man-Made Object.** Amol's class labels are pre-7.x (`E22: Man-Made
Object`, `E42: Object Identifier`). `concept E22` gives *Human-Made Object* as
the current label. Current labels are used here.

**E40 Legal Body.** My first draft typed the National Trust as `E40: Legal Body`,
which is what an example of this vintage would have used. `validate --xml`
returned `unknown_class E40`, and `concept E40` gave the reason and the fix:
"E40 Legal Body | use E74 Group" from the v7.3.2 deprecated-class migration
table. All organisations here are E74 Group. This is recorded as a note inside
the model as well, since it is the kind of thing a reader of the XML will wonder
about.

---

## 3. The choices that were genuinely difficult

### 3.1 What class is a hill figure?

The object is a landscape feature: trenches cut into a chalk hillside and packed
with crushed chalk. It has no boundaries that separate it from the hill, so it is
not an E19 Physical Object and therefore not E22 Human-Made Object (whose scope
note requires "physical boundaries that separate them completely in an objective
way from other objects").

`concept E25` settles it. **E25 Human-Made Feature** — "physical features that
are purposely created by human activity" — carries as its own examples "the
temple in Abu Simbel before its removal, which was carved out of solid rock" and
"the carved letters on the Rosetta Stone". A chalk-cut figure is the same kind of
thing. E25 is a subclass of both E24 Physical Human-Made Thing (so P108 *has
produced* and P62 *depicts* apply) and E26 Physical Feature (so it is an E18 and
takes materials, condition, owners and location).

The hill is **E27 Site** ("pieces of land or sea floor"), which is a sibling of
E25 under E26.

**Relating the two was the awkward part.** The obvious candidate, P56 *bears
feature*, has domain E19 Physical Object, and `validate E27 bears_feature E26`
returns `illegal: E27 is not a E19` — a site cannot bear a feature. `connect E25
E27` offers P46 *is composed of / forms part of* as the only mereological link
available, so the figure `forms_part_of` the site and the site `is_composed_of`
the figure. It is the right answer but it is reached by elimination, and the
CRM's inability to say "this feature is cut into that site" other than as
part-whole is a genuine thinness (§6).

### 3.2 Contested dating and attribution

The article carries six rival accounts of when and by whom the figure was made:
Aubrey on Hengist and Horsa; Aubrey again on the British Celts; Wise (1742) on
Alfred the Great; Piggott (1931) on c. 100 BC; Marples (1949) on the Bronze Age;
Palmer and Miles on 1380–550 BC by luminescence.

Each is an **E13 Attribute Assignment** hung off the E12 Production by P140i
`was_attributed_by`, with `assigned_property_of_type` naming the property being
asserted (`carried out by` or `has time-span`), `assigned` carrying the value,
`carried_out_by` naming the scholar, a date, and `is_documented_in` pointing at
the source the article cites. This is what the E13 scope note describes: "the use
of instances of E13 Attribute Assignment marks the fact that the maintaining team
is in general neutral to the validity of the respective assertion, but registers
someone else's opinion", and it explicitly anticipates that "multiple use of
instances of E13 Attribute Assignment may possibly lead to a collection of
contradictory values."

`docs --kind principles` supplies the licence for leaving them contradictory:
principle **6.2 "Allow alternatives or contradictions in the data — Let 100
flowers blossom"**: "To adequately represent the available knowledge, we must be
able to represent its indeterminate or plural state. Therefore, the knowledge
base should admit multiple, potentially cont[radictory]…". Nothing here is
reconciled.

The production's own P4 `has_time-span` **does** carry 1380–550 BC as an outer
bound, because the article asserts it in its own voice ("was created some time
between 1380 and 550 BC"; "the figure's origin was finally settled"). Asserting
the outcome *and* recording the determination that produced it is clayton's
pattern (`has_type` alongside `was_classified_by`) and the CRM's shortcut
doctrine.

One consequence worth flagging: the luminescence date is a date *for silt*, not
for the cutting. I modelled that chain rather than collapsing it — an E13 that
assigns the time-span to the silt deposits, and a second E13 that assigns the
same time-span to the production, linked by P17 `was_motivated_by`.

**Rule adopted, and stated because it is a real editorial decision:** an E13 or
E17 is created only where the article names the person or body making the
assertion. Unattributed opinions ("it has long been debated whether…", "the horse
is thought to represent a tribal symbol", "the notion of it being a post-Roman
creation remained popular", "some scholars have compared the figure to Epona")
are recorded as typed `Contested reading` notes on the entity they concern. The
alternative — an E13 with an invented anonymous actor — would fabricate an actor,
and P14 *carried out by* is quantified as necessary on E13. Ann Ross is the edge
case: the article says she conducted comparative analysis in 1967 but records no
conclusion of hers, so she gets an E7 Activity with no assignment attached and an
explicit note that there is nothing to assign.

### 3.3 What it depicts

The figure has been called a horse since the eleventh century, but the article
reports live disagreement about whether it is a horse, a dog or a sabre-toothed
cat, and separate readings of it as a tribal symbol and as a solar horse.

`concept P199` gave the sharpest distinction available. P199 *represents instance
of type* "is used when the identity of the thing depicted is unknown or
unrecorded, but is clearly a particular thing of that type", and its scope note
adds: "If the instance of E36 Visual Item directly depicts the concept of the E55
Type rather than an instance of a thing of that type, then this should be
represented using E36 Visual Item P138 represents E55 Type." That is exactly the
axis the article's debate runs along. I used P199 with `horse`, and recorded in a
note attached to that very link that if the emblematic readings are right then
P138 is the correct property instead. The uncertainty is in the model, not
resolved away.

Pollard's solar-horse reading is named and dated, so it is an E17 Type Assignment
on the visual item. The dog and sabre-toothed cat readings are unattributed, so
they are notes.

**P130 shows features of** carries the resemblance to the horses on the coinage
of the Dobunni and Atrebates and on the Marlborough Bucket. Its scope note says
the domain should be "the derivative or influenced item", which on the article's
own dating would make the *coins* the domain — but the article claims only
resemblance, and the same scope note says P130 "expresses a symmetric
relationship in case no direction of influence can be established". I asserted it
from the Uffington design and said so in a note. The refining property P130.1
*kind of similarity* is not used: the example format has no unambiguous way to
write a property of a property, and a nested `<kind_of_similarity>` element makes
the validator report `not_a_class_link: its domain is the property P130, not a
class`. (Amol's nested `<has_type>` inside `<has_note>` looks like P3.1 but the
validator resolves it as plain P2, because P3's range is a literal. I use the
idiom for the same reason amol does — it works — but that is what it means.)

### 3.4 Alteration, and the one alteration that was reversed

- **Scouring** is both a single continuing practice and a series of datable
  episodes, so it is one collective E11 Modification decomposed by P9
  `consists_of` into three: the septennial scourings to the late nineteenth
  century, the 2009 revival, and the continuing National Trust programme. P9's
  domain is E4 Period; `validate E11 consists_of E11` confirms E11 inherits it
  through E7 → E5 → E4.
- **The 2002 rider and dogs** and **the 2012 jockey** are each an **E12
  Production** that both `has_produced` the new features and `has_modified` the
  horse. Not E79 Part Addition: its scope note requires that "both the E18
  Physical Thing being augmented and the E18 Physical Thing that is being added
  are treated as separate identifiable wholes **prior to**" the addition, and
  these figures did not exist before they were cut. E12 is a subclass of E11, so
  one event legitimately carries both properties.
- **The wartime covering** is an E11 Modification with P126 `employed` turf and
  hedge trimmings and P21 `had_general_purpose` concealment from aerial
  navigation. Not E79 either: the turf never became part of the figure.
- **The post-war uncovering by W. F. Grimes** is the only alteration in the
  article that is explicitly undone. The CRM has no "reversed" or "undid"
  property. P17 *was motivated by* links the uncovering back to the covering,
  which is true but weaker than the relation actually is, and a note says so.
- **The 2023 plan** is an E65 Creation of an E29 Design or Procedure, because the
  article reports the project as *planned*, not carried out. The 2024 restoration
  is a separate E11 Modification, and the two are **not** linked: the article
  never says the 2024 project executes the 2023 plan, and P33 *used specific
  technique* would have been an invented connection.

### 3.5 The excavation, and the deposit that was dated

The 1990 excavation is **A9 Archaeological Excavation** (CRMarchaeo) with
**AP3 `investigated`** → the E27 Site. CRMbase has no excavation class; A9's own
scope note describes "a coordinated set of activities performed on an area
considered as part of a broader topographical, rural, urban or monumental
context", which is what this was. Both examples are pure CRMbase, so this is a
deliberate departure, taken because the brief asks specifically about excavation
and because AP3's domain and range (A9 → E27) fit without strain.

The silt deposits are **A2 Stratigraphic Volume Unit**. Relating them to the
figure was the second awkward join. AP21 *contains* runs the wrong way (the silt
does not contain the horse); P46 *forms part of* would assert that a later
intrusive accumulation is a constituent of the thing that was made, which I am
not prepared to claim. Instead the figure has P59 `has_section` → an E53 Place
"the trenches of the Uffington White Horse", and the silt has P53
`has_former_or_current_location` → that same place. The deposit is located in the
cut without being made part of the figure.

---

## 4. `validate --xml` output, and every finding accounted for

```
415 links checked: 341 ok, 74 ok_literal
structural elements skipped: CRM_Entity in_class unit value
```

Zero `illegal`, zero `unknown_name`, zero `unknown_class`, zero
`not_a_class_link`. Every element name in the file is a real CRM property label
or inverse label, and every link stays inside its declared domain and range.

Findings printed below the summary line: **36 `LABEL_MISMATCH`, all of one kind.**

```
LABEL_MISMATCH E55: Note Type
    E55 is named 'Type' in the model; document says 'Note Type'
    -- a retired name, or a role qualifier
```

Counted: `Note Type` ×16, `Technique Type` ×4, `Property Type` ×2, `Modification
Type` ×2, `Legal Status Type` ×2, `Depicted Type` ×2, and one each of `Tool`,
`Purpose`, `Object`, `Identifier`, `Dimension`, `Condition`, `Assertion` and
`Appellation Type`. **All 36 are role qualifiers on E55, and none is a retired
name.** They stand, for three reasons:

1. It is the shared convention of both published examples — amol writes `E55:
   Object Type` and `E55: Dimension Type`, clayton writes `E55: Clayton Barcode
   Type` and `E55: Acquisition Type` — and running the same check on the examples
   reproduces the same warning there (amol: 4, clayton: 11).
2. The validator's own message offers "or a role qualifier" as the benign reading,
   and the qualifier is not counted in the summary tallies.
3. It carries information the format otherwise loses: in a document with 100-plus
   instances of E55, the qualifier is what tells a reader whether a given type is
   a note kind, a technique, a legal status or a depicted subject.

Every other class label in the file is the exact current label from `ontology`
(`E25 Human-Made Feature`, `E42 Identifier`, `E52 Time-Span`, and so on), so no
mismatch is a retired name.

**Findings fixed during the run, listed because they are the interesting ones:**

| Finding | Fix |
|---|---|
| `unknown_class E40` on the National Trust | `concept E40`: deprecated, "use E74 Group". Changed. |
| `illegal has_time-span: E31 is not a E2` on the Red Book of Hergest | P4's domain is E2 Temporal Entity; a document is not one. The manuscript's date now hangs on an E65 Creation, `was_created_by`. |
| `not_a_class_link kind_of_similarity` (probe) | P130.1 dropped; the qualification is a note. |
| `illegal bears_feature: E27 is not a E19` (probe) | P56 abandoned for P46 — §3.1. |
| `illegal has_right_on: E30 is not a E39` (probe) | P105 runs E72 → E39, not from the right. Dropped; no right-holder is named anyway. |
| `unknown_name is_current_or_former_owner_of` (probe) | The inverse label is *is former or current owner of*; word order matters. Used P51 from the object's side instead. |

I checked the element names in a probe file first, then checked the finished
document as written. The two probe files are in the scratchpad
(`probe1.xml`, `probe2.xml`).

**One caveat for the reviewer:** `search.py` was being edited by another agent
during this session (a traceback moved from line 1042 to line 1055 between runs,
and `LABEL_MISMATCH` did not exist when I first validated the two examples). The
example figures quoted in §2 and the final figure above were produced by
different builds of the validator. Re-running everything against one build would
be worth a minute.

---

## 5. Absences: things in the fixed scope that this article gives no basis for

Recorded here and, where they belong to a specific entity, as `Absence in source`
notes in the XML. Nothing was invented to fill them.

- **Deposition, burial, findspot, rediscovery — nothing.** The figure was never
  deposited and never found. It has been continuously visible since it was made;
  the article's own claim is that it "has remained clear of turf throughout its
  long existence" apart from the deliberate wartime covering. There was no
  excavation *of the object*: the 1990 excavation dug the site and the silt in the
  trenches, and no part of the figure was lifted or removed. CRMsci S19 Encounter
  Event, which would be the class for a discovery, is not used, and no E9 Move
  exists in the model.
- **Ownership transfer and custody transfer — nothing.** The article says the site
  is owned and managed by the National Trust and never says from whom, when or by
  what act. P52 `has_current_owner`, P51 and P50 are asserted; no E8 Acquisition
  and no E10 Transfer of Custody. The lord of the manor who sponsored the
  post-scouring festival is recorded as sponsor only — the article does not say he
  owned anything, and no ownership is inferred from it.
- **Ownership determinations — none.** Nothing in the article is an assessment of
  who owns the figure, so there is no E13 in the ownership area.
- **The maker — unnamed.** The E12 Production carries no P14 `carried_out_by`.
  Every candidate maker in the article appears only inside somebody's E13.
- **The designating authority for the scheduling — unnamed.** The E17 for the 1929
  scheduling has a date and an assigned type but no P14.
- **A right-holder for the scheduled-monument protection — unnamed.** The E30
  Right exists; P105 *right held by* does not, and no statute is named.
- **Decoration — none.** The figure is the image; the article records no
  ornament, inscription or mark on it. No E34 Inscription, no E37 Mark, no P128
  *carries*.
- **Removal of the 2002 additions and of the 2012 jockey — not recorded.** The
  article says an alteration happened and never says it was undone. No removal is
  modelled for either; the silence is noted on both events.
- **Any measurement of the shrinkage since the 1980s — none.** The condition state
  exists; there is no E16 Measurement and no dimension for the loss.
- **Parts — one only.** The head is the sole part the article names, and it names
  it in an image caption. It is modelled with a note saying so. The trenches are
  modelled as a Place (an extent), not as parts.

Two internal contradictions in the article are carried into the model unresolved
rather than picked between, per principle 6.2:

- **Length: 110 m** (opening sentence, sourced to Powell 2017) versus **100 m**
  (infobox). Two E54 Dimensions, both typed `length`, with a note on the second.
- **NHLE entry number: 1008413** (body, with the descriptive title "The White
  Horse hill figure 170 m NNE of Uffington Castle") versus **1008412** (infobox).
  Both are E42 Identifiers attached by P1. P48 *has preferred identifier* is
  deliberately **not** used: the article gives no basis for preferring either, and
  using P48 would smuggle in a judgement.

Also carried rather than corrected: the article writes "Morris Marple" in the
passage on the 1949 Bronze Age dating and "Marples, Morris" in its own
bibliography for the same author's book. Noted on the E13.

## Scope decisions inside the fixed list

- **Excluded as reception / later cultural reference**, per the brief: the 2003
  Big Brother advertisement (a separate temporary hill figure "placed near the
  figure", not an alteration of this object); the Guardian's "masterpiece of
  minimalist art"; all later white horses, replicas, emblems, literature and
  music; the scouring *festival* itself, which is recorded only as a note on the
  episode of restoration it accompanied.
- **Included as needed to place the object**: Whitehorse Hill (site and place),
  Uffington Castle (the NHLE entry locates the figure by reference to it, and the
  figure is thought connected to its builders), and the Letcombe Bassett
  settlement — the last named only inside the E13 that uses it to claim who made
  the figure, with no description of its own.

---

## 6. Where the CRM, or this format, does not cover the case well

1. **A feature cut into a site.** The only relation available between E25 and E27
   is P46 part-whole (`connect E25 E27`). P56 *bears feature* would say it, but
   its domain is E19 Physical Object, so a site can never bear a feature. The
   distinction between "is a part of" and "is incised into" is not expressible.
2. **Undoing.** There is no property meaning that one activity reversed another.
   The wartime covering and its post-war removal are related only by P17 *was
   motivated by* plus prose. Given that the brief asks specifically for
   reconstructions "including any later reversed or superseded", this is a real
   gap for this kind of object.
3. **Continuous maintenance as constitutive.** A chalk figure exists only because
   it is re-cut; the article says so outright. The CRM has E11 Modification and
   P9 to decompose a series of them, but nothing that says the thing's persistence
   depends on the series. `P130`, `E81 Transformation` and `E12` all say something
   adjacent and none says this. Left as prose.
4. **Whether scheduling is an E30 Right.** E30 is scoped to "legal privileges
   concerning material and immaterial things", with reproduction and property
   rights as its examples. A statutory *protection*, which restricts what the
   owner may do and vests in no named party, is not obviously a privilege. I used
   E30 with P104 *is subject to* because it is the closest thing available, and
   also recorded the scheduling as an E17 Type Assignment with its 1929 date, so
   the fact survives even if the E30 reading is judged wrong. Flagging it as
   genuinely unresolved rather than settling it.
5. **A property of a property.** P130.1, P62.1, P3.1 and P14.1 cannot be written
   unambiguously in this XML form. Amol's nested `<has_type>` inside `<has_note>`
   reads like P3.1 but the validator resolves it as P2. A `<kind_of_similarity>`
   element resolves to P130.1 but is reported `not_a_class_link`. The format
   predates the `.1` properties and has no slot for them.
6. **Mixing extension models.** Both published examples are pure CRMbase, so
   there is no precedent in the format for A9 or A2. The validator accepts them
   and resolves AP3 and its inverse correctly, but a consumer written against the
   examples would not expect a class id beginning with `A`.

## 7. Notes on the search system itself

Recorded because the point of the exercise is to test the tool.

- **`ontology --model CRMbase`** — one line per identifier with domain and range —
  was the single most useful call, and made per-id recall unnecessary.
- **`concept E40` caught a real error before I made it**, reporting the
  deprecation *and* the migration instruction ("use E74 Group"). `concept` on a
  live class gives the scope note, the examples, the siblings, the required
  properties and both directions of every applicable property; that was enough to
  decide §3.1 and §3.3 without going anywhere else.
- **`validate --xml` is the load-bearing tool.** It caught E40, the P4-on-E31
  domain violation, `bears_feature`, `has_right_on`, and my wrong guess at the
  inverse label of P51 — five errors I would otherwise have shipped. Checking
  element names in a throwaway probe file first, then the real document, worked
  well.
- **Gap: there is no way to read a full document section.** `docs` returns only
  the opening ~300 characters of a section; `--raw` does not lengthen it; `show`
  works only on archive messages and returns "No such message" for a document id.
  I reconstructed principle 6.2 by firing `quote crmprinciples#s0053 "<guess>"`
  repeatedly and stitching the ~15-word windows together. That worked, but it is
  guess-and-check, and it would fail for any passage whose wording I could not
  anticipate.
- **Minor:** `validate --xml` resolves its path relative to the repo root, and a
  relative path from elsewhere produces a raw `FileNotFoundError` traceback rather
  than a message.
- **Minor:** `validate <s> <p> <o>` needs three separate arguments; passing the
  triple as one quoted string gives a usage error that does not say which form was
  wrong.
