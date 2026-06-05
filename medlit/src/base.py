"""Base models for the medlit schema.

Schema version: 2.0.0
Changes from 1.0.0:
  - Added TruthStatus enum (from Holmes unified Statement model)
  - Added statement_id() for content-addressed relationship IDs
  - Added Trait marker classes (Symmetric, Transitive, Functional,
    InverseFunctional, Inverse) matching the Holmes formal definition
  - These enable E ⊆ V at the medlit level: relationships gain stable,
    deterministic IDs so they can be referenced by higher-order predicates
    (Contradicts, meta-analysis aggregations, etc.)
"""

from typing import Optional, Generic, TypeVar, ForwardRef, get_args, get_origin
import sys
import uuid
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


"""
## BaseRelationship

Minimal base class replacing the external `kgschema` dependency.
`subject_id` and `object_id` remain `str` for pipeline and Postgres
compatibility — typed subject/object fields (R6) are deferred pending a
schema update.
"""


class BaseRelationship(BaseModel):
    """Base class for all relationship types."""
    subject_id: str
    object_id: str
    predicate: str

    def get_edge_type(self) -> str:
        return self.predicate


"""
## Extraction provenance and metadata

Support models for recording *how* a record was produced: which pipeline
version ran, which LLM was used, which prompt template was applied, and
when and where extraction happened. These fields are orthogonal to the
medical content — they enable reproducibility, debugging, and pipeline
evolution tracking.
"""


class ModelInfo(BaseModel):
    """Information about the model used for extraction."""
    name: str
    version: str


class ExtractionProvenance(BaseModel):
    """
    Complete provenance metadata for an extraction.

    Enables:
    - Reproducing exact extraction with same code/models/prompts
    - Comparing outputs from different pipeline versions
    - Debugging quality issues
    - Tracking pipeline evolution over time
    - Meeting reproducibility requirements for research

    Example queries enabled by provenance:
    - "Find all papers extracted with prompt v1 so I can re-extract with v2"
    - "Which papers were extracted with uncommitted code changes?"
    - "Compare entity extraction quality between llama3.1:70b and claude-4"
    """
    extraction_pipeline: Optional["ExtractionPipelineInfo"] = None
    models: dict[str, ModelInfo] = Field(default_factory=dict)
    prompt: Optional["PromptInfo"] = None
    execution: Optional["ExecutionInfo"] = None
    entity_resolution: Optional["EntityResolutionInfo"] = None
    model_info: Optional[ModelInfo] = None  # Legacy support


class SectionType(str, Enum):
    """Type of section in a paper."""
    ABSTRACT = "abstract"
    INTRODUCTION = "introduction"
    METHODS = "methods"
    RESULTS = "results"
    DISCUSSION = "discussion"
    CONCLUSION = "conclusion"


class TextSpanRef(BaseModel):
    """
    Structural locator for text within a parsed document.

    Uses structural coordinates (section type, paragraph index, sentence
    index) to locate text before final character offsets are computed.
    Distinct from TextSpan (entity.py), which is a graph entity anchor
    with precise character offsets.
    """
    paper_id: str
    section_type: SectionType
    paragraph_idx: int
    sentence_idx: Optional[int] = None
    text_span: Optional[str] = None
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None


class ExtractionMethod(str, Enum):
    """Method used for extraction."""
    SCISPACY_NER = "scispacy_ner"
    LLM = "llm"
    TABLE_PARSER = "table_parser"
    PATTERN_MATCH = "pattern_match"
    MANUAL = "manual"


class StudyType(str, Enum):
    """Type of study."""
    OBSERVATIONAL = "observational"
    RCT = "rct"
    META_ANALYSIS = "meta_analysis"
    CASE_REPORT = "case_report"
    REVIEW = "review"


class Polarity(str, Enum):
    """Polarity of evidence relative to a claim."""
    SUPPORTS = "supports"
    REFUTES = "refutes"
    NEUTRAL = "neutral"


class EvidenceType(BaseModel):
    """
    The type of evidence supporting a relationship, linked to evidence
    ontologies (ECO, SEPIO).

    Examples:
        RCT: ontology_id="ECO:0007673"
        Observational: ontology_id="ECO:0000203"
    """
    ontology_id: str
    ontology_label: str
    description: Optional[str] = None


class Measurement(BaseModel):
    """
    Quantitative measurements associated with relationships.

    Stores numerical data with appropriate metadata for statistical
    analysis and evidence quality assessment.

    Example:
        >>> measurement = Measurement(
        ...     value=0.59,
        ...     value_type="response_rate",
        ...     p_value=0.001,
        ...     confidence_interval=(0.52, 0.66),
        ...     study_population="BRCA-mutated breast cancer patients"
        ... )
    """
    value: float
    unit: Optional[str] = None
    value_type: str
    p_value: Optional[float] = None
    confidence_interval: Optional[tuple[float, float]] = None
    study_population: Optional[str] = None
    measurement_context: Optional[str] = None


"""
## Truth status

`TruthStatus` is the graph's explicit commitment to a proposition. Presence
in the graph does NOT assert — `truth_status` carries the assertion
explicitly. The medlit variant adds `SUPERSEDED` to the Holmes set: a
finding may be correct within its original population and methodology but
replaced by stronger subsequent evidence. This is distinct from
`ASSERTED_FALSE` (the claim was wrong) and `RETRACTED` (the paper was
formally withdrawn).

Lifecycle: `hypothetical → asserted_true | asserted_false → disputed |
retracted | superseded`
"""


