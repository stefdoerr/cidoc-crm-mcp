# Uffington White Horse — CIDOC CRM model: argumentation and tool notes

Turtle file: `v2_uffington.ttl` (same directory as this report).

## 1. Argumentation, for a CRM reviewer

### The class for the object itself: E25 Human-Made Feature, not E22 or E26

The obvious first instinct for "a museum object" is **E22 Human-Made Object**. I rejected
it. E22's own scope note requires "physical boundaries that separate [it] completely in
an objective way from other objects" — its examples are the Rosetta Stone, a locomotive,
a vase: things you could in principle pick up. The White Horse is trenches cut into the
hillside and filled with chalk; it has no boundary separating it from Whitehorse Hill, and
removing it would mean removing the hillside.

I asked the server directly whether this kind of thing is even debatable, and it turned up
a 2015 SIG thread (t0821) asking exactly this question about rock-cut structures: "should
we regard all the immobile buildings as E25 Man-made Feature?" Simon Spero's answer became
my test: "the salient feature of a man made feature is that it is formed by modification
of some physically existing thing, and cannot exist entirely separately from that
substrate." Martin Doerr sharpened it further in the same thread: the defining property is
that "removing implies destruction of material substance around it (cutting etc.)," citing
the Abu Simbel temple — carved out of solid rock — as the canonical E25 case. That is
exactly the White Horse's situation, and Abu Simbel is literally one of E25's own listed
examples in its scope note, alongside the Manchester Ship Canal (another large excavated
linear feature). A December 2025 thread (t1874) on E24's scope note reinforced the same
line: George Bruseker's summary — "if you need to talk about things that are movable you
hop down to E22, and if you are needing to make statements about things that are
features hop down to E25" — is precisely the fork I was resolving.

I also rejected **E26 Physical Feature** (the un-made superclass: scratches, holes,
natural boundaries) because the White Horse is *purposely created by human activity* —
E26's scope note covers naturally occurring or found features (a cave, damage to a
sphinx's nose) as well as made ones, and E25 is the strictly-more-specific class the CRM
provides for exactly the human-made case. There is no reason to back off to the parent
when the child fits and is better attested.

### Who made it, and when: nothing asserted as fact beyond the OSL date

The article gives a Late Bronze Age–Early Iron Age date (1380–550 BC) as **settled**
("finally settled") by 1990 optically-stimulated-luminescence (OSL) dating, and gives no
maker at all — only a string of superseded, mutually contradictory claims that predate
that dating. I asserted only the confirmed date directly on the E12 Production event
(`ex:Production crm:P4_has_time-span ex:ProductionTimeSpan`) and left `P14 carried out by`
absent from that event entirely. That absence is a genuine, and slightly uncomfortable,
modelling decision: a reviewer skimming the file might read a missing `P14` as an oversight
rather than a considered "no maker is known." I addressed that with a `P3 has_note` on the
Production event saying so explicitly, but flag it here too — this is the single point in
the file most likely to be misread as incomplete rather than as a faithful gap.

For the superseded claims, I used **E13 Attribute Assignment** uniformly, and specifically
its `P140`/`P141`/`P177` triple, because that pattern is designed for exactly this: "the
maintaining team is in general neutral to the validity of the respective assertion, but
registers someone else's opinion and how it came about" (E13's own scope note). `P177
assigned property of type` names *which* property is being hedged; I modelled it against
the CRM's own worked example almost verbatim ("Current Ownership Assessment... assigned
property of type P52 has former or current owner") — my Aubrey and Wise assignments target
the Production event with `P177 = crm:P14_carried_out_by`, and my Piggott assignment
targets it with `P177 = crm:P4_has_time-span`. I checked this pattern is current and not
about to be revised: a SIG vote closed 23 January 2026 (thread t1877, issue 615) tightened
E13's scope note but changed nothing about `P140`/`P141`/`P177` themselves, so the idiom is
safe to rely on.

I considered, and rejected, just attaching a probability or a free-text hedge to a direct
`P14` on the real Production event ("possibly Alfred the Great"). CRM has no native
uncertainty qualifier on a property assertion; bending `P14` to carry a maybe would blur
the one fact the source treats as settled (the OSL date) with several it does not. Keeping
the hedged claims in separate E13 nodes, each pointing at *who* made the claim and *when*,
is more work but is the only way to keep "settled" and "speculative" visibly distinct in
the graph.

