# Plan Review AI Hybrid

Plataforma de grado de ingeniería para la revisión, auditoría y control de calidad (QA/QC) de planos técnicos y documentos PDF de arquitectura e ingeniería.

- **Fase 3 (Identidad, Organizaciones, RBAC y Aislamiento Multi-Tenant)**:
  - **Identidad & Criptografía**: Hashing robusto con Argon2id por defecto y fallback PBKDF2-HMAC-SHA256 (600.000 iteraciones, salt 32 bytes, rehash automático). Tokens JWT con claims mínimas (`sub`, `email`, `exp`, `iat`, `iss`, `jti`), validez corta (30 min) y lista de revocación en memoria.
  - **Organizaciones & Membresías RBAC**: Modelo multi-tenant desacoplado con roles jerárquicos: `admin`, `audit_lead`, `reviewer`, `contributor`, `viewer`.
  - **Validación Estricta de Contexto**: Header `X-Organization-Id` tratado exclusivamente como selector de contexto, validado dinámicamente contra membresías activas. Retorno de `404 Not Found` ante recursos de otros tenants y `403 Forbidden` ante operaciones no autorizadas por rol.
  - **Defensa en Profundidad (PostgreSQL RLS)**: Script declarativo `migrations/rls_prepared_policies.sql` con políticas de seguridad por fila vinculadas a variable de sesión `app.current_organization_id`.
  - **Control de Concurrencia & Locks Huérfanos**: Detección de ejecuciones concurrentes por `(organization_id, scope_type, scope_id)` con respuesta `409 Conflict` y expiración automática de locks huérfanos tras 30 minutos de inactividad.
### Matriz de Permisos RBAC
| Rol | Alcance | Ver Datos | Ingesta / Subida | Ejecutar Pipeline | Resolver Hallazgos Críticos | Descargar PDF/JSON | Descargar Bundle ZIP | Administrar Miembros |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **admin** | Toda la Organización | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **audit_lead** | Proyectos asignados | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| **reviewer** | Auditoría & QA/QC | ✅ | ❌ | ❌ | ✅ (no críticos) | ✅ | ✅ | ❌ |
| **contributor** | Carga y verificación | ✅ | ✅ | ✅ (propios) | ❌ | ✅ | ❌ (`403`) | ❌ |
| **viewer** | Solo lectura | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ (`403`) | ❌ |

---

## Arquitectura del Pipeline One-Click Review

```text
  [ Cliente / SPA ]
         │
         │  1. POST /api/v1/pipelines/documents/{id}/run
         ▼
  [ FastAPI Router ]  ──►  2. Crea ReviewPipelineRun (status="queued", progress=0%)
         │                 3. Retorna HTTP 202 Accepted { pipeline_run_id, poll_url }
         │
         ▼
  [ JobDispatcher ]  ──►  4. Despacha ejecución en hilo aislado (SessionLocal)
         │
         ▼
  [ ReviewPipelineService ]  ──►  5. Ejecuta secuencialmente las 8 etapas con idempotencia:
         │
         ├───► Etapa 1: Ingesta (Verifica PDF, páginas y renders) ──────────► 10%
         ├───► Etapa 2: OCR Espacial (PaddleOCR / Tesseract / VectorPDF) ───► 25%
         ├───► Etapa 3: Layout Macro-Regional (5 macro-regiones) ───────────► 40%
         ├───► Etapa 4: Title Block Matching (Metadata de viñeta) ──────────► 55%
         ├───► Etapa 5: Extracción Tabular (Grillas y cuadros técnicos) ────► 70%
         ├───► Etapa 6: Detección de Símbolos (Puertas, ventanas, etc.) ────► 80%
         ├───► Etapa 7: Reglas QA/QC (Conciliación cruzada & hallazgos) ────► 90%
         └───► Etapa 8: Reportes & Bundle (PDF 1.4, JSON, ZIP + Manifest) ─► 100%
                                   │
                                   ▼
         6. Si hay hallazgos críticos abiertos ──► Estado: "awaiting_review"
         7. Si todo es conforme ────────────────► Estado: "completed"
```

