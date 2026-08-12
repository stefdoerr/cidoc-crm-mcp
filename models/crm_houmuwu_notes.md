# Houmuwu ding — CIDOC CRM encoding: rationale

Model: `crm_houmuwu.xml`
Subject: <https://en.wikipedia.org/wiki/Houmuwu_ding>
Format references: `crm_amol_1.xml`, `crm_clayton1.xml` (old.cidoc-crm.org)
Everything asserted here about the CRM was obtained through `search.py`.

---

## 1. Conventions taken from the two examples

Both examples share one form, and I kept it:

- Root `<CRMset>`; each record a `<CRM_Entity>` whose **leading text is the
  instance's identity**; a `<in_class>Exx: Class Name</in_class>` child declares
  its class.
- **Properties are elements whose name is the CRM property label with spaces
  replaced by underscores**, either direction (`is_identified_by`,
  `was_classified_by`). Nesting means *parent — property → child*.
- A child with no `<in_class>` is a literal; both examples rely on this for
  `has_note`.
- Typed notes use amol's idiom: free text in `has_note` with a nested
  `has_type` naming the kind of note.
- **Instances co-refer by their label text.** clayton already depends on this —
  the actor `Clayton` and the document `Flora Virginica` recur in 25 records —
  so it is the examples' rule, not one I invented.

### Where the two examples disagree, and what I picked

| Point | amol | clayton | Taken |
|---|---|---|---|
| Grain | one flat `E22` per object; no events at all, everything in typed notes ("Made", "Used", "OwnedExchange" are *note types*, not events) | event-centred: `E8 Acquisition`, `E17 Type Assignment`, with actors, places, time-spans | **clayton.** amol's approach cannot express *who* determined *what* *when*, which is the whole subject here. Where the article gives only prose with no agent, I fall back to amol's typed note. |
| Dimensions | `E54 Dimension` + `has_type` + bare `<value>`/`<unit>` | none | **amol's structure**, with the real property labels (below). |
| Identifiers | `is_identified_by` → `E42` only | adds `preferred_identifier_is` and a type on the identifier | **clayton's two-tier idea**, with the correct label (below). |
| Class-label style | invented E55 sub-labels (`E55: Object Type`, `E55: Dimension Type`) | same, plus malformed `E:55 Type` | **Neither.** I write `E55: Type` and express the kind-of-type with a nested `has_type`, which is what clayton itself does one level down. The validator confirms every class in my file "is named as the model names it". |
| Encoding | ISO-8859-1 | ISO-8859-1 | **UTF-8** — unavoidable, the subject is Chinese. |
| Top-level records | only objects | only objects | **Also events, actors, places, documents.** Nothing in the format forbids it, and a single 900-line nest would be unreadable. |

## 2. Where an example is wrong

I ran the validator on both published examples first, to learn the format from
the tool rather than by assumption.

```
$ validate --xml amol.xml
637 links checked: 426 ok, 211 ok_literal
Every link resolves to a real property and stays inside its declared domain and range.

$ validate --xml clayton.xml
656 links checked: 25 illegal, 420 ok, 120 ok_literal, 91 unknown_name
```

**amol is clean. clayton is not**, and this is exactly the trap the brief warns
about. Its four faults, and what I did:

