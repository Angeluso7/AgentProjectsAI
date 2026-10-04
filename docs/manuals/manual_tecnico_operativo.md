# Manual Técnico y Operativo — Plan Review AI Hybrid

> **Documento de Arquitectura, Flujo de Datos, Gobernanza y Operación Técnica**  
> **Versión de la Plataforma:** v0.3.0  
> **Nivel de Fidelidad:** Estricto (Reflejo del código real en backend, frontend, bases de datos y servicios).

---

## 1. Visión General de la Arquitectura del Sistema

**Plan Review AI Hybrid** implementa una arquitectura híbrida desacoplada en tres capas principales:

```
+---------------------------------------------------------------------------------------+
|                                  CLIENTE WEB (SPA)                                    |
|   React 18 + TypeScript + Vite 5 + Tailwind CSS v3 (Visor SVG, Copilot Drawer, Triage)|
+---------------------------------------------------------------------------------------+
                                           | HTTP REST (JSON / Multipart / JWT / Tenant)
                                           v
+---------------------------------------------------------------------------------------+
|                                GATEWAY API (FastAPI)                                  |
|   - Middleware de Autenticación JWT + Aislamiento Multi-Tenant (Org ID)               |
|   - Control de Acceso Basado en Roles (RBAC: Admin, Auditor, Revisor, Lector)         |
|   - Endpoints v1 (/intake, /ocr, /rules, /assistant, /knowledge, /maturity, /reports) |
+---------------------------------------------------------------------------------------+
         |                      |                       |                      |
         v                      v                       v                      v
+----------------+     +----------------+     +------------------+    +----------------+
|  PERCEPCIÓN    |     | MOTOR REGLAS   |     | ASISTENTE RAG    |    |  ADQUISICIÓN & |
|  MULTI-MOTOR   |     | DETERMINÍSTICO |     | MULTI-TIER       |    |  MADUREZ       |
| - PyMuPDF /    |     | - 6 Reglas Core|     | - RAG Gobernado  |    | - Web-First    |
|   Tesseract OCR|     | - Conciliación |     | - 3 Tiers IA     |    |   con Permiso  |
| - Spatial      |     |   Geométrica   |     | - 9 Tareas       |    | - 5 Dimensiones|
|   Density      |     | - Decision     |     | - Trazabilidad & |    |   de Madurez   |
| - Grid Tables  |     |   Traces       |     |   Feedback HITL  |    | - Gatekeeper   |
| - YOLO / Templ.|     | - Rule Findings|     | - Cost / Latency |    | - Snapshots    |
+----------------+     +----------------+     +------------------+    +----------------+
         |                      |                       |                      |
         +----------------------+-----------------------+----------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|                                PERSISTENCIA Y VOLÚMENES                               |
|   - PostgreSQL 16 + PostGIS: Tablas relacionales, metadatos, trazas y RLS             |
|   - Redis 7: Colas de procesamiento asíncrono y control de tokens revocados           |
|   - Filesystem / Volúmenes Docker: /data/uploads/, /data/raster/, /storage/crops/     |
+---------------------------------------------------------------------------------------+
```

---

## 2. Inventario de Módulos del Sistema y Relaciones de Servicio

