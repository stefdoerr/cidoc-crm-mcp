# Modelling the Bayeux Tapestry in CIDOC CRM — rationale

Object: the Bayeux Tapestry, from the English Wikipedia article of that name.
Model: `crm_bayeux.xml`, in the XML form of the two published CIDOC CRM
examples `crm_amol_1.xml` and `crm_clayton1.xml`.

Everything asserted here about the CRM came from `search.py` — `ontology`,
`concept`, `docs`, `issues`, `quote` and `validate`. No source document was
opened.

---

## 1. The format, as taken from the two examples

Both examples share one dialect, and I followed it:

- Root `<CRMset>`; each identifiable thing that needs a description of its own
  is a top-level `<CRM_Entity>` whose text content is the instance's name.
- `<in_class>Enn: Label</in_class>` declares the class of the instance whose
  element it sits inside.
- Every other element name is a **CRM property label with spaces replaced by
  underscores**; its text is the name of the object instance, followed by that
  instance's own `<in_class>` and any further nested properties.
- There is no identifier/reference mechanism. **Co-reference is by identical
  text.** "Clayton", "Virginia" and "Flora Virginica" recur verbatim across
  clayton's 25 entities and are meant as the same instances each time. I used
  the same device: "Bayeux Tapestry", "the Musee de la Tapisserie de Bayeux",
  "Lucien Musset, The Bayeux Tapestry, Boydell Press, 2005" and so on are
  written identically wherever they recur, and where a thing has properties of
  its own it also gets a top-level `<CRM_Entity>` (the visual narrative, the
  tituli, the backing cloth, the missing section, the 1941 fragments).
- Inverse directions are written as the inverse label: clayton has
  `<was_classified_by>` for P41i, and I use `<was_produced_by>`,
  `<changed_ownership_through>`, `<custody_transferred_through>`,
  `<was_modified_by>` and so on the same way.
- Literal-valued properties carry the value as text with no `<in_class>`
  (`<has_note>`), as clayton does.
- `<value>` and `<unit>` are structural shorthands inside `<has_dimension>`,
  from amol. The validator recognises them as structural and skips them, so
  they are part of this dialect rather than a mistake; I kept them rather than
  writing `has_value`/`has_unit` (P90/P91), which would also have validated.

### Where the two examples disagree, and what I picked

| Point | amol | clayton | What I did |
|---|---|---|---|
| Notes | `has_note` carries a nested `has_type` (P3.1) giving the note's kind — Statement, Description, Marks, Made Note | bare `has_note`, untyped | **amol.** The article yields several genuinely different kinds of note (a summary statement, a physical description, editorial notes about the article's own inconsistencies, absence notes), and P3.1 exists precisely to distinguish them. Untyped notes elsewhere, as clayton does, where the kind is obvious from position. |
| Dimensions | full `has_dimension`/`has_type`/`value`/`unit` blocks | none at all | **amol.** |
| Events | none — amol is a flat catalogue record | acquisitions, type assignments, actors, places | **clayton.** This object's history is almost entirely events. |
| Depth | shallow, two levels | deep, up to five | **clayton**, and deeper still: an attribute assignment nested in a production nested in the object, with its source document nested in it. |
| Class labels | role-qualified and stale: `E22: Man-Made Object`, `E55: Object Type`, `E55: Dimension Type` | role-qualified and malformed: `E55: Clayton Old Barcode Type`, `E:55 Type Type` | **Neither.** I used the exact current labels from `ontology --model CRMbase` (`E22: Human-Made Object`, `E55: Type`). `validate --xml` reports `LABEL_MISMATCH` on four distinct labels in amol and several in clayton; my file reports none. Where a type needs a role, the role is in the instance name or in a nested `has_type`, not smuggled into the class label. |
| Preferred identifier | not used | `<preferred_identifier_is>` on every object | Not used — see §2, and see the absence note in §6. |

## 2. Where the examples are wrong, and what I did instead

`validate --xml` on the two source files:

```
amol.xml    : 637 links checked: 426 ok, 211 ok_literal   (plus 4 LABEL_MISMATCH)
clayton.xml : 656 links checked: 25 illegal, 420 ok, 120 ok_literal, 91 unknown_name
```

Clayton is the example with the broken names. It has three, and one illegal
nesting, all repeated across its 25 near-identical entities:

1. **`preferred_identifier_is`** — not a CRM property label. The property is
   **P48 has preferred identifier**, so the element is `has_preferred_identifier`
   (verified with a probe file: it validates). I did not need it — see §6.
