# Mao Gong ding — CIDOC CRM model: report

Turtle file: `v2_maogong.ttl` (same directory).

## 1. The argumentation

### The object itself: E22 Human-Made Object
No real fork here — it's a made physical object, so E22 (E19/E24 combined) is the
only class that fits; E19 Physical Object alone would drop the "human-made" fact
the article states outright ("bronze tripod ding vessel"). Not spending more space
on it.

### Major parts: deliberately none
I considered adding part-objects for the tripod's legs, or a separate "interior
surface" feature to carry the inscription (`P56_bears_feature`, E26 Physical
Feature). I rejected both. The article gives no count or description of legs
beyond the word "tripod" embedded in the vessel-type name, and inventing three
leg-objects would be structure the source doesn't support. For the inscription
I used `crm:P128_carries` straight from the E22 object to the E34 Inscription —
that's the property's actual domain (E24 Physical Human-Made Thing), so the
"surface" node would have been an unnecessary extra hop, not a real distinction
the article draws.

### The inscription: E34 Inscription, and a single Production rather than two events
`crm_concept E34` confirms it as a subclass of both E33 Linguistic Object (via
E73/E89, giving it `P129_is_about`) and E37 Mark (via E36), which is exactly the
double nature a cast bronze inscription has: text and physical mark at once.

The real fork was whether to add a second event — an E65 Creation for the
*authorship* of the inscription's wording, separate from the E12 Production that
casts the physical vessel (the way FRBRoo splits expression-creation from
manufacture). I rejected it: the article never says who composed the text, only
that the Duke of Mao "presents the ding" containing the king's speech and his
own thanks — that's compatible with him commissioning the words but doesn't
establish authorship. Asserting `P94_has_created` naming him as author would
overclaim. So the object and its cast-in inscription are produced together, in
one E12 Production; `P129_is_about` on the inscription carries the content
(King Xuan, the Lord of Mao, King Wen, King Wu, and the "King Xuan restoration")
without asserting who wrote it.

### Making: E12 Production, with the Lord of Mao as commissioner, not maker
The article never names an artisan. I used `P14_carried_out_by` on the
Lord of Mao anyway, because CRM's own convention is that P14 names whoever is
responsible for the activity, not necessarily the hand that did the physical
work — confirmed by reading SIG thread **t1345** (2020), where George Bruseker's
worked examples ("carried out by X as representative of Y") treat P14 plus a
role label as the standard way to qualify *how* someone participated, distinct
from a different problem (representing an organisation) that thread was
actually about. I *wanted* to attach the role formally via `P14.1_in_the_role_of`
("commissioner") but couldn't get a confirmed RDF encoding for it — see §2 — so
I fell back to a plain `P3_has_note` stating the distinction in prose. That's a
real gap between what I intended and what I shipped; flagging it rather than
guessing a reification pattern I couldn't verify.

