# Diseño Técnico: Catálogo Canónico de Simbología de Piping (Incremento 01)

## 1. Contexto y Objetivos

Este documento establece la arquitectura técnica, modelo de datos y flujo operativo para el primer vertical slice del **Catálogo Canónico de Simbología de Piping** en `plan-review-ai-hybrid`.

El ciclo vertical completo cubre:
```
Documento normativo / Leyenda P&ID
  → Candidato con geometría válida
    → Revisión y curación HITL
      → StructuredSymbol
        → SymbolTemplate versionado (SymbolTemplate + SymbolTemplateVersion)
          → Catálogo de piping activo
            → Lectura de planos / documentos de proyecto
              → Matching geométrico progresivo (Geometría + Topología + Visual)
                → SymbolOccurrence en proyecto
                  → Conteo, ubicación, estado y hallazgos QA/QC
```

### Regla Innegociable de Detección
```
GEOMETRÍA VISUAL VÁLIDA
  → Candidato visual
    → Clasificación de primitivas
      → Matching geométrico / topológico
        → OCR / Contexto como enriquecimiento o desempate limitado
          → Decisión
            → Revisión HITL o Promoción
```

**Queda estrictamente prohibido:**
- Generar candidatos a partir de OCR breve, texto, tags, códigos, columna 0, posición de celda o encabezados.
- Convertir un símbolo detectado directamente en una `RuleDefinition`.
- Reemplazar la evidencia geométrica por heurísticas alfanuméricas.

---

## 2. Inventario de Componentes y Modelos Reutilizados

| Componente / Modelo | Ubicación | Estado Actual | Adaptación en este Incremento |
| :--- | :--- | :--- | :--- |
| `SymbolTemplate` | `backend/app/db/models/template_memory.py` | Modelo de tabla `symbol_templates` creado en 0007 y ampliado en 0022 con descriptores de forma (Hu, contorno, aspecto, primitivas). | Se extiende con `canonical_code`, `canonical_name`, `subcategory`, `discipline`, `technical_function`, `standard_reference`, `status` y relación 1:N a `SymbolTemplateVersion`. |
| `DetectedSymbol` / `SymbolOccurrence` | `backend/app/db/models/document_memory.py` | Modelo de tabla `detected_symbols` creado en 0007 y ampliado en 0022 con `match_score_visual`, `match_rotation_deg`, `match_evidence`. | Se reutiliza y extiende con los campos de ocurrencia de proyecto (`project_id`, `project_document_id`, `matched_template_id`, `matched_template_version_id`, `match_score`, `geometry_score`, `topology_score`, `visual_score`, `context_score`, `detected_tag_or_code`, `context_text`, `review_status`, `detection_run_id`). |
| `StructuredSymbol` | `backend/app/db/models/intake_extractions.py` | Modelo de tabla `structured_symbols` creado en 0016 y ampliado en 0019 con contexto de tabla, linaje y render mode. | Punto de entrada del candidato validado que se promueve a versión de plantilla canónica. |
| `GeometricEvidenceValidator` | `backend/app/services/symbols/geometric_validator.py` | Validador estricto con eliminación de bordes de tabla, fondos y glifos tipográficos aislados. | Provee la precondición obligatoria de entrada al matching. |
| `TemplateNormalizer` | `backend/app/services/symbols/template_normalizer.py` | Normalizador de imagen a máscara binaria 128x128 con cálculo de momentos de Hu y contorno. | Genera firmas normalizadas para `SymbolTemplateVersion`. |
| `TemplateMatcher` | `backend/app/services/symbols/template_matcher.py` | Motor determinista basado en correlación cruzada normalizada (OpenCV NCC) y momentos de Hu. | Se integra como subcomponente del cálculo del `visual_score` dentro del nuevo motor progresivo. |
| `SymbolDeduplicationService` | `backend/app/services/symbols/deduplication_service.py` | Deduplicación multi-factor con dHash perceptual, tamaño físico y ontología ISA. | Enlaza variantes visuales y agrupa candidatos duplicados conservando ocurrencias. |
| `LegendTableExtractor` | `backend/app/services/symbols/legend_table_extractor.py` | Extractor de tablas de leyenda con linaje celda-fila-dibujo interno. | Extrae candidatos visuales desde láminas técnicas de leyenda. |
| Migraciones previas | `migrations/versions/0019_...py` y `0022_...py` | 0019 introdujo soporte piping dual; 0022 expandió `symbol_templates` y `detected_symbols`. | La nueva migración `0023` se encadena de forma directa sobre la revisión `0022_expand_symbol_templates`. |