1. `at_most_within` (41×) — **`unknown_name`; not a CRM property label at all.**
   Used from `E8`/`E17` to `E52 Time-Span`. The property it is reaching for is
   **P4 has time-span**; the "at most" sense belongs one level lower, on the
   time-span, as **P82 at some time within** (`E52 → E61 Time Primitive`).
   I use `has_time-span` + `at_some_time_within`, and `beginning_is_qualified_by`
   (P79) where the article qualifies a boundary in words ("after the death of
   Fu Jing"). **Copying `at_most_within` is the specific mistake the required
   check exists to catch.**
2. `preferred_identifier_is` (25×) — **`unknown_name`.** The property is
   **P48 has preferred identifier**; the label is `has preferred identifier`.
   I use `has_preferred_identifier`.
3. `changed_ownership_by` (25×) — **`unknown_name`.** P24's inverse is
   *changed ownership **through***, not *by*. Moot for this object: it records
   no acquisition (§5).
4. `took_place_at` nested under `transferred_title_to` (25×) — **`illegal`,
   `E39 is not a E4`.** A nesting slip: the place belongs to the acquisition,
   not to the actor who received title. I keep P7 on events only.

One more thing amol does that is not wrong but is not standard either: bare
`<value>` and `<unit>` inside `E54 Dimension`. The validator *skips* these as
structural rather than flagging them, so copying them would have passed. They
are not property labels; the properties are **P90 has value** (→ E60 Number)
and **P91 has unit** (→ E58 Measurement Unit). I write `has_value` and
`has_unit`, which validate as a real literal link and a real typed link
respectively. Deviation from amol, deliberate, per the brief's "follow the
standard, not the example".

## 3. The naming — the hard part of this object

The article reports a name that changed and a reading that is still argued
about. Three things are distinct and are modelled separately:

**(a) The physical text.** `TX1 Written Text` (CRMtex) — three characters in
bronzeware script on the interior wall, attached with **P56 bears feature**
(`E19 → E26`; `TX1 < E25 < E26`). I assert **no `P190 has symbolic content`
on it**: every transcription in the article is somebody's reading, and writing
one into the text itself would settle the dispute by fiat.

**(b) The readings.** Six `TX14 Reading` events (`TX14 < I1 Argumentation`),
each `read` (TXP18) the same written text, each with its reader and date where
the article names one, each `concluded_that` (J2) an `I2 Belief` that (J4) an
`I17 One-Proposition Set` carrying the proposition, `holds_to_be` (J5) true.
This is the CRMinf apparatus for exactly this situation, and it is what
Modelling Principle **6.2 "Allow alternatives or contradictions in the data"**
and **6.3 "Make sure alternative assertions can be unambiguously related to a
single entity"** ask for: all six beliefs hang off one written text, so a reader
finds the contradiction in one place instead of finding one winner.

The six: the unattributed original transcription 司母戊; the October 1946
"Queen Wu"/"Wife Wu"; Zhang Feng, November 1946, "Simu Wu"; Guo Moruo,
sī = "sacrifice"; Li Xueqin, 1977, first glyph = 后 hòu; Sun Ji, 后 as the
horizontal reflection of 司.

**(c) The namings of the vessel.** Three `E15 Identifier Assignment`s — Zhang
Feng 1946, Guo Moruo, and the National Museum of China in March 2011 — each
`assigned_attribute_to` the vessel, `assigned` a name, `assigned_property_of_type`
"P1 is identified by", and `was_motivated_by` the corresponding reading. Only
the 2011 act carries **`deassigned` (P38)** of 司母戊鼎, which is the one CRM
construct that says *superseded*, and it is the reason the vessel now has
`has_preferred_identifier` → 后母戊鼎.

Three checks decided the details:

- `concept E15` — its scope note is written for this case: *"Documenting the act
  of identifier assignment and deassignment is especially useful when objects
  change custody or the identification system of an organization is changed."*
- The same scope note: *"The syntax and kinds of constituents to be used may be
  declared in a rule constituting an instance of E29 Design or Procedure."* The
  article devotes a paragraph to precisely such a rule (last character = ware
  type; the owner-naming character from the inscription). So the naming
  convention is an `E29 Design or Procedure` and each naming event
  `used_specific_technique` (P33) it.
- The same scope note again: preferred status *"can better be expressed … by
  assigning a suitable E55 Type, such as 'preferred identifier assignment', to
  the respective instance of E15"*. The 2011 event carries that `has_type`, and
  P177 stays "P1 is identified by" for consistency with the other two.

### The judgement call I am least sure of: E41 vs E42

I made the three vessel names **`E42 Identifier`, not `E41 Appellation`.**
`concept E42` gives the class as *"strings or codes assigned to instances of
E1 CRM Entity in order to identify them uniquely and permanently within the
context of one or more organisations"*, and among its own examples is
*"Guillaume de Machaut (1300?-1377) [a controlled personal name heading that
follows the French rules]"* — i.e. a rule-formed name heading counts. These
names are rule-formed (the E29 above), are institutionally assigned, and one
was institutionally withdrawn. And P37/P38 have range **E42**: had I used E41,
`deassigned` would have been illegal and the supersession inexpressible without
a workaround.

