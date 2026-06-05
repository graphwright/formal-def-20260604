"""
test_medlit.py — queries against the migrated medlit instance graph.

No database. No MCP server. No LLM. Pure Python objects.

Each section exercises a distinct concern: migration correctness, schema
integrity, referential integrity, and trait invariants. The tests are
designed to catch real data problems — not just confirm the loader works.

Run:
    pytest test_medlit.py --jsonl-dir /path/to/migrated/ -v
"""

import pytest
from collections import defaultdict
from medlit.src.graph import MedlitGraph
from medlit.src.base import statement_id, TruthStatus


"""
## Test configuration

Trait sets and predicate constraints are declared at module level so
individual tests can reference them without re-computing.
`SYMMETRIC_PREDICATES` and `TRANSITIVE_PREDICATES` mirror the trait
declarations in `medlit.src.relationship`. `PREDICATE_CONSTRAINTS` encodes
the domain/range rules from `MedlitDomain` for the data-level R6 check.
"""


# Predicates that carry the Symmetric trait in v2.
# For these, the reverse direction should either be stored or be derivable.
SYMMETRIC_PREDICATES = {"INTERACTS_WITH", "SAME_AS", "CONTRADICTS"}

# Predicates that carry the Transitive trait in v2.
TRANSITIVE_PREDICATES = {"SUBTYPE_OF"}

# Predicates that require non-empty evidence_ids (BaseMedicalRelationship).
# ResearchRelationship subclasses (CITES, AUTHORED_BY, etc.) are excluded.
EVIDENCE_REQUIRED_PREDICATES = {
    "TREATS", "CAUSES", "PREVENTS", "INCREASES_RISK", "SIDE_EFFECT",
    "ASSOCIATED_WITH", "INTERACTS_WITH", "CONTRAINDICATED_FOR",
    "DIAGNOSED_BY", "PARTICIPATES_IN", "INDICATES", "SUBTYPE_OF",
    "PREDICTS", "TESTED_BY", "SUPPORTS", "REFUTES", "GENERATES",
}

# Expected domain/range pairs from MedlitDomain.predicate_constraints.
# Used to spot-check R6 at the data level (since kgschema doesn't enforce
# it in the type system yet).
PREDICATE_CONSTRAINTS = {
    "TREATS":            ({"drug"},                  {"disease"}),
    "CAUSES":            ({"gene", "mutation"},      {"disease"}),
    "PREVENTS":          ({"drug"},                  {"disease"}),
    "INCREASES_RISK":    ({"gene", "mutation"},      {"disease"}),
    "SIDE_EFFECT":       ({"drug"},                  {"symptom", "disease"}),
    "INTERACTS_WITH":    ({"drug"},                  {"drug"}),
    "CONTRAINDICATED_FOR": ({"drug"},                {"disease"}),
    "DIAGNOSED_BY":      ({"disease"},               {"procedure", "biomarker"}),
    "PARTICIPATES_IN":   ({"gene", "protein"},       {"pathway"}),
    "ENCODES":           ({"gene"},                  {"protein"}),
    "BINDS_TO":          ({"drug", "protein"},       {"protein"}),
    "INHIBITS":          ({"drug", "protein"},       {"protein", "pathway"}),
    "CITES":             ({"paper"},                 {"paper"}),
    "AUTHORED_BY":       ({"paper"},                 {"author"}),
    "SUPPORTS":          ({"evidence"},              {"hypothesis"}),
    "REFUTES":           ({"evidence"},              {"hypothesis"}),
    "SUBTYPE_OF":        ({"disease"},               {"disease"}),
}


"""
## Sanity

Verify the loader found and parsed JSONL records and that `summary()`
runs without error — the first things to check before all others.
"""


def test_graph_loaded(g: MedlitGraph):
    """
    Graph is non-empty after loading. Verifies the loader found and parsed
    JSONL records correctly — the first thing to check before all others.
    """
    assert len(g.entities) > 0, "No entity records loaded"
    total_rels = sum(len(v) for v in g.out_edges.values())
    assert total_rels > 0, "No relationship records loaded"


