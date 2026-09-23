import json
import os
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.db.models.decision_memory import (
    ReviewDiscipline,
    ReviewTopic,
    RuleDefinition,
    RuleApplicability,
    RuleExecutionDependency
)
from app.services.rules.engine import RuleRegistry
from app.core.logging import logger

TAXONOMY_JSON_PATHS = [
    os.path.join(os.getcwd(), "data", "review_taxonomy", "review_disciplines_topics_v1.json"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "review_taxonomy", "review_disciplines_topics_v1.json"),
    "/app/data/review_taxonomy/review_disciplines_topics_v1.json",
    os.path.join("..", "data", "review_taxonomy", "review_disciplines_topics_v1.json"),
]


class TaxonomyService:
    """Servicio de gestión y sincronización de taxonomía de revisión y aplicabilidad canónica."""

    @classmethod
    def _find_taxonomy_file(cls) -> Optional[str]:
        for path in TAXONOMY_JSON_PATHS:
            if os.path.exists(path):
                return path
        return None

    @classmethod
    def seed_taxonomy_and_rules(cls, db: Session) -> Dict[str, int]:
        """Siembra de forma idempotente las disciplinas, temas, reglas y aplicabilidades canónicas."""
        # 1. Asegurar siembra de reglas base en rule_definitions
        RuleRegistry.seed_database_definitions(db)

        # 2. Cargar archivo JSON de taxonomía
        tax_path = cls._find_taxonomy_file()
        disciplines_seeded = 0
        topics_seeded = 0
        applicabilities_seeded = 0

        tax_data = {"disciplines": [], "topics": []}
        if tax_path:
            try:
                with open(tax_path, "r", encoding="utf-8") as f:
                    tax_data = json.load(f)
            except Exception as e:
                logger.error(f"Error leyendo archivo de taxonomía en {tax_path}: {e}")

        # Mapa de código de disciplina -> ID en DB
        discipline_map: Dict[str, str] = {}

        # 3. Sembrar disciplinas
        for d in tax_data.get("disciplines", []):
            code = d.get("code")
            if not code:
                continue
            existing = db.query(ReviewDiscipline).filter(ReviewDiscipline.code == code).first()
            if not existing:
                disc = ReviewDiscipline(
                    code=code,
                    name=d.get("name", code),
                    description=d.get("description"),
                    order_index=d.get("display_order", 0),
                    is_active=True
                )
                db.add(disc)
                db.flush()
                discipline_map[code] = disc.id
                disciplines_seeded += 1
            else:
                existing.name = d.get("name", existing.name)
                existing.description = d.get("description", existing.description)
                existing.order_index = d.get("display_order", existing.order_index)
                discipline_map[code] = existing.id

        # 4. Sembrar temas (topics)
        topic_map: Dict[str, str] = {}
        for t in tax_data.get("topics", []):
            code = t.get("code")
            if not code:
                continue
            disc_code = t.get("discipline_code")
            disc_id = discipline_map.get(disc_code) if disc_code else None
            meta = t.get("metadata", {})
            enabled_mvp = meta.get("enabled_mvp", False) or (code == "PID_SYMBOLS")
            is_transversal = meta.get("is_transversal", False) or (disc_code is None)

            existing = db.query(ReviewTopic).filter(ReviewTopic.code == code).first()
            if not existing:
                topic = ReviewTopic(
                    code=code,
                    name=t.get("name", code),
                    description=t.get("description"),
                    discipline_id=disc_id,
                    is_transversal=is_transversal,
                    enabled_mvp=enabled_mvp,
                    order_index=t.get("display_order", 0),
                    is_active=True
                )
                db.add(topic)
                db.flush()
                topic_map[code] = topic.id
                topics_seeded += 1
            else:
                existing.name = t.get("name", existing.name)
                existing.description = t.get("description", existing.description)
                existing.discipline_id = disc_id or existing.discipline_id
                existing.enabled_mvp = enabled_mvp
                existing.is_transversal = is_transversal
                topic_map[code] = existing.id

        db.commit()

        # 5. Sembrar aplicabilidades canónicas para el MVP
        # PIPING + PID_SYMBOLS
        piping_disc_id = discipline_map.get("PIPING")
        general_disc_id = discipline_map.get("GENERAL")
        pid_symbols_topic_id = topic_map.get("PID_SYMBOLS")

        if piping_disc_id and pid_symbols_topic_id:
            # Lista de reglas para piping / pid_symbols
            mvp_rules = [
                ("SYM-UNKNOWN-001", piping_disc_id, "primary", "approved", "Validación canónica de símbolos no reconocidos en P&ID"),
                ("SYM-AMBIGUOUS-001", piping_disc_id, "primary", "approved", "Detección de ambigüedad y solape clasificatorio top-1 vs top-2"),
                ("SYM-LEGEND-CONSISTENCY-001", piping_disc_id, "primary", "approved", "Conciliación cruzada entre dibujo P&ID y cuadro de leyendas"),
                ("SYM-TAG-MISSING-001", piping_disc_id, "primary", "approved", "Presencia obligatoria de tags en válvulas y componentes"),
            ]
            if general_disc_id:
                mvp_rules.append(
                    ("GEN-DOC-001", general_disc_id, "general", "approved", "Integridad y trazabilidad documental básica del plano")
                )

            for rule_code, disc_id, role, app_status, rationale in mvp_rules:
                rule_def = db.query(RuleDefinition).filter(RuleDefinition.code == rule_code).first()
                if not rule_def:
                    continue

                existing_app = db.query(RuleApplicability).filter(
                    RuleApplicability.rule_id == rule_def.id,
                    RuleApplicability.discipline_id == disc_id,
                    RuleApplicability.topic_id == pid_symbols_topic_id
                ).first()

                if not existing_app:
                    app = RuleApplicability(
                        rule_id=rule_def.id,
                        discipline_id=disc_id,
                        topic_id=pid_symbols_topic_id,
                        role=role,
                        source="human",
                        approval_status=app_status,
                        reviewer="system_lead_auditor",
                        rationale=rationale,
                        confidence=1.0
                    )
                    db.add(app)
                    applicabilities_seeded += 1
                else:
                    existing_app.approval_status = app_status
                    existing_app.role = role
                    existing_app.rationale = rationale

            db.commit()

            # 6. Sembrar dependencias de ejecución entre reglas
            sym_unknown = db.query(RuleDefinition).filter(RuleDefinition.code == "SYM-UNKNOWN-001").first()
            if sym_unknown:
                for dep_code in ["SYM-AMBIGUOUS-001", "SYM-LEGEND-CONSISTENCY-001", "SYM-TAG-MISSING-001"]:
                    dep_rule = db.query(RuleDefinition).filter(RuleDefinition.code == dep_code).first()
                    if dep_rule:
                        existing_dep = db.query(RuleExecutionDependency).filter(
                            RuleExecutionDependency.rule_id == dep_rule.id,
                            RuleExecutionDependency.depends_on_rule_id == sym_unknown.id
                        ).first()
                        if not existing_dep:
                            db.add(RuleExecutionDependency(
                                rule_id=dep_rule.id,
                                depends_on_rule_id=sym_unknown.id,
                                dependency_type="requires_evaluated"
                            ))
                db.commit()

        return {
            "disciplines_seeded": disciplines_seeded,
            "topics_seeded": topics_seeded,
            "applicabilities_seeded": applicabilities_seeded
        }

    @classmethod
    def get_disciplines(cls, db: Session, active_only: bool = True) -> List[ReviewDiscipline]:
        query = db.query(ReviewDiscipline)
        if active_only:
            query = query.filter(ReviewDiscipline.is_active.is_(True))
        return query.order_by(ReviewDiscipline.order_index, ReviewDiscipline.code).all()

    @classmethod
    def get_topics(cls, db: Session, discipline_code: Optional[str] = None, active_only: bool = True) -> List[ReviewTopic]:
        query = db.query(ReviewTopic)
        if active_only:
            query = query.filter(ReviewTopic.is_active.is_(True))

        if discipline_code:
            disc = db.query(ReviewDiscipline).filter(ReviewDiscipline.code == discipline_code).first()
            if disc:
                # Incluye temas de la disciplina O temas transversales
                query = query.filter(
                    or_(
                        ReviewTopic.discipline_id == disc.id,
                        ReviewTopic.is_transversal.is_(True)
                    )
                )

        return query.order_by(ReviewTopic.order_index, ReviewTopic.code).all()

    @classmethod
    def get_applicable_rules(
        cls,
        db: Session,
        discipline_code: str,
        topic_code: str,
        mode: str = "production"
    ) -> List[Dict[str, Any]]:
        """
        Retorna las reglas aplicables canónicamente para una disciplina y un tema.
        En modo 'production': solo reglas con RuleApplicability 'approved' y RuleDefinition enabled y 'approved'.
        En modo 'sandbox': permite reglas en estado 'proposed' o 'draft'.
        """
        # Buscar IDs
        disc = db.query(ReviewDiscipline).filter(ReviewDiscipline.code == discipline_code).first()
        gen_disc = db.query(ReviewDiscipline).filter(ReviewDiscipline.code == "GENERAL").first()
        topic = db.query(ReviewTopic).filter(ReviewTopic.code == topic_code).first()

        if not topic:
            return []

        # Disciplinas aplicables: la disciplina solicitada + GENERAL
        disc_ids = [disc.id] if disc else []
        if gen_disc and gen_disc.id not in disc_ids:
            disc_ids.append(gen_disc.id)

        query = db.query(RuleApplicability, RuleDefinition).join(
            RuleDefinition, RuleApplicability.rule_id == RuleDefinition.id
        ).filter(
            RuleApplicability.topic_id == topic.id,
            RuleApplicability.discipline_id.in_(disc_ids)
        )

        if mode == "production":
            query = query.filter(
                RuleApplicability.approval_status == "approved",
                RuleDefinition.enabled.is_(True),
                RuleDefinition.source_status == "approved"
            )
        else:
            # En Sandbox, se admiten reglas aprobadas, propuestas o en borrador
            query = query.filter(
                RuleApplicability.approval_status.in_(["approved", "proposed", "draft"]),
                RuleDefinition.enabled.is_(True)
            )

        results = query.all()
        applicable = []

        for app, rule in results:
            applicable.append({
                "rule_id": rule.id,
                "code": rule.code,
                "name": rule.name,
                "category": rule.category,
                "discipline": rule.discipline,
                "severity_default": rule.severity_default,
                "description": rule.description,
                "rule_scope": rule.rule_scope,
                "execution_phase": rule.execution_phase,
                "priority": rule.priority,
                "requires_data": rule.requires_data or [],
                "applicable_document_types": rule.applicable_document_types or [],
                "applicability_id": app.id,
                "role": app.role,
                "approval_status": app.approval_status,
                "source": app.source,
                "rationale": app.rationale,
                "confidence": app.confidence
            })

        # Ordenar topológicamente: primero menor execution_phase, luego menor priority (mayor prioridad)
        applicable.sort(key=lambda r: (r["execution_phase"], r["priority"], r["code"]))
        return applicable