2. **`changed_ownership_by`** — not a label. P24's inverse is
   **"changed ownership through"**, so the element is
   `changed_ownership_through`. That is what my file uses, 3 times.
3. **`at_most_within`** — not a label, and doubly wrong. Clayton hangs it
   straight off an E8 Acquisition with an `E52: Time Span` as its object. The
   CRM route is **P4 has time-span: E52 Time-Span**, and then, inside the
   time-span, **P82 at some time within: E61 Time Primitive**. (`concept P82`
   gives `E52 -> E61`, not `E8 -> E52`.) So every date in my file is
   `<has_time-span>` → `E52: Time-Span` → `<at_some_time_within>` or
   `<ongoing_throughout>` → `E61: Time Primitive`.
4. **`took_place_at` nested under `transferred_title_to`** — 25 ILLEGAL
   findings, `E39 -> E53`, "E39 is not a E4". Clayton attaches the place of the
   acquisition to the *actor* who acquired title. P7 has domain E4 Period.
   In my file `took_place_at` always hangs off the event.

Clayton's `E52: Time Span` (no hyphen) and `E:55 Type Type` (colon misplaced)
are further label errors; the current labels are `Time-Span` and `Type`.

## 3. The modelling choices that were actually difficult

**Contested attribution — the spine of this object.** Almost nothing about the
making of the Bayeux Tapestry is agreed. The scope note of **E13 Attribute
Assignment** (`concept E13`) says exactly what to do: "the use of instances of
E13 Attribute Assignment marks the fact that the maintaining team is in general
neutral to the validity of the respective assertion, but registers someone
else's opinion and how it came about." The Conceptual Modelling Principles back
this up — principle **6.2 "Allow alternatives or contradictions in the data"**
(`docs --kind principles`), and 5.2 "Do not model conclusions before and
without their reasons".

