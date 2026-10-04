import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.db.models.core import Project
from app.db.models.document_memory import Document
from app.db.models.completeness import (
    ProjectDeliverableRequirement, DocumentDeliverable, ProjectCompletenessEvaluation
)
from app.db.models.decision_memory import RuleDefinition
from app.schemas.common import (
    ProjectStageEnum, DeliverableTypeEnum, EvidenceReadinessStatusEnum,
    AuditVerdictEnum, UnverifiableReasonEnum
)
from app.core.logging import logger

DEFAULT_REQUIREMENTS_SEED = [
    # --- INGENIERÍA BÁSICA ---
    {
        "stage": "Ingeniería Básica",
        "discipline": "architecture",
        "deliverable_type": "plano_general",
        "title": "Plantas Generales y Emplazamiento",
        "description": "Planos arquitectónicos de plantas generales con viñetas y cotas principales.",
        "is_mandatory": True,
        "blocked_rule_codes": ["RULE_TITLE_BLOCK_FIELDS_V1", "RULE_TITLE_BLOCK_SCALE_V1"]
    },
    {
        "stage": "Ingeniería Básica",
        "discipline": "structural",
        "deliverable_type": "memoria_calculo",
        "title": "Memoria de Criterios de Diseño Estructural",
        "description": "Documento con hipótesis de cálculo, normativas y parámetros sísmicos.",
        "is_mandatory": True,
        "blocked_rule_codes": ["RULE_NORMATIVE_MIN_DOOR_WIDTH_V1"]
    },
    {
        "stage": "Ingeniería Básica",
        "discipline": "general",
        "deliverable_type": "especificaciones_tecnicas",
        "title": "Especificaciones Técnicas Generales (EETT)",
        "description": "Alcance técnico y normativo básico del proyecto.",
        "is_mandatory": True,
        "blocked_rule_codes": ["RULE_REQUIRED_TABLES_V1"]
    },
    {
        "stage": "Ingeniería Básica",
        "discipline": "structural",
        "deliverable_type": "mecanica_suelos",
        "title": "Informe Preliminar de Mecánica de Suelos",
        "description": "Reconocimiento geotécnico y estratigrafía preliminar.",
        "is_mandatory": False,
        "blocked_rule_codes": []
    },

    # --- INGENIERÍA DE DETALLE ---
    {
        "stage": "Ingeniería de Detalle",
        "discipline": "architecture",
        "deliverable_type": "plano_general",
        "title": "Planos de Plantas, Cortes y Elevaciones Definitivos",
        "description": "Juego completo de láminas arquitectónicas acotadas con simbología y viñetas.",
        "is_mandatory": True,
        "blocked_rule_codes": [
            "RULE_DOOR_COUNT_MATCH_V1",
            "RULE_WINDOW_COUNT_MATCH_V1",
            "RULE_TITLE_BLOCK_FIELDS_V1",
            "RULE_TITLE_BLOCK_SCALE_V1"
        ]
    },
    {
        "stage": "Ingeniería de Detalle",
        "discipline": "architecture",
        "deliverable_type": "plano_detalles",
        "title": "Detalles Constructivos y Cuadros de Vanos",
        "description": "Tablas y cuadros de puertas, ventanas y detalles de terminaciones.",
        "is_mandatory": True,
        "blocked_rule_codes": [
            "RULE_DOOR_COUNT_MATCH_V1",
            "RULE_WINDOW_COUNT_MATCH_V1",
            "RULE_NORMATIVE_MIN_DOOR_WIDTH_V1"
        ]
    },
    {
        "stage": "Ingeniería de Detalle",
        "discipline": "structural",
        "deliverable_type": "plano_estructural",
        "title": "Planos de Enfierraduras, Fundaciones y Estructuras",
        "description": "Láminas estructurales con tablas de pilares, vigas y losas.",
        "is_mandatory": True,
        "blocked_rule_codes": ["RULE_REQUIRED_TABLES_V1"]
    },
    {
        "stage": "Ingeniería de Detalle",
        "discipline": "structural",
        "deliverable_type": "memoria_calculo",
        "title": "Memoria de Cálculo Estructural Definitiva",
        "description": "Modelación computacional y verificación de elementos sismorresistentes.",
        "is_mandatory": True,
        "blocked_rule_codes": []
    },
    {
        "stage": "Ingeniería de Detalle",
        "discipline": "general",
        "deliverable_type": "especificaciones_tecnicas",
        "title": "Especificaciones Técnicas Especiales (EETT)",
        "description": "EETT definitivas con requisitos de materiales, dosificación y tolerancias.",
        "is_mandatory": True,
        "blocked_rule_codes": ["RULE_REQUIRED_TABLES_V1", "RULE_NORMATIVE_MIN_DOOR_WIDTH_V1"]
    },
    {
        "stage": "Ingeniería de Detalle",
        "discipline": "structural",
        "deliverable_type": "mecanica_suelos",
        "title": "Estudio de Mecánica de Suelos Definitivo",
        "description": "Ensayos de laboratorio, capacidad admisible y recomendaciones de fundación.",
        "is_mandatory": True,
        "blocked_rule_codes": []
    },
    {
        "stage": "Ingeniería de Detalle",
        "discipline": "electrical",
        "deliverable_type": "cuadro_cargas",
        "title": "Cuadros de Cargas y Diagramas Eléctricos",
        "description": "Tableros de distribución, alimentadores y cálculos de potencia.",
        "is_mandatory": False,
        "blocked_rule_codes": []
    },
    {
        "stage": "Ingeniería de Detalle",
        "discipline": "general",
        "deliverable_type": "plan_seguridad",
        "title": "Plan de Evacuación y Protección Contra Incendios",
        "description": "Cálculo de vías de escape, resistencia al fuego y extintores.",
        "is_mandatory": False,
        "blocked_rule_codes": []
    }
]

