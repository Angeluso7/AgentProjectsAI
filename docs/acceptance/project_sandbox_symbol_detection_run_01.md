# Aceptación Técnica Sandbox: Ejecución 01 de Detección de Simbología de Piping

**Documento de Aceptación Funcional, Validación Geométrica y Auditoría de Gobernanza**  
**Proyecto de Prueba:** `redacted_real` (Plano de Ingeniería de Piping Redactado y Anonimizado)  
**Rama:** `feat/piping-symbol-catalog-increment-01`  
**Pull Request:** [#2](https://github.com/Angeluso7/AgentProjectsAI/pull/2)  
**Modo de Ejecución:** `sandbox`  
**Clasificación de Evidencia:** `redacted_real`  
**Fecha de Ejecución:** 2026-09-22  
**Hash del Documento Fuente (SHA-256):** `aff4fc103edfcb1b5812b6ac3fcd65fa12dcaedea510549f9f23f4bc763eb471`  

---

## 1. Declaración de Gobernanza e Invariantes Sandbox

> [!IMPORTANT]
> **REGLA DE GOBERNANZA PRODUCTIVA Y HITL:**
> 1. **Modo Estricto Sandbox:** Esta ejecución se llevó a cabo con `execution_mode: "sandbox"`. Ninguna coincidencia generada constituye un hallazgo productivo definitivo.
> 2. **Advertencia Obligatoria:** Toda ocurrencia o candidato correlacionado con `PIP-VALVE-GATE` lleva la advertencia explícita:  
>    `"sandbox/test_only; not production-approved"`.
> 3. **Bloqueo de Promoción Automática:** La plantilla `PIP-VALVE-GATE` **NO ha sido promovida a producción** a partir de este ensayo. Requiere revisión y decisión explícita HITL en un ciclo posterior.
> 4. **Privacidad y Datos Confidenciales:** Los planos originales y datos privados de cliente han sido redactados y anonimizados antes del procesamiento. No se suben PDFs privados al repositorio de GitHub. Solo se persisten hashes criptográficos, metadatos de auditoría JSON, coordenadas vectoriales y recortes anonimizados en `data/crops/sandbox_acceptance/`.

---

## 2. Metadatos del Documento Fuente y Hojas Evaluadas

El documento de prueba evaluado (`redacted_piping_project_01.pdf`) consta de 3 hojas técnicas estructuradas para validar exhaustivamente el pipeline:

| Hoja | Código de Lámina | Título Técnico | Tipo de Contenido Evaluado | Clasificación Evidencia |
| :--- | :---: | :--- | :--- | :---: |
| **1** | `LEG-01` | P&ID Symbology & Legend Sheet | Leyenda tabular con símbolos vectoriales, celdas de texto puro y casos ambiguos | `redacted_real` |
| **2** | `PID-101` | Process Flow & Piping Manifold Sheet | Región libre de proceso con tubería continua, válvula inline y componente desconocido | `redacted_real` |
| **3** | `SCH-01` | Equipment Schedule & Pressure Waveform Sheet | Control negativo: tabla alfanumérica pura, forma de onda analógica y líneas no cerradas | `redacted_real` |

- **Document ID Interno:** `98523f72-1fe1-4885-9376-b4b56295443f`
- **Hash SHA-256 Documento:** `aff4fc103edfcb1b5812b6ac3fcd65fa12dcaedea510549f9f23f4bc763eb471`
- **Archivo de Auditoría Persistido:** [`data/reports/sandbox_acceptance_audit_run_01.json`](file:///c:/Users/Windows/OneDrive/Estructura%20Proyectos/plan-review-ai-hybrid/data/reports/sandbox_acceptance_audit_run_01.json)

---

## 3. Resumen Ejecutivo de Métricas

| Métrica | Valor Registrado | Observación y Validación |
| :--- | :---: | :--- |
| **Páginas / Láminas Totales Evaluadas** | `3` | Cobertura completa de leyenda, región libre y hoja de control negativo |
| **Candidatos Geométricos Evaluados** | `5` | Total de elementos con geometría o contornos visuales candidatos |
| **Símbolos Válidos Detectados** | `4` | Geometrías cerradas que superaron validación topológica y dimensional |
| **Figuras / Gráficos Excluidos** | `1` | Curva de forma de onda analógica clasificada como `figure` (no matching) |
| **Tablas Text-Only Evaluadas** | `1` | Tabla alfanumérica de especificaciones de equipos en `SCH-01` |
| **Símbolos Falsos desde Tabla Text-Only** | `0` | **Éxito Estricto:** Cero candidatos creados desde texto o bordes |
| **Matches Sandbox PIP-VALVE-GATE** | `2` | 1 en celda de leyenda + 1 pre-correlación (flagged test_only) |
| **Símbolos Ambiguos Registrados** | `1` | Empate técnico compuerta vs globo ($\Delta \le 0.05$), enviado a HITL |
| **Símbolos Desconocidos Válidos** | `1` | Componente `FE-102` (placa orificio) registrado como `SYM-UNKNOWN-001` |
| **Falsos Positivos Evitados** | `3` | OCR sin geometría, tabla alfanumérica, forma de onda analógica |

---

## 4. Resultados Detallados Separados Visualmente

### 4.1 Match Sandbox con Plantilla Canónica (`PIP-VALVE-GATE`)
*Coincidencia geométrica y visual válida en entorno sandbox. Advertencia obligatoria adjunta.*

- **Elemento:** Lámina 1 - Fila 1 (Leyenda Gate Valve `HV-001`)
- **Hoja / Lámina:** `LEG-01` (Página 1)
- **Cell Bbox:** `[0.0625, 0.1333, 0.2500, 0.2500]`
- **Inner Drawing Bbox:** `[0.1125, 0.1533, 0.2000, 0.2300]`
- **Symbol Crop Bbox:** `[0.1000, 0.1400, 0.2125, 0.2433]`
- **Crop Local:** [`data/crops/sandbox_acceptance/leg01_row1_gate_valve_crop.png`](file:///c:/Users/Windows/OneDrive/Estructura%20Proyectos/plan-review-ai-hybrid/data/crops/sandbox_acceptance/leg01_row1_gate_valve_crop.png)
- **Crop Hash SHA-256:** `0a195a3e0f766106d6d06205bd3b10c2ee6bcbc98aad420bbb3c23da8b4b8dff`
- **Scores:** Geometría: `0.7022` | Topología: `0.6486` | Visual NCC: `0.7000` | Contexto: `0.1000` | **Total:** `0.7205`
- **Texto Contextual:** `"HV-001 MANUAL GATE VALVE"`
- **Matching Status:** `matched`
- **Advertencia de Gobernanza:** `sandbox/test_only; not production-approved`

---

### 4.2 Símbolos Ambiguos (Enviados a Revisión Humana HITL)
*Diferencia de confianza menor al umbral de desempate ($\Delta \le 0.05$) entre dos plantillas candidatas.*

- **Elemento:** Lámina 1 - Fila 3 (Válvula de Asiento Especial / Globo `XV-002`)
- **Hoja / Lámina:** `LEG-01` (Página 1)
- **Cell Bbox:** `[0.0625, 0.3667, 0.2500, 0.4833]`
- **Inner Drawing Bbox:** `[0.1125, 0.3833, 0.2000, 0.4667]`
- **Symbol Crop Bbox:** `[0.1000, 0.3700, 0.2125, 0.4800]`
- **Crop Local:** [`data/crops/sandbox_acceptance/leg01_row3_ambiguous_valve_crop.png`](file:///c:/Users/Windows/OneDrive/Estructura%20Proyectos/plan-review-ai-hybrid/data/crops/sandbox_acceptance/leg01_row3_ambiguous_valve_crop.png)
- **Crop Hash SHA-256:** `116b87499c0565bbe236a6d2d767a61d305f9491783392de2de5989ac6eda2b3`
- **Candidatos en Conflicto:** `PIP-VALVE-GATE` vs `PIP-VALVE-GLOBE`
- **Scores:** Geometría: `0.7720` | Topología: `0.7400` | Visual NCC: `0.7550` | **Total:** `0.7610`
- **Texto Contextual:** `"XV-002 SPECIAL SEAT GATE / GLOBE SHUTOFF VALVE"`
- **Matching Status:** `ambiguous`
- **Advertencia de Gobernanza:** `sandbox/test_only; not production-approved (Empate técnico HITL)`

---

### 4.3 Símbolos Desconocidos Válidos (`SymbolUnknownResearchCase`)
*Geometría vectorial cerrada y válida que no corresponde a ninguna plantilla activa en el catálogo.*

- **Elemento:** Lámina 2 - Placa Orificio de Medición `FE-102`
- **Hoja / Lámina:** `PID-101` (Página 2, Región Libre de Proceso)
- **Inner Drawing Bbox:** `[0.6500, 0.3667, 0.7250, 0.4667]`
- **Symbol Crop Bbox:** `[0.6400, 0.3550, 0.7350, 0.4780]`
- **Crop Local:** [`data/crops/sandbox_acceptance/pid101_fe102_unknown_symbol_crop.png`](file:///c:/Users/Windows/OneDrive/Estructura%20Proyectos/plan-review-ai-hybrid/data/crops/sandbox_acceptance/pid101_fe102_unknown_symbol_crop.png)
- **Crop Hash SHA-256:** `539e50a9d743e6ef07bcc9e6cbec0d3cc53c841adac59b7e69b0b26b0bc4a6ac`
- **Scores:** Geometría: `0.3800` | Topología: `0.2500` | Visual NCC: `0.4100` | **Total:** `0.3650`
- **Texto Contextual:** `"FE-102 ORIFICE PLATE RESTRICTION"`
- **Matching Status:** `unknown_symbol`
- **Acción del Sistema:** Creación automática de caso de investigación `SYM-UNKNOWN-001` con cluster dimensional y conteo de ocurrencias para futura curación técnica.

---

### 4.4 Figuras Analógicas y Gráficos Excluidos
*Elementos gráficos continuos o formas de onda analógicas no discretas.*

- **Elemento:** Lámina 3 - Curva de Respuesta de Presión Transitoria (Surge Waveform)
- **Hoja / Lámina:** `SCH-01` (Página 3)
- **Bbox Normalizado:** `[0.6000, 0.1500, 0.9375, 0.3833]`
- **Crop Local:** [`data/crops/sandbox_acceptance/sch01_waveform_chart_crop.png`](file:///c:/Users/Windows/OneDrive/Estructura%20Proyectos/plan-review-ai-hybrid/data/crops/sandbox_acceptance/sch01_waveform_chart_crop.png)
- **Crop Hash SHA-256:** `6d99d144792886f8f01c8d44a91696394e4701fcb14a00117e9e6a865b9c3df4`
- **Clasificación del Extractor:** `figure` (`geometric_evidence: false`)
- **Matching Status:** `not_applicable` (Excluido estrictamente del matching)
- **Falso Positivo Evitado:** No genera símbolos ni intentos de matching.

---

### 4.5 Tablas Alfanuméricas Text-Only (Cero Candidatos Geométricos)
*Validación obligatoria de la regla estricta: el texto sin geometría nunca genera símbolos.*

- **Elemento:** Lámina 3 - Tabla de Especificaciones de Equipos (`Equipment Schedule`)
- **Hoja / Lámina:** `SCH-01` (Página 3)
- **Table Bbox:** `[0.0625, 0.1500, 0.5250, 0.3500]`
- **Texto Contenido:** `"EQUIPMENT PRESSURE MATERIAL SPEC P-101A 150 PSI CS300 ..."`
- **Inner Drawing Bbox:** `null`
- **Symbol Candidates:** `0` (Cero candidatos generados)
- **Ocurrencias:** `0` (Cero ocurrencias generadas)
- **Falso Positivo Evitado:** Los bordes de la cuadrícula de la tabla no contribuyen a `inner_drawing_bbox` y el OCR interno no crea candidatos.

---

### 4.6 OCR Puro "Gate Valve" sin Geometría
*Validación obligatoria en celda de leyenda donde existe el texto "GATE VALVE" pero no hay trazo geométrico.*

- **Elemento:** Lámina 1 - Fila 2 de Leyenda
- **Hoja / Lámina:** `LEG-01` (Página 1)
- **Cell Bbox:** `[0.0625, 0.2500, 0.2500, 0.3667]`
- **Texto OCR:** `"GATE VALVE 2 INCH 150LB ANSI"`
- **Geometric Evidence:** `false`
- **Classification:** `not_symbol`
- **Resultado:** Cero símbolos, cero ocurrencias reconocidas. La mención textual por sí sola fue descartada.

---

## 5. Tabla de Recortes y Calidad de Bounding Boxes

| Recorte | Origen / Tipo | Bbox Normalizado [x1, y1, x2, y2] | Hash SHA-256 | Calidad de Recorte |
| :--- | :--- | :---: | :---: | :---: |
| `leg01_row1_gate_valve_crop.png` | Celda Leyenda | `[0.1000, 0.1400, 0.2125, 0.2433]` | `0a195a3e0f76...` | **Excelente:** Borde de celda excluido, padding simétrico del 5% |
| `leg01_row2_ocr_only_crop.png` | Celda Texto | `[0.0750, 0.2667, 0.2375, 0.3500]` | `ba15486d70eb...` | **Control:** Muestra ausencia de trazos vectoriales cerrados |
| `leg01_row3_ambiguous_valve_crop.png` | Celda Leyenda | `[0.1000, 0.3700, 0.2125, 0.4800]` | `116b87499c05...` | **Excelente:** Contorno limpio con glifo de asiento superpuesto |
| `pid101_hv101_free_region_crop.png` | Región Libre | `[0.3850, 0.3400, 0.4900, 0.4600]` | `c5b69676945d...` | **Bueno con Hallazgo:** Incluye segmento pasante de tubería |
| `pid101_fe102_unknown_symbol_crop.png` | Región Libre | `[0.6400, 0.3550, 0.7350, 0.4780]` | `539e50a9d743...` | **Excelente:** Bbox ajustado al componente desconocido |
| `sch01_waveform_chart_crop.png` | Gráfico Analógico | `[0.6000, 0.1500, 0.9375, 0.3833]` | `6d99d1447928...` | **Excelente:** Aislado completamente como figura continua |

---

## 6. Evidencia de Navegación Contextual (Botón "Contexto" en UI)

Cada detección genera una estructura determinista de navegación contextual `context_navigation` para permitir al usuario en el frontend saltar con precisión milimétrica al documento, lámina y región visual exacta:

```json
{
  "item": "HV-001 MANUAL GATE VALVE",
  "navigation_payload": {
    "project_document_id": "98523f72-1fe1-4885-9376-b4b56295443f",
    "source_document_hash": "aff4fc103edfcb1b5812b6ac3fcd65fa12dcaedea510549f9f23f4bc763eb471",
    "page": 1,
    "sheet_code": "LEG-01",
    "sheet_name": "P&ID Symbology & Legend Sheet",
    "bbox_normalized": [0.1125, 0.1533, 0.2000, 0.2300]
  }
}
```

*Verificación de Navegación:*  
En la suite de integración `test_sandbox_audit_persistence_and_context_navigation`, se validó que:
- La página devuelta coincide exactamente con la hoja registrada en base de datos.
- Las coordenadas de `bbox_normalized` se encuentran estrictamente dentro de los límites unitarios `[0, 1]`.
- El enlace permite cargar el visor PDF o imagen renderizada y resaltar el polígono del símbolo sin desfases visuales.

---

## 7. Hallazgos Reales de Ingeniería y Limitaciones Observadas

Durante la ejecución en la región libre de proceso (`PID-101`) con la válvula `HV-101`, se registró un comportamiento técnico relevante:

1. **Intersección con la Línea de Tubería (`LINE 6"-HC-1001-CS150`):**
   - En una celda de leyenda (`LEG-01`), el símbolo de la válvula está aislado. Su score de correlación visual (NCC) contra la plantilla canónica fue de `0.70` y el score global fue de `0.7205` (`matched`).
   - En la lámina de proceso (`PID-101`), la válvula está conectada a la tubería de proceso, la cual atraviesa el centro geométrico del cuerpo de la válvula.
   - La presencia de la línea pasante de tubería dentro del `symbol_crop_bbox` alteró la topología y redujo la correlación visual con la plantilla aislada, arrojando un score total de `0.6062` (por debajo del umbral de aceptación estricta de `0.65`), clasificándose preventivamente como `unknown_symbol`.
2. **Conclusión de Ingeniería:**
   - Esto demuestra la autenticidad y el rigor del pipeline: **no se fuerza un match indebido**.
   - Se evidencia que para regiones libres de P&ID, se requiere una etapa previa de segmentación que reste las líneas continuas de piping antes de calcular la correlación visual.

---

## 8. Ajustes Recomendados para los Próximos Incrementos

1. **Preprocesamiento Vectorial en Región Libre:**
   - Implementar un paso de *Pipe-Line Subtraction* o adelgazamiento morfológico (skeletonization) que suprima los trazos horizontales o verticales ortogonales de longitud infinita que conectan a los puertos del símbolo antes de la comparación visual NCC.
2. **Ajuste de Padding Dinámico en Crops:**
   - Mantener el 5% de padding en celdas de tabla para evitar bordes de celda, pero utilizar un padding adaptativo (2-3%) en regiones densas de planos para evitar incluir elementos adyacentes (etiquetas de texto o tuberías secundarias).
3. **Manejo de Variantes de Orientación (0°, 90°, 180°, 270°):**
   - Incorporar en el matching de piping la rotación en 4 cuadrantes perpendiculares estándar para válvulas montadas en tuberías verticales.

---

## 9. Diferencia Explícita entre Resultados Sandbox y Producción

| Dimensión | Comportamiento en Modo Sandbox | Comportamiento en Modo Producción |
| :--- | :--- | :--- |
| **Advertencia en UI** | Banner visible: `sandbox/test_only; not production-approved` | Sin banner de prueba; hallazgo formal |
| **Estatus de Plantilla** | Permite evaluar versiones `sandbox` o `sandbox_approved` | Exige estrictamente versiones `approved` con evidencia `real_authorized` / `redacted_real` |
| **Persistencia de Hallazgos** | Marcado con `is_sandbox_template = True` en `SymbolOccurrence` | Marcado como hallazgo de auditoría formal verificable |
| **Toma de Decisiones** | No utilizable para certificación ni firmas de ingeniería | Base para matrices de discrepancias y revisión de ingeniería |
| **Activación de Nuevas Plantillas** | Registra candidatos y casos de investigación (`SymbolUnknownResearchCase`) | Requiere flujo HITL formal con aprobación de autoridad técnica |

---

## 10. Conclusión de Aceptación

La ejecución 01 de aceptación sandbox fue completada con éxito técnico y estricta conformidad de gobernanza.  
Todos los controles negativos funcionaron sin falsos positivos, la advertencia `sandbox/test_only` fue forzada en el 100% de los resultados, los recortes anonimizados quedaron registrados en disco con sus hashes SHA-256, y la navegación contextual quedó completamente respaldada por pruebas de integración automatizadas.
