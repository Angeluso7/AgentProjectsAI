import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.template_memory import SymbolTemplate
from app.db.models.symbol_catalog import (
    SymbolTemplateVersion,
    SymbolGeometricFeature,
    SymbolFeatureRelation,
    SymbolSourceEvidence,
    SymbolReviewDecision,
    SymbolUnknownResearchCase,
)
from app.db.models.document_memory import DetectedSymbol
from app.schemas.symbol_catalog import (
    CanonicalSymbolTemplateDetail,
    SymbolTemplateVersionDetail,
    SymbolGeometricFeatureDTO,
    SymbolFeatureRelationDTO,
    SymbolSourceEvidenceDTO,
    PromoteCandidateToCanonicalRequest,
    PromoteCandidateToCanonicalResponse,
    MatchOccurrenceRequest,
    MatchOccurrenceResponse,
    SymbolReviewDecisionRequest,
    SymbolReviewDecisionResponse,
)
from app.services.symbols.canonical_catalog_service import CanonicalPipingCatalogService

router = APIRouter()


def _map_template_version(v: SymbolTemplateVersion) -> SymbolTemplateVersionDetail:
    features_dto = [
        SymbolGeometricFeatureDTO(
            id=f.id,
            feature_type=f.feature_type,
            feature_count=f.feature_count,
            feature_parameters=f.feature_parameters or {},
            normalized_bbox=f.normalized_bbox or [],
            relative_position=f.relative_position,
            orientation_degrees=f.orientation_degrees,
            confidence=f.confidence,
            relationship_group=f.relationship_group,
        )
        for f in (v.geometric_features or [])
    ]

    evidence_dto = None
    if v.source_evidence:
        e = v.source_evidence
        evidence_dto = SymbolSourceEvidenceDTO(
            id=e.id,
            source_document_id=e.source_document_id,
            source_document_hash=e.source_document_hash,
            evidence_kind=e.evidence_kind,
            page_number=e.page_number,
            sheet_id=e.sheet_id,
            table_id=e.table_id,
            cell_id=e.cell_id,
            bbox_normalized=e.bbox_normalized or [],
            cell_bbox=e.cell_bbox,
            inner_drawing_bbox=e.inner_drawing_bbox,
            symbol_crop_bbox=e.symbol_crop_bbox,
            crop_image_path=e.crop_image_path,
            crop_image_hash=e.crop_image_hash,
            source_excerpt=e.source_excerpt,
            grid_source=e.grid_source,
            geometric_confidence=e.geometric_confidence,
            source_standard_or_project=e.source_standard_or_project,
            source_revision=e.source_revision,
            source_date=e.source_date,
        )

    return SymbolTemplateVersionDetail(
        id=v.id,
        symbol_template_id=v.symbol_template_id,
        version_number=v.version_number,
        approval_status=v.approval_status,
        source_kind=v.source_kind,
        canonical_crop_path=v.canonical_crop_path,
        canonical_crop_hash=v.canonical_crop_hash,
        orientation_policy=v.orientation_policy,
        scale_policy=v.scale_policy,
        geometric_signature=v.geometric_signature or {},
        perceptual_signature=v.perceptual_signature or {},
        matcher_thresholds=v.matcher_thresholds or {},
        approved_by=v.approved_by,
        approved_at=v.approved_at,
        notes=v.notes,
        created_at=v.created_at,
        geometric_features=features_dto,
        source_evidence=evidence_dto,
    )


def _map_canonical_template(t: SymbolTemplate) -> CanonicalSymbolTemplateDetail:
    versions_dto = [_map_template_version(v) for v in (t.versions or [])]
    return CanonicalSymbolTemplateDetail(
        id=t.id,
        canonical_code=t.canonical_code or getattr(t, "symbol_class", ""),
        canonical_name=t.canonical_name or getattr(t, "display_name", ""),
        category=t.category or "valve",
        subcategory=t.subcategory or getattr(t, "symbol_class", "gate_valve"),
        discipline=t.discipline or "piping",
        technical_function=t.technical_function,
        standard_reference=t.standard_reference,
        status=t.status or "active",
        current_version_id=t.current_version_id,
        aliases=t.aliases or [],
        created_at=t.created_at,
        updated_at=t.updated_at or t.created_at,
        versions=versions_dto,
    )


@router.get("/templates", response_model=List[CanonicalSymbolTemplateDetail])
def list_canonical_templates(
    family: Optional[str] = Query(None, description="Filtra por canonical_code o symbol_family"),
    discipline: Optional[str] = Query(None, description="Filtra por disciplina"),
    status: Optional[str] = Query(None, description="draft, active, deprecated, superseded"),
    db: Session = Depends(get_db),
):
    """
    Lista las plantillas canónicas de simbología con sus versiones activas y rasgos geométricos.
    """
    service = CanonicalPipingCatalogService(db)
    templates = service.list_canonical_templates(family=family, discipline=discipline, status=status)
    return [_map_canonical_template(t) for t in templates]


