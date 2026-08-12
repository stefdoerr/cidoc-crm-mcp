# Bianzhong of Marquis Yi of Zeng — modelling notes

Model: `crm_marquis_yi.xml`.
Source modelled: the English Wikipedia article *Bianzhong of Marquis Yi of Zeng*.
Format references: `crm_amol_1.xml`, `crm_clayton1.xml`.
Everything I learned about the CRM came through `search.py`; the CRM sources
themselves were not opened.

**The article is short — about 400 words of prose.** Four of the seven scope
items have no basis in it at all. They are recorded as absences in §5 below
and nothing is modelled for them. The model is short because the source is
short, not because the scope was trimmed.

---

## 1. Conventions taken from the examples

Both examples share one dialect, which I followed:

- A root `<CRMset>` containing top-level `<CRM_Entity>` elements, one per
  object treated as a unit of documentation. My file has two: the instrument,
  and the wooden hammers found with it.
- An instance is a **label plus a class**: the element's leading text is the
  instance's identifying label, and a nested `<in_class>Enn: Label</in_class>`
  gives its class. Identity is by label string — clayton repeats the same
  `Clayton` actor and `Virginia` place in all 25 entities and expects them to
  be the same thing. I do the same with
  `The place of the Tomb of Marquis Yi of Zeng` and
  `The 1978 excavation of the Tomb of Marquis Yi of Zeng`, each of which
  appears under both top-level entities.
- **Properties are elements named with the CRM property label, lowercased,
  spaces to underscores, in whichever direction reads better from the
  containing instance** — `is_identified_by` (P1), `was_classified_by` (P41i),
  `is_documented_in` (P70i). I use the inverse direction the same way:
  `was_produced_by` (P108i), `was_object_encountered_through` (O19i).
- Nesting *is* the link: a property element's content is the range instance,
  written out in full each time it occurs.
- Places are chained with nested `falls_within` (clayton: Virginia → USA). I
  reuse this for the six-deep findspot hierarchy.
- Dimensions are `has_dimension` → `E54: Dimension`, carrying a `has_type`
  for the dimension kind and bare `<value>` / `<unit>` elements (amol).