So the E12 Production asserts **only** what the article does not contest: the
technique (embroidery; stem stitch; couching), the materials, and a wide
time-span (11th century, within a few years of 1066). Everything else — who
commissioned it (Odo / Matilda / Edith of Wessex), who designed it (Scolland /
Lanfranc), who stitched it, where (England / Saumur), when (the 1070s), for
whom (William / Odo's hall / the 1077 dedication) — is a numbered E13 hanging
off the production or off the design, each carrying `P177 assigned property of
type`, `P141 assigned`, `P14 carried out by` (the scholar), a date, and
`P70i is documented in` (the publication). There are 22 of them.

This also solves scope item 7 cleanly: the sources for contested points are not
a bibliography bolted on the side, they are the range of `is_documented_in` on
the assignment that each source supports.

**The design is not the object.** `concept E36` and `concept E12`: the physical
embroidering produces an E24, the conception of the narrative creates an E28.
Clarke and Grainge are arguing about "the individual responsible for its
overall narrative and political argument" — that is the creator of the E36
Visual Item, not a participant in the E12 Production. So the designer
attributions (4, 5, 15) sit on an **E65 Creation** attached to the visual item
by `was_created_by`, and the production carries a note saying where they went.

**P62 depicts vs the long path.** E36's scope note states outright that "P62
depicts ... can be regarded as a shortcut of the more fully developed path
from E24 ... through P65 shows visual item, E36 Visual Item, P138 represents".
I used the long path throughout and P62 nowhere, so that the depicted content
can carry its own structure — the three zones as `is_composed_of` (P106), the
scene count as alternative dimensions, the disputed identifications as E13s.

**Commissioning.** The CRM has no "commissioned by". `concept P14` says P14
"implies causal or legal responsibility", and the CRM's own example uses
P14.1 in the role of. A commissioner has causal responsibility, so the Odo,
Matilda and Edith attributions assign `P177` = "carried out by, in the role of
commissioner". Searching the mailing list and the issue register for
commissioner/patron modelling turned up nothing decisive.

**E79 Part Addition vs E11 Modification.** E79's scope note requires that
"Both the E18 Physical Thing being augmented and the E18 Physical Thing that is
being added are treated as separate identifiable wholes prior to the instance of
E79 Part Addition". The 1724 linen backing cloth was such a whole → **E79**.
The spurious final titulus "Et fuga verterunt Angli", added shortly before 1814,
was embroidered into the cloth and was never a separate whole → **E11
Modification**. The 1941 fragments were removed as identifiable pieces →
**E80 Part Removal**.

**The scene numerals: E37 Mark, not E34 Inscription.** E34 requires `P72 has
language: E56 Language` (`concept E34` lists it as necessary) and E34 is a
subclass of E33 Linguistic Object. Large ink numerals are not an expression in
natural language. E37 Mark — "symbols, signs, signatures, or short texts
applied to instances of E24 ... in order to ... communicate information
generally" — fits, and carries no language requirement. The tituli, which are
Medieval Latin, are E34 with `has_language`.

**The rediscovery of 1729: S19 Encounter Event, from CRMsci.** This is the only
place I stepped outside CRMbase, which is all either example uses. `concept S19`:
"This knowledge may be new to the group of people the actor belongs to. In that
case, we would talk about discovery." That is precisely the 1729 event — the
tapestry was never lost, it was hanging annually in the cathedral; what was new
was the scholarly community's knowledge of it. The archaeological reading of
S19 (an object *in situ* in surrounding matter) does not apply and I said so in
the file. The alternative was an untyped E7 Activity, which would have thrown
away the one class in the family that names this kind of event. Same class for
the 2023 discovery of the stolen fragments.

**The UNESCO register is not an E32.** My first instinct was `P71i is listed in:
E32 Authority Document`. `concept E32` rules it out: E32 is "encyclopaedia,
thesauri, authority lists and other documents that **define terminology or
conceptual systems**". A register of heritage items defines no terminology. So
the 2007 admission is an **E17 Type Assignment** carried out by UNESCO
assigning the type "globally important documentary heritage", with the register
itself as a plain E31 Document. (E32 does appear once, correctly: the OED, for
the definition of "tapestry".)

**The tapestry/embroidery dispute.** The object is typed `embroidery` directly,
because the article asserts that in its own voice; the conventional
classification as a "tapestry" is an E17 Type Assignment with the OED and Saul
attached, because the article marks it as convention rather than fact.

**Two contradictions inside the article itself,** recorded rather than
resolved: the length is "nearly 70 m" in the lead and 68.38 m in the
Construction section (two E54 Dimensions, the approximate one flagged as such);
and the Paris exhibition is dated 1803/Musee Napoleon in the History section but
1797/Louvre in the Later reputation section (both recorded, with an editorial
note on each).

**Three estimates of the missing length** — Musset ~1.5 m, Norton ~3 m, Hicks
"perhaps even another 6.4 m" — are three E54 Dimensions on the missing section,
each with its source. Likewise the scene count, 58 or 70, is two E54 Dimensions
on the visual item.

## 4. Where I drew the line on the depicted narrative

The depicted narrative is the bulk of the article and runs to dozens of scenes.
Modelling all 58 would have put one part of the record at a much finer grain
than everything else. The line I drew:

- **In:** the narrative as a whole (E36, with P138 to the Norman Conquest, the
  Battle of Hastings, Edward's death, Harold's coronation, Harold's oath,
  Harold's death, Halley's Comet, the Aelfgyva scene); all 19 persons the
  article lists as depicted; the three zones of the design; the border
  decoration in aggregate, as `represents_instance_of_type` (birds, beasts,
  fish, fables, agriculture, hunting, nude figures, arms and apparel); the
  three objects the article singles out (the harrow as the earliest known
  depiction, the motte and bailey, the ships); the tituli; the four disputed
  readings the article devotes space to.
- **Out:** the scene-by-scene retelling. The 16 scenes the article discusses
  individually are listed in one scope note on the visual item, with their
  numbers, so nothing is silently dropped; the ones it merely narrates are not
  given instances.
- **Out per the brief:** reception, influence, popular culture, replicas and
  continuations (the Leek/Wardle 1885-86 replica, Ray Dugan, Lindholm Hoje,
  ReVille, the Geraldine mosaic, Jason Welch, Mia Hansson, the Victorian
  photographic copy the museum bought in 2024, the needle-lace runner, and the
  Messent and Alderney reconstructions of the missing ending). Note that the
  Messent and Alderney pieces are reconstructions *of the lost part* as new
  objects, not alterations of this object, so they fall under "replicas", not
  under scope item 6.
- The Girona Tapestry, the Cloth of Saint Gereon, the Oseberg and Overhogdal
  finds and Byrhtnoth's lost hanging are other objects; only Byrhtnoth's
  appears, inside a note, because Dodwell's bequest argument depends on it.

## 5. `validate --xml` — the required check

Run against the file as written, not against transcribed triples:

```
$ uv run python search.py validate --xml crm_bayeux.xml
575 links checked: 2 ambiguous, 437 ok, 136 ok_literal
structural elements skipped: CRM_Entity in_class unit value

AMBIGUOUS links are legal but underdetermined. This format writes property
labels as element names, so the file cannot say which of them it means --
record the intent in your notes; there is nothing to fix in the document.

  AMBIGUOUS      assigned
      E17 -> E55   at CRM_Entity[E22]/was_classified_by/assigned
      P42 or P141 both fit; the element name cannot distinguish them
  AMBIGUOUS      assigned
      E17 -> E55   at CRM_Entity[E22]/was_classified_by/assigned
      P42 or P141 both fit; the element name cannot distinguish them
```

**No `illegal`, no `unknown_name`, no `LABEL_MISMATCH`.**

Account of the two findings, which are the only ones:

- Both are the `<assigned>` element inside the two `<was_classified_by>`
  blocks on the object — the conventional classification as a "tapestry", and
  the 2007 UNESCO admission. **P42 assigned** (E17 → E55) and **P141 assigned**
  (E13 → E1) genuinely share the label "assigned", and this format writes
  labels, so the document cannot say which. **My intent in both cases is
  P42 assigned**, the specialised property of E17 Type Assignment, since both
  are classifications and both objects are instances of E55 Type. This is not a
  defect I can fix in the file; clayton has the same construct (its
  `<assigned>` under `<was_classified_by>`), and the tool's own message says
  there is nothing to fix in the document.

Two earlier findings were fixed rather than defended:

- `ILLEGAL has_time-span, E31 -> E52` — I had dated the 1476 cathedral
  inventory by hanging P4 off the E31 Document. E31 is not an E2 Temporal
  Entity. Fixed by giving the inventory an **E65 Creation** and dating that.
- An XML well-formedness error, not a CRM error: `--` inside XML comments.

En route I probed 50 element names in throwaway files before using them, so
that no name in the final document was guessed: `has_time-span` (with the
hyphen), `has_preferred_identifier`, `changed_ownership_through`,
`custody_transferred_through`, `was_object_encountered_through`,
`assigned_property_of_type`, `was_made_for`, `represents_instance_of_type` and
the rest all resolve.

## 6. What the article gave no basis for — modelled as nothing, recorded here

The brief asks for these to be explicit rather than silently skipped.

- **Burial, deposition, excavation, findspot: none.** The Bayeux Tapestry was
  never buried and never excavated. Its recorded history is continuous
  above-ground custody from at latest 1476. Scope item 4 is therefore satisfied
  only by its rediscovery half: the scholarly rediscovery of 1729 (S19), and
  the 2023 discovery of the fragments stolen in 1941. Two absence notes in the
  file say this in the record itself.
- **No identifier.** The article gives no inventory number, accession number or
  catalogue number. Both published examples build their whole record around
  `E42: Object Identifier` and clayton adds a preferred identifier; I have
  neither, and used **E41 Appellation** for the five names the article does
  give (Bayeux Tapestry, Tapisserie de Bayeux, La telle du conquest, Tapete
  Baiocense, La Tapisserie de la Reine Mathilde). No `P48 has preferred
  identifier` appears, because there is no E42 to point it at.
- **No current owner.** The 1792 confiscation vested title in the French state;
  nothing afterwards is described as a transfer of *title*, only of custody. So
  no `P52 has current owner` is asserted. This is a real gap in the article, not
  in the model.
- **No reversed or superseded restoration.** Scope item 6 asks for alterations
  "including any later reversed or superseded". The article records none that
  was undone. The nearest things are the alleged conversion of a spear into the
  arrow in Harold's eye, which is contested rather than reversed (recorded as an
  E11 typed `alleged alteration` + `contested`, with the assertion and the
  counter-assertion as two E13s), and the Matilda attribution, which is
  superseded scholarship rather than a physical alteration (typed
  `superseded attribution`).