I picked **three** representative hedged claims (Aubrey → Hengist and Horsa, 17th century;
Wise → Alfred the Great, undated; Piggott → circa 100 BC, 1931) and explicitly did not give
Ann Ross (1967) or Morris Marples (1949, Bronze Age) their own E13 nodes, noting this choice
inside Piggott's node. Marples in particular is a hard case to leave out — he guessed
Bronze Age in 1949, and the 1990 OSL dating vindicated him — but adding him would have been
a fourth near-identical assignment illustrating the same pattern, not a new kind of
decision, and the brief's own instruction is not to pad with decisions that only had one
reasonable shape once the pattern was set.

### The "17th century" and "summer 2024" — formalising vague dates as ranges

The article says only "in the 17th century" for Aubrey's claim. I formalised that as
1600-01-01 to 1699-12-31 via `P82a`/`P82b`, and said so directly in a note on that
time-span — this is the brief's own example of a defensible-but-not-literal move, done
deliberately. Symmetrically, I did **not** do this for the OSL-dated 1380–550 BC range: at
that scale, encoding "550 BC" as an exact ISO date forces a choice about astronomical vs.
historical year-numbering (year 0 exists in one convention and not the other, so "550 BC"
is off by one year depending which you pick) that manufactures a false extra digit of
precision the source does not carry. I left that range as a label and a note instead of a
literal. For "the summer of 2024" I mapped the begin bound to 2024-06-01 as a plausible
but not-stated reading, and left the end open because the article records no completion
date — I did not invent one.

### The 1990 dating: E16 Measurement, not a CRMarchaeo excavation class

The article's phrase is "following an excavation in 1990... Simon Palmer and David Miles
... dated silt deposits." CRMarchaeo's `A9 Archaeological Excavation` (from the
`http://www.cidoc-crm.org/extensions/crmarchaeo/` namespace, which I confirmed exists via
`crm_list`) looks tailor-made for the word "excavation" in that sentence. I rejected it: the
article gives nothing about the excavation itself beyond "in 1990" and that it produced
datable silt — no site codes, no context numbers, no separate trench identity. Instantiating
A9 would produce a second, almost-empty event node carrying the same single fact
(`P4 has time-span = 1990`) that the dating measurement's own time-span already states.
That is padding, not depth, so I used only **E16 Measurement** for the dating act itself.
E16's scope note gives its own carbon-14-dating example ("the carbon-14 dating of the
Schoeninger Speer... in 1996") as a direct structural parallel to an OSL date, which is why
I'm confident E16 — not a generic E7 Activity — is the right level of specificity here.

