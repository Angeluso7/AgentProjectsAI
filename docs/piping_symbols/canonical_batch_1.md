# Lote Canónico Inicial - Simbología de Piping e Instrumentación (Fase 2)

**Fecha de Consolidación:** Septiembre 2026  
**Disciplina:** Piping / Mecánica de Procesos / Instrumentación y Control  
**Normas de Referencia:** ISA-5.1-2009 / ASME B16.34 / API 609 / ISO 10628  
**Gobernanza:** Curación Asistida HITL (Human-in-the-Loop) & Auditoría Trazable  

---

## 1. Resumen Ejecutivo del Lote Canónico

En cumplimiento de la **Condición 5 de la Fase 2**, la plataforma consolida su primer lote gobernado y reutilizable de símbolos de piping e instrumentación, promovidos a `SymbolTemplate` (`template_memory`).

Este lote canónico no es un mero listado de nombres, sino una colección estructurada que incorpora:
- Descriptores geométricos y físicos normalizados en milímetros (mm).
- Huellas digitales visuales (`dHash` de 64 bits horizontal).
- Agrupación por familias ontológicas y variantes visuales (`visual_variant_group_id`).
- Trazabilidad y auditoría de aprobación humana (`approved_by`, `approved_at`, `notes`).

---

## 2. Inventario de Símbolos Curados (Lote 1)

| # | Clase Canónica (`symbol_class`) | Nombre Técnico Oficial | Familia | Norma | Dimensiones Físicas (mm) | Grupo Variante (`visual_variant_group_id`) | Auditor Aprobador |
|---|---|---|---|---|---|---|---|
| 1 | `gate_valve` | Válvula de Compuerta Manual ASME B16.34 | `valves` | ASME B16.34 / API 600 | 10.5 x 8.0 mm | `VVG-VALVE-GATE-01` | Ingeniero Revisor Piping |
| 2 | `globe_valve` | Válvula de Globo para Regulación de Caudal | `valves` | ASME B16.34 | 10.5 x 8.0 mm | `VVG-VALVE-GLOBE-01` | Ingeniero Revisor Piping |
| 3 | `check_valve` | Válvula de Retención / Check Tipo Columpio | `valves` | ASME B16.34 / API 594 | 10.5 x 7.0 mm | `VVG-VALVE-CHECK-01` | Ingeniero Revisor Piping |
| 4 | `ball_valve` | Válvula de Bola de Paso Total | `valves` | ASME B16.34 / API 608 | 10.5 x 8.0 mm | `VVG-VALVE-BALL-01` | Ingeniero Revisor Piping |
| 5 | `butterfly_valve` | Válvula de Mariposa Wafer Tipo Eje Concéntrico | `valves` | API 609 / ASME B16.34 | 10.0 x 8.0 mm | `VVG-VALVE-BUTTERFLY-01` | Ingeniero Revisor Piping |
| 6 | `control_valve` | Válvula de Control con Actuador Neumático Diafragma | `valves` | ISA-5.1 / IEC 60534 | 12.0 x 18.0 mm | `VVG-VALVE-CONTROL-01` | Ingeniero Revisor Piping |
| 7 | `pressure_transmitter` | Transmisor de Presión Montado en Campo (PT-101) | `instruments` | ISA-5.1 | 9.0 x 9.0 mm | `VVG-INST-PT-01` | Ingeniero Revisor Instrumentación |
| 8 | `temperature_transmitter` | Transmisor de Temperatura Montado en Campo (TT-102) | `instruments` | ISA-5.1 | 9.0 x 9.0 mm | `VVG-INST-TT-01` | Ingeniero Revisor Instrumentación |

---

## 3. Especificación Detallada por Componente

### 3.1. Válvula de Compuerta (`gate_valve`)
- **Geometría:** Dos triángulos simétricos opuestos por el vértice con línea de vástago perpendicular y volante horizontal superior.
- **Aspect Ratio:** 1.31 (10.5 mm / 8.0 mm).
- **dHash (64-bit):** `e0e0f0f00f0f0707`.
- **Aliases Aceptados:** `gate valve`, `válvula de compuerta`, `compuerta manual`, `compuerta bridada`.
- **Uso en Detección:** Símbolo patrón para aislamiento en líneas principales de proceso.

### 3.2. Válvula de Globo (`globe_valve`)
- **Geometría:** Dos triángulos opuestos con un círculo oscuro central que representa el tapón cónico de regulación.
- **Aspect Ratio:** 1.31 (10.5 mm / 8.0 mm).
- **dHash (64-bit):** `f0f0e0e007070f0f`.
- **Aliases Aceptados:** `globe valve`, `válvula de globo`, `válvula de aguja o regulación`.
- **Uso en Detección:** Distingue estrangulación de caudal frente al corte neto de la compuerta.