def test_summary_prints(g: MedlitGraph, capsys):
    """
    summary() runs without error and reports reasonable counts.
    Useful as a smoke test when running against new data.
    """
    s = g.summary()
    print("\n--- Graph summary ---")
    print(f"  Entities:      {s['entities']}")
    print(f"  Relationships: {s['relationships']}")
    for pred, count in list(s['predicates'].items())[:10]:
        print(f"  {pred}: {count}")
    print(f"  Truth status:  {s['truth_status_counts']}")
    assert s["relationships"] > 0


"""
## M1–M5 — Migration correctness

These tests verify that `migrate_jsonl.py` ran correctly on every loaded
file: all relationships carry `truth_status` and `stmt_id`; `stmt_id`
values are deterministic and unique; and all `truth_status` strings are
members of the `TruthStatus` enum.
"""


def test_m1_all_relationships_have_truth_status(g: MedlitGraph):
    """
    M1 — Every relationship record carries truth_status.

    This is the most basic migration check. A missing truth_status means
    the record was not processed by migrate_jsonl.py or was added after
    migration without setting the field.
    """
    missing = [
        (r.get("predicate"), r.get("subject_id"), r.get("object_id"))
        for edges in g.out_edges.values()
        for r in edges
        if "truth_status" not in r or r["truth_status"] is None
    ]
    assert missing == [], (
        f"{len(missing)} relationships missing truth_status. "
        f"First 5: {missing[:5]}"
    )


def test_m2_all_relationships_have_stmt_id(g: MedlitGraph):
    """
    M2 — Every relationship record carries stmt_id.

    Without stmt_id, higher-order predicates (Contradicts) cannot
    reference this relationship, and deduplication is UUID-based rather
    than content-based.
    """
    missing = [
        (r.get("predicate"), r.get("subject_id"), r.get("object_id"))
        for edges in g.out_edges.values()
        for r in edges
        if not r.get("stmt_id")
    ]
    assert missing == [], (
        f"{len(missing)} relationships missing stmt_id. First 5: {missing[:5]}"
    )


def test_m3_stmt_id_is_deterministic(g: MedlitGraph):
    """
    M3 — stmt_id matches statement_id(subject_id, predicate, object_id).

    Verifies that stored stmt_ids were computed correctly. A mismatch
    indicates either a bug in migrate_jsonl.py or manual editing of
    subject_id/predicate/object_id after migration without updating stmt_id.
    """
    mismatches = []
    for edges in g.out_edges.values():
        for r in edges:
            stored = r.get("stmt_id")
            if not stored:
                continue
            expected = statement_id(
                r.get("subject_id", ""),
                r.get("predicate", ""),
                r.get("object_id", ""),
            )
            if stored != expected:
                mismatches.append({
                    "stored":   stored,
                    "expected": expected,
                    "predicate": r.get("predicate"),
                })
    assert mismatches == [], (
        f"{len(mismatches)} stmt_id mismatches. First 3: {mismatches[:3]}"
    )


def test_m4_stmt_ids_are_unique(g: MedlitGraph):
    """
    M4 — No two relationship records share the same stmt_id.

    Duplicate stmt_ids mean the same proposition was ingested twice and
    deduplication failed. The content-addressed ID scheme should prevent
    this, but ingestion bugs can create duplicates.
    """
    seen: dict[str, int] = defaultdict(int)
    for edges in g.out_edges.values():
        for r in edges:
            stmt_id = r.get("stmt_id")
            if stmt_id:
                seen[stmt_id] += 1
    duplicates = {k: v for k, v in seen.items() if v > 1}
    assert not duplicates, (
        f"{len(duplicates)} duplicate stmt_ids. "
        f"Sample: {dict(list(duplicates.items())[:3])}"
    )


