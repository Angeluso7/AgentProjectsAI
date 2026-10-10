# AGENTS.md — Guía Viva de Desarrollo para Asistentes y Colaboradores

Documento de gobernanza arquitectónica y operativa para **Plan Review AI Hybrid**. Todo agente de IA (Antigravity u otros) y colaborador humano debe leer y acatar estas directrices antes de modificar el repositorio.

---

## 1. Visión del Proyecto

**Plan Review AI Hybrid** es una plataforma de auditoría y aseguramiento de calidad técnica (QA/QC) especializada en la revisión automatizada y asistida de planos y especificaciones de ingeniería, con foco primordial en **piping, instrumentación (P&ID), mecánica y plantas de procesos**.

El sistema integra:
- **Pipeline de Ingesta y Visión Híbrida:** Rasterizado de láminas, OCR vectorial y óptico, segmentación de layout, extracción de tablas/viñetas y detección geométrica/neuronal de simbología técnica.
- **Catálogo Canónico y Gobernanza de Símbolos:** Validación estricta con evidencia real y humana en el bucle (HITL) para promover plantillas a producción.
- **Motor de Reglas QA/QC Determinista:** Verificación paramétrica de normativas (ASME B31.3, NCh, ISO) libre de alucinaciones.
- **Inteligencia Artificial Real vía Claude (Anthropic API):** Razonamiento normativo Tier 2/3 mediante `claude-sonnet-5-5` para extracción semántica, sugerencia de reglas y diagnóstico en el copilot, con conmutación limpia a fallbacks heurísticos deterministas ante desconexión o falta de credenciales.

---

## 2. Reglas No Negociables de Arquitectura

1. **Esquema de Base de Datos exclusivamente por Alembic:**
   - **NUNCA** ejecutar DDL con SQL crudo ni `Base.metadata.create_all()` en el ciclo de vida de la aplicación (`main.py lifespan`).
   - Todo cambio en tablas, columnas, índices o claves foráneas debe implementarse mediante migraciones versionadas en `backend/alembic/versions` y validarse con `alembic upgrade head`.

2. **Inclusión Total de Terminología de Piping / Mecánica / Procesos:**
   - **NUNCA** excluir términos de piping, líneas de proceso, tags de válvulas o instrumentación en listas hardcodeadas de keywords o disciplinas (OCR, layout, extracción de tablas, detección de símbolos).
   - El sistema debe tratar `piping`, `mecanica` y `procesos` como disciplinas de primer orden en todos los módulos clasificadores y diccionarios de sinónimos.

3. **Visibilidad Obligatoria de Estados en la UI:**
   - Todo detector o pipeline de IA/heurística (OCR, segmentación, tablas, símbolos, review run) debe exponer su estado de ciclo de vida (`queued`, `running`, `completed/succeeded`, `failed`, `unknown/not_evaluable`) de forma visible en la interfaz de usuario (visores, modales, tablas de proyectos y pipelines), no sólo en assertions de tests.

4. **Persistencia Remota Obligatoria por Sesión:**
   - Toda rama de trabajo —incluso si contiene avances parciales no finalizados— debe concluir la sesión con **commit claro y push a GitHub**. Ningún trabajo debe quedar exclusivamente en local.

5. **Seguridad Absoluta de Credenciales y Secretos:**
   - `ANTHROPIC_API_KEY`, tokens de GitHub y cualquier secreto de API **NUNCA** se deben escribir, pegar, versionar ni imprimir en código fuente, commits, logs, pull requests ni archivos bajo control de versiones.
   - Las claves residen exclusivamente en el `.env` local del desarrollador/entorno, el cual debe permanecer permanentemente excluido en `.gitignore`.

6. **Validación Estricta de Schemas Pydantic (`extra='forbid'`):**
   - Para prevenir que desalineaciones de nombres de campo pasen inadvertidas (ya que Pydantic v2 ignora por defecto kwargs desconocidos), los schemas de endpoints nuevos deben incorporar `model_config = ConfigDict(extra="forbid")`.
   - Las suites de tests deben validar explícitamente todos los campos clave de la respuesta (tanto a nivel raíz como en items individuales de listas).