The cost: a purist can say the common name of a famous object is an appellation,
not an identifier. Because `E42 < E41`, everything else still holds — P1, P139
`has_alternative_form`, and P48 all accept them. **A reviewer should look here
first.** The alternative I rejected was carrying both an E41 and an E42 per
name, which in a format where instances co-refer by label text would have put
two nodes with near-identical labels into the graph.

## 4. The other decisions worth defending

- **`S19 Encounter Event` (CRMsci) for the 1939 unearthing**, not `A9
  Archaeological Excavation` or `A1 Excavation Processing Unit` (CRMarchaeo) and
  not a bare `E7 Activity`. The article says only "unearthed in 1939 in Wuguan
  Village" — no excavator, no institution, no method, no stratigraphy. S19's
  scope note is written for the minimal case: *"an Actor encounters an instance
  of E18 Physical Thing … This knowledge may be new to the group of people the
  actor belongs to. In that case, we would talk about discovery."* Choosing A9
  would assert an archaeological excavation the article never describes.
  Same class, same reasoning, for the 1959 locating of tomb 260.
- **Tomb 260 is modelled but is *not* the findspot.** The article introduces it
  only to say that Fu Jing's tomb "was not located until 1959, and was found to
  have been looted", in explicit contrast with the 1939 find at Wuguan Village.
  Linking the vessel to the tomb would be the single most tempting invention
  here. There is a `has_type` "Scope note" on tomb 260 saying so in the file.
- **The looting is a state, not an event.** `E3 Condition State` typed "looted",
  per E3's own scope note pattern (*"the instance … 'condition of the SS Great
  Britain between …' can be characterized as an instance 'wrecked' of E55
  Type"*). The article describes no looting event and gives it no date.
- **Presumptive maker.** "presumably by her son, Zu Geng of Shang" is recorded
  as `P14 carried out by` with a typed `Attribution note` saying the attribution
  is presumptive. CRMbase has no uncertainty qualifier on P14; the honest
  options were assert-and-flag or omit-and-lose. CRMinf could wrap it in an
  `I2 Belief`, but the article attributes the presumption to no one, so there
  would be no believer to attach — the flag is the truthful form.
- **Relative dating.** The making is dated two ways that the article does not
  reconcile: "12th-century BC" in its own summary, and "after her death" in the
  body. Both are kept: `at_some_time_within 1200 BC/1101 BC`, plus
  `starts_after_or_with_the_end_of` (P182, inverse) the `E69 Death of Fu Jing`,
  plus `beginning_is_qualified_by` "after the death of Fu Jing". No date is
  invented for the death.
- **Parts are `E24 Physical Human-Made Thing`, not `E22`.** `concept E22`
  requires *"physical boundaries that separate them completely in an objective
  way from other objects"*; the legs and handles of a single casting have no
  such boundary. E24 is the nearest ancestor without that clause, and
  `P46 is composed of` takes `E18 → E18`.
- **Decoration via `P65 shows visual item` → `E36` → `P199 represents instance
  of type`**, not the `P62 depicts` shortcut. E36's scope note names P62 as *"a
  shortcut of the more fully developed path"* through P65/E36; the fuller path
  lets the two decorative schemes (the taotie/kuilong band on the sides, the
  tiger-and-human-head on the handles) sit on different carriers, which is what
  the article describes. P199 rather than P138 because taotie and kuilong are
  kinds, not individuals.
- **Chiang Kai-shek's 1948 inspection is included, and flagged.** It comes only
  from a photograph caption and is not a custody transfer. It is the only datum
  the article offers on the vessel between 1939 and the museum, so dropping it
  silently seemed worse than including it with an explicit scope note saying
  what it is not. A reviewer may reasonably call this over-inclusion.

## 5. Scope items with no basis in the article — modelled as nothing

Per the brief, and per Modelling Principle **6.1 "The absence of a property in
the knowledge base is not its negation in reality"**, these are recorded and
left empty. Each also carries a typed `Documentation gap` note in the XML so
the file itself is honest about them.