| Módulo de Servicio | Ubicación en Código | Responsabilidad Técnica Principal | Dependencias Clave |
| :--- | :--- | :--- | :--- |
| **Intake & Sources** | `backend/app/services/intake/` | Carga de archivos, normalización de metadatos, asignación de disciplina y extracción inicial. | `PyMuPDF`, `PostgreSQL`, `Storage` |
| **Rasterizer** | `backend/app/services/ingest/` | Renderizado de láminas PDF a PNG (150 DPI) con matriz de transformación escalada. | `fitz (PyMuPDF)`, `PIL` |
| **OCR Service** | `backend/app/services/ocr/` | Extracción de bloques de texto vectoriales nativos (`vector_pdf`) o raster (`tesseract`). | `PyMuPDF`, `Tesseract 5.5` |
| **Layout Service** | `backend/app/services/layout/` | Segmentación macro-espacial de láminas (dibujo, viñeta, notas, cuadros técnicos). | Heurísticas de densidad espacial |
| **Tables Service** | `backend/app/services/tables/` | Detección de rejillas ortogonales y parseo tabular de cuadros de vanos y especificaciones. | Análisis morfológico de líneas |
| **Symbols Service** | `backend/app/services/symbols/` | Detección de simbología arquitectónica, sanitaria y eléctrica con fallback de templates. | `YOLO SAHI`, `Template Memory` |
| **Rules Engine** | `backend/app/services/rules/` | Evaluación determinística de 6 reglas QA/QC y generación de `RuleFinding` y `DecisionTrace`. | Lógica determinística pura |
| **Knowledge Base** | `backend/app/services/knowledge/`| Catálogo de conocimiento estructurado en 13 dominios y 8 estados con chunking y versionamiento. | `KnowledgeItem`, `KnowledgeChunk` |
| **Assistant Engine** | `backend/app/services/assistant/`| Orquestación del Copilot con recuperación RAG gobernada, routing multi-tier y feedback HITL. | `AiEngineRouter`, `KnowledgeBaseService` |
| **Acquisition Svc** | `backend/app/services/acquisition/`| Detección de faltantes, búsqueda web con permiso, scoring matemático y captura visual del visor. | `KnowledgeBaseService`, `Google Search API` |
| **Maturity Service** | `backend/app/services/maturity/` | Evaluación de 5 dimensiones de suficiencia informacional, gaps críticos y rutas de adquisición. | `ProjectMaturityProfile`, `Completeness` |
| **Completeness Svc** | `backend/app/services/completeness/`| Matriz de entregables requeridos por etapa y control de bloqueos del Gatekeeper. | `ProjectDeliverableRequirement` |
| **Observations Svc** | `backend/app/services/observations/`| Gestión de observaciones, RFIs, ciclo de vida de cierre/reapertura y trazabilidad. | `AuditObservation`, `AuditObservationTrace` |
| **Reporting Svc** | `backend/app/services/reporting/` | Generación de previews en vivo y emisión de snapshots inmutables con hash SHA-256. | `ProjectStageReportSnapshot` |

---

## 3. Gobernanza de la Base de Conocimiento Operacional

La Base de Conocimiento Operacional actúa como la memoria técnica institucional del sistema y está sujeta a políticas estrictas de ciclo de vida:

### Dominios de Conocimiento Canónicos (13 Dominios)
1. `normative_knowledge`: Artículos, ordenanzas y normas técnicas oficiales.
2. `rule_knowledge`: Definiciones y lógicas de reglas de auditoría QA/QC.
3. `deliverable_knowledge`: Requisitos y matrices de entregables por etapa.
4. `guide_document_knowledge`: Manuales de diseño y guías corporativas.
5. `review_knowledge`: Criterios y precedentes de revisión técnica.
6. `observation_rfi_knowledge`: Historial de observaciones, RFIs y soluciones aceptadas.
7. `project_knowledge`: Antecedentes específicos de proyectos y memorias de cálculo.
8. `feedback_learning_knowledge`: Correcciones de auditor humano (falsos positivos, ajustes).
9. `symbol_knowledge`: Simbología gráfica normalizada con recortes visuales.
10. `template_knowledge`: Plantillas de viñetas, tablas y detalles típicos.
11. `lesson_knowledge`: Lecciones aprendidas aplicables a futuros proyectos.
12. `guide_knowledge`: Documentos guía y criterios metodológicos.
13. `web_research_knowledge`: Fragmentos técnicos adquiridos de la web previa validación humana.

### Estados del Ciclo de Vida del Conocimiento (8 Estados)
```
[draft / extracted] ---> [reviewed] ---> [validated] ---> [approved_for_reuse]
        |                    |                 |
        v                    v                 v
   [rejected]           [superseded]       [archived]
```

- **`draft`**: Creado manualmente o en edición. No reutilizable.
- **`extracted`**: Extraído automáticamente por OCR o búsqueda web. No reutilizable.
- **`reviewed`**: Verificado técnicamente, pendiente de aprobación formal.
- **`validated`**: Validado técnicamente por el auditor. Apto para RAG.
- **`approved_for_reuse`**: Estado canónico de máxima confianza. Reutilizable en cualquier proyecto de la organización.
- **`superseded`**: Reemplazado por una versión más reciente.
- **`archived`**: Retirado de uso activo por obsolescencia.
- **`rejected`**: Descartado por el revisor.