- Typed notes: `has_note` with a nested `has_type` naming the kind of note
  (amol's `Statement`, `Description`, `Marks`, `Made Note`). I use
  `Statement`, `Description`, `Sound`, `Scope`, `Source Note`.

### Where the two examples disagree, and what I chose

| Point | amol | clayton | Chosen |
|---|---|---|---|
| Granularity | 30 flat sibling entities, no nesting below the object | 1 entity per specimen, deep nesting, events and actors | clayton — the article's content is events and relations, not a flat record |
| Notes | heavily typed (`has_type` inside `has_note`) | mostly untyped | amol — the type is what tells a reader whether a note is the article's words or my caveat |
| Identifiers | `is_identified_by` only | `is_identified_by` + `preferred_identifier_is` | amol — and see §2; `preferred_identifier_is` is not a real label |
| Sources | `is_documented_in` → E31 | `is_referred_to_by` → E32 Authority Document, with a `has_note` for the page reference | both, with a distinction: `is_documented_in` for what documents the object (the Wikipedia article, its photograph), `is_referred_to_by` for works the article points at |
| Dates | none anywhere | `at_most_within` → E52 | neither works; see §2 |
| Text layout | label indented on its own line, or inline | same, inconsistently | indented, consistently |

Two deviations from **both** examples, both forced:

- **Encoding.** Both declare `ISO-8859-1`. That charset cannot represent
  曾侯乙编钟, and the object's Chinese names are half of its identity. The
  file is UTF-8.
- **`<?xml-stylesheet href="crm.xsl"?>`.** Both carry it; I dropped it, as no
  `crm.xsl` accompanies this file and a dangling stylesheet reference is
  noise.

---

## 2. Where the examples are wrong

`validate --xml` on the two references (run to learn the dialect, not to
grade them):

```
amol:    637 links checked: 426 ok, 211 ok_literal        — clean
clayton: 656 links checked: 25 illegal, 420 ok, 120 ok_literal, 91 unknown_name
```

clayton's 91 `unknown_name` hits are three distinct names, each repeated
once per specimen, and the 25 illegal hits are one mistake repeated:

| In clayton | Problem | What I did |
|---|---|---|
| `at_most_within` (×41) | Not a CRM property label. It is the CRM 3.x name for the maximum bound of a time-span. | Used `at_some_time_within`. `search.py validate E52 "at some time within" E61` → **LEGAL P82**; `concept P82` confirms it is exactly "the maximum period of time within which an E52 Time-Span falls", with worked examples in BC dates. |
| `preferred_identifier_is` (×25) | Not a label. P48's labels are *has preferred identifier* / *is preferred identifier of*. | Not needed — the article assigns the object no identifier (§5.1). I confirmed `has_preferred_identifier` validates, in case it were. |
| `changed_ownership_by` (×25) | Not a label. P24's inverse is *changed ownership through*. | Not needed — no acquisition is recorded (§5.5). `changed_ownership_through` validates. |
| `took_place_at` nested inside `transferred_title_to` (×25, all 25 `illegal`) | P7 applied to an **E39 Actor**. P7's domain is E4 Period. The acquisition took place in Virginia; the actor did not. | Followed the standard: in my file every spatial property hangs off an event or a physical thing, never off an actor. |
| `<in_class>E:55 Type</in_class>`, `E:55 Type Type` (×50) | Malformed identifier — the colon is inside the id. Also `E42: Object identifier` alongside `E42: Object Identifier`. | Consistent, well-formed ids throughout. |

And in amol:

| In amol | Problem | What I did |
|---|---|---|
| `<in_class>E22: Man-Made Object</in_class>` (×30) | The class is right, the label is the CRM 3.x/5.x one. `ontology --model CRMbase` and `concept E22` both give **E22 Human-Made Object**. | Wrote the current label. Note that the validator never sees this: it reads the id before the colon and ignores the text after it, so both this and clayton's `E:55` pass silently. |
| `<value>` and `<unit>` | Not CRM property labels either. | **Kept them.** The validator classifies them as *structural elements skipped*, alongside `CRM_Entity` and `in_class` — i.e. the tool treats them as part of this XML dialect rather than as errors, and both published examples use them. They stand for P90 has value → E60 Number and P91 has unit → E58 Measurement Unit. I verified that the explicit `has_value` / `has_unit` forms also validate, so a stricter file could use them; the brief asks me to prefer the examples' conventions where they are not actually wrong, and a name the validator declares structural is not a wrong property name. **This is the one place where my file contains element names that are not CRM property labels, and it is deliberate.** |

A general point about both: they are CRM 3.x-era documents. `at_most_within`
and `Man-Made Object` are not sloppiness, they are a 20-year-old version of
the standard. Copying their vocabulary wholesale would have produced a file
that validates the way clayton does.

---

## 3. The choices that were actually hard

**Is a 64-bell set one object or 64?** Settled by the scope note, not by
taste. `concept E19`: "The class also includes **all aggregates of objects
made for functional purposes of whatever kind, independent of physical
coherence, such as a set of chessmen**." A chime-bell set played as one
instrument is precisely that. So the instrument is one `E22 Human-Made
Object`, and the counts go on P57 has number of parts — whose own worked
example in `concept P57` is "Chess set 233 (E22) has number of parts 33
(E60)", and whose scope note says it is "a method of checking inventory
counts with regard to aggregate or collective objects". Nothing had to be
forced.

**Which of the structure to decompose and which to leave in prose.** P46's
scope note draws the line: "This property is intended to describe specific
components that are **individually documented** … Overall descriptions of the
structure of an instance of E18 Physical Thing are captured by the P3 has
note property." The article individually counts the three levels (19 / 33 /
12), so each level is a sub-aggregate with its own P57. It never counts the
eight groups separately, so the eight groups stay in a `Description` note.
The largest and smallest bells are individually documented — with dimensions
— so they are P46 parts of the bell set; the article does not say which level
either hangs at, and P46 is transitive, so attaching them to the set rather
than to a level asserts exactly what is known and no more.

**Racks: part, or support?** Both, and they say different things. The racks
are P46 parts of the instrument; the rack assembly P198 holds or supports the
bell set. `concept P198` is explicit that the two are not redundant: "It is
**not** a sub-property of P46 is composed of, as the held or supported object
is not a component of the container or support."

