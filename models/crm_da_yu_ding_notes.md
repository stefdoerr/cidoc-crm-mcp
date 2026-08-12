# Notes on `crm_da_yu_ding.xml`

A CIDOC CRM encoding of the Da Yu ding (大盂鼎), in the XML form of
`crm_amol_1.xml` and `crm_clayton1.xml`. Content comes from the English
Wikipedia article "Da Yu ding" and nothing else. Everything I know about the
CRM in this file came through `search.py`.

**Size:** 31 distinct CRM classes, 61 distinct CRM properties, 379 links.

---

## 1. Conventions taken from the two examples

Both files agree on the essentials, and I followed them:

- Root element `<CRMset>`; each top-level record is a `<CRM_Entity>`.
- **An instance is an element whose text content is its label, with a child
  `<in_class>Exx: Class Name</in_class>`.** There are no `id`/`ref`
  attributes anywhere.
- **Identity is by label string.** The same label used twice denotes the same
  instance. Clayton depends on this heavily — "Clayton", "J.L. Reveal",
  "Species Plantarum" recur across all 25 records — so I use it too: the ding's
  ownership chain, its places and its sources are all cross-linked by repeating
  labels, and three entities that needed their own detail (the Xiao Yu ding, the
  Da Ke ding, the death of Zhou Gengsheng) sit in their own `<CRM_Entity>`
  records and are referred to from the main one by name.
- **Property elements are the CRM property label with spaces replaced by
  underscores and no P-number**, e.g. `transferred_title_to`, `took_place_at`.
  Either direction may be used, whichever reads parent-to-child: Clayton's
  `is_documented_in` is P70i, `was_classified_by` is P41i. I use both directions
  the same way.
- **Literal-valued properties carry bare text and no `<in_class>`** —
  `has_note`, `has_value`.
- Both examples sub-type E55 inside the `in_class` string —
  "E55: Dimension Type", "E55: Acquisition Type", "E55: Genus Type". These are
  not CRM class names; the validator parses only the leading number and ignores
  the label. I kept the convention (Note Type, Object Type, Acquisition Type,
  Motif Type, Property Type, …) because both examples use it and it makes the
  file readable, but see §2.4 on how little that text is worth.

### Where the two examples disagree, and what I picked

| | amol | clayton | what I did |
|---|---|---|---|
| **Dimensions** | `has_dimension` with `<value>` and `<unit>` children | none | amol's structure, but with the real labels `has_value` (P90) and `has_unit` (P91), and `<in_class>E58: Measurement Unit</in_class>` on the unit instead of a bare string. `validate --xml` reports `value` and `unit` as "structural elements skipped" — it cannot check them at all — whereas `has_value`/`has_unit` are checked and pass. Following the standard over the example, as instructed. |
| **Identifiers** | `is_identified_by` only | adds `preferred_identifier_is` | `is_identified_by` (P1) only. `preferred_identifier_is` is not a property label (§2.1), and in any case the article gives no accession number, so the names are E41 Appellation, not E42 Identifier. |
| **Where content lives** | almost everything in typed `has_note` blocks (Statement / Made / Description / Marks / Subject) | structured properties, occasional untyped notes | clayton's structured grain for the substance; amol's typed-note convention for what the CRM cannot structure. My note vocabulary is Statement, Description, Content, **Source discrepancy**, **Contested**, **Modelling note** — the last three carry every place where the article disagrees with itself, hedges, or is silent. |
| **Class labels** | "E22: Man-Made Object" (the pre-7.0 label) | "E42: Object Identifier" and "E42: Object identifier" for the same class in adjacent elements; "E:55 Type Type" with the colon misplaced | v7.3.2 labels throughout, spelled consistently. E22 is **Human-Made Object** in the current standard. |
| **Nesting** | one flat record per object | events nested under the object | clayton's nesting, plus the three satellite records noted above. |

---

## 2. Where an example is wrong

I ran the checker on both published files first, to calibrate.

```
amol:    637 links checked: 426 ok, 211 ok_literal
clayton: 656 links checked: 25 illegal, 420 ok, 120 ok_literal, 91 unknown_name
```