> **Regla de Oro de Recuperación RAG:** El motor RAG **solo recupera** ítems en estado `approved_for_reuse` o `validated` con la bandera `is_active_for_reuse = True`. Todo ítem en estado borrador, extraído o rechazado queda completamente excluido de las respuestas del asistente.

---

## 4. Asistente Operacional, RAG Activo y Catálogo de Tareas

El Asistente Operacional opera mediante el servicio `AssistantService` (`backend/app/services/assistant/service.py`) e implementa un pipeline de 4 pasos por cada interacción:

1. **Recuperación Contextual RAG Gobernada:** Ejecuta una búsqueda filtrada por `organization_id`, `project_id`, `discipline` y `stage`, restringida a ítems activos y validados. Si el proyecto cuenta con un perfil de madurez, inyecta el score y los gaps críticos en el contexto.
2. **Evaluación de Routing y Escalamiento:** Determina el tier inicial de procesamiento según la tarea y evalúa si corresponde escalar de tier.
3. **Ejecución de Inferencia:** Genera la respuesta técnica, salida estructurada y cálculo de costos/latencia.
4. **Persistencia Trazable y Ciclo de Feedback HITL:** Registra la interacción en la tabla `assistant_interactions` vinculando los IDs de los fragmentos recuperados (`retrieved_knowledge_ids`), el tier ejecutado y el estado de feedback (`pending`, `accepted`, `edited`, `rejected`).

### Catálogo de 9 Tareas Asistidas

| Tarea Asistida | ID de Tarea | Tier Base | Motor Predeterminado | Triggers de Escalamiento |
| :--- | :--- | :---: | :--- | :--- |
| **Clarificación de Símbolos** | `symbol_clarification` | 1 | `fastapi_rule_reasoner` | Símbolo sin leyenda asociada o discrepancia crítica en plano. |
| **Consulta Normativa** | `normative_query` | 1 | `fastapi_rule_reasoner` | Ambigüedad normativa o score RAG interno < 0.40. |
| **Sugerencia de Reglas QA/QC** | `rule_suggestion` | 2 | `google_gemini_flash` | Reglas complejas multidisciplinares. |
| **Asistencia de Completitud** | `completeness_assistance`| 1 | `fastapi_rule_reasoner` | Bloqueos críticos de Gatekeeper sin evidencia. |
| **Clasificación de Entregables**| `document_classification`| 1 | `fastapi_rule_reasoner` | Documento atípico o sin metadatos claros. |
| **Apoyo a Revisión Técnica** | `review_support` | 2 | `google_gemini_flash` | Veredictos contradictorios o hallazgos de alto impacto. |
| **Borrador de Observación/RFI** | `observation_rfi_draft` | 2 | `google_gemini_flash` | Severidad Crítica o Bloqueo Documental (Escala a Tier 3). |
| **Explicación de Hallazgos** | `finding_explanation` | 1 | `fastapi_rule_reasoner` | Hallazgo Crítico o de Alta Severidad (Escala a Tier 2/3). |
| **Síntesis de Corte de Etapa** | `stage_synthesis` | 2 | `google_gemini_flash` | Veredicto global No Aprobable o Bloqueado (Escala a Tier 3). |

---

## 5. Estrategia de Routing de Motores IA Multi-Tier

El `AiEngineRouter` (`backend/app/services/assistant/router.py`) gestiona tres niveles de inferencia:

```
                     [Petición de Usuario + RAG Context]
                                      |
                                      v
                        ¿Tarea asignada a Tier 1 o 2?
                                      |
              +-----------------------+-----------------------+
              |                                               |
              v                                               v
    [Tier 1: Local Heuristic]                       [Tier 2: Gemini 2.0 Flash]
    - Gratis (0.00 USD)                             - Rápido & Multimodal (0.00015 USD)
    - Latencia < 15 ms                              - Latencia ~ 320 ms
    - Reglas & Deducción determinística             - Redacción técnica y RAG balanceado
              |                                               |
              +-----------------------+-----------------------+
                                      |
                       ¿Se activa Trigger Crítico?
          (Severidad Crítica / Bloqueo Gatekeeper / Score RAG < 0.40)
                                      |
                                      v
                          [Tier 3: OpenAI GPT-4o]
                          - Alta Exigencia (0.0050 USD)
                          - Latencia ~ 880 ms
                          - Resolución de conflictos mayores
```

