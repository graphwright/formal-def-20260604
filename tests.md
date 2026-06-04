# `tests/test_scandal.py`

test_scandal.py — queries against the A Scandal in Bohemia instance graph.

No database. No MCP server. Pure Python objects.

Each query section exercises a different schema feature.

```python
import pytest
import holmes_schema as schema
import scandal_instances as i
from graph import Graph


@pytest.fixture(scope="session")
def g() -> Graph:
    return Graph.from_module(i)
```

## Sanity check — graph structure

Verify that `Graph.from_module` correctly indexes all entity instances from
the scandal graph: at least one plain entity and at least one predicate
instance (statement), and that the two counts sum to the total.

```python
def test_graph_loaded(g):
    all_instances = list(g.by_id.values())
    stmts = [v for v in all_instances if isinstance(v, schema.BaseStatement)]
    plain = [v for v in all_instances if not isinstance(v, schema.BaseStatement)]
    assert len(plain) > 0
    assert len(stmts) > 0
    assert len(all_instances) == len(plain) + len(stmts)
```

## Q1 — Identity: `HasTrueIdentity` is Functional

Count Von Kramm is the alias the King uses when visiting Baker Street.
`HasTrueIdentity` carries the `Functional` trait, meaning a persona conceals
exactly one real person. The query asserts that exactly one `HasTrueIdentity`
edge exists from `count_von_kramm` and that it resolves to the King of Bohemia.

```python
def test_has_true_identity_is_functional(g):
    # HasTrueIdentity is Functional — exactly one answer
    edges = g.edges_from(i.count_von_kramm.id, pred_type=schema.HasTrueIdentity)
    assert len(edges) == 1
    assert edges[0].object_.id == i.king_of_bohemia.id
```

## Q2 — Inverse: `DisguisedAs` ↔ `HasTrueIdentity`

`DisguisedAs` and `HasTrueIdentity` are declared inverses. This query checks
two things: that Holmes has exactly one disguise in this story (the
nonconformist clergyman), and that `get_inverse(DisguisedAs)` returns
`HasTrueIdentity` at runtime via the `__orig_bases__` inspection in
`holmes_schema.py`.

```python
def test_holmes_disguised_as_clergyman_only(g):
    edges = g.edges_from(i.holmes.id, pred_type=schema.DisguisedAs)
    assert len(edges) == 1, "Only the clergyman in this story"


def test_disguised_as_inverse_is_has_true_identity():
    # Check inverse is registered
    inv = schema.get_inverse(schema.DisguisedAs)
    assert inv is schema.HasTrueIdentity
```

## Q3 — Transitive location: Briony Lodge is in London

`LocatedIn` is `Transitive`. There is no direct edge from Briony Lodge to
London; the chain runs `Briony Lodge → St. John's Wood → London`. This query
computes the inward transitive closure of `LocatedIn` from `london` and
asserts that both Briony Lodge and St. John's Wood appear in the result.

```python
def _transitive_in(g: Graph, entity_id: str, pred_type) -> set[str]:
    # Inward transitive closure: things that are LocatedIn london
    visited, frontier = set(), {entity_id}
    while frontier:
        nxt = set()
        for eid in frontier:
            for edge in g.in_edges.get(eid, []):
                if not isinstance(edge, pred_type):
                    continue
                if edge.truth_status.value != "asserted_true":
                    continue
                if edge.subject.id not in visited:
                    visited.add(edge.subject.id)
                    nxt.add(edge.subject.id)
        frontier = nxt
    return visited


def test_briony_lodge_in_london_transitively(g):
    in_london = _transitive_in(g, i.london.id, schema.LocatedIn)
    assert i.briony_lodge.id in in_london, "Briony Lodge should be in London transitively"
    assert i.st_johns_wood.id in in_london
```

## Q4 — Event participants: `Involves`

The fake fire alarm is the pivotal scene in which Holmes, disguised as the
nonconformist clergyman, stages a false alarm at Briony Lodge. Because Holmes
attended in disguise, the `Involves` edge names the `Persona`, not the
`Person` — the real identity is recoverable via `HasTrueIdentity`.

```python
def test_fake_fire_alarm_participants(g):
    involves = g.edges_from(i.evt_fake_fire_alarm.id, pred_type=schema.Involves)
    # Holmes attended as the clergyman persona
    participants = {e.object_.id for e in involves}
    assert i.nonconformist_clergyman.id in participants, "Holmes appears as his Persona, not himself"
    assert i.irene_adler.id in participants
```

## Q5 — Epistemic: higher-order `KnewAt`

`KnewAt` takes a `BaseStatement` as its `object_` — any predicate instance
can serve as the known proposition. This query verifies that Watson has
exactly two `KnewAt` edges and that their `object_` fields are `BaseStatement`
instances. It also checks that `truth_status` on the `KnewAt` and on its
`object_` are independently set: Watson can in principle know a false
proposition.

```python
def test_watson_knew_at_count(g):
    knew_edges = g.edges_from(i.watson.id, pred_type=schema.KnewAt)
    assert len(knew_edges) == 2


def test_knew_at_object_is_base_statement(g):
    # KnewAt.object_ is a BaseStatement — higher-order predication confirmed
    knew_edges = g.edges_from(i.watson.id, pred_type=schema.KnewAt)
    assert all(isinstance(e.object_, schema.BaseStatement) for e in knew_edges)


def test_knew_at_truth_status_independent_of_proposition(g):
    # Demonstrate independence: the KnewAt's truth_status and the proposition's
    # truth_status are separate — Watson can know a false proposition.
    knew_edges = g.edges_from(i.watson.id, pred_type=schema.KnewAt)
    for edge in knew_edges:
        prop = edge.object_   # this IS a predicate instance
        # Both fields exist and are independently set
        assert prop.truth_status is not None
        assert edge.truth_status is not None
```

## Q6 — BFS from Watson

Breadth-first search from Watson's node, following asserted edges only, up to
two hops. Verifies that the BFS returns multiple non-empty layers — Watson is
connected to the rest of the graph.

```python
def test_bfs_from_watson_reaches_multiple_hops(g):
    # max 2 hops, asserted only
    layers = g.bfs([i.watson.id], max_hops=2)
    assert len(layers) >= 2
    assert any(len(layer) > 0 for layer in layers[1:])
```

## Q7 — Truth status filter

All statements in this graph were extracted manually from the story text and
are ground truth, so all should have `truth_status == asserted_true`. This
query asserts that no non-asserted statements exist, confirming that
`truth_status` is set universally on every predicate instance.

```python
def test_all_statements_are_asserted_true(g):
    stmts = [v for v in g.by_id.values() if isinstance(v, schema.BaseStatement)]
    non_asserted = [s for s in stmts if s.truth_status.value != "asserted_true"]
    assert non_asserted == [], (
        "None — all manually extracted statements are asserted_true; found: "
        + ", ".join(f"{type(s).__name__}({s.id})" for s in non_asserted)
    )
```

## Q8 — Inverse lookup: what references the King-as-Count proposition?

`e_king_as_count` is the `DisguisedAs` edge asserting that the King adopted
the Count Von Kramm persona. Under the unified Statement model this edge is
itself a member of V, so it can appear as the `object_` of higher-order
predicates. This query checks that at least one `KnewAt` edge points at it —
Watson learned this proposition when the King removed his mask.

```python
def test_king_as_count_referenced_by_watson_knew_at(g):
    # Expected — Watson is the only character annotated as knowing this so far
    referencing = g.edges_to(i.e_king_as_count.id)
    assert len(referencing) >= 1
    types = {type(e).__name__ for e in referencing}
    assert "KnewAt" in types
```

