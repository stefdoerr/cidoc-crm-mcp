# The Bianzhong of Marquis Yi of Zeng — modelling report

Turtle file: `v2_marquisyi.ttl` (same directory).

## 1. Argumentation

### The object itself: E22 Human-Made Object, not E78 Curated Holding

The article's own subject is a single named thing — "the name given to an
ancient musical instrument made of bells... unearthed in 1978" — that turns
out, on inspection, to bundle three physically separate kinds of item
(bells, two racks, hammers). `crm_concept E22` settled this: E22's scope
note reads "The class also includes all aggregates of objects made for
functional purposes of whatever kind, independent of physical coherence,
**such as a set of chessmen**." That is exactly this case, and it is a
directly-quoted example, not an inference on my part. I rejected E78 Curated
Holding (the modern name for what used to be called E78 Collection): its
scope note requires the aggregate to be "assembled and maintained... by one
or more Actors over time for a specific purpose and audience, according to a
particular collection development plan" — a museological curatorial act.
The bianzhong were assembled once, by their maker, as an instrument; nobody
"curated" them into being. E78 would misdescribe the object's own history to
get a class that sounds appropriately plural.

### Two tiers, not one: `ex:instrument` vs `ex:bellSet`

The article uses "Bianzhong of Marquis Yi of Zeng" for the whole find and
plain "bianzhong" (lower-case, plural) for the 64 bells specifically, and it
dates only the latter: "The bianzhong were made in 433 B.C." never extends
that date, in the text, to the racks or the hammers — those get their own,
separate, undated sentences. I therefore split the model into `ex:instrument`
(E22, the named whole: bells + racks + hammers, P46-composed) and
`ex:bellSet` (E22, just the 64 bells, itself P46-composed into
`ex:instrument`), and scoped the E12 Production event's `P108_has_produced`
to `ex:bellSet` only. This is a real interpretive fork — a reviewer could
reasonably read "the bianzhong were made in 433 BC" as loosely covering the
whole ensemble — but the narrower reading is what the sentence boundaries
actually support, and I did not want to silently backdate the racks.

### Racks and hammers as `P46`-composed parts, not separate finds

Same E22 aggregate logic as above: the racks and the wooden hammers are
functionally part of the playable instrument even though nothing says they
were made at the same time or place as the bells. I linked them via
`P46_is_composed_of` rather than, say, only a co-discovery relation, because
the "independent of physical/temporal coherence" aggregate reading in E22's
scope note licenses exactly this.

### Levels reified as sub-aggregates; groups left as notes — an asymmetric, flagged choice

The article gives per-level bell counts (19/33/12) and per-level group counts
(3/3/2) with total 8 groups. I reified the three **levels** as their own
E22 individuals (`ex:topLevel` etc., each P46-composed into `ex:bellSet`,
each carrying `P57_has_number_of_parts`) so the counts are queryable
structured data, not prose. I did **not** reify the **groups**: the article
never says what physically distinguishes a "group" (adjacent bells? a tuning
cluster?), so instantiating eight group-objects would assert a boundary the
source doesn't actually draw. Group counts are recorded only as
`P3_has_note` text on each level. This is a judgement call I'm not fully
settled on — an equally defensible alternative is to drop level-reification
too and put everything in one note — but reifying only the coarser,
better-evidenced tier struck me as the more honest middle ground.

The two individually-measured extremes (`ex:bell_biggest`, `ex:bell_smallest`)
are attached directly to `ex:bellSet`, not nested inside a specific level,
because the article never says which level holds the biggest or smallest
bell. Nesting them would have been a guess.

### Material: deliberately absent for the bells — the biggest hedge in this model

The brief's own framing sentence calls the object "a set of bronze bells,"
and it is common knowledge that bianzhong are bronze. **The cached article
text never uses the word "bronze," or names any metal, anywhere.** Per the
brief's instruction not to invent materials the page doesn't state, I did
not assert `P45_consists_of` for the bells, `ex:bellSet`, the levels, or
`ex:instrument` — and I was careful not to smuggle "bronze" back in through
a type label either. Wood, by contrast, is asserted for the racks and the
hammers, because the article says "wooden racks" and "wooden hammers"
explicitly. The completeness pass confirms this split cleanly (8 of 11 E22
individuals lack `P45`, and they are exactly the bell-related ones) — this
is the one place in the report where I want a reviewer to notice that the
model is *less* complete than general knowledge would allow, on purpose.

### Finding the bells: S19 Encounter Event, not a bespoke Discovery class or E8/E10

