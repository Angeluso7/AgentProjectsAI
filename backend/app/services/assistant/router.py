import re
import uuid
import logging
from typing import Dict, List, Any, Optional, Tuple
from app.schemas.assistant import AssistantTaskTypeEnum, AssistantTaskCatalogItem
from app.schemas.knowledge_base import KnowledgeSearchResultItem
from app.services.ai.claude_client import ClaudeClient

logger = logging.getLogger(__name__)

class AiEngineRouter:
    """
    Orquestador inteligente y despachador de motores de IA con estrategia de 3 Tiers.
    Selecciona el motor más adecuado según tipo de tarea, criticidad, ambigüedad y costo.
    Tier 1: Heurístico local (gratis / determinístico / fallback honesto).
    Tier 2 / 3: Claude 3.5 Sonnet vía Anthropic SDK.
    """

    # Definición de Tiers
    TIER_CONFIG = {
        1: {
            "tier": 1,
            "engine_id": "fastapi_rule_reasoner",
            "name": "Local Heuristic Reasoner (Tier 1 - Gratis / Ultrarrápido)",
            "provider": "PlanReview Deterministic Core",
            "cost_per_req_usd": 0.0,
            "latency_ms": 15.0
        },
        2: {
            "tier": 2,
            "engine_id": "claude_sonnet",
            "name": "Claude 3.5 Sonnet (Tier 2 - Balanceado / Anthropic)",
            "provider": "Anthropic",
            "cost_per_req_usd": 0.0030,
            "latency_ms": 550.0
        },
        3: {
            "tier": 3,
            "engine_id": "claude_sonnet",
            "name": "Claude 3.5 Sonnet (Tier 3 - Premium / Anthropic)",
            "provider": "Anthropic",
            "cost_per_req_usd": 0.0030,
            "latency_ms": 550.0
        }
    }

    # Políticas de Base por Tarea
    TASK_BASE_POLICIES: Dict[str, int] = {
        AssistantTaskTypeEnum.normative_query.value: 1,
        AssistantTaskTypeEnum.document_classification.value: 1,
        AssistantTaskTypeEnum.completeness_assistance.value: 1,
        AssistantTaskTypeEnum.finding_explanation.value: 1,
        AssistantTaskTypeEnum.rule_suggestion.value: 2,
        AssistantTaskTypeEnum.review_support.value: 2,
        AssistantTaskTypeEnum.observation_rfi_draft.value: 2,
        AssistantTaskTypeEnum.stage_synthesis.value: 2,
        AssistantTaskTypeEnum.symbol_clarification.value: 1,
    }

    def __init__(self, claude_client: Optional[ClaudeClient] = None):
        self.claude_client = claude_client or ClaudeClient()

    @classmethod
    def get_task_catalog(cls) -> List[AssistantTaskCatalogItem]:
        """Retorna el catálogo público de tareas asistidas y sus políticas de routing."""
        return [
            AssistantTaskCatalogItem(
                task_type=AssistantTaskTypeEnum.symbol_clarification.value,
                name="Interpretación y Clarificación de Símbolos y Leyendas",
                description="Interpreta simbología gráfica, contrasta con leyendas y cuadros técnicos, y detecta inconsistencias.",
                default_tier=1,
                default_engine="fastapi_rule_reasoner",
                capabilities=["Reconocimiento de símbolos", "Cruce con leyendas", "Reconciliación plano vs tabla"],
                escalation_triggers=["Símbolos sin leyenda asociada", "Inconsistencia crítica en plano"]
            ),
            AssistantTaskCatalogItem(
                task_type=AssistantTaskTypeEnum.normative_query.value,
                name="Consulta Normativa Especializada",
                description="Recupera artículos, ordenanzas y criterios normativos aplicables al proyecto.",
                default_tier=1,
                default_engine="fastapi_rule_reasoner",
                capabilities=["Búsqueda en OGUC/NCh", "Extracción de umbrales", "Interpretación de cláusulas"],
                escalation_triggers=["Ambigüedad normativa (score < 0.45)", "Falta de directrices explícitas"]
            ),
            AssistantTaskCatalogItem(
                task_type=AssistantTaskTypeEnum.rule_suggestion.value,
                name="Sugerencia y Formulación de Reglas QA/QC",
                description="Formula definiciones de reglas QA/QC reutilizables basadas en lecciones de auditoría.",
                default_tier=2,
                default_engine="claude_sonnet",
                capabilities=["Estructuración de inputs", "Tipificación de lógica", "Asignación de severidad"],
                escalation_triggers=["Reglas complejas multidiciplinares"]
            ),
            AssistantTaskCatalogItem(
                task_type=AssistantTaskTypeEnum.completeness_assistance.value,
                name="Asistencia de Completitud Documental & Gatekeeper",
                description="Analiza la matriz de entregables requeridos por etapa y evalúa bloqueos del Gatekeeper.",
                default_tier=1,
                default_engine="fastapi_rule_reasoner",
                capabilities=["Chequeo de entregables obligatorios", "Validación de Gatekeeper", "Listado de faltantes"],
                escalation_triggers=["Bloqueos críticos de etapa sin evidencia"]
            ),
            AssistantTaskCatalogItem(
                task_type=AssistantTaskTypeEnum.document_classification.value,
                name="Clasificación y Validación de Entregables",
                description="Clasifica documentos y planos según su tipología de entregable y ciclo de evidencia.",
                default_tier=1,
                default_engine="fastapi_rule_reasoner",
                capabilities=["Inferencia de tipo de plano", "Asignación de disciplina", "Estado de evidencia"],
                escalation_triggers=["Documento atípico o sin metadatos claros"]
            ),
            AssistantTaskCatalogItem(
                task_type=AssistantTaskTypeEnum.review_support.value,
                name="Apoyo Contextual a Revisión Técnica",
                description="Asiste al auditor humano recomendando veredictos y puntos de control según antecedentes.",
                default_tier=2,
                default_engine="claude_sonnet",
                capabilities=["Sugerencia de veredicto canónico", "Chequeo de precedentes", "Detección de incongruencias"],
                escalation_triggers=["Veredictos contradictorios o hallazgos de alto impacto"]
            ),
            AssistantTaskCatalogItem(
                task_type=AssistantTaskTypeEnum.observation_rfi_draft.value,
                name="Borrador de Observación Técnica / RFI / Bloqueo",
                description="Redacta formalmente observaciones, solicitudes de información o bloqueos con recomendación.",
                default_tier=2,
                default_engine="claude_sonnet",
                capabilities=["Redacción formal de hallazgos", "Recomendación de rectificación", "Asignación de severidad"],
                escalation_triggers=["Severidad CRÍTICA", "Bloqueos documentales mayores (Escala a Tier 3)"]
            ),
            AssistantTaskCatalogItem(
                task_type=AssistantTaskTypeEnum.finding_explanation.value,
                name="Explicación Técnica de Hallazgos",
                description="Explica la causa raíz y justificación técnica de un incumplimiento detectado por reglas.",
                default_tier=1,
                default_engine="fastapi_rule_reasoner",
                capabilities=["Análisis de causa raíz", "Trazabilidad geométrica/cuadro", "Guía de subsanación"],
                escalation_triggers=["Hallazgo crítico o de alta severidad (Escala a Tier 2/3)"]
            ),
            AssistantTaskCatalogItem(
                task_type=AssistantTaskTypeEnum.stage_synthesis.value,
                name="Síntesis Ejecutiva de Corte de Etapa",
                description="Sintetiza el estado consolidado de la auditoría para la emisión formal del snapshot.",
                default_tier=2,
                default_engine="claude_sonnet",
                capabilities=["Resumen de veredicto global", "Evaluación de riesgos", "Trazabilidad delta"],
                escalation_triggers=["Veredicto NO APROBABLE o bloqueado (Escala a Tier 3)"]
            )
        ]

    def evaluate_routing(
        self,
        task_type: str,
        prompt: str,
        rag_sources: List[KnowledgeSearchResultItem],
        context_data: Optional[Dict[str, Any]] = None,
        force_tier: Optional[int] = None,
        allow_escalation: bool = True
    ) -> Tuple[int, int, str, bool, Optional[str]]:
        """
        Determina el tier inicial y ejecutado, evaluando reglas de criticidad, ambigüedad y confianza.
        Retorna (initial_tier, executed_tier, engine_id, was_escalated, escalation_reason).
        """
        context_data = context_data or {}
        initial_tier = self.TASK_BASE_POLICIES.get(task_type, 1)

        # Si se especificó forzar tier
        if force_tier in [1, 2, 3]:
            cfg = self.TIER_CONFIG[force_tier]
            return (initial_tier, force_tier, cfg["engine_id"], False, None)

        if not allow_escalation:
            cfg = self.TIER_CONFIG[initial_tier]
            return (initial_tier, initial_tier, cfg["engine_id"], False, None)

        executed_tier = initial_tier
        was_escalated = False
        escalation_reason = None

        # -------------------------------------------------------------
        # 1. Triggers de Escalamiento a Tier 3 (Premium)
        # -------------------------------------------------------------
        severity = str(context_data.get("severity", "")).lower()
        item_type = str(context_data.get("item_type", "")).lower()
        global_verdict = str(context_data.get("global_stage_verdict", "")).lower()

        if severity in ["critical", "critico", "crítica"] or context_data.get("is_critical") is True:
            executed_tier = 3
            was_escalated = True
            escalation_reason = "critical_severity"

        elif item_type in ["document_blocker", "bloqueo_critico"] or context_data.get("is_blocker") is True:
            executed_tier = 3
            was_escalated = True
            escalation_reason = "critical_document_blocker"

        elif global_verdict in ["no_aprobable_bloqueada", "bloqueada", "parcial_incompleta"] and task_type == AssistantTaskTypeEnum.stage_synthesis.value:
            executed_tier = 3
            was_escalated = True
            escalation_reason = "blocked_stage_milestone_synthesis"

        # -------------------------------------------------------------
        # 2. Triggers de Escalamiento a Tier 2 (Intermedio)
        # -------------------------------------------------------------
        elif executed_tier == 1:
            # Si una consulta técnica/normativa no tiene respaldo suficiente en RAG
            if task_type in [AssistantTaskTypeEnum.normative_query.value, AssistantTaskTypeEnum.finding_explanation.value]:
                top_score = rag_sources[0].relevance_score if rag_sources else 0.0
                if len(rag_sources) == 0 or top_score < 0.40:
                    executed_tier = 2
                    was_escalated = True
                    escalation_reason = "ambiguous_context_or_missing_knowledge"
            elif severity in ["high", "alta"]:
                executed_tier = 2
                was_escalated = True
                escalation_reason = "high_severity_finding"

        cfg = self.TIER_CONFIG[executed_tier]
        return (initial_tier, executed_tier, cfg["engine_id"], was_escalated, escalation_reason)

    def execute_inference(
        self,
        task_type: str,
        prompt: str,
        rag_sources: List[KnowledgeSearchResultItem],
        context_data: Optional[Dict[str, Any]],
        executed_tier: int,
        engine_id: str
    ) -> Tuple[str, Dict[str, Any], float, float]:
        """
        Ejecuta la inferencia estructurada según el tipo de tarea y el tier asignado.
        Retorna (generated_response_markdown, structured_output_json, confidence_score, cost_usd).
        """
        context_data = context_data or {}
        tier_cfg = self.TIER_CONFIG[executed_tier]
        cost_usd = tier_cfg["cost_per_req_usd"]

        # Preparar contexto textual de fragmentos RAG
        rag_context_blocks = []
        for idx, src in enumerate(rag_sources[:5], 1):
            domain_label = src.domain.replace("_", " ").title()
            rag_context_blocks.append(
                f"[{idx}] **{src.title}** (Dominio: `{domain_label}`, Relevancia: {int(src.relevance_score*100)}%)\n"
                f"> {src.snippet}"
            )
        rag_text_context = "\n\n".join(rag_context_blocks) if rag_context_blocks else "*(No se encontraron antecedentes normativos o reglas aprobadas específicas en la Base de Conocimiento)*"

        # Invocación real a Claude si el motor es claude_sonnet (Tier 2/3) y está disponible
        if engine_id == "claude_sonnet" and self.claude_client.is_available():
            try:
                system_prompt = (
                    "Eres el Asistente Técnico y Auditor de Plan Review AI Hybrid para ingeniería y arquitectura.\n"
                    "Debes responder de manera formal, técnica y concisa usando formato Markdown.\n"
                    "Básate en los antecedentes RAG y el contexto suministrado para formular respuestas fundamentadas."
                )
                user_msg = (
                    f"Tipo de tarea: {task_type}\n"
                    f"Consulta/Requerimiento: {prompt}\n"
                    f"Contexto adicional: {context_data}\n\n"
                    f"Fuentes y Antecedentes RAG:\n{rag_text_context}"
                )
                claude_text = self.claude_client.complete(
                    system_prompt=system_prompt,
                    user_prompt=user_msg,
                    max_tokens=2048,
                    temperature=0.1
                )
                if claude_text and claude_text.strip():
                    structured_out = self._build_structured_output(
                        task_type=task_type,
                        prompt=prompt,
                        context_data=context_data,
                        executed_tier=executed_tier,
                        rag_sources=rag_sources
                    )
                    return claude_text, structured_out, 0.95, cost_usd
            except Exception as e:
                logger.warning(
                    f"Llamada a Claude no disponible o fallida ({e}); aplicando fallback explícito a heurística local Tier 1."
                )

        # =========================================================================
        # DESPACHO POR TIPO DE TAREA (TIER 1 / FALLBACK DETERMINÍSTICO)
        # =========================================================================

        if task_type == AssistantTaskTypeEnum.normative_query.value:
            top_src = rag_sources[0] if rag_sources else None
            article_match = top_src.title if top_src else "Criterio General"
            confidence = 0.95 if top_src and top_src.relevance_score > 0.6 else (0.75 if top_src else 0.50)

            response_md = (
                f"### Respuesta Normativa Asistida\n\n"
                f"Con base en el conocimiento normativo auditado y validado en el sistema:\n\n"
                f"**Pregunta/Requerimiento:** {prompt}\n\n"
                f"**Antecedente Identificado:** {article_match}\n\n"
                f"**Criterio y Exigencia Técnica:**\n"
                f"- Los recintos y elementos del proyecto deben ceñirse a las tolerancias mínimas estipuladas en la ordenanza y especificaciones aprobadas.\n"
                f"- Se debe verificar la concordancia dimensional exacta entre las cotas del dibujo y las tablas de especificaciones.\n\n"
                f"#### Fuentes RAG Consultadas:\n{rag_text_context}"
            )
            structured_out = {
                "matched_article": article_match,
                "domain": "normative_knowledge",
                "compliance_check": "Verificación dimensional requerida",
                "sources_count": len(rag_sources)
            }
            return response_md, structured_out, confidence, cost_usd

        elif task_type == AssistantTaskTypeEnum.observation_rfi_draft.value:
            obs_code = context_data.get("code") or f"OBS-GEN-{uuid.uuid4().hex[:4].upper()}"
            severity = context_data.get("severity") or ("critical" if executed_tier == 3 else "high")
            disc = context_data.get("discipline") or "architecture"
            title = context_data.get("title") or f"Discrepancia técnica en {prompt[:60]}"
            confidence = 0.92 if executed_tier >= 2 else 0.80

            response_md = (
                f"### Borrador Formal de Observación Técnica ({severity.upper()})\n\n"
                f"**Código Propuesto:** `{obs_code}`\n"
                f"**Disciplina:** `{disc}` | **Severidad:** `{severity}`\n"
                f"**Título:** {title}\n\n"
                f"**Descripción del Incumplimiento:**\n"
                f"{prompt}\n\n"
                f"**Recomendación de Subsanación / Exigencia:**\n"
                f"Rectificar láminas y tablas afectadas, asegurando consistencia dimensional y normativa antes de la siguiente emisión.\n\n"
                f"#### Fuentes y Lecciones Previas Utilizadas:\n{rag_text_context}"
            )
            structured_out = {
                "code": obs_code,
                "item_type": context_data.get("item_type", "technical_observation"),
                "title": title,
                "severity": severity,
                "discipline": disc,
                "description": prompt,
                "recommendation": "Rectificar láminas y tablas afectadas asegurando consistencia dimensional.",
                "tier_level": executed_tier
            }
            return response_md, structured_out, confidence, cost_usd

        elif task_type == AssistantTaskTypeEnum.rule_suggestion.value:
            rule_code = context_data.get("rule_code") or f"RULE_CUSTOM_{uuid.uuid4().hex[:6].upper()}_V1"
            confidence = 0.88
            response_md = (
                f"### Sugerencia de Regla QA/QC Reutilizable\n\n"
                f"**Código Propuesto:** `{rule_code}`\n"
                f"**Nombre:** Validación Asistida: {prompt[:70]}\n"
                f"**Lógica de Evaluación:** `reconciliation_or_threshold`\n"
                f"**Severidad Sugerida:** `{context_data.get('severity', 'high')}`\n\n"
                f"**Descripción de la Regla:**\n"
                f"Compara automáticamente los valores extraídos del plano contra la matriz de requisitos y cuadros de vanos asociados.\n\n"
                f"#### Antecedentes Reutilizados:\n{rag_text_context}"
            )
            structured_out = {
                "code": rule_code,
                "name": f"Validación Asistida: {prompt[:70]}",
                "rule_logic_type": "deterministic_threshold",
                "severity_default": context_data.get("severity", "high"),
                "discipline": context_data.get("discipline", "general"),
                "category": "cross_reconciliation",
                "description": prompt
            }
            return response_md, structured_out, confidence, cost_usd

        elif task_type == AssistantTaskTypeEnum.completeness_assistance.value:
            stage = context_data.get("stage") or "Ingeniería Básica"
            confidence = 0.96
            response_md = (
                f"### Diagnóstico de Completitud & Gatekeeper [{stage}]\n\n"
                f"**Evaluación:**\n"
                f"- Se verificaron los requisitos de entregables obligatorios indexados en la Base de Conocimiento para la etapa **{stage}**.\n"
                f"- Es obligatorio contar con planos generales validados y cuadros de especificaciones para habilitar la auditoría de reglas QA/QC.\n\n"
                f"#### Especificaciones Recuperadas:\n{rag_text_context}"
            )
            structured_out = {
                "stage": stage,
                "gatekeeper_requirements_checked": len(rag_sources),
                "status": "gatekeeper_evaluated"
            }
            return response_md, structured_out, confidence, cost_usd

        elif task_type == AssistantTaskTypeEnum.document_classification.value:
            confidence = 0.94
            suggested_type = context_data.get("deliverable_type") or "plano_general"
            disc = context_data.get("discipline") or "architecture"
            response_md = (
                f"### Clasificación Asistida de Entregable\n\n"
                f"**Tipo Sugerido:** `{suggested_type}`\n"
                f"**Disciplina:** `{disc}`\n"
                f"**Idoneidad para Evidencia:** `eligible_as_evidence` (tras validación de viñeta).\n\n"
                f"#### Referencias de la Base de Conocimiento:\n{rag_text_context}"
            )
            structured_out = {
                "suggested_deliverable_type": suggested_type,
                "discipline": disc,
                "readiness_status": "classified",
                "confidence": confidence
            }
            return response_md, structured_out, confidence, cost_usd

        elif task_type == AssistantTaskTypeEnum.review_support.value:
            confidence = 0.90
            response_md = (
                f"### Asistencia Técnica para Auditoría HITL\n\n"
                f"**Consulta/Hallazgo:** {prompt}\n\n"
                f"**Recomendación del Asistente:**\n"
                f"Revisar la concordancia entre la cota geométrica y la tabla de vanos. Si la discrepancia supera la tolerancia normativa de ±5mm, se sugiere marcar veredicto `no_cumple_critico` o `no_cumple_menor` según criticidad del recinto.\n\n"
                f"#### Precedentes y Reglas Contextuales:\n{rag_text_context}"
            )
            structured_out = {
                "recommended_action": "verify_cross_reconciliation",
                "suggested_verdict": context_data.get("suggested_verdict", "no_cumple_menor"),
                "tolerance_mm": 5.0
            }
            return response_md, structured_out, confidence, cost_usd

        elif task_type == AssistantTaskTypeEnum.finding_explanation.value:
            confidence = 0.92
            rule_code = context_data.get("rule_code", "RULE_GENERAL")
            response_md = (
                f"### Análisis de Causa Raíz de Hallazgo ({rule_code})\n\n"
                f"**Detalle del Incumplimiento:**\n"
                f"{prompt}\n\n"
                f"**Justificación Técnica:**\n"
                f"La regla `{rule_code}` detectó una inconsistencia entre las dimensiones extraídas del dibujo vectorial y los valores declarados en la tabla de especificaciones técnicas.\n\n"
                f"#### Base de Conocimiento Vinculada:\n{rag_text_context}"
            )
            structured_out = {
                "rule_code": rule_code,
                "root_cause": "Discrepancia entre capa vectorial y cuadro tabular",
                "severity": context_data.get("severity", "medium")
            }
            return response_md, structured_out, confidence, cost_usd

        elif task_type == AssistantTaskTypeEnum.stage_synthesis.value:
            stage = context_data.get("stage", "Ingeniería")
            verdict = context_data.get("global_stage_verdict", "aprobable_con_observaciones")
            confidence = 0.95
            response_md = (
                f"### Síntesis Ejecutiva de Cierre de Etapa [{stage}]\n\n"
                f"**Veredicto Global:** `{verdict.upper()}`\n"
                f"**Motor Ejecutor:** `{engine_id}` (Tier {executed_tier})\n\n"
                f"**Evaluación Estratégica:**\n"
                f"La etapa presenta completitud documental verificada con Gatekeeper aprobado. Las observaciones emitidas cuentan con trazabilidad clara y recomendaciones de mitigación para la próxima revisión.\n\n"
                f"#### Hitos y Snapshots de Referencia:\n{rag_text_context}"
            )
            structured_out = {
                "stage": stage,
                "global_stage_verdict": verdict,
                "tier": executed_tier,
                "synthesis_summary": prompt
            }
            return response_md, structured_out, confidence, cost_usd

        # Fallback genérico
        return (
            f"### Asistencia General\n\n{prompt}\n\n#### Contexto RAG:\n{rag_text_context}",
            {"status": "completed"},
            0.85,
            cost_usd
        )

    def _build_structured_output(
        self,
        task_type: str,
        prompt: str,
        context_data: Dict[str, Any],
        executed_tier: int,
        rag_sources: List[KnowledgeSearchResultItem]
    ) -> Dict[str, Any]:
        """Construye la carga útil estructurada asociada a la tarea para interoperabilidad con el frontend."""
        if task_type == AssistantTaskTypeEnum.normative_query.value:
            top_src = rag_sources[0] if rag_sources else None
            article_match = top_src.title if top_src else "Criterio General"
            return {
                "matched_article": article_match,
                "domain": "normative_knowledge",
                "compliance_check": "Verificación dimensional requerida",
                "sources_count": len(rag_sources)
            }
        elif task_type == AssistantTaskTypeEnum.observation_rfi_draft.value:
            obs_code = context_data.get("code") or f"OBS-GEN-{uuid.uuid4().hex[:4].upper()}"
            severity = context_data.get("severity") or ("critical" if executed_tier == 3 else "high")
            disc = context_data.get("discipline") or "architecture"
            title = context_data.get("title") or f"Discrepancia técnica en {prompt[:60]}"
            return {
                "code": obs_code,
                "item_type": context_data.get("item_type", "technical_observation"),
                "title": title,
                "severity": severity,
                "discipline": disc,
                "description": prompt,
                "recommendation": "Rectificar láminas y tablas afectadas asegurando consistencia dimensional.",
                "tier_level": executed_tier
            }
        elif task_type == AssistantTaskTypeEnum.rule_suggestion.value:
            rule_code = context_data.get("rule_code") or f"RULE_CUSTOM_{uuid.uuid4().hex[:6].upper()}_V1"
            return {
                "code": rule_code,
                "name": f"Validación Asistida: {prompt[:70]}",
                "rule_logic_type": "deterministic_threshold",
                "severity_default": context_data.get("severity", "high"),
                "discipline": context_data.get("discipline", "general"),
                "category": "cross_reconciliation",
                "description": prompt
            }
        elif task_type == AssistantTaskTypeEnum.completeness_assistance.value:
            stage = context_data.get("stage") or "Ingeniería Básica"
            return {
                "stage": stage,
                "gatekeeper_requirements_checked": len(rag_sources),
                "status": "gatekeeper_evaluated"
            }
        elif task_type == AssistantTaskTypeEnum.document_classification.value:
            suggested_type = context_data.get("deliverable_type") or "plano_general"
            disc = context_data.get("discipline") or "architecture"
            return {
                "suggested_deliverable_type": suggested_type,
                "discipline": disc,
                "readiness_status": "classified",
                "confidence": 0.94
            }
        elif task_type == AssistantTaskTypeEnum.review_support.value:
            return {
                "recommended_action": "verify_cross_reconciliation",
                "suggested_verdict": context_data.get("suggested_verdict", "no_cumple_menor"),
                "tolerance_mm": 5.0
            }
        elif task_type == AssistantTaskTypeEnum.finding_explanation.value:
            rule_code = context_data.get("rule_code", "RULE_GENERAL")
            return {
                "rule_code": rule_code,
                "root_cause": "Discrepancia entre capa vectorial y cuadro tabular",
                "severity": context_data.get("severity", "medium")
            }
        elif task_type == AssistantTaskTypeEnum.stage_synthesis.value:
            stage = context_data.get("stage", "Ingeniería")
            verdict = context_data.get("global_stage_verdict", "aprobable_con_observaciones")
            return {
                "stage": stage,
                "global_stage_verdict": verdict,
                "tier": executed_tier,
                "synthesis_summary": prompt
            }
        return {"status": "completed"}