---

## Convención de Coordenadas Normalizadas

Para garantizar desacoplamiento total de la resolución DPI y facilitar overlays responsivos en el frontend, todos los textos, regiones, celdas y símbolos utilizan la siguiente convención:
- **Origen $(0.0, 0.0)$**: Esquina superior izquierda de la lámina (*Top-Left*).
- **Extremo $(1.0, 1.0)$**: Esquina inferior derecha de la lámina (*Bottom-Right*).
- **Estructura de Caja**: $[x_0, y_0, x_1, y_1]$ donde $0.0 \le x_0 \le x_1 \le 1.0$ y $0.0 \le y_0 \le y_1 \le 1.0$.

---

## Estructura del Monorepo
```text
plan-review-ai-hybrid/
├── backend/            # API FastAPI, repositorios SQLAlchemy, modelos ORM y servicios
│   ├── app/
│   │   ├── services/
│   │   │   ├── operations/ # Orquestador ReviewPipelineService, dispatcher de jobs y revisión HITL
│   │   │   ├── reporting/  # Renderizador PDF, exportador JSON, empaquetador ZIP y orquestador
│   │   │   ├── rules/      # Motor RuleEngine, BaseRule, contratos y reglas baseline
│   │   │   ├── symbols/    # Motor de detección visual (YOLO/SAHI/Geometría) y servicio de símbolos
│   │   │   ├── tables/     # Extractor espacial de grillas, clasificador y servicio tabular
│   │   │   ├── intake/     # Registro, gobierno y ruteo a memorias (SourceAsset)
│   │   │   ├── ingest/     # Ingesta PDF y rasterizado (PyMuPDF)
│   │   │   ├── ocr/        # Motor de OCR espacial (PaddleOCR, Tesseract, VectorPDF)
│   │   │   └── layout/     # Segmentación macro-regional y title block matcher
├── frontend/           # SPA React 18 + Vite + TypeScript + Visor multicapa + Pipeline One-Click
├── knowledge/          # Estándares, normativas (OGUC/NFPA), ontologías y plantillas semilla
├── memory/             # Documentación y esquemas declarativos de las 4 memorias
├── rules/              # Motor de reglas determinísticas por disciplina (QA/QC, arquitectura, eléctrica)
├── data/               # Almacenamiento local de desarrollo (PDFs raw, renders, thumbnails, intake, reports)
├── migrations/         # Migraciones Alembic (0001 a 0010)
├── shared/             # Contratos geométricos y eventos de mensajería compartidos
├── scripts/            # Utilidades CLI (seeder de conocimiento, utilitarios)
└── docker-compose.yml  # Orquestación multicontenedor (DB, Redis, Backend, Frontend)
```

---

---

## Pruebas de Integración y Validación Real de PostgreSQL Row-Level Security (RLS)

El proyecto cuenta con dos niveles diferenciados de pruebas:
1. **Tests Unitarios Rápidos en Memoria (SQLite)**: Validan la lógica de negocio, schemas Pydantic, endpoints FastAPI, idempotencia del pipeline y RBAC a nivel de servicio. Se ejecutan con `pytest -m "not postgres"`.
2. **Suite de Integración Real contra PostgreSQL 15+ (`test_postgres_rls.py`)**: Valida que las políticas de seguridad a nivel de fila (`ENABLE ROW LEVEL SECURITY` y `FORCE ROW LEVEL SECURITY`) aíslen efectivamente a nivel de motor de BD utilizando el rol no privilegiado `app_user` (`NOBYPASSRLS`).