The unearthing needed a class, and CRM's history here is genuinely
interesting. `crm_search` turned up a 2013 SIG thread (`t0689`,
"ISSUE: add Activity subclass Discovery (Finding)") in which Vladimir
Alexiev proposed a dedicated `Discovery`/`Finding` subclass of E7 Activity,
specifically for archaeological find events lacking production data.
Stephen Stead's reply set the bar: "we do/try not to add classes to the
model unless it forms an anchor for some properties or is structurally
necessary" — and no such class was adopted. Instead, per a 2014 message from
Wolfgang Schmidle surfaced in the same search ("I see that the Find event in
archaeology has found a new home... in the form of S19 Encounter Event"),
and confirmed by a 2020 thread where Robert Sanderson reports Linked Art
settling on "S19 and O19... as the correct modeling constructs" for find
events, the 1978 unearthing is modelled as `crmsci:S19_Encounter_Event`,
with `O19_encountered_object` → `ex:instrument` and `O21_encountered_at` →
the tomb. I used the CRMsci-specific `O19`/`O21` properties rather than the
generic `P12_occurred_in_the_presence_of` / `P7_took_place_at` because they
are the properties actually built for this case (confirmed present and
legal on S19 via `crm_concept S19`). I rejected E8 Acquisition or
E10 Transfer of Custody for this same moment: the article names no party
who took title or custody in 1978 — only that the bells "were unearthed" —
so there is no acquisition/transfer to reify, only an encounter with a
pre-existing thing.

### No actor, anywhere — a genuine gap, not a choice

Neither the production (`ex:production`) nor the encounter (`ex:encounter`)
carries `P14_carried_out_by`. The article names no maker, no commissioner,
and no excavator. I left both empty rather than inventing a placeholder
actor. The completeness run flags `P14` as "never stated" across both
instances; that's correct, and it isn't fixable from this source.

### Marquis Yi of Zeng himself is never instantiated

Both the tomb's name and the instrument's name embed "Marquis Yi of Zeng,"
which invites the assumption that he commissioned, owned, or was buried
with the bells. The article never actually says any of that — only that the
tomb bears his name and the bells were found in it. I kept his name purely
inside the two `E41_Appellation` literal strings and did **not** create an
`E21_Person` for him, precisely to avoid the appearance of an asserted
production/ownership link that the text doesn't make. A reviewer who knows
the real archaeology may find this too cautious; I'd rather be told that
than have invented the link.

### Custody and location: `P50`/`P54`, not a reified transfer event

Nothing in the article describes a specific transfer of custody from
excavators to the museum — only "unearthed in 1978" and "on permanent
display at the Hubei Provincial Museum" now. So I used state-properties
(`P50_has_current_keeper`, `P54_has_current_permanent_location`) rather than
inventing an E10 Transfer of Custody with unknown parties and an unknown
date. I chose `P54` over the more general `P55_has_current_location`
specifically because `crm_concept P54`'s scope note gives a fictitious
example ("Silver cup 232 (E22) has current permanent location Shelf 3.1,
Store 2, Museum of Oxford (E53)") that is a near-exact structural match for
"on permanent display" — P54 is built for exactly this reading, where P55 is
the weaker, temporary-location property. The museum is modelled as
`E74_Group`, not `E40_Legal_Body`: E40 doesn't appear anywhere in the
current `crm_list CRMbase` output, and the deprecated-class table surfaced
by `crm_concept E22` states outright "E40 Legal Body → use E74 Group."

### Dates: `P81`/`P82` with plain-text values, and one date left less formal on purpose

Both 433 BC and 1978 are stated as flat, unhedged facts — the article has no
"circa," "probably," or "attributed to" anywhere, so there was no hedge to
preserve here (see below). Initially I gave both time-spans only an
`rdfs:label`; the completeness pass correctly flagged that CRM's own
temporal-extent properties (`P81_ongoing_throughout`,
`P82_at_some_time_within`) were unused. I fixed this — but differently for
the two dates. `crm_concept P81`'s scope note gives an official worked
example using a plain string, not a typed date: *"The time-span of the
First Intermediate Period of Ancient Egypt... ongoing throughout '2181 BC –
2160 BC' (E61)."* That licensed using plain literal strings rather than
`xsd:date`. For 1978 this is low-risk. For 433 BC I stayed with a plain
string ("433 BC") rather than converting to ISO-8601's astronomical year
numbering (`-0432`, not `-0433` — the year-zero convention makes BC-to-ISO
conversion an easy off-by-one mistake) specifically to avoid asserting a
falsely-precise, possibly-wrong numeric value. I'd rather the model be
visibly informal here than silently wrong.

### Tonal range: a note, not a Dimension

"Tonal range from C2 to D7" and "all twelve half tones" sound like they
belong under `E54_Dimension` with `P90a_has_lower_value_limit` /
`P90b_has_upper_value_limit`. I rejected this: `crm_concept E60`'s own scope
note draws exactly the distinction that sinks it — "Identifiers in continua
... are instances of E41 Appellation, such as Gregorian dates or spatial
coordinates" and are explicitly **not** E60 Numbers, even though their
encoding may look similar. Scientific pitch notation ("C2", "D7") is
structurally that same kind of identifier-in-a-continuum, not a computable
number, and the article gives no Hz value to convert it into one. I
recorded the tonal-range facts as `P3_has_note` free text on `ex:bellSet`
instead of forcing them into machinery they don't fit.

### Suizhou / "then Sui County": the one real hedge in the source, and how it's carried

The only place-name uncertainty in the article is administrative, not
temporal: "Suizhou (then 'Sui County')." I modelled two `E41_Appellation`
instances on the one `ex:suizhou` Place, linked by
`P139_has_alternative_form`, with a note on "Sui County" recording that it
was the name in use in 1978. This is the only hedge the source actually
contains — I looked for "attributed to" / "probably" language elsewhere and
found none; the rest of the article states everything (dates, counts,
dimensions) as flat fact, so there was nothing else to carry as a hedge.

### Replicas: bare minimum, on purpose

"Copies have been made for other museums" names no museum, no date, no
count. I added one `E22` node linked by `P130_shows_features_of` (its scope
note: "generalises the notions of 'copy of'...") and nothing else —
deliberately resisting the temptation to give it a label implying more
detail than the source has.

### Place hierarchy and a shared node

I built the full `P89_falls_within` chain the article gives — tomb →
Leigudun Community → Nanjiao Subdistrict → Zengdu District → Suizhou →
Hubei Province → China — because every link is explicitly named, not
inferred. Wuhan (city) and the museum's site both fall within the same
`ex:hubei` node used by the find-spot branch, rather than a second,
disconnected "Hubei" — both branches describe the same real province, and
duplicating it would misrepresent that.

### Naming: `P1`/`E41` over `P102`/`E35` for the instrument's name

The article's own phrase is "the name given to," which reads as a
conventional/scholarly name rather than an authored title, so I used the
general `P1_is_identified_by`/`E41_Appellation` route rather than
`P102_has_title`/`E35_Title`. Both are legal; this is a minor fork, included
because it was a real (if low-stakes) choice.

## 2. The tools

**Final validator result:** `Verdict: PASSED -- every link resolves within
its declared domain and range, every rdf:type is a class this model
declares, and every owl:inverseOf claim holds` (both the plain pass and the
`completeness: true` pass, run twice each — once before and once after
adding `P81`/`P82` to the two time-spans).

**MCP calls: 17**, no retries needed, nothing failed.
`--list` (1); `crm_list` for CRMbase/CRMarchaeo/CRMsci (3, for exact RDF
spellings and to see what family extensions exist); `crm_concept` for E22,
S19, E60, P54, P81, P82 (6, scope notes for the load-bearing class/property
decisions above); `crm_search` once (the Discovery-class question);
`crm_thread` once (reading `t0689` in full); `crm_docs` once ("musical
instrument," confirming CRM has no domain-specific instrument class);
`crm_validate_rdf` four times (plain + completeness, before and after the
P81/P82 fix).

**Wanted to ask and couldn't:** whether `P54` is formally a sub-property of
`P53`, and `O21`/`O19` of `P7`/`P12`. The completeness checker flags `P53`,
`P7`, and `P12` as "never stated" even though I used what I judged to be
their more specific children (`P54`, `O21`) — I believe this is because the
checker isn't doing subproperty closure, not because my modelling is
incomplete, but there's no tool here that answers "is X a subproperty of
Y" directly; `crm_connect` finds legal joins between two classes, not
subsumption between two properties. I inferred the relationship from scope
notes and sibling context instead, which is a weaker basis than I'd like.

**Rough edges:** `crm_search` prints an "unauthenticated HuggingFace Hub"
warning to stderr on every call and has a few seconds of model-load latency
— harmless but noisy. `crm_validate_rdf`'s output lists every `rdfs:label`
triple as a `NOT_CRM` line before the verdict; correct, but on a
40-triple-label model that's 40+ lines of boilerplate to scroll past to
reach the one line that matters — a `--quiet`/summary-only flag would help.
Otherwise the tools did what their one-line descriptions said they would.
