# Mao Gong ding in CIDOC CRM — modelling notes

Model: `crm_mao_gong.xml`. Subject: the English Wikipedia article *Mao Gong ding*.
Format references: `crm_amol_1.xml` and `crm_clayton1.xml`.
Everything I know about the CRM here came through `search.py`; the two example
files and the article were fetched from the three URLs in the brief.

27 distinct classes, 44 distinct properties, 247 links.

---

## 1. Conventions taken from the two examples

Both examples share a single, unstated serialisation, and I followed it:

- Root `<CRMset>`; each independently-declared instance is a `<CRM_Entity>` child.
- **An element's text content is the instance's identity.** Two elements with the
  same text are the same instance. That is how Clayton makes the actor "Clayton"
  recur across 25 records, and it is how this document makes
  `the inscription of the Mao Gong ding` appear under both the vessel and Chen
  Jieqi's rubbings, and `Chen Jieqi` appear under an acquisition, a production and
  his own top-level entity.
- **A nested `<in_class>Exx: Label</in_class>` types the instance.**
- **Every other element name is a CRM property label with spaces as underscores**,
  written in whichever of the two directions makes the enclosing instance the
  subject (`is_documented_in` for P70i, `was_produced_by` for P108i, and so on).
- Freetext hangs on `has_note`; classification on `has_type`; naming on
  `is_identified_by`.
- Both keep the `<?xml-stylesheet href="crm.xsl"?>` instruction. I kept it.

### Where the two examples differ, and what I picked

| Point | AMOL | Clayton | Chosen |
|---|---|---|---|
| Depth | flat: object, identifier, notes, types, dimensions. No events at all. | event-centric: acquisitions, type assignments, actors, places, time-spans. | **Clayton.** Six of the seven required topics are events; AMOL's shape cannot express any of them. AMOL contributes the dimension and `is_documented_in` patterns. |
| Role of a type | encoded in `in_class`: `E55: Dimension Type`, `E55: Object Type` | encoded as a nested `has_type` on the type itself: `E55: Plant Species Type` *and* `<has_type>Plant Species</has_type>` | **Neither literally.** Both write role names into `in_class`, and `validate --xml` flags every one as `LABEL_MISMATCH` against the model's own label for E55. I write `E55: Type` and carry the role in the instance's text and, where useful, in `has_broader_term`. |
| Dimension value | bare `<value>` / `<unit>` elements | no dimensions | **Neither.** See §2. |
| Identifier | `is_identified_by` → E42 Object Identifier | additionally `preferred_identifier_is` → E42 | **`is_identified_by` → E41 Appellation.** The article supplies names, not codes; see §4.1. |
| Encoding | ISO-8859-1 | ISO-8859-1 | **UTF-8**, because the object's name is 毛公鼎. |

I also added something neither example has: XML comments as section headers. They
cost nothing (the validator skips them) and the document is 800 lines long. Note
that `--` may not appear inside an XML comment, which is what a run of dashes as
a divider produces; that is what broke my first parse.

---

## 2. Where an example is wrong, and what I did instead

`validate --xml` on the two examples themselves, which is the cheapest way to find
this out:

**AMOL** — `637 links checked: 426 ok, 211 ok_literal`, plus four `LABEL_MISMATCH`
(`E22: Man-Made Object`, `E42: Object Identifier`, `E55: Object Type`,
`E55: Dimension Type`). No `unknown_name`: the validator lists `value` and `unit`
among its *skipped structural elements*, so AMOL's bare `<value>275.0</value>`
passes unexamined rather than passing correctly.

**Clayton** — three distinct `UNKNOWN_NAME`s repeated across all 25 records, one
`ILLEGAL`, and one `AMBIGUOUS`:

| In Clayton | Verdict | Standard | Used here |
|---|---|---|---|
| `preferred_identifier_is` | `UNKNOWN_NAME` | P48's label is **has preferred identifier** | not needed — no identifier in the source |
| `changed_ownership_by` | `UNKNOWN_NAME` | P24i is **changed ownership through** | `changed_ownership_through` |
| `at_most_within` | `UNKNOWN_NAME` | P82 is **at some time within**, and its range is **E61 Time Primitive**, not E52 | `has_time-span` → E52, then `at_some_time_within` → E61 |
| `took_place_at` nested under `transferred_title_to` | `ILLEGAL` — "E39 is not a E4" | P7's domain is E4 Period | `took_place_at` hangs on the event, never on the actor |
| `assigned` on E17 → E55 | `AMBIGUOUS` — P42 or P141 | genuinely undecidable from the label | not used |

