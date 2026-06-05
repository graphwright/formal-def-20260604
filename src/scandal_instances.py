"""
# A Scandal in Bohemia — instance graph

This file populates the first instance graph from the Holmes corpus.
Source: *The Adventures of Sherlock Holmes*, Project Gutenberg edition
(https://www.gutenberg.org/files/1661/1661-h/1661-h.htm).

Paragraph indices below refer to the double-newline-separated paragraphs
of the story text, zero-indexed from the title. `extraction_method` is
`"manual"` throughout; `extraction_confidence` is `1.0` for unambiguous
assertions and lower where Watson hedges.

This graph exercises all major schema features:

- `DisguisedAs` / `HasTrueIdentity` inverse pair (King + Holmes both
  appear in disguise)
- `LocatedIn` transitive chain (Briony Lodge → St. John's Wood → London)
- `KnewAt` demonstrating higher-order predication — its object_ is a
  predicate instance (e.g. a `DisguisedAs` edge), not a separate
  Statement entity
- `Possesses` (added to the schema when the photograph forced the issue)
- `Symmetric` (`Knows`), `Functional` (`HasTrueIdentity`)

Schema version: 0.7.0-draft (unified Statement model)

Under the unified model, every predicate instance IS a statement: it has
an `id` (content-addressed), a `truth_status`, and can be referenced by
higher-order predicates like `KnewAt` and `Contradicts`. There is no
separate Statement entity type. The former `stmt_king_is_count_von_kramm`
is now simply the `DisguisedAs` edge itself, pointed at directly by
`KnewAt`.
"""

from .holmes_schema import (
    AssociatedWith,
    BaseStatement,
    DisguisedAs,
    Document,
    Event,
    Executes,
    HasTrueIdentity,
    Involves,
    KnewAt,
    Knows,
    Location,
    LocatedIn,
    Moment,
    Object,
    OccurredAt,
    Person,
    Persona,
    Plan,
    Possesses,
    TruthStatus,
    statement_id,
)


"""
## Provenance shorthand

Every predicate instance in this file was extracted manually from the
Project Gutenberg text of *A Scandal in Bohemia*. `_p(para)` returns the
shared provenance fields plus `truth_status` (defaulting to ASSERTED_TRUE
since all manual extractions from this story are ground truth). `_sid()`
computes the content-addressed id for a predicate instance.
"""

STORY = "scandal_in_bohemia"


def _p(para: int, narrator: "Person | None" = None,
       truth: TruthStatus = TruthStatus.ASSERTED_TRUE) -> dict:
    return dict(
        story_id=STORY,
        paragraph_index=para,
        extraction_method="manual",
        extraction_confidence=1.0,
        asserting_narrator=narrator,
        truth_status=truth,
    )


def _sid(subject, predicate_cls, object_):
    """Content-addressed id for a predicate instance."""
    return statement_id(subject.id, predicate_cls.__name__, object_.id)


"""
## Persons

Five people with speaking roles or decisive agency. Baker Street Wiki URIs
serve as canonical IDs for all five — they are externally authoritative
entities, not corpus-local constructs.
"""

holmes = Person(
    id="https://bakerstreet.fandom.com/wiki/Sherlock_Holmes",
    display_name="Sherlock Holmes",
)
watson = Person(
    id="https://bakerstreet.fandom.com/wiki/John_H._Watson",
    display_name="Dr. John H. Watson",
)
irene_adler = Person(
    id="https://bakerstreet.fandom.com/wiki/Irene_Adler",
    display_name="Irene Adler",
)
king_of_bohemia = Person(
    id="https://bakerstreet.fandom.com/wiki/Wilhelm_Gottsreich_Sigismond_von_Ormstein",
    display_name="Wilhelm Gottsreich Sigismond von Ormstein",
)
godfrey_norton = Person(
    id="https://bakerstreet.fandom.com/wiki/Godfrey_Norton",
    display_name="Godfrey Norton",
)


"""
## Personas

Two disguises appear in this story, each exercising the `DisguisedAs` /
`HasTrueIdentity` inverse pair.

**Count Von Kramm** is the alias the King uses when visiting Baker Street.
He announces it himself (para 46), then drops the mask at para 57 when
Holmes makes clear he already knows.

**The Nonconformist Clergyman** is Holmes's cover when he infiltrates
Briony Lodge on the evening of March 21 (para 173).

Both are corpus-local — no Baker Street Wiki authority covers fictional
aliases as first-class articles.
"""

count_von_kramm = Persona(
    id="sib:persona:count_von_kramm",
    display_name="Count Von Kramm",
)
nonconformist_clergyman = Persona(
    id="sib:persona:nonconformist_clergyman",
    display_name="Nonconformist Clergyman",
)


"""
## Locations

The geographic chain London → St. John's Wood → Briony Lodge is the one
transitive `LocatedIn` chain this story exercises.
"""

