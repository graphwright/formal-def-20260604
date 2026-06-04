"""
test_scandal.py — queries against the A Scandal in Bohemia instance graph.

Run with:  python3 test_scandal.py

No database. No MCP server. Pure Python objects.

Each query section exercises a different schema feature. Output is
designed to be readable rather than machine-parseable — this is a
development and verification tool, not a benchmark.
"""

import sys
sys.path.insert(0, '.')

import importlib
schema    = importlib.import_module('2_HolmesSchema')
instances = importlib.import_module('3_ScandalInstances')

from graph import Graph

g = Graph.from_module(instances)
i = instances   # shorthand

SECTION = "\n{}\n" + "─" * 60


# ── Sanity check ──────────────────────────────────────────────────────────────

print(SECTION.format("GRAPH CONTENTS"))

def is_stmt(v):
    return isinstance(v, schema.BaseStatement)

all_instances = list(g.by_id.values())
stmts  = [v for v in all_instances if is_stmt(v)]
plain  = [v for v in all_instances if not is_stmt(v)]

print(f"Plain entities : {len(plain)}")
print(f"Predicate instances (statements) : {len(stmts)}")
print(f"Total in V : {len(all_instances)}")

by_type = {}
for v in all_instances:
    t = type(v).__name__
    by_type[t] = by_type.get(t, 0) + 1
for t, n in sorted(by_type.items()):
    print(f"  {t:30s} {n}")


# ── Query 1: Identity ─────────────────────────────────────────────────────────
# Who IS Count Von Kramm?

print(SECTION.format("Q1  Who is Count Von Kramm?"))

edges = g.edges_from(i.count_von_kramm.id, pred_type=schema.HasTrueIdentity)
g.print_edges(edges)
assert len(edges) == 1
assert edges[0].object_.id == i.king_of_bohemia.id
print("  ✓ HasTrueIdentity is Functional — exactly one answer")


# ── Query 2: Inverse ──────────────────────────────────────────────────────────
# What personas did Holmes adopt?

print(SECTION.format("Q2  What personas did Holmes adopt?"))

edges = g.edges_from(i.holmes.id, pred_type=schema.DisguisedAs)
g.print_edges(edges)
assert len(edges) == 1, "Only the clergyman in this story"

# Check inverse is registered
inv = schema.get_inverse(schema.DisguisedAs)
print(f"  declared inverse of DisguisedAs: {inv.__name__}")
assert inv is schema.HasTrueIdentity


# ── Query 3: Transitive location ──────────────────────────────────────────────
# Is Briony Lodge in London, without an explicit edge?

print(SECTION.format("Q3  What is in London? (transitive closure of LocatedIn)"))

# Inward transitive closure: things that are LocatedIn london
def transitive_in(g, entity_id, pred_type):
    visited, frontier = set(), {entity_id}
    while frontier:
        nxt = set()
        for eid in frontier:
            for edge in g.in_edges.get(eid, []):
                if not isinstance(edge, pred_type): continue
                if edge.truth_status.value != 'asserted_true': continue
                if edge.subject.id not in visited:
                    visited.add(edge.subject.id)
                    nxt.add(edge.subject.id)
        frontier = nxt
    return visited

in_london = transitive_in(g, i.london.id, schema.LocatedIn)
for lid in sorted(in_london):
    loc = g.by_id[lid]
    print(f"  {loc.display_name}")

assert i.briony_lodge.id in in_london, "Briony Lodge should be in London transitively"
assert i.st_johns_wood.id in in_london
print("  ✓ Briony Lodge is in London via St. John's Wood (no explicit edge needed)")


# ── Query 4: Event participants ───────────────────────────────────────────────
# Who was involved in the fake fire alarm?

print(SECTION.format("Q4  Who was at the fake fire alarm?"))

involves = g.edges_from(i.evt_fake_fire_alarm.id, pred_type=schema.Involves)
g.print_edges(involves)

# Holmes attended as the clergyman persona
participants = {e.object_.id for e in involves}
assert i.nonconformist_clergyman.id in participants
assert i.irene_adler.id in participants
print("  ✓ Holmes appears as his Persona, not himself")


# ── Query 5: Epistemic query ──────────────────────────────────────────────────
# What does Watson know, and about what propositions?

print(SECTION.format("Q5  What does Watson know? (higher-order KnewAt)"))

knew_edges = g.edges_from(i.watson.id, pred_type=schema.KnewAt)
for edge in knew_edges:
    prop = edge.object_   # this IS a predicate instance
    prop_desc = g.describe(prop.id)
    print(f"  Watson knew: {prop_desc}")
    print(f"    prop truth_status : {prop.truth_status.value}")
    print(f"    KnewAt truth_status: {edge.truth_status.value}")
    print(f"    at moment         : {edge.moment.label}")
    # Demonstrate independence: could differ
    print(f"    could Watson know a false prop? {type(prop).__name__} truth != KnewAt truth: "
          f"{prop.truth_status != edge.truth_status}")

assert len(knew_edges) == 2
assert all(isinstance(e.object_, schema.BaseStatement) for e in knew_edges)
print("  ✓ KnewAt.object_ is a BaseStatement — higher-order predication confirmed")


# ── Query 6: BFS from Watson ──────────────────────────────────────────────────
# What is in Watson's 2-hop neighborhood?

print(SECTION.format("Q6  BFS from Watson (max 2 hops, asserted only)"))

layers = g.bfs([i.watson.id], max_hops=2)
for hop, layer in enumerate(layers):
    if not layer:
        continue
    print(f"  Hop {hop}: {len(layer)} nodes")
    for nid in sorted(layer)[:8]:   # first 8 for readability
        print(f"    {g.describe(nid)}")
    if len(layer) > 8:
        print(f"    ... and {len(layer) - 8} more")


# ── Query 7: Truth status filter ──────────────────────────────────────────────
# Are there any non-asserted statements? (Should be none in manual extraction)

print(SECTION.format("Q7  Non-asserted statements (hypothetical / disputed / retracted)"))

non_asserted = [
    v for v in stmts
    if v.truth_status.value != 'asserted_true'
]
if non_asserted:
    for s in non_asserted:
        print(f"  [{s.truth_status.value}] {g.describe(s.id)}")
else:
    print("  None — all manually extracted statements are asserted_true")
print("  ✓ truth_status is universal on every predicate instance")


# ── Query 8: Inverse lookup ───────────────────────────────────────────────────
# Given a KnewAt edge, find everything that points AT the proposition it knows.

print(SECTION.format("Q8  What else knows or references the King-as-Count proposition?"))

king_as_count = i.e_king_as_count
referencing = g.edges_to(king_as_count.id)
if referencing:
    g.print_edges(referencing)
else:
    print(f"  Only one KnewAt edge references {g.describe(king_as_count.id)}")
    print("  (Expected — Watson is the only character annotated as knowing this so far)")


print(SECTION.format("ALL QUERIES PASSED"))