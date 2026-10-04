# Plan de Implementación: Límites de Búsqueda Web, Criterios de Suficiencia y Normalización del Conocimiento Visual

Implementar mejoras operativas profundas en la Arquitectura de Incorporación de Información y Base de Conocimiento Operacional en dos ejes fundamentales:
1. **Límites de Búsqueda Web y Criterios de Suficiencia**: Iteraciones máximas, score multi-criterio de suficiencia, estados de término trazables y escalamiento estructurado y explicable a Solicitud Documental.
2. **Normalización y Gobernanza del Conocimiento Visual**: Captura enriquecida desde el Visor (símbolos, tablas, detalles, viñetas), deduplicación y vinculación de ocurrencias, versionamiento, ciclo de vida formal y consumo activo por el Asistente Copilot RAG.

---

## Cambios Propuestos

### 1. Backend: Modelos y Base de Datos

#### [MODIFY] [`backend/app/db/models/acquisition.py`](file:///c:/Users/Windows/OneDrive/Estructura%20Proyectos/plan-review-ai-hybrid/backend/app/db/models/acquisition.py)
- Añadir campos de control de iteración y límites:
  - `iteration_count: Integer` (número de iteraciones ejecutadas).
  - `max_iterations: Integer` (límite máximo, default 3).
  - `search_sources_limit: Integer` (límite de fuentes por consulta, default 5).
  - `relevance_score: Float`, `confidence_score: Float`, `coverage_score: Float`, `overall_adequacy_score: Float`.
  - `termination_reason: String(64)` (`resolved_satisfactory`, `partial_needs_validation`, `insufficient_document_requested`, `cancelled_by_user`, `exhausted_max_attempts`, `not_applicable_private_project_data`).
  - `escalation_details: JSON` (payload explicable: `missing_information_details`, `why_web_internal_failed`, `requested_document_type`, `suggested_responsible`, `audit_impact_justification`, `unlocked_deliverables_and_rules`).

#### [MODIFY] [`backend/app/db/models/knowledge_base.py`](file:///c:/Users/Windows/OneDrive/Estructura%20Proyectos/plan-review-ai-hybrid/backend/app/db/models/knowledge_base.py)
- Asegurar que `structured_payload` soporte de forma normalizada:
  - `normalized_category: str` (e.g. `extinguisher_pqs`, `electrical_board_teg`, `door_single_leaf`).
  - `aliases: List[str]` (sinónimos y términos equivalentes).
  - `visual_properties: dict` (dimensiones, tipo de geometría, color, viñeta).
  - `related_legend_id / related_legend_text: str`.
  - `related_table_id / related_table_code: str`.
  - `related_rule_code: str`.
  - `linked_occurrences: List[dict]` (referencias a otras láminas/documentos donde aparece el mismo símbolo sin duplicar la unidad).

---

### 2. Backend: Esquemas y Lógica de Servicio

#### [MODIFY] [`backend/app/schemas/acquisition.py`](file:///c:/Users/Windows/OneDrive/Estructura%20Proyectos/plan-review-ai-hybrid/backend/app/schemas/acquisition.py)
- Esquemas actualizados:
  - `SufficiencyAssessmentDTO` (scores de relevancia, cobertura, suficiencia y clasificación: `sufficient`, `partially_sufficient`, `insufficient`, `not_found`, `not_applicable`).
  - `EscalationDiagnosticDTO` (diagnóstico detallado para solicitud de documentos).
  - `VisualKnowledgeCaptureRequest` enriquecido (con `normalized_category`, `aliases`, `related_legend_text`, `related_rule_code`, `page_number`, `deduplication_mode`).
  - `VisualDeduplicationCheckResponse` (posibles coincidencias existentes para vincular ocurrencia o crear versión).

#### [MODIFY] [`backend/app/services/acquisition/service.py`](file:///c:/Users/Windows/OneDrive/Estructura%20Proyectos/plan-review-ai-hybrid/backend/app/services/acquisition/service.py)
- `detect_information_gap`: evalúa si la brecha es de naturaleza privada del proyecto (detecta keywords como "cálculo", "suelos", "fundaciones", "memorias") y pre-clasifica como `not_applicable` para búsqueda web directa, sugiriendo escalamiento inmediato.
- `respond_web_search_permission`:
  - Ejecuta búsqueda con límites estrictos (`max_iterations`, `search_sources_limit`).
  - Evalúa multi-criterio de suficiencia (`relevance_score`, `coverage_score`, `overall_adequacy_score`).
  - Clasifica en: `sufficient` (score >= 0.75), `partially_sufficient` (0.50 <= score < 0.75), `insufficient` (score < 0.50).
  - Si es insuficiente o privado, genera el payload estructurado de escalamiento a documento (`escalation_details`).
  - Registra `termination_reason`.