I linked the Production to a separate `E7_Activity` ("King Xuan's appointment of
the Lord of Mao") via `P17_was_motivated_by`, since the article gives this as
the reason the ding exists at all ("gifted the ding to the King after being
appointed to help run state affairs"). I did not invent a CRM class for
"appointment to office" — there isn't one — E7 Activity is the generic, honest
choice.

### The presentation to the king: not modelled as a change of ownership
This is the fork I'm least certain about, so I'm flagging it plainly. The lead
sentence says the ding "was presented to him [King Xuan]" by the Lord of Mao;
the inscription summary later says the Duke "presents the ding … for future
generations" after expressing his gratitude — which reads as dedicating it
within his own family's line, not handing it to the king. These two framings
pull in different directions, and the History section starts the ownership
chain at the 1843 excavation with no mention of any royal custody in between,
which fits the second reading much better than the first (a vessel in the
king's possession is an odd thing to find buried near Qishan generations
later). I chose **not** to assert an `E8_Acquisition` transferring title to
King Xuan. Instead I modelled "the presentation" only as something the
inscription's `P129_is_about` points at — an E7 Activity with the Lord of Mao
as `P14_carried_out_by` and King Xuan as `P11_had_participant` — which records
the article's claim about what happened without committing the object's own
provenance chain to a transfer I'm not confident the source actually supports.
A reviewer who reads the lead sentence more literally than I did would
disagree with this call.

### Finding: S19 Encounter Event (CRMsci), not A9 Archaeological Excavation
The article says only "was excavated … in 1843" — no excavator, no campaign,
no stratigraphy. `crm_search` on "discovery excavation encounter event" surfaced
the actual 2013 SIG proposal to add a dedicated "Discovery" class (thread
**t0689**) and the 2014 follow-up ("finding things", thread **t0760**) noting
that need was resolved by placing a Find event in the Scientific Observation
extension as **S19 Encounter Event** — precisely the precedent the
`crm_thread` tool description itself points to. I used that rather than
CRMarchaeo's A9 Archaeological Excavation, which models an organised dig
campaign (`AP3_investigated` an E27 Site) — a heavier commitment than "was
excavated" supports. I used S19's own `O21_encountered_at` rather than the
generic inherited `P7_took_place_at` for the location, since it's the more
specific property built for exactly this case (confirmed via `crm_concept S19`).

### Ownership chain: E96 Purchase vs. plain E8 Acquisition, chosen by the article's verb
`crm_concept`/`crm_docs` on E8 and E96 confirm E96 Purchase is the *only*
subclass CRM gives for a specific mode of transfer (compensated exchange); there
is no parallel "Gift" or "Donation" class. So I split by the article's own verb:
"bought"/"sold" → `E96_Purchase`; "acquired" (mode unstated) → plain
`E8_Acquisition` with no type at all; "was presented with" / "donated" →
`E8_Acquisition` + `P2_has_type` "gift"/"donation". That third pattern is my own
inference from the class hierarchy, not something a scope note stated outright
— worth a reviewer's second look, though it matches common CRM practice.

Two more decisions inside this chain:
- **Anonymous parties as E74 Group, not as the named individuals.** "The Chen
  family" bought from Duanfang in 1909–1911, decades after Chen Jieqi
  (1813–1884) died — so I made "the Chen family" a distinct E74 Group rather
  than reusing the `ChenJieqi` person node, which would have quietly asserted a
  dead man conducted a sale. Same reasoning for "the Ye family" (vs. Ye
  Gongchuo personally) and the anonymous "friends of Ye Gongchuo."
- **The general as `P14_carried_out_by`, separate from the legal parties.**
  Chen Yon Ren donated the ding "through a general" — I read that as the
  general being the one who physically carried out the handover, while
  `P22`/`P23` (transferred title to/from) stay on Chen Yon Ren and the
  Kuomintang Shanghai Government as the actual legal parties. This is exactly
  the kind of role CRM's P14 vs P22/23 split is for, and I'm fairly confident
  in it — more confident than the P14.1 label I couldn't attach.

**Gaps I chose to leave open rather than paper over:** no custody is asserted
between the 1843 excavation and Chen Jieqi's 1852 acquisition (nine years, no
source); no seller is named for that 1852 acquisition; the friends'-purchase-
from-the-bank has no date at all; and I never asserted how the bank came to
hold the ding as mortgage collateral, or from whom. All four are real holes in
the source, not oversights in the model.

### Dates given only vaguely
Where the article gives an exact year or month (1843, 1852, April 1946, 1949) I
bounded the E52 Time-Span to that unit with `P82a`/`P82b`. Where it gives a
named era with an explicit bracket ("Xuantong era (1909–1911)") I used that
bracket directly — it's the article's own numbers, not my calculation. Where it
gives only a named period with no bracket of its own ("during the Second
Sino-Japanese War") I left the time-span **unbounded**, on purpose: I know the
conventional 1937–1945 dates for that war, but the article doesn't state them,
and the brief's own instruction was not to invent what isn't there. Same
treatment for the Western Zhou dynasty's own "c. 1045 – c. 771 BCE" — I did not
convert those hedged "c." dates into exact xsd:date bounds; the production
event's time-span only says "during the reign of King Xuan" and falls loosely
within that unbounded dynastic span. This is the one place the article's own
hedge language ("c.") shows up, and I carried it through by *not* resolving it,
rather than by picking a specific year and calling it done.

### Beyond the source, flagged explicitly
Two small additions go past what's literally stated: `P72_has_language`
"Chinese" on the inscription (the article never says the inscription's
language in words, though it's obvious from context — the Chinese characters
in the title, the "Chinese bronze inscriptions" see-also link); and treating
"one of the museum's three treasures" as a `P2_has_type` tag on the object
rather than modelling an actual E78 Curated Holding with the Jadeite Cabbage
and Meat-Shaped Stone as fellow members — the latter would have required
asserting facts about two objects this run has no sourced information on, so I
kept it as a lighter descriptive type instead.

### Current state: keeper and location only, no asserted current owner
`crm_connect(E22, E39)` showed `P50`/`P52`/`P49`/`P51` are all shortcuts over
the full E10/E8 event paths. I used the full E8/E9/S19 events for history (they
carry dates the shortcuts would lose) and reserved the shortcuts for
present-day facts the article states directly: `P50_has_current_keeper` →
National Palace Museum, `P55_has_current_location` → Taipei. I deliberately did
**not** assert `P52_has_current_owner`: the last stated legal owner in the
chain is "the Kuomintang Shanghai Government" (1946), a wartime body that
doesn't meaningfully exist today, and the article never states who owns the
ding now (only who houses it) — asserting that 1946 entity as *current* owner
would misuse the property's own present-tense semantics.

## 2. The tools

**Final validator result:** `Verdict: PASSED -- every link resolves within its
declared domain and range, every rdf:type is a class this model declares, and
every owl:inverseOf claim holds`. The completeness pass (`completeness: true`)
came back clean too — every "partly stated" and "never stated" property it
listed traced back to a deliberate choice above (unstated dates/actors,
generic ancestor properties left unused in favour of the more specific
property that subsumes them — e.g. `P7`/`P92`/`P14` vs. the `O21`/`P108`/`P22`
I actually used), not a real omission.

**MCP calls made: 19**, roughly: `--list` (1); `crm_list` for CRMbase,
CRMarchaeo, CRMsci (3, to get exact RDF spellings in bulk rather than one
`crm_concept` call per identifier); `crm_concept` for S19, S27, E40 (3, to
check class hierarchies and confirm E40 Legal Body is deprecated in favour of
E74 Group); `crm_search` for the discovery/excavation precedent and for
patron/commissioner precedent (2); `crm_thread` for t1345 (1, read in full
before relying on it); `crm_docs` for acquisition-mode typing and for the
P14.1 RDF encoding (2); `crm_connect` for E22↔E39 and E52↔E61 (2); and
`crm_validate_rdf` (4: the first full run, a re-run after fixing an
unparseable BCE date literal, one completeness run, and a final confirmation
run after tightening two P14 assignments). No call failed outright, so none
needed a retry.

**What I wanted to ask and couldn't get a clean answer on:** how a `.1`
qualifier property like `P14.1_in_the_role_of` is actually meant to be encoded
in RDF/Turtle. `crm_docs` returned only the scope note, never an encoding
example. I went looking at the reification classes that should carry this
(`crm_list` showed `PC0`, `PC1`, `PC2`, `PC14` in CRMbase), but every one of
them came back "archive-attested only; no current declaration" — the
mechanism that should answer this question isn't populated in the server's
data. I ended up not asserting `P14.1` at all rather than guess a pattern I
couldn't verify, which is a real loss of precision in the model (see the
commissioner-role note above).

**Blunt notes on the tools themselves:**
- The `PC*` gap above is the sharpest one: any model that needs to qualify a
  P14/P11/etc. relationship (a very common CRM need — roles, manner) has
  nothing to check its encoding against.
- `crm_validate_rdf` doesn't itself flag it, but feeding it a negative-year
  (BCE) `xsd:date` literal makes the underlying rdflib parser throw a raw
  Python traceback to stderr (`Invalid isoformat string: '-1044-01-01'`) on
  every triple that touches it — silently, since the verdict still says
  PASSED. For an ontology this heavily used in archaeology and ancient
  history, not being able to state a BCE date as a real bounded value without
  tripping the underlying library is a real gap, not a corner case.
- `crm_search` prints an "unauthenticated HF Hub" warning block on every call;
  harmless, but it's stderr noise on every single search.
- Two `crm_docs` queries phrased differently about "how to mark a gift vs. a
  purchase acquisition" both returned the same E8/E96/P22/P23 scope notes
  rather than any narrative guidance — the convention I used (E96 only for
  compensated transfers, `P2_has_type` for everything else) is my own
  read of the class hierarchy, not something the server told me outright.
  Worth a second opinion from a reviewer who knows of a documented example I
  didn't find.