- **The nine linen panels are not individually identified** in the article
  (only "between fourteen and three metres in length"), so they are one
  collective part plus `P57 has number of parts: 9`, not nine instances.
- **No agent** is named for the 1724 backing, the c.1800 numerals, the
  spurious 1814 titulus, the 19th-century restoration, the restorations of the
  first and last sections, the collective patching, the 1870 storage, or the
  2023 discovery. Those events have no `carried_out_by`. P14 is quantified
  "necessary (1,n:0,n)" on E7, so strictly every one of them is under-specified;
  inventing a restorer would be worse.

## 7. Where the CRM does not cover this well

- **An intended transfer that did not happen.** On 18 August 1944 Himmler
  ordered the tapestry taken to Berlin, and on 22 August the SS tried and
  failed to take possession. The CRM models what happened; there is no way to
  state that a transfer of custody was ordered or attempted and did not occur.
  E29 Design or Procedure is the nearest fit for the order itself but has no
  property tying an unexecuted plan to its intended object. Both facts are in a
  `has_note` on the 1944 Gestapo transfer, and flagged as a gap in the file.
- **No property for "made for a person".** P19 was intended use of relates an
  activity to a thing, and its inverse "was made for" therefore takes an
  activity, which works for Norton's 1077 cathedral dedication but not for
  "perhaps as a gift for William". P103 was intended for takes an E55 Type.
  There is no E71 → E39 property. Carried by `P177 assigned property of type` =
  "intended recipient" on the relevant E13.