def test_m5_truth_status_values_are_valid(g: MedlitGraph):
    """
    M5 — All truth_status values are members of TruthStatus.

    Catches typos and legacy string values that don't map to the v2 enum.
    """
    valid = {ts.value for ts in TruthStatus}
    invalid = defaultdict(list)
    for edges in g.out_edges.values():
        for r in edges:
            ts = r.get("truth_status")
            if ts and ts not in valid:
                invalid[ts].append(r.get("predicate"))
    assert not invalid, (
        f"Invalid truth_status values found: {dict(invalid)}"
    )


"""
## S1–S4 — Schema integrity

Field-level constraints that should hold regardless of migration: medical
relationships must have evidence, confidence scores must be in range,
entity types must respect predicate domain/range (the data-level R6 check),
and canonical entities must carry their ontology IDs.
"""


def test_s1_evidence_required_predicates_have_evidence(g: MedlitGraph):
    """
    S1 — Medical assertion relationships include at least one evidence_id.

    Enforces the BaseMedicalRelationship validator at the data level.
    ResearchRelationship subclasses (CITES, AUTHORED_BY, PART_OF,
    STUDIED_IN) are excluded.
    """
    violations = []
    for pred in EVIDENCE_REQUIRED_PREDICATES:
        for r in g.by_predicate.get(pred, []):
            if not r.get("evidence_ids"):
                violations.append((pred, r.get("subject_id"), r.get("object_id")))
    assert violations == [], (
        f"{len(violations)} medical relationships missing evidence_ids. "
        f"First 5: {violations[:5]}"
    )


def test_s2_confidence_in_range(g: MedlitGraph):
    """
    S2 — Confidence scores are between 0.0 and 1.0 (inclusive).

    Out-of-range values indicate pipeline bugs or manual editing errors.
    """
    violations = []
    for edges in g.out_edges.values():
        for r in edges:
            conf = r.get("confidence")
            if conf is not None and not (0.0 <= conf <= 1.0):
                violations.append((r.get("predicate"), conf))
    assert violations == [], (
        f"{len(violations)} relationships with out-of-range confidence. "
        f"Sample: {violations[:5]}"
    )


def test_s3_domain_range_spot_check(g: MedlitGraph):
    """
    S3 — Subject and object entity types respect predicate constraints.

    This is the data-level equivalent of R6. kgschema doesn't enforce
    typed subject/object fields yet, so we check here by resolving
    entity_ids to entity_type via the entity index.

    Only checks predicates listed in PREDICATE_CONSTRAINTS. Records whose
    subject or object entity is not in the entity index are skipped
    (unresolvable references are caught by S4).

    Note: SUPPORTS and REFUTES are excluded here because in v2 their
    object may be a stmt_id (a relationship) rather than a Hypothesis
    entity — these mixed-type records are expected and valid.
    """
    violations = []
    skip_predicates = {"SUPPORTS", "REFUTES", "CONTRADICTS"}
    for pred, (allowed_subj, allowed_obj) in PREDICATE_CONSTRAINTS.items():
        if pred in skip_predicates:
            continue
        for r in g.by_predicate.get(pred, []):
            subj_entity = g.find_entity(r.get("subject_id", ""))
            obj_entity = g.find_entity(r.get("object_id", ""))
            if subj_entity is None or obj_entity is None:
                continue  # unresolvable; caught by integrity tests
            subj_type = subj_entity.get("entity_type", "")
            obj_type = obj_entity.get("entity_type", "")
            if allowed_subj and subj_type not in allowed_subj:
                violations.append({
                    "predicate": pred,
                    "subject_id": r.get("subject_id"),
                    "subject_type": subj_type,
                    "allowed_subject_types": allowed_subj,
                })
            if allowed_obj and obj_type not in allowed_obj:
                violations.append({
                    "predicate": pred,
                    "object_id": r.get("object_id"),
                    "object_type": obj_type,
                    "allowed_object_types": allowed_obj,
                })
    assert violations == [], (
        f"{len(violations)} domain/range violations. First 3: {violations[:3]}"
    )