7. **Sincronización de Dependencias en Entornos Docker Locales:**
   - Debido a que `docker-compose.yml` monta un volumen anónimo para `node_modules` (`/app/node_modules`) para aislar y optimizar el rendimiento en desarrollo, las dependencias añadidas a `package.json` (o dependencias de backend) no se instalan automáticamente al reiniciar el contenedor.
   - Tras fusionar un PR o actualizar ramas con nuevas dependencias, se debe ejecutar `docker compose exec frontend npm install` (o `docker compose up -d --build frontend/backend`) antes de probar la aplicación en local para evitar fallos de resolución de módulos en Vite (`Failed to resolve import`).

8. **Incondicionalidad Estricta de Hooks en Componentes React (Rules of Hooks):**
   - En todos los componentes y vistas React de la plataforma, **TODOS** los hooks (`useState`, `useEffect`, `useMemo`, `useCallback`, etc.) deben declararse incondicionalmente al principio de la función, **ANTES** de cualquier sentencia `return` condicional (como `if (!isOpen || !run) return null;`).
   - Las variables o derivaciones necesarias para los hooks deben formularse de forma defensiva mediante encadenamiento opcional (`run?.id`, `run?.symbol_inventory`) y valores por defecto (`defaultMetrics`), evitando discrepancias en el conteo u orden de hooks entre renders consecutivos que provoquen el error fatal *"Rendered more/fewer hooks than during the previous render"*.

9. **Sincronización Obligatoria de Flags en Reglas (`enabled` e `is_active`):**
   - El modelo `RuleDefinition` posee dos flags booleanos independientes consultados en diferentes partes del sistema (`taxonomy_service.py` filtra por `enabled`, mientras que `engine.py` y el endpoint `GET /rules` filtran por `is_active`).
   - Para que la activación/desactivación sea 100% consistente y no cosmética, **AMBOS** flags deben actualizarse siempre al unísono con el mismo valor booleano (`enabled = value`, `is_active = value`). Nunca modificar solo uno.

10. **Resolución Determinística de Jerarquías y Fallbacks:**
    - Toda query o lógica que deba resolver una coincidencia específica frente a un fallback genérico (ej. disciplina técnica solicitada vs. disciplina `GENERAL`) **NUNCA** debe confiar en el orden físico de las filas devuelto por un `OR` sin `ORDER BY`.
    - Debe implementarse una consulta explícita en dos pasos (primero coincidencia exacta activa; solo si no existe, consulta del fallback general) o utilizar un ordenamiento determinístico explícito (`order_by(..., ...)`).

11. **Idempotencia Estricta en Migraciones de Esquema (`sa.inspect`):**
    - Toda migración de Alembic que agregue una columna o índice a una tabla ya existente debe verificar primero mediante `sa.inspect(conn).get_columns(...)` si la columna ya existe antes de invocar `op.add_column(...)`, exactamente como en `0033_add_project_id_to_decision_traces.py` y `0035_add_discipline_code_to_document_deliverables.py`.
    - Esto es obligatorio porque scripts de validación integral (como Gate 4) pueden reconstruir el esquema completo vía `Base.metadata.create_all()` usando los modelos ORM actuales antes de reproducir el historial de Alembic, provocando errores `DuplicateColumn` si las migraciones intermedias sobre tablas fuera de la ventana de downgrade probada no son idempotentes.

12. **Vigencia y Deprecación de Identificadores de Modelos de IA:**
    - Los identificadores y alias de modelos de IA en `claude_client.py` y `registry.py` deben revisarse periódicamente contra la documentación oficial y calendarios de deprecación del proveedor (Anthropic, OpenAI, Google).
    - **NUNCA** resolver alias internos hacia snapshots con fecha descontinuados (ej. `claude-3-5-sonnet-20241022`). Los modelos de generación actual (como `claude-sonnet-5-5`) deben enviarse como identificador semántico directo a la API, y los alias heredados deben redirigirse a los modelos vigentes recomendados para evitar fallos silenciosos en producción.

---

## 3. Mapa de Servicios Clave