class TruthStatus(str, Enum):
    """
    Graph-level commitment to a proposition.

    Every relationship (predicate instance) carries truth_status. Presence
    in the graph does NOT by itself assert the proposition — truth_status
    carries the assertion explicitly.

    Lifecycle:
        hypothetical → asserted_true | asserted_false → disputed |
        retracted | superseded

    superseded is medlit-specific: a finding may be correct within its
    original population/methodology but replaced by stronger subsequent
    evidence. This is distinct from asserted_false (which means the claim
    was wrong) and retracted (which means the paper was formally withdrawn).
    """
    ASSERTED_TRUE = "asserted_true"
    ASSERTED_FALSE = "asserted_false"
    HYPOTHETICAL = "hypothetical"
    DISPUTED = "disputed"
    RETRACTED = "retracted"
    SUPERSEDED = "superseded"   # medlit addition: replaced by stronger evidence


"""
## Content-addressed relationship IDs

`statement_id` produces a deterministic string key for a proposition
`(subject_id, predicate, object_id)`. Two records expressing the same
claim compute the same key, enabling O(1) deduplication across extraction
runs and allowing higher-order predicates (`Contradicts`) to reference
relationships by stable identity rather than by UUID.

`statement_uuid` derives a UUID5 from the same key for systems (e.g. the
existing Postgres storage layer) that require a UUID primary key.
"""


def statement_id(subject_id: str, predicate_name: str, object_id: str) -> str:
    """
    Compute a content-addressed string ID for a relationship instance.

    Two instances expressing the same proposition (same subject, predicate,
    and object) compute the same stmt_id. This makes deduplication across
    extraction runs O(1) and ensures that multi-paper support for the same
    claim attaches to a single canonical relationship rather than creating
    duplicate records with different UUIDs.

    The string form is human-readable; use statement_uuid() for systems
    that require a UUID.

    Example:
        >>> statement_id("RxNorm:1187832", "TREATS", "C0006142")
        'stmt:RxNorm:1187832:TREATS:C0006142'
    """
    return f"stmt:{subject_id}:{predicate_name}:{object_id}"


def statement_uuid(subject_id: str, predicate_name: str, object_id: str) -> uuid.UUID:
    """
    Deterministic UUID5 derived from the content-addressed statement ID.

    Useful for systems (e.g. the existing Postgres storage layer) that
    require a UUID primary key. UUID5 is deterministic: same inputs always
    produce the same UUID, enabling backward-compatible migration of existing
    UUID-keyed records by recomputing rather than re-extracting.

    Example:
        >>> u = statement_uuid("RxNorm:1187832", "TREATS", "C0006142")
        >>> isinstance(u, uuid.UUID)
        True
    """
    sid = statement_id(subject_id, predicate_name, object_id)
    return uuid.uuid5(uuid.NAMESPACE_URL, sid)


"""
## Trait markers

Traits are declarative semantic properties of predicate types — they belong
to the class, not to any instance. The set matches the Holmes formal
definition: `Symmetric`, `Transitive`, `Functional`, `InverseFunctional`,
and `Inverse[P]`. Usage in medlit: `InteractsWith` is `Symmetric`;
`SubtypeOf` is `Transitive`; `Encodes` and `IsEncodedBy` are mutual
`Inverse`s.
"""


class Trait:
    """Marker base for all semantic traits."""


class Transitive(Trait):
    """
    If A -[p]-> B and B -[p]-> C then A -[p]-> C.
    Applied to: SubtypeOf, LocatedIn (if added).
    """


class Symmetric(Trait):
    """
    If A -[p]-> B then B -[p]-> A.
    Applied to: InteractsWith, SameAs.
    One stored edge suffices; the symmetric direction is derived.
    """


class Functional(Trait):
    """
    A given subject has at most one object via this predicate.
    Applied to: HasTrueIdentity (Holmes). In medlit, potentially
    applicable to unique ontology mappings.
    """


class InverseFunctional(Trait):
    """A given object has at most one subject via this predicate."""


P = TypeVar('P')


class Inverse(Trait, Generic[P]):
    """
    This predicate is the inverse of P.
    E.g. Encodes and IsEncodedBy are inverses.
    """


def get_inverse(cls: type) -> type | None:
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


"""
## Provenance metadata

Detailed provenance classes capturing the extraction pipeline version, the
prompt used, execution context, and entity resolution statistics. These are
optional on `ExtractionProvenance` — older records may carry only
`model_info` (the legacy field).
"""


class ExtractionPipelineInfo(BaseModel):
    """
    Information about the extraction pipeline version.

    Tracks the exact code version that performed entity/relationship
    extraction. Essential for reproducibility and debugging.
    """
    name: str
    version: str
    git_commit: str
    git_commit_short: str
    git_branch: str
    git_dirty: bool
    repo_url: str


class PromptInfo(BaseModel):
    """
    Information about the prompt used.

    prompt checksum enables exact reproduction; schema_version tracks
    which entity/predicate vocabulary the prompt was built against.
    """
    version: str
    template: str
    checksum: Optional[str] = None
    schema_version: Optional[str] = None


class ExecutionInfo(BaseModel):
    """Information about when and where extraction was performed."""
    timestamp: str
    hostname: str
    python_version: str
    duration_seconds: Optional[float] = None


class EntityResolutionInfo(BaseModel):
    """
    Information about entity resolution process.

    Tracks how entities were matched to canonical IDs.
    """
    canonical_entities_matched: int
    new_entities_created: int
    similarity_threshold: float
    embedding_model: str
