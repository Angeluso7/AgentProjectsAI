# Arquitectura del Pipeline de Reconocimiento y Extracción Simbólica

## 1. Regla Innegociable del Sistema: Geometría Visual Válida Antes que OCR

El principio fundamental que rige el subsistema de extracción y reconocimiento simbólico en `plan-review-ai-hybrid` es:

```
GEOMETRÍA VISUAL VÁLIDA
  → Símbolo candidato
    → OCR y contexto para enriquecimiento semántico
      → Revisión / Curación HITL
        → Promoción a SymbolTemplate / StructuredSymbol
```

### Prohibiciones Estrictas de Generación de Candidatos

**NUNCA** se crea ni promueve un símbolo candidato a partir de:
- OCR breve o cadenas de texto aisladas (ej. `"V-01"`, `"P-101"`, `"MAT-02"`).
- Textos puros o tablas de especificaciones alfanuméricas.
- Columna 0 de una tabla por mera posición ordinal.
- Coordenadas de celda sin dibujo interno (`cell_bbox` sin `inner_drawing_bbox`).
- Códigos de tag o nombres de fila.
- Heurísticas basadas en títulos de encabezado (ej. asumir símbolo porque el encabezado dice `"SÍMBOLO"` cuando la celda contiene solo texto).
- Ausencia de detección geométrica (no hay fallbacks que "inventen" símbolos).

---

## 2. Flujo Completo del Pipeline

El pipeline end-to-end opera de acuerdo con la siguiente secuencia rigurosa:

```
┌─────────────────┐
│     GRILLA      │ (Detección vectorial / raster / lógica de tabla)
└────────┬────────┘
         ▼
┌─────────────────┐
│     CELDA       │ (Segmentación espacial [row, col] con cell_bbox)
└────────┬────────┘
         ▼
┌─────────────────┐
│    GEOMETRÍA    │ (Inspección vectorial / trazos / exclusión de bordes y texto)
└────────┬────────┘
         ▼
┌─────────────────┐
│      CROP       │ (Generación de recorte con margen 3 mm, acotado a la celda)
└────────┬────────┘
         ▼
┌─────────────────┐
│   OCR/CONTEXTO  │ (Enriquecimiento direccional: nombre, función, tag, norma)
└────────┬────────┘
         ▼
┌─────────────────┐
│  CLASIFICACIÓN  │ (symbol vs figure vs table_graphic vs not_symbol)
└────────┬────────┘
         ▼
┌─────────────────┐
│  DEDUPLICACIÓN  │ (Plantilla canónica hash/IoU conservando todas las ocurrencias)
└────────┬────────┘
         ▼
┌─────────────────┐
│     UI / HITL   │ (Curación humana, asignación de disciplina y validación)
└─────────────────┘
```

---

## 3. Modelo de Grilla de Tabla (Estilo Hoja de Cálculo / Excel)

Las tablas dentro de planos y documentos técnicos (diagramas P&ID, unilineales, cuadros de cargas, especificaciones de piping, listados de válvulas e instrumentos) se modelan formalmente como grillas bidimensionales estructuradas:

1. **Detección de Grilla Física Vectorial:**
   - Análisis de primitivas gráficas (`drawings`, paths, rectángulos y líneas) mediante PyMuPDF (`fitz`).
   - Clasificación taxonómica de 9 tipos de trazos vectoriales:
     - `table_outer_border`: perímetro exterior de la tabla.
     - `table_row_boundary`: separadores horizontales de filas.
     - `table_column_boundary`: separadores verticales de columnas.
     - `table_subgrid`: subdivisiones internas secundarias.
     - `cell_content`: trazos internos constitutivos del gráfico o símbolo.
     - `axis`: líneas de referencia o ejes cartesianos.
     - `waveform`: trenes de pulsos o curvas de señal analógica.
     - `diagram_connection`: líneas de proceso o tubería conectadas.
     - `unknown`: primitivas no clasificadas.
   - **Regla Estructural:** Únicamente `table_outer_border`, `table_row_boundary` y `table_column_boundary` son elegibles para definir los límites `x_boundaries` e `y_boundaries` de la grilla. Los elementos gráficos internos nunca modifican el contorno de la celda.

2. **Detección de Grilla Raster:**
   - Para documentos escaneados o planos rasterizados, detección morfológica mediante transformaciones de apertura horizontal y vertical (kernels lineales) para extraer la retícula ortogonal.

3. **Fallback Lógico por Alineamiento de Texto:**
   - En tablas sin bordes explícitos (grillas invisibles o cuadros alfanuméricos flotantes), se agrupan los bloques de texto proyectando histogramas de densidad horizontal (filas) y vertical (columnas) para inferir la matriz de celdas virtuales.

---

## 4. Segmentación y Clasificación de Celdas

Cada celda resultante de la intersección $[r, c]$ se segmenta y se le asigna una categoría explícita:

| Clase de Celda | Criterio de Clasificación | Elegible para Símbolo |
| :--- | :--- | :---: |
| `symbol_cell` | Contiene dibujo vectorial cerrado o raster significativo tras excluir bordes y texto. | **SÍ** |
| `text_cell` / `text_only` | Contiene texto o caracteres alfanuméricos sin trazos gráficos técnicos internos. | **NO** |
| `mixed_cell` | Contiene simultáneamente texto y geometría interna diferenciada. | **SÍ** (se enmascara el texto) |
| `empty_cell` / `empty` | Sin texto ni trazos gráficos. | **NO** |