amol is clean. Clayton is not, and its faults are the ones this exercise is
built to catch. Each appears once per record, ×25 records.

**2.1 Three element names that are not CRM property labels.**

| clayton writes | intended property | correct element name |
|---|---|---|
| `preferred_identifier_is` | P48 has preferred identifier | `has_preferred_identifier` |
| `changed_ownership_by` | P24i changed ownership **through** | `changed_ownership_through` |
| `at_most_within` | P82 at some time within | `at_some_time_within` |

I use `changed_ownership_through` and `at_some_time_within` throughout. I do not
need P48.

**2.2 `at_most_within` is wrong twice over.** Clayton points it at an
`E52: Time Span`. `concept P82` gives the range as **E61 Time Primitive**, not
E52. The correct shape is event → P4 has time-span → E52 Time-Span → P82 at some
time within → E61 Time Primitive, and that is the shape used everywhere in my
file (18 occurrences).

**2.3 25 `illegal` links: `took_place_at` on an actor.** Clayton nests
`took_place_at` inside `transferred_title_to`, so P7 hangs off the E39 Actor
rather than off the E8 Acquisition. P7's domain is E4 Period; an actor is not a
period, and in any case the place belongs to the transfer, not to the person. In
my file `took_place_at` appears only on events.

**2.4 The `in_class` label text is unchecked.** `E:55 Type Type`,
`E:55 Type` and the `Object Identifier`/`Object identifier` casing split all pass
silently, because the validator reads only the number. That means the label half
of `in_class` carries no guarantee in these files and should not be trusted as
evidence of anything — including as evidence for the current spelling of a class
name, which is why I took spellings from `ontology --model CRMbase` instead.

---

## 3. The modelling choices that were actually hard

### 3.1 An inscribed artefact is three things

This is the distinction everyday language collapses, and the CRM does not:

| | class | instance in this file |
|---|---|---|
| the bronze | **E22 Human-Made Object** | `Da Yu ding` |
| the text, as an immaterial prototype | **E34 Inscription** | `the inscription of the Da Yu ding` |
| the one physical embodiment of that text | **E25 Human-Made Feature** | `the cast characters on the interior wall of the Da Yu ding` |

`concept E34` is explicit that the second and third are different things:

> This class is not intended to describe the idiosyncratic characteristics of an
> individual physical embodiment of an inscription, but the underlying prototype.
> The physical embodiment is modelled in the CIDOC CRM as instances of E24
> Physical Human-Made Thing.

`concept E25` settled which E24 subclass: its own worked examples include *"the
carved letters on the Rosetta Stone"*.

The links:

- E22 **P128 carries** E34 — the bronze carries the text.
- E34 **P200 has complete copy** E25 — the text's complete physical realisation.
  `concept P200` describes it as "a complete, identifying representation of its
  content in the form of a sufficiently readable instance of E25 Human-Made
  Feature carrying it". For a cast bronze this is the only realisation there has
  ever been, so it is also the last witness of the content, which is exactly the
  case that scope note is written for.
- E22 **P56 bears feature** E25 — stated as well as implied, because
  `concept P56` quantifies P56 as *dependent* (0,n:1,1): every physical feature
  is found on exactly one object.

