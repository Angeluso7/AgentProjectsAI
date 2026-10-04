# Plan Review AI Hybrid — Manual de Usuario y Operación

> **Documento**: 02_manual_de_usuario_y_operacion.md  
> **Audiencia**: Auditores Técnicos, Revisores Independientes, Jefes de Taller, Operadores  
> **Propósito**: Guía operativa paso a paso para utilizar el sistema, interpretar resultados y resolver triage técnico.

---

## 1. Flujograma de Operación del Usuario

```mermaid
flowchart TD
    A[1. Inicio de Sesión\nSelección de Organización] --> B[2. Registro de Proyecto\ny Disciplina]
    B --> C[3. Carga de Planos PDF\n(Validación de Integridad)]
    C --> D[4. Lanzamiento de One-Click Review\n(Ejecución de Pipeline)]
    D --> E{¿Hay Review Tasks\npendientes?}
    E -- Sí (Incertidumbre) --> F[5. Triage Humano / HITL\n(Aprobar / Descartar)]
    E -- No --> G[6. Inspección de Hallazgos\n(RuleFindings & Severidades)]
    F --> G
    G --> H[7. Generación de Informe\nPDF + JSON + Evidence Bundle]
    H --> I[8. Descarga y Envío a Titular\n(Previa Validación Profesional)]
```

---

## 2. Requisitos Previos y Preparación de Archivos PDF

Para maximizar la precisión de extracción, asegúrate de que los archivos PDF cumplan con las siguientes recomendaciones:

| Parámetro | Recomendación Óptima | Aceptable con Advertencia | No Recomendado |
| :--- | :--- | :--- | :--- |
| **Origen del PDF** | Exportado directamente desde CAD/BIM (vectorial). | Escaneo nítido a 300 DPI en escala de grises. | Fotos de celular o capturas de pantalla de baja resolución. |
| **Orientación** | Lámina horizontal o vertical estándar sin rotación invertida. | Lámina rotada a 90° (el sistema detecta rotación en OCR). | Planos escaneados con inclinación angular oblicua. |
| **Texto de Viñeta** | Tipografía estándar TrueType/OpenType (Arial, Romans, ISOCP). | Texto caligráfico o manuscrito. | Texto explotado en líneas vectoriales sin caracteres. |
| **Escala** | Escala gráfica o numérica explícita en viñeta (e.g., 1:50, 1:100). | Escala declarada en texto de notas. | Sin escala declarada (las cotas absolutas serán relativas). |

---

## 3. Estados del Sistema y su Significado

Durante el ciclo de vida de un plano o una corrida de revisión, encontrarás los siguientes estados:

```
[queued] ──> [running] ──> [awaiting_review] ──> [completed]
                 │                                    │
                 ├──> [partially_completed]           └──> [insufficient_evidence]
                 └──> [failed]
```

| Estado | Significado Técnico | Acción Requerida por el Usuario |
| :--- | :--- | :--- |
| **`queued`** | El trabajo está en cola esperando un worker disponible. | Esperar unos segundos a que inicie el procesamiento. |
| **`running`** | El pipeline está ejecutando etapas (OCR, tablas, símbolos o reglas). | Monitorear el porcentaje de avance en pantalla. |
| **`awaiting_review`** | Se detectó baja confianza en algún dato crítico (e.g. cota dudosa). | Ir a la pestaña **Triage & Revisión (HITL)** para resolver la tarea. |
| **`completed`** | El plano fue auditado completamente y el informe está listo. | Revisar los hallazgos y descargar el paquete de auditoría. |
| **`partially_completed`**| Algunas etapas concluyeron pero una regla secundaria falló. | Inspeccionar qué etapa arrojó advertencia en el visor de logs. |
| **`insufficient_evidence`**| La regla no pudo emitir juicio porque falta información en el plano. | Verificar si falta subir láminas complementarias (e.g. cuadro de puertas). |
| **`failed`** | Ocurrió un error no controlado (e.g. PDF corrupto o sin permisos). | Consultar la sección de troubleshooting y reintentar con el archivo corregido. |

---

## 4. Interpretación de Hallazgos (*RuleFindings*) y Severidades