| Servicio / Módulo | Ruta de Archivo | Responsabilidad Principal |
| :--- | :--- | :--- |
| **SymbolService** | [`backend/app/services/symbols/service.py`](backend/app/services/symbols/service.py) | Orquestación de detección, emparejamiento con catálogo y persistencia de símbolos en láminas. |
| **RulePromotionService** | [`backend/app/services/rules/promotion_service.py`](backend/app/services/rules/promotion_service.py) | Promoción gobernada de reglas desde candidatos sandbox/HITL hacia catálogo productivo. |
| **CanonicalPipingCatalogService** | [`backend/app/services/symbols/canonical_catalog_service.py`](backend/app/services/symbols/canonical_catalog_service.py) | Gestión del catálogo canónico de símbolos de piping, validación de evidencia y políticas de orientación. |
| **AiEngineRouter** | [`backend/app/services/assistant/router.py`](backend/app/services/assistant/router.py) | Enrutador multicapa (Tier 1 heurístico vs Tier 2 LLM Claude) con políticas de escalado y fallback. |
| **ClaudeClient** | [`backend/app/services/ai/claude_client.py`](backend/app/services/ai/claude_client.py) | Cliente SDK Anthropic para inferencia estructurada (`claude-sonnet-5-5`), soporte multimodal de visión y manejo seguro de errores. |
| **SymbolResearchService** | [`backend/app/services/symbols/research_service.py`](backend/app/services/symbols/research_service.py) | Orquestación de investigación de símbolos desconocidos vía Claude Vision, validación humana HITL y promoción al catálogo canónico. |
| **Review Orchestrator** | [`backend/app/services/review/orchestrator.py`](backend/app/services/review/orchestrator.py) | Orquestador integral de auditorías One-Click Review: ejecuta fases 1 a 9, evaluando reglas y hallazgos. |

---

## 4. Pendientes Conocidos y Próximos Pasos

- **[RESUELTO] Actualización y Vigencia de Motores de IA (Claude, OpenAI, Gemini):** Resuelto el bug crítico de degradación de modelo en `ClaudeClient` donde `claude-sonnet-5-5` se resolvía erróneamente hacia el snapshot retirado `claude-3-5-sonnet-20241022`. Se reconfiguró `MODEL_ALIASES` para preservar `claude-sonnet-5-5` como ID de API nativo y redirigir los alias obsoletos (`claude-3-5-sonnet`, `claude-3.5-sonnet`, `claude-3-7-sonnet`) hacia `claude-sonnet-5-5`. Se actualizaron los metadatos de catálogo en `registry.py` reflejando la generación vigente (`Claude Sonnet 5.5`, OpenAI `GPT-6 Sol / Luna` v6.1, Google `Gemini 3.8 Flash / Gemini 3.1 Pro`) y trazabilidad de traducción en `translation_service.py` y `translations.py`.