| Scope item | Status |
|---|---|
| 1 — condition | **Nothing.** The article states no condition, no conservation history, no damage. No `E3`, no `E14`. |
| 2 — place of making | **Nothing.** Anyang is where it was *found*. No `P7` on the production. |
| 2 — technique detail | Only "cast", and that from within a report of Guo Moruo's reading. No mould, workshop or piece-mould procedure. |
| 4 — deposition / burial | **Nothing.** No burial event, no tomb, no stratigraphy, no assemblage for *this vessel*. Only "unearthed". |
| 5 — ownership | **Nothing.** No acquisition, no title transfer, no purchase, no gift, no legal determination, at any date. **No `E8 Acquisition` in the file.** Custody is asserted only as far as the article goes: `P50 has current keeper` → National Museum of China. |
| 6 — reconstruction / restoration / alteration | **Nothing.** No physical alteration of any kind, current, reversed or superseded. What was superseded here is the *name*, modelled under §3. |
| 1 — inventory number | **Nothing.** The National Museum of China's accession number is not in the article. |
| 1 — language of the inscription | **Nothing.** The article names the *script* (bronzeware script, → `P2 has type`) but not the language; `P72 has language` is quantified as necessary on E34/TX1's ancestors and is nevertheless left out rather than guessed. |

Two things I saw and deliberately left out, so the decision is on the record:
the "List of Chinese cultural relics forbidden to be exhibited abroad" (a
See-also link and a category, not a prose assertion — it would have been an
`E30 Right` / `P104 is subject to`, and I judged the article does not assert
it); and the Duling *fangding*s and Fu Hao battle axes, which the brief excludes
as other objects and which survive as descriptive notes.

## 6. Where the article contradicts itself, and what the model does

- **Guo Moruo's date.** The Discovery section says "In 1959, Guo Moruo believed
  …"; the Epigraphic readings section says "After 1949, Guo Moruo, then
  president of the Chinese Academy of Sciences, interpreted …". The time-span is
  left as the interval both allow, `1949/1959`, with a `Source conflict` note.
  Not silently resolved to either.
- **Guo Moruo's actual claim.** The Discovery section's wording is corrupt as
  the article stands — *"Guo Moruo believed that 'Si' is the same as 'Si'"* —
  and cannot be transcribed as a proposition. The modelled proposition is taken
  from the coherent Epigraphic readings section; the corruption is noted.
- **Source quality.** The whole Discovery section rests on one Weixin post that
  the article itself tags dead-link and `WP:NOTRS`. Since the points it carries
  (Shao Shenzhi, Zhang Feng, the 1959 dating) are precisely the contested ones,
  that document is in the model with its standing recorded, rather than dropped
  or laundered.

Sources are `E31 Document`, not clayton's `E32 Authority Document`: `concept
E32` scopes that class to *"encyclopaedia, thesauri, authority lists"*, which
Li Song's monograph and the *Wenbo* article are not. They attach with
`P70 documents` / `is_documented_in` and `P67 refers to` / `is_referred_to_by`,
following clayton's placement of a page reference in a nested `has_note`.

## 7. Where the CRM (or this format) does not cover the case well

1. **No spouse.** The article's "queen and primary wife of Wu Ding" has no home
   in CRMbase. `P152 has parent` covers Fu Jing → Zu Geng; there is no
   equivalent for a marriage, and forcing it into `E85 Joining` or `P107 has
   current or former member` would misdescribe it. Recorded as a note on Fu Jing.
2. **No proximity between places.** "Wuguan Village … near Yinxu" has no
   property. `P89 falls within`, `P121 overlaps with`, `P122 borders with` and
   `P189 approximates` all mean something stronger or different. Recorded as a
   note; both are tied to Anyang instead.
3. **CRMtex declares `TX13 Script` but gives no property from `TX1 Written Text`
   to it.** `connect TX1 TX13` returns only `P130 shows features of`, `P62
   depicts` and `L54 is same as` — none of which means "is written in". I used
   `P2 has type` "bronzeware script (jinwen)" instead, which is what E34's scope
   note recommends for the alphabet, and left TX13 out of the file.
4. **No uncertainty qualifier on a plain property.** "presumably by her son" can
   only be asserted-and-annotated, promoted to an `E13`, or dropped. See §4.
5. **The examples' element-naming convention is genuinely ambiguous where CRM
   reuses a label — and the tool says so.** Three properties are labelled
   *assigned*: **P37** (E15→E42), **P42** (E17→E55) and **P141** (E13→E1).
   Because E15 and E17 are both subclasses of E13, and E42 and E55 are both
   subclasses of E1, two candidates are legal at each of my two uses:

   ```
   $ validate E15 assigned E42   ->  AMBIGUOUS: P37 and P141 are both legal here.
   $ validate E17 assigned E55   ->  AMBIGUOUS: P42 and P141 are both legal here.
                                     Name the identifier rather than the label.
   ```

   The tool's advice is exactly right and the format cannot take it: an element
   name in this XML form *is* a label, so there is nowhere to put the
   identifier. **Intent: P37 in the `E15` blocks, P42 in the `E17` block** —
   stated here because the file cannot state it. Two unresolvable links out of
   322 is the price of the examples' format; I judged that lower than the price
   of inventing a syntax the examples do not have.

   The same hazard is latent in *consists of* (P5/P9/P45), *is composed of*
   (P46/P106), *falls within* (P10/P86/P89) and *forms part of* (P9i/P46i/
   TXP17i). At my uses the endpoint classes settle them, and I checked each:
   `E22 consists_of E57 → P45`; `E22 is_composed_of E24 → P46`;
   `E12 forms_part_of E4 → P9i`; `E27 forms_part_of E27 → P46i`;
   `E53 falls_within E53 → P89`; `E22 was_attributed_by E15 → P140i`.
6. **`P3.1 has type` is unreachable as such.** A `has_type` nested inside a
   `has_note` — amol's idiom for typed notes, which I kept — is read by the
   validator as `P2` from the note's string, not as the property-of-property
   `P3.1`. Legal (E62 < E1), but not the same statement.

## 8. Required check — `validate --xml`, as written

```
$ uv run python search.py validate --xml crm_houmuwu.xml
322 links checked: 222 ok, 100 ok_literal
structural elements skipped: CRM_Entity in_class unit value

