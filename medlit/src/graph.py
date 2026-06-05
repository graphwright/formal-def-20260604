"""
medlit_graph.py — in-memory graph over medlit JSONL records.

No database, no MCP server, no LLM. Load migrated JSONL files, build
indexes, run queries directly against the Python objects.

Typical usage:
    from medlit_graph import MedlitGraph
    g = MedlitGraph.from_jsonl_dir("data/migrated/")
    treats = g.edges_from("RxNorm:1187832", predicate="TREATS")

Differences from Holmes graph.py:
  - Relationships carry subject_id/object_id strings, not typed objects.
    Traversal resolves them through the entity index on demand.
  - Records are stored as plain dicts rather than frozen Pydantic instances
    for speed during bulk loading. Pydantic validation is a separate step
    (see validate_against_schema()).
  - Multiple JSONL files are loaded and merged into one graph.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Iterator


"""
## Helpers

Duck-typed predicates for classifying JSONL records during graph
construction. A record is a *relationship* if it carries `subject_id`,
`predicate`, and `object_id`. A record is an *entity* if it carries
`entity_type` or an `entity_id` without a `predicate`. Records that match
neither (schema metadata, comment lines) are silently ignored.
"""


def _is_relationship(record: dict) -> bool:
    return all(k in record for k in ("subject_id", "predicate", "object_id"))


def _is_entity(record: dict) -> bool:
    return "entity_type" in record or (
        "entity_id" in record and "predicate" not in record
    )


"""
## MedlitGraph

In-memory knowledge graph indexed for O(1) neighbour lookup over medlit
JSONL records. Unlike the Holmes `Graph`, relationships are stored as plain
dicts for fast bulk loading — Pydantic validation is a separate step.