---

## 3. Relación Explícita con Migraciones 0019 y 0022

1. **Migración 0019 (`0019_piping_symbol_dual`):**
   - Agregó a `structured_symbols` los campos de render dual (`source_render_mode`), contexto (`layout_context`, `context_association_mode`), referencia normativa (`standard_reference`), familia (`canonical_symbol_family`), grupo de variantes (`visual_variant_group_id`), linaje (`source_table_id`, `row_index`, `col_index`, `cell_bbox`, `row_bbox`) y tamaño estimado en mm (`estimated_physical_size_mm`).
2. **Migración 0022 (`0022_expand_symbol_templates`):**
   - Agregó a `symbol_templates` los descriptores geométricos (`normalized_mask_path`, `mask_hash`, `hu_moments`, `contour_signature`, `canonical_width_mm`, `canonical_height_mm`, `aspect_ratio`, `primitive_signature`, `rotation_invariance_mode`, `is_active_for_detection`, `organization_id`).
   - Agregó a `detected_symbols` los campos de auditoría de matching (`match_score_visual`, `match_rotation_deg`, `match_method`, `match_evidence`, `algorithm_version`).
3. **Nueva Migración 0023 (`0023_piping_canonical_catalog_and_occurrences`):**
   - Sucede inmediatamente a `0022_expand_symbol_templates`.
   - Extiende `symbol_templates` con `canonical_code`, `canonical_name`, `subcategory`, `technical_function`, `status`, `current_version_id`, `created_by`, `updated_at`.
   - Crea las tablas hijas relacionales:
     - `symbol_template_versions`
     - `symbol_geometric_features`
     - `symbol_feature_relations`
     - `symbol_source_evidences`
     - `symbol_review_decisions`
     - `symbol_unknown_research_cases`
   - Extiende `detected_symbols` (entidad base de `SymbolOccurrence`) con las columnas de matching y scoring progresivo desglosado.

---

## 4. Diagrama Entidad-Relación

```
┌────────────────────────────────┐
│         ExtractedItem          │ (Candidato de leyenda / documento)
└───────────────┬────────────────┘
                │ 1:1
┌───────────────▼────────────────┐
│        StructuredSymbol        │ (Símbolo curado con geometría y metadatos)
└───────────────┬────────────────┘
                │ Promoción HITL
┌───────────────▼────────────────┐
│         SymbolTemplate         │ (Identidad técnica canónica: PIP-VALVE-GATE)
└───────────────┬────────────────┘
                │ 1:N
┌───────────────▼────────────────┐       1:N      ┌───────────────────────────────┐
│     SymbolTemplateVersion      ├────────────────►    SymbolGeometricFeature     │
└───────┬───────────────┬────────┘                └──────────────┬────────────────┘
        │ 1:1           │ 1:N                                    │ 1:N
┌───────▼────────┐ ┌────▼───────────────────────┐ ┌──────────────▼────────────────┐
│ SourceEvidence │ │  DetectedSymbol /          │ │    SymbolFeatureRelation      │
└────────────────┘ │  SymbolOccurrence          │ └───────────────────────────────┘
                   └────┬───────────────────────┘
                        │ 1:N
                   ┌────▼───────────────────────┐
                   │    SymbolReviewDecision    │
                   └────────────────────────────┘
```

---

## 5. Familia Inicial Seleccionada: `PIP-VALVE-GATE` (Válvula de Compuerta)