I gave the measurement's actual target as a separate `ex:SiltDeposits` (`E18 Physical
Thing`, `P46i forms part of` the White Horse) rather than pointing `P39 measured` straight
at the White Horse feature: the article is explicit that silt, not the chalk figure itself,
is what was dated, and E16's scope note is explicit that "the carrier can be named" via
`P16`/`P39` when there is a distinguishable sampled substrate. I then used the same
`P140`/`P141`/`P177` idiom as the attributions above (`P177 = crm:P4_has_time-span`,
target = the Production event) to carry the measurement's *result* onto the dating of the
figure, keeping "what was physically sampled" and "what date got assigned to the making of
the object" as two distinct, honestly-related claims rather than collapsing them.

### What it depicts: a horse, but the identification itself has a history

`P62 depicts` → a `Horse` type is asserted directly and unhedged, because the article
itself treats this as settled by continuous attestation, not as a live debate: "it has been
called a horse since the 11th century at least," backed by the Abingdon Abbey cartulary
(1072–1084) using "mons albi equi." The article does mention that "it has long been debated
whether the chalk figure was intended to represent a horse or some other animal, such as a
dog or a sabre-toothed cat" — I recorded that only as a `P3 has_note`, deliberately **not**
as another E13 Attribute Assignment, because no claimant is named for it ("has long been
debated" is passive and anonymous). This is the rule I applied throughout the file: a named
claimant earns an E13 node; an anonymous, passively-phrased conjecture gets a note. I think
this is defensible but it is also the kind of line-drawing a reviewer might reasonably want
moved — a stricter reading would put *every* debated identification into E13 regardless of
attribution, at the cost of a much larger file.

### What it means: Pollard's solar-horse theory via P103, not P62

Joshua Pollard's theory (named, affiliated to the University of Southampton) is about
*why* the horse was made — alignment with the midwinter sun — not what shape it shows. I
targeted his E13 assignment's `P177` at `crm:P103_was_intended_for` (purpose/significance)
rather than `crm:P62_depicts` (visual subject), keeping the "what is drawn" question
(horse, settled) separate from the "why was it drawn this way" question (solar symbolism,
contested). The competing, unattributed "tribal symbol connected with the builders of
Uffington Castle" reading I left as a plain note on the object with no formal property at
all, even unhedged — asserting `P103_was_intended_for` for it, even inside an E13 wrapper,
would have required inventing an author for a claim the article gives none. This is the
most conservative of the "considered and rejected" calls in the file, and I'd flag it as
slightly under-modelled rather than over-modelled if a reviewer disagrees.

### Ownership and movement: no E8 Acquisition, no E9 Move

`P52 has_current_owner` / `P50 has_current_keeper` → National Trust are asserted as a bare,
undated, current fact. I did not construct an `E8 Acquisition` event: the article never
says when or from whom the National Trust obtained the site, and inventing a plausible date
would be exactly the kind of fabrication the brief prohibits. Equally, no `E9 Move` appears
anywhere in the file — the object is immovable, and the article records no relocation, only
maintenance and alteration in place. This is a case where the brief's own template ("its
history of ownership or movement") assumes more than the source, or the object, supports;
saying so once, plainly, felt more useful than silently leaving the properties out.

### "How it was found": the brief's template doesn't quite fit this object

The brief asks how the object was "found or acquired," which presumes something that was
lost, buried, or excavated as a discrete find. The White Horse was never lost: it has been
continuously visible (bar the WWII camouflage) and continuously named since at least
1072–1084. I treated the two early textual attestations — the Abingdon Abbey cartulary and
the Llyfr Coch Hergest (Red Book of Hergest, compiled 1375–1425) — as `E31 Document`
instances that `P70 documents` the object, i.e. as evidence of *naming*, not of
*discovery*. The nearest real analogue to "how it was found" in this source is the 1990 OSL
dating, which I modelled as described above. I want to flag this mismatch explicitly rather
than force a `Discovery`-shaped event where the source doesn't supply one.

### The scouring custom: one type, one ranged event, one revival — not one event per cycle

The article says the horse was "scoured every seven years... from time immemorial," names
1755 and 1857 as the first and (informally) last of a documented run, and says the custom
was revived in 2009. I did not try to instantiate one `E11 Modification` per seven-year
cycle — the article gives no list of specific dates, only a rule and two endpoints — so I
modelled the documented run as a single event spanning 1755–1857 (typed via a shared
`Scouring` `E55 Type`, linked to Thomas Hughes' 1859 book via `P70i is_documented_in`), plus
a separate, properly dated 2009 revival event carrying the same type. This is an economy
decision I'm fairly confident in: enumerating imaginary seven-year dates the source doesn't
give would be worse than compressing the documented ones.

### Alterations kept in, and one kept out

2002 (rider and three dogs, Real Countryside Alliance), 2012 (a jockey, an unnamed
bookmaker), and 2024 (the restoration project) are each modelled as `E11 Modification`. I
did **not** give the 2012 jockey addition a `P14 carried out by`: the article names the
agent only as "a bookmaker," and inventing a placeholder resource for an anonymous role felt
like manufacturing a named actor the source doesn't supply. I also deliberately **excluded**
the 2003 Big Brother advertisement: the article places it "near the figure," not on it, so
it is not a fact about this object, and including it would be exactly the kind of tangential
padding the brief warns against.

For 2024, I merged the August 2023 planning announcement (National Trust + archaeologist
Adrian Cox) and the summer 2024 start of work (Oxford Archaeology + National Trust +
English Heritage) into one event, because the article does not clearly present them as two
activities with distinct scopes — one is a plan, the other its execution. I kept Adrian Cox
out of that event's `P14 carried out by`, since the article names him only against the 2023
plan, not the 2024 work, and noted this distinction explicitly rather than silently folding
him in. I also deliberately did **not** assert that "Oxford Archaeology" (2024) and the
"Oxford Archaeological Unit" (1990) are the same organisation, even though in reality they
almost certainly are (the Unit was renamed) — the article uses two different names and
never states an identity between them, so I kept them as two separate `E74 Group`
resources. This is a case where outside knowledge would improve the model and I chose not
to use it, on the brief's instruction to model only what the page supports.

### "Scheduled monument" via P2 has_type, not E30 Right

I considered `E30 Right` (`P104 is_subject_to`) for the statutory "scheduled monument"
status, since E30's applicable-properties list includes exactly that path from a physical
thing. I rejected it: E30's own scope note and both its worked examples (copyright, Louvre's
ownership of the Mona Lisa) describe transactable legal privileges — things one party holds
and could in principle transfer or license — not a statutory listing grade assigned by a
public body. "Scheduled monument" reads to me as a classification of the object, which is
what `P2 has_type` is for, so I used that instead. This is a real judgement call, not a
forced move, and a reviewer more comfortable stretching E30 to cover regulatory status might
reasonably choose differently.

### Names: full rigour once, shorthand everywhere else

I used the complete `P1_is_identified_by` → `E41 Appellation` → `P190_has_symbolic_content`
chain only for the object's own name ("Uffington White Horse"), since that is the one
identifier the brief specifically calls out. Every other name in the file (persons, places,
groups, types) carries only an `rdfs:label`. This is a deliberate economy, not an oversight
— doing the full chain for every one of the ~30 named resources would have added dozens of
near-identical triples without adding an argument — but it does mean the file is
inconsistent about which names are "real" CRM identifications and which are conveniences,
and I want that visible rather than implied.

## 2. The tools

**Final validator result:** `Verdict: PASSED -- every link resolves within its declared
domain and range, every rdf:type is a class this model declares, and every owl:inverseOf
claim holds` (run twice: once producing 2 illegal links — `P4 has_time-span` wrongly used on
two `E31 Document` instances, fixed by moving those dates into notes — and once clean).
`completeness: true` then reported only "partly stated" and "never stated" gaps I had
already deliberately chosen and mostly already annotated in-file (missing dates on the WWII
events, missing agents on the anonymous alterations, and a long list of spacetime-volume
apparatus — `P10`, `P12`, `P160`, `P161`, `P7`, `P196` — that no practical CRM dataset
populates).

**MCP calls: 18 total.** Roughly: 1 `--list`; 2 `crm_list` (CRMarchaeo, then all of
CRMbase for spellings); 9 `crm_concept` (E25, E26, E22, E13, P177, E16, A9, E30, E11); 3
`crm_thread` (t0821 rock-cut-structures-as-E25, t1874 E24-movability, t1877 the Jan-2026
E13 scope-note vote); 3 `crm_validate_rdf` (two structural passes plus one completeness
pass). No `crm_connect` calls — every join I needed was already visible in a `crm_concept`
dump's "applicable properties" section, so `crm_connect` never earned its own call. No tool
call failed; none needed a retry.

**Wanted to ask and couldn't:** whether the SIG has ever discussed a chalk hill figure or
geoglyph specifically (as opposed to the general rock-cut-structure discussion I found in
t0821). I didn't spend a further `crm_search`/`crm_docs` call chasing that once E25 was
well-supported by the Abu Simbel/Manchester-Ship-Canal precedent, so this is an unpursued
lead rather than a dead end.

**Blunt feedback:**
- The single biggest source of friction was that every `crm_concept` dump lists the same
  ~10 spacetime-volume/witness properties (`P10 falls within`, `P12 occurred in the
  presence of`, `P160`/`P161`, `P7 took place at`, `P196 defines`) as "Required" on nearly
  every event class, with no visual distinction from properties that are actually
  substantive for a working model. I had to eyeball past this boilerplate on every single
  class lookup to find the 3–4 properties that mattered, and the completeness checker
  dutifully re-surfaces the same boilerplate as "never stated" clutter around the few
  genuinely useful omissions. A "core" vs. "formal-completeness" split in the property
  listing would have saved real time.
- One `crm_concept` output (`P52_has_current_owner`) had a truncated prose description
  ("identifies the instance of E21 Person...") that didn't match its own structured
  domain/range column a few lines above (`E18 -> E39`). I trusted the structured column and
  it validated correctly, but a less careful read could easily walk away thinking P52's
  range is restricted to persons rather than any Actor.
- Otherwise the tools did what they claimed: `crm_thread` surfaced exactly the debates I
  needed (the E25-vs-immobile-structures argument and the live Jan-2026 E13 vote) on the
  first targeted query, and `crm_validate_rdf`'s error messages (`"E31 is not a E2"`) were
  specific enough to fix without a second guess.