### Triggers Determinísticos de Escalamiento
- **Escalamiento a Tier 3:**
  - Severidad del contexto = `CRITICAL` o `is_critical = True`.
  - Tipo de ítem = `document_blocker` o `is_blocker = True`.
  - Veredicto de etapa = `no_aprobable_bloqueada` en tareas de síntesis ejecutiva.
- **Escalamiento a Tier 2 (desde Tier 1):**
  - Consultas normativas o explicaciones técnicas donde el score de relevancia RAG interno es < 0.40 o existen 0 coincidencias.

---

## 6. Política de Adquisición de Información (Web-First con Permiso)

El servicio `InformationAcquisitionService` (`backend/app/services/acquisition/service.py`) regula la adquisición de información faltante:

### 1. Detección de Faltantes y Consulta RAG Interna
- El sistema evalúa si la consulta técnica puede resolverse internamente en la Base de Conocimiento aprobada.
- Si el score de relevancia es `>= 0.60`, la consulta se declara resuelta internamente.
- Si el score es `< 0.60` o no hay resultados, se crea un registro `InformationAcquisitionRequest` con estado `pending_permission`.

### 2. Permiso Explícito del Usuario y Límites de Seguridad
- El sistema **nunca busca en la web de forma automática**. Presenta un diálogo de autorización al usuario.
- **Límites de Ejecución:** Máximo 3 iteraciones de búsqueda y hasta 5 fuentes calificadas por consulta.
- Si el usuario rechaza: La solicitud se cierra con `termination_reason = 'cancelled_by_user'`.

### 3. Evaluación Matemática de Suficiencia
Para los resultados obtenidos, el sistema calcula de forma determinística:

$$\text{Relevance Score} = \min\left(1.0, \frac{\text{Hits de palabras clave}}{\text{Total esperado}} \times 0.70 + 0.30\right)$$

$$\text{Confidence Score} = \frac{1}{N} \sum_{i=1}^N \text{Credibilidad de la fuente}_i$$

$$\text{Coverage Score} = \min\left(1.0, \frac{\text{Aspectos normativos cubiertos}}{6} + 0.25\right)$$

$$\text{Overall Adequacy Score} = (0.40 \times \text{Relevance}) + (0.30 \times \text{Confidence}) + (0.30 \times \text{Coverage})$$

- **`Sufficient` ($\ge 75\%$ y Cobertura $\ge 70\%$):** Se almacena como `KnowledgeItem` en estado `extracted` para revisión del usuario.
- **`Partially Sufficient` ($50\% \text{ a } 74\%$):** Se marca como parcial y requiere validación puntual.
- **`Insufficient` ($< 50\%$ o necesidad privada de proyecto):** El sistema **escala automáticamente a una Solicitud Documental de Proyecto**, indicando el documento específico requerido (ej. *Memoria de Cálculo de Fundaciones*) y el responsable sugerido.

---

## 7. Visor como Fuente de Conocimiento Visual y Deduplicación

El Visor de Planos interactúa con el backend para transformar recortes gráficos en conocimiento reutilizable:

```
[Selección en Visor] ---> [Recorte Base64] ---> [Check Deduplicación Visual]
                                                       |
         +---------------------------------------------+---------------------------------------------+
         |                                             |                                             |
         v                                             v                                             v
[Coincidencia >= 85%]                         [Coincidencia 70-84%]                         [Sin Coincidencia (<70%)]
-> Sugiere: link_occurrence                   -> Sugiere: new_version                       -> Modo: create_new
-> Vincula lámina al ítem existente          -> Crea versión v2 del ítem                   -> Crea nuevo KnowledgeItem
-> Incrementa contador de ocurrencias         -> Hereda categoría y metadatos              -> Estado: approved_for_reuse
```

