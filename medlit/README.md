# medlit — Medical Literature Knowledge Graph

Schema and in-memory query layer for a biomedical knowledge graph extracted from journal articles. No database, no MCP server, no LLM at query time.

## What it is

`medlit` defines typed entities and relationships for biomedical text — drugs, genes, diseases, proteins — and the predicates that connect them: `TREATS`, `CAUSES`, `INTERACTS_WITH`, `ENCODES`, and ~25 others. Records live in JSONL files; `MedlitGraph` loads them into memory and provides O(1) traversal.

**Schema version: 2.0.0.** The v2 additions are:
- `truth_status` on every relationship — the graph's explicit commitment to a proposition
- `stmt_id` — a content-addressed string ID enabling deduplication and higher-order predication
- Trait mixins (`Symmetric`, `Transitive`, `Inverse`) declaring semantic properties of predicate types
- Frozen Pydantic models throughout; `truth_status` updates use `model_copy(update={...})`

## Directory layout

```
medlit/
  src/
    base.py          — TruthStatus, statement_id, Trait markers, ExtractionProvenance
    relationship.py  — All predicate classes (~28 types) and create_relationship()
    graph.py         — MedlitGraph: in-memory graph with five indexes
  tests/
    conftest.py      — pytest fixtures: --jsonl-dir option, session-scoped MedlitGraph
    test_medlit.py   — Migration correctness, schema integrity, trait invariants
  scripts/
    migrate_jsonl.py — v1 → v2 migration: adds truth_status and stmt_id to JSONL records
```

## Predicate vocabulary

### Therapeutic (medical assertions)

Require non-empty `evidence_ids`. Inherit from `BaseMedicalRelationship`.

| Predicate | Subject → Object | Notes |
|---|---|---|
| `TREATS` | Drug → Disease | `response_rate`, `line_of_therapy`, `indication` |
| `CAUSES` | Gene/Mutation → Disease | `frequency`, `onset`, `severity` |
| `PREVENTS` | Drug → Disease | `risk_reduction` |
| `INCREASES_RISK` | Gene/Mutation → Disease | `risk_ratio`, `penetrance`, `population` |
| `SIDE_EFFECT` | Drug → Symptom | `frequency`, `reversible` |
| `ASSOCIATED_WITH` | Disease/Gene → Disease | non-causal statistical association |
| `INTERACTS_WITH` | Drug ↔ Drug | **Symmetric** |
| `CONTRAINDICATED_FOR` | Drug → Disease | `severity`: absolute/relative |
| `DIAGNOSED_BY` | Disease → Procedure/Biomarker | `sensitivity`, `specificity` |
| `PARTICIPATES_IN` | Gene/Protein → Pathway | `regulatory_effect` |
| `INDICATES` | Biomarker → Disease | |
| `SUBTYPE_OF` | Disease → Disease | **Transitive**; forms a DAG |

### Biological (no evidence_ids required)

Inherit from `BaseRelationship` directly.

| Predicate | Subject → Object | Notes |
|---|---|---|
| `ENCODES` | Gene → Protein | **Inverse** of `IS_ENCODED_BY` |
| `IS_ENCODED_BY` | Protein → Gene | **Inverse** of `ENCODES` |
| `BINDS_TO` | Drug/Protein → Protein | |
| `INHIBITS` | Drug/Protein → Protein/Pathway | |
| `UPREGULATES` | — → — | |
| `DOWNREGULATES` | — → — | |

### Research / bibliographic

Inherit from `ResearchRelationship`. No evidence_ids required.

| Predicate | Subject → Object | Notes |
|---|---|---|
| `CITES` | Paper → Paper | `context`, `sentiment` |
| `STUDIED_IN` | Entity → Paper | `role`, `section` |
| `AUTHORED_BY` | Paper → Author | `position` |
| `PART_OF` | Paper → ClinicalTrial | |
| `SAME_AS` | Entity ↔ Entity | **Symmetric**; provisional identity link |

### Scientific method

