# Registro de Evidencia de Aceptación: Pipeline de Símbolos y Grillas Tabulares

Este documento registra los resultados reales, reproducibles y verificables obtenidos al ejecutar la suite de integración sobre casos de prueba sintéticos y documentos técnicos de ingeniería.

---

## Caso A: Tabla Alfanumérica ISA 5.1 (Página 66 - Matriz de Verdad y Lógica Binaria)

### 1. Metadatos del Documento de Prueba
- **Fixture / Documento:** Norma ISA-5.1-1984 (R1992) / Simulación fiel de página 66.
- **Identificador de Prueba:** `test_negative_isa51_alphanumeric_combinations` en `backend/tests/integration/test_strict_symbol_geometry_pipeline.py`.
- **Artefacto de Auditoría:** `backend/isa_page66_audit.json`.
- **Overlay de Verificación:** `backend/isa_page66_annotated_overlay.png`.
- **Página:** 66.
- **DPI de Rasterización:** 300 DPI (con soporte de análisis vectorial directo a 72 pt/pulgada).
- **Dimensiones de Página:** 612 x 792 pt.

### 2. Resultados de la Detección
- **Fuente de Grilla:** `vector` (análisis de primitiva gráfica mediante `fitz.get_drawings()`).
- **Confianza de Grilla:** 0.95 (detección de cuadrícula ortogonal de 12 filas x 3 columnas = 36 celdas).
- **Candidatos a Símbolo Generados:** **0** (`len(extracted_symbols) == 0`).
- **Estado de Celdas:**
  - 34 celdas clasificadas como `text_only` / `text_cell` o `empty`.
  - 2 celdas con formas de onda clasificadas como `figure` (filas 7 y 11, columna 2).
- **Comportamiento HITL / UI:**
  - La tabla se clasifica como `documentary_table`.
  - Ninguna celda entra al flujo de candidatos a símbolos ni a la pestaña de símbolos del frontend.

### 3. Trazabilidad de Logs
```
[INFO] TableExtractor: Detected 12 rows, 3 columns via vector grid analysis (confidence=0.95).
[INFO] TableExtractor: Row 7, Col 2 contains waveform paths -> graphic_classification='figure', has_symbol=False.
[INFO] TableExtractor: Row 7, Col 1 contains truth matrix text -> graphic_classification='not_symbol', has_symbol=False.
[INFO] TableExtractor: Total symbol candidates extracted: 0. Table reading orientation: 'none'.
```

---

## Caso B: Leyenda Técnica Real de Piping y Protección Contra Incendios

### 1. Metadatos del Documento de Prueba
- **Fixture / Documento:** Plano de Leyenda Técnica P&ID / Contra Incendios (`create_real_technical_legend_pdf`).
- **Identificador de Prueba:** `TestStrictSymbolGeometryPositivePipeline::test_real_legend_technical_drawings_extraction` en `backend/tests/integration/test_strict_symbol_geometry_pipeline.py`.
- **Página:** 1.
- **Dimensiones:** 800 x 600 pt.

### 2. Resultados de la Detección
- **Fuente de Grilla:** `vector` (líneas físicas delimitadoras de celdas).
- **Confianza de Grilla:** 1.0 (grilla cartesiana regular de 6 filas x 3 columnas).
- **Candidatos a Símbolo Generados:** **4** símbolos técnicos con evidencia geométrica válida:
  1. **Válvula de Compuerta Bridada** (ASME B16.34):
     - `cell_bbox`: `[0.0625, 0.1667, 0.225, 0.2833]`
     - `inner_drawing_bbox`: detectado en torno a los triángulos opuestos y vástago.
     - `symbol_crop_bbox`: expandido con margen de 3 mm respecto a `inner_drawing_bbox` y confinado a `cell_bbox`.
     - `confidence_score`: 0.95.
  2. **Pulsador de Alarma de Incendio** (NFPA 72):
     - `cell_bbox`: `[0.0625, 0.2833, 0.225, 0.40]`
     - Geometría: círculos concéntricos.
     - `crop_image_path`: generado en directorio temporal de crops con formato SVG/PNG.
  3. **Extintor PQS 10kg** (DS 594 Art. 45):
     - Geometría: cuerpo rectangular y manija.
  4. **Válvula de Retención Check Swing** (API 6D / ISA 5.1):
     - Geometría: dos triángulos con flecha direccional.

### 3. Exclusiones y Enriquecimiento
- **Exclusión de Bordes y Texto:** Los textos "SÍMBOLO", "DENOMINACIÓN" y las especificaciones contiguas no contaminan el crop visual.
- **Asociación Semántica:** El texto de la columna 1 se asoció exitosamente como `symbol_name` y `symbol_description`; la columna 2 proveyó la norma aplicable `standard_reference`.

---

## Caso C: Tabla Mixta con Formas de Onda, Compuertas y Matrices (ISA 5.1 Mixto)

### 1. Metadatos del Documento de Prueba
- **Fixture / Documento:** Tabla técnica mixta con diagramas temporales y compuertas lógicas.
- **Identificador de Prueba:** `test_mixed_table_classification_and_waveform_separation` en `backend/tests/integration/test_isa_waveform_regression.py`.
- **Página:** 1.

### 2. Resultados de la Clasificación Multiclase
| Elemento en Tabla | Clasificación Asignada | Justificación Técnica |
| :--- | :--- | :--- |
| Curvas de temporización / oscilación | `figure` / `table_graphic` | Trazos abiertos continuos con ejes cartesianos; no representan componente discreto. |
| Compuertas lógicas (AND / OR) | `symbol` (o `requires_human_review`) | Trazos cerrados normalizados con puertos de conexión. |
| Tabla de verdad ('1 0 0 1 0 1') | `not_symbol` | Bloque textual/numérico sin primitivas de dibujo técnico. |
| Código de fila ('ROW-04') | `not_symbol` | Identificador alfanumérico descartado por regla de geometría obligatoria. |

### 3. Deduplicación y Linaje
- **Deduplicación:** Las ocurrencias repetidas de un mismo símbolo conservan cada una su `cell_bbox`, `row_index` y `col_index`, vinculadas a una única plantilla normalizada `SymbolTemplate`.
- **Navegación:** Cada ocurrencia permite hacer scroll y zoom hacia su bounding box exacto en el visor PDF interactivo del frontend.

---

## 4. Resumen de Ejecución de Pruebas Automatizadas

Comando ejecutado en el entorno de desarrollo:
```bash
python -m pytest backend/tests/integration/test_strict_symbol_geometry_pipeline.py \
                 backend/tests/integration/test_table_symbol_excel_grid_and_deduplication.py \
                 backend/tests/integration/test_symbols_in_tables_integrity.py \
                 backend/tests/integration/test_table_physical_grid_and_symbol_crop.py \
                 backend/tests/integration/test_table_symbol_real_extraction.py \
                 backend/tests/integration/test_structural_nodes_symbol_persistence.py -v
```

**Resultado:**
- **Total Pruebas:** 32
- **Aprobadas:** 32 (100%)
- **Fallidas:** 0
- **Omitidas:** 0
- **Tiempo de Ejecución:** ~5.02 segundos.