### Identidad Técnica y Cita de Fuentes Concretas
- **Código Canónico:** `PIP-VALVE-GATE`
- **Nombre Canónico:** Válvula de compuerta manual (Gate Valve)
- **Categoría:** `valve`
- **Subcategoría:** `gate_valve`
- **Disciplina:** `piping`
- **Función Técnica:** Válvula de aislamiento y bloqueo bidireccional de paso total para apertura/cierre de línea.
- **Fuentes Técnicas Verificadas y Citadas:**
  - *Lámina de Leyenda P&ID de Proyecto*: Bloque de leyenda de tuberías e instrumentación (PID-LEG-001 Rev. 2).
  - *Práctica Estándar de la Industria PIP PNC00001 (Process Industry Practices - Piping and Instrumentation Diagram Documentation Guidelines)*: Símbolo de cuerpo de válvula formado por dos triángulos con vértices concurrentes enfrentados sobre la línea de proceso, con vástago lineal vertical rematado en barra transversal representativa del volante manual.
  - *Referencia de Aplicación ISA-5.1 (Sección 5.4)*: Emplea la misma representación geométrica de cuerpo de válvula con dos triángulos opuestos para indicar cuerpos de válvula en diagramas de lazos e instrumentación.

### Rasgos Geométricos Explicables
1. **Triángulos Opuestos (Cuerpo de Válvula):**
   - Dos polígonos triangulares equiláteros o isósceles cuyas puntas convergen exactamente en el vértice central (punto de cierre).
   - Relación espacial: `touches` (contacto en vértice) y `symmetric_to` (simetría axial respecto al plano transversal).
2. **Vástago (Stem):**
   - Segmento rectilíneo vertical conectado perpendicularmente al punto central superior de los triángulos.
   - Relación espacial: `connected_to` (origen en el vértice/cuerpo de la válvula).
3. **Volante / Actuador Manual (Handwheel):**
   - Segmento rectilíneo horizontal centrado sobre el extremo del vástago, paralelo al eje de la tubería.
   - Relación espacial: `intersects` / `touches` en el punto terminal del vástago.

### Política de Orientación para `PIP-VALVE-GATE`
- **Política asignada:** `rotation_equivalent_180` (en línea de tubería horizontal) con comprobación ortogonal controlada (`orthogonal_pipe_axes`).
- **Justificación técnica:**
  - En una línea de tubería horizontal, el cuerpo de la válvula de compuerta es simétrico a 180° (el flujo puede ingresar por la izquierda o por la derecha indistintamente).
  - A 90° o 270°, el símbolo representa una válvula instalada sobre una línea de tubería vertical.
  - No es `rotation_invariant` libre (un ángulo de 45° no es válido a menos que la línea esté a 45°).
  - El vástago y volante indican la orientación espacial del vástago para verificación de interferencias y accesibilidad de operación.

---

## 6. Política Estricta de Etiquetado y Registro de Evidencia Visual

Todo fixture o muestra de evidencia visual utilizada en el catálogo y pruebas debe etiquetarse inequívocamente con uno de los siguientes tres estados:

1. **`synthetic`**: Generado por script, código de dibujo procedural o librerías de prueba (PyMuPDF, PIL, OpenCV). **Bajo ninguna circunstancia se denominará "documento real"**.
2. **`redacted_real`**: Derivado de un documento industrial o plano de proyecto legítimo, con datos sensibles (nombres de clientes, proyectos, firmas, coordenadas geoespaciales) enmascarados o anonimizados.
3. **`real_authorized`**: Extraído íntegramente de un documento normativo público, lámina de catálogo de fabricante autorizada o plano de proyecto con autorización explícita.

### Metadatos Obligatorios para Evidencia Autorizada (`SymbolSourceEvidence`):
- `source_document_id`: Identificador único del documento origen.
- `source_document_hash`: SHA-256 del archivo PDF origen.
- `page_number`: Número de página (1-indexed).
- `bbox_normalized`: Coordenadas relativas `[x0, y0, x1, y1]`.
- `crop_image_path`: Ruta física del recorte generado.
- `crop_image_hash`: SHA-256 de la imagen recortada.
- `source_standard_or_project`: Nombre de la norma, catálogo o proyecto origen.
- `source_revision`: Código de revisión del documento (ej. `Rev. 0`, `Ed. 2024`).
- `source_date`: Fecha de emisión del documento origen.

---

## 7. Precondición Única de Entrada al Matching