| Predicate | Subject → Object | Notes |
|---|---|---|
| `PREDICTS` | Hypothesis → Outcome | `prediction_type`, `testable` |
| `TESTED_BY` | Hypothesis → Paper | `test_outcome` |
| `SUPPORTS` | Evidence → Hypothesis ∣ Relationship | v2: `object_id` may be a `stmt_id` |
| `REFUTES` | Evidence → Hypothesis ∣ Relationship | v2: `object_id` may be a `stmt_id` |
| `GENERATES` | Paper/Trial → Evidence | `eco_type`, `quality_score` |

### Higher-order

| Predicate | Subject → Object | Notes |
|---|---|---|
| `CONTRADICTS` | Relationship ↔ Relationship | **Symmetric**; both ends are `stmt_ids` |

`Contradicts` records a direct conflict between two medical claims. Because both ends are `stmt_ids`, no entity lookup is needed — the relationship instances themselves are the nodes.

## Truth status

Every `BaseMedicalRelationship` carries a `truth_status` field. Presence in the graph does **not** assert the proposition — `truth_status` does.

```
hypothetical → asserted_true | asserted_false → disputed | retracted | superseded
```

| Value | Meaning |
|---|---|
| `asserted_true` | Accepted finding |
| `asserted_false` | Claim was wrong |
| `hypothetical` | In-pipeline default; not yet reviewed |
| `disputed` | Contradicted by other evidence |
| `retracted` | Paper was formally withdrawn |
| `superseded` | Correct at the time, but replaced by stronger evidence *(medlit addition)* |

`superseded` is distinct from `asserted_false`: a drug may have genuinely treated a disease in the studied population, but a later larger RCT changed clinical practice.

## Content-addressed IDs

`statement_id(subject_id, predicate, object_id)` returns a deterministic string:

```python
>>> statement_id("RxNorm:1187832", "TREATS", "C0006142")
'stmt:RxNorm:1187832:TREATS:C0006142'
```

Two records expressing the same proposition compute the same `stmt_id`. This makes deduplication across extraction runs O(1) and allows `Contradicts` (and `Supports`/`Refutes` in v2) to reference relationships by stable identity.

`statement_uuid()` derives a UUID5 from the same key for storage layers that require a UUID primary key.

## Trait semantics

Traits are class-level declarations — they belong to the predicate type, not to any instance. The set matches the Holmes formal definition:

| Trait | Declaration | Applied to |
|---|---|---|
| `Symmetric` | If A→B then B→A; one stored edge suffices | `InteractsWith`, `SameAs`, `Contradicts` |
| `Transitive` | If A→B and B→C then A→C | `SubtypeOf` |
| `Functional` | At most one object per subject | (reserved) |
| `InverseFunctional` | At most one subject per object | (reserved) |
| `Inverse[P]` | This predicate is the inverse of P | `Encodes` ↔ `IsEncodedBy` |

Traits are inspectable at runtime:

```python
from medlit.src.base import Symmetric, Transitive
from medlit.src.relationship import InteractsWith, SubtypeOf, Encodes, IsEncodedBy
from medlit.src.base import get_inverse

assert issubclass(InteractsWith, Symmetric)
assert issubclass(SubtypeOf, Transitive)
assert get_inverse(Encodes) is IsEncodedBy
```

## Query API

```python
from medlit.src.graph import MedlitGraph

g = MedlitGraph.from_jsonl_dir("data/migrated/")

# Outward edges
treats_edges = g.edges_from("RxNorm:1187832", predicate="TREATS",
                             truth_status="asserted_true")

# Inward edges
disease_sources = g.edges_to("C0006142", predicate="TREATS")

# All relationships of a type
all_treats = g.all_relationships(predicate="TREATS")

# Content-addressed lookup
rel = g.find_relationship("stmt:RxNorm:1187832:TREATS:C0006142")

# Entity lookup
entity = g.find_entity("RxNorm:1187832")

# Transitive closure (e.g. all disease subtypes reachable from a root)
subtypes = g.transitive_closure("C0006142", predicate="SUBTYPE_OF")

# Cycle detection (DAG check for transitive predicates)
assert not g.has_cycle("SUBTYPE_OF")

# Summary
print(g.summary())
# {'entities': ..., 'relationships': ..., 'predicates': {...}, 'truth_status_counts': {...}}
```