- **Almacenamiento Físico:** Los recortes se guardan en el volumen `./storage/crops/{document_id}/{sheet_id}/{hash}.png`.
- **Deduplicación Heurística:** Compara slugs canónicos (`_normalize_category_slug`), similitud de títulos con `difflib.SequenceMatcher` y correspondencia de alias.

---

## 8. Perfil de Madurez y Suficiencia Informacional por Proyecto

El `ProjectMaturityService` (`backend/app/services/maturity/service.py`) evalúa 5 dimensiones ponderadas:

| Dimensión Evaluada | Peso | Factores de Medición |
| :--- | :---: | :--- |
| **1. Documental & Planos** | 25% | Cantidad de láminas rasterizadas, memorias de cálculo, especificaciones y estado de evidencia. |
| **2. Completitud & Gatekeeper**| 25% | Cumplimiento de entregables obligatorios por etapa y estado del Gatekeeper (0 bloqueos). |
| **3. Normativa & Criterios** | 20% | Fuentes normativas asociadas, criterios aprobados y cobertura de reglas QA/QC activas. |
| **4. Base de Conocimiento** | 15% | Ítems de conocimiento validados (`approved_for_reuse`) vs borradores no validados. |
| **5. Observaciones & RFIs** | 15% | Tasa de resolución y cierre de observaciones técnicas y RFIs generados. |

### Niveles de Madurez
- **`initial` ($< 35\%$):** Proyecto con antecedentes mínimos, etapa bloqueada.
- **`basic` ($35\% \text{ a } 54\%$):** Documentación parcial, faltan entregables obligatorios.
- **`intermediate` ($55\% \text{ a } 74\%$):** Etapa en revisión, requiere cerrar observaciones abiertas.
- **`advanced` ($75\% \text{ a } 89\%$):** Suficiencia alta, apto para pre-emisión de snapshot.
- **`optimal` ($\ge 90\%$):** Cobertura completa, sin bloqueos de Gatekeeper y 100% de reglas validadas.

---

## 9. Flujo de Revisión por Etapas, Veredictos y Snapshots

### Matriz de los 4 Veredictos QA/QC Canónicos
1. **`Cumple Totalmente`:** La entidad o lámina cumple rigurosamente con la regla y los cuadros de especificaciones.
2. **`Cumple con Observaciones Menores`:** Discrepancias no críticas (ej. falta de texto aclaratorio en nota secundaria) que no impiden la aprobación.
3. **`No Cumple - Requiere Subsanación`:** Incumplimiento normativo o discrepancia geométrica crítica que genera un `RuleFinding` y bloquea la aprobación.
4. **`No Aplica`:** La regla no corresponde a la tipología o disciplina de la lámina actual.

### Snapshots de Etapa Inmutables
- Endpoint: `POST /api/v1/consolidated-reports/emit`.
- Congela el estado consolidado de la auditoría en un registro `ProjectStageReportSnapshot`.
- Genera un hash criptográfico de manifiesto (**SHA-256**) que garantiza que el reporte emitido no pueda ser alterado retroactivamente.
- Permite comparar versiones sucesivas mediante el análisis **Delta Evolution** (observaciones resueltas vs persistentes vs reabiertas).

---

## 10. Matriz de Estado Real de Implementación y Diagnóstico Técnico