- **[RESUELTO] Resolución Determinística de Disciplina/Punto de Revisión y Re-sincronización de Alcance:** Se resolvió la anomalía donde reglas validadas de documentos de Piping (ej. ISA 5.1 2009) se promovían con disciplina `GENERAL` y tópico `DOCUMENT_COMPLETENESS` debido a una query `OR` no determinística que favorecía el orden físico de inserción de Postgres. Se implementó resolución determinística jerárquica (búsqueda exacta de especialidad primero, fallback a GENERAL solo si no existe, y orden determinístico por `order_index` en tópicos), soporte para parámetros explícitos `discipline_code` y `topic_code` en `promote_rule_document_to_baseline` y en `POST /rules/documents/{doc_id}/promote-to-baseline` (`extra='forbid'`), endpoint de reparación masiva idempotente `POST /rules/documents/{doc_id}/resync-applicability`, y en frontend el modal interactivo `PromoteDocumentScopeModal` con selector pre-cargado de Disciplina y Punto de Revisión tanto en `RulesPage` ("Promover a Baseline QA/QC", "Sincronizar Baseline", "Re-sinc. Alcance") como en `DocumentContentReviewModal`, permitiendo corregir o definir el alcance de auditoría One-Click Review sin duplicación de aplicabilidades.
- **[RESUELTO] Validación Masiva de Reglas en Contenido Documental:** Resuelto el vacío funcional donde solo los símbolos poseían acción en bloque ("Curar Símbolos") mientras que los ítems tipo regla requerían validación individual por fila, manteniendo inactivos los botones del footer "Validar Contenido" y "Promover Documento a Baseline QA/QC". Se implementó el endpoint `POST /rules/documents/{doc_id}/items/bulk-validate` con schema Pydantic (`extra="forbid"`), el método repositorio `bulk_validate_rule_items` que excluye de forma estricta símbolos, tablas, figuras y eliminados, y en `DocumentContentReviewModal` el botón de cabecera "Validar Reglas (N)", banner superior con selección múltiple/todas, y checkboxes por fila, desbloqueando la promoción masiva a Baseline QA/QC sin afectar el flujo de símbolos ni la validación individual.
- **[RESUELTO] Retiro de Reglas Demo de Arquitectura y Gestión Self-Service de Reglas:** Las 6 reglas de ejemplo de arquitectura (`RULE_DOOR_COUNT_MATCH_V1`, `RULE_WINDOW_COUNT_MATCH_V1`, `RULE_TITLE_BLOCK_REQUIRED_FIELDS_V1`, `RULE_TITLE_BLOCK_SCALE_VALID_V1`, `RULE_REQUIRED_TABLES_BY_DOCUMENT_TYPE_V1`, `RULE_NORMATIVE_MIN_WIDTH_DOOR_V1`) fueron retiradas de la inicialización por defecto (`RuleRegistry.register_default_rules()`) y desactivadas de forma permanente mediante la migración `0034_deactivate_legacy_architecture_rules` (`enabled=false`, `is_active=false`), preservando las filas para salvaguardar la trazabilidad de ejecuciones/hallazgos históricos. Se implementaron los endpoints `PATCH /rules/{rule_code}` y `DELETE /rules/{rule_code}` (con respuesta 409 segura y desactivación automática si existen ejecuciones o hallazgos asociados, o borrado físico si no existen referencias) y controles visuales interactivos en `RulesPage` (toggle activar/desactivar, eliminación con modal de confirmación y banner de feedback), brindando gestión self-service completa sin requerir intervención manual por prompts.
- **[RESUELTO] Ingestión de Documentos por Carpeta (Batch Intake):** Implementado con selector dual de archivos sueltos y carpetas completas vía `webkitdirectory` para documentos de proyecto (`/documents/batch-upload`) y fuentes de entrenamiento (`/intake/sources/batch-upload`), con filtrado cliente de archivos de sistema, streaming eficiente en backend y preservación de rutas relativas jerárquicas en metadatos.
- **[RESUELTO] Ciclo de Vida de Símbolos Desconocidos y Consola HITL:** Backend implementado al 100% con `SymbolResearchService` y visión multimodal (`ClaudeClient.complete_vision`). Consola visual implementada al 100% en frontend mediante el componente modal `ResearchCasesPanel` accesible desde `RulesPage`, con filtros por estado de investigación, previsualización de recortes con fallback defensivo, disparo de investigación asistida por IA (`POST /ai-research`), modal de promoción estructurada a plantilla canónica (`POST /promote`) y descarte formal de casos (`POST /dismiss`).
- **Captura Estructurada de Correcciones Humanas para Fine-Tuning / Active Learning:** Implementar el módulo dedicado de *MLOps & Active Learning* (desacoplado de la Base de Conocimiento) para almacenar retroalimentación de triage, correcciones de bboxes de símbolos y falsos positivos como dataset etiquetado para reentrenamiento de modelos YOLO/SAHI.
- **Ingestión de Fuentes Normativas Web (Deferida):** Diseñar conectores de adquisición normativas externas con validación formal de gobernanza y control de propiedad intelectual antes de ingresar a la memoria normativa.
- **Catálogo de Símbolos Esperados por Proyecto/Norma (Evolución de Resumen Ejecutivo):** La lista base de 7 familias de válvulas estándar (`PIP-VALVE-GATE`, `PIP-VALVE-GLOBE`, etc.) en `generate_executive_summary` es un supuesto temporal de referencia general para la visualización del MVP, no un catálogo cerrado ni específico del proyecto ni de la norma aplicable. Debe evolucionar hacia una derivación dinámica según la disciplina, el catálogo canónico del proyecto o las especificaciones técnicas aplicables.
- **Motor de Comparación de Símbolos y Primitivas Geométricas:** El motor de comparación de símbolos contra el catálogo canónico se mantiene en NCC + Momentos de Hu (`TemplateMatcher`). Las tablas `SymbolGeometricFeature` / `SymbolFeatureRelation` (primitivas geométricas explicables) no son el motor de matching activo; quedan como metadato de auditoría para un único tipo de ejemplo (válvula de compuerta). Pendiente futuro: embeber imágenes de símbolo en el PDF exportado (requiere soporte de XObject de imagen en `SimplePdfCanvas`).