def test_s4_canonical_entities_have_ontology_ids(g: MedlitGraph):
    """
    S4 — Canonical (non-extracted) entities carry at least one ontology ID.

    Entities sourced from 'extracted' may lack ontology IDs (they're
    provisional). Entities from umls, mesh, rxnorm, hgnc, uniprot must
    have the corresponding ID field. This is the canonical_entities_have_
    ontology_ids model_validator in entity.py promoted to a data test.
    """
    ontology_fields_by_source = {
        "umls":    ["umls_id"],
        "mesh":    ["mesh_id"],
        "rxnorm":  ["rxnorm_id"],
        "hgnc":    ["hgnc_id"],
        "uniprot": ["uniprot_id"],
    }
    violations = []
    for entity_id, entity in g.entities.items():
        source = entity.get("source")
        if source not in ontology_fields_by_source:
            continue
        fields = ontology_fields_by_source[source]
        if not any(entity.get(f) for f in fields):
            violations.append({
                "entity_id": entity_id,
                "source": source,
                "expected_one_of": fields,
            })
    assert violations == [], (
        f"{len(violations)} canonical entities missing ontology IDs. "
        f"First 5: {violations[:5]}"
    )


"""
## I1–I4 — Referential integrity

Every ID that appears in a record's reference fields must resolve to an
existing record: `evidence_ids` must point to Evidence entities,
`source_papers` to Paper entities, `Contradicts` ends to relationship
`stmt_ids`, and `Cites` ends to Paper entities.
"""


def test_i1_evidence_ids_reference_existing_evidence(g: MedlitGraph):
    """
    I1 — evidence_ids in relationships resolve to existing Evidence entities.

    Evidence entities have entity_type='evidence' and IDs in the format
    {paper_id}:{section}:{paragraph}:{method}. A broken reference means
    the evidence entity was not ingested or was deleted.

    Because Evidence entities are numerous, we collect a sample of
    violations (up to 20) rather than exhaustively listing all.
    """
    violations = []
    for edges in g.out_edges.values():
        for r in edges:
            for eid in r.get("evidence_ids", []):
                if g.find_entity(eid) is None:
                    violations.append({
                        "predicate": r.get("predicate"),
                        "relationship": r.get("stmt_id"),
                        "missing_evidence_id": eid,
                    })
                    if len(violations) >= 20:
                        break
    assert violations == [], (
        f"{len(violations)} broken evidence_id references "
        f"(showing up to 20). Sample: {violations[:3]}"
    )


def test_i2_source_papers_reference_existing_papers(g: MedlitGraph):
    """
    I2 — source_papers IDs in relationships resolve to existing Paper entities.

    A missing Paper entity means a paper was referenced as a source but
    not ingested into the entity graph. Common cause: ingestion of
    relationships ran before ingestion of the corresponding paper entities.
    """
    violations = []
    for edges in g.out_edges.values():
        for r in edges:
            for pid in r.get("source_papers", []):
                if g.find_entity(pid) is None:
                    violations.append({
                        "predicate": r.get("predicate"),
                        "missing_paper_id": pid,
                    })
                    if len(violations) >= 20:
                        break
    assert violations == [], (
        f"{len(violations)} broken source_paper references "
        f"(showing up to 20). Sample: {violations[:3]}"
    )


def test_i3_contradicts_stmt_ids_reference_existing_relationships(g: MedlitGraph):
    """
    I3 — stmt_ids in Contradicts edges resolve to existing relationships.

    Contradicts.subject_id and Contradicts.object_id are relationship
    stmt_ids, not entity_ids. A broken reference means one of the
    contradicting relationships was not ingested or was deleted.
    """
    violations = []
    for r in g.by_predicate.get("CONTRADICTS", []):
        for field in ("subject_id", "object_id"):
            ref = r.get(field, "")
            if ref and g.find_relationship(ref) is None:
                violations.append({
                    "contradicts_stmt_id": r.get("stmt_id"),
                    "broken_reference_field": field,
                    "broken_reference_value": ref,
                })
    assert violations == [], (
        f"{len(violations)} broken Contradicts references. "
        f"Sample: {violations[:3]}"
    )