london = Location(
    id="https://bakerstreet.fandom.com/wiki/London",
    display_name="London",
)
st_johns_wood = Location(
    id="https://bakerstreet.fandom.com/wiki/St._John%27s_Wood",
    display_name="St. John's Wood",
)
baker_street_221b = Location(
    id="https://bakerstreet.fandom.com/wiki/221B_Baker_Street",
    display_name="221B Baker Street",
)
briony_lodge = Location(
    id="https://bakerstreet.fandom.com/wiki/Briony_Lodge",
    display_name="Briony Lodge, Serpentine Avenue",
)
church_of_st_monica = Location(
    id="https://bakerstreet.fandom.com/wiki/Church_of_St._Monica",
    display_name="Church of St. Monica, Edgware Road",
)


"""
## Objects and Documents

**The photograph** is the story's MacGuffin — a cabinet-size photograph
of Irene Adler and the King together (para 78, 119).

**The advance note** is the unsigned, undated letter delivered to Holmes
before the King's visit (para 22–23).

**Irene's farewell letter** is left at Briony Lodge for Holmes to find the
morning of March 22 (para 246–247).
"""

irene_photograph = Object(
    id="https://bakerstreet.fandom.com/wiki/Irene_Adler%27s_photograph",
    display_name="Cabinet photograph of Irene Adler and the King",
)
advance_note = Document(
    id="sib:doc:advance_note",
    display_name="Advance note from the King's agent",
    story_id=STORY,
    document_type="letter",
)
farewell_letter = Document(
    id="sib:doc:farewell_letter",
    display_name="Farewell letter from Irene Norton to Sherlock Holmes",
    story_id=STORY,
    document_type="letter",
)


"""
## Events

Six discrete occurrences anchor the story's causal structure.

| ID | Description | Para |
|---|---|---|
| `evt_kings_visit` | King visits Baker Street as Count Von Kramm | 43 |
| `evt_holmes_surveillance` | Holmes watches Briony Lodge as a groom | 129 |
| `evt_norton_visits_irene` | Godfrey Norton arrives at Briony Lodge | 135 |
| `evt_wedding` | Irene and Norton marry at St. Monica's | 140–144 |
| `evt_fake_fire_alarm` | Holmes triggers false alarm at Briony Lodge | 196 |
| `evt_discovery_of_flight` | Holmes/Watson/King find Irene has fled | 238–245 |
"""

evt_kings_visit = Event(
    id="sib:event:kings_visit",
    story_id=STORY,
    description="The King of Bohemia visits Holmes at Baker Street, initially as Count Von Kramm.",
)
evt_holmes_surveillance = Event(
    id="sib:event:holmes_surveillance",
    story_id=STORY,
    description="Holmes loiters near Briony Lodge disguised as a groom, observing Irene and Norton.",
)
evt_norton_visits_irene = Event(
    id="sib:event:norton_visits_irene",
    story_id=STORY,
    description="Godfrey Norton arrives at Briony Lodge by hansom cab and meets with Irene.",
)
evt_wedding = Event(
    id="sib:event:wedding_at_st_monica",
    story_id=STORY,
    description="Irene Adler and Godfrey Norton marry at the Church of St. Monica.",
)
evt_fake_fire_alarm = Event(
    id="sib:event:fake_fire_alarm",
    story_id=STORY,
    description="Holmes, disguised as a clergyman, stages a fake fire alarm at Briony Lodge to locate the photograph.",
)
evt_discovery_of_flight = Event(
    id="sib:event:discovery_of_flight",
    story_id=STORY,
    description="Holmes, Watson, and the King arrive at Briony Lodge to find Irene has fled to the Continent.",
)


"""
## Moments

Moments without a `narrator` sit on the **objective story timeline**.
Moments with a narrator sit on that person's **epistemic timeline**.
"""

moment_kings_visit = Moment(
    id="sib:moment:kings_visit_evening",
    story_id=STORY,
    label="Evening of 20 March 1888 — King visits Baker Street",
)
moment_wedding = Moment(
    id="sib:moment:wedding_morning",
    story_id=STORY,
    label="Morning of 21 March 1888 — Wedding at St. Monica's",
)
moment_fake_fire = Moment(
    id="sib:moment:fake_fire_evening",
    story_id=STORY,
    label="Evening of 21 March 1888 — fake fire alarm at Briony Lodge",
)
moment_discovery = Moment(
    id="sib:moment:discovery_morning",
    story_id=STORY,
    label="Morning of 22 March 1888 — discovery that Irene has fled",
)