Clayton's `at_most_within` error is the more interesting of the three: it is not
just a bad label, it also collapses two levels. The CRM's route from an event to a
date is *event → P4 has time-span → E52 Time-Span → P82 at some time within → E61
Time Primitive*, and the reference model is explicit that P82 "is the default for
historical dates, given, for instance, in years for events of much smaller
duration" (`docs`, chunk `crm732#s0078`). Every date in this document takes that
three-step route.

AMOL's `value`/`unit` are not CRM labels either — P90 **has value** (→ E60 Number)
and P91 **has unit** (→ E58 Measurement Unit) are. They escape the validator only
because it whitelists them as structural. I write them out in full, with classes.

### The typed note: a third example defect, which the validator does not flag

Both examples type their notes by nesting `has_type` inside `has_note`:

```xml
<has_note>Textile length, batik, silk...<has_type>Statement
  <in_class>E55: Type</in_class></has_type></has_note>
```

The intent is unmistakably **P3.1 has type**, the CRM's `.1` property for
qualifying a note. But P3.1's label *is* "has type" — the same string as P2 — and
this format has only element names to work with. I checked what the validator
actually makes of it, by tracing paths in `validate --xml --json`:

```
('E22', 'has_type', 'E55', 'ok', 'P2')  |  CRM_Entity[E22]/has_note/has_type
```

It resolves to **P2, with the grandparent as subject**. Read literally, AMOL
asserts that a silk textile *has type "Statement"* and *has type "Marks"*. My first
draft, which copied the idiom, asserted that the Mao Gong ding has type "Absence of
evidence" twenty-one times over.

I confirmed the format cannot express P3.1 at all: giving the note an explicit
`<in_class>E62: String</in_class>` so that the `has_type` would attach to the note
produces

```
NOT_A_CLASS_LINK has_type — E22 -> E12 — its domain is the property P3, not a class
```

So there is no correct spelling. I removed all 21 nested `has_type`s and folded the
category into the note text as a leading word (`Absence of evidence. …`,
`Modelling note. …`, `Scope decision. …`). This is the one place where I broke a
convention both examples share; a false triple seemed worse than a lost affordance.
This is the same class of problem as the `AMBIGUOUS` verdict — a shared label the
element name cannot disambiguate — except that here the validator picks one reading
silently instead of reporting the tie.

---

## 3. The `validate --xml` output

```
$ uv run python search.py validate --xml crm_mao_gong.xml
247 links checked: 195 ok, 52 ok_literal
structural elements skipped: CRM_Entity in_class unit value

Every link resolves to a real property and stays inside its declared domain and
range, and every class is named as the model names it.
```

No `unknown_name`, no `illegal`, no `ambiguous`, no `label_mismatch`,
no `not_a_class_link`. **There is nothing to account for.**

Because a clean report is also what an unread file produces, I mutation-tested the
checker against this document before trusting it:

- injecting `<bogus_prop>` deep inside a note → `UNKNOWN_NAME` at
  `.../has_note/has_type/bogus_prop`, so it does descend into note subtrees;
- injecting `transferred_title_to` on an E31 Document in the last block of the file
  → `ILLEGAL — E31 is not a E8`, so it does reach the end.

The 52 `ok_literal` links are the `has_note`s (P3) and the two
`beginning_is_qualified_by` / `end_is_qualified_by` strings (P79/P80), all of which
have E62 String ranges and so carry no `in_class`.

---

## 4. The choices that were actually hard

### 4.1 No identifier

Both examples are built around an assigned code — an AMOL object ID, a Clayton
barcode — and Clayton distinguishes a current from a superseded one. The article
gives this object no accession number, inventory number or catalogue code at all.
So there is no E42 Identifier and no P48 in this file: only E41 Appellations for
the five names the article does give (*Mao Gong ding*, 毛公鼎 with *Máogōng dǐng*
as a P139 alternative form, the gloss *Lord Mao's cauldron*, and *the Duke Mao
Tripod* from the World Digital Library citation). Recorded in the file as an
absence, since the reflex is to invent one.

### 4.2 Dating: three grains, no dispute