### Roles de Base de Datos
- **`postgres_migrator` (Rol Privilegiado / Owner)**: Utilizado exclusivamente para ejecutar migraciones Alembic, `CREATE TABLE`, `ALTER TABLE ... ENABLE/FORCE ROW LEVEL SECURITY`, `CREATE POLICY` y otorgar permisos.
- **`app_user` (Rol de Aplicación / Runtime)**: Cuenta con permisos limitados `SELECT, INSERT, UPDATE, DELETE` y está configurado estrictamente con `NOBYPASSRLS, NOSUPERUSER, NOCREATEDB, NOCREATEROLE`.

### Comandos de Ejecución de la Suite PostgreSQL RLS
```bash
# 1. Levantar contenedor PostgreSQL de integración aislado (puerto 5433)
docker compose -f docker-compose.integration.yml up -d

# 2. Configurar tablas, aplicar políticas RLS y verificar app_user
python scripts/setup_postgres_rls.py

# 3. Ejecutar la suite de integración RLS
pytest backend/tests/integration/test_postgres_rls.py -v -m postgres
```

### Matriz de Tablas y Políticas RLS Aplicadas
| Tipo de Tabla | Tablas Protegidas | Estrategia de Filtrado RLS | Política |
| :--- | :--- | :--- | :--- |
| **Directas** | `projects`, `source_assets`, `documents`, `processing_jobs`, `review_pipeline_runs`, `review_tasks`, `decision_traces`, `review_runs`, `rule_findings`, `audit_reports`, `evidence_manifests`, `audit_logs` | `organization_id = get_current_organization_id()` | `USING + WITH CHECK` (`FORCE RLS`) |
| **Heredadas (JOIN Document)** | `document_sheets`, `sheet_regions`, `extracted_texts`, `title_block_extractions`, `extracted_tables`, `detected_symbols`, `visual_evidences`, `rule_executions` | `document_id IN (SELECT id FROM documents WHERE organization_id = ...)` | `USING + WITH CHECK` (`FORCE RLS`) |
| **Heredadas (JOIN Celda)** | `extracted_table_cells` | `table_id IN (SELECT t.id FROM extracted_tables t JOIN document_sheets s ...)` | `USING + WITH CHECK` (`FORCE RLS`) |
| **Heredadas (JOIN Pipeline/Finding)** | `pipeline_stage_runs`, `finding_resolutions`, `finding_evidences` | `pipeline_run_id` / `finding_id` en subquery del tenant | `USING + WITH CHECK` (`FORCE RLS`) |

### Comportamiento Fail-Closed ante Ausencia de Contexto
Si una consulta se ejecuta con el rol `app_user` sin invocar previamente `SELECT set_config('app.current_organization_id', :org_id, true)`, la función `get_current_organization_id()` retorna `NULL`, lo que hace que todas las políticas evalúen a falso y retornen estrictamente **0 filas** (nunca revelando registros de ningún tenant).

---

---

## Fase 3 – Línea 2: Golden Dataset, Evaluación de Calidad y Calibración de Confianza

La capa de evaluación formal permite medir la precisión y robustez del sistema de auditoría antes de entrenar modelos nuevos o realizar fine-tuning.

### 1. Taxonomía de Datasets de Producto vs. Splits Experimentales
- **Datasets de Producto (Propósito Operativo)**:
  - `golden`: Conjunto curado de referencia institucional y máxima confianza.
  - `regression`: Suite de control para prevenir degradación de calidad ante cambios de código o reglas.
  - `benchmark`: Dataset para comparación histórica y evolución de versiones de pipeline.
  - `pilot`: Conjunto de prueba acotado para nuevos dominios o clientes.
- **Splits Experimentales (Sin Contaminar Entrenamiento)**:
  - `test`: Muestras oficiales para evaluación de calidad y cálculo de métricas estándar.
  - `holdout`: Muestras retenidas a ciegas para validación final sin sesgo de sobreajuste.
  - `validation`: Muestras para calibración de umbrales e hiperparámetros.