moment_watson_sees_king_unmasked = Moment(
    id="sib:moment:watson_sees_king_unmasked",
    story_id=STORY,
    label="Watson witnesses the King remove his mask",
    narrator=watson,
)
moment_watson_learns_irene_married = Moment(
    id="sib:moment:watson_learns_irene_married",
    story_id=STORY,
    label="Holmes tells Watson that Irene married Norton (in the King's brougham)",
    narrator=watson,
)


"""
## Structural edges

### Geographic containment (`LocatedIn`, Transitive)

The transitive chain `briony_lodge → st_johns_wood → london` means that
any reasoner following `LocatedIn` edges transitively can derive
`briony_lodge LocatedIn london` without an explicit edge.

Every predicate instance now carries an `id` (content-addressed via
`_sid()`) and a `truth_status` (defaulting to ASSERTED_TRUE via `_p()`).
These are the new universal fields from the unified Statement model.
"""

e_briony_in_stjohnswood = LocatedIn(
    id=_sid(briony_lodge, LocatedIn, st_johns_wood),
    subject=briony_lodge, object_=st_johns_wood,
    **_p(118, watson),
)
e_stjohnswood_in_london = LocatedIn(
    id=_sid(st_johns_wood, LocatedIn, london),
    subject=st_johns_wood, object_=london,
    **_p(118, watson),
)
e_bakerstreet_in_london = LocatedIn(
    id=_sid(baker_street_221b, LocatedIn, london),
    subject=baker_street_221b, object_=london,
    **_p(4, watson),
)
e_stmonica_in_london = LocatedIn(
    id=_sid(church_of_st_monica, LocatedIn, london),
    subject=church_of_st_monica, object_=london,
    **_p(138, watson),
)

"""
### Habitual associations (`AssociatedWith`)
"""

e_holmes_at_bakerstreet = AssociatedWith(
    id=_sid(holmes, AssociatedWith, baker_street_221b),
    subject=holmes, object_=baker_street_221b,
    **_p(3, watson),
)
e_irene_at_briony = AssociatedWith(
    id=_sid(irene_adler, AssociatedWith, briony_lodge),
    subject=irene_adler, object_=briony_lodge,
    **_p(118, watson),
)


"""
## Social edges (`Knows`, Symmetric)

`Knows` is symmetric — one edge suffices for a mutual acquaintance.
"""

e_holmes_knows_watson = Knows(
    id=_sid(holmes, Knows, watson),
    subject=holmes, object_=watson,
    **_p(5, watson),
)
e_watson_knows_of_irene = Knows(
    id=_sid(watson, Knows, irene_adler),
    subject=watson, object_=irene_adler,
    **{**_p(63, watson), "extraction_confidence": 0.7},
)


"""
## Identity edges (`DisguisedAs` / `HasTrueIdentity`)

Each disguise requires a forward edge (`DisguisedAs`) and its inverse
(`HasTrueIdentity`). `HasTrueIdentity` is also `Functional`.

Under the unified model, these edges are directly referenceable by
`KnewAt` — they ARE the propositions Watson comes to know, without
any intermediate Statement entity.
"""

e_king_as_count = DisguisedAs(
    id=_sid(king_of_bohemia, DisguisedAs, count_von_kramm),
    subject=king_of_bohemia, object_=count_von_kramm,
    **_p(46, watson),
)
e_count_is_king = HasTrueIdentity(
    id=_sid(count_von_kramm, HasTrueIdentity, king_of_bohemia),
    subject=count_von_kramm, object_=king_of_bohemia,
    **_p(57, watson),
)
e_holmes_as_clergyman = DisguisedAs(
    id=_sid(holmes, DisguisedAs, nonconformist_clergyman),
    subject=holmes, object_=nonconformist_clergyman,
    **_p(173, watson),
)
e_clergyman_is_holmes = HasTrueIdentity(
    id=_sid(nonconformist_clergyman, HasTrueIdentity, holmes),
    subject=nonconformist_clergyman, object_=holmes,
    **_p(173, watson),
)


"""
## Possession (`Possesses`)

The photograph's provenance is the King's direct testimony (para 78).
`asserting_narrator` is None — Watson is reporting what the King said.
"""

e_irene_possesses_photo = Possesses(
    id=_sid(irene_adler, Possesses, irene_photograph),
    subject=irene_adler, object_=irene_photograph,
    **{**_p(78), "extraction_confidence": 0.95},
)


"""
## Event structure (`OccurredAt`, `Involves`)

`OccurredAt` anchors each event to its objective moment. `Involves` names
each participant.

Note that the King *arrives* as Count Von Kramm, so the `Involves` edge
for `evt_kings_visit` uses the `count_von_kramm` Persona as the visible
participant. Similarly, Holmes attends the wedding (para 144) and the fake
fire (para 196) as the clergyman persona.
"""

