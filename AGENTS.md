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

---

## 3. Mapa de Servicios Clave

| Servicio / Módulo | Ruta de Archivo | Responsabilidad Principal |
| :--- | :--- | :--- |
| **SymbolService** | [`backend/app/services/symbols/service.py`](backend/app/services/symbols/service.py) | Orquestación de detección, emparejamiento con catálogo y persistencia de símbolos en láminas. |
| **RulePromotionService** | [`backend/app/services/rules/promotion_service.py`](backend/app/services/rules/promotion_service.py) | Promoción gobernada de reglas desde candidatos sandbox/HITL hacia catálogo productivo. |
| **CanonicalPipingCatalogService** | [`backend/app/services/symbols/canonical_catalog_service.py`](backend/app/services/symbols/canonical_catalog_service.py) | Gestión del catálogo canónico de símbolos de piping, validación de evidencia y políticas de orientación. |
| **AiEngineRouter** | [`backend/app/services/assistant/router.py`](backend/app/services/assistant/router.py) | Enrutador multicapa (Tier 1 heurístico vs Tier 2 LLM Claude) con políticas de escalado y fallback. |
| **ClaudeClient** | [`backend/app/services/ai/claude_client.py`](backend/app/services/ai/claude_client.py) | Cliente SDK Anthropic para inferencia estructurada (`claude-sonnet-5-5`) y manejo seguro de errores. |
| **Review Orchestrator** | [`backend/app/services/review/orchestrator.py`](backend/app/services/review/orchestrator.py) | Orquestador integral de auditorías One-Click Review: ejecuta fases 1 a 9, evaluando reglas y hallazgos. |

---

## 4. Pendientes Conocidos y Próximos Pasos

- **[RESUELTO] Ingestión de Documentos por Carpeta (Batch Intake):** Implementado con selector dual de archivos sueltos y carpetas completas vía `webkitdirectory` para documentos de proyecto (`/documents/batch-upload`) y fuentes de entrenamiento (`/intake/sources/batch-upload`), con filtrado cliente de archivos de sistema, streaming eficiente en backend y preservación de rutas relativas jerárquicas en metadatos.
- **Captura Estructurada de Correcciones Humanas para Fine-Tuning / Active Learning:** Implementar el módulo dedicado de *MLOps & Active Learning* (desacoplado de la Base de Conocimiento) para almacenar retroalimentación de triage, correcciones de bboxes de símbolos y falsos positivos como dataset etiquetado para reentrenamiento de modelos YOLO/SAHI.
- **Ingestión de Fuentes Normativas Web (Deferida):** Diseñar conectores de adquisición normativas externas con validación formal de gobernanza y control de propiedad intelectual antes de ingresar a la memoria normativa.
- **Catálogo de Símbolos Esperados por Proyecto/Norma (Evolución de Resumen Ejecutivo):** La lista base de 7 familias de válvulas estándar (`PIP-VALVE-GATE`, `PIP-VALVE-GLOBE`, etc.) en `generate_executive_summary` es un supuesto temporal de referencia general para la visualización del MVP, no un catálogo cerrado ni específico del proyecto ni de la norma aplicable. Debe evolucionar hacia una derivación dinámica según la disciplina, el catálogo canónico del proyecto o las especificaciones técnicas aplicables.