Para que cualquier elemento participe en el matching productivo frente al catálogo canónico, debe satisfacer conjuntamente la siguiente condición:

```python
is_eligible_for_matching = (
    geometric_evidence is True
    and geometric_confidence >= settings.SYMBOL_MIN_GEOMETRIC_CONFIDENCE # (ej. 0.70)
    and graphic_classification == "symbol"
    and inner_drawing_bbox is not None and len(inner_drawing_bbox) == 4
    and symbol_crop_bbox is not None and len(symbol_crop_bbox) == 4
    and crop_image_path is not None and os.path.exists(crop_image_path)
)
```

- `has_real_geometry` se implementa como propiedad calculada (`derived property`) idéntica a `geometric_evidence`, evitando dobles fuentes de verdad.
- Elementos clasificados como `figure`, `table_graphic` o `not_symbol` quedan **excluidos** del matching.

---

## 8. Arquitectura de Scoring Ponderado y Criterios de Decisión

### Desglose de Scores
El matching evalúa tres dimensiones principales y una dimensión secundaria limitada:

1. **`geometric_score` (Peso: 0.35):**
   - Verificación de primitivas requeridas (triángulos concurrentes, segmentos ortogonales).
   - Relación de aspecto normalizada y compacidad.
2. **`topology_score` (Peso: 0.20):**
   - Cumplimiento de relaciones espaciales (`touches` en vértice, `connected_to` de vástago, `intersects` de volante).
3. **`visual_score` (Peso: 0.35):**
   - Correlación cruzada normalizada (OpenCV NCC `TM_CCOEFF_NORMED`) calculada según la política de orientación.
   - Distancia logarítmica de Momentos de Hu invariantes.
   - *Nota de limitaciones visuales:* NCC y Hu son sensibles a la rasterización en baja resolución, variaciones de grosor de línea (`stroke_width`), recortes parciales con líneas adyacentes de tubería y artefactos de compresión. Por ello, el score visual nunca puede forzar un match si la geometría o topología son insuficientes.
4. **`context_score` (Peso máximo: 0.10):**
   - Similitud textual del tag adyacente o descripción (ej. `"V-01"`, `"COMPUERTA"`, `"GATE"`).
   - **Restricción estricta:** Solo actúa como desempate fino; un score de contexto alto con geometría incompatible no puede rescatar la detección.

**Peso combinado no-textual (Geometría + Topología + Visual):** `0.35 + 0.20 + 0.35 = 0.90 >= 0.85`.

### Reglas de Declaración de Estado de Matching (`matching_status`)
Para declarar una ocurrencia como `matched`:
1. `total_score >= 0.82` (umbral configurable de auto-match).
2. `geometric_score >= 0.75`.
3. `topology_score >= 0.70` (para símbolos con topología compuesta).
4. La versión de la plantilla debe estar en estado `approved`.
5. La plantilla canónica debe estar en estado `active`.
6. **Margen de ambigüedad:** `best_score - second_best_score >= 0.10` (`ambiguity_margin`).

- Si `total_score >= 0.65` pero la diferencia frente a la segunda plantilla es `< 0.10`:
  `matching_status = "ambiguous"`, `review_status = "needs_review"`.
- Si el elemento posee geometría válida (`geometric_evidence == True`) pero ninguna plantilla supera el umbral:
  `matching_status = "unknown_symbol"`, se abre automáticamente un caso en `SymbolUnknownResearchCase`.
- Si el elemento carece de geometría válida:
  `matching_status = "not_applicable"`, rechazado.

---

## 9. Validación Dual: SQLite Rápido y PostgreSQL Real

- **Entorno de Desarrollo y Pruebas Rápidas:** SQLite en memoria (`sqlite:///:memory:`) para iteración y tests unitarios de milisegundos.
- **Entorno de Integración y Compatibilidad:** PostgreSQL 15+ real (mediante service container en GitHub Actions o contenedor local).
  - Validación de migración Alembic `upgrade` y `downgrade` completos.
  - Validación de tipos JSON nativos, restricciones de clave foránea con borrado en cascada, índices únicos y compatibilidad RLS.