- `capture_from_viewer_to_knowledge`:
  - Chequeo de deduplicación semántica/visual en la organización.
  - Si existe un símbolo canónico similar y `deduplication_mode="link_occurrence"`, agrega la nueva lámina/bbox a `linked_occurrences` del ítem existente en lugar de crear un duplicado huérfano.
  - Si `deduplication_mode="new_version"`, versiona el ítem existente (`v2`).
  - Si `deduplication_mode="create_new"`, crea nuevo ítem normalizado.
- `check_visual_deduplication`: método para que el frontend alerte al usuario antes de guardar si el símbolo ya existe en el catálogo.

#### [MODIFY] [`backend/app/api/v1/endpoints/acquisition.py`](file:///c:/Users/Windows/OneDrive/Estructura%20Proyectos/plan-review-ai-hybrid/backend/app/api/v1/endpoints/acquisition.py)
- Añadir endpoint `POST /api/v1/acquisition/visual-dedup-check` para consultar símbolos existentes antes de guardar.

---

### 3. Frontend: Tipos, API y Componentes

#### [MODIFY] [`frontend/src/types/index.ts`](file:///c:/Users/Windows/OneDrive/Estructura%20Proyectos/plan-review-ai-hybrid/frontend/src/types/index.ts)
- Actualizar `InformationAcquisitionRequestDTO`, `ViewerKnowledgeCaptureDTO`, y agregar `VisualDeduplicationMatchDTO`.

#### [MODIFY] [`frontend/src/services/api.ts`](file:///c:/Users/Windows/OneDrive/Estructura%20Proyectos/plan-review-ai-hybrid/frontend/src/services/api.ts)
- Agregar método `checkVisualDeduplication`.

#### [MODIFY] [`frontend/src/components/InformationAcquisitionManagerView.tsx`](file:///c:/Users/Windows/OneDrive/Estructura%20Proyectos/plan-review-ai-hybrid/frontend/src/components/InformationAcquisitionManagerView.tsx)
- Mostrar límites de iteración, scores de suficiencia/cobertura, causas de término y desglose completo del diagnóstico de escalamiento documental.

#### [MODIFY] [`frontend/src/components/PlanSelectionsModal.tsx`](file:///c:/Users/Windows/OneDrive/Estructura%20Proyectos/plan-review-ai-hybrid/frontend/src/components/PlanSelectionsModal.tsx)
- Diálogo modal de guardado de conocimiento visual con campos de categoría normalizada, alias, leyenda relacionada, regla asociada y opción de vincular a símbolo existente si se detecta duplicado.

#### [MODIFY] [`frontend/src/components/KnowledgeBaseManager.tsx`](file:///c:/Users/Windows/OneDrive/Estructura%20Proyectos/plan-review-ai-hybrid/frontend/src/components/KnowledgeBaseManager.tsx)
- Visualización de recortes gráficos, leyendas asociadas, ocurrencias en láminas y tags de categoría normalizada en el catálogo.

---

### 4. Verificación y Suite de Pruebas

#### [MODIFY] [`backend/tests/integration/test_information_acquisition_and_web_first_flow.py`](file:///c:/Users/Windows/OneDrive/Estructura%20Proyectos/plan-review-ai-hybrid/backend/tests/integration/test_information_acquisition_and_web_first_flow.py)
- Validar los 8 escenarios solicitados:
  1. Captura de símbolo desde el visor con crop, coordenadas y origen de lámina.
  2. Asociación de disciplina, categoría normalizada, nombre, alias y OCR.
  3. Relación con leyenda, tabla y regla QA/QC.
  4. Revisión y aprobación formal del ítem visual (`draft` -> `approved_for_reuse`).
  5. Recuperación RAG por el Asistente Copilot del símbolo aprobado.
  6. Captura de símbolo equivalente en otra lámina y deduplicación / vinculación de ocurrencia sin duplicar entidad.
  7. Confirmación de que ítems visuales no validados no son recuperados por el RAG activo.
  8. Límite de intentos de búsqueda web, cálculo de suficiencia y escalamiento a solicitud documental explicable.