class CompletenessService:
    """Motor de Evaluación de Completitud Documental y Gatekeeper de Auditoría."""

    def __init__(self, db: Session):
        self.db = db

    def seed_default_requirements(self) -> None:
        """Siembra la matriz de requisitos documentales por defecto si no existen."""
        count = self.db.query(ProjectDeliverableRequirement).count()
        if count == 0:
            for item in DEFAULT_REQUIREMENTS_SEED:
                req = ProjectDeliverableRequirement(
                    stage=item["stage"],
                    discipline=item["discipline"],
                    deliverable_type=item["deliverable_type"],
                    title=item["title"],
                    description=item["description"],
                    is_mandatory=item["is_mandatory"],
                    blocked_rule_codes=item["blocked_rule_codes"]
                )
                self.db.add(req)
            self.db.commit()
            logger.info("Matriz estándar de completitud documental sembrada exitosamente.")

    def get_requirements(self, stage: Optional[str] = None, discipline: Optional[str] = None) -> List[ProjectDeliverableRequirement]:
        self.seed_default_requirements()
        q = self.db.query(ProjectDeliverableRequirement)
        if stage:
            q = q.filter(ProjectDeliverableRequirement.stage == stage)
        if discipline and discipline != "all":
            q = q.filter(ProjectDeliverableRequirement.discipline.in_([discipline, "general"]))
        return q.all()

    def classify_document_deliverable(
        self,
        document_id: str,
        deliverable_type: str,
        readiness_status: str = "classified",
        validation_notes: Optional[str] = None,
        classified_by: str = "auditor_qa"
    ) -> DocumentDeliverable:
        """Clasifica un documento y gestiona su ciclo de vida como evidencia."""
        doc = self.db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError(f"Documento '{document_id}' no encontrado.")

        deliv = self.db.query(DocumentDeliverable).filter(DocumentDeliverable.document_id == document_id).first()
        now = datetime.utcnow()
        if not deliv:
            deliv = DocumentDeliverable(
                project_id=doc.project_id,
                document_id=document_id,
                deliverable_type=deliverable_type,
                readiness_status=readiness_status,
                validation_notes=validation_notes,
                classified_by=classified_by,
                validated_at=now if readiness_status == "eligible_as_evidence" else None
            )
            self.db.add(deliv)
        else:
            deliv.deliverable_type = deliverable_type
            deliv.readiness_status = readiness_status
            deliv.validation_notes = validation_notes
            deliv.classified_by = classified_by
            if readiness_status == "eligible_as_evidence":
                deliv.validated_at = now
            deliv.updated_at = now

        self.db.commit()
        self.db.refresh(deliv)
        return deliv

    def evaluate_project_completeness(self, project_id: str, stage_override: Optional[str] = None) -> Dict[str, Any]:
        """
        Ejecuta el chequeo de completitud documental contra la matriz de la etapa.
        Detecta faltantes críticos y genera el mapa de reglas bloqueadas preventivamente.
        """
        self.seed_default_requirements()
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Proyecto '{project_id}' no encontrado.")

        settings = project.settings or {}
        target_stage = stage_override or settings.get("stage", "Ingeniería de Detalle")
        target_disc = project.discipline or "architecture"

        # Obtener requisitos aplicables a la etapa
        requirements = self.db.query(ProjectDeliverableRequirement).filter(
            ProjectDeliverableRequirement.stage == target_stage
        ).all()

        # Si no hay requisitos exactos para la etapa, usar Ingeniería de Detalle como fallback
        if not requirements:
            requirements = self.db.query(ProjectDeliverableRequirement).filter(
                ProjectDeliverableRequirement.stage == "Ingeniería de Detalle"
            ).all()

        # Obtener documentos activos del proyecto y sus clasificaciones
        docs = self.db.query(Document).filter(
            Document.project_id == project_id,
            Document.status.notin_(["deleted", "archived"])
        ).all()

        deliverables_by_doc_id: Dict[str, DocumentDeliverable] = {}
        for d in docs:
            deliv = self.db.query(DocumentDeliverable).filter(DocumentDeliverable.document_id == d.id).first()
            if deliv:
                deliverables_by_doc_id[d.id] = deliv

        # Evaluación de la matriz
        matrix: List[Dict[str, Any]] = []
        missing_deliverables: List[Dict[str, Any]] = []
        blocked_rule_codes_set = set()
        blocked_rules_detail: List[Dict[str, Any]] = []

        total_mandatory = 0
        fulfilled_mandatory = 0
        total_optional = 0
        fulfilled_optional = 0

        for req in requirements:
            # Buscar documentos provistos para este tipo de entregable
            matching_docs = []
            has_eligible = False

            for d in docs:
                deliv = deliverables_by_doc_id.get(d.id)
                # Si el documento no tiene clasificación explícita, se asume 'plano_general' si su document_type es plan
                deliv_type = deliv.deliverable_type if deliv else "plano_general"
                deliv_status = deliv.readiness_status if deliv else "uploaded"

                if deliv_type == req.deliverable_type:
                    is_eligible = deliv_status == "eligible_as_evidence"
                    if is_eligible:
                        has_eligible = True
                    matching_docs.append({
                        "document_id": d.id,
                        "document_filename": d.filename,
                        "document_title": d.filename,
                        "deliverable_type": deliv_type,
                        "readiness_status": deliv_status,
                        "is_eligible": is_eligible
                    })

            is_fulfilled = has_eligible
            if req.is_mandatory:
                total_mandatory += 1
                if is_fulfilled:
                    fulfilled_mandatory += 1
                else:
                    # Falta entregable obligatorio -> Bloquear reglas dependientes
                    missing_deliverables.append({
                        "requirement_id": req.id,
                        "title": req.title,
                        "deliverable_type": req.deliverable_type,
                        "is_mandatory": True,
                        "blocked_rule_codes": req.blocked_rule_codes or []
                    })
                    for r_code in (req.blocked_rule_codes or []):
                        blocked_rule_codes_set.add(r_code)
                        # Obtener nombre de la regla
                        rule_def = self.db.query(RuleDefinition).filter(RuleDefinition.code == r_code).first()
                        rule_name = rule_def.name if rule_def else r_code
                        blocked_rules_detail.append({
                            "rule_code": r_code,
                            "rule_name": rule_name,
                            "discipline": req.discipline,
                            "blocked_by_deliverable_title": req.title,
                            "blocked_by_deliverable_type": req.deliverable_type,
                            "reason": "blocked_by_missing_doc",
                            "detail": f"Regla bloqueada preventivamente: Requiere entregable «{req.title}» en estado 'Apto como Evidencia'."
                        })
            else:
                total_optional += 1
                if is_fulfilled:
                    fulfilled_optional += 1
                else:
                    missing_deliverables.append({
                        "requirement_id": req.id,
                        "title": req.title,
                        "deliverable_type": req.deliverable_type,
                        "is_mandatory": False,
                        "blocked_rule_codes": []
                    })

            matrix.append({
                "requirement": {
                    "id": req.id,
                    "stage": req.stage,
                    "discipline": req.discipline,
                    "deliverable_type": req.deliverable_type,
                    "title": req.title,
                    "description": req.description,
                    "is_mandatory": req.is_mandatory,
                    "blocked_rule_codes": req.blocked_rule_codes or []
                },
                "provided_documents": matching_docs,
                "is_fulfilled": is_fulfilled,
                "status": "eligible" if is_fulfilled else ("pending_validation" if len(matching_docs) > 0 else ("missing_mandatory" if req.is_mandatory else "missing_optional"))
            })

        total_reqs = total_mandatory + total_optional
        total_fulfilled = fulfilled_mandatory + fulfilled_optional
        percentage = round((total_fulfilled / total_reqs * 100.0), 1) if total_reqs > 0 else 100.0
        is_gate_passed = (total_mandatory == fulfilled_mandatory) and total_mandatory > 0

        # Persistir la evaluación en base de datos
        evaluation = ProjectCompletenessEvaluation(
            project_id=project_id,
            stage=target_stage,
            completeness_percentage=percentage,
            is_gate_passed=is_gate_passed,
            total_required_count=total_reqs,
            eligible_count=total_fulfilled,
            missing_mandatory_count=total_mandatory - fulfilled_mandatory,
            missing_optional_count=total_optional - fulfilled_optional,
            blocked_rules_count=len(blocked_rule_codes_set),
            deliverables_matrix=matrix,
            missing_deliverables=missing_deliverables,
            blocked_rules=blocked_rules_detail,
            evaluated_at=datetime.utcnow()
        )
        self.db.add(evaluation)
        self.db.commit()
        self.db.refresh(evaluation)

        return {
            "id": evaluation.id,
            "project_id": project_id,
            "stage": target_stage,
            "completeness_percentage": percentage,
            "is_gate_passed": is_gate_passed,
            "total_required_count": total_reqs,
            "eligible_count": total_fulfilled,
            "missing_mandatory_count": total_mandatory - fulfilled_mandatory,
            "missing_optional_count": total_optional - fulfilled_optional,
            "blocked_rules_count": len(blocked_rule_codes_set),
            "deliverables_matrix": matrix,
            "missing_deliverables": missing_deliverables,
            "blocked_rules": blocked_rules_detail,
            "blocked_rule_codes": list(blocked_rule_codes_set),
            "evaluated_at": evaluation.evaluated_at.isoformat()
        }