Every link resolves to a real property and stays inside its declared domain and range, and every class is named as the model names it.
```

**Findings: none.** No `illegal`, no `unknown_name`, nothing to account for.
The file is what was checked, not a transcription of it.

Note on the summary line: `structural elements skipped: … unit value` is the
validator listing names it will ignore in general, not a report that this file
uses them — it does not; §2 explains why `has_value`/`has_unit` replaced them.

Counts: **28 distinct CRM classes** and **52 distinct CRM properties**
(46 CRMbase, `O19`/`O21` CRMsci, `TXP18` CRMtex, `J2`/`J4`/`J5` CRMinf),
counting a property once whichever direction it is written in.

## 9. Notes on the search tool

- The workflow that made this tractable was `ontology --model <M>` (whole
  vocabulary, one line each, both directions) to choose candidates, `concept
  <id>` to read the scope note before committing, and `validate --xml` on a
  throwaway probe file to confirm that an element name resolves at all. Two
  probe rounds settled 60-odd element names before a line of the real model was
  written, including the fact that `has_time-span` — a property label with a
  hyphen in it — is accepted.
- **Running `validate --xml` on the two published examples first** was the
  highest-value thing the tool allowed. It located clayton's four faults in one
  command; reading the file would not have.
- **`validate --xml` reports pass/fail but never says which property identifier
  it resolved an element name to** — which for ambiguous labels (§7.5) is the
  one thing needed. The single-triple form fills the gap and fills it well:
  `validate E15 assigned E42` returns `AMBIGUOUS: P37 and P141 are both legal
  here. Name the identifier rather than the label.` That is a better answer than
  a silent pass. It would be worth surfacing the same warning from `--xml`,
  since a document check is where the ambiguity actually bites.
- **Not a tool gap, a shell trap worth recording:** the single-triple form takes
  three separate arguments. Passing them as one quoted string
  (`validate "E15 assigned E42"`) is rejected, and under `zsh` an unquoted
  `$var` holding the triple is *not* word-split, so a loop over triples silently
  hits the same rejection. I first concluded the feature was broken. It is not.
- **Gap:** `concept <id>` returns the v7.1.3 declaration plus a v7.3.2 FOL
  addendum, and its property lists give the forward label but not the inverse
  alongside — `ontology` does give both directions, so the two commands have to
  be used together to find out what an inverse element name should be called.
- **Gap:** nothing in the tool maps a class to the extension that best covers a
  case. Finding `S19 Encounter Event` and `TX14 Reading` meant listing whole
  models (`ontology --model CRMsci`, `--model CRMtex`) and reading. `connect`
  helped in the negative direction — `connect TX1 TX13` establishing that CRMtex
  has *no* property joining a written text to its script (§7.3) is a finding the
  tool produced cleanly.