Cada observación generada por el motor de reglas se clasifica según su impacto técnico y normativo:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   CRITICAL   │     │     HIGH     │     │    MEDIUM    │     │  LOW / INFO  │
│  Infracción  │     │ Incumplimien-│     │ Discrepancia │     │  Omisión de  │
│ que impide la│     │ to normativo │     │ geométrica o │     │ formato o    │
│  recepción   │     │ de seguridad │     │  tabular     │     │ recomendación│
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

- **`CRITICAL` (Crítica)**: Infracción legal severa que impide la aprobación o recepción de la obra (e.g., ausencia total de salidas de emergencia, altura de evacuación inferior a norma obligatoria).
- **`HIGH` (Alta)**: No-conformidad técnica relevante (e.g., ancho de puerta de escape menor a $0.90\text{ m}$, discrepancia mayor en cuadro de cargas eléctricas).
- **`MEDIUM` (Media)**: Desalineación entre plano y tabla (e.g., el cuadro indica 14 ventanas pero se dibujaron 12; error de rotulación en viñeta).
- **`LOW` (Baja)**: Inconsistencia menor de graficación (e.g., escala gráfica desfasada respecto a escala numérica).
- **`INFO` (Informativa)**: Nota técnica o cálculo automático exitoso para constancia en el expediente.

---

## 5. Guía de Acción ante Situaciones Especiales

### A. ¿Qué hacer si el sistema no detecta bien un texto o tabla?
1. Abre la lámina en el **Visor de Planos & Overlays**.
2. Activa la capa **OCR / Layout** para verificar si la región fue reconocida.
3. Si el texto tiene bajo contraste o es un PDF rasterizado muy comprimido, genera una nueva versión en PDF vectorial desde el software CAD original.

### B. ¿Qué hacer si el sistema genera demasiadas observaciones dudosas?
1. Revisa si el plano tiene una disciplina incorrecta asignada (e.g., un plano de estructuras evaluado con reglas de arquitectura).
2. Ajusta la **Política de Confianza** en la configuración de la organización para requerir mayor certeza antes de disparar alertas.

### C. ¿Qué hacer si el pipeline queda en estado `awaiting_review`?
1. Dirígete a la pestaña **Triage & Revisión (HITL)**.
2. Selecciona la tarea pendiente: el sistema mostrará el recorte visual exacto del plano al lado del valor sugerido.
3. Opciones de resolución:
   - **Aprobar**: Confirma el dato extraído.
   - **Corregir**: Escribe el valor correcto si el OCR tuvo un error de un dígito.
   - **Descartar**: Si se trataba de una anotación no relevante o un falso positivo.
   - **Aceptar Riesgo**: Si el proyecto contempla una excepción justificada.

---

## 6. Checklists de Operación

### Checklist 1: "Antes de Correr el Pipeline"
- [ ] El PDF corresponde a la versión final aprobada para revisión (no preliminar).
- [ ] La lámina tiene viñeta legible con código de plano y escala declarada.
- [ ] El proyecto y la disciplina correcta están seleccionados en el sistema.
- [ ] El usuario activo cuenta con rol `contributor`, `reviewer` o `audit_lead`.

### Checklist 2: "Antes de Compartir el Reporte con Terceros"
- [ ] Todas las tareas en estado `awaiting_review` han sido resueltas en el Triage HITL.
- [ ] Los hallazgos con severidad `CRITICAL` y `HIGH` han sido inspeccionados visualmente por el auditor responsable.
- [ ] El paquete de auditoría ZIP incluye el manifiesto de evidencia con hashes SHA-256 intactos.
- [ ] El informe PDF cuenta con el visto bueno del profesional competente a cargo.

---

## 7. Matriz de Errores Comunes de Uso

| Error de Uso | Consecuencia | Corrección Inmediata |
| :--- | :--- | :--- |
| **Subir PDF escaneado a 72 DPI** | Fallos en lectura OCR y caracteres borrosos. | Re-escanear a 300 DPI o exportar directamente en PDF vectorial. |
| **Seleccionar disciplina incorrecta** | Reglas no aplicables generarán falsas no-conformidades. | Editar las propiedades del documento y re-ejecutar el pipeline. |
| **Ignorar tareas de Triage HITL** | El informe final quedará incompleto con estado `insufficient_evidence`. | Completar la bandeja de Triage antes de emitir el reporte. |
| **Asumir que el reporte es una aprobación legal automática** | Riesgo legal para la oficina de arquitectura o ingeniería. | Siempre someter el informe al juicio y firma del profesional colegiado. |