### Enmascaramiento de Texto y Exclusión de Bordes
Para aislar la geometría pura del símbolo:
1. **Exclusión de Bordes:** Se aplica un buffer interno de exclusión respecto a las 4 líneas divisorias de la celda para ignorar los trazos limítrofes de la grilla.
2. **Enmascaramiento de Texto OCR:** Todo bounding box de texto detectado dentro de la celda se proyecta como máscara de exclusión. Los trazos dentro de esta máscara se descartan para el cómputo de convexidad, densidad y centroide de la geometría.
3. **Cálculo de `inner_drawing_bbox`:** El bounding box ajustado a los trazos gráficos remanentes tras la exclusión de bordes y texto.
4. **Cálculo de `symbol_crop_bbox` con Margen de 3 mm:**
   - Se toma el `inner_drawing_bbox`.
   - Se calcula el equivalente en puntos tipográficos de 3.0 mm (aprox. $3.0 \times \frac{72}{25.4} \approx 8.5$ pt).
   - Se expande el bbox con este margen simétrico en los cuatro costados.
   - **Restricción estricta:** El `symbol_crop_bbox` se clampa para que nunca exceda los límites de la celda física contenedora (`cell_bbox`).

---

## 5. Orientación de Lectura y Enriquecimiento Semántico Direccional

Para asociar los atributos contextuales (descripción, función, tag, norma) al símbolo identificado, el pipeline analiza la topología de la tabla:

- **Orientación Detectada:**
  - `row_major`: Símbolo a la izquierda o derecha; especificaciones, tags y normas en celdas de la misma fila.
  - `col_major`: Símbolo en la cabecera; atributos en celdas de la misma columna descendente.
  - `mixed`: Coexistencia de agrupaciones horizontales y verticales.
  - `undetermined`: Estructura irregular sometida a scoring de proximidad geométrica.
  - `none`: Tabla sin símbolos (especificaciones o planillas puras).

### Enriquecimiento Multimodal
- **Extracción de Texto:** El OCR adyacente provee metadatos complementarios (nombre propuesto, norma de referencia, tag o número de parte).
- **Sanitización Estructural:** Textos masivos, tablas de verdad alfanuméricas o ruido binario se filtran mediante `structural_sanitizer` para evitar desbordamiento en campos de visualización (`title` <= 120 caracteres, `hierarchy_path` <= 180 caracteres, `content_text` <= 350 caracteres), preservando el OCR crudo íntegro en `structured_payload`.

---

## 6. Taxonomía de Clasificación Visual y Separación de Gráficos

El clasificador discrimina categóricamente entre:

1. **`symbol`:**
   - Representaciones esquemáticas estandarizadas de componentes de ingeniería (válvulas, bombas, motores, instrumentos, compuertas lógicas, extintores, rociadores).
2. **`figure`:**
   - Formas de onda analógicas/digitales (diagramas de temporización ISA 5.1 página 66), detalles constructivos, secciones de corte arquitectónico, diagramas de flujo libres.
   - **Regla:** Formas de onda se catalogan como `figure`, nunca como símbolo canónico.
3. **`table_graphic`:**
   - Diagramas o gráficos integrados en cuadros técnicos que ilustran configuraciones particulares de montaje.
4. **`not_symbol`:**
   - Celdas con texto puro, códigos tabulares o ruido visual menor a los umbrales mínimos de área y complejidad.
5. **`requires_human_review`:**
   - Geometrías ambiguas con confianza limítrofe o variantes visuales atípicas derivadas al flujo HITL.

---

## 7. Deduplicación: Plantilla Canónica vs Ocurrencias

Para optimizar el inventario sin perder trazabilidad:
- **`SymbolTemplate` (Plantilla Canónica):** Representa la firma visual normalizada (hash perceptual / embedding geométrico invariant a escala y rotación menor). Agrupa atributos normativos canónicos y catálogo de piezas.
- **`SymbolOccurrence` (Ocurrencia):** Cada detección física individual en un plano o tabla conserva:
  - Documento fuente (`document_id`).
  - Hoja o página (`sheet_id`, `page_number`).
  - Linaje tabular (`source_table_id`, `row_index`, `col_index`).
  - Coordenadas normalizadas (`cell_bbox`, `inner_drawing_bbox`, `symbol_crop_bbox`).
  - Ruta de imagen de recorte físico (`crop_image_path`).

---

## 8. Flujo UI / HITL y Separación de Conceptos Normativos

### Prohibición Estricta: Símbolos NO son Reglas de Auditoría
Está terminantemente prohibido promover símbolos a `RuleDefinition`. Un símbolo no es una regla de validación ni una cláusula prescriptiva.

### Flujo Correcto de Promoción:
```
ExtractedSymbolCandidateDTO
  ▼
StructuredSymbol (Persistido en document_structural_nodes / detected_symbols)
  ▼
Curación en UI (SymbolCurationStudioModal / HITL Review)
  ▼
SymbolTemplate (Biblioteca canónica de símbolos del proyecto/organización)
```