The article dates the vessel three times and never reconciles the three: the
infobox says `c. 805 BCE`; the lead says *Western Zhou dynasty (c. 1045–771 BCE)*;
the lead also says it *dates from the reign of King Xuan of Zhou*. It gives King
Xuan no regnal dates.

Nothing here is *contested* — no source is reported as disagreeing with another —
so I did not reach for E13 Attribute Assignment or for rival E17 Type Assignments,
which is Clayton's device for exactly that (three dated determinations by different
botanists on one sheet). What this is instead is a single claim held at three
resolutions, so the model nests them:

```
E12 Production
 ├ P4  has time-span → E52 "date of production"
 │      ├ P82 at some time within → E61 "805 BCE"
 │      ├ P79 beginning is qualified by "circa"     (both are P3 subproperties,
 │      ├ P80 end is qualified by "circa"            scoped for exactly this)
 │      └ P86 falls within → E52 "time-span of the Western Zhou dynasty"
 └ P10 falls within → E4 "the reign of King Xuan of Zhou"
```

`falls_within` is a label shared by P10 (E92→E92), P86 (E52→E52) and P89 (E53→E53).
Domain and range settle it in every one of the thirteen uses in this file, and the
validator reported no ambiguity, but it is worth stating that E52→E52 is meant as
P86, E53→E53 as P89 (place nesting: Qishan County ⊂ Shaanxi ⊂ China; the museum ⊂
Taipei ⊂ Taiwan), and event→E4 Period as P10.

The same nesting handles the undated transfers: the sale to Chen Yon Ren is placed
inside `the Second Sino-Japanese War` with P10 and given no numeric span of its own,
because the article supplies no dates for the war. I did not fill them in from
elsewhere.

### 4.3 The 1843 find

Modelled as **S19 Encounter Event** (CRMsci) with **O19i was object encountered
through** and **O21 encountered at** → Qishan County. S19's scope note is written
for this case: an actor encounters a physical thing, "this knowledge may be new to
the group of people the actor belongs to. In that case, we would talk about
discovery," and it explicitly anticipates archaeology recording the absolute
position and time of the observation. The CRMbase alternative — an E7 Activity
typed "excavation" with P12 occurred in the presence of — says less and asserts
more.

Two things I deliberately did not do:

- **No CRMarchaeo.** A9 Archaeological Excavation, A7 Embedding and AP17 is found
  by all presuppose a recorded excavation with stratigraphic context. The article
  offers one sentence and no context whatever.
- **P14 carried out by is left unfilled**, even though `concept S19` lists it among
  the properties the CRM quantifies as *necessary* on S19 (inherited from S27
  Observation), alongside P12 and P7. The article uses the passive and names
  nobody. The quantification is a claim about the world, not a demand on the
  record, so an instance without it is still valid — but the gap is real and is
  recorded in the file.

### 4.4 Deposition: modelled as nothing

Required topic 4 is "burial, excavation, findspot". The article has the excavation
and a county-level findspot; of the burial it says **nothing** — not that the
object was buried, not when, not by whom, not in what. So there is no E9 Move into
the ground, no S17 Physical Genesis, no A4 Stratigraphic Genesis. Roughly 2,650
years between the casting and 1843 are blank in the source, and the file says so
rather than leaving a reader to wonder whether I forgot.

### 4.5 Ownership: seven transfers, one right, one move

Every transfer the article records, in order, each as its own event:

1. **E8 Acquisition**, type *gift* — Lord Yin of Mao → King Xuan of Zhou, within the
   reign, `was_motivated_by` (P17) the appointment "to help run state affairs".
2. **E8 Acquisition**, 1852 — → Chen Jieqi. E8 and not E96 Purchase: E96's scope
   note requires that "the transferring party is completely compensated by the
   payment of a monetary amount", and the article says only "acquired". No seller
   is named, so P23 is empty.
3. **E96 Purchase**, Xuantong era — the Chen family → Duanfang. "Bought", so E96;
   no price, so no P179; the date is an era, so P82 spans 1909/1911.
4. **E30 Right**, type *mortgage*, held by the Tianjin Dao Sheng Bank.
5. **E96 Purchase** — the bank → Ye Gongchuo's friends (one unnamed E74 Group,
   since the article treats them collectively and as plural).
6. **E8 Acquisition**, type *gift* — those friends → Ye Gongchuo.
7. **E96 Purchase**, during the war — the Ye family → Chen Yon Ren.
8. **E8 Acquisition**, type *donation*, April 1946 — Chen Yon Ren → the Kuomintang
   Shanghai Government, with the unnamed general as **P11 had participant**. He is
   an intermediary the transfer went "through", not its performer, so not P14.
