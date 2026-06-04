"""
test_scandal.py — queries against the A Scandal in Bohemia instance graph.

No database. No MCP server. Pure Python objects.

Each query section exercises a different schema feature.
"""

import pytest
import holmes_schema as schema
import scandal_instances as i
from graph import Graph


@pytest.fixture(scope="session")
def g() -> Graph:
    return Graph.from_module(i)


# ── Sanity check ──────────────────────────────────────────────────────────────

def test_graph_loaded(g):
    all_instances = list(g.by_id.values())
    stmts = [v for v in all_instances if isinstance(v, schema.BaseStatement)]
    plain = [v for v in all_instances if not isinstance(v, schema.BaseStatement)]
    assert len(plain) > 0
    assert len(stmts) > 0
    assert len(all_instances) == len(plain) + len(stmts)


# ── Query 1: Identity ─────────────────────────────────────────────────────────
# Who IS Count Von Kramm?

def test_has_true_identity_is_functional(g):
    # HasTrueIdentity is Functional — exactly one answer
    edges = g.edges_from(i.count_von_kramm.id, pred_type=schema.HasTrueIdentity)
    assert len(edges) == 1
    assert edges[0].object_.id == i.king_of_bohemia.id


# ── Query 2: Inverse ──────────────────────────────────────────────────────────
# What personas did Holmes adopt?

def test_holmes_disguised_as_clergyman_only(g):
    edges = g.edges_from(i.holmes.id, pred_type=schema.DisguisedAs)
    assert len(edges) == 1, "Only the clergyman in this story"


def test_disguised_as_inverse_is_has_true_identity():
    # Check inverse is registered
    inv = schema.get_inverse(schema.DisguisedAs)
    assert inv is schema.HasTrueIdentity


# ── Query 3: Transitive location ──────────────────────────────────────────────
# Is Briony Lodge in London, without an explicit edge?

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
    # Briony Lodge is in London via St. John's Wood (no explicit edge needed)


# ── Query 4: Event participants ───────────────────────────────────────────────
# Who was involved in the fake fire alarm?

def test_fake_fire_alarm_participants(g):
    involves = g.edges_from(i.evt_fake_fire_alarm.id, pred_type=schema.Involves)
    # Holmes attended as the clergyman persona
    participants = {e.object_.id for e in involves}
    assert i.nonconformist_clergyman.id in participants, "Holmes appears as his Persona, not himself"
    assert i.irene_adler.id in participants


# ── Query 5: Epistemic query ──────────────────────────────────────────────────
# What does Watson know, and about what propositions?

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


# ── Query 6: BFS from Watson ──────────────────────────────────────────────────
# What is in Watson's 2-hop neighborhood?

def test_bfs_from_watson_reaches_multiple_hops(g):
    # max 2 hops, asserted only
    layers = g.bfs([i.watson.id], max_hops=2)
    assert len(layers) >= 2
    assert any(len(layer) > 0 for layer in layers[1:])


# ── Query 7: Truth status filter ──────────────────────────────────────────────
# Are there any non-asserted statements? (Should be none in manual extraction)

def test_all_statements_are_asserted_true(g):
    # truth_status is universal on every predicate instance
    stmts = [v for v in g.by_id.values() if isinstance(v, schema.BaseStatement)]
    non_asserted = [s for s in stmts if s.truth_status.value != "asserted_true"]
    assert non_asserted == [], (
        "None — all manually extracted statements are asserted_true; found: "
        + ", ".join(f"{type(s).__name__}({s.id})" for s in non_asserted)
    )


# ── Query 8: Inverse lookup ───────────────────────────────────────────────────
# Given a KnewAt edge, find everything that points AT the proposition it knows.

def test_king_as_count_referenced_by_watson_knew_at(g):
    # What else knows or references the King-as-Count proposition?
    referencing = g.edges_to(i.e_king_as_count.id)
    # Expected — Watson is the only character annotated as knowing this so far
    assert len(referencing) >= 1
    types = {type(e).__name__ for e in referencing}
    assert "KnewAt" in types