- **No property for "commissioned by"** — handled through P14 + a role, as
  above, but the role has to be smuggled into a type string because this XML
  dialect has no way to write a property-of-property like P14.1 except as a
  nested element, and clayton and amol only ever do that for P3.1.
- **A missing part that is simply gone.** The end of the tapestry has been
  missing "from time immemorial". E6 Destruction would assert a destruction the
  article does not record; E80 Part Removal would assert a removal event and an
  agent. I modelled the missing section as an E22 with its three competing
  estimated lengths and *no* event, and said so in a note. The CRM has no way
  to say "this part is absent and we do not know how".
- **Alternative values with no arbiter.** Recording 58-or-70 scenes and
  1.5-or-3-or-6.4 m as parallel E54 Dimensions is what principle 6.2 asks for,
  but nothing in CRMbase marks the set as *mutually exclusive alternatives*
  rather than as several true measurements. CRMinf's belief adoption machinery
  would say it; CRMbase cannot.
- **One event, two classes.** Several 20th-century episodes are simultaneously
  a physical move and a change of custody (1803 Paris, 1944 Louvre, 2026
  London). The CRM allows an instance to be both E9 and E10; this XML dialect
  has one `<in_class>` per instance and no way to say so. I chose the class the
  article emphasises (E10 in each case) and used E9 only for the 19 September
  2025 removal, which the article describes as a movement with no change of
  keeper.

## 8. Notes on the search tool itself

Recorded because the brief asks for it.

- `validate --xml` is the strongest thing in the toolbox. It caught the
  clayton errors before I could copy them, it distinguishes
  `unknown_name` / `illegal` / `ambiguous` / `LABEL_MISMATCH`, and it accepts
  CRMsci identifiers alongside CRMbase without complaint. Probing throwaway
  files with it is a fast way to confirm an element-name spelling.
- `ontology --model CRMbase` in one call gives every id, label, superclass and
  domain→range in 264 lines — the single most useful call for this task, and
  it is what stopped me writing `E38 Image` or `E84 Information Carrier`, both
  of which no longer exist in 7.3.2.
- **Limitation:** `docs` returns only a ~300-character head snippet of the
  matching section and there is no way to read the rest. `--raw` does not
  expand it, `show` only works on mailing-list messages, and `quote` returns a
  ~150-character window around a phrase you must already guess. I could not
  read Modelling Principle 6.2 or the "Authorship of Knowledge Base Contents"
  section in full; I worked from the snippets plus the E13 scope note, which
  was enough here, but a reader who needed the argument rather than the
  headline would be stuck.
- **Minor:** the same label mismatch is reported as `LABEL_MISMATCH` when it is
  the only finding and as `STALE_LABEL` when other findings are present, which
  makes it easy to grep for the wrong string.
- `issues` and the mailing-list search returned nothing decisive on
  commissioner/patron modelling; that is a real absence in the SIG record as
  far as these queries reach, not a tool failure.

## 9. Counts

- 32 distinct CRM classes: E3 E5 E7 E8 E9 E10 E11 E12 E13 E17 E21 E22 E31 E32
  E34 E36 E37 E41 E52 E53 E54 E55 E56 E57 E60 E61 E65 E69 E74 E79 E80, plus
  S19 (CRMsci).
- 51 distinct CRM properties, counting each property once regardless of
  direction: P1 P2 P3 P4 P7 P12 P14 P22 P23 P24 P25 P27 P28 P29 P30 P31 P32
  P41 P42 P43 P44 P45 P46 P49 P53 P57 P65 P67 P70 P72 P79 P80 P81 P82 P89 P94
  P106 P108 P110 P111 P112 P113 P126 P128 P138 P140 P141 P177 P199, plus O19
  and O21 (CRMsci).
- 575 links checked, 0 illegal, 0 unknown_name.