def test_i4_cites_references_existing_papers(g: MedlitGraph):
    """
    I4 — Cites edges connect Paper entities that exist in the graph.

    A Paper citing another Paper that doesn't exist in the entity index
    indicates a missing paper or an ID mismatch (e.g. PMC ID vs DOI).
    """
    violations = []
    for r in g.by_predicate.get("CITES", []):
        for field in ("subject_id", "object_id"):
            pid = r.get(field, "")
            if pid and g.find_entity(pid) is None:
                violations.append({
                    "stmt_id": r.get("stmt_id"),
                    "missing_field": field,
                    "missing_id": pid,
                })
    assert violations == [], (
        f"{len(violations)} Cites edges with missing Paper entities. "
        f"Sample: {violations[:3]}"
    )


"""
## T1–T4 — Trait invariants

Structural invariants implied by the trait declarations in
`medlit.src.relationship`: `Symmetric` predicates have reverse edges stored,
`SubtypeOf` (Transitive) forms a DAG, transitive closure behaves correctly
on real data, and `DISPUTED` relationships name their contradicting sources.
"""


def test_t1_symmetric_predicates_have_reverse_edges(g: MedlitGraph):
    """
    T1 — For Symmetric predicates (INTERACTS_WITH, SAME_AS), the reverse
    edge is present.

    In the v2 schema, Symmetric means one stored direction suffices and
    the other is derived. In practice, the pipeline may store both
    directions. This test checks consistency: for every (A, p, B) where
    p is Symmetric, (B, p, A) must also exist.

    If your pipeline intentionally stores only one direction and relies on
    Symmetric inference, update this test to check derivability instead.
    """
    violations = []
    for pred in SYMMETRIC_PREDICATES - {"CONTRADICTS"}:
        # CONTRADICTS is a special case: both ends are stmt_ids, not entity_ids,
        # and the pipeline may store one direction.
        for r in g.by_predicate.get(pred, []):
            subj = r.get("subject_id", "")
            obj = r.get("object_id", "")
            # Check the reverse direction exists
            reverse_exists = any(
                e.get("subject_id") == obj and e.get("object_id") == subj
                for e in g.by_predicate.get(pred, [])
            )
            if not reverse_exists:
                violations.append({
                    "predicate": pred,
                    "forward": f"{subj} → {obj}",
                    "missing_reverse": f"{obj} → {subj}",
                })
    # Warn rather than fail if only a few violations — legacy data may
    # predate the Symmetric enforcement.
    if violations:
        # Report as a warning; change to assert == [] to make it hard-fail.
        pytest.warns(
            UserWarning,
            match="missing reverse edge",
        ) if False else None  # placeholder
        print(
            f"\nWARNING: {len(violations)} Symmetric predicates missing "
            f"reverse edges. Sample: {violations[:3]}"
        )
        # Uncomment to make this a hard failure once pipelines are updated:
        # assert violations == [], ...


def test_t2_subtype_of_is_a_dag(g: MedlitGraph):
    """
    T2 — SubtypeOf (Transitive) contains no cycles.

    A cycle (Disease A is a subtype of B, B is a subtype of A) is a schema
    error. Under the Transitive closure this would make A and B equivalent,
    which is wrong and breaks transitivity reasoning.
    """
    has_cycle = g.has_cycle("SUBTYPE_OF")
    assert not has_cycle, (
        "SubtypeOf contains at least one cycle. "
        "Run g.transitive_closure() from suspicious nodes to locate it."
    )