`MedlitGraph` stores relationships as plain dicts for fast bulk loading. Five indexes: `out_edges`, `in_edges`, `by_stmt_id`, `by_uuid` (legacy), `entities`.

## Migration: v1 → v2

Existing JSONL records are valid v2 records after adding two fields. The migration script does this without re-extracting anything:

```bash
# Single file
pdm run python medlit/scripts/migrate_jsonl.py input.jsonl output.jsonl

# Dry run (validate, no write)
pdm run python medlit/scripts/migrate_jsonl.py input.jsonl output.jsonl --dry-run

# Batch
for f in data/*.jsonl; do
    pdm run python medlit/scripts/migrate_jsonl.py "$f" "v2/${f##*/}"
done
```

What the script adds:

- `truth_status = "asserted_true"` — all ingested records were ground truth at ingestion time. Records with a non-empty `contradicted_by` field are flagged as `"disputed"` and emitted with a warning for manual review.
- `stmt_id = "stmt:{subject_id}:{predicate}:{object_id}"` — content-addressed ID.
- `schema_version = "2.0.0"`.

Entity records pass through unchanged except for the `schema_version` tag.

An optional second pass (`build_stmt_id_index` + `restructure_supports`) rewires `SUPPORTS`/`REFUTES` edges to point at relationship `stmt_ids` rather than `Hypothesis` entity IDs. This is not run by default — it requires a manually constructed `hypothesis_to_claim_map`.

## Tests

Tests require a directory of migrated JSONL files:

```bash
pdm run pytest medlit/tests/ --jsonl-dir /path/to/migrated/ -v
```

Without `--jsonl-dir` (or if the fallback `medlit/tests/data/migrated/` doesn't exist), all tests are skipped cleanly. The session-scoped `g` fixture builds the graph once and shares it across all tests.

Test coverage:
- **Sanity** — loader found records; `summary()` runs
- **Migration correctness** — all relationship records have `truth_status` and `stmt_id`; `stmt_id` format matches `statement_id()` output; no `HYPOTHETICAL` truth status (all records were promoted during ingestion)
- **Schema version** — all records carry `schema_version = "2.0.0"`
- **Referential integrity** — subject/object IDs for entity-typed predicates resolve in the entity index; no dangling references
- **Evidence integrity** — `evidence_ids` non-empty for all `BaseMedicalRelationship` predicates
- **Trait invariants** — `SUBTYPE_OF` forms a DAG (no cycles); `INTERACTS_WITH` is symmetric (if A→B then B→A or B←A stored)
- **Contradicts** — both ends of every `CONTRADICTS` edge are valid `stmt_ids` in `by_stmt_id`

## Provenance

`ExtractionProvenance` captures how a record was produced: pipeline version, git commit, model, prompt template and checksum, execution timestamp, and entity resolution statistics. These are optional — older records may carry only the legacy `model_info` field. Provenance enables:

- Reproducing an extraction run exactly
- Comparing entity quality across pipeline versions or models
- Finding all records extracted with a specific prompt version for re-extraction

## Entity IDs

Canonical entity IDs use authority prefixes:

| Authority | Prefix | Entity types |
|---|---|---|
| UMLS | `UMLS:C...` | Diseases, symptoms, procedures |
| HGNC | `HGNC:...` | Genes |
| RxNorm | `RxNorm:...` | Drugs |
| UniProt | `UniProt:...` | Proteins |
| Local | `local:...` | Provisional entities without a canonical match |

## Relationship factory

`create_relationship()` constructs a typed instance from a predicate string, auto-injecting `stmt_id`:

```python
from medlit.src.relationship import create_relationship, TruthStatus

rel = create_relationship(
    "TREATS",
    subject_id="RxNorm:1187832",
    object_id="UMLS:C0006142",
    evidence_ids=["PMC999"],
    truth_status=TruthStatus.ASSERTED_TRUE,
    response_rate=0.59,
    confidence=0.85,
)
# rel.stmt_id == "stmt:RxNorm:1187832:TREATS:UMLS:C0006142"
```

Pass `auto_stmt_id=False` when loading pre-computed `stmt_ids` from JSONL to avoid recomputing.