**What it says.** P106 is composed of splits the inscription into its four
sections — the first speech (the moral history of the Shang's fall), the second
(the charge to emulate Nan Gong), the third (the appointment and the inventory,
including the 1,726 people listed), and Yu's closing dedication. P106 rather than
P148 has component: `concept E34` lists both as applicable, but P106 is the
symbolic-object composition (E90→E90) and these are parts of a text, not
components of a proposition. P129 is about reaches the royal charge at Zongzhou
that the text narrates; P67 refers to reaches the people it names.

**P190 has symbolic content is deliberately left empty on the inscription.**
Thread **t1838** (2025-04-17, Velios → Doerr, *decided*) settles that E34's scope
note should recommend P190 over P3 for the transcription — so P190 is the right
slot. But the article does not reproduce the Chinese text; it gives only an
English translation. P190 must carry *this* symbolic object's content, not a
rendering of it into another language, so the translation is a separate E33
Linguistic Object reached by P73 has translation, and *it* carries the P190.

**P62 depicts is deliberately not used for the inscription.** Its scope note
excludes exactly this: *"The property does not pertain to inscriptions or any
other information encoding."*

### 3.2 Taotie versus animal faces: P138 or P199

`concept P199` draws the line I needed:

> This property is used when the identity of the thing depicted is unknown or
> unrecorded, but is clearly a particular thing of that type. If the instance of
> E36 Visual Item directly depicts the concept of the E55 Type rather than an
> instance of a thing of that type, then this should be represented using
> E36 Visual Item P138 represents E55 Type.

- The **taotie** on the mouth is a conventional mythical mask motif. It shows the
  concept, not some individual creature whose name has been lost → **P138
  represents** → E55 Type `taotie (饕餮)`.
- The **animal face patterns** on the legs name a kind of thing with no
  identifiable subject → **P199 represents instance of type** → E55 Type
  `animal face`.

Both hang on E36 Visual Items attached by P65 shows visual item to the *features*
(the mouth, the legs) rather than to the object as a whole, because the article
localises them.

### 3.3 Three competing dates, none of them resolved

The article gives three datings, all agreeing on the regnal year and disagreeing
on the absolute one: **early 10th century BC** (infobox, unsourced), **997 BC**
(Shanghai Museum 1959, from the ding's own statement of King Kang's 23rd year on
a 1020 BC accession), and **981 BCE** (Minford 2009, after Shaughnessy in the
*Cambridge History of Ancient China*).

`concept P81` returned the SIG's own worked example for precisely this problem —
the First Intermediate Period given P81 ongoing throughout "2181 BC – 2160 BC",
annotated *"This is the minimal common agreement of two conflicting dates"*
(Breasted vs Shaw), with P82 carrying the outer bound. I applied the same
construction:

- **P82 at some time within `997 BC to 981 BC`** on the production's time-span —
  the intersection of the maximum extents the sources justify.
- **No P81.** The two absolute proposals are points that do not overlap, so there
  is no common inner bound to assert. Writing one would invent agreement.
- **One E13 Attribute Assignment per proposal**, each with P177 assigned property
  of type, P140 assigned attribute to, P141 assigned and P70i is documented in.

`concept E13` licenses this directly:

> the use of instances of E13 Attribute Assignment marks the fact that the
> maintaining team is in general neutral to the validity of the respective
> assertion, but registers someone else's opinion and how it came about. …
> Multiple use of instances of E13 Attribute Assignment may possibly lead to a
> collection of contradictory values.

**The article contradicts itself here** and I recorded it rather than picking a
side: it dates King Kang's reign 1020–996 BC, which makes his 23rd year 997 BC,
and then gives 981 BCE for that same 23rd year — a date outside the reign the
same article states.

The **attribution to King Kang's reign** is likewise an E13, not a direct P4,
because the article's two grounds are both inferential: the Xiao Yu ding found
alongside (P16 used specific object) and stylistic comparison with other bronzes
of the period.

### 3.4 Ownership: the arithmetic decided the model

The article calls Zuo Zongtang "the fifth owner" and Pan Zuyin "the sixth". That
only comes out right if Song Jinjian's recovery is a *third* distinct ownership:

> Song Jinjian (1) → Zhou Gengsheng (2) → Song Jinjian again (3) → Yuan Baoheng
> (4) → Zuo Zongtang (5) → Pan Zuyin (6)

So the expropriation and the recovery are two separate instances of E8
Acquisition, not one disputed episode. This is also the clearest instance in the
article of a transfer later **reversed**.

Other decisions in the chain:

- **The 1873 purchase** is E96 Purchase, whose scope note requires the
  transferring party to be "completely compensated by the payment of a monetary
  amount" — satisfied. P179 had sales price → E97 Monetary Amount, P90 has value
  700, P180 has currency → E98 `tael of silver`. The seller is not named, so no
  P23. Dated by terminus ante quem (Wu Dacheng saw it in Yuan's estate in winter
  1873) using P80 end is qualified by.
- **Yuan → Zuo** is hedged in the source ("Yuan *may have* sent the tripod he
  bought to Zuo"). I instantiate the acquisition anyway, because the same article
  calls Zuo the fifth owner and has him giving the ding away in 1875, which
  entails he held it; what is uncertain is the route, not the fact. The hedge is
  carried by `has_type` "reported but not established" and a Contested note.
- **The Ko family** is an E13, not a rival E8. The article reports a disagreement
  about *who owned it*, citing 陝西金石志 (1934); it does not describe a transfer.
  Modelling a phantom acquisition would assert more than the source does.
- **Pan Zunian's inheritance** is instantiated with a Contested note: the article
  says he inherited "the family property" and does not name the ding.
- **The 1951→1959 gap.** The article never says how title passed from Pan Zunian
  (d. 1925) to Pan Dayu, who made the 1951 donation. Recorded as a gap.
- **1959 is E10 Transfer of Custody, not E8.** The article says only
  "transferred". Nothing in it says legal title moved to the National Museum of
  China, so I model custody (plus an E9 Move, Shanghai → Beijing) and say in a
  note that an E8 would be needed if title moved too. This also **supersedes** the
  1951–1959 joint display at the Shanghai Museum.
- **March 2004** is a second E10, typed "temporary loan for exhibition". The
  article does not record the return, so no reversing transfer is asserted.

### 3.5 Deposition, rediscovery, and two silences

- **The 1849 find.** There is no class in CRMbase that means "was found" (§5.1).
  Modelled as E9 Move typed "unearthing (chance find)", with P27 moved from and
  P7 took place at the findspot, P12 occurred in the presence of the Xiao Yu ding,
  and — separately, on the object — P53 has former or current location for the
  findspot itself, with P89 falls within nesting Li Village → Jingdang Township →
  Qishan County → Shaanxi → China, after clayton's Virginia → USA. Infobox 1849
  and body "Daoguang era" are compatible (P86 falls within) and both are recorded.
- **The original deposition is absent from the article.** Nothing about when, how,
  or from what context the ding entered the ground. Not asserted; recorded as a
  Modelling note.
- **The 1937 burial** is an E9 Move typed "deliberate concealment by burial", with
  P16 used specific object → the wooden box, P14 carried out by the Pan family,
  P17 was motivated by the outbreak of the Second Sino-Japanese War, and P25
  moved also reaching the Da Ke ding. The article gives no burial location, so no
  P26 moved to. **It also never records the recovery**, though the 1951 donation
  entails one. Both silences are noted rather than filled.

### 3.6 Restoration and condition: the article has neither

Scope item 6 asks for every reconstruction, restoration or alteration. **The
article records none**, and makes no statement about the object's physical
condition. So there is no E3 Condition State and no post-production E11
Modification in this file, and an explicit Modelling note on the object says so —
the absence is in the source, not in the model. I have not invented a
conservation history to fill the slot.

The clause "including any later reversed or superseded" does have referents here,
but they are in the custody chain rather than in the fabric, and all three are
modelled: the expropriation reversed by Song's recovery (§3.4), the 1951–1959
Shanghai display superseded by the 1959 transfer, and the 2004 loan typed as
temporary. The dating and the first-owner claim are the *superseded assertions*,
handled in §3.3 and §3.4.

### 3.7 Smaller points

- **E40 Legal Body is deprecated.** `concept E40` returns no definition plus the
  migration row "E40 Legal Body | use E74 Group". Museums are E74 Group.
- **No E42, no P48.** The article gives no accession number. The names are E41
  Appellation, with P139 has alternative form linking 大盂鼎 to its romanisations.
  Asserting an E42 Object Identifier here — which is what both examples would
  invite — would be inventing a museum number.
- **The aperture.** The body calls 77.8 cm the aperture, the infobox calls the
  same figure "width". Recorded as aperture (the running-prose reading) with the
  disagreement in a Source discrepancy note.
- **Three legs or four.** The article says "round, with three legs" and, two
  sentences later, "its four legs are engraved with animal face patterns". Both
  are recorded, as two E13 Attribute Assignments on the legs feature, plus a
  Source discrepancy note. Neither is preferred (§5.5).
- **Language.** The article names only the script ("Chinese characters"), so the
  E56 Language is `Chinese` with a note that Old Chinese would be more precise but
  is not stated. P72 has language is a *necessary* property on E33/E34, so it had
  to be filled with something.
- **The casting place is unknown.** Zongzhou is where the King charged Yu, not
  where the vessel was cast. No P7 on the production.

---

## 4. `validate --xml` — required check

```
$ uv run python search.py validate --xml /home/sdoerr/Fun/papa/crm_da_yu_ding.xml
379 links checked: 307 ok, 72 ok_literal
structural elements skipped: CRM_Entity in_class unit value

Every link resolves to a real property and stays inside its declared domain and range.
```

**`unknown_name`: none.** The three that appear in the clayton example
(`preferred_identifier_is`, `changed_ownership_by`, `at_most_within`) were
identified before I wrote anything, by running the checker on the examples
themselves, and deliberately not copied. See §2.1.

**`illegal`: none in the final file.** Two arose on the first full run and both
were real errors of mine, fixed rather than argued away:

1. `ILLEGAL at_some_time_within  E4 -> E61  at
   .../was_attributed_by/assigned/at_some_time_within — E4 is not a E52`.
   I had hung P82 straight off the E4 Period "the reign of King Kang of Zhou".
   P82's domain is E52 Time-Span. **Fixed** by inserting P4 has time-span → E52
   between the period and the time primitive.
2. `ILLEGAL was_present_at  E22 -> E4  at CRM_Entity[E22]/was_present_at —
   E4 is not a E5`. I had used P12i to place the object in the Western Zhou
   dynasty. P12's domain is E5 Event, and E4 Period is E5's *superclass*, not a
   subclass — so a period cannot have had anything present at it. **Fixed** by
   reaching the period from the production instead, by **P10 falls within**, which
   relates spacetime volumes (E92→E92) and admits both an E12 and an E4.

**`structural elements skipped: … unit value`** — this line reflects the
validator's allowance for amol's bare `<value>`/`<unit>`, which it cannot check.
My file does not use those names; it uses `has_value` (P90) and `has_unit` (P91),
which *are* checked and pass. Nothing of mine is being skipped.

**`ok_literal` (72)** are the notes and numeric values — `has_note`,
`has_symbolic_content`, `has_value`, `beginning_is_qualified_by`,
`end_is_qualified_by`. All are properties whose range is a primitive
(E62 String, E60 Number), correctly written as bare text.

One caveat I want on the record: `<has_type>` nested inside `<has_note>` — a
construction both examples use and which I kept — is formally **P3.1 has type**,
a property of the property P3, not P2 on some node. The checker does not object,
but it is not verifying what the construction actually means. See §5.2.

---

## 5. What the CRM, or this XML form, could not carry

**5.1 There is no CRMbase class meaning "was found".** The 1849 rediscovery is the
weakest join in the file. **CRMsci S19 Encounter Event**, with O19 encountered
object and O21 encountered at, is the class that means this; CRMarchaeo A9
Archaeological Excavation would be wrong, since a chance find by villagers in
1849 is not an excavation project. I could not use S19 — see §6.1 — so the event
is an E9 Move typed "unearthing (chance find)", which captures the relocation out
of the ground and loses the finding. A note on the event says so.

**5.2 Property-of-property (`.1`) qualifiers have no slot in this XML form.** Yu
commissioned the ding rather than casting it; P14.1 in the role of is the CRM's
device for that, and there is nowhere to put it. `validate --xml` confirms the
shape is not expressible:

```
NOT_A_CLASS_LINK in_the_role_of
    E21 -> E55   ...  its domain is the property P14, not a class
```

The role is carried in a Modelling note instead. The same limitation silently
affects the `<has_type>`-inside-`<has_note>` construction both examples use
(P3.1), and would affect P62.1 mode of depiction and P67.1 had I needed them.

**5.3 There is no way to hedge a single property instance.** "Yuan *may have* sent
the tripod to Zuo" is a claim about the confidence of one link. CRMinf's I2
Belief / J4 that / J5 holds to be is the machinery for this, but it requires the
proposition to be reified as an I4 Proposition Set, and this XML form has no way
to name a triple so as to point at it. I fell back on E13 Attribute Assignment
plus typed notes, which records *that* something is contested but not *how
strongly*.

**5.4 Deliberate concealment is not a modelled act.** E9 Move plus a type carries
the 1937 burial's relocation; the CRM has no notion of an object being put beyond
reach and later retrieved. CRMarchaeo A7 Embedding describes the resulting
stratigraphic state, not the act of hiding.

**5.5 Nothing says "these two assertions conflict".** E13 lets me record the
three-legs claim and the four-legs claim side by side, but there is no property
joining them as a contradiction — the reader has to notice. Same for the two
datings, and for Song Jinjian versus the Ko family. I compensated with a
`Source discrepancy` / `Contested` note type, which is documentation, not
structure.

**5.6 A probable error in the v7.3.2 text.** `concept P200` gives P200 has
complete copy as a **subproperty of P128 carries**, but with domain E90 and range
E25 — running the opposite way from P128 (E18 → E90). Its own scope note then
refers to it as *"the property P128 has complete copy (is complete copy of)"*. One
of the two is wrong. I used P200 as declared (E34 → E25) and it validates.

---

## 6. Findings about the search system itself

**6.1 `validate --xml` knows CRMbase property labels only.** Extension *classes*
resolve correctly — `<in_class>S19: Encounter Event</in_class>` is placed in the
hierarchy and `took_place_at` on it validates — but every extension *property*
label I tried came back `unknown_name`:

```
UNKNOWN_NAME  encountered_object   S19 -> E22    (CRMsci O19)
UNKNOWN_NAME  encountered_at       S19 -> E53    (CRMsci O21)
UNKNOWN_NAME  that                 I2  -> I4     (CRMinf J4)
UNKNOWN_NAME  holds_to_be          I2  -> I6     (CRMinf J5)
```

This is the single biggest limit I hit. `unknown_name` from a correctly-spelled
extension property is indistinguishable from `unknown_name` from a typo, so using
CRMsci or CRMinf would have made the required verification step meaningless — I
would be signing off a file with findings I had chosen to ignore. Both published
examples are pure CRMbase, so staying in CRMbase is also the conservative reading
of "follow the examples". It cost me §5.1 and §5.3.

**6.2 `docs` truncates at ~300 characters and there is no way to read a whole
section.** The passage most relevant to §3.3 — "Dates and Durations" in the
Introduction (`crm732#s0078`), which the search itself returned as the top hit for
conflicting dates — is cut off mid-sentence, and `quote` only confirms a phrase I
would have to already know in order to ask for it. **Workaround:** `concept P81`
and `concept P82` return complete scope notes *and* complete example lists, and
the P81 examples contained the SIG's own worked treatment of two conflicting
dates. For anything the narrative index merely teases, go to `concept`.

**6.3 `ontology --model CRMbase` should be the first command anyone runs for this
task.** 264 lines, every identifier with both directions of every property label
and its domain and range. In this XML form the element name *is* the property
label, so getting a label wrong is the exact failure this exercise tests for, and
one call removes the entire class of error. It is listed in the brief but not
flagged as load-bearing; it is.

**6.4 Two "current" versions in one answer.** `concept E34` is headed
`[v7.1.3 (current)]` and then appends "From CIDOC CRM v7.3.2 (not in the v7.1.3
XML above)", while `concept P199` and `concept P200` are headed
`[CIDOC CRM v7.3.2 (current)]`. Two documents are being merged and both are
labelled current. It did not mislead me, but it took a second reading to be sure
which text was standing — and for a task whose whole point is "follow the
standard, not the example", that ambiguity is not free.

**6.5 What worked well.** `validate --xml` run against the *published examples*
before writing a line was the highest-value thing I did: it produced the exact
list of names not to copy, with the correct replacements derivable from
`ontology`. Probing candidate element names in a throwaway file before committing
to them turned label-guessing into a checked step — that is how I learned that
`has_time-span` (with the hyphen) parses, that `moved_by` is right and
`was_moved_by` is not, and that `in_the_role_of` has no expressible form.