e_kings_visit_time = OccurredAt(
    id=_sid(evt_kings_visit, OccurredAt, moment_kings_visit),
    subject=evt_kings_visit, object_=moment_kings_visit, **_p(43, watson),
)
e_wedding_time = OccurredAt(
    id=_sid(evt_wedding, OccurredAt, moment_wedding),
    subject=evt_wedding, object_=moment_wedding, **_p(140, watson),
)
e_fake_fire_time = OccurredAt(
    id=_sid(evt_fake_fire_alarm, OccurredAt, moment_fake_fire),
    subject=evt_fake_fire_alarm, object_=moment_fake_fire, **_p(196, watson),
)
e_discovery_time = OccurredAt(
    id=_sid(evt_discovery_of_flight, OccurredAt, moment_discovery),
    subject=evt_discovery_of_flight, object_=moment_discovery, **_p(238, watson),
)

# evt_kings_visit participants
e_visit_involves_count    = Involves(id=_sid(evt_kings_visit, Involves, count_von_kramm),    subject=evt_kings_visit, object_=count_von_kramm, **_p(43, watson))
e_visit_involves_holmes   = Involves(id=_sid(evt_kings_visit, Involves, holmes),              subject=evt_kings_visit, object_=holmes,           **_p(43, watson))
e_visit_involves_watson   = Involves(id=_sid(evt_kings_visit, Involves, watson),              subject=evt_kings_visit, object_=watson,           **_p(43, watson))

# evt_wedding participants
e_wedding_involves_irene  = Involves(id=_sid(evt_wedding, Involves, irene_adler),             subject=evt_wedding, object_=irene_adler,             **_p(140, watson))
e_wedding_involves_norton = Involves(id=_sid(evt_wedding, Involves, godfrey_norton),           subject=evt_wedding, object_=godfrey_norton,          **_p(140, watson))
e_wedding_involves_holmes = Involves(id=_sid(evt_wedding, Involves, nonconformist_clergyman),  subject=evt_wedding, object_=nonconformist_clergyman, **_p(144, watson))

# evt_fake_fire_alarm participants
e_fire_involves_holmes    = Involves(id=_sid(evt_fake_fire_alarm, Involves, nonconformist_clergyman), subject=evt_fake_fire_alarm, object_=nonconformist_clergyman, **_p(196, watson))
e_fire_involves_irene     = Involves(id=_sid(evt_fake_fire_alarm, Involves, irene_adler),             subject=evt_fake_fire_alarm, object_=irene_adler,             **_p(196, watson))

# evt_discovery_of_flight participants
e_disc_involves_holmes    = Involves(id=_sid(evt_discovery_of_flight, Involves, holmes),          subject=evt_discovery_of_flight, object_=holmes,          **_p(238, watson))
e_disc_involves_watson    = Involves(id=_sid(evt_discovery_of_flight, Involves, watson),          subject=evt_discovery_of_flight, object_=watson,          **_p(238, watson))
e_disc_involves_king      = Involves(id=_sid(evt_discovery_of_flight, Involves, king_of_bohemia), subject=evt_discovery_of_flight, object_=king_of_bohemia, **_p(238, watson))


"""
## Epistemic edges (`KnewAt`) — higher-order predication

These edges demonstrate the unified model's key capability: `KnewAt` takes
a predicate instance as its `object_`. No intermediate Statement entity is
needed — the `DisguisedAs` edge *is* the proposition Watson comes to know.

**Watson learns the King's true identity** at `moment_watson_sees_king_unmasked`
(para 57). The proposition is `e_king_as_count` — the DisguisedAs edge
itself. Watson's KnewAt instance points directly at it.

**Watson learns Irene possesses the photograph** at `moment_kings_visit`
(para 78). The proposition is `e_irene_possesses_photo` — the Possesses
edge. Watson now knows the fact; the fact's own truth_status is
independent of Watson's knowledge of it.

Note the two distinct truth_status values in play for each KnewAt:

- The KnewAt instance's own truth_status: "did Watson really learn this?"
  (ASSERTED_TRUE — yes, Watson was there)
- The object_'s truth_status: "is the proposition itself true?"
  (ASSERTED_TRUE for both, but they COULD differ — Watson can know a
  false proposition, e.g. if truth_status on the object_ were
  ASSERTED_FALSE while the KnewAt remains ASSERTED_TRUE)
"""

e_watson_knew_king_disguised = KnewAt(
    id=_sid(watson, KnewAt, e_king_as_count),
    subject=watson,
    object_=e_king_as_count,      # higher-order: pointing at a DisguisedAs instance
    moment=moment_watson_sees_king_unmasked,
    **_p(57, watson),
)
e_watson_knew_irene_has_photo = KnewAt(
    id=_sid(watson, KnewAt, e_irene_possesses_photo),
    subject=watson,
    object_=e_irene_possesses_photo,  # higher-order: pointing at a Possesses instance
    moment=moment_kings_visit,
    **_p(78, watson),
)