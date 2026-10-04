import re
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.db.models.decision_memory import (
    RuleDefinition, RuleApplicability, RuleReviewDecision,
    ReviewDiscipline, ReviewTopic
)
from app.db.models.intake_extractions import (
    RuleDocument, RuleDocumentItem, ExtractedItem
)
from app.schemas.rule_candidates import (
    PromoteRuleCandidateRequest, PromoteRuleCandidateResponse, RuleApplicabilityItemResponse
)
from app.core.logging import logger


class RulePromotionService:
    """
    Servicio de dominio único para la promoción de reglas candidatas validadas
    hacia RuleDefinition + Baseline QA/QC + RuleApplicability aprobada.
    """

    @classmethod
    def promote_candidate(
        cls,
        db: Session,
        candidate_id: str,
        payload: PromoteRuleCandidateRequest,
        user_id: str,
        user_role: str,
        organization_id: Optional[str] = None
    ) -> PromoteRuleCandidateResponse:
        """
        Promueve una regla candidata individual a Baseline QA/QC.
        - Valida tenant y RBAC (admin, audit_lead, auditor).
        - Excluye símbolos (deben ir a SymbolTemplate).
        - Deriva el linaje inmutable desde el candidato y documento en DB (no del payload).
        - Valida taxonomía de disciplinas y tópicos aplicables.
        - Aplica idempotencia para no duplicar reglas ya promovidas.
        - Registra auditoría inmutable en RuleReviewDecision.
        """
        # 1. Validar RBAC
        allowed_roles = ["admin", "audit_lead", "auditor"]
        normalized_role = (user_role or "auditor").lower()
        if normalized_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso insuficiente. El rol '{user_role}' no está autorizado para promover reglas."
            )

        # 2. Localizar candidato en DB (RuleDocumentItem o ExtractedItem)
        candidate: Optional[RuleDocumentItem] = db.query(RuleDocumentItem).filter(
            RuleDocumentItem.id == candidate_id
        ).first()

        doc: Optional[RuleDocument] = None
        if candidate:
            doc = db.query(RuleDocument).filter(RuleDocument.id == candidate.rule_document_id).first()
        else:
            # Buscar en ExtractedItem si se pasó un candidate_id de extracción directa
            extracted: Optional[ExtractedItem] = db.query(ExtractedItem).filter(
                ExtractedItem.id == candidate_id
            ).first()
            if extracted:
                # Buscar si existe RuleDocumentItem asociado
                candidate = db.query(RuleDocumentItem).filter(
                    RuleDocumentItem.extracted_item_id == extracted.id
                ).first()
                if candidate:
                    doc = db.query(RuleDocument).filter(RuleDocument.id == candidate.rule_document_id).first()

        if not candidate or not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Regla candidata '{candidate_id}' no encontrada en el sistema."
            )

        # 3. Validar Tenant Isolation
        if organization_id and doc.organization_id and doc.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: el candidato pertenece a otra organización."
            )

        # 4. Restricción Estricta de Símbolos: NUNCA promover a RuleDefinition
        item_type = (candidate.item_type or "").lower()
        if item_type in ["symbol", "simbolo", "symbol_candidate"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Los símbolos no pueden ser promovidos a RuleDefinition. Deben gestionarse a través del Catálogo de Simbología y SymbolTemplate."
            )

        # 5. Flujo de Rechazo HITL
        if payload.decision == "reject":
            candidate_prev_state = {
                "status": candidate.status,
                "promotion_status": candidate.promotion_status,
                "promoted_rule_definition_id": candidate.promoted_rule_definition_id
            }
            candidate.status = "eliminado"
            candidate.promotion_status = "rejected"
            candidate.promotion_error = payload.reviewer_rationale
            
            decision_record = RuleReviewDecision(
                candidate_id=candidate.id,
                rule_definition_id=candidate.promoted_rule_definition_id,
                decision="reject",
                reviewer_id=user_id,
                reviewer_role=normalized_role,
                reviewer_rationale=payload.reviewer_rationale,
                rule_code=payload.rule_code,
                payload_snapshot=payload.dict(),
                previous_state=candidate_prev_state,
                new_state={"status": "eliminado", "promotion_status": "rejected"}
            )
            db.add(decision_record)
            db.commit()

            return PromoteRuleCandidateResponse(
                candidate_id=candidate.id,
                candidate_status="rejected",
                rule_definition_id=None,
                rule_code=None,
                rule_definition_status="rejected",
                baseline_status="inactive",
                applicabilities=[],
                already_promoted=False,
                message="Regla candidata rechazada exitosamente sin crear RuleDefinition."
            )

        # 6. Idempotencia: Verificar si ya fue promovido
        if candidate.promoted_rule_definition_id:
            existing_def = db.query(RuleDefinition).filter(
                RuleDefinition.id == candidate.promoted_rule_definition_id
            ).first()
            if existing_def:
                # Obtener aplicabilidades actuales
                existing_apps = db.query(RuleApplicability).filter(
                    RuleApplicability.rule_id == existing_def.id
                ).all()
                app_responses = []
                for a in existing_apps:
                    disc = db.query(ReviewDiscipline).filter(ReviewDiscipline.id == a.discipline_id).first()
                    top = db.query(ReviewTopic).filter(ReviewTopic.id == a.topic_id).first()
                    app_responses.append(RuleApplicabilityItemResponse(
                        discipline=disc.code if disc else a.discipline_id,
                        topic=top.code if top else a.topic_id,
                        approval_status=a.approval_status,
                        role=a.role
                    ))
                
                return PromoteRuleCandidateResponse(
                    candidate_id=candidate.id,
                    candidate_status=candidate.promotion_status or "promoted",
                    rule_definition_id=existing_def.id,
                    rule_code=existing_def.code,
                    rule_definition_status=existing_def.source_status,
                    baseline_status="active" if (existing_def.is_active and existing_def.enabled) else "inactive",
                    applicabilities=app_responses,
                    already_promoted=True,
                    message=f"Regla ya existe en Baseline: {existing_def.code}."
                )

        # 7. Validar y Normalizar Código de Regla
        raw_code = (payload.rule_code or "").strip()
        clean_code = re.sub(r"[^A-Za-z0-9_\-]+", "_", raw_code).upper()
        if not clean_code or len(clean_code) < 3:
            disc_prefix = (doc.discipline or "GEN").upper()[:3]
            clean_code = f"{disc_prefix}-RULE-{candidate.id[:6].upper()}"

        # 8. Validar Taxonomía (Disciplinas y Tópicos)
        resolved_disciplines, resolved_topics, pairs = cls._validate_taxonomy(
            db, payload.discipline_ids, payload.topic_ids
        )

        # 9. Derivar Linaje Fuente Inmutable desde DB
        source_lineage = cls._derive_source_lineage(db, candidate, doc)

        # 10. Determinar Estado según Política de Roles
        # admin y audit_lead pueden "promote_and_activate"; auditor sólo "promote_for_review"
        requested_action = payload.action
        if normalized_role in ["admin", "audit_lead"] and requested_action != "promote_for_review":
            rule_enabled = payload.enabled
            rule_source_status = "approved"
            app_approval_status = "approved"
            candidate_prom_status = "promoted"
            baseline_status = "active" if rule_enabled else "inactive"
        else:
            rule_enabled = False
            rule_source_status = "proposed"
            app_approval_status = "proposed"
            candidate_prom_status = "promoted_draft"
            baseline_status = "pending_approval"

        # 11. Normalizar Severidad
        severity_map = {
            "critical": "critical",
            "major": "high",
            "high": "high",
            "medium": "medium",
            "low": "low",
            "info": "info"
        }
        normalized_severity = severity_map.get((payload.severity or "medium").lower(), "medium")

        # Snapshot de estado previo
        candidate_prev_state = {
            "status": candidate.status,
            "promotion_status": candidate.promotion_status,
            "promoted_rule_definition_id": candidate.promoted_rule_definition_id
        }

        # 12. Crear o Actualizar RuleDefinition
        existing_rule_by_code = db.query(RuleDefinition).filter(
            RuleDefinition.code == clean_code
        ).first()

        primary_discipline_code = resolved_disciplines[0].code if resolved_disciplines else (doc.discipline or "general")

        if existing_rule_by_code:
            rule_def = existing_rule_by_code
            rule_def.name = payload.title
            rule_def.description = candidate.content_text or candidate.description or payload.title
            rule_def.discipline = primary_discipline_code
            rule_def.severity_default = normalized_severity
            rule_def.execution_phase = payload.execution_phase
            rule_def.enabled = rule_enabled
            rule_def.source_status = rule_source_status
            rule_def.is_active = True
            rule_def.source_candidate_id = candidate.id
            rule_def.source_document_id = doc.id
            rule_def.source_page = source_lineage["page"]
            rule_def.source_bbox = source_lineage["bbox"]
            rule_def.source_excerpt = source_lineage["excerpt"]
            rule_def.source_hash = source_lineage["hash"]
            rule_def.input_requirements = {
                "source_document_id": doc.id,
                "source_document_title": doc.title,
                "rule_document_item_id": candidate.id,
                "authority": doc.authority,
                "derived_lineage": source_lineage
            }
            rule_def.updated_at = datetime.utcnow()
        else:
            rule_def = RuleDefinition(
                code=clean_code,
                name=payload.title,
                category="normative_compliance",
                discipline=primary_discipline_code,
                severity_default=normalized_severity,
                description=candidate.content_text or candidate.description or payload.title,
                rule_scope="specialty" if primary_discipline_code != "GENERAL" else "general",
                execution_phase=payload.execution_phase,
                priority=100,
                enabled=rule_enabled,
                source_status=rule_source_status,
                is_active=True,
                version=doc.version or "1.0",
                source_candidate_id=candidate.id,
                source_document_id=doc.id,
                source_page=source_lineage["page"],
                source_bbox=source_lineage["bbox"],
                source_excerpt=source_lineage["excerpt"],
                source_hash=source_lineage["hash"],
                input_requirements={
                    "source_document_id": doc.id,
                    "source_document_title": doc.title,
                    "rule_document_item_id": candidate.id,
                    "authority": doc.authority,
                    "derived_lineage": source_lineage
                },
                rule_logic_type="normative_check",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(rule_def)
            db.flush()

        # 13. Crear / Actualizar RuleApplicabilities canónicas
        applicabilities_out: List[RuleApplicabilityItemResponse] = []
        for disc, top in pairs:
            existing_app = db.query(RuleApplicability).filter(
                RuleApplicability.rule_id == rule_def.id,
                RuleApplicability.discipline_id == disc.id,
                RuleApplicability.topic_id == top.id
            ).first()

            if not existing_app:
                app_record = RuleApplicability(
                    rule_id=rule_def.id,
                    discipline_id=disc.id,
                    topic_id=top.id,
                    role="primary",
                    source="human",
                    approval_status=app_approval_status,
                    reviewer=user_id,
                    rationale=payload.reviewer_rationale,
                    confidence=1.0,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(app_record)
            else:
                existing_app.approval_status = app_approval_status
                existing_app.reviewer = user_id
                existing_app.rationale = payload.reviewer_rationale
                existing_app.updated_at = datetime.utcnow()

            applicabilities_out.append(RuleApplicabilityItemResponse(
                discipline=disc.code,
                topic=top.code,
                approval_status=app_approval_status,
                role="primary"
            ))

        # 14. Actualizar Estado de Candidate (RuleDocumentItem)
        candidate.promoted_rule_definition_id = rule_def.id
        candidate.promoted_at = datetime.utcnow()
        candidate.promoted_by = user_id
        candidate.promotion_status = candidate_prom_status
        candidate.status = "validada"
        candidate.metadata_payload = {
            **(candidate.metadata_payload or {}),
            "promoted_to_baseline": True,
            "promoted_at": candidate.promoted_at.isoformat(),
            "promoted_by": user_id,
            "rule_definition_id": rule_def.id,
            "baseline_code": rule_def.code,
            "baseline_status": baseline_status
        }

        # 15. Registrar Decisión HITL Inmutable
        review_decision = RuleReviewDecision(
            candidate_id=candidate.id,
            rule_definition_id=rule_def.id,
            decision="approve",
            reviewer_id=user_id,
            reviewer_role=normalized_role,
            reviewer_rationale=payload.reviewer_rationale,
            rule_code=rule_def.code,
            payload_snapshot=payload.dict(),
            previous_state=candidate_prev_state,
            new_state={
                "candidate_status": candidate_prom_status,
                "rule_definition_id": rule_def.id,
                "rule_code": rule_def.code,
                "source_status": rule_source_status,
                "enabled": rule_enabled,
                "applicabilities": [a.dict() for a in applicabilities_out]
            }
        )
        db.add(review_decision)

        # 16. Transaccional: Commit atómico
        db.commit()

        logger.info(
            f"Regla candidata '{candidate.id}' promovida exitosamente a '{rule_def.code}' "
            f"con estado '{baseline_status}' por usuario '{user_id}' ({normalized_role})."
        )

        return PromoteRuleCandidateResponse(
            candidate_id=candidate.id,
            candidate_status=candidate_prom_status,
            rule_definition_id=rule_def.id,
            rule_code=rule_def.code,
            rule_definition_status=rule_source_status,
            baseline_status=baseline_status,
            applicabilities=applicabilities_out,
            already_promoted=False,
            message="Regla promovida a Baseline QA/QC exitosamente."
        )

    DISCIPLINE_ALIASES = {
        "ARQUITECTURA": "ARCHITECTURE",
        "ARCHITECTURE": "ARCHITECTURE",
        "ESTRUCTURA": "STRUCTURES",
        "ESTRUCTURAS": "STRUCTURES",
        "STRUCTURES": "STRUCTURES",
        "TUBERIAS": "PIPING",
        "TUBERÍAS": "PIPING",
        "PIPING": "PIPING",
        "MECANICA": "HVAC",
        "MECÁNICA": "HVAC",
        "HVAC": "HVAC",
        "CLIMATIZACION": "HVAC",
        "CLIMATIZACIÓN": "HVAC",
        "ELECTRICO": "ELECTRICAL",
        "ELECTRICA": "ELECTRICAL",
        "ELÉCTRICO": "ELECTRICAL",
        "ELÉCTRICA": "ELECTRICAL",
        "ELECTRICAL": "ELECTRICAL",
        "INSTRUMENTACION": "INSTRUMENTATION_CONTROL",
        "INSTRUMENTACIÓN": "INSTRUMENTATION_CONTROL",
        "INSTRUMENTATION": "INSTRUMENTATION_CONTROL",
        "INCENDIO": "FIRE_PROTECTION",
        "FIRE": "FIRE_PROTECTION",
        "FIRE_PROTECTION": "FIRE_PROTECTION",
        "SANITARIA": "SANITARY",
        "SANITARY": "SANITARY",
        "CIVIL": "CIVIL",
        "BIM": "BIM_COORDINATION",
        "BIM_COORDINATION": "BIM_COORDINATION",
        "SEGURIDAD": "CONSTRUCTABILITY_SAFETY",
        "GENERAL": "GENERAL",
    }

    @classmethod
    def _validate_taxonomy(
        cls,
        db: Session,
        discipline_ids: List[str],
        topic_ids: List[str]
    ) -> Tuple[List[ReviewDiscipline], List[ReviewTopic], List[Tuple[ReviewDiscipline, ReviewTopic]]]:
        """
        Valida que cada disciplina y tópico existan, estén activos y sean estrictamente compatibles entre sí.
        - Cada topic_id debe pertenecer a una disciplina seleccionada O ser transversal (o disciplina GENERAL/all).
        - Si la disciplina está inactiva o no existe: HTTP 422.
        - Si el tópico está inactivo o no existe: HTTP 422.
        - Si la combinación disciplina/tópico es incompatible: HTTP 422 estructurado.
        - No se crean definiciones ni aplicabilidades huérfanas o erróneas.
        """
        if db.query(ReviewDiscipline).count() == 0:
            try:
                from app.services.review.taxonomy_service import TaxonomyService
                TaxonomyService.seed_taxonomy_and_rules(db)
            except Exception as e:
                logger.warning(f"No se pudo sembrar taxonomía automáticamente: {e}")

        if not discipline_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "missing_discipline",
                    "message": "Debe especificar al menos una disciplina técnica válida.",
                    "field": "discipline_ids"
                }
            )

        if not topic_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "missing_topic",
                    "message": "Debe especificar al menos un tópico técnico de revisión.",
                    "field": "topic_ids"
                }
            )

        # 1. Resolver y validar Disciplinas
        resolved_disciplines: List[ReviewDiscipline] = []
        for d in discipline_ids:
            clean_d = d.strip()
            norm_code = cls.DISCIPLINE_ALIASES.get(clean_d.upper(), clean_d.upper())
            
            disc = db.query(ReviewDiscipline).filter(
                or_(
                    ReviewDiscipline.code == norm_code,
                    ReviewDiscipline.code == clean_d.upper(),
                    ReviewDiscipline.id == clean_d,
                    ReviewDiscipline.name.ilike(f"{clean_d}")
                )
            ).first()

            if not disc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "discipline_not_found",
                        "message": f"La disciplina '{d}' no existe en el catálogo de taxonomía.",
                        "field": "discipline_ids",
                        "value": d
                    }
                )

            if not disc.is_active:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "inactive_discipline",
                        "message": f"La disciplina '{disc.code}' ({disc.name}) se encuentra inactiva.",
                        "field": "discipline_ids",
                        "value": disc.code
                    }
                )

            if disc not in resolved_disciplines:
                resolved_disciplines.append(disc)

        # 2. Resolver y validar Tópicos
        resolved_topics: List[ReviewTopic] = []
        for t in topic_ids:
            clean_t = t.strip()
            top = db.query(ReviewTopic).filter(
                or_(
                    ReviewTopic.code == clean_t.upper(),
                    ReviewTopic.id == clean_t,
                    ReviewTopic.name.ilike(f"{clean_t}")
                )
            ).first()

            if not top:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "topic_not_found",
                        "message": f"El tópico '{t}' no existe en el catálogo de taxonomía.",
                        "field": "topic_ids",
                        "value": t
                    }
                )

            if not top.is_active:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "inactive_topic",
                        "message": f"El tópico '{top.code}' ({top.name}) se encuentra inactivo.",
                        "field": "topic_ids",
                        "value": top.code
                    }
                )

            if top not in resolved_topics:
                resolved_topics.append(top)

        # 3. Validar Compatibilidad Estricta Disciplina <-> Tópico
        pairs: List[Tuple[ReviewDiscipline, ReviewTopic]] = []
        disc_ids_set = {disc.id for disc in resolved_disciplines}
        has_general_disc = any(disc.code in ["GENERAL", "ALL"] for disc in resolved_disciplines)

        for top in resolved_topics:
            is_transversal = bool(top.is_transversal or top.discipline_id is None)

            if is_transversal:
                # Tópicos transversales son compatibles con cualquier disciplina o GENERAL
                for disc in resolved_disciplines:
                    pairs.append((disc, top))
            else:
                # Tópico específico: debe pertenecer a una de las disciplinas seleccionadas
                if top.discipline_id in disc_ids_set:
                    matching_disc = next(d for d in resolved_disciplines if d.id == top.discipline_id)
                    pairs.append((matching_disc, top))
                elif has_general_disc:
                    # Regla transversal/general con disciplina general
                    general_disc = next(d for d in resolved_disciplines if d.code in ["GENERAL", "ALL"])
                    pairs.append((general_disc, top))
                else:
                    # Incompatible: buscar la disciplina propietaria del tópico
                    topic_disc = db.query(ReviewDiscipline).filter(ReviewDiscipline.id == top.discipline_id).first()
                    topic_disc_code = topic_disc.code if topic_disc else "DESCONOCIDA"
                    selected_disc_codes = [d.code for d in resolved_disciplines]
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={
                            "error": "invalid_taxonomy_combination",
                            "message": f"Combinación incompatible: El tópico '{top.code}' pertenece a la disciplina '{topic_disc_code}', no a las disciplinas seleccionadas: {selected_disc_codes}.",
                            "field": "topic_ids",
                            "topic_code": top.code,
                            "topic_discipline": topic_disc_code,
                            "selected_disciplines": selected_disc_codes
                        }
                    )

        if not pairs:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "no_valid_pairs",
                    "message": "No se encontraron combinaciones válidas entre las disciplinas y tópicos seleccionados.",
                    "field": "taxonomy"
                }
            )

        return resolved_disciplines, resolved_topics, pairs

    @classmethod
    def _derive_source_lineage(
        cls,
        db: Session,
        candidate: RuleDocumentItem,
        doc: RuleDocument
    ) -> Dict[str, Any]:
        """
        Deriva inmutablemente los metadatos de linaje fuente desde las entidades en DB.
        """
        # 1. Página y Bounding Box
        page = 1
        bbox = None
        if candidate.metadata_payload:
            page = candidate.metadata_payload.get("page_number") or candidate.metadata_payload.get("page") or 1
            bbox = candidate.metadata_payload.get("bbox_normalized") or candidate.metadata_payload.get("bbox")

        # Si viene vinculado a ExtractedItem, usar datos de extracción original
        if candidate.extracted_item_id:
            ext_item = db.query(ExtractedItem).filter(ExtractedItem.id == candidate.extracted_item_id).first()
            if ext_item:
                if ext_item.page_number:
                    page = ext_item.page_number
                if ext_item.bbox_normalized and not bbox:
                    bbox = ext_item.bbox_normalized

        # 2. Extracto de texto
        excerpt = candidate.content_text or candidate.description or candidate.title

        # 3. Hash inmutable
        source_hash = ""
        if doc.metadata_info:
            source_hash = doc.metadata_info.get("file_hash") or doc.metadata_info.get("sha256") or ""
        if not source_hash:
            content_to_hash = f"{doc.id}_{page}_{excerpt}"
            source_hash = hashlib.sha256(content_to_hash.encode("utf-8")).hexdigest()

        return {
            "page": page,
            "bbox": bbox,
            "excerpt": excerpt,
            "hash": source_hash,
            "document_title": doc.title,
            "authority": doc.authority,
            "version": doc.version
        }