| Módulo / Funcionalidad | Estado Real | Nivel de Estabilidad | Notas y Límites Operativos |
| :--- | :---: | :---: | :--- |
| **Autenticación JWT & Multi-Tenant** | `VALIDADO` | Alta | Login con RBAC y persistencia en PostgreSQL con RLS. |
| **Intake de Fuentes & Planos** | `VALIDADO` | Alta | Carga de archivos, clasificación de disciplinas y almacenamiento. |
| **Rasterizado PyMuPDF (150 DPI)** | `VALIDADO` | Alta | Renderizado de láminas PDF a PNG en `./data/raster/`. |
| **Visor de Planos Multicapa** | `VALIDADO` | Alta | Zoom, pan, overlays SVG de 5 capas y selector de recortes. |
| **Extracción OCR (VectorPDF + Tesseract)**| `VALIDADO` | Alta | Extracción en milisegundos con coordenadas normalizadas (0..1). |
| **Segmentación de Layout & Tablas** | `VALIDADO` | Alta | Detección de viñetas, notas y celdas ortogonales. |
| **Detección de Símbolos** | `PARCIAL / FALLBACK`| Media | Opera con `Template Matching` local ante la ausencia de pesos `yolo_symbols.pt`. |
| **Motor de Reglas QA/QC Determinístico** | `VALIDADO` | Alta | 6 reglas matemáticas determinísticas con trazas y severidad. |
| **Triage Humano (HITL)** | `VALIDADO` | Alta | Transiciones `accepted`, `rejected_false_positive` y ajuste geométrico. |
| **Base de Conocimiento Operacional** | `VALIDADO` | Alta | CRUD, 13 dominios, 8 estados, chunking y trazabilidad de procedencia. |
| **Asistente Operacional RAG** | `VALIDADO` | Alta | Recuperación contextual gobernada con exclusión de no validados. |
| **Routing Multi-Tier de Motores IA** | `VALIDADO` | Alta | Tier 1 local activo; Tiers 2/3 listos para credenciales en la nube. |
| **Adquisición Web con Permiso & Scoring** | `VALIDADO` | Alta | Flujo de autorización, fórmulas de adecuación y escalamiento documental. |
| **Captura Visual & Deduplicación** | `VALIDADO` | Alta | Guardado en disco, linking de ocurrencias y versionamiento. |
| **Perfil de Madurez Informacional** | `VALIDADO` | Alta | 5 dimensiones, cálculo delta y rutas de adquisición. |
| **Gatekeeper & Completitud** | `VALIDADO` | Alta | Matriz de entregables y bloqueos de etapa. |
| **Snapshots & Reportes Consolidados** | `VALIDADO` | Alta | Preview en vivo, cálculo de veredicto global y emisión con hash SHA-256. |
| **Scorecard & Golden Dataset Masivo** | `PENDIENTE DE VALIDACIÓN` | Media | Esquemas listos; pendiente ejecución con lote de 100 planos industriales. |

---

## 11. Guía Rápida de Despliegue y Verificación de Servicios

### Requisitos de Infraestructura
- **Docker Engine:** v24.0+ y **Docker Compose:** v2.20+
- **Python:** 3.11+
- **Node.js:** 20.x LTS

### Comandos de Arranque y Verificación
```bash
# 1. Iniciar servicios de base de datos, backend y frontend
docker-compose up -d

# 2. Verificar estado de los contenedores
docker-compose ps

# 3. Ejecutar migraciones de base de datos
docker-compose exec api alembic upgrade head

# 4. Ejecutar suite de pruebas de integración
docker-compose exec api pytest tests/ -v
```

### URLs de Acceso Local
- **Frontend SPA:** `http://localhost:5173`
- **API Swagger Docs:** `http://localhost:8000/docs`
- **Healthcheck General:** `http://localhost:8000/api/v1/health`

---

## 12. Compuertas de Calidad Obligatorias (CI/CD Gates)

Para asegurar la estabilidad estructural y funcional antes de integrar o desplegar cambios:
1. `cd frontend && npm run test:smoke` (Verificación estática y resolución JSX)
2. `cd frontend && npm run build` (Compilación estricta y empaquetado)
3. `cd backend && pytest tests/integration/ -v --disable-warnings` (Pruebas de integración y journey E2E)

---

## 13. Checklist de Preproducción y Riesgos Residuales

### Checklist de Despliegue
- [ ] PostgreSQL 16 con PostGIS y extensiones espaciales.
- [ ] Migraciones Alembic aplicadas (`alembic upgrade head`).
- [ ] Redis y workers Celery configurados con memoria adecuada.
- [ ] Almacenamiento persistente montado en `./storage/`.
- [ ] API keys de proveedores LLM activas y con cuotas configuradas.
- [ ] Carga de proyecto piloto con planos de prueba reales.

### Riesgos Residuales de Preproducción
- Comprobación de rendimiento de consultas espaciales en PostGIS bajo concurrencia.
- Consumo de memoria en rasterizado de PDFs vectoriales grandes (>100MB).
- Monitoreo de latencia y rate limits en LLMs externos.

