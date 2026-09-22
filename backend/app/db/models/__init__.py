from app.db.session import Base
from app.db.models.core import Organization, User, OrganizationMembership, Project, ProjectVersion, AuditLog
from app.db.models.knowledge_asset import KnowledgeAsset
from app.db.models.intake import SourceAsset
from app.db.models.operations import (
    ProcessingJob, JobEvent, ConfidencePolicy, ReviewTask, ReviewDecision, DecisionTrace,
    ReviewPipelineRun, PipelineStageRun
)
from app.db.models.document_memory import (
    Document, DocumentSheet, SheetRegion, TitleBlockExtraction, ExtractedText,
    ExtractedTable, ExtractedTableCell, DetectedSymbol, SymbolOccurrence, VisualEvidence
)
from app.db.models.normative_memory import (
    NormativeDocument, NormativeClause, NormativeCriterion, NormativeEmbedding
)
from app.db.models.template_memory import (
    TitleBlockTemplate, SymbolLibrary, SymbolTemplate,
    TableSchemaTemplate, OntologyDictionary
)
from app.db.models.decision_memory import (
    RuleDefinition, RuleExecution, ReviewRun, RuleFinding, FindingResolution,
    FindingEvidence, HumanFeedback, DecisionPrecedent
)
from app.db.models.reporting import (
    AuditReport, EvidenceManifest, ProjectStageReportSnapshot
)
from app.db.models.evaluation import (
    EvaluationDataset, EvaluationSample, AnnotationSet, EvaluationRun, EvaluationMetric
)
from app.db.models.active_learning import (
    ManualAnnotation, KnowledgeLibraryEntry, ActiveLearningPromotion
)
from app.db.models.intake_extractions import (
    SourceExtraction, ExtractedItem, RuleDocument, RuleDocumentItem,
    StructuredTable, StructuredSymbol, StructuredEquipment, StructuredRulePremise
)
from app.db.models.research import (
    ResearchQuery, ResearchResult, ResearchSource, ResearchItem
)
from app.db.models.completeness import (
    ProjectDeliverableRequirement, DocumentDeliverable, ProjectCompletenessEvaluation
)
from app.db.models.observations import (
    AuditObservation, ObservationResponse
)
from app.db.models.knowledge_base import (
    KnowledgeItem, KnowledgeChunk
)
from app.db.models.assistant import (
    AssistantInteraction
)
from app.db.models.maturity import (
    ProjectMaturityProfile
)
from app.db.models.acquisition import (
    InformationAcquisitionRequest
)
from app.db.models.translations import (
    Translation
)
from app.db.models.symbol_catalog import (
    SymbolTemplateVersion, SymbolGeometricFeature, SymbolFeatureRelation,
    SymbolSourceEvidence, SymbolReviewDecision, SymbolUnknownResearchCase
)

__all__ = [
    "Base",
    "Translation",
    "InformationAcquisitionRequest",
    "ProjectMaturityProfile",
    "AssistantInteraction",
    "KnowledgeItem",
    "KnowledgeChunk",
    "ProjectDeliverableRequirement",
    "DocumentDeliverable",
    "ProjectCompletenessEvaluation",
    "AuditObservation",
    "ObservationResponse",
    "ResearchQuery",
    "ResearchResult",
    "ResearchSource",
    "ResearchItem",
    "Organization",
    "User",
    "OrganizationMembership",
    "Project",
    "ProjectVersion",
    "AuditLog",
    "EvaluationDataset",
    "EvaluationSample",
    "AnnotationSet",
    "EvaluationRun",
    "EvaluationMetric",
    "KnowledgeAsset",
    "SourceAsset",
    "ProcessingJob",
    "JobEvent",
    "ConfidencePolicy",
    "ReviewTask",
    "ReviewDecision",
    "DecisionTrace",
    "ReviewPipelineRun",
    "PipelineStageRun",
    "Document",
    "DocumentSheet",
    "SheetRegion",
    "TitleBlockExtraction",
    "ExtractedText",
    "ExtractedTable",
    "ExtractedTableCell",
    "DetectedSymbol",
    "SymbolOccurrence",
    "VisualEvidence",
    "NormativeDocument",
    "NormativeClause",
    "NormativeCriterion",
    "NormativeEmbedding",
    "TitleBlockTemplate",
    "SymbolLibrary",
    "SymbolTemplate",
    "SymbolTemplateVersion",
    "SymbolGeometricFeature",
    "SymbolFeatureRelation",
    "SymbolSourceEvidence",
    "SymbolReviewDecision",
    "SymbolUnknownResearchCase",
    "TableSchemaTemplate",
    "OntologyDictionary",
    "RuleDefinition",
    "RuleExecution",
    "ReviewRun",
    "RuleFinding",
    "FindingResolution",
    "FindingEvidence",
    "HumanFeedback",
    "DecisionPrecedent",
    "AuditReport",
    "EvidenceManifest",
    "ManualAnnotation",
    "KnowledgeLibraryEntry",
    "ActiveLearningPromotion",
    "SourceExtraction",
    "ExtractedItem",
    "RuleDocument",
    "RuleDocumentItem",
    "StructuredTable",
    "StructuredSymbol",
    "StructuredEquipment",
    "StructuredRulePremise",
]

