"""
migrate_jsonl.py — Migrate medlit JSONL files from schema v1 to v2.

What this script does
---------------------
Adds two new fields to every relationship record without touching anything else:

  truth_status = "asserted_true"
      All records in the existing JSONL were produced by the ingestion
      pipeline and accepted into the graph — they were ground truth at
      time of ingestion. ASSERTED_TRUE is the correct default.

      Exception: records with non-empty contradicted_by should be reviewed
      and may warrant DISPUTED. This script flags them rather than silently
      setting ASSERTED_TRUE.

  stmt_id = "stmt:{subject_id}:{predicate}:{object_id}"
      Deterministic content-addressed ID. Two records expressing the same
      proposition compute the same stmt_id, enabling deduplication and
      higher-order predicate references (Contradicts).

What this script does NOT do
-----------------------------
  - Re-extract anything from source papers. No API calls, no LLM.
  - Change subject_id, object_id, predicate, evidence_ids, confidence,
    source_papers, or any other existing fields.
  - Restructure Supports/Refutes to point at stmt_ids — that is a
    separate graph transformation step if desired. See restructure_supports()
    below for a template.

Entity records (no subject/predicate/object fields) are passed through
unchanged with only an added schema_version tag.

Usage
-----
  python migrate_jsonl.py input.jsonl output.jsonl
  python migrate_jsonl.py input.jsonl output.jsonl --dry-run
  python migrate_jsonl.py --help

For a directory of JSONL files:
  for f in data/*.jsonl; do
      python migrate_jsonl.py "$f" "v2/${f##*/}"
  done
"""

import argparse
import json
import sys
from pathlib import Path


SCHEMA_VERSION_V1 = "1.0.0"
SCHEMA_VERSION_V2 = "2.0.0"


"""
## Helpers

`statement_id` mirrors `medlit.src.base.statement_id` exactly so this script
has no runtime dependency on the medlit package. `is_relationship_record` is
the same duck-typed check used in `MedlitGraph`: a record is a relationship if
it carries all three of `subject_id`, `predicate`, and `object_id`.
"""


def statement_id(subject_id: str, predicate: str, object_id: str) -> str:
    """Content-addressed ID matching medlit_schema.base.statement_id."""
    return f"stmt:{subject_id}:{predicate}:{object_id}"


def is_relationship_record(record: dict) -> bool:
    """True if the record represents a relationship (has subject/predicate/object)."""
    return all(k in record for k in ("subject_id", "predicate", "object_id"))


"""
## Migration functions

`migrate_relationship` adds `truth_status` and `stmt_id` to a relationship
record. Records with a non-empty `contradicted_by` field are flagged as
`"disputed"` rather than silently set to `"asserted_true"` — they require
manual review. `migrate_entity` is a pass-through: entity records receive only
a `schema_version` tag since they carry no predicate fields to migrate.
"""


def migrate_relationship(record: dict) -> tuple[dict, list[str]]:
    """
    Migrate a single relationship record from v1 to v2.

    Returns (migrated_record, warnings). Warnings are non-fatal issues
    that should be reviewed manually.
    """
    warnings = []
    r = dict(record)

    # Add truth_status
    if "truth_status" not in r:
        contradicted = r.get("contradicted_by", [])
        if contradicted:
            # Has known contradictions — flag for manual review rather than
            # silently asserting true
            r["truth_status"] = "disputed"
            warnings.append(
                f"Predicate {r['predicate']} ({r.get('subject_id')} → "
                f"{r.get('object_id')}) has contradicted_by={contradicted}; "
                f"set to 'disputed' — review whether this should be "
                f"'asserted_true' with disputed flag or fully disputed."
            )
        else:
            r["truth_status"] = "asserted_true"

    # Add stmt_id
    if "stmt_id" not in r:
        r["stmt_id"] = statement_id(
            r["subject_id"], r["predicate"], r["object_id"]
        )

    # Tag schema version
    r["schema_version"] = SCHEMA_VERSION_V2

    return r, warnings


def migrate_entity(record: dict) -> dict:
    """Pass entity records through with only a schema version tag."""
    r = dict(record)
    r["schema_version"] = SCHEMA_VERSION_V2
    return r


"""
## File migration

`migrate_file` streams a JSONL file line by line, routing each record through
`migrate_relationship` or `migrate_entity`, and writes the results to
`output_path`. Blank lines and `#` comment lines are preserved verbatim so
the migrated file stays human-readable. `dry_run=True` performs all parsing
and validation but skips the write — useful for a pre-flight check before
committing to an output directory.
"""


def migrate_file(
    input_path: Path,
    output_path: Path,
    dry_run: bool = False,
) -> dict:
    """
    Migrate a JSONL file. Returns a summary dict.

    Each line is expected to be a valid JSON object. Blank lines and
    comment lines (starting with #) are preserved as-is.
    """
    stats = {
        "total": 0,
        "relationships_migrated": 0,
        "entities_passed_through": 0,
        "already_v2": 0,
        "warnings": [],
        "errors": [],
    }

    output_lines = []

    with input_path.open() as f:
        for lineno, raw in enumerate(f, 1):
            stripped = raw.rstrip("\n")

            # Pass blank lines and comments through unchanged
            if not stripped or stripped.startswith("#"):
                output_lines.append(raw)
                continue

            stats["total"] += 1

            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as e:
                stats["errors"].append(f"Line {lineno}: JSON parse error: {e}")
                output_lines.append(raw)
                continue

            # Already migrated?
            if record.get("schema_version") == SCHEMA_VERSION_V2:
                stats["already_v2"] += 1
                output_lines.append(raw)
                continue

            if is_relationship_record(record):
                migrated, warnings = migrate_relationship(record)
                stats["relationships_migrated"] += 1
                for w in warnings:
                    stats["warnings"].append(f"Line {lineno}: {w}")
            else:
                migrated = migrate_entity(record)
                stats["entities_passed_through"] += 1

            output_lines.append(json.dumps(migrated, ensure_ascii=False) + "\n")

    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w") as f:
            f.writelines(output_lines)

    return stats