- **Política Estricta para Datasets Globales (`organization_id = NULL`)**:
  - Los datasets de sistema compartidos restringen estrictamente su política de origen a `synthetic`, `anonymized` o `internal` institucionalmente aprobados. No se permite la carga de datos crudos de clientes (`consented`) en el catálogo global.

### 2. Trazabilidad y Parámetros Exactos de Reproducibilidad
Cada registro de `EvaluationRun` persiste de forma obligatoria e inmutable:
- `git_commit_hash`: Commit exacto del repositorio en ejecución.
- `ocr_raster_config`: Configuración de rasterizado y OCR (`dpi`, `engine`, `binarization`).
- `inference_thresholds`: Umbrales de inferencia visual (`symbol_confidence`, `uncertainty_max`, `iou_threshold`).
- `prompts_and_rules_config`: Reglas normativas activas y prompts auxiliares si aplican.
- `snapshot_manifest_hash`: Hash SHA-256 generado al congelar el dataset (`freeze`), garantizando que las anotaciones aprobadas sean inmutables.

### 3. Workflow de Anotación Ground Truth y Adjudicación
```text
[draft] -> [submitted] -> [reviewed] -> [approved] (Ground Truth Oficial)
                                           |
                                           v
                             [superseded] (Si se aprueba una nueva versión)
```
- Únicamente las anotaciones en estado `approved` son tomadas como Ground Truth.
- Si dos anotadores discrepan, la adjudicación de una nueva versión marca automáticamente la versión previa como `superseded`.

### 4. Separación de Evaluación Perceptual vs. Decisional
- **Evaluación Perceptual**:
  - **OCR**: Character Error Rate (CER), Word Error Rate (WER), F1 en textos críticos, BBox MAE.
  - **Layout**: IoU por macro-región y Mean IoU (mIoU).
  - **Title Block**: Exact match ratio, precisión normalizada, completitud de campos requeridos.
  - **Tablas**: IoU de detección, exactitud de celdas, exactitud de encabezados y unidades.
  - **Símbolos**: Precisión, Recall, F1 por clase (desglose por `class_name`), Error Absoluto de Conteo (MAE) y mAP@0.5:0.95 cuando hay cajas delimitadoras.
- **Evaluación Decisional**:
  - **Reglas QA/QC**: Matriz de Confusión (True Positive, False Positive, False Negative, True Negative), FPR, FNR, exactitud de clasificación de severidad.
  - **HITL (Calibración Humana)**: Tasa de confirmación, tasa de descarte (dismissed), tasa de riesgo aceptado y tasa de desacuerdo regla vs. auditor.

### 5. Prerrequisito Obligatorio antes de SAHI / YOLO Fine-Tuning
> [!IMPORTANT]
> **Bloqueo Operativo**: No se iniciará el entrenamiento ni fine-tuning de modelos YOLO ni la integración de SAHI (Slicing Aided Hyper Inference) hasta ejecutar primero una corrida real suficiente sobre el Golden Dataset institucional y documentar formalmente las métricas baseline por componente y disciplina.

---

## Limitaciones Reales de la Implementación Actual
1. **Revocación JWT en Memoria**: La lista de `_REVOKED_JTIS` reside actualmente en la memoria de proceso del worker de desarrollo. Para despliegues multi-nodo productivos debe conectarse al servicio Redis.
2. **Alcance Organizacional sin `ProjectMembership`**: Los roles RBAC están asignados a nivel de Organización (`OrganizationMembership`). La asignación granular por proyecto está planificada para la siguiente iteración.
3. **Locks de Pipeline en BD Local**: El control de concurrencia y detección de locks huérfanos opera mediante consultas sobre `review_pipeline_runs`. En un clúster de alta concurrencia se recomienda implementar distributed locking con Redis Redlock.
4. **Editor Gráfico de Anotaciones**: La carga y modificación de anotaciones Ground Truth se realiza actualmente mediante importación y validación de payloads JSON estructurados; un editor interactivo sobre canvas de plano está proyectado para fases futuras.