**"Unearthed in 1978" — the one place I left CRMbase.** CRMbase has no
property for *finding*. The nearest, P12 occurred in the presence of, says
only that the object was there, which is true of everything in the tomb and
is not what the sentence means. CRMsci `S19 Encounter Event` is the
standard's own construct for this, and its scope note is written for exactly
this case: "In Archaeology, there is a particular interest if an object is
found 'in situ' … The surrounding matter with the relative position of the
object in it, as well as the absolute position and time of the observation
may be recorded to enable inferences about the history of the object." So the
1978 event is an S19, with O19i `was_object_encountered_through` from each
found object and O21 `encountered_at` for the findspot.

I considered CRMarchaeo `A9 Archaeological Excavation` (with AP3 investigated
→ E27 Site) and rejected it. A9 commits to an excavation *project* with
stratigraphic units and an investigating body; the article gives one word,
"unearthed", and names nobody. What the article records is the *finding*, and
that is S19. The excavation character is carried by P2 has type
"archaeological excavation" on the S19 instead, which asserts the kind of
event without asserting machinery the source does not support. This is the
one deviation in vocabulary from the two examples, which are CRMbase-only;
the alternative was to say nothing about how the object came to light.

**Tomb: E53 Place or E27 Site?** Both, joined by P156 occupies. `concept
E27`: a Site is a "constellation of matter on the surface of the Earth", in
contrast to "the purely geometric notion of E53 Place". The excavation
happened *within the tomb as a physical thing* → P8 took place on or within →
E27. The object's former location and the findspot are *places* → P53 and O21
→ E53. P156 (`concept P156`: domain E18, range E53) ties the two together
without conflating them.

**The museum.** My first instinct was E40 Legal Body. `concept E40` returned
"no definition in v7.1.3 (deprecated vocabulary)" and the migration table
entry "E40 Legal Body | use E74 Group". So `E74: Group`. "On permanent
display" became P54 has current permanent location (the premises, as an E53
inside Wuhan) plus P50 has current keeper (the E74). Not P52 has current
owner: display is not ownership and the article never says who owns the
bells.

**"Suizhou (then 'Sui County')".** Modelled as two E41 Appellations joined by
P139 has alternative form, typed *current name* / *former name*, with a note
saying "Sui County" is the name in use at the time of the excavation. The CRM
has no way to time-bound an appellation on the E41 itself; doing it properly
needs an E15 Identifier Assignment with its own P4 time-span, and the article
describes no naming event. A typed alternative form plus a note is as far as
the source reaches.

**Bronze.** The prose never states the bells' material. The article
classifies the object under "Zhou dynasty bronzeware". I recorded P45
consists of bronze on the bell set **with an attached `Source Note` saying
where it comes from**, rather than either asserting it as if it were in the
text or dropping a fact the article does carry. The honest alternative —
omit it entirely — would have lost information the page genuinely supplies.
Flagged here so a reviewer can strike it if they read the scope more
narrowly.

---

## 4. `validate --xml` output

```
$ uv run python search.py validate --xml crm_marquis_yi.xml
148 links checked: 120 ok, 28 ok_literal
structural elements skipped: CRM_Entity in_class unit value

Every link resolves to a real property and stays inside its declared domain and range.
```

**Every finding accounted for:**

- **0 `illegal`, 0 `unknown_name`.** Nothing to fix.
- **148 links checked** equals the total number of non-structural property
  elements in the file (I counted them independently: 148). Nothing was
  silently skipped.
- **28 `ok_literal`** = 23 `has_note` (P3 → E62 String) + 5
  `has_symbolic_content` (P190 → E62). Both are literal-ranged by definition;
  `ok_literal` is the expected verdict, not a warning.
- **`structural elements skipped: CRM_Entity in_class unit value`.**
  `CRM_Entity` and `in_class` are the dialect's frame. `unit` and `value` are
  the amol dimension convention, discussed in §2 — the only non-CRM property
  names in my file, kept deliberately, standing for P91 and P90.

Distinct identifiers used — **14 classes**: E12, E22, E27, E31, E41, E52,
E53, E54, E55, E57, E60, E61, E74, S19 (CRMsci). **25 properties**: P1, P2,
P3, P4, P8, P43, P45, P46, P50, P53, P54, P57, P67i, P70i, P82, P89, P101,
P103, P108i, P139, P156, P190, P198, O19i, O21. Every one was checked with
`concept`, the `ontology` listing, or a `validate <s> <p> <o>` triple before
use; none from recall.

---

## 5. The scope list, item by item — including what is absent

