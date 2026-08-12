Produce a CIDOC CRM model of {subject}, written in Turtle, from {source}.

## Getting the vocabulary right

Ask this server rather than recalling the CRM from memory. Two habits pay
for themselves:

- `crm_list` with a `model` argument prints every identifier in that model
  WITH the RDF local name to write and the namespace at the top. One call
  spells a whole model. Do not call `crm_concept` once per identifier just
  to learn a spelling: that costs a call per identifier and buys nothing a
  single listing does not already give you.
- `crm_connect` between two classes shows every property that can legally
  join them, in both directions. Reach for it before you write a triple you
  are unsure of; it is the difference between choosing a property and
  inventing one.

Read `crm_concept` when you need to choose BETWEEN candidates -- the scope
note is what distinguishes two classes that both look plausible.

## When the ontology cannot settle it

A scope note says what a class is. It often will not say which of two
classes the standard intends for your case, or why a property is shaped as
it is. Where this server exposes the SIG archive, that is what it is for:
the list has argued out most of the choices the specification leaves open,
and the reasoning survives only there. Search it, and read the thread rather
than trusting a summary line.

## Modelling

Most intuitive binary relationships conceal a temporal entity. "X owns Y",
"A made B" and "this was found at P" are each an event with participants,
a time and a place, and modelling them as a direct property loses everything
that makes them checkable. This is the most common error in CRM models.

Model what {source} actually supports. Do not supply facts it does not
state. There is a real line here, and it is worth holding: turning "the 17th
century" into a bounded time-span, or a stated administrative hierarchy into
a chain of places, is FORMALISING what you were given, because the CRM needs
a shape for it. Adding a country nobody mentioned, or dates for a named war,
is INVENTING. Do the first freely; do the second only if you say so
explicitly.

Where the source hedges -- "attributed to", "probably", "one theory holds"
-- carry the hedge into the model rather than flattening it into a fact.

## Check the subject of every property, not only the property

RDF is context free. A statement is about the node it hangs off and nothing
else. Writing `A -> B` does not put later statements about B "inside" A:
there is no scope, no nesting, no salience. Indentation in a Turtle file, or
in any tree view of one, is layout.

Prose works the other way, which is what makes this the commonest way a
model goes wrong while staying legal. Say a chair is typed "oak dining
chair". A note that its left arm is scratched, attached to that type, says
oak dining chairs have a scratched left arm -- everywhere, for everyone who
uses that type. It belongs on the chair.

E55 Type is the usual casualty, because a type is shared vocabulary: it
carries what defines it, and a fact about one object belongs on that object.

The failure is not choosing the wrong subject. It is never treating the
subject as a choice: attention goes to picking the property, or to whether
something warrants a note or a full attribute assignment, and the subject is
inherited from whatever you were already thinking about. So make it
explicit. Read each triple with the surrounding lines deleted. If the
sentence is only true because of what came before it, the subject is wrong.

Nothing checks this for you. P3 has note is legal on any class, so domain
and range validation is silent here by construction.

## Checking

Validate the whole document with `crm_validate_rdf`, not a link at a time:
an author who checks only the links they already doubt skips the ones they
got wrong.

Read the verdicts precisely. `not_crm` and `unchecked` mean NOT EXAMINED,
not "fine" -- a predicate outside the CRM and a subject with no type are
both reported and neither fails. `rdfs:label` showing as `not_crm` is
expected and correct.

Then run it once more with `completeness: true`. That lists properties the
CRM marks necessary for a class that your instances do not carry. They are
not errors -- the specification says quantifiers are for semantic
clarification and that every property should be implemented as optional --
so use judgement: something one instance in ten lacks is likely an
oversight, something every instance lacks is likely a convention. Fix the
first kind where the source supports it.

Finish with the validator reporting no failure.

## Write up the reasoning

Your model will be read by someone who knows the CRM and will ask "why that
class?". Answer it in advance. For every decision that could reasonably have
gone another way: what you chose, what you considered and rejected, and why
-- citing the scope note, the `crm_connect` result or the thread that
decided it.

Say plainly where you are unsure. A decision flagged as shaky is more useful
than one presented as settled. List separately anywhere the model goes
beyond its source. Do not pad this with decisions that had only one legal
option; attention is the scarce thing, so spend it on the genuine forks.
