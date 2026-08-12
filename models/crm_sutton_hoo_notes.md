# Notes on `crm_sutton_hoo.xml`

A CIDOC CRM encoding of the Sutton Hoo helmet, from the English Wikipedia
article of that name, in the XML form of the two published CIDOC CRM examples
`crm_amol_1.xml` and `crm_clayton1.xml`.

Everything about the CRM below was obtained through `search.py`. No source
document under the repository was opened.

**Scale.** 456 links; 30 distinct classes and 60 distinct properties.
28 classes are CRMbase; `S18 Alteration` and `S19 Encounter Event` are CRMsci
and `A9 Archaeological Excavation` is CRMarchaeo. All 60 properties are
CRMbase — see "The one place the tool constrained the model" below for why.

---

## 1. Conventions taken from the examples

Both examples share a single, unstated grammar, and I followed it:

- Root `<CRMset>`; one `<CRM_Entity>` per documented thing.
- The **text content** of an element is the label of the instance; a child
  `<in_class>` names its class as `Enn: Label`.
- **Element names are CRM property labels** with spaces replaced by
  underscores and no P-number: `is_identified_by`, `has_dimension`,
  `took_place_at`, `carried_out_by`.
- **Direction is chosen to suit the nesting.** Both examples freely use
  inverse labels (`is_identified_by` = P1i, `is_documented_in` = P70i) so that
  the object under description stays the outermost element. I did the same:
  `was_produced_by` (P108i), `changed_ownership_through` (P24i),
  `was_attributed_by` (P140i), `moved_by` (P25i).
- **An element with no `<in_class>` child is a literal.** Amol uses this for
  `has_note`; I use it for notes, for `has_value`, and for the E61 Time
  Primitives under `at_some_time_within` / `ongoing_throughout`.
- **Co-reference is by identical label.** Neither example has IDs or IDREFs;
  Clayton simply repeats the actor "Clayton" in all 25 records. So
  "Sutton Hoo, Suffolk", "British Museum", "iron", "Rupert Bruce-Mitford" and
  the like recur verbatim wherever they are needed, and identity of label is
  identity of instance. This is the format's weakest point (§5).
- **`has_note` with a nested `has_type`** to say what kind of note it is —
  Amol's idiom (`Statement`, `Description`, `Marks`). I use `Description`,
  `Criticism` and `Cataloguer note`.

### Where the two examples differ, and what I picked

| Point | Amol | Clayton | Chosen | Why |
|---|---|---|---|---|
| Citing a source | `is_documented_in` → E31 Document (an image filename) | `is_referred_to_by` → E32 Authority Document + `has_note` with volume/page | **both, split by role** | Clayton's idiom carries the page reference, which is what a contested point needs, so scholarly citations attached to an assertion use `is_referred_to_by` (P67i) with a page note. The general bibliography of works documenting the object uses Amol's `is_documented_in` (P70i), which is what P70 "documents" actually means. |
| Preferred identifier | not distinguished from other identifiers | `preferred_identifier_is` alongside `is_identified_by` | **Clayton's distinction, Amol's discipline** | The distinction is real and worth keeping (P48 exists); Clayton's *name* for it is wrong. See §2. |
| Sub-typing an E55 | `E55: Object Type`, `E55: Dimension Type` in `<in_class>` | both that (`E55: Clayton Barcode Type`) **and** a nested `has_type` naming the type-of-type | **the nested `has_type`** | `<in_class>` should name a class. "Object Type" and "Clayton Barcode Type" are not classes. Clayton's other idiom — an E55 instance carrying `has_type` → another E55 — is plain P2 and says the same thing correctly. |
| Encoding | ISO-8859-1 | ISO-8859-1 | **UTF-8** | The subject has "Rædwald" and "Valsgärde" in it. In the event I transliterated both and the file is pure ASCII, but UTF-8 is the safer declaration and costs nothing. |

---

## 2. Where an example is wrong, and what I did instead

I ran `validate --xml` on both examples first. **`crm_amol_1.xml` is clean**
(637 links, 426 ok, 211 ok_literal). **`crm_clayton1.xml` is not**:

