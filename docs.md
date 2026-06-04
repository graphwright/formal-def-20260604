# Principles of Reliable Reasoning: Formal Definition

This is stuff from [this GH gist](https://gist.github.com/wware/b6ec395549569fc217744ec27bcfcb18).

This defines the formal model precisely, establishes vocabulary, states hard rules,
and lists explicit non-goals. When in doubt, check against this file before generating
code, prose, or schema definitions.

The notation itself isn't the point — the benefits come from what the process of
formalizing forces, and those benefits survive translation into plain prose.

**It settles ambiguity permanently.** Natural language descriptions of data structures
always leave wiggle room. "Edges have types" could mean a dozen things. A formal
definition closes off all of them at once. Even if readers never see the notation,
the author has made decisions that make every subsequent explanation consistent.

**It separates schema from instance.** The $T$ vs. $V$ split is the single most
important conceptual distinction in the book. A formal definition makes it impossible
to conflate the two.

**It gives you a checklist.** The 4-tuple is a completeness check. If you can't place
something in one of those slots, either it doesn't belong in the model or the model
is missing a slot. That discipline propagates into the code, the explanations, and
the worked examples.

**It anchors the vocabulary.** Once you've defined $\text{Tr}(p)$ formally, "trait"
has a precise meaning for the rest of the book.

---

## Formal Definition

A typed graph $G$ is a 4-tuple $\mathbf{(T,\ \Phi,\ V,\ \tau)}$ where:

### Schema layer — fixed at graph-design time

- $T$ — finite set of **types**, partitioned into:
  * $T_\text{ent}$ — **entity types** (e.g. Person, Drug, Location)
  * $T_\text{pred}$ — **predicate types** (e.g. Treats, KnewAt, LocatedIn)
- $\Phi: T \to \text{FieldSchema}$ — the **field schema**, mapping each type to a
  Pydantic model declaration of named, typed fields. For predicate types,
  $\Phi$ includes three distinguished fields:
  * `subject` — typed reference to an instance in $V$; the type annotation
    constitutes $\text{dom}(p)$
  * `object_` — typed reference to an instance in $V$; the type annotation
    constitutes $\text{ran}(p)$
  * `truth_status` — the graph's current commitment to the proposition
    this instance expresses
- For each $p \in T_\text{pred}$:
  * $\text{dom}(p) \subseteq T$ — permitted subject types, read from the type
    annotation of `subject` in $\Phi(p)$
  * $\text{ran}(p) \subseteq T$ — permitted object types, read from the type
    annotation of `object_` in $\Phi(p)$
  * $\text{Tr}(p) \subseteq \text{Trait}$ — finite set of semantic traits

The field schema $\Phi$ is the central structural definition. It defines what each
type IS — including whether a type is a predicate (carries subject/object/truth_status)
or a plain entity (does not). Domain and range constraints, truth semantics, and
field validation all derive from $\Phi$. The graph topology is emergent: it is
recovered by reading the subject/object fields of predicate-typed instances.

### Instance layer — populated at ingestion or reasoning time

- $V$ — set of all **instances** (both entity instances and predicate instances)
- $\tau: V \to T$ — type assignment for all instances

The **edge set** $E$ is derived, not primitive:

$$
E = \\{v \in V : \tau(v) \in T_\text{pred}\\}
$$

$E \subseteq V$, that is,
every member of $E$ is also a member of $V$. A predicate instance IS an entity
instance — it has an id, it can be referenced by other predicate instances as
their subject or object. This is the single relaxation relative to the classical
graph formalism, where $V$ and $E$ are disjoint sorts. It is what enables
higher-order predication without a separate reification mechanism.

### Validity constraint

Each instance $v \in V$ carries fields conforming to $\Phi(\tau(v))$.

For predicate instances, this subsumes domain/range enforcement: if $\Phi(p)$
declares `subject: Drug` and `object_: Disease`, then an instance of type $p$
whose subject is a Location fails field validation. No separate domain/range
check is needed.

### Trait vocabulary

$$
\text{Trait} ::= \text{Symmetric} \mid \text{Transitive} \mid \text{Functional} \mid \text{InverseFunctional} \mid \text{Inverse}(p') \mid \text{Rule}(\phi \Rightarrow \psi)
$$

Traits are realized as Python mixin classes inherited alongside the base predicate
class. The unparameterized traits (`Symmetric`, `Transitive`, `Functional`,
`InverseFunctional`) are plain marker classes. `Inverse` is a generic parameterized
by the partner predicate type. `Rule` has no clean type-level expression and is
documented in prose on the predicate class.

### Truth status

Every predicate instance carries a `truth_status` field:

$$
\text{TruthStatus} ::= \text{asserted\\_true} \mid \text{asserted\\_false} \mid \text{hypothetical} \mid \text{disputed} \mid \text{retracted}
$$

Under the closed-world assumption, the presence of a predicate instance does NOT
by itself assert the proposition; the `truth_status` field carries the assertion
explicitly. This replaces the classical convention where edge-presence is assertion.

The **asserted graph** — the first-order fact graph available for traversal — is
the projection of $E$ where `truth_status = asserted_true`. A disputed proposition
remains in $V$ (it can be referenced, queried, and reasoned about) but is excluded
from the asserted graph.

Lifecycle: a predicate instance is typically created as `hypothetical` at first
mention, promoted to `asserted_true` when grounded, and may later become `disputed`
(conflicting sources) or `retracted` (overturned by new evidence).

---

## Vocabulary

Use these terms consistently throughout the book. Do not treat them as synonyms.

| Term                  | Definition |
|-----------------------|------------|
| **Entity type**       | A member of $T_\text{ent}$. Realized as a Python class inheriting from `EntityInstance`. Defines a class of entities: the fields they carry and their permitted roles in predicates. Example: `Person`, `Location`, `Moment`. |
| **Predicate type**    | A member of $T_\text{pred}$. Realized as a Python class inheriting from `BaseStatement`. Defines a class of propositions: their field schema, domain, range, traits, and truth status. Example: `LocatedIn`, `KnewAt`, `Treats`. |
| **Entity instance**   | A member of $V$ with $\tau(v) \in T_\text{ent}$. A concrete node — an instance of an `EntityInstance` subclass with an `id` and data fields. Example: a specific `Person` instance for Sherlock Holmes. |
| **Statement**         | A member of $V$ with $\tau(v) \in T_\text{pred}$. A concrete proposition — an instance of a `BaseStatement` subclass with an `id`, a `subject`, an `object_`, a `truth_status`, and metadata fields. Also a member of $E$ (the derived edge set). The term "edge instance" is an informal synonym when traversing the asserted graph. |
| **Field schema**      | $\Phi(t)$: the Pydantic model declaration of named fields and their types for type $t$. For predicate types, $\Phi$ includes `subject`, `object_`, and `truth_status` as distinguished fields whose type annotations constitute domain, range, and truth semantics. |
| **Domain**            | $\text{dom}(p)$ — the set of types permitted in the subject role for predicate $p$. Read from the type annotation of `subject` in $\Phi(p)$. |
| **Range**             | $\text{ran}(p)$ — the set of types permitted in the object role for predicate $p$. Read from the type annotation of `object_` in $\Phi(p)$. When $\text{ran}(p)$ includes a predicate type (i.e. a `BaseStatement` subclass), predicate $p$ enables higher-order claims. |
| **Trait**             | A declarative semantic property of a predicate type. Member of $\text{Tr}(p)$. Belongs to the schema, not to any instance. Realized as a Python mixin class. |
| **Schema**            | The tuple $(T,\ \Phi)$ together with trait declarations. Fixed at graph-design time. |
| **Instance graph**    | The tuple $(V,\ \tau)$. Populated at ingestion or reasoning time. |
| **Asserted graph**    | The subset of $E$ where `truth_status = asserted_true`, indexed for traversal. The first-order fact graph. |

### Terms to avoid or use carefully

- **Edge** — informal synonym for Statement when discussing traversal. Acceptable in casual prose; in definitions, use "Statement" or "predicate instance."
- **Relationship** — use this to mean a predicate instance, never a predicate type.
- **Node** — informal synonym for entity instance. Acceptable in casual prose, not in definitions.
- **Property** — overloaded; could mean a field on an instance or a trait on a predicate type. Be explicit.
- **Reification** — in this model, there is nothing to reify. Every predicate instance is already a member of $V$ and can be referenced by any predicate whose range includes its type. The word applies to models where edges and vertices are disjoint sorts; here they are not.

---

## Hard Rules

These rules follow from the formal definition and must not be violated in code
examples, schema designs, or explanatory prose.

**R1. Traits belong to predicate types, never to instances.** A predicate either
has `Transitive` or it does not. That is part of what the predicate *means*. An
individual instance cannot be transitive or non-transitive — that distinction
belongs to its type. In Python, traits are declared by inheriting the trait mixin
class alongside `BaseStatement`.

**R2. Metadata fields belong to instances, never to predicate types.** Provenance,
confidence, timestamps — all of these are facts about a particular assertion. They
live on the instance. The predicate type defines which fields are required (via
$\Phi$), but carries no values itself.

**R3. Every predicate instance is a directed, typed, truth-bearing proposition.**
A predicate instance carries `subject`, `object_`, `truth_status`, and whatever
additional fields $\Phi$ requires. It is simultaneously a proposition (it has
subject, predicate type, and object), an entity (it has an id and can be referenced),
and a potential edge in the asserted graph (if its truth_status is `asserted_true`).

**R4. Domain and range are sets of types, not instances.** Formally,
$\text{dom}(p) \subseteq T$, not $\subseteq V$. You constrain which *kinds* of
things may appear as subject or object, not which specific things.

**R5. Schema is fixed; instances are populated.** Nothing discovered during
ingestion changes $T$, $\Phi$, domain, range, or traits. If a new type seems
necessary mid-ingestion, that is a schema design problem, not an ingestion problem.

**R6. Domain and range constraints are enforced by the Python type system.** Types
are Python classes. Each predicate class declares its `subject` and `object_` fields
with concrete class annotations. Mypy enforces these constraints statically; Pydantic
enforces them at construction time. When a predicate permits multiple subject or
object types, declare a `Union` (e.g. `subject: Person | Organization`). The field
name `object_` is used throughout to avoid shadowing the Python builtin `object`.

**R7. Pydantic models for instances are frozen.** Use
`model_config = ConfigDict(frozen=True)`. Instances are facts; they must not be
mutated after construction.

**R8. Higher-order predication is a schema-level type declaration, not a runtime
promotion.** A predicate enables higher-order claims when its range includes a
predicate type (a `BaseStatement` subclass). This is declared once in $\Phi$ at
schema design time — e.g. `object_: BaseStatement` on `KnewAt`. There is no runtime
"promotion" of instances between layers. Every predicate instance is a referable
member of $V$ from birth; whether any other predicate can point at it is determined
by the type declarations in $\Phi$.

Do **not** use higher-order predication to attach provenance, confidence, or
epistemic metadata to a proposition. That is R2's job — such fields belong on the
instance directly, declared in $\Phi$. Higher-order predication is for *predicating
over* a proposition (knowing it, disputing it, supporting it), not for *annotating*
one. Using it for annotation reintroduces exactly the overhead this model exists to
reject (see Non-Goals: *Not RDF/OWL*).

---

## Python Enforcement Pattern

Entity types are `EntityInstance` subclasses; predicate types are `BaseStatement`
subclasses with trait mixins inherited alongside. Domain and range constraints are
expressed as Pydantic field type annotations — no custom validation logic is needed.
Traits are introspectable at runtime (`issubclass(LocatedIn, Transitive)`), and
`get_inverse` resolves declared inverse pairs. The full schema is in
`src/holmes_schema.py`.

---

## Non-Goals

**Not RDF / OWL.** In RDF, predicates are URIs and are themselves nodes; the graph
is a flat set of triples with no first-class edge objects. OWL adds description
logic semantics and open-world assumption. This model is a closed-world typed graph
where every predicate instance is a truth-bearing, field-carrying entity. RDF
requires reification or named graphs for higher-order predication; this model
handles it through type declarations on domain and range.

**Not Neo4j's informal property graph.** Neo4j allows arbitrary key-value properties
on edges without schema enforcement. This model requires a declared field schema
($\Phi$) and enforced domain/range constraints. The structure is similar; the
discipline is different.

**Not an entity-relationship diagram.** ER diagrams are a database design tool.
This is a runtime knowledge representation with provenance, epistemic scope, and
trait-based inference semantics.

**Not a general ontology language.** This model does not support open-world reasoning,
class hierarchies, disjointness axioms, or the full OWL trait vocabulary. Traits are
a small, fixed set of declarative properties. If a use case seems to require full
description logic, that is scope creep.

**Not a stringly-typed system.** Types are Python classes, not ID prefixes. Domain
and range enforcement is the job of the Python type system and Pydantic, not of
string parsing. Any pattern that encodes type information inside an identifier
string and then parses that string to enforce constraints is a violation of R6.

---

## Current Domain: Holmes Corpus

The worked example uses the Sherlock Holmes canon as domain.

- **Ontology authority**: Baker Street Wiki (https://bakerstreet.fandom.com)
- **Schema construction method**: inductive — built by annotating stories, not pre-designed
- **Primary stories**: "A Scandal in Bohemia", "The Speckled Band"
- **Provisional entity types**: `Person`, `Location`, `Object`, `Document`,
  `Moment`, `Event`, `Persona`, `Plan`
- **Higher-order predicates**: `KnewAt`, `Contradicts` — these take `BaseStatement`
  in their range, enabling epistemic and dispute tracking
- **Epistemic fields on predicate instances**: `moment`, `narrator_confidence`,
  provenance fields

---

# `src/holmes_schema.py`

Holmes Schema — Python realization of the typed graph schema for the
Sherlock Holmes canonical corpus (Conan Doyle, 60 stories).

Schema version: 0.7.0-draft
Authoritative ontology: Baker Street Wiki (https://bakerstreet.fandom.com)

Identity conventions
--------------------
Entities with an external authority (Person, Location, Object, Document):
    id IS the Baker Street Wiki URI.

Corpus-local entities (Event, Moment, Persona, Plan):
    id is a synthetic identifier, stable within the corpus but not grounded
    in any external authority.

Predicate instances (all BaseStatement subclasses):
    id is content-addressed — derived deterministically from
    (subject.id, predicate_type_name, object_.id). Two instances expressing
    the same proposition compute the same id by construction.

Unified Statement model
-----------------------
There is no separate Statement entity type. Every predicate instance inherits
from BaseStatement, which inherits from EntityInstance. A predicate instance
is simultaneously:

  - An entity: it has an id and is a member of V.
  - A proposition: it has subject, object_, and truth_status.
  - A potential edge in the asserted graph: if truth_status == asserted_true.

Higher-order predicates (KnewAt, Contradicts) are simply predicates whose
domain or range includes BaseStatement — the base class for all predicate
types. This is a type declaration, not a runtime promotion. Every predicate
instance is referable from birth; whether any other predicate can point at
it is determined by the type annotations in Phi.

The former Statement entity type, AssertionMixin, and the assertion field
group have been removed. truth_status is universal on BaseStatement,
eliminating the possibility of status drift between two representations
of the same proposition.

```python
import sys
from typing import ClassVar, ForwardRef, Generic, Literal, TypeVar, get_args, get_origin
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
```

## Truth status

`TruthStatus` is the graph's explicit commitment to a proposition. Every
predicate instance carries this field; the asserted graph is the projection
where `truth_status == ASSERTED_TRUE`. Under the unified model, *presence*
in the graph does not assert — `truth_status` carries the assertion explicitly.

Lifecycle: `hypothetical → asserted_true | asserted_false → disputed | retracted`

```python
class TruthStatus(str, Enum):
    """Graph-level commitment to a proposition.

    Every predicate instance carries truth_status. Under the unified model,
    presence does NOT assert — truth_status carries the assertion explicitly.

    Lifecycle: hypothetical → asserted_true | asserted_false → disputed | retracted
    """
    ASSERTED_TRUE = "asserted_true"
    ASSERTED_FALSE = "asserted_false"
    HYPOTHETICAL = "hypothetical"
    DISPUTED = "disputed"
    RETRACTED = "retracted"
```

## Trait markers

Traits are declarative semantic properties of predicate types — they belong
to the class, not to any instance. `Trait` must not inherit from `BaseModel`
so that Pydantic's `ModelMetaclass` stays in control of class construction.

`Inverse[P]` is generic and names the paired predicate type. `get_inverse`
resolves it at runtime by inspecting `__orig_bases__` — the list Python
preserves from the class statement, including un-evaluated generic arguments.

```python
class Trait:
    """Marker base for all semantic traits."""


class Transitive(Trait): ...
class Symmetric(Trait): ...
class Functional(Trait): ...
class InverseFunctional(Trait): ...

P = TypeVar('P', bound='BaseStatement')

class Inverse(Trait, Generic[P]):
    """This predicate is the inverse of P."""


def get_inverse(cls: type['BaseStatement']) -> type['BaseStatement'] | None:
    """Return the declared inverse predicate type, if any."""
    module = sys.modules[cls.__module__].__dict__
    for base in getattr(cls, '__orig_bases__', []):
        if get_origin(base) is Inverse:
            args = get_args(base)
            if args:
                arg = args[0]
                if isinstance(arg, str):
                    return module.get(arg)
                if isinstance(arg, ForwardRef):
                    return module.get(arg.__forward_arg__)
                return arg
    return None
```

## Base classes

`EntityInstance` is the root of the hierarchy: every object in the graph has
an `id`. For plain entities this is an authoritative URI or a corpus-local
synthetic identifier; for predicate instances it is content-addressed via
`statement_id`.

`BaseStatement` extends `EntityInstance` with `subject`, `object_`, and
`truth_status`. Because it inherits from `EntityInstance`, every predicate
instance is a full member of V — it can be referenced by higher-order
predicates like `KnewAt` without any special promotion.

```python
class EntityInstance(BaseModel):
    """Base class for all entity types (members of T_ent).

    Every instance has an id. For predicate instances (BaseStatement subclasses),
    id is content-addressed. For plain entity instances, id is either an
    authoritative URI or a corpus-local synthetic identifier."""
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
    id: str

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.id!r})"


def statement_id(subject_id: str, predicate_name: str, object_id: str) -> str:
    """Compute the content-addressed id for a predicate instance.

    Two instances expressing the same proposition compute the same id.
    This is the mechanism that makes mate-lookup O(1) and eliminates
    the possibility of duplicate representations."""
    return f"stmt:{subject_id}:{predicate_name}:{object_id}"


class BaseStatement(EntityInstance):
    """Base class for all predicate types (members of T_pred).

    A BaseStatement is simultaneously:
    - An entity (has an id, inherits from EntityInstance, is a member of V)
    - A proposition (has subject, object_, truth_status)
    - A potential edge in the asserted graph (if truth_status == asserted_true)

    This is the formal definition's E ⊆ V realized in Python's class hierarchy.

    Subclasses declare typed subject and object_ fields that constitute domain
    and range constraints, enforced by Pydantic at construction time (R6).

    truth_status defaults to HYPOTHETICAL. Ingestion pipelines create instances
    as hypothetical; a consensus/promotion pass sets truth_status based on
    evidence. The asserted graph is the projection where
    truth_status == ASSERTED_TRUE.
    """
    truth_status: TruthStatus = TruthStatus.HYPOTHETICAL
```

## Entity types (T_ent)

Plain entity classes cover the domain concepts that appear in the stories:
people, personas (disguises), locations, physical objects, documents, discrete
events, points in time, and goal-directed plans.

`Moment` carries a `narrator` field that doubles as an axis selector: absent
means the objective story timeline; present means that person's epistemic
timeline. One type handles both axes the corpus needs.

```python
class Person(EntityInstance):
    """A human character with an independent existence in the fictional world.
    id IS the Baker Street Wiki URI."""
    display_name: str


class Persona(EntityInstance):
    """An assumed identity adopted as a disguise. Not treated as a subtype of
    Person — predicates accepting both declare an explicit union (Person | Persona).
    id is a corpus-local synthetic identifier."""
    display_name: str


class Location(EntityInstance):
    """A physical place referenced in the stories.
    id IS the Baker Street Wiki URI."""
    display_name: str


class Object(EntityInstance):
    """A significant physical object.
    id IS the Baker Street Wiki URI."""
    display_name: str


class Document(EntityInstance):
    """A load-bearing text or image artifact: letter, photograph, telegram,
    newspaper. Distinct from Object because documents carry content and
    authenticity properties physical objects do not.
    id IS the Baker Street Wiki URI."""
    display_name: str
    story_id: str
    document_type: Literal["letter", "photograph", "telegram", "newspaper", "other"]


class Event(EntityInstance):
    """A discrete occurrence within a story: an action, observation, revelation.
    id is corpus-local."""
    story_id: str
    description: str


class Moment(EntityInstance):
    """A named point on a timeline.

    narrator absent  → objective story timeline (when something happened).
    narrator present → that Person's epistemic timeline (when they learned it).

    One type carries both axes the corpus demands. id is corpus-local."""
    story_id: str
    label: str
    narrator: Person | None = None


class Plan(EntityInstance):
    """A goal-directed sequence of actions attributed to an agent.
    id is corpus-local."""
    provisional: ClassVar[bool] = True
    story_id: str
    description: str
    goal: str | None = None
```

## Field group mixins (Φ components)

Field groups are reusable bundles of fields — Pydantic mixins that predicate
classes inherit alongside `BaseStatement`. Named "field groups" rather than
"trait groups" to avoid collision with the formal trait vocabulary.

`ProvenanceMixin` tracks where an assertion comes from in the text.
`EpistemicMixin` records the narrator's in-world certainty, which is distinct
from the pipeline's `extraction_confidence`.

`AssertionMixin` has been removed. `truth_status` is now universal on
`BaseStatement`, eliminating the status-drift problem that arose when two
objects (an edge and a Statement entity) could carry `truth_status`
independently — status now lives in exactly one place.

```python
class ProvenanceMixin(BaseModel):
    """Source-tracing fields. Required on every evidential predicate.

    extraction_confidence: pipeline confidence that the text asserts this.
    asserting_narrator: who in the story reported it; absent if the source
        is the omniscient narrator or is unattributable."""
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
    story_id: str
    paragraph_index: int
    asserting_narrator: Person | None = None
    extraction_method: str
    extraction_confidence: float = Field(ge=0.0, le=1.0)


class EpistemicMixin(BaseModel):
    """In-world certainty. Distinct from extraction_confidence (pipeline) and
    from truth_status (graph-level commitment).

    narrator_confidence: how certain the in-story narrator is at narration time."""
    model_config = ConfigDict(frozen=True)
    narrator_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
```

## Predicate types (T_pred)

Each predicate class inherits from `BaseStatement` (which inherits from
`EntityInstance`), so every instance has an `id`, `subject`, `object_`, and
`truth_status`. The `id` should be computed via `statement_id()` at
construction.

MRO convention: `BaseStatement` first, then field group mixins, then Trait
and `Inverse` markers last.

Higher-order predicates (`KnewAt`, `Contradicts`) accept `BaseStatement` as
their subject or object type — any predicate instance can fill that role.
This is a type declaration, not a runtime mechanism: every predicate instance
is referable from birth.

```python
class AssociatedWith(BaseStatement, ProvenanceMixin):
    """Person is habitually connected to a location."""
    subject: Person
    object_: Location


class Knows(BaseStatement, ProvenanceMixin, EpistemicMixin, Symmetric):
    """Person has an acquaintance or professional relationship with another.
    Deliberately coarse; split into sub-predicates only if the corpus rewards it.
    Symmetric: if Holmes knows Watson, Watson knows Holmes."""
    subject: Person
    object_: Person


class LocatedIn(BaseStatement, ProvenanceMixin, Transitive):
    """A location is situated within another location. Transitive.
    Asserted edges carry source provenance; inferred transitive edges carry
    inference provenance instead."""
    subject: Location
    object_: Location


class Involves(BaseStatement, ProvenanceMixin):
    """Event involves an entity as a participant. Accepts Person or Persona —
    if Holmes attended in disguise, the Persona is the participant visible to
    other characters; the real Person is recoverable via HasTrueIdentity."""
    subject: Event
    object_: Person | Persona


class OccurredAt(BaseStatement, ProvenanceMixin):
    """Event is anchored to its objective point in time. The Moment's narrator
    field must be absent (objective timeline). Distinct from KnewAt."""
    subject: Event
    object_: Moment


class KnewAt(BaseStatement, ProvenanceMixin, EpistemicMixin):
    """Person came to know a proposition at a given Moment.

    Higher-order: object_ is BaseStatement, meaning any predicate instance
    can be the known proposition. The knower is the subject; the proposition
    is the object; the moment is a typed field on the instance.

    truth_status on this instance is the graph's commitment to the claim
    "Person knew this at that moment" — distinct from the object_'s own
    truth_status, which is the commitment to the proposition itself.
    Watson can know (truth_status=asserted_true on KnewAt) a proposition
    that is false (truth_status=asserted_false on the object_)."""
    subject: Person
    object_: BaseStatement    # higher-order: range includes all predicate types
    moment: Moment


class DisguisedAs(BaseStatement, ProvenanceMixin, EpistemicMixin,
                  Inverse['HasTrueIdentity']):
    """Real Person adopted a Persona. A person may hold many disguises.
    Inverse of HasTrueIdentity."""
    subject: Person
    object_: Persona


class HasTrueIdentity(BaseStatement, ProvenanceMixin, EpistemicMixin,
                      Functional, Inverse[DisguisedAs]):
    """A Persona conceals exactly one real Person. Functional: a persona
    cannot conceal more than one person. Inverse of DisguisedAs."""
    subject: Persona
    object_: Person


class Possesses(BaseStatement, ProvenanceMixin, EpistemicMixin):
    """Person possesses an Object or Document. Added when the photograph
    in Bohemia forced the issue."""
    subject: Person
    object_: Object | Document


class Contradicts(BaseStatement, ProvenanceMixin, Symmetric):
    """One proposition directly contradicts another. Symmetric.

    Higher-order: both subject and object_ are BaseStatement, meaning any
    predicate instance can participate. Used to surface conflicts between
    belief states or between a character's belief and ground truth."""
    provisional: ClassVar[bool] = True
    subject: BaseStatement    # higher-order
    object_: BaseStatement    # higher-order


class Executes(BaseStatement, ProvenanceMixin):
    """Person is the agent responsible for carrying out a Plan."""
    provisional: ClassVar[bool] = True
    subject: Person
    object_: Plan
```

## Forward reference resolution

Pydantic's `model_rebuild()` resolves any `ForwardRef` annotations left from
the class definitions above — in particular the `Inverse['HasTrueIdentity']`
string annotation on `DisguisedAs`, which references a class declared later.
This call must come after all classes are defined.

```python
for _cls in [
    Person, Persona, Location, Object, Document,
    Event, Moment, Plan,
    AssociatedWith, Knows, LocatedIn, Involves, OccurredAt,
    KnewAt, DisguisedAs, HasTrueIdentity, Possesses, Contradicts, Executes,
]:
    _cls.model_rebuild()
```

---

# `src/scandal_instances.py`

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

```python
from holmes_schema import (
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
```

## Provenance shorthand

Every predicate instance in this file was extracted manually from the
Project Gutenberg text of *A Scandal in Bohemia*. `_p(para)` returns the
shared provenance fields plus `truth_status` (defaulting to ASSERTED_TRUE
since all manual extractions from this story are ground truth). `_sid()`
computes the content-addressed id for a predicate instance.

```python
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
```

## Persons

Five people with speaking roles or decisive agency. Baker Street Wiki URIs
serve as canonical IDs for all five — they are externally authoritative
entities, not corpus-local constructs.

```python
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
```

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

```python
count_von_kramm = Persona(
    id="sib:persona:count_von_kramm",
    display_name="Count Von Kramm",
)
nonconformist_clergyman = Persona(
    id="sib:persona:nonconformist_clergyman",
    display_name="Nonconformist Clergyman",
)
```

## Locations

The geographic chain London → St. John's Wood → Briony Lodge is the one
transitive `LocatedIn` chain this story exercises.

```python
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
```

## Objects and Documents

**The photograph** is the story's MacGuffin — a cabinet-size photograph
of Irene Adler and the King together (para 78, 119).

**The advance note** is the unsigned, undated letter delivered to Holmes
before the King's visit (para 22–23).

**Irene's farewell letter** is left at Briony Lodge for Holmes to find the
morning of March 22 (para 246–247).

```python
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
```

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

```python
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
```

## Moments

Moments without a `narrator` sit on the **objective story timeline**.
Moments with a narrator sit on that person's **epistemic timeline**.

```python
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
```

## Structural edges

### Geographic containment (`LocatedIn`, Transitive)

The transitive chain `briony_lodge → st_johns_wood → london` means that
any reasoner following `LocatedIn` edges transitively can derive
`briony_lodge LocatedIn london` without an explicit edge.

Every predicate instance now carries an `id` (content-addressed via
`_sid()`) and a `truth_status` (defaulting to ASSERTED_TRUE via `_p()`).
These are the new universal fields from the unified Statement model.

```python
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
```

### Habitual associations (`AssociatedWith`)

```python
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
```

## Social edges (`Knows`, Symmetric)

`Knows` is symmetric — one edge suffices for a mutual acquaintance.

```python
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
```

## Identity edges (`DisguisedAs` / `HasTrueIdentity`)

Each disguise requires a forward edge (`DisguisedAs`) and its inverse
(`HasTrueIdentity`). `HasTrueIdentity` is also `Functional`.

Under the unified model, these edges are directly referenceable by
`KnewAt` — they ARE the propositions Watson comes to know, without
any intermediate Statement entity.

```python
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
```

## Possession (`Possesses`)

The photograph's provenance is the King's direct testimony (para 78).
`asserting_narrator` is None — Watson is reporting what the King said.

```python
e_irene_possesses_photo = Possesses(
    id=_sid(irene_adler, Possesses, irene_photograph),
    subject=irene_adler, object_=irene_photograph,
    **{**_p(78), "extraction_confidence": 0.95},
)
```

## Event structure (`OccurredAt`, `Involves`)

`OccurredAt` anchors each event to its objective moment. `Involves` names
each participant.

Note that the King *arrives* as Count Von Kramm, so the `Involves` edge
for `evt_kings_visit` uses the `count_von_kramm` Persona as the visible
participant. Similarly, Holmes attends the wedding (para 144) and the fake
fire (para 196) as the clergyman persona.

```python
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
```

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

```python
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
```

---

# `src/graph.py`

graph.py — in-memory typed graph over BaseStatement/EntityInstance objects.

No database, no MCP server. Load a set of instances, build indexes, run
BFS and named queries directly against the Python objects.

Typical usage:

    from graph import Graph
    import scandal_instances
    g = Graph.from_module(scandal_instances)
    g.bfs(['sib:persona:count_von_kramm'], max_hops=2)

```python
from __future__ import annotations
from collections import defaultdict
from typing import Iterable, Type
```

## Helpers

Duck-typed predicates used during graph construction. Avoiding a direct
import of `EntityInstance` and `BaseStatement` keeps `graph.py` decoupled
from the schema module — any object that has the right attributes will be
indexed correctly.

```python
def _is_entity(obj):
    return hasattr(obj, 'id') and not callable(obj)

def _is_statement(obj):
    return hasattr(obj, 'subject') and hasattr(obj, 'object_') and hasattr(obj, 'truth_status')
```

## Graph

`Graph` is an in-memory knowledge graph indexed for O(1) neighbor lookup.
Instances are bucketed into three indexes: `by_id` for direct access,
`out_edges` keyed by `subject.id` for forward traversal, and `in_edges`
keyed by `object_.id` for backward traversal.

Because predicate instances are also entities under the unified Statement
model, they are indexed in `by_id` and can themselves appear as the
subject or object of higher-order predicates.

```python
class Graph:

    def __init__(self, instances: Iterable):
        self.by_id: dict = {}
        self.out_edges: dict[str, list] = defaultdict(list)   # subject.id -> [stmt]
        self.in_edges: dict[str, list] = defaultdict(list)    # object_.id -> [stmt]

        for inst in instances:
            if not _is_entity(inst):
                continue
            self.by_id[inst.id] = inst
            if _is_statement(inst):
                self.out_edges[inst.subject.id].append(inst)
                self.in_edges[inst.object_.id].append(inst)

    @classmethod
    def from_module(cls, module) -> Graph:
        """Build a Graph from all EntityInstance values in a module's namespace."""
        return cls(
            v for v in vars(module).values()
            if _is_entity(v) and not isinstance(v, type)
        )

    # ── Basic traversal ────────────────────────────────────────────────────

    def edges_from(self, entity_id: str,
                   pred_type=None,
                   truth=None) -> list:
        """Outward edges from entity_id, optionally filtered by type and truth_status."""
        edges = self.out_edges.get(entity_id, [])
        if pred_type:
            edges = [e for e in edges if isinstance(e, pred_type)]
        if truth:
            truth_set = {truth} if not isinstance(truth, (set, list, tuple)) else set(truth)
            edges = [e for e in edges if e.truth_status.value in truth_set or e.truth_status in truth_set]
        return edges

    def edges_to(self, entity_id: str,
                 pred_type=None,
                 truth=None) -> list:
        """Inward edges to entity_id, optionally filtered by type and truth_status."""
        edges = self.in_edges.get(entity_id, [])
        if pred_type:
            edges = [e for e in edges if isinstance(e, pred_type)]
        if truth:
            truth_set = {truth} if not isinstance(truth, (set, list, tuple)) else set(truth)
            edges = [e for e in edges if e.truth_status.value in truth_set or e.truth_status in truth_set]
        return edges

    # ── BFS ───────────────────────────────────────────────────────────────

    def bfs(self, seed_ids: list[str],
            max_hops: int = 3,
            pred_types=None,
            truth_values=('asserted_true',)) -> list[set[str]]:
        """BFS from seed_ids. Returns a list of sets — one per hop layer
        (layer 0 = seeds). Traverses outward edges only.

        truth_values: tuple of truth_status values to follow. Default is
        asserted-only (the first-order asserted graph). Pass
        ('asserted_true', 'disputed', 'hypothetical') to traverse all.

        pred_types: if given, a list of predicate classes to follow;
        others are ignored. None means follow all.
        """
        visited: set[str] = set(seed_ids)
        frontier: set[str] = set(seed_ids)
        layers: list[set[str]] = [set(seed_ids)]

        for _ in range(max_hops):
            next_frontier: set[str] = set()
            for eid in frontier:
                for edge in self.out_edges.get(eid, []):
                    if pred_types and not isinstance(edge, tuple(pred_types)):
                        continue
                    if edge.truth_status.value not in truth_values:
                        continue
                    # Navigate to the object entity.
                    obj_id = edge.object_.id
                    if obj_id not in visited:
                        visited.add(obj_id)
                        next_frontier.add(obj_id)
                    # The edge itself is in V; add it too so higher-order
                    # predicates can follow it in later hops.
                    if edge.id not in visited:
                        visited.add(edge.id)
                        next_frontier.add(edge.id)
            layers.append(next_frontier)
            frontier = next_frontier
            if not frontier:
                break

        return layers

    # ── Transitive closure ────────────────────────────────────────────────

    def transitive_closure(self, entity_id: str,
                           pred_type,
                           truth_values=('asserted_true',)) -> set[str]:
        """All entities reachable from entity_id by following pred_type
        transitively. Does not include entity_id itself."""
        visited: set[str] = set()
        frontier: set[str] = {entity_id}
        while frontier:
            next_f: set[str] = set()
            for eid in frontier:
                for edge in self.out_edges.get(eid, []):
                    if not isinstance(edge, pred_type):
                        continue
                    if edge.truth_status.value not in truth_values:
                        continue
                    obj_id = edge.object_.id
                    if obj_id not in visited:
                        visited.add(obj_id)
                        next_f.add(obj_id)
            frontier = next_f
        return visited

    # ── Display helpers ────────────────────────────────────────────────────

    def describe(self, entity_id: str) -> str:
        """Human-readable description of an instance by id."""
        inst = self.by_id.get(entity_id)
        if inst is None:
            return f"<not found: {entity_id}>"
        if _is_statement(inst):
            subj = getattr(inst.subject, 'display_name', inst.subject.id)
            obj  = getattr(inst.object_, 'display_name', inst.object_.id)
            return f"{type(inst).__name__}({subj} → {obj})"
        name = getattr(inst, 'display_name', None) or getattr(inst, 'label', None) or entity_id
        return f"{type(inst).__name__}({name})"

    def print_edges(self, edges: list, indent: int = 2) -> None:
        pad = ' ' * indent
        for e in edges:
            subj = getattr(e.subject, 'display_name', e.subject.id)
            obj  = getattr(e.object_, 'display_name', None) or self.describe(e.object_.id)
            ts   = e.truth_status.value
            print(f"{pad}{type(e).__name__}:  {subj}  →  {obj}  [{ts}]")
```