9. **E9 Move**, 1949 — P26 moved to Taiwan, P14 Chiang Kai-shek and the Kuomintang.
   No P27, because the article gives no origin. Location only: no title changed in
   1949.

Three decisions inside that chain:

**The mortgage.** P105 right held by is declared by the CRM as "a shortcut of the
fully developed path from E72 Legal Object, P104 is subject to, E30 Right, P75i is
possessed by to E39 Actor". I wrote the full path and did **not** also assert the
shortcut. Same reasoning for P51 has former or current owner, which `concept P51`
describes as a shortcut through E8 Acquisition: since every acquisition is present
in full, adding P51 would state each owner twice by two routes, one of them lossy.
The examples do not face this choice — Clayton has no E30 at all.

**The bank's hold is a right, not an event.** The article says the bank "had it as
a mortgage" and that friends "bought the tripod from" it. How it got there after
Duanfang's death in 1911, and whether the bank ever held title or only physical
possession, is simply not stated. So: an E30 Right, and no E10 Transfer of Custody
into the bank.

**No current owner.** Title last moved in April 1946 to the Kuomintang Shanghai
Government. The article then says only that the object is "housed at" and
"currently located at" the National Palace Museum. Housing is custody, not title,
so the museum gets **P50 has current keeper** and **P55 has current location** and
the file records that no present owner can be stated. Note that the museum also
gets no E10: the article describes no accession, deposit or loan event.

### 4.6 The inscription, and where it sits

The article's headline fact — the longest known inscription on any Chinese bronze —
needed three distinct things kept apart:

- **the text**: E34 Inscription, carried by the ding (P128). `concept E34` is
  explicit that the class is "the underlying prototype", not "the idiosyncratic
  characteristics of an individual physical embodiment".
- **the physical marks**: `bears_feature` (P56) → **TX1 Written Text** (CRMtex), a
  subclass of E25 Human-Made Feature, which in turn `carries` the same E34.
- **the area they occupy**: `has_section` (P59) → E53 Place "the interior surface
  of the Mao Gong ding". P59's scope note is written for named areas of an object
  ("the poop deck of H.M.S. Victory"), which is exactly the article's "the interior
  surface of the ding".

Keeping the text separate from its embodiment is what lets Chen Jieqi's 1852
rubbings carry the *same* instance of E34 as the vessel does — the one place in
this model where two physical objects meet.

The inscription's content is given as a `has_note` holding the museum summary the
article quotes, plus **P67 refers to** links for everything that summary names:
King Xuan, King Wen, King Wu, the Duke of Mao, the Mandate of Heaven (E28
Conceptual Object), the King Xuan restoration and the Gonghe interregnum (E4
Periods), and the bestowal of gifts (E7 Activity, carried out by King Xuan, with
nothing else said about it because the article says nothing else).

**P72 has language is left unfilled** although `concept E34` lists it as necessary:
the article never states the language, and "Chinese bronze inscription" is a
corpus, not a language. No P190 has symbolic content either — the article gives no
transcription. Both absences are in the file.

### 4.7 Depiction and condition: modelled as nothing

Required topics 3 and 6 come out empty and are recorded as empty:

- **No decoration, no depiction.** The article describes no ornament, motif or
  relief. Nothing in it supports P62 depicts or P65 shows visual item. Everything
  it says about the surface is text, which belongs to P128 carries, not to P65 —
  and the E34/E36 boundary is precisely where an over-eager model would put a
  *taotie* mask that the source never mentions.
- **No condition.** No damage, corrosion, loss or conservation assessment: no E3
  Condition State, no P44.
- **No restoration, repair or alteration**, and so none later reversed or
  superseded: no E11 Modification, E79, E80, E81. The only intervention reported —
  the 1852 rubbings — leaves the object unchanged, and is modelled as **P16i was
  used for** an E12 Production of the rubbings, not as a modification of the ding.

### 4.8 Sources

The article marks nothing as contested, so required topic 7 resolves to: attach
each cited reference to the thing it is cited for. Following AMOL's
`is_documented_in`, P70i hangs on the specific node — the 1961 catalogue on the
height and width dimensions and on the production; Tan 1986 on the weight, the
sale, the donation and the move; the museum's *Bell and Cauldron* page on the
inscription, the production and the gift to King Xuan. Each source is also a
top-level `<CRM_Entity>` of class E31 Document, with what the article says about it
(author, date, type), Tan Danjiong's article getting a P94i was created by → E65
Creation. Both article images are E31 Documents too, as AMOL treats its `.jpg`
filenames.

### 4.9 What I left out on purpose

The brief's exclusions bite in three places, all recorded in the file:

- the "three treasures" standing alongside the *Jadeite Cabbage* and the
  *Meat-Shaped Stone* — reception — and with it the article's reference 倪再沁,
  神畫的形塑—論故宮三寶 (2007), which is cited for that claim and nothing else. It is
  the only one of the article's seven references that appears nowhere in the model;
- the See also links and the link to the retreat of the ROC government to Taiwan;
- Shanghai as the place of the sale to Chen Yon Ren is an **inference** — the
  article locates the buyer there, not the transaction. I kept the P7 and flagged
  it in the note rather than dropping a fact or hiding a guess.

The one inclusion that runs against an exclusion is Chen Jieqi's rubbings, which
are arguably reproductions. They are in because they are one of the article's cited
sources and because they evidence Chen Jieqi's custody. Two nodes, and the reason
is in the file.

---

## 5. Where the CRM, or this format, does not cover it well

1. **Counting glyphs.** "500 characters arranged in 32 lines" is modelled as two
   E54 Dimensions with E58 units *character* and *line*. E58's scope note asks for
   "Système International (SI) units or internationally recognized non-SI terms"
   and preserves "archaic measurement units used in historical records"; a glyph
   count is neither. P57 has number of parts would be right in spirit but its
   domain is E19 Physical Object, and the count belongs to the E34 text. CRMtex has
   TX8 Grapheme, TX11 Grapheme Occurrence and TX12 Grapheme Sequence but no
   cardinality property. E54 with a stretched unit is the least bad option.
2. **E54's own warning.** Its scope note says "simple terms such as 'diameter' or
   'length' are normally insufficient to unambiguously describe a respective
   dimension. In contrast, 'maximum linear extent' may be sufficient." The article
   gives bare "53.8 cm high, 47.9 cm wide". I kept its terms as the P2 types rather
   than upgrading them to something the source does not support, and no E16
   Measurement is asserted because no measurer, method or date is recorded.
3. **A reign has no ruler.** `connect E4 E39` returns only `L54 is same as`. There
   is no property joining an E4 Period to the actor whose reign it is. Three of the
   five periods in this file are reigns or eras (King Xuan, Daoguang, Xuantong) and
   in none of them can the ruler be attached, short of recasting the reign as an
   E7 Activity that he carried out — a different claim, and not the one the article
   makes, since it uses all three purely as date brackets. Recorded in the file on
   `the reign of King Xuan of Zhou`.
4. **P3.1 is unwritable in this format.** §2 above.
5. **Absence is not expressible.** Thirteen of the notes in this file say what the
   article does *not* record. None of that is machine-readable: the CRM's own SIG
   has an open thread on modelling negative information (`thread t1281`, listed by
   `concept E22` as unresolved), and CRMinf's belief apparatus is about propositions
   held, not propositions missing. Prose in `has_note` is the only option, and it
   means the difference between "the article records no restoration" and "nobody
   has checked" is invisible to a consumer of the XML.
6. **P74 for an institution's seat.** The National Palace Museum's building is
   attached with P74 has current or former residence. P74's domain is E39, which
   includes E74 Group, so this is legal, but "residence" for a museum is a stretch
   the scope note does not illustrate.

---

## 6. On the tool

The search system carried the whole job. Two things did most of the work:

- `ontology --model CRMbase` printing every identifier with **both directions of
  every property label** on one line each. In this format the element name *is* the
  label, so that listing is the serialisation dictionary; nothing else would have
  given me `changed_ownership_through` or `has_time-span` reliably, and recall
  would have reproduced Clayton's three broken names.
- `validate --xml` run **on the two published examples first**. That is what turned
  "study the examples" into a list of five specific defects to avoid, before I had
  written a line.

One gap worth naming: nothing in the tool warns that a *legal* link may still be a
*false* one. The nested-`has_type`-in-`has_note` problem passes validation as `ok`
and is only visible if you read the `--json` paths and notice the subject is the
grandparent. A checker for this format could reasonably flag any `has_type` whose
parent element carries no `in_class`.