```
656 links checked: 25 illegal, 420 ok, 120 ok_literal, 91 unknown_name
```

Four distinct defects, each repeated across its 25 records:

1. **`preferred_identifier_is`** — not a CRM label. The property is
   **P48 has preferred identifier**; `validate E1 P48 E42` confirms
   `E1 -> E42`. I use `has_preferred_identifier`.

2. **`changed_ownership_by`** — not a CRM label. The inverse of
   **P24 transferred title of** is labelled *"changed ownership **through**"*.
   I use `changed_ownership_through`. (This one is a near-miss that reads
   perfectly naturally, which is exactly why it survived publication.)

3. **`at_most_within`** — not a CRM label, and the construct beneath it is
   also flattened. Clayton hangs it straight off the E8 Acquisition to an E52
   Time-Span. The CRM path is **P4 has time-span** → E52 Time-Span →
   **P82 at some time within** → E61 Time Primitive; P82 is what "at most
   within" is reaching for ("the maximum period of time within which an E52
   Time-Span falls"). I use `has_time-span` / `at_some_time_within`, with
   `ongoing_throughout` (P81, the minimum period) where the article supports
   an inner bound.

4. **`took_place_at` nested under `transferred_title_to`** — 25 ILLEGAL
   findings, `E39 is not a E4`. Clayton wants to say the collection happened
   in Virginia, but attaches P7 to the Actor instead of to the Acquisition.
   In this document every `took_place_at` hangs off an event.

**A fifth thing, which the checker does not catch.** Amol's `<value>` and
`<unit>` are not CRM property labels either — the properties are **P90 has
value** and **P91 has unit**. They pass only because the checker lists `value`
and `unit` among its skipped structural elements, i.e. the tool was taught to
tolerate them. Amol's clean summary line is therefore partly an accommodation
rather than a property of Amol. I use `has_value` and `has_unit`, with
`<in_class>E58: Measurement Unit</in_class>` on the unit.

**Sixth:** Amol writes `E22: Man-Made Object`, the pre-7.x label; Clayton has
`E:55 Type` with the colon misplaced, and writes `E42: Object identifier`
and `E42: Object Identifier` in the same record. The checker reads only the
number, so none of this is flagged. I used the current v7.1.3/7.3.2 labels
exactly as `concept` returns them (`E22 Human-Made Object`).

---

## 3. The modelling choices that were genuinely difficult

### 3.1 Is the object in Room 41 still the same object? (E11 vs E81)

The helmet was reduced to >500 fragments in the ground, built into a plaster
head by Maryon in 1945–46, cut apart with a saw in 1970, and rebuilt on jute
and resin in 1971. Two scope notes pull in opposite directions, and I checked
both by quote:

- **E80 Part Removal**: *"If the instance of E80 Part Removal results in the
  total decomposition of the original object into pieces, such that the whole
  ceases to exist, the activity should instead be modelled as an instance of
  E81 Transformation"* (verified, `quote crm732#E80`).
- **E24 Physical Human-Made Thing**: *"interventions of conservation and
  repair are not regarded to produce a new Human-Made thing"* (verified,
  `quote crm732#E24`).

**Decided for E11 and its subclasses, not E81.** What E80 removed in 1970 was
the *1945–46 fill* — the plaster, the wire mesh, the Plasticine — modelled as
a part added in 1945 and removed in 1970. The ancient fragments were separated
but never ceased to be the helmet: they were never reregistered, and
1939,1010.93 is continuous across all of it. E81 would additionally require
the product to have "fundamentally different nature or identity", which is the
opposite of what a conservator is trying to achieve. The reasoning is recorded
as a `Cataloguer note` inside the file so that a reader who disagrees can see
where the seam is.

Consequently: 1945–46 is **E11 Modification**, the 1970 dismantling is
**E80 Part Removal** (P113 removed → the 1945–46 fill), the 1970–71 rebuild is
**E79 Part Addition** (P111 added → the 1970–71 fill), and the two are joined
by **P134 continued**, whose own example is the Cologne Cathedral construction
resumed in the 19th century — a good match for a second attempt at the same
intention.