### 3.3. Válvula de Retención / Check (`check_valve`)
- **Geometría:** Dos triángulos con línea diagonal de retención o clapeta interior orientada según el sentido de flujo.
- **Aspect Ratio:** 1.50 (10.5 mm / 7.0 mm).
- **dHash (64-bit):** `cccc3333cccc3333`.
- **Aliases Aceptados:** `check valve`, `válvula check`, `válvula de retención`, `non-return valve`.
- **Uso en Detección:** Protección de equipos de bombeo y prevención de reflujo.

### 3.4. Válvula de Bola (`ball_valve`)
- **Geometría:** Dos triángulos opuestos con un círculo blanco interior concéntrico que representa la esfera hueca.
- **Aspect Ratio:** 1.31 (10.5 mm / 8.0 mm).
- **dHash (64-bit):** `a5a55a5aa5a55a5a`.
- **Aliases Aceptados:** `ball valve`, `válvula de bola`, `válvula esférica`, `1/4 turn valve`.
- **Uso en Detección:** Aislamiento rápido en servicios limpios y de instrumentación.

### 3.5. Válvula de Mariposa (`butterfly_valve`)
- **Geometría:** Línea perpendicular que cruza el cuerpo valvular con extremos tipo wafer.
- **Aspect Ratio:** 1.25 (10.0 mm / 8.0 mm).
- **dHash (64-bit):** `1f1f8e8e1f1f8e8e`.
- **Aliases Aceptados:** `butterfly valve`, `válvula mariposa`, `wafer butterfly`.
- **Uso en Detección:** Válvulas de gran diámetro y peso reducido entre bridas.

### 3.6. Válvula de Control Diafragma (`control_valve`)
- **Geometría:** Cuerpo de válvula genérico vinculado por vástago vertical a un sombrerete semicircular o trapezoidal con diafragma interno.
- **Aspect Ratio:** 0.67 (12.0 mm / 18.0 mm) - Predominancia vertical.
- **dHash (64-bit):** `7e7e81817e7e8181`.
- **Aliases Aceptados:** `control valve`, `válvula de control`, `válvula automática con actuador`, `FCV`, `PCV`, `TCV`.
- **Uso en Detección:** Lazos de control analógicos en P&ID según ISA-5.1.

### 3.7. Transmisores de Proceso (PT-101 y TT-102)
- **Geometría:** Círculo (burbuja) de 9 mm de diámetro, línea perimetral continua sin raya horizontal divisoria (indica montaje local en campo).
- **Aspect Ratio:** 1.0 (cuadrado / circular).
- **dHash (64-bit):** `00ffff0000ffff00` (PT) / `00f00f0000f00f00` (TT).
- **Asociación OCR:** Detección y emparejamiento con el texto interior de dos letras (P = Presión, T = Transmisor; T = Temperatura, T = Transmisor).
- **Uso en Detección:** Identificación de instrumentación de campo y trazabilidad de lazos de automatización.

---

## 4. Trazabilidad de Auditoría en `template_memory`

Cada registro en `SymbolTemplate` almacena en su campo JSON `feature_descriptors` la auditoría exigida por la **Condición 4**:
```json
{
  "source": "canonical_batch_phase2",
  "canonical_symbol_family": "valves",
  "discipline": "piping",
  "reference_standard": "ASME B16.34 / API 600",
  "visual_variant_group_id": "VVG-VALVE-GATE-01",
  "dhash_64": "e0e0f0f00f0f0707",
  "aliases": ["gate valve", "valvula compuerta", "valvula de compuerta"],
  "estimated_physical_size_mm": {
    "width_mm": 10.5,
    "height_mm": 8.0
  },
  "aspect_ratio": 1.31,
  "approval_audit": {
    "approved_by": "Ingeniero Revisor Piping (Senior HITL)",
    "approved_at": "2026-09-04T18:27:00Z",
    "validation_notes": "Lote inicial canónico aprobado según ASME B16.34 Clase 150 RF."
  }
}
```

---

## 5. Próximos Pasos (Hacia Fase 3)

1. **Ingesta de Láminas Adicionales:** Incorporar láminas de leyenda de otras firmas de ingeniería para registrar variantes visuales adicionales asociadas a los mismos `visual_variant_group_id`.
2. **Matching Masivo Multi-Factor:** Conectar este catálogo canónico como target de matching (visual + semántico + geométrico) sobre planos P&ID de plantas completas.
3. **Optimización de Bundle:** Aplicar code-splitting en `SymbolCurationStudioModal` y librerías auxiliares (deuda técnica registrada).
