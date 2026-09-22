# Aceptación Visual y de Gobernanza: Vertical Slice PIP-VALVE-GATE

**Documento de Aceptación Técnica y Evidencia Determinista**  
**Familia Canónica:** `PIP-VALVE-GATE` (Válvula de Compuerta / Gate Valve)  
**Disciplina:** Piping / P&ID  
**Rama:** `feat/piping-symbol-catalog-increment-01`  
**Pull Request:** [#2](https://github.com/Angeluso7/AgentProjectsAI/pull/2)  
**Fecha:** 2026-09-22  
**Clasificación de Evidencia Actual:** `synthetic` (Entorno Sandbox / Test Only)  

---

## 1. Declaración Formal de Gobernanza y Alcance

> [!IMPORTANT]
> **POLÍTICA DE EVIDENCIA Y ESTADOS (AUDITORÍA HITL):**  
> El vertical slice `PIP-VALVE-GATE` contenido en este incremento está respaldado **única y exclusivamente por un fixture canónico sintético controlado (`evidence_kind: "synthetic"`)**.  
> En cumplimiento estricto de la política de gobernanza del sistema:
> - La plantilla canónica está catalogada con estado **`status: "sandbox"`** y su versión inicial como **`approval_status: "sandbox_approved"`**.
> - **NO SE ACTIVA COMO PRODUCTIVA** (`status: "active"` / `approval_status: "approved"`).
> - Toda ejecución en modo de producción (`execution_mode: "production"`) ignora o rechaza matches contra esta plantilla, devolviendo `not_applicable` o `unknown_symbol`.
> - Solo en modo sandbox explícito (`execution_mode: "sandbox"`) o suites de pruebas está habilitado su matching.
> - **No se afirma falsamente la existencia de documentos reales autorizados**. La transición a productivo requerirá evidencia documental real (`real_authorized` o `redacted_real`) con hash, página, bbox normalizado y aprobación formal HITL.

---

## 2. Plantilla Canónica Curada (`PIP-VALVE-GATE`)

### 2.1 Identidad y Trazabilidad de Origen
- **Código Canónico:** `PIP-VALVE-GATE`
- **Nombre Canónico:** Gate Valve (Válvula de Compuerta)
- **Categoría / Subcategoría:** `valve` / `gate_valve`
- **Función Técnica:** Isolation or shutoff valve in piping networks
- **Referencia Normativa:** PIP PNC00001 / ISA-5.1 (Simbología común P&ID)
- **Clasificación de Evidencia:** `synthetic`
- **Fuente Documental:** `fixtures/piping/canonical_gate_valve_synthetic.png`
- **SHA-256 del Recorte Original:** `b986873ca9cbbcfdc80a962a2faeb25a6984e723ae7367c3b886d3e38c4c7847`
- **SHA-256 de Máscara Normalizada 128x128:** `7e016f4d360fbcceca8f5aeeb2ec0dbbc0d11f7c70c0c283626e2e503e7e2c9e`

### 2.2 Bounding Boxes y Coordenadas Normalizadas
- **Inner Drawing Bbox:** `[0.10, 0.10, 0.90, 0.90]`
- **Symbol Crop Bbox:** `[0.05, 0.05, 0.95, 0.95]`
- **Aspect Ratio:** `1.0` (Centrado isotrópico normalizado)

### 2.3 Rasgos Geométricos Explicables (`SymbolGeometricFeature`)
1. **`valve_body` (feature_type: `triangle`, count: 2):**
   - Lóbulos triangulares opuestos simétricos.
   - Vértice común de convergencia central (asiento): `[0.50, 0.55]`.
   - Lóbulo izquierdo: `[[0.15, 0.25], [0.50, 0.55], [0.15, 0.85]]`.
   - Lóbulo derecho: `[[0.85, 0.25], [0.50, 0.55], [0.85, 0.85]]`.
   - Bbox normalizado: `[0.15, 0.25, 0.85, 0.85]`.
   - Confianza: `0.95`.
2. **`actuator_stem` (feature_type: `line_segment`, count: 1):**
   - Vástago vertical ortogonal a la línea de flujo: `start=[0.50, 0.55]`, `end=[0.50, 0.15]`.
   - Bbox normalizado: `[0.48, 0.15, 0.52, 0.55]`.
   - Confianza: `0.92`.
3. **`handwheel` (feature_type: `line_segment`, count: 1):**
   - Volante o barra transversal horizontal superior: `start=[0.35, 0.15]`, `end=[0.65, 0.15]`.
   - Bbox normalizado: `[0.35, 0.12, 0.65, 0.18]`.
   - Confianza: `0.90`.
4. **`ports` (feature_type: `connection_port`, count: 2):**
   - Puerto entrada: `[0.15, 0.55]`, Puerto salida: `[0.85, 0.55]`.
   - Eje de flujo: Horizontal `0°` (o `180°`).
   - Confianza: `0.98`.

### 2.4 Relaciones Topológicas (`SymbolFeatureRelation`)
- `actuator_stem` -> **`connected_to`** -> `valve_body` en `center_vertex` (`confidence: 0.98`).
- `handwheel` -> **`touches`** -> `actuator_stem` en `stem_top` (`confidence: 0.95`).

### 2.5 Política de Orientación
- **Política:** `rotation_equivalent_180` (Rotaciones ortogonales permitidas: `0°`, `180°`; `90°` y `270°` condicionadas a compatibilidad del eje de puertos).

### 2.6 Decisión HITL de Curación
- **Decisión ID:** `dec-hitl-curate-gate-001`
- **Revisor:** `lead_piping_auditor`
- **Veredicto:** `create_template` (Aprobado como Sandbox / Test Only)
- **Snapshot Rationale:** *"Validada geometría de válvula de compuerta sintética canónica. Se rechaza estatus productivo directo debido a política de evidencia sintética."*

---

## 3. Ocurrencia Reconocida en Documento de Proyecto

### 3.1 Identificación y Localización Contextual
- **Documento:** `DOC-PID-PROJ-01` (Lámina General de Piping)
- **Página:** `1` | **Hoja:** `P-001` (`sheet_id: 11111111-1111-1111-1111-111111111111`)
- **Bbox Absoluto:** `[100, 150, 180, 230]`
- **Bbox Normalizado:** `[0.1000, 0.1500, 0.1800, 0.2300]`
- **Crop Local:** `data/crops/doc_pid_01_crop_gate_01.png`
- **Hash SHA-256 del Crop:** `4f38a56b2e591789c0a6b7d287955fba730cfec921a99878dc1e428e12450893`

### 3.2 Desglose Progresivo de Puntuación Multi-Etapa
| Etapa | Métrica y Fundamento | Ponderación Máx. | Score Obtenido | Contribución |
| :--- | :--- | :---: | :---: | :---: |
| **Etapa 1: Geometría** | Relación de aspecto `1.0`, densidad `0.23` compatible | `0.35` | `0.9420` | **`0.3297`** |
| **Etapa 2: Topología** | Simetría bilateral horizontal/vertical y unión en vértice | `0.20` | `0.9100` | **`0.1820`** |
| **Etapa 3: Visual** | NCC sobre máscara normalizada + Hu Moments (`0°` / `180°`) | `0.35` | `0.9250` | **`0.3238`** |
| **Etapa 4: Contexto** | Tag adyacente `"V-101 Gate Valve"` (secundario) | `0.10` | `1.0000` | **`0.1000`** |
| **TOTAL** | **Suma ponderada (No-textual: 0.8355 >= 0.85 req)** | **`1.00`** | **`0.9355`** | **`0.9355`** |

- **Veredicto de Matching:** `matched` (en entorno `sandbox`)
- **Versión de Plantilla Empleada:** `PIP-VALVE-GATE` v1 (`sandbox_approved`)
- **Aviso Visible de Entorno:** `"Aviso: Match ejecutado en entorno sandbox con plantilla no productiva (test_only/sandbox)."`

---

## 4. Ocurrencia Ambigua (`matching_status: ambiguous`)

### 4.1 Escenario
Un candidato geométrico presenta simetría de dos lóbulos pero con vástago reducido, situándose entre una válvula de compuerta (`PIP-VALVE-GATE`) y una válvula de globo (`PIP-VALVE-GLOBE` candidata).

### 4.2 Comparación de Scores
- **Candidato A (`PIP-VALVE-GATE`):** Total Score = `0.7620` (Geom: `0.78`, Topo: `0.72`, Visual: `0.75`, Context: `0.00`)
- **Candidato B (`PIP-VALVE-GLOBE`):** Total Score = `0.7410` (Geom: `0.76`, Topo: `0.70`, Visual: `0.74`, Context: `0.00`)
- **Diferencia de Score:** `|0.7620 - 0.7410| = 0.0210 < AMBIGUITY_MARGIN (0.05)`

### 4.3 Acción de Gobernanza
- **Veredicto:** `ambiguous`
- **Acción del Sistema:** No se selecciona plantilla arbitrariamente.
- **Registro Generado:** `SymbolReviewDecision(subject_type="occurrence", decision="needs_review")`
- **Acción HITL Disponible en UI:** El operador humano dispone de botón para desambiguar, confirmar vinculación a plantilla específica o marcar como nuevo tipo de válvula.

---

## 5. Símbolo Desconocido con Geometría Válida (`SYM-UNKNOWN-001`)

### 5.1 Escenario
Aparición de un elemento con evidencia geométrica física real (`geometric_evidence: True`, `confidence: 0.94`, `classification: "symbol"`, trazos cerrados vectoriales), pero cuya geometría no coincide con ninguna plantilla canónica activa.

### 5.2 Evidencia Registrada
- **Bbox:** `[0.4500, 0.6000, 0.5200, 0.6800]`
- **Top Match Score:** `0.3850 < MIN_CANDIDATE_SCORE (0.65)`
- **Matching Status:** `unknown_symbol`
- **Hallazgo Creado:** `SYM-UNKNOWN-001`
- **Caso de Investigación Técnica:** `SymbolUnknownResearchCase`
  - `status: "unknown"`
  - `proposed_name: "SYM-UNKNOWN-001"`
  - `proposed_standard_reference: "PIP PNC00001 / ISA-5.1"`
  - `research_notes: "Geometría real válida detectada sin coincidencia en catálogo canónico activo."`
- **Regla Estricta:** El símbolo desconocido **NUNCA se auto-promueve a plantilla canónica sin validación humana (HITL)**.

---

## 6. Casos Negativos y Falsos Positivos Excluidos

| Tipo de Negativo | Entrada Probada | Comportamiento del Sistema | Resultado de Gobernanza |
| :--- | :--- | :--- | :--- |
| **Texto OCR sin geometría** | OCR detecta `"GATE VALVE"` en celda vacía | Precondiciones fallan (`geometric_evidence: False`) | **0 candidatos**, **0 ocurrencias**. Rechazo inmediato. |
| **Tabla ISA alfanumérica** | Celda con texto `"ISA-101-FCV"` sin dibujo | `has_symbol: False`, sin trazos de dibujo interno | No genera candidato ni ocurrencia. |
| **Forma de onda / Gráfico** | Curva analógica de proceso | Clasificado como `figure` / `not_symbol` | `record_kind: "candidate"`, `matching_status: "not_applicable"`. Cero ocurrencias reconocidas. |
| **Dos triángulos sin válvula** | Dos triángulos separados por 20px sin vértice común | `lacks_central_junction: True` -> `topology_score: 0.25` | Score total capado a `0.45`. Rechazado (`unknown_symbol` o `rejected`). |
| **Recorte con borde de grilla** | Borde de celda negro que invade el crop | `has_border_contamination: True` -> penalización severa | Score visual capado a `0.35`. Rechazado. |

---

## 7. Instrucciones para Reproducción Local

Para reproducir determinísticamente esta suite de validación en entorno local con PostgreSQL real:

```bash
# 1. Asegurar contenedor de PostgreSQL de pruebas activo
docker ps | grep plan_review_postgres_test

# 2. Ejecutar la validación completa del catálogo y gobernanza
python backend/scripts/validate_canonical_symbol_catalog_postgres.py

# 3. Ejecutar las pruebas de integración en pytest
python -m pytest backend/tests/integration/test_canonical_piping_symbol_catalog.py -v
```