### 3.2 Four reconstructions, one object: E3 Condition State

Scope item 6 asks for *every* reconstruction "including any later reversed or
superseded", which is a request to model states over time, not just events.
`concept E3` supplied the pattern directly: its own examples are *"the
'reconstructed' state of the Amber Room in Tsarskoje Selo from summer 2003
until now"* and *"the 'ruined' state of Peterhof Palace near Saint Petersburg
from 1944 to 1946"*. So the helmet carries four instances of E3 Condition
State via P44, each `has_type`d and each with its own time-span: shattered
(to 1945), first reconstruction (1946–1968), dismantled (1970), current
reconstruction (1971–). The superseded state is therefore *in* the model as a
state, not merely as a discarded opinion.

### 3.3 Contested dates: one Time-Span, several Time Primitives

`concept E61` states the rule outright and I verified it: *"Only one E52
Time-Span should be instantiated since there is only one real phenomenal time
extent"* — multiple opinions go on as multiple instances of E61 Time Primitive
against that one span (`quote crm732#E61`, FOUND).

So the burial has **one** E52 Time-Span carrying `ongoing_throughout`
`0620/0625` (the commonly given estimate) and `at_some_time_within`
`0613/0650` (the numismatic terminus post quem widened by Wilson's "any other
great man of East Anglia from 610 to 650"), plus `beginning_is_qualified_by`
"circa" (P79).

The **withdrawn** 650–660 dating is deliberately *not* a third time primitive
on that span. It was retracted, not held alongside the current one, so putting
it on the same span would assert that the burial is within 650–660, which
nobody now claims. It is instead an **E13 Attribute Assignment** with its own
date ("before 1960") and its own source, sitting beside the E13 for the
specific-gravity redating. That is the distinction the CRM draws between
approximating one extent and recording somebody's opinion.

### 3.4 Contested everything else: E13 Attribute Assignment

`concept E13` is explicit that this is the mechanism: *"the use of instances of
E13 Attribute Assignment marks the fact that the maintaining team is in general
neutral to the validity of the respective assertion, but registers someone
else's opinion and how it came about. Multiple use of instances of E13
Attribute Assignment may possibly lead to a collection of contradictory
values."* Thirteen of them are in the file, deliberately in contradictory
pairs where the article gives a pair:

| Assertion | Rival |
|---|---|
| burial is Rædwald's (Keynes, Campbell) | no secure attribution possible (Wilson, Carver, Campbell 2014) |
| coins date the burial 650–660 (pre-1960) | coins date it 613–635 (Oddy & Hughes 1972) |
| sinister eyebrow is a deliberate Odin allusion (Price & Mortimer 2014) | it is the trace of a repair (Marzinzik 2007) |
| niello is present (Maryon 1947) | it is an uncorroded metallic inlay, not niello (Oddy 1980) |
| 23 / 25 garnets (Bruce-Mitford 1978 p. 169) | 21 / 22 (technical report, same volume pp. 229–230) |
| neck guard shows 7 vertical strips | 5 is equally possible (Bruce-Mitford 1982) |
| cap beaten from a single piece | not conclusively provable (Hood et al. 2012) |
| Design 3 replaced a damaged panel | contradicted by the placement of fragment (c) |

P177 `assigned_property_of_type` names the CRM property being asserted —
following the CRM's own example for P177, which uses *"P52 has current owner"*
as the E55 value. This is what makes an E13 machine-usable rather than a
typed note: `P51 has former or current owner`, `P4 has time-span`,
`P45 consists of`, `P57 has number of parts`, `P62 depicts`,
`P31i was modified by`, `P32 used general technique`, `P108i was produced by`.

An E13 that *declines* to assign (Wilson's) carries P177 and P14 but no P141.
That is legal — P141 is 0,n — and reads correctly: an assessment was made, and
its outcome was that no value can be given.

### 3.5 Depiction: the long path, not the shortcut

`concept E36` states that P62 depicts *"can be regarded as a shortcut of the
more fully developed path from E24 through P65 shows visual item, E36 Visual
Item, P138 represents, to E1"*. Since the article treats the five designs as
objects of study in their own right — countable, die-identified, individually
placed and re-placed across two reconstructions — they must be first-class
E36 Visual Items, so the long path is used for all five plus the composite
winged-dragon motif. P62 is kept for exactly one thing the article states
directly of the object and not of a design: that the face mask presents the
image of a man.

Design 3 gets a Visual Item with **no `represents`**. Seven fragments, no
recoverable subject. Leaving the property off is the honest encoding.

### 3.6 The production date, and not inventing one

The article gives **no** date, place or maker for the manufacture. It gives two
things only: that the helmet was "likely around 100 years old when buried", and
(implicitly) that it precedes the burial. So:

- The production's Time-Span carries `at_some_time_within 0450/0625` and an
  attached note saying in the file that this bound is the cataloguer's and is
  derived from those two statements.
- The relation to the burial is stated properly rather than by arithmetic:
  **P183 ends before the start of** from the Production to the deposition
  E9 Move. This is a real temporal primitive (`concept P183`: "A end < B start
  is true"), it is what the article actually asserts, and it needs no dates.
- The "100 years" estimate itself is an E13 carried out by Bruce-Mitford with
  its two page references, not a fact about the object.

### 3.7 Findspot, where the record is a hole

The article is unusually clear that the findspot was *not* recorded: no in-situ
photographs, no relative positions, only a circle on the excavation diagram
labelled "nucleus of helmet remains". I considered CRMarchaeo's `A7 Embedding`
with AP18/AP19 into an `A2 Stratigraphic Volume Unit`, which is the precise
construct, and rejected it: building a stratigraphic record for an object whose
stratigraphic record is the article's stated absence would be modelling the
apparatus and not the evidence. Instead: **P53 has former or current location**
to the burial chamber, with Phillips's "four feet east of the shield boss on
the north side of the central deposit" and the statement of what was not
recorded, both as notes on the place.

### 3.8 The 1966 Ordnance Survey drawing is not a modification

It is called a "reconstruction" in the article and it is listed under a section
about the first reconstruction, so it is a scope-item-6 candidate. But it never
touched the object: it is a drawing showing a larger cap, a straighter face
mask and rearranged panels. Modelled as an **E31 Document** with an
**E65 Creation** naming the British Museum, the Ordnance Survey's Archaeology
Division and Phillips, with a note saying why it is not an E11. Modelling a
proposal as an intervention would have made the object's history wrong.

### 3.9 Scope: what was deliberately left at the edge

Rædwald appears only as the value of a contested ownership assignment, not as a
described person; Sutton Hoo appears as a Place and (for the excavations) an
E27 Site; the ship-burial appears only as the destination of the deposition.
The British Museum is an **E74 Group** (an Actor), *not* an E78 Curated
Holding — `concept E78` warns that the class is the holding, not the actor
often named after it, and separately that collective objects "like a tomb full
of gifts" belong in E19, not E78. So neither the museum collection nor the
Sutton Hoo assemblage is modelled as an E78. Note that `E40 Legal Body`, which
would have been the natural class for the museum, returns
*"no definition in v7.1.3 (deprecated vocabulary)"* from `concept E40`; E74 is
the live class.

---

## 4. The `validate --xml` output

```
456 links checked: 295 ok, 161 ok_literal
structural elements skipped: CRM_Entity in_class unit value

Every link resolves to a real property and stays inside its declared domain and range.
```

**Zero `unknown_name`, zero `illegal`. Nothing stands unexplained.**

The first run had one finding, now fixed:

```
UNKNOWN_NAME   was_moved_by
    E22 -> E9   at CRM_Entity[E22]/was_moved_by
    'was_moved_by' is not a CRM property label
```

I had written the inverse of P25 from memory as "was moved by". It is not:
`validate E19 P25i E9` returns `LEGAL P25i moved by`. The label is bare
**"moved by"**, without the "was". Renamed to `moved_by`. This is precisely the
class of error the file check exists to catch — it would have survived a
transcription of my own triples, because I would have transcribed the
identifier P25i and not the string I actually wrote.

Two things the summary line does not tell you and which I checked separately:

- `structural elements skipped: ... unit value` — this document contains no
  `unit` or `value` elements, so nothing of mine was skipped on that account.
  All 456 links were really checked.
- The three non-CRMbase classes are genuinely checked, not waved through. A
  deliberately wrong probe confirms it:

  ```
  ILLEGAL  has_current_owner   E22 -> S19    S19 is not a E39
  ILLEGAL  consists_of         E22 -> A9     A9 is not a E57
  ```

  while `was_present_at` → S18 in the same probe came back `ok`. So the
  checker resolves CRMsci and CRMarchaeo class identifiers and range-checks
  them; the `ok` on my S18/S19/A9 links is a real result.

---

## 5. Findings about the tool and the format

### 5.1 The one place the tool constrained the model

`validate --xml` resolves element names **by property label**, and its label
index covers **CRMbase only**. Family-model properties are unreachable by
label even though the same tool knows them perfectly well by identifier:

```
$ search.py validate S19 O19 E18
  LEGAL  O19  encountered object (was object enc  S19 -> E18

$ search.py validate S19 "encountered at" E53
  ERROR: no property matches 'encountered at'
```

A probe file using `was_object_encountered_through` (O19i), `encountered_at`
(O21), `is_embedded` (AP18i) and `is_embedding_in` (AP19) returned four
`unknown_name` findings, all four properties being real and current.
`search.py connect E22 S19` lists O19 with its label, so the gap is in the XML
checker's index specifically, not in the knowledge base.

**Worked around in the open.** I kept the family *classes*, which the checker
does resolve and does test, and attached them with CRMbase properties that
are true generalisations of the family ones:

| wanted | used | why it is sound |
|---|---|---|
| S19 —O19→ E18 | E22 —P12i `was_present_at`→ S19 | S19 < S27 < I1 < E7 < E5, and `concept S19` lists P12 among its *required* properties |
| S19 —O21→ E53 | S19 —P7 `took_place_at`→ E53 | P7 is likewise listed as required on S19 |
| A9 —AP3→ E27 | A9 —P8 `took_place_on_or_within`→ E27 | E27 Site < E26 < E18, the range of P8 |
| A1 within A9 | S19 —P9i `forms_part_of`→ A9 | both are E4 Periods |

The cost is real but small: I lose the assertion that the 1939 event was an
*encounter with this object* as opposed to an event this object was present
at, and that the excavation *investigated* the site rather than merely
occurring on it. The class of each event still carries most of that meaning.
If the checker's label index were widened to the family models, four elements
in this file would become more precise with no other change.

### 5.2 `concept` and `docs` are not the same snapshot

`concept E22` etc. return v7.1.3 and say so; `docs` and `quote` are keyed to
the v7.3.2 reference document. Mostly harmless, but the E78 sentence about
"a tomb full of gifts" that `concept E78` shows is not retrievable through
`quote crm732#E78`, whose indexed chunk for E78 holds the examples rather than
the full scope note. A phrase legitimately read out of `concept` can therefore
fail `quote`, which is disconcerting when you are trying to be careful. I have
cited that one as a v7.1.3 scope note rather than as a v7.3.2 quotation.

In fairness, `quote` earned its keep on a different check. My first attempt at
the E24 sentence returned `NOT FOUND` with `closest match (90% of the phrase,
contiguous)`, revealing that the real wording ends *"a new **Human-Made
thing**"* and not *"a new instance of E24 Physical Human-Made Thing"* as I had
paraphrased it. §3.1 quotes what the tool returned, not what I remembered.

### 5.3 The published format has no identity mechanism

There is no way in this XML to say that the "British Museum" under
`transferred_title_to` and the "British Museum" under `has_current_owner` are
one Actor, other than by spelling them identically — which is what Clayton
does 25 times over. Nor is there any way to point from one `CRM_Entity` to
another. Every non-tree relation must be re-expressed by repeating a label,
and a typo silently forks an entity into two. This document is one tree with
disciplined label reuse, but the discipline is unenforceable, and the checker
cannot see it: co-reference errors are invisible to `validate --xml`.

Related: the format cannot express **properties of properties**. Amol's
`has_note` → `has_type` idiom means P3.1 has type, but as written the checker
reads it as P2 on the note string (both are legal, so it passes). Same for
P14.1 in the role of and P62.1 mode of depiction, which I therefore did not
attempt.

---

## 6. Where the CRM does not cover the subject well

1. **Non-intentional damage.** The burial chamber collapsed and shattered the
   helmet. CRMbase has nothing between `E5 Event` (says nothing) and
   `E6 Destruction` (wrong: the object survived) or `E11 Modification` (wrong:
   modification is *undertaken*, by an Actor, per E7). CRMsci's
   **S18 Alteration** is exactly right — *"natural events or man-made processes
   that create, alter or change physical things, by affecting permanently their
   form or consistency without changing their identity"* — and is in fact the
   superclass of E11. I used S18, attached with P12i. That CRMbase alone cannot
   say "this object was broken by something that was nobody's doing" is a real
   gap for archaeological material.

2. **"May have been."** Two of the alterations in scope item 6 may never have
   happened: the ancient repair of a Design 2 panel, and the possible repair of
   the sinister eyebrow. The CRM has no way to instantiate an event whose
   occurrence is in doubt — instantiating it asserts it. I instantiated the
   first as an E11 (the article treats the damage at the back of the helmet as
   real, only its repair as inferred) with the doubt in a note and in a paired
   set of E13s, and modelled the second *only* as two rival E13s with no E11 at
   all. CRMinf's I2 Belief over an I4 Proposition Set is the designed answer,
   but it is unreachable through this checker (§5.1) and neither example uses
   it. This is the weakest join in the document and I would flag it for review.

3. **Estimated versus measured dimensions.** The 2.5 kg weight is an estimate
   of the *original* object, and cannot be got by weighing what is in Room 41,
   which is half absent and half plaster. `concept E54` says the method of
   determination should go on P2 has type and that "the identity of an instance
   of E54 Dimension depends on the method of its determination" — so the type
   ought to be a determination method, not "weight". Since the article names no
   method, I typed it "weight" and put the estimate's status in a note. A
   full E16 Measurement would be fabrication.

4. **"Less than half the original surface area."** P90 has value ranges over
   E60 Number. A one-sided inequality is not a number. `concept E60` does allow
   "intervals of these values to express limited precision", so an interval
   would be in scope, but the article gives a bound and not an interval. I
   recorded the string `less than 0.5` as the value, which is honest and
   type-loose; the alternative was to invent an interval.

5. **Quantities of a repeated design.** "Design 2 appeared twelve times on the
   helmet" is a statement about how many impressions of one Visual Item the
   object carries. P57 has number of parts is about parts of an E19, not about
   occurrences of a visual item, so it does not fit; there is no P-of-P on P65.
   These counts are in notes on the Visual Items. Someone should raise it —
   repeated ornament from a single die is not a rare situation.

---

## 7. Worth a reviewer's eye

- **§3.1**, the E11-versus-E81 call on the dismantling. Two scope notes
  genuinely conflict and I chose one. If a reviewer takes E80's "the whole
  ceases to exist" literally, the 1970 dismantling becomes an E81
  Transformation and the object in Room 41 is a different object from the one
  Pretty gave away — which I think is wrong, but it is arguable.
- **§6.2**, the possible-but-maybe-never-happened repairs. Two different
  treatments for two structurally identical cases, decided on how much of each
  the article treats as established. Defensible, not obviously right.
- **§5.1**, the family-model workaround. It is a deliberate loss of precision
  forced by the checker, not by the ontology, and it should be undone if the
  label index is widened.