Five indexes: `out_edges` and `in_edges` for traversal, `by_stmt_id` for
content-addressed lookup, `by_uuid` for legacy UUID lookup, and `entities`
for entity resolution. Multiple JSONL files are loaded and merged in sorted
order so results are deterministic.
"""


class MedlitGraph:
    """
    In-memory knowledge graph indexed for O(1) neighbour lookup.

    Three relationship indexes:
      out_edges  — subject_id  → [relationship records]
      in_edges   — object_id   → [relationship records]
      by_stmt_id — stmt_id     → relationship record
      by_uuid    — id (UUID)   → relationship record (legacy key)

    One entity index:
      entities   — entity_id   → entity record

    Relationships without a stmt_id (pre-migration records) are still
    indexed under their UUID id field if present.
    """

    def __init__(self, records: Iterable[dict]):
        self.entities: dict[str, dict] = {}
        self.by_stmt_id: dict[str, dict] = {}
        self.by_uuid: dict[str, dict] = {}
        self.out_edges: dict[str, list[dict]] = defaultdict(list)
        self.in_edges: dict[str, list[dict]] = defaultdict(list)
        self.by_predicate: dict[str, list[dict]] = defaultdict(list)

        for record in records:
            if _is_relationship(record):
                self._index_relationship(record)
            elif _is_entity(record):
                eid = record.get("entity_id") or record.get("id")
                if eid:
                    self.entities[eid] = record
            # Records that are neither (e.g. schema metadata) are ignored.

    def _index_relationship(self, record: dict) -> None:
        subj = record.get("subject_id", "")
        obj = record.get("object_id", "")
        pred = record.get("predicate", "")
        stmt_id = record.get("stmt_id")
        uid = str(record.get("id", ""))

        self.out_edges[subj].append(record)
        self.in_edges[obj].append(record)
        self.by_predicate[pred].append(record)

        if stmt_id:
            self.by_stmt_id[stmt_id] = record
        if uid:
            self.by_uuid[uid] = record

    # ── Loading ───────────────────────────────────────────────────────────

    @classmethod
    def from_jsonl_file(cls, path: Path) -> "MedlitGraph":
        """Build a graph from a single JSONL file."""
        return cls(cls._iter_jsonl(path))

    @classmethod
    def from_jsonl_dir(
        cls,
        directory: Path,
        glob: str = "*.jsonl",
    ) -> "MedlitGraph":
        """
        Build a graph by loading and merging all JSONL files in a directory.

        Files are loaded in sorted order so results are deterministic.
        """
        return cls(cls._iter_dir(directory, glob))

    @staticmethod
    def _iter_jsonl(path: Path) -> Iterator[dict]:
        with path.open() as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                try:
                    yield json.loads(stripped)
                except json.JSONDecodeError:
                    pass  # Callers can run a separate parse-validation step

    @classmethod
    def _iter_dir(cls, directory: Path, glob: str) -> Iterator[dict]:
        for path in sorted(directory.glob(glob)):
            yield from cls._iter_jsonl(path)

    # ── Basic traversal ───────────────────────────────────────────────────

    def edges_from(
        self,
        entity_id: str,
        predicate: str | None = None,
        truth_status: str | None = None,
    ) -> list[dict]:
        """
        Outward edges from entity_id, optionally filtered by predicate
        and/or truth_status.
        """
        edges = self.out_edges.get(entity_id, [])
        if predicate:
            edges = [e for e in edges if e.get("predicate") == predicate]
        if truth_status:
            edges = [e for e in edges if e.get("truth_status") == truth_status]
        return edges

    def edges_to(
        self,
        entity_id: str,
        predicate: str | None = None,
        truth_status: str | None = None,
    ) -> list[dict]:
        """
        Inward edges to entity_id, optionally filtered.
        """
        edges = self.in_edges.get(entity_id, [])
        if predicate:
            edges = [e for e in edges if e.get("predicate") == predicate]
        if truth_status:
            edges = [e for e in edges if e.get("truth_status") == truth_status]
        return edges

    def all_relationships(
        self,
        predicate: str | None = None,
        truth_status: str | None = None,
    ) -> list[dict]:
        """All relationship records, optionally filtered."""
        if predicate:
            rels = self.by_predicate.get(predicate, [])
        else:
            rels = [r for pred_list in self.by_predicate.values() for r in pred_list]
        if truth_status:
            rels = [r for r in rels if r.get("truth_status") == truth_status]
        return rels

    def find_relationship(self, stmt_id: str) -> dict | None:
        """Look up a relationship by its content-addressed stmt_id."""
        return self.by_stmt_id.get(stmt_id)

    def find_entity(self, entity_id: str) -> dict | None:
        """Look up an entity by its entity_id."""
        return self.entities.get(entity_id)

    # ── Transitive closure ────────────────────────────────────────────────

    def transitive_closure(
        self,
        entity_id: str,
        predicate: str,
        truth_status: str = "asserted_true",
        max_depth: int = 50,
    ) -> set[str]:
        """
        All entity IDs reachable from entity_id by following predicate
        transitively (outward direction). Does not include entity_id itself.

        max_depth guards against cycles; a separate cycle-detection test
        is more appropriate for data validation.
        """
        visited: set[str] = set()
        frontier: set[str] = {entity_id}
        depth = 0
        while frontier and depth < max_depth:
            next_f: set[str] = set()
            for eid in frontier:
                for edge in self.out_edges.get(eid, []):
                    if edge.get("predicate") != predicate:
                        continue
                    if edge.get("truth_status") != truth_status:
                        continue
                    obj = edge.get("object_id", "")
                    if obj and obj not in visited:
                        visited.add(obj)
                        next_f.add(obj)
            frontier = next_f
            depth += 1
        return visited

    def has_cycle(self, predicate: str) -> bool:
        """
        Detect whether any cycle exists for the given predicate using
        iterative DFS. Used to verify Transitive predicates like SubtypeOf
        form a DAG.
        """
        all_nodes = set(self.out_edges.keys()) | set(self.in_edges.keys())
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for edge in self.out_edges.get(node, []):
                if edge.get("predicate") != predicate:
                    continue
                neighbour = edge.get("object_id", "")
                if not neighbour:
                    continue
                if neighbour not in visited:
                    if dfs(neighbour):
                        return True
                elif neighbour in rec_stack:
                    return True
            rec_stack.discard(node)
            return False

        for node in all_nodes:
            if node not in visited:
                if dfs(node):
                    return True
        return False

    # ── Stats ─────────────────────────────────────────────────────────────

    def summary(self) -> dict:
        """Quick summary of graph contents."""
        total_rels = sum(len(v) for v in self.out_edges.values())
        return {
            "entities": len(self.entities),
            "relationships": total_rels,
            "predicates": dict(
                sorted(
                    {k: len(v) for k, v in self.by_predicate.items()}.items(),
                    key=lambda x: -x[1],
                )
            ),
            "truth_status_counts": self._truth_status_counts(),
        }

    def _truth_status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for edges in self.out_edges.values():
            for e in edges:
                ts = e.get("truth_status", "missing")
                counts[ts] += 1
        return dict(counts)