"""
## Optional: restructure Supports/Refutes

Not run by default. `build_stmt_id_index` and `restructure_supports` together
implement the optional follow-on migration that rewires `SUPPORTS`/`REFUTES`
edges from Hypothesis `entity_id` targets to the relationship `stmt_id` targets
they correspond to. This enables higher-order predication: a paper can assert
`SUPPORTS` against a specific claim (a `stmt_id`) rather than against a vague
Hypothesis entity.

Precondition: the relationship JSONL must already have been migrated (all
`stmt_id` fields populated) before calling `restructure_supports`. The
`hypothesis_to_claim_map` must be constructed manually or via a separate
analysis step — it cannot be derived from the JSONL alone.
"""


def build_stmt_id_index(relationship_jsonl: Path) -> dict[str, dict]:
    """
    Build a {stmt_id: record} index from a migrated relationship JSONL.

    Used by restructure_supports() to resolve Hypothesis entity_ids to
    the relationship stmt_ids they correspond to.
    """
    index = {}
    with relationship_jsonl.open() as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                record = json.loads(stripped)
                if "stmt_id" in record:
                    index[record["stmt_id"]] = record
            except json.JSONDecodeError:
                pass
    return index


def restructure_supports(
    supports_refutes_jsonl: Path,
    hypothesis_to_claim_map: dict[str, list[str]],
    output_path: Path,
) -> dict:
    """
    Rewire Supports/Refutes records from Hypothesis entity_ids to the
    relationship stmt_ids that embody those hypotheses.

    hypothesis_to_claim_map: {hypothesis_entity_id: [stmt_id, ...]}
    Built from domain knowledge about which specific claims correspond to
    which hypothesis entities. This mapping must be constructed manually
    or via a separate analysis step — it cannot be derived from the JSONL
    alone.

    Records that cannot be mapped are passed through unchanged with a
    warning tag.
    """
    stats = {"rewired": 0, "unmapped": 0, "errors": []}
    output_lines = []

    with supports_refutes_jsonl.open() as f:
        for lineno, raw in enumerate(f, 1):
            stripped = raw.rstrip("\n")
            if not stripped or stripped.startswith("#"):
                output_lines.append(raw)
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as e:
                stats["errors"].append(f"Line {lineno}: {e}")
                output_lines.append(raw)
                continue

            pred = record.get("predicate", "")
            if pred in ("SUPPORTS", "REFUTES"):
                obj_id = record.get("object_id", "")
                mapped_stmts = hypothesis_to_claim_map.get(obj_id)
                if mapped_stmts:
                    # Expand one Supports/Refutes into one per mapped claim
                    for stmt_id_target in mapped_stmts:
                        new_record = dict(record)
                        new_record["object_id"] = stmt_id_target
                        new_record["object_type"] = "relationship"
                        new_record["stmt_id"] = statement_id(
                            new_record["subject_id"], pred, stmt_id_target
                        )
                        output_lines.append(
                            json.dumps(new_record, ensure_ascii=False) + "\n"
                        )
                        stats["rewired"] += 1
                else:
                    record["_migration_note"] = "hypothesis_not_mapped"
                    output_lines.append(
                        json.dumps(record, ensure_ascii=False) + "\n"
                    )
                    stats["unmapped"] += 1
            else:
                output_lines.append(raw)

    with output_path.open("w") as f:
        f.writelines(output_lines)

    return stats


"""
## CLI

`main` wires `migrate_file` to an `argparse` CLI. It accepts an input JSONL
path, an output path, and an optional `--dry-run` flag. Non-zero exit on
parse errors; warnings (disputed records) are printed but do not cause failure.
"""


def main():
    parser = argparse.ArgumentParser(
        description="Migrate medlit JSONL from schema v1 to v2."
    )
    parser.add_argument("input", type=Path, help="Input JSONL file")
    parser.add_argument("output", type=Path, help="Output JSONL file")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate without writing output",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: {args.input} does not exist", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print(f"Dry run: reading {args.input}")
    else:
        print(f"Migrating {args.input} → {args.output}")

    stats = migrate_file(args.input, args.output, dry_run=args.dry_run)

    print(f"\nSummary:")
    print(f"  Total records:          {stats['total']}")
    print(f"  Relationships migrated: {stats['relationships_migrated']}")
    print(f"  Entities passed through:{stats['entities_passed_through']}")
    print(f"  Already v2 (skipped):   {stats['already_v2']}")

    if stats["warnings"]:
        print(f"\nWarnings ({len(stats['warnings'])}):")
        for w in stats["warnings"]:
            print(f"  ⚠  {w}")

    if stats["errors"]:
        print(f"\nErrors ({len(stats['errors'])}):")
        for e in stats["errors"]:
            print(f"  ✗  {e}")
        sys.exit(1)

    if args.dry_run:
        print("\nDry run complete — no files written.")
    else:
        print(f"\nDone. Written to {args.output}")


if __name__ == "__main__":
    main()
