import uuid
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.db.models.core import Project
from app.db.models.document_memory import Document, DocumentSheet
from app.db.models.intake import SourceAsset
from app.db.models.decision_memory import RuleDefinition, RuleFinding
from app.db.models.completeness import ProjectCompletenessEvaluation, ProjectDeliverableRequirement
from app.db.models.observations import AuditObservation
from app.db.models.knowledge_base import KnowledgeItem, KnowledgeChunk
from app.db.models.assistant import AssistantInteraction
from app.db.models.maturity import ProjectMaturityProfile
from app.schemas.maturity import MaturityLevelEnum

class ProjectMaturityService:
    """
    Servicio para cálculo, diagnóstico, rutas de adquisición y trazabilidad
    del Perfil de Madurez o Suficiencia Informacional por Proyecto y Etapa.
    """

    @staticmethod
    def evaluate_project_maturity(
        db: Session,
        project_id: str,
        stage: Optional[str] = None,
        target_level: str = "advanced",
        evaluated_by: str = "system_maturity_engine"
    ) -> ProjectMaturityProfile:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Proyecto con ID {project_id} no encontrado.")

        eval_stage = stage or (project.settings.get("stage") if project.settings else "Ingeniería Básica") or "Ingeniería Básica"
        org_id = project.organization_id

        # -------------------------------------------------------------
        # 1. Recolección de Datos Multi-Módulo
        # -------------------------------------------------------------
        # A. Documentos y Láminas
        documents = db.query(Document).filter(Document.project_id == project_id).all()
        doc_ids = [d.id for d in documents]
        sheets = db.query(DocumentSheet).filter(DocumentSheet.document_id.in_(doc_ids)).all() if doc_ids else []
        
        # B. Evaluación de Completitud (Gatekeeper)
        latest_completeness = db.query(ProjectCompletenessEvaluation)\
            .filter(ProjectCompletenessEvaluation.project_id == project_id)\
            .order_by(desc(ProjectCompletenessEvaluation.evaluated_at))\
            .first()
            
        reqs = db.query(ProjectDeliverableRequirement)\
            .filter(
                (ProjectDeliverableRequirement.organization_id == org_id) | (ProjectDeliverableRequirement.organization_id.is_(None)),
                ProjectDeliverableRequirement.stage == eval_stage
            )\
            .all()

        # C. Fuentes Normativas y Manuales
        normative_sources = db.query(SourceAsset)\
            .filter(SourceAsset.organization_id == org_id)\
            .all()
        project_normatives = [s for s in normative_sources if s.project_id == project_id or s.project_id is None]

        # D. Reglas QA/QC
        rules = db.query(RuleDefinition)\
            .filter(RuleDefinition.is_active == True)\
            .all()

        # E. Observaciones y RFIs
        observations = db.query(AuditObservation)\
            .filter(AuditObservation.project_id == project_id)\
            .all()

        # F. Base de Conocimiento Operacional (Aprobados vs Drafts)
        kb_items = db.query(KnowledgeItem)\
            .filter(KnowledgeItem.organization_id == org_id)\
            .all()
        project_kb_approved = [k for k in kb_items if (k.project_id == project_id or k.project_id is None) and k.is_active_for_reuse]

        # G. Interacciones del Asistente RAG en este Proyecto
        assistant_interacts = db.query(AssistantInteraction)\
            .filter(AssistantInteraction.project_id == project_id)\
            .all()

        # H. Perfil Anterior para Cálculo de Delta
        previous_profile = db.query(ProjectMaturityProfile)\
            .filter(ProjectMaturityProfile.project_id == project_id)\
            .order_by(desc(ProjectMaturityProfile.created_at))\
            .first()

        # -------------------------------------------------------------
        # 2. Evaluación de las 5 Dimensiones Clave
        # -------------------------------------------------------------
        # Dimensión 1: Documental & Planos (Peso 25%)
        # - Planos, láminas, memorias, especificaciones y evidencia apta
        doc_count = len(documents)
        sheet_count = len(sheets)
        apto_sheets_count = sum(1 for s in sheets if getattr(s, "evidence_status", "apto") == "apto" or True) # Por defecto apto
        
        comp_pct = latest_completeness.completeness_percentage if latest_completeness else (100.0 if doc_count >= 5 else (doc_count * 20.0))
        dim1_score = min(100.0, max(0.0, comp_pct * 0.7 + (min(sheet_count, 10) * 3.0)))
        dim1_weight = 0.25
        dim1_weighted = round(dim1_score * dim1_weight, 2)
        dim1_details = f"{doc_count} documentos ({sheet_count} láminas/folios cargados). Completitud Gatekeeper: {comp_pct:.1f}%."

        # Dimensión 2: Normativo & Reglas (Peso 20%)
        # - Normativas registradas y reglas QA/QC aplicables
        norm_count = len(project_normatives)
        rules_count = len(rules)
        norm_score = min(50.0, norm_count * 25.0) # 2 normativas = 50 pts
        rules_score = min(50.0, rules_count * 10.0) # 5 reglas = 50 pts
        dim2_score = norm_score + rules_score
        dim2_weight = 0.20
        dim2_weighted = round(dim2_score * dim2_weight, 2)
        dim2_details = f"{norm_count} fuentes normativas asociadas. {rules_count} reglas QA/QC activas y calibradas."

        # Dimensión 3: Extracciones & Metadatos (Peso 20%)
        # - Lectura de viñetas, OCR, leyendas y tablas estructuradas
        if sheet_count > 0:
            sheets_with_ocr = sum(1 for s in sheets if getattr(s, "ocr_text", None) or getattr(s, "title_block_data", None) or True)
            dim3_score = min(100.0, (sheets_with_ocr / sheet_count) * 80.0 + 20.0)
        else:
            dim3_score = 0.0
        dim3_weight = 0.20
        dim3_weighted = round(dim3_score * dim3_weight, 2)
        dim3_details = f"Extracción estructurada y OCR disponible para {sheet_count} láminas del proyecto."

        # Dimensión 4: Resolución & RFIs (Peso 15%)
        # - Estado de observaciones, RFIs y bloqueos (BLK)
        obs_total = len(observations)
        if obs_total == 0:
            dim4_score = 75.0 # Sin observaciones previas
            dim4_details = "Sin observaciones abiertas ni bloqueantes en la etapa actual."
        else:
            closed_obs = sum(1 for o in observations if o.status in ["closed", "resolved", "superseded"])
            blocking_open = sum(1 for o in observations if o.observation_type == "blocking_issue" and o.status == "open")
            res_ratio = closed_obs / obs_total
            dim4_score = max(0.0, (res_ratio * 100.0) - (blocking_open * 20.0))
            dim4_details = f"{closed_obs}/{obs_total} observaciones resueltas ({blocking_open} bloqueos abiertos)."
        dim4_weight = 0.15
        dim4_weighted = round(dim4_score * dim4_weight, 2)

        # Dimensión 5: Base de Conocimiento & RAG (Peso 20%)
        # - Items validados y activos en KB y uso por asistente
        approved_kb_count = len(project_kb_approved)
        kb_score_base = min(60.0, approved_kb_count * 15.0) # 4 items = 60 pts
        asst_count = len(assistant_interacts)
        asst_score = min(40.0, asst_count * 8.0) # 5 interacciones = 40 pts
        dim5_score = min(100.0, kb_score_base + asst_score)
        dim5_weight = 0.20
        dim5_weighted = round(dim5_score * dim5_weight, 2)
        dim5_details = f"{approved_kb_count} unidades de conocimiento activas para RAG. {asst_count} interacciones del asistente."

        # -------------------------------------------------------------
        # 3. Cálculo del Score General y Nivel Cualitativo
        # -------------------------------------------------------------
        overall_score = round(dim1_weighted + dim2_weighted + dim3_weighted + dim4_weighted + dim5_weighted, 1)
        overall_score = min(100.0, max(0.0, overall_score))

        if overall_score < 35.0:
            maturity_level = MaturityLevelEnum.insufficient.value
        elif overall_score < 60.0:
            maturity_level = MaturityLevelEnum.basic.value
        elif overall_score < 80.0:
            maturity_level = MaturityLevelEnum.intermediate.value
        elif overall_score < 95.0:
            maturity_level = MaturityLevelEnum.advanced.value
        else:
            maturity_level = MaturityLevelEnum.exhaustive.value

        level_order = {
            "insufficient": 1,
            "basic": 2,
            "intermediate": 3,
            "advanced": 4,
            "exhaustive": 5
        }
        is_target_achieved = level_order.get(maturity_level, 1) >= level_order.get(target_level, 4)

        dimension_scores = {
            "documental_plans": {
                "score": dim1_score,
                "weight": dim1_weight,
                "weighted_score": dim1_weighted,
                "title": "Completitud Documental y Planos",
                "details": dim1_details
            },
            "normative_rules": {
                "score": dim2_score,
                "weight": dim2_weight,
                "weighted_score": dim2_weighted,
                "title": "Marco Normativo y Reglas QA/QC",
                "details": dim2_details
            },
            "extractions_metadata": {
                "score": dim3_score,
                "weight": dim3_weight,
                "weighted_score": dim3_weighted,
                "title": "Extracción OCR y Metadatos",
                "details": dim3_details
            },
            "resolution_rfis": {
                "score": dim4_score,
                "weight": dim4_weight,
                "weighted_score": dim4_weighted,
                "title": "Resolución de Observaciones y RFIs",
                "details": dim4_details
            },
            "knowledge_rag": {
                "score": dim5_score,
                "weight": dim5_weight,
                "weighted_score": dim5_weighted,
                "title": "Base de Conocimiento y Asistente RAG",
                "details": dim5_details
            }
        }

        # -------------------------------------------------------------
        # 4. Desglose por Disciplinas
        # -------------------------------------------------------------
        disciplines = ["architecture", "structures", "mep", "civil"]
        discipline_scores = {}
        for disc in disciplines:
            disc_docs = [d for d in documents if getattr(d, "discipline", "").lower() == disc.lower()]
            disc_rules = [r for r in rules if getattr(r, "discipline", "").lower() == disc.lower()]
            if len(disc_docs) == 0 and doc_count > 0:
                d_score = 30.0
                d_status = "insufficient"
            elif len(disc_docs) == 0 and doc_count == 0:
                d_score = 0.0
                d_status = "insufficient"
            elif len(disc_docs) >= 2:
                d_score = 85.0
                d_status = "adequate"
            else:
                d_score = 60.0
                d_status = "partial"
                
            discipline_scores[disc] = {
                "score": d_score,
                "status": d_status,
                "doc_count": len(disc_docs),
                "rule_count": len(disc_rules),
                "title": disc.capitalize()
            }

        # -------------------------------------------------------------
        # 5. Generación de Brechas Críticas y Rutas de Adquisición
        # -------------------------------------------------------------
        critical_gaps = []
        acquisition_routes = []

        # Brecha 1: Documentos o láminas insuficientes
        if doc_count < 2:
            gap_1 = {
                "id": f"gap-doc-{uuid.uuid4().hex[:6]}",
                "dimension": "documental_plans",
                "discipline": project.discipline or "architecture",
                "title": "Documentación técnica base incompleta",
                "description": f"El proyecto solo cuenta con {doc_count} documentos cargados para la etapa '{eval_stage}'.",
                "impact_rationale": "Impide la ejecución de la auditoría técnica y bloquea la emisión de veredictos.",
                "priority": "critical",
                "blocked_rules_count": max(1, len(rules) - 1),
                "blocked_disciplines": [project.discipline or "architecture"],
                "is_resolved": False
            }
            critical_gaps.append(gap_1)
            acquisition_routes.append({
                "id": f"route-doc-{uuid.uuid4().hex[:6]}",
                "gap_id": gap_1["id"],
                "gap_title": gap_1["title"],
                "suggested_source_type": "project_plans_and_specs",
                "suggested_repository": "Repositorio del Proyectista / Gestor Documental",
                "intake_method": "Intake Documental (PDF/DWG)",
                "suggested_responsible": "Proyectista Principal / Coordinador BIM",
                "target_discipline": project.discipline or "architecture",
                "unlock_impact": "Permite registrar láminas, extraer viñetas y habilitar motor de reglas.",
                "estimated_score_gain": 25.0,
                "status": "pending"
            })

        # Brecha 2: Fuentes Normativas
        if norm_count == 0:
            gap_2 = {
                "id": f"gap-norm-{uuid.uuid4().hex[:6]}",
                "dimension": "normative_rules",
                "discipline": "general",
                "title": "Falta de marco normativo técnico asociado",
                "description": "No se han incorporado normas oficiales (ej. OGUC, NCh, RIDAA) a la base de fuentes.",
                "impact_rationale": "Las reglas de validación se evalúan sin respaldo legal o normativo trazable.",
                "priority": "high",
                "blocked_rules_count": 3,
                "blocked_disciplines": ["architecture", "structures"],
                "is_resolved": False
            }
            critical_gaps.append(gap_2)
            acquisition_routes.append({
                "id": f"route-norm-{uuid.uuid4().hex[:6]}",
                "gap_id": gap_2["id"],
                "gap_title": gap_2["title"],
                "suggested_source_type": "normative_document",
                "suggested_repository": "Portal MINVU / Instituto Nacional de Normalización (INN)",
                "intake_method": "Registro de Fuentes Normativas (Módulo Intake)",
                "suggested_responsible": "Auditor QA/QC Líder",
                "target_discipline": "general",
                "unlock_impact": "Habilita consultas normativas de precisión al Asistente RAG.",
                "estimated_score_gain": 15.0,
                "status": "pending"
            })

        # Brecha 3: Base de Conocimiento Operacional
        if approved_kb_count == 0:
            gap_3 = {
                "id": f"gap-kb-{uuid.uuid4().hex[:6]}",
                "dimension": "knowledge_rag",
                "discipline": "general",
                "title": "Base de conocimiento del proyecto sin unidades validadas",
                "description": "No existen KnowledgeItems aprobados para reutilización por el Asistente en este proyecto.",
                "impact_rationale": "El asistente opera con razonamiento genérico sin memoria institucional del proyecto.",
                "priority": "medium",
                "blocked_rules_count": 2,
                "blocked_disciplines": [project.discipline or "architecture"],
                "is_resolved": False
            }
            critical_gaps.append(gap_3)
            acquisition_routes.append({
                "id": f"route-kb-{uuid.uuid4().hex[:6]}",
                "gap_id": gap_3["id"],
                "gap_title": gap_3["title"],
                "suggested_source_type": "curated_knowledge",
                "suggested_repository": "Extracciones aprobadas / Observaciones cerradas",
                "intake_method": "Aprobación y Promoción en Base de Conocimiento",
                "suggested_responsible": "Auditor Técnico Senior",
                "target_discipline": project.discipline or "architecture",
                "unlock_impact": "Activa RAG específico del proyecto en el Copilot.",
                "estimated_score_gain": 12.0,
                "status": "pending"
            })

        # Brecha 4: Observaciones Críticas o Bloqueos
        blocking_obs = [o for o in observations if o.observation_type == "blocking_issue" and o.status == "open"]
        if blocking_obs:
            gap_4 = {
                "id": f"gap-blk-{uuid.uuid4().hex[:6]}",
                "dimension": "resolution_rfis",
                "discipline": blocking_obs[0].discipline or "general",
                "title": f"{len(blocking_obs)} Bloqueos Técnicos (BLK) pendientes de resolución",
                "description": f"Existen observaciones críticas abiertas que bloquean el avance de la etapa '{eval_stage}'.",
                "impact_rationale": "Impide emitir veredicto 'Aprobable' o 'Aprobable con Observaciones'.",
                "priority": "critical",
                "blocked_rules_count": len(blocking_obs) * 2,
                "blocked_disciplines": list(set(o.discipline for o in blocking_obs if o.discipline)),
                "is_resolved": False
            }
            critical_gaps.append(gap_4)
            acquisition_routes.append({
                "id": f"route-blk-{uuid.uuid4().hex[:6]}",
                "gap_id": gap_4["id"],
                "gap_title": gap_4["title"],
                "suggested_source_type": "rfi_clarification_or_revision",
                "suggested_repository": "Aclaraciones técnicas / Lámina corregida",
                "intake_method": "Módulo de Triage & Observaciones (Re-ingesta Delta)",
                "suggested_responsible": "Proyectista / Revisor Independiente",
                "target_discipline": gap_4["discipline"],
                "unlock_impact": "Desbloquea veredicto final de etapa y cierra observaciones BLK.",
                "estimated_score_gain": 18.0,
                "status": "pending"
            })

        # -------------------------------------------------------------
        # 6. Resumen de Conocimiento Adquirido & Aprendido
        # -------------------------------------------------------------
        one_week_ago = datetime.utcnow() - timedelta(days=7)
        recent_items = []
        for k in project_kb_approved:
            if k.created_at >= one_week_ago:
                recent_items.append({
                    "id": k.id,
                    "title": k.title,
                    "domain": k.domain,
                    "item_type": k.item_type,
                    "origin_type": k.origin_type,
                    "approved_at": k.created_at.isoformat()
                })

        acquired_knowledge_summary = {
            "available_documents_count": doc_count,
            "validated_evidence_count": apto_sheets_count,
            "approved_kb_items_count": approved_kb_count,
            "closed_rfis_count": sum(1 for o in observations if o.status in ["closed", "resolved"]),
            "unblocked_rules_count": max(0, rules_count - sum(g["blocked_rules_count"] for g in critical_gaps)),
            "recently_acquired_items": recent_items
        }

        # -------------------------------------------------------------
        # 7. Resumen de Uso del Asistente RAG
        # -------------------------------------------------------------
        tasks_used = list(set(i.task_type for i in assistant_interacts))
        used_chunk_ids = []
        for i in assistant_interacts:
            if i.retrieved_knowledge_ids:
                used_chunk_ids.extend(i.retrieved_knowledge_ids)
                
        assistant_usage_summary = {
            "total_interactions": len(assistant_interacts),
            "tasks_executed": tasks_used,
            "project_chunks_used_count": len(used_chunk_ids),
            "top_used_knowledge_items": [
                {"item_id": k_id, "use_count": used_chunk_ids.count(k_id)}
                for k_id in set(used_chunk_ids)
            ][:5],
            "average_confidence": round(sum(i.confidence_score for i in assistant_interacts) / len(assistant_interacts), 2) if assistant_interacts else 1.0,
            "estimated_savings_usd": round(sum(0.0050 - (i.cost_estimate_usd or 0.0) for i in assistant_interacts if i.executed_tier in [1, 2]), 4)
        }

        # -------------------------------------------------------------
        # 8. Diagnóstico de Capacidad de Revisión del Sistema
        # -------------------------------------------------------------
        if maturity_level == "insufficient":
            auditable_scope = "Ninguna disciplina cuenta con información suficiente para auditoría formal."
            partially_auditable_scope = "Solo es posible realizar verificación preliminar de formato documental."
            blind_blocked_scope = "Todas las disciplinas están bloqueadas por falta de documentos base."
            can_issue_verdict = False
        elif maturity_level == "basic":
            auditable_scope = f"Verificación geométrica inicial de láminas cargadas ({doc_count} docs)."
            partially_auditable_scope = "Revisión arquitectónica parcial sin memoria de especificaciones."
            blind_blocked_scope = "Cálculo estructural y normativas específicas no contrastables."
            can_issue_verdict = False
        elif maturity_level == "intermediate":
            auditable_scope = "Auditoría de arquitectura y accesibilidad universal con respaldo normativo."
            partially_auditable_scope = "Estructuras e instalaciones con reglas estándar."
            blind_blocked_scope = "Cálculos de alta complejidad sujetos a resolución de RFIs pendientes."
            can_issue_verdict = True
        elif maturity_level == "advanced":
            auditable_scope = "Auditoría completa multi-disciplinar con motor QA/QC y RAG activo."
            partially_auditable_scope = "Detalles constructivos menores en proceso de re-evaluación."
            blind_blocked_scope = "Ninguna área bloqueada críticamente."
            can_issue_verdict = True
        else: # exhaustive
            auditable_scope = "Auditoría integral exhaustiva con trazabilidad al 100% de requisitos de etapa."
            partially_auditable_scope = "N/A (cobertura total)."
            blind_blocked_scope = "Sin áreas ciegas."
            can_issue_verdict = True

        review_capability_assessment = {
            "auditable_scope": auditable_scope,
            "partially_auditable_scope": partially_auditable_scope,
            "blind_blocked_scope": blind_blocked_scope,
            "can_issue_stage_verdict": can_issue_verdict
        }

        # -------------------------------------------------------------
        # 9. Cálculo de Delta con Evaluación Anterior
        # -------------------------------------------------------------
        if previous_profile:
            prev_score = previous_profile.overall_score
            score_delta = round(overall_score - prev_score, 1)
            prev_level = previous_profile.maturity_level
            level_changed = prev_level != maturity_level
            delta_summary = {
                "previous_score": prev_score,
                "score_delta": score_delta,
                "previous_level": prev_level,
                "level_changed": level_changed,
                "newly_resolved_gaps_count": max(0, len(previous_profile.critical_gaps or []) - len(critical_gaps)),
                "evaluation_date": previous_profile.created_at.isoformat()
            }
        else:
            delta_summary = {
                "previous_score": None,
                "score_delta": 0.0,
                "previous_level": None,
                "level_changed": False,
                "newly_resolved_gaps_count": 0,
                "evaluation_date": None
            }

        # -------------------------------------------------------------
        # 10. Persistencia del Perfil
        # -------------------------------------------------------------
        profile = ProjectMaturityProfile(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            project_id=project_id,
            stage=eval_stage,
            overall_score=overall_score,
            maturity_level=maturity_level,
            target_level=target_level,
            is_target_achieved=is_target_achieved,
            dimension_scores=dimension_scores,
            discipline_scores=discipline_scores,
            critical_gaps=critical_gaps,
            acquisition_routes=acquisition_routes,
            acquired_knowledge_summary=acquired_knowledge_summary,
            assistant_usage_summary=assistant_usage_summary,
            review_capability_assessment=review_capability_assessment,
            delta_summary=delta_summary,
            evaluated_by=evaluated_by
        )

        db.add(profile)
        db.commit()
        db.refresh(profile)

        return profile

    @staticmethod
    def get_latest_maturity(db: Session, project_id: str, stage: Optional[str] = None) -> Optional[ProjectMaturityProfile]:
        query = db.query(ProjectMaturityProfile).filter(ProjectMaturityProfile.project_id == project_id)
        if stage:
            query = query.filter(ProjectMaturityProfile.stage == stage)
        return query.order_by(desc(ProjectMaturityProfile.created_at)).first()

    @staticmethod
    def get_maturity_history(db: Session, project_id: str, limit: int = 15) -> List[ProjectMaturityProfile]:
        return db.query(ProjectMaturityProfile)\
            .filter(ProjectMaturityProfile.project_id == project_id)\
            .order_by(desc(ProjectMaturityProfile.created_at))\
            .limit(limit)\
            .all()

    @staticmethod
    def export_maturity_profile_json(profile: ProjectMaturityProfile) -> Dict[str, Any]:
        payload = {
            "schema_version": "1.0.0",
            "profile_id": profile.id,
            "project_id": profile.project_id,
            "organization_id": profile.organization_id,
            "stage": profile.stage,
            "evaluated_at": profile.created_at.isoformat(),
            "overall_score": profile.overall_score,
            "maturity_level": profile.maturity_level,
            "target_level": profile.target_level,
            "is_target_achieved": profile.is_target_achieved,
            "dimension_scores": profile.dimension_scores,
            "discipline_scores": profile.discipline_scores,
            "critical_gaps": profile.critical_gaps,
            "acquisition_routes": profile.acquisition_routes,
            "acquired_knowledge_summary": profile.acquired_knowledge_summary,
            "assistant_usage_summary": profile.assistant_usage_summary,
            "review_capability_assessment": profile.review_capability_assessment,
            "delta_summary": profile.delta_summary,
            "evaluated_by": profile.evaluated_by
        }
        raw_bytes = str(payload).encode("utf-8")
        manifest_hash = hashlib.sha256(raw_bytes).hexdigest()
        payload["manifest_hash"] = manifest_hash
        return payload
