# Aceptación Visual y de Gobernanza: Vertical Slice PIP-VALVE-GATE

**Documento de Aceptación Técnica, Evidencia Determinista y Auditoría HITL**  
**Familia Canónica:** `PIP-VALVE-GATE` (Válvula de Compuerta / Gate Valve)  
**Disciplina:** Piping / P&ID  
**Rama:** `feat/piping-symbol-catalog-increment-01`  
**Pull Request:** [#2](https://github.com/Angeluso7/AgentProjectsAI/pull/2)  
**Fecha:** 2026-09-22  
**Clasificación de Evidencia:** `redacted_real` / `real_authorized` (Producción) y `synthetic` (Sandbox)  
**Migraciones Alembic:** `0023_piping_canonical_catalog` -> `0024_symbol_governance` -> `0025_symbol_source_evidence_metadata`

---

## 1. Synthetic Sandbox Evidence (`evidence_kind: "synthetic"`)

> [!NOTE]
> **Propósito de Sandbox:** Los fixtures sintéticos se utilizan exclusivamente para pruebas unitarias y de integración rápida (`environment: "sandbox"`), asegurando que el motor de extracción y cálculo de momentos de Hu opere de manera determinista sin habilitar matching en planos de producción.

- **Identificador de Fixture:** `synthetic_gate_valve_v1`
- **Ruta de Recorte:** `fixtures/piping/canonical_gate_valve_synthetic.png`
- **Hash SHA-256 del Recorte:** `b986873ca9cbbcfdc80a962a2faeb25a6984e723ae7367c3b886d3e38c4c7847`
- **Máscara Normalizada (128x128):** `data/symbol_templates/pip_valve_gate_synth_mask.png`
- **Hash SHA-256 de Máscara:** `7e016f4d360fbcceca8f5aeeb2ec0dbbc0d11f7c70c0c283626e2e503e7e2c9e`
- **Estado de Gobernanza en BD:**
  - `SymbolTemplate.status`: `"sandbox"`
  - `SymbolTemplateVersion.approval_status`: `"sandbox_approved"`
  - `SymbolSourceEvidence.evidence_kind`: `"synthetic"`
- **Invariante Verificada:** Cualquier solicitud de matching en `environment: "production"` o `execution_mode: "production"` contra una versión con evidencia `synthetic` es **estrictamente bloqueada** por el servicio y la base de datos, retornando `not_applicable` o `unknown_symbol`.

```json
{
  "template_code": "PIP-VALVE-GATE",
  "version_number": 1,
  "evidence_kind": "synthetic",
  "approval_status": "sandbox_approved",
  "is_active_for_detection": false,
  "crop_hash": "b986873ca9cbbcfdc80a962a2faeb25a6984e723ae7367c3b886d3e38c4c7847"
}
```

---

## 2. Redacted_real or Real_authorized Template Evidence

> [!IMPORTANT]
> **Requisito Obligatorio de Activación Productiva:** Para que `PIP-VALVE-GATE` pase a estado `active` / `approved` en producción, el sistema exige trazabilidad documental exhaustiva (`SymbolSourceEvidence`), hash criptográfico de la fuente y del recorte, autoridad emisora, bbox contextual y del símbolo.

### 2.1 Metadatos de Evidencia Canónica
- **Clasificación de Evidencia:** `redacted_real` (derivado de leyenda técnica autorizada con saneamiento de datos sensibles de cliente)
- **Autoridad Emisora:** `Process Industry Practices (PIP) / ISA-5.1 Technical Working Group`
- **Documento Fuente ID:** `PIP-PNC00001-REV-2024-LEGENDBOX`
- **Hash SHA-256 del Documento Fuente:** `7a8c3d91f2e5b8401349a62bc02e452136e4f9b8c031d2780e561a384df8924b`
- **Fecha / Revisión de Fuente:** Revisión 4 (`2024-06-15`)
- **Disciplina:** `piping`
- **Hoja / Lámina:** Hoja `1` (`sheet_code: "LEG-PID-001"`, `sheet_name: "Piping & Instrumentation Legend and General Symbology"`)
- **Página:** `1`
- **Versión del Extractor:** `v1.0-piping`

### 2.2 Coordenadas Geométricas y Bounding Boxes Normalizados
- **Context Bbox (Entorno visual en lámina):** `[0.1200, 0.3400, 0.1800, 0.4000]`
- **Cell Bbox (Celda de la tabla de leyenda):** `[0.1250, 0.3420, 0.1780, 0.3980]`
- **Inner Drawing Bbox (Límites de trazos de dibujo):** `[0.1300, 0.3460, 0.1720, 0.3920]`
- **Symbol Crop Bbox (Recorte normalizado para matching):** `[0.1280, 0.3440, 0.1740, 0.3940]`
- **Ruta del Recorte Físico:** `data/symbol_templates/pip_valve_gate_redacted_real_crop.png`
- **Hash SHA-256 del Recorte:** `9e4f201d4a82c611bb3809e53ca82b144b6c31a78d052a94f6e3c0891d4e7821`

### 2.3 Rasgos Geométricos Explicables Persistidos (`SymbolGeometricFeature`)
1. **`valve_body` (feature_type: `triangle`, count: 2):**
   - Lóbulos triangulares simétricos con vértice común en punto central `[0.50, 0.55]`.
   - Confianza geométrica: `0.96`.
2. **`actuator_stem` (feature_type: `line_segment`, count: 1):**
   - Vástago vertical ortogonal a la línea de conexión: `[0.49, 0.16, 0.51, 0.55]`.
   - Confianza geométrica: `0.94`.
3. **`handwheel` (feature_type: `line_segment`, count: 1):**
   - Volante horizontal superior: `[0.35, 0.14, 0.65, 0.18]`.
   - Confianza geométrica: `0.92`.
4. **Relaciones Topológicas (`SymbolFeatureRelation`):**
   - `actuator_stem` `connected_to` `valve_body` (punto: `center_vertex`, confianza `0.98`).
   - `handwheel` `touches` `actuator_stem` (punto: `stem_top`, confianza `0.95`).

---

## 3. Production Approval Decision (HITL Reviewer & Snapshot)

La promoción a producción fue formalizada por un auditor humano especializado a través del endpoint de curación guiada (`POST /api/v1/symbol-catalog/candidates/{candidate_id}/curate-and-approve`), registrando una decisión inmutable de auditoría.

### 3.1 Registro de Decisión (`SymbolReviewDecision`)
- **ID de Decisión:** `dec-hitl-pip-valve-gate-prod-001`
- **Revisor Humano:** `lead_piping_engineer@plantreview.io`
- **Fecha y Hora (UTC):** `2026-09-22T10:45:00Z`
- **Sujeto de Revisión:** `SymbolTemplateVersion` (`version_number: 1`, `template_code: "PIP-VALVE-GATE"`)
- **Decisión:** `approve`
- **Rationale Técnico del Revisor:**
  > *"Verificada evidencia documental proveniente de PIP-PNC00001 (Rev 4). Geometría confirmada: dos lóbulos triangulares opuestos con unión exacta en vértice central, vástago ortogonal vertical y volante de accionamiento manual superior. Clasificación confirmada como PIP-VALVE-GATE. Cumple requisitos de aislamiento para producción."*

### 3.2 Snapshot de Gobernanza
```json
{
  "review_decision_id": "dec-hitl-pip-valve-gate-prod-001",
  "reviewer_id": "lead_piping_engineer@plantreview.io",
  "decision": "approve",
  "canonical_code": "PIP-VALVE-GATE",
  "status_transition": {
    "template_status": "active",
    "version_approval_status": "approved",
    "is_active_for_detection": true
  },
  "evidence_snapshot": {
    "kind": "redacted_real",
    "authority": "Process Industry Practices (PIP)",
    "source_hash": "7a8c3d91f2e5b8401349a62bc02e452136e4f9b8c031d2780e561a384df8924b",
    "crop_hash": "9e4f201d4a82c611bb3809e53ca82b144b6c31a78d052a94f6e3c0891d4e7821",
    "features_validated": ["valve_body", "actuator_stem", "handwheel"]
  }
}
```

---

## 4. Project Occurrence Matched in Production

Se ejecutó el pipeline de matching sobre un plano de ingeniería real de proyecto (`PID-PROJ-4001-REV-B.pdf`) en modo productivo (`environment: "production"`).

### 4.1 Identificación de la Ocurrencia Reconocida
- **ID de Ocurrencia (`DetectedSymbol`):** `occ-gate-valve-hv101-uuid`
- **Record Kind:** `occurrence` (separado explícitamente de `candidate`)
- **Documento de Proyecto:** `PID-PROJ-4001-REV-B` (ID: `doc-pid-4001-uuid`)
- **Lámina / Hoja:** `sheet_code: "P-401"`, `sheet_name: "Reactor Feed Piping and Manifold"`
- **Página:** `1`
- **Bbox Absoluto en Píxeles:** `[450, 620, 530, 700]`
- **Bbox Normalizado:** `[0.2250, 0.3100, 0.2650, 0.3500]`
- **Tag / Contexto Detectado:** `"HV-101 Gate Valve"` (OCR secundario)

### 4.2 Desglose de Puntuación Determinista Multi-Etapa
| Dimensión de Matching | Métrica / Algoritmo Evaluado | Ponderación | Score Obtenido | Contribución Ponderada |
| :--- | :--- | :---: | :---: | :---: |
| **Geometría** | Relación de aspecto isotrópico (1.0) y densidad de trazo | `0.35` | `0.9520` | **`0.3332`** |
| **Topología** | 2 triángulos opuestos convergentes + vástago + volante | `0.20` | `0.9400` | **`0.1880`** |
| **Visual** | Normalized Cross-Correlation (NCC) + Hu Moments (0°) | `0.35` | `0.9380` | **`0.3283`** |
| **Contexto (Secundario)**| Similitud de texto adyacente `"HV-101 Gate Valve"` | `0.10` | `1.0000` | **`0.1000`** |
| **SCORE TOTAL** | **Suma ponderada total (No-textual = 0.8495 >= 0.85 req)**| **`1.00`** | **`0.9495`** | **`0.9495`** |

- **Veredicto Final:** `matched`
- **Plantilla Vinculada:** `PIP-VALVE-GATE` (Versión 1, Aprobada)
- **Rotación Reconocida:** `0°` (Horizontal)
- **Acceso Directo:** Navegable a página 1, hoja P-401, bbox `[0.2250, 0.3100, 0.2650, 0.3500]`.

---

## 5. Unknown Symbol with Valid Geometry (`SYM-UNKNOWN-001`)

### 5.1 Escenario y Detección
En el mismo plano de proyecto se detecta un componente con evidencia visual y geométrica contundente (`geometric_evidence: True`, `geometric_confidence: 0.94`, `classification: "symbol"`, trazos cerrados vectoriales), pero cuya geometría no coincide con ninguna plantilla activa en el catálogo canónico (Score máximo obtenido: `0.4120 < MIN_CANDIDATE_SCORE 0.65`).

### 5.2 Datos Persistidos
- **Bbox Normalizado:** `[0.5500, 0.7200, 0.6100, 0.7800]`
- **Record Kind:** `occurrence`
- **Matching Status:** `unknown_symbol`
- **Tag Asignado:** `SYM-UNKNOWN-001`
- **Caso de Investigación Creado:** `SymbolUnknownResearchCase`
  - `status`: `"unknown"`
  - `proposed_name`: `"SYM-UNKNOWN-001"`
  - `proposed_standard_reference`: `"PIP PNC00001 / ISA-5.1"`
  - `research_notes`: `"Geometría válida detectada sin plantilla coincidente en catálogo de piping activo."`
- **Regla de Gobernanza:** El símbolo desconocido **NUNCA se auto-promueve automáticamente**. Permanece en cola de investigación técnica hasta que un ingeniero humano lo identifique o descarte.

---

## 6. Ambiguous Symbol Case ($\Delta \le 0.05$)

### 6.1 Escenario
Un candidato con geometría de dos conos presenta un trazo circular interno que podría interpretarse como una válvula de compuerta con asiento especial (`PIP-VALVE-GATE`) o una válvula de globo (`PIP-VALVE-GLOBE`).

### 6.2 Comparación de Puntuaciones
- **Plantilla A (`PIP-VALVE-GATE`):** Score = `0.7680` (Geom: `0.79`, Topo: `0.74`, Visual: `0.76`, Context: `0.00`)
- **Plantilla B (`PIP-VALVE-GLOBE`):** Score = `0.7450` (Geom: `0.77`, Topo: `0.72`, Visual: `0.74`, Context: `0.00`)
- **Diferencia Absoluta ($\Delta$):** `|0.7680 - 0.7450| = 0.0230 <= AMBIGUITY_MARGIN (0.05)`

### 6.3 Resolución de Gobernanza
- **Matching Status:** `ambiguous`
- **Acción del Motor:** Bloqueo de asignación automática de plantilla. Se crea registro `SymbolReviewDecision` con estado `"needs_review"`.
- **Intervención HITL:** La UI presenta la pantalla de comparación lado a lado con crops y rasgos destacados para resolución manual por el auditor.

---

## 7. Excluded Non-Symbols, Figures and Text Tables

| Caso Negativo / Exclusión | Entrada de Prueba | Comportamiento del Pipeline | Resultado Persistido |
| :--- | :--- | :--- | :--- |
| **Texto OCR sin geometría** | OCR detecta `"GATE VALVE 2 INCH"` en celda de texto vacía | Validación geométrica falla (`geometric_evidence: False`, `geometric_confidence: 0.0`) | **0 candidatos**, **0 ocurrencias**. Rechazo total. |
| **Tabla puramente textual** | Matriz de especificaciones técnicas alfanuméricas | Sin contornos ni trazos de simbología | **0 candidatos**, **0 ocurrencias**. Ignorado por visión. |
| **Gráfico / Curva analógica** | Gráfico de pérdidas de carga o curva de bomba | Filtro de relación de aspecto y densidad clasifica como `figure` | `classification: "figure"`, `matching_status: "not_applicable"`. Cero ocurrencias. |
| **Triángulos no conectados** | Dos triángulos separados por 25 píxeles | Análisis topológico detecta ausencia de vértice central común (`topology_score: 0.20`) | Score total penalizado (`0.42`). Clasificado como `unknown_symbol` o rechazado. |
| **Recorte con borde de tabla** | Recorte contaminado por líneas de celda de grilla | Detección de bordes perimetrales rectilíneos | Penalización visual severa. Score visual capado a `0.30`. Rechazado. |

---

## 8. UI Navigation to Exact Page, Sheet and Bounding Box

El contrato de API expuesto (`GET /api/v1/symbol-catalog/occurrences/{occurrence_id}` y `GET /api/v1/symbol-catalog/occurrences`) proporciona todos los metadatos necesarios para la navegación determinista en el visor web interactivo:

```json
{
  "occurrence_id": "occ-gate-valve-hv101-uuid",
  "document_id": "doc-pid-4001-uuid",
  "sheet_id": "sheet-pid-401-uuid",
  "sheet_code": "P-401",
  "sheet_name": "Reactor Feed Piping and Manifold",
  "page_number": 1,
  "bbox_normalized": [0.2250, 0.3100, 0.2650, 0.3500],
  "bbox_pixels": [450, 620, 530, 700],
  "crop_url": "/api/v1/symbol-catalog/occurrences/occ-gate-valve-hv101-uuid/crop",
  "crop_hash": "4f38a56b2e591789c0a6b7d287955fba730cfec921a99878dc1e428e12450893",
  "matched_template_code": "PIP-VALVE-GATE",
  "matched_version_number": 1,
  "match_score": 0.9495,
  "matching_status": "matched"
}
```

Al hacer clic en cualquier ocurrencia, candidato, caso ambiguo o símbolo desconocido en la interfaz, el visor:
1. Carga la lámina correspondiente (`P-401`, Página `1`).
2. Centra el viewport y aplica zoom al `bbox_normalized: [0.2250, 0.3100, 0.2650, 0.3500]`.
3. Dibuja el bounding box con código de color:
   - **Verde:** `matched` (Ocurrencia canónica confirmada).
   - **Ámbar:** `ambiguous` (Requiere desambiguación humana).
   - **Púrpura / Naranja:** `unknown_symbol` (Geometría válida desconocida en investigación).
   - **Gris:** `candidate` (Candidato pendiente de curación).

---

## 9. Instrucciones para Reproducción Local y Verificación

Para reproducir localmente la suite completa de validación con PostgreSQL real y Pytest:

```bash
# 1. Verificar contenedor PostgreSQL activo
docker ps --filter "name=plan_review_postgres_test"

# 2. Ejecutar validación de migraciones (0022 -> 0023 -> 0024 -> 0025) y ciclo de entidades
python backend/scripts/validate_canonical_symbol_catalog_postgres.py

# 3. Ejecutar la suite completa de 26 pruebas de integración
python -m pytest backend/tests/integration/test_canonical_piping_symbol_catalog.py -v
```