### 5.1 The object itself — *partly modelled*
Modelled: five appellations (English name, English alternative, Chinese
simplified, Chinese traditional, Pinyin) with P190 symbolic content; P2 has
type *bianzhong*; P101 had as general use *musical instrument*; the
composition (64 bells → three levels of 19 / 33 / 12, largest and smallest
bell; two racks); P57 counts at four levels; P45 wood on the racks and bronze
on the bells (caveated); dimensions of both racks and of the largest and
smallest bells.

**Absent, modelled as nothing:**
- **No identifier.** No accession number, inventory number or catalogue code.
  Both examples' objects are built around one; this one has none, so there is
  no E42 Identifier anywhere in the file — only E41 Appellations.
- **No condition statement of any kind.** No E3 Condition State, no P44. The
  article says nothing about completeness, damage, corrosion or stability.
- **No overall dimensions.** Only the two racks and the two extreme bells are
  measured; the instrument as a whole is not.
- **Material of the bells is not in the prose** — see §3.

### 5.2 Its making — *modelled, thinly*
An E12 Production with a P4 time-span of 433 BC and a P82 `at_some_time_within`
of "433 BC" (`concept E61` gives "85th century BCE" as a sample value, so a
literal BC string is the intended form; I did not silently convert it to a
proleptic ISO year).

**Absent:** no producer (no P14), no place of production (no P7), no
technique (no P32 / P33). **And nothing is contested.** The article gives one
flat date with no hedging, no alternative dating and no disputed attribution.
The scope item's "contested attribution or dating" clause is empty for this
object — there is no uncertainty in the source to model, and manufacturing
one would be inventing a scholarly disagreement.

### 5.3 What it depicts or is decorated with — *nothing modelled*
The article describes **no** decoration, no ornament, no motif, no
iconography and **no inscription**. There is no P62 depicts, no P65 shows
visual item, no P128 carries, no E34 Inscription and no E36 Visual Item in
the file. (This is the slot where invention would be easiest and most
tempting for this particular object. The article does not go there, so
neither does the model.)

### 5.4 Deposition and rediscovery — *rediscovery modelled, deposition not*
- **Deposition: absent.** The article records no burial, no interment event,
  no date of deposition, no depositor and no rite. What it states is that the
  object was unearthed *in* the tomb. That supports P53 has former or current
  location → the tomb's place, and it supports the encounter; it does not
  support an E9 Move, an E7 Activity or any burial event, and none is
  asserted.
- **Rediscovery: modelled.** S19 Encounter Event, 1978, typed *archaeological
  excavation*, O19i from both found objects. **Absent within it:** no
  excavator, no excavating institution, no P14 carried out by, no month or
  day.
- **Findspot: modelled in full** — the tomb (E27 Site, P156 occupying its
  place) inside Leigudun Community → Nanjiao Subdistrict → Zengdu District →
  Suizhou (formerly Sui County) → Hubei Province → China.

### 5.5 Ownership and custody — *one present state; no events*
The article records exactly one custody fact: "The original bells are on
permanent display at the Hubei Provincial Museum in Wuhan." Modelled as P54 +
P50 as above.

**Absent:** **no transfer of any kind.** No acquisition, no accession, no
sale, no gift, no loan, no deposit event, no change of keeper, no statement
of who owns the object, and no determination of any sort. There is no E8
Acquisition and no E10 Transfer of Custody in the file. (clayton's central
construct — `changed_ownership_by` → E8 with a `transferred_title_to` — has
no counterpart here. The object goes from a tomb to a display case with
nothing in between recorded.)

### 5.6 Reconstruction, restoration or alteration — *nothing modelled*
The article records **none** — none current, none superseded, none reversed,
no conservation, no re-hanging, no repair. There is no E11 Modification, no
E79 Part Addition and no E80 Part Removal in the file. The bells being
"hung on" racks in the museum might in fact reflect a modern re-erection, but
the article does not say so and I did not assume it.

### 5.7 Sources cited for contested points — *vacuous; sources modelled anyway*
**No point in the article is presented as contested**, so this item has no
content in the strict sense. The article's apparatus is modelled regardless,
with the distinction preserved by type:
- One inline citation: the Hubei Provincial Museum website, accessed
  2019-08-26, link dead, archived 2019-03-08 — attached to the display
  statement, typed *Cited source*.
- Three *Further reading* items (Lee & Shen 1999; Shen 1987; von Falkenhausen
  1993), each typed *Further reading* and noted as "not cited in support of
  any statement".
- The article itself and its photograph, via `is_documented_in`.

