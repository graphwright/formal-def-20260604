"""Medlit relationship definitions.

Schema version: 2.0.0
Changes from 1.0.0:

Structural changes
------------------
  - BaseMedicalRelationship gains truth_status (TruthStatus, default
    HYPOTHETICAL) and stmt_id (content-addressed string ID).
  - Trait mixins applied to InteractsWith (Symmetric), SubtypeOf
    (Transitive), SameAs (Symmetric), Encodes (Inverse[IsEncodedBy]).
  - New Contradicts predicate (higher-order: both ends are stmt_ids,
    enabling dispute tracking between any two relationship instances).
  - Supports and Refutes range expanded: object_id may now be a stmt_id
    (a relationship's content-addressed ID) rather than only a Hypothesis
    entity_id. This is backward-compatible — existing Hypothesis-pointing
    records are valid; new records may point at any relationship.
  - Models are frozen (ConfigDict frozen=True). truth_status updates
    use model_copy(update={...}).

R6 status
---------
  subject_id and object_id remain str for pipeline / Postgres
  compatibility. The typed subject/object fields from the Holmes schema
  require a kgschema update and are deferred. Domain/range constraints
  are currently enforced in MedlitDomain.predicate_constraints; they
  will move into type annotations once kgschema provides BaseStatement.

Migration path for existing JSONL
----------------------------------
  See migrate_jsonl.py. All existing records are valid v2 records after:
    1. truth_status = "asserted_true"   (all ingested data was ground truth)
    2. stmt_id = statement_id(subject_id, predicate, object_id)
  No re-extraction required.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict
from kgschema.relationship import BaseRelationship
from medlit_schema.base import (
    Measurement,
    TruthStatus,
    Symmetric,
    Transitive,
    Inverse,
    statement_id,
)


class EvidenceItem(BaseModel):
    """
    Lightweight evidence reference for relationships.

    Attributes:
        paper_id: PMC ID of source paper
        study_type: Type of study (observational, rct, etc.)
        sample_size: Number of subjects in the study
        confidence: Confidence score (0.0-1.0)
    """
    paper_id: str
    study_type: str
    sample_size: Optional[int] = None
    confidence: float = 0.5


class BaseMedicalRelationship(BaseRelationship):
    """
    Base class for all medical relationships.

    v2 additions:
      truth_status — the graph's explicit commitment to this proposition.
        Default is HYPOTHETICAL; ingestion pipelines promote to
        ASSERTED_TRUE after quality checks. A disputed finding becomes
        DISPUTED; a retracted paper's relationships become RETRACTED;
        a superseded finding (correct at the time, replaced by better
        evidence) becomes SUPERSEDED.

      stmt_id — content-addressed string ID. Two records expressing the
        same proposition (same subject_id, predicate, object_id) compute
        the same stmt_id, enabling O(1) deduplication across extraction
        runs and allowing higher-order predicates (Contradicts) to
        reference relationships by stable identity rather than UUID.

    Schema Rules:
      - Medical assertion relationships MUST have non-empty evidence_ids.
      - truth_status HYPOTHETICAL is appropriate during ingestion; a
        background consensus pass should promote or dispute.
      - Instances are frozen; update truth_status via
        rel.model_copy(update={'truth_status': TruthStatus.DISPUTED}).
    """
    model_config = ConfigDict(frozen=True)

    # ── v2: truth status and content-addressed ID ────────────────────────
    truth_status: TruthStatus = TruthStatus.HYPOTHETICAL

    stmt_id: Optional[str] = Field(
        default=None,
        description=(
            "Content-addressed ID: statement_id(subject_id, predicate, object_id). "
            "Set at construction time; used by higher-order predicates (Contradicts) "
            "and for deduplication."
        ),
    )

    # ── Provenance (unchanged from v1) ───────────────────────────────────
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    source_papers: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    contradicted_by: list[str] = Field(default_factory=list)
    first_reported_date: Optional[str] = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    measurements: list[Measurement] = Field(default_factory=list)
    properties: dict = Field(default_factory=dict)

    @field_validator("evidence_ids")
    def evidence_required_for_medical_assertions(cls, v):  # pylint: disable=no-self-argument
        if not v or len(v) == 0:
            raise ValueError("Medical relationships must include evidence")
        return v


# ── Medical: Therapeutic ─────────────────────────────────────────────────────

class Treats(BaseMedicalRelationship):
    """
    Drug -[TREATS]-> Disease

    Attributes:
        efficacy: Effectiveness measure or description
        response_rate: Percentage of patients responding (0.0-1.0)
        line_of_therapy: Treatment sequence
        indication: Specific approved use or condition

    Example:
        >>> treats = Treats(
        ...     subject_id="RxNorm:1187832",
        ...     object_id="C0006142",
        ...     predicate="TREATS",
        ...     evidence_ids=["PMC999:results:5:rct"],
        ...     truth_status=TruthStatus.ASSERTED_TRUE,
        ...     stmt_id=statement_id("RxNorm:1187832", "TREATS", "C0006142"),
        ...     response_rate=0.59,
        ...     confidence=0.85,
        ... )
    """
    efficacy: Optional[str] = None
    response_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    line_of_therapy: Optional[Literal[
        "first-line", "second-line", "third-line", "maintenance", "salvage"
    ]] = None
    indication: Optional[str] = None

    def get_edge_type(self) -> str:
        return "TREATS"


class Causes(BaseMedicalRelationship):
    """
    Gene/Mutation/Disease -[CAUSES]-> Disease/Symptom

    Attributes:
        frequency: How often (always, often, sometimes, rarely)
        onset: When symptom typically appears (early, late)
        severity: Typical severity (mild, moderate, severe)
    """
    frequency: Optional[Literal["always", "often", "sometimes", "rarely"]] = None
    onset: Optional[Literal["early", "late"]] = None
    severity: Optional[Literal["mild", "moderate", "severe"]] = None

    def get_edge_type(self) -> str:
        return "CAUSES"


class Prevents(BaseMedicalRelationship):
    """Drug -[PREVENTS]-> Disease"""
    efficacy: Optional[str] = None
    risk_reduction: Optional[float] = Field(None, ge=0.0, le=1.0)

    def get_edge_type(self) -> str:
        return "PREVENTS"


class IncreasesRisk(BaseMedicalRelationship):
    """
    Gene/Mutation -[INCREASES_RISK]-> Disease

    Attributes:
        risk_ratio: Numeric risk increase (e.g., 2.5 = 2.5× higher risk)
        penetrance: Percentage who develop condition (0.0-1.0)
        age_of_onset: Typical age range
        population: Studied population or ethnic group
    """
    risk_ratio: Optional[float] = Field(None, gt=0.0)
    penetrance: Optional[float] = Field(None, ge=0.0, le=1.0)
    age_of_onset: Optional[str] = None
    population: Optional[str] = None

    def get_edge_type(self) -> str:
        return "INCREASES_RISK"


class SideEffect(BaseMedicalRelationship):
    """Drug -[SIDE_EFFECT]-> Symptom"""
    frequency: Optional[Literal["common", "uncommon", "rare"]] = None
    severity: Optional[Literal["mild", "moderate", "severe"]] = None
    reversible: bool = True

    def get_edge_type(self) -> str:
        return "SIDE_EFFECT"


class AssociatedWith(BaseMedicalRelationship):
    """
    Disease/Gene/Biomarker -[ASSOCIATED_WITH]-> Disease

    For relationships where causality is not established but statistical
    association exists.
    """
    association_type: Optional[Literal["positive", "negative", "neutral"]] = None
    strength: Optional[Literal["strong", "moderate", "weak"]] = None
    statistical_significance: Optional[float] = Field(None, ge=0.0, le=1.0)

    def get_edge_type(self) -> str:
        return "ASSOCIATED_WITH"


class InteractsWith(BaseMedicalRelationship, Symmetric):
    """
    Drug -[INTERACTS_WITH]-> Drug

    Symmetric: if A interacts with B then B interacts with A.
    One stored edge suffices.

    Attributes:
        interaction_type: Nature of interaction (synergistic, antagonistic, additive)
        severity: Clinical severity (major, moderate, minor)
        mechanism: Pharmacological mechanism
        clinical_significance: Description of clinical implications
    """
    interaction_type: Optional[Literal["synergistic", "antagonistic", "additive"]] = None
    severity: Optional[Literal["major", "moderate", "minor"]] = None
    mechanism: Optional[str] = None
    clinical_significance: Optional[str] = None

    def get_edge_type(self) -> str:
        return "INTERACTS_WITH"


class ContraindicatedFor(BaseMedicalRelationship):
    """Drug -[CONTRAINDICATED_FOR]-> Disease/Condition"""
    severity: Optional[Literal["absolute", "relative"]] = None
    reason: Optional[str] = None

    def get_edge_type(self) -> str:
        return "CONTRAINDICATED_FOR"


class DiagnosedBy(BaseMedicalRelationship):
    """
    Disease -[DIAGNOSED_BY]-> Procedure/Biomarker

    Attributes:
        sensitivity: True positive rate (0.0-1.0)
        specificity: True negative rate (0.0-1.0)
        standard_of_care: Whether this is standard clinical practice
    """
    sensitivity: Optional[float] = Field(None, ge=0.0, le=1.0)
    specificity: Optional[float] = Field(None, ge=0.0, le=1.0)
    standard_of_care: bool = False

    def get_edge_type(self) -> str:
        return "DIAGNOSED_BY"


class ParticipatesIn(BaseMedicalRelationship):
    """Gene/Protein -[PARTICIPATES_IN]-> Pathway"""
    role: Optional[str] = None
    regulatory_effect: Optional[Literal["activates", "inhibits", "modulates"]] = None

    def get_edge_type(self) -> str:
        return "PARTICIPATES_IN"


# ── Biological ───────────────────────────────────────────────────────────────

class Encodes(BaseRelationship, Inverse['IsEncodedBy']):
    """
    Gene -[ENCODES]-> Protein

    Inverse of IsEncodedBy. One directed edge suffices; the inverse
    direction is derived.
    """
    model_config = ConfigDict(frozen=True)

    def get_edge_type(self) -> str:
        return "ENCODES"


class IsEncodedBy(BaseRelationship, Inverse[Encodes]):
    """
    Protein -[IS_ENCODED_BY]-> Gene

    Derived inverse of Encodes. May be stored explicitly or computed.
    """
    model_config = ConfigDict(frozen=True)

    def get_edge_type(self) -> str:
        return "IS_ENCODED_BY"


class BindsTo(BaseRelationship):
    model_config = ConfigDict(frozen=True)

    def get_edge_type(self) -> str:
        return "BINDS_TO"


class Inhibits(BaseRelationship):
    model_config = ConfigDict(frozen=True)

    def get_edge_type(self) -> str:
        return "INHIBITS"


class Upregulates(BaseRelationship):
    model_config = ConfigDict(frozen=True)

    def get_edge_type(self) -> str:
        return "UPREGULATES"


class Downregulates(BaseRelationship):
    model_config = ConfigDict(frozen=True)

    def get_edge_type(self) -> str:
        return "DOWNREGULATES"


class SubtypeOf(BaseMedicalRelationship, Transitive):
    """
    Disease -[SUBTYPE_OF]-> Disease

    Transitive: if A is a subtype of B and B is a subtype of C, then A is
    a subtype of C. The transitive closure can be computed over the asserted
    edges without storing every inferred pair explicitly.
    """
    def get_edge_type(self) -> str:
        return "SUBTYPE_OF"


class Indicates(BaseMedicalRelationship):
    """Biomarker/Evidence -[INDICATES]-> Disease"""
    def get_edge_type(self) -> str:
        return "INDICATES"


# ── Research Metadata ────────────────────────────────────────────────────────

class ResearchRelationship(BaseRelationship):
    """
    Base for bibliographic/metadata relationships.

    Unlike medical relationships, these don't require evidence_ids because
    they represent bibliographic facts (authorship, citation) rather than
    medical claims.

    Frozen in v2 for consistency with BaseMedicalRelationship.
    """
    model_config = ConfigDict(frozen=True)
    properties: dict = Field(default_factory=dict)


class Cites(ResearchRelationship):
    """
    Paper -[CITES]-> Paper

    Attributes:
        context: Section where citation appears
        sentiment: How the citation is used (supports, contradicts, mentions)
    """
    context: Optional[Literal["introduction", "methods", "results", "discussion"]] = None
    sentiment: Optional[Literal["supports", "contradicts", "mentions"]] = None

    def get_edge_type(self) -> str:
        return "CITES"


class StudiedIn(ResearchRelationship):
    """Medical entity -[STUDIED_IN]-> Paper"""
    role: Optional[Literal["primary_focus", "secondary_finding", "mentioned"]] = None
    section: Optional[Literal["results", "methods", "discussion", "introduction"]] = None

    def get_edge_type(self) -> str:
        return "STUDIED_IN"


class AuthoredBy(ResearchRelationship):
    """Paper -[AUTHORED_BY]-> Author"""
    position: Optional[Literal["first", "last", "corresponding", "middle"]] = None

    def get_edge_type(self) -> str:
        return "AUTHORED_BY"


class PartOf(ResearchRelationship):
    """Paper -[PART_OF]-> ClinicalTrial"""
    publication_type: Optional[Literal["protocol", "results", "analysis"]] = None

    def get_edge_type(self) -> str:
        return "PART_OF"


class SameAs(ResearchRelationship, Symmetric):
    """
    Provisional identity link between two entities.

    Symmetric: if A same-as B then B same-as A.
    Not a BaseMedicalRelationship — no evidence_ids required.

    Attributes:
        confidence: Strength of identity claim (0.0-1.0)
        resolution: Outcome after review ("merged", "distinct", None=unreviewed)
        note: Free text explaining the ambiguity
    """
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    resolution: Optional[Literal["merged", "distinct"]] = None
    note: Optional[str] = None

    def get_edge_type(self) -> str:
        return "SAME_AS"


# ── Hypothesis / Scientific Method ───────────────────────────────────────────

class Predicts(BaseMedicalRelationship):
    """Hypothesis -[PREDICTS]-> Disease/Outcome"""
    prediction_type: Optional[Literal["positive", "negative", "conditional"]] = None
    conditions: Optional[str] = None
    testable: bool = True

    def get_edge_type(self) -> str:
        return "PREDICTS"


class TestedBy(BaseMedicalRelationship):
    """Hypothesis -[TESTED_BY]-> Paper/ClinicalTrial"""
    test_outcome: Optional[Literal["supported", "refuted", "inconclusive"]] = None
    methodology: Optional[str] = None
    study_design_id: Optional[str] = None

    def get_edge_type(self) -> str:
        return "TESTED_BY"


class Supports(BaseMedicalRelationship):
    """
    Evidence -[SUPPORTS]-> Hypothesis | Relationship

    v2: object_id may be a Hypothesis entity_id (existing behaviour) or
    a relationship stmt_id. When object_id is a stmt_id, this edge
    records that a body of evidence supports a specific medical claim
    (e.g. a Treats edge) rather than an abstract hypothesis node.

    Backward compatible: all v1 records pointing at Hypothesis entities
    remain valid.

    Attributes:
        support_strength: Strength of support (strong, moderate, weak)
        object_type: Hint for query routing ("hypothesis" or "relationship")
    """
    support_strength: Optional[Literal["strong", "moderate", "weak"]] = None
    object_type: Literal["hypothesis", "relationship"] = "hypothesis"

    def get_edge_type(self) -> str:
        return "SUPPORTS"


class Refutes(BaseMedicalRelationship):
    """
    Evidence -[REFUTES]-> Hypothesis | Relationship

    v2: same range expansion as Supports. object_id may be a stmt_id.
    When pointing at a relationship stmt_id, update that relationship's
    truth_status to DISPUTED and record this refutation's evidence_ids.

    Attributes:
        refutation_strength: Strength of refutation (strong, moderate, weak)
        alternative_explanation: Alternative explanation for observations
        limitations: Limitations of the refuting evidence
        object_type: Hint for query routing ("hypothesis" or "relationship")
    """
    refutation_strength: Optional[Literal["strong", "moderate", "weak"]] = None
    alternative_explanation: Optional[str] = None
    limitations: Optional[str] = None
    object_type: Literal["hypothesis", "relationship"] = "hypothesis"

    def get_edge_type(self) -> str:
        return "REFUTES"


class Generates(BaseMedicalRelationship):
    """ClinicalTrial/Paper -[GENERATES]-> Evidence"""
    evidence_type: Optional[str] = None
    eco_type: Optional[str] = None
    quality_score: Optional[float] = Field(None, ge=0.0, le=1.0)

    def get_edge_type(self) -> str:
        return "GENERATES"


# ── New in v2: Higher-order dispute tracking ──────────────────────────────────

class Contradicts(ResearchRelationship, Symmetric):
    """
    Relationship -[CONTRADICTS]-> Relationship

    Higher-order: both subject_id and object_id are stmt_ids — the
    content-addressed IDs of BaseMedicalRelationship instances. Used to
    surface direct conflicts between two medical claims (e.g. one paper's
    TREATS assertion vs. another's finding of no effect).

    Symmetric: if A contradicts B then B contradicts A. Store one
    direction; the other is derived.

    This predicate does NOT inherit from BaseMedicalRelationship because
    the relationship *between* two claims is a structural observation, not
    a medical assertion requiring its own evidence_ids. The referenced
    relationships carry their own provenance.

    Attributes:
        subject_stmt_id: stmt_id of the first relationship
        object_stmt_id: stmt_id of the second relationship
        contradiction_type: Nature of conflict (direction, magnitude,
            population, methodology)
        resolved: Whether the contradiction has been adjudicated
        resolution_note: Free text explaining resolution if any
    """
    # Override subject_id / object_id semantics: these ARE stmt_ids, not
    # entity_ids. The field names are kept for pipeline compatibility but
    # their content is a relationship stmt_id.
    contradiction_type: Optional[Literal[
        "direction", "magnitude", "population", "methodology", "other"
    ]] = None
    resolved: bool = False
    resolution_note: Optional[str] = None

    def get_edge_type(self) -> str:
        return "CONTRADICTS"


# ── Relationship factory ──────────────────────────────────────────────────────
# Retained for backward compatibility with the ingestion pipeline.
# New code should construct relationship instances directly.
# Note: create_relationship cannot populate stmt_id automatically because
# it would need to call statement_id(), which is now imported from base.
# Callers should set stmt_id explicitly:
#
#   rel = Treats(
#       subject_id=..., object_id=..., predicate="TREATS",
#       stmt_id=statement_id(subject_id, "TREATS", object_id),
#       truth_status=TruthStatus.ASSERTED_TRUE,
#       ...
#   )

RELATIONSHIP_TYPE_MAP = {
    "TREATS": Treats,
    "PREVENTS": Prevents,
    "CONTRAINDICATED_FOR": ContraindicatedFor,
    "SIDE_EFFECT": SideEffect,
    "CAUSES": Causes,
    "INCREASES_RISK": IncreasesRisk,
    "ASSOCIATED_WITH": AssociatedWith,
    "INTERACTS_WITH": InteractsWith,
    "DIAGNOSED_BY": DiagnosedBy,
    "PARTICIPATES_IN": ParticipatesIn,
    "INDICATES": Indicates,
    "SUBTYPE_OF": SubtypeOf,
    "SAME_AS": SameAs,
    "ENCODES": Encodes,
    "IS_ENCODED_BY": IsEncodedBy,
    "BINDS_TO": BindsTo,
    "INHIBITS": Inhibits,
    "UPREGULATES": Upregulates,
    "DOWNREGULATES": Downregulates,
    "CITES": Cites,
    "STUDIED_IN": StudiedIn,
    "AUTHORED_BY": AuthoredBy,
    "PART_OF": PartOf,
    "PREDICTS": Predicts,
    "TESTED_BY": TestedBy,
    "SUPPORTS": Supports,
    "REFUTES": Refutes,
    "GENERATES": Generates,
    "CONTRADICTS": Contradicts,
}


def create_relationship(
    predicate: str,
    subject_id: str,
    object_id: str,
    auto_stmt_id: bool = True,
    **kwargs,
) -> BaseRelationship:
    """
    Factory function for creating typed relationship instances.

    v2 addition: auto_stmt_id=True automatically computes and injects
    stmt_id from (subject_id, predicate, object_id) if not already
    provided in kwargs. Set auto_stmt_id=False to suppress this (e.g.
    when loading pre-computed stmt_ids from JSONL).

    Args:
        predicate: Relationship type (must match RELATIONSHIP_TYPE_MAP keys)
        subject_id: Entity ID of the subject
        object_id: Entity ID of the object
        auto_stmt_id: Whether to compute stmt_id automatically
        **kwargs: Relationship-specific fields

    Raises:
        ValueError: If predicate is not recognized
    """
    if predicate not in RELATIONSHIP_TYPE_MAP:
        raise ValueError(
            f"Unknown predicate: {predicate}. "
            f"Valid predicates: {sorted(RELATIONSHIP_TYPE_MAP.keys())}"
        )
    if auto_stmt_id and "stmt_id" not in kwargs:
        kwargs["stmt_id"] = statement_id(subject_id, predicate, object_id)

    cls = RELATIONSHIP_TYPE_MAP[predicate]
    return cls(subject_id=subject_id, predicate=predicate, object_id=object_id, **kwargs)