@router.get("/templates/{template_id}", response_model=CanonicalSymbolTemplateDetail)
def get_canonical_template(template_id: str, db: Session = Depends(get_db)):
    """
    Obtiene el detalle completo de una plantilla canónica por su identificador.
    """
    service = CanonicalPipingCatalogService(db)
    t = service.get_canonical_template(template_id)
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantilla canónica no encontrada")
    return _map_canonical_template(t)


@router.post("/promote-candidate", response_model=PromoteCandidateToCanonicalResponse)
def promote_candidate_to_canonical(
    payload: PromoteCandidateToCanonicalRequest,
    db: Session = Depends(get_db),
):
    """
    HITL: Promueve un StructuredSymbol validado con evidencia geométrica física
    a una plantilla canónica versionada (SymbolTemplate + SymbolTemplateVersion)
    con rasgos geométricos y evidencia de origen tipificada.
    """
    service = CanonicalPipingCatalogService(db)
    return service.promote_candidate_to_canonical(payload)


@router.post("/match-occurrence", response_model=MatchOccurrenceResponse)
def match_occurrence(
    payload: MatchOccurrenceRequest,
    db: Session = Depends(get_db),
):
    """
    Ejecuta el motor progresivo multi-etapa de matching para una ocurrencia o recorte candidato.
    Valida estrictamente las precondiciones geométricas (geometric_evidence == True, confianza >= umbral,
    bbox válidos, archivo de crop existente).
    Aplica pesos: Geometría + Topología + Similitud Visual >= 0.85, Contexto <= 0.10.
    """
    service = CanonicalPipingCatalogService(db)
    return service.match_occurrence(payload)


@router.get("/occurrences")
def list_symbol_occurrences(
    project_id: Optional[str] = Query(None, description="Filtra por ID de proyecto"),
    document_id: Optional[str] = Query(None, description="Filtra por documento de proyecto"),
    matching_status: Optional[str] = Query(None, description="matched, ambiguous, unknown_symbol, rejected, unconfirmed"),
    canonical_family: Optional[str] = Query(None, description="Filtra por familia canónica detectada"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Lista las ocurrencias de símbolos detectadas en documentos de proyectos,
    incluyendo su estado de matching y scores multi-etapa.
    """
    query = db.query(DetectedSymbol)
    if project_id:
        query = query.filter(DetectedSymbol.project_id == project_id)
    if document_id:
        query = query.filter(DetectedSymbol.project_document_id == document_id)
    if matching_status:
        query = query.filter(DetectedSymbol.matching_status == matching_status)
    if canonical_family:
        query = query.filter(DetectedSymbol.detected_tag_or_code == canonical_family)

    total = query.count()
    items = query.order_by(DetectedSymbol.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "items": [
            {
                "id": str(item.id),
                "project_id": item.project_id,
                "project_document_id": item.project_document_id,
                "classification": item.classification,
                "geometric_evidence": item.geometric_evidence,
                "geometric_confidence": item.geometric_confidence,
                "matching_status": item.matching_status,
                "matched_template_id": item.matched_template_id,
                "matched_template_version_id": item.matched_template_version_id,
                "match_score": item.match_score,
                "geometry_score": item.geometry_score,
                "topology_score": item.topology_score,
                "visual_score": item.visual_score,
                "context_score": item.context_score,
                "detected_tag_or_code": item.detected_tag_or_code,
                "crop_image_path": item.crop_image_path,
                "crop_image_hash": item.crop_image_hash,
                "review_status": item.review_status,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in items
        ],
    }


@router.post("/decisions", response_model=SymbolReviewDecisionResponse)
def record_review_decision(
    payload: SymbolReviewDecisionRequest,
    db: Session = Depends(get_db),
):
    """
    Registra una decisión de revisión humana (accept, reject, edit_bbox, edit_family, merge, split)
    sobre una ocurrencia o candidato, preservando el linaje histórico sin sobreescrituras destructivas.
    """
    service = CanonicalPipingCatalogService(db)
    return service.record_review_decision(payload)


@router.get("/research-cases")
def list_research_cases(
    status: Optional[str] = Query(None, description="unknown, queued_for_research, sources_found, resolved, dismissed"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Lista casos de investigación para símbolos desconocidos (geometría real sin coincidencia en catálogo canónico).
    """
    query = db.query(SymbolUnknownResearchCase)
    if status:
        query = query.filter(SymbolUnknownResearchCase.status == status)

    cases = query.order_by(SymbolUnknownResearchCase.created_at.desc()).limit(limit).all()
    return [
        {
            "id": c.id,
            "symbol_occurrence_id": c.symbol_occurrence_id,
            "status": c.status,
            "search_query": c.search_query,
            "source_urls": c.source_urls or [],
            "proposed_name": c.proposed_name,
            "proposed_standard_reference": c.proposed_standard_reference,
            "research_notes": c.research_notes,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in cases
    ]