### Deliberately out of scope
- "Copies have been made for other museums" — replicas, excluded by the
  brief.
- The *See also* link and category "Chinese cultural relics forbidden to be
  exhibited abroad". This is a live legal restriction and the CRM models it
  well (E30 Right, P104 is subject to). It is not one of the seven items —
  it is not ownership, custody, transfer or deposit — and it comes from a
  category and a see-also link rather than from the prose. Left out; noted
  here so the omission is visible rather than silent.

Warrant for leaving the empty slots empty rather than hedging them into the
model: CRM Conceptual Modelling Principles 6.1, *"The absence of a property
in the knowledge base is not its negation in reality"* (verified with
`search.py quote crmprinciples#s0052`). Modelling nothing is the correct
representation of knowing nothing; it does not assert that nothing happened.

---

## 6. Where the CRM does not cover this object well

- **Musical behaviour.** "Each bell can play two tones with three degrees'
  interval between them"; "tonal range … from C2 to D7"; "all twelve half
  tones". None of this is an E54 Dimension: P90 has value ranges over E60
  Number and P91 has unit over E58 Measurement Unit, and a pitch range is
  neither a number nor a number with a unit. There is no CRM vocabulary for
  pitch, interval, tuning or the sounding behaviour of an instrument, and
  E100 Audio Item is about recorded audio, not about what an object can
  sound. All of it went into a typed `Sound` note. For an object whose entire
  significance is acoustic, this is the model's largest silence — and it is
  the CRM's, not the article's.
- **Relative spatial arrangement.** "The two racks are perpendicular to each
  other." No CRM property relates two physical things by orientation. P46's
  scope note explicitly routes overall structural description to P3 has note,
  which is where it went, but the geometry is then only readable by a human.
- **Language and script of an appellation.** P72 has language has domain E33
  Linguistic Object; E41 Appellation is under E90 Symbolic Object, not E33,
  so the simplified/traditional/Pinyin distinction could not be P72 and had
  to become P2 has type. Workable, but it turns a structural fact into a
  free-vocabulary label.
- **"Used with" between two objects.** The hammers are associated with the
  bells by use, not by composition. P103 was intended for → E55 carries it
  as a *type* of use; the direct object-to-object relation would need P19 was
  intended use of, which requires a specific E7 Activity the article never
  describes. So the link between the hammers and the bells they struck lives
  in an E55 type string and a note.
- **Provenance of a statement.** I wanted to mark "bronze" as coming from the
  article's classification rather than its prose. In full CRM that is an E13
  Attribute Assignment with its own carrier and source — real machinery, and
  disproportionate for one adjective in a 400-word article. The dialect of
  these two examples has no slot for statement-level provenance at all, so it
  became a typed note. A larger model of a contested object would need E13
  properly.

---

## 7. Notes on the search tool itself

What worked:
- `ontology --model CRMbase` in one call gave every id, its label and both
  directions. That is what made it safe to write underscored element names
  without guessing.
- `concept E19` answered the central question of this object (is a 64-bell
  set one thing?) in its scope note, and `concept P57`'s chess-set example
  confirmed it from the property side. `concept E40` caught a deprecation I
  would otherwise have shipped as an error.
- `validate --xml` is the right shape of check: it caught clayton's four
  distinct defects immediately and confirmed my file in one pass.

Friction, recorded as the brief asks:
- **`validate <s> <p> <o>` will not accept the underscored label form.**
  `validate E22 has_number_of_parts E60` fails with a usage error; `validate
  E22 "has number of parts" E60` works. The XML dialect — the one the
  examples are written in and the one `validate --xml` parses — uses the
  underscored form throughout, so the two halves of the same tool disagree on
  how a property may be named. One round trip each time.
- **`validate --xml` reports every occurrence, not every distinct defect.**
  clayton's three bad names produced 91 near-identical blocks. Fine at 148
  links; unreadable at 6,500.
- **The text after the colon in `<in_class>` is never checked.** `E22:
  Man-Made Object` (a label retired two major versions ago) and clayton's
  malformed `E:55 Type` both pass silently. Since the dialect writes the
  label there by convention, checking it against the current label would have
  caught the most visible error in each example — and would tell an author
  their vocabulary is stale, which the id alone never will.
- `validate` disambiguates homonymous labels correctly and helpfully — `E22
  "consists of" E57` walks P5, P9 and P45 and answers "Use P45". Worth
  recording because I expected it to fail and it did not.