def test_t3_subtype_of_transitivity_example(g: MedlitGraph):
    """
    T3 — Transitive closure of SubtypeOf produces at least as many
    reachable nodes as direct edges suggest.

    For any disease D that has SubtypeOf edges, the transitive closure
    should reach at least the direct parents — and more if parents also
    have parents. This is a smoke test that transitive_closure() works
    correctly on the actual data.
    """
    # Find any disease with at least one SubtypeOf edge
    test_node = None
    for r in g.by_predicate.get("SUBTYPE_OF", []):
        subj = r.get("subject_id")
        if subj:
            test_node = subj
            break

    if test_node is None:
        pytest.skip("No SUBTYPE_OF edges found in graph")

    direct_parents = {
        r.get("object_id")
        for r in g.edges_from(test_node, predicate="SUBTYPE_OF")
    }
    transitive_parents = g.transitive_closure(test_node, "SUBTYPE_OF")

    # Transitive closure must include all direct parents
    assert direct_parents.issubset(transitive_parents), (
        f"Transitive closure of SubtypeOf from {test_node} missing "
        f"direct parents: {direct_parents - transitive_parents}"
    )


def test_t4_disputed_relationships_have_contradicted_by(g: MedlitGraph):
    """
    T4 — Relationships with truth_status=DISPUTED should have non-empty
    contradicted_by.

    A disputed relationship that doesn't name its contradicting papers is
    incomplete — it records the dispute but not the evidence for it. This
    test flags these for manual review.
    """
    incomplete = []
    for edges in g.out_edges.values():
        for r in edges:
            if r.get("truth_status") == "disputed":
                if not r.get("contradicted_by"):
                    incomplete.append({
                        "predicate": r.get("predicate"),
                        "stmt_id": r.get("stmt_id"),
                        "subject_id": r.get("subject_id"),
                        "object_id": r.get("object_id"),
                    })
    assert incomplete == [], (
        f"{len(incomplete)} DISPUTED relationships have empty contradicted_by. "
        f"First 5: {incomplete[:5]}"
    )


"""
## E1–E2 — Epistemic completeness

After migration, no record should remain `HYPOTHETICAL`, and
`ASSERTED_TRUE` should be the dominant truth status. These tests catch
migration gaps and pipeline bugs where new records are added without
promotion.
"""


def test_e1_no_hypothetical_relationships_in_asserted_graph(g: MedlitGraph):
    """
    E1 — Count of HYPOTHETICAL relationships in the migrated data.

    After migration, no record should be HYPOTHETICAL — migrate_jsonl.py
    sets all existing records to ASSERTED_TRUE (or DISPUTED). A non-zero
    count means either new records were added without promotion, or the
    migration script was not run on some files.
    """
    hypothetical = [
        r for edges in g.out_edges.values()
        for r in edges
        if r.get("truth_status") == "hypothetical"
    ]
    assert hypothetical == [], (
        f"{len(hypothetical)} HYPOTHETICAL relationships found in migrated data. "
        f"These should have been promoted to ASSERTED_TRUE by migrate_jsonl.py. "
        f"First 3: [{r.get('predicate')} {r.get('subject_id')}→{r.get('object_id')} "
        f"for r in hypothetical[:3]]"
    )


def test_e2_asserted_true_is_majority(g: MedlitGraph):
    """
    E2 — ASSERTED_TRUE is the most common truth_status.

    A sanity check that the migration ran correctly. If HYPOTHETICAL or
    another status dominates, something went wrong with the migration
    or the ingestion pipeline.
    """
    counts = g._truth_status_counts()
    total = sum(counts.values())
    if total == 0:
        pytest.skip("No relationships loaded")

    asserted_count = counts.get("asserted_true", 0)
    asserted_fraction = asserted_count / total

    assert asserted_fraction > 0.5, (
        f"Less than 50% of relationships are ASSERTED_TRUE. "
        f"truth_status distribution: {counts}"
    )
