# Diagramas de Flujo del Asistente y Procesos del Sistema

> **Documento de Especificación Visual de Flujos de Trabajo**  
> **Versión de la Plataforma:** v0.3.0  
> **Propósito:** Representación gráfica completa de todos los flujos de decisión, percepción, interacción y aprendizaje del Asistente Operacional y los módulos de Plan Review AI Hybrid.

---

## 1. Flujo General del Proyecto con Intervención del Asistente

```mermaid
flowchart TD
    Start([Inicio: Creación de Proyecto]) --> Intake[Intake de Fuentes Normativas y Planos PDF]
    Intake --> Raster[Rasterizado 150 DPI y Segmentación de Láminas]
    
    subgraph PreAuditoria["Fase 1: Pre-Auditoría & Completitud"]
        Raster --> GatekeeperCheck{¿Completitud de Entregables OK?}
        GatekeeperCheck -- No --> Blocker[Gatekeeper Bloquea Etapa / Asistente Alerta Faltantes]
        Blocker --> RequestDocs[Solicitud de Documentos Faltantes]
        RequestDocs --> Intake
        GatekeeperCheck -- Sí --> MaturityEval[Evaluación Inicial de Madurez Informacional]
    end
    
    subgraph AuditoriaPerceptual["Fase 2: Percepción & Reglas QA/QC"]
        MaturityEval --> ExecPipe[Ejecutar Pipeline Híbrido: OCR + Layout + Tablas + Símbolos]
        ExecPipe --> RulesEval[Evaluación de 6 Reglas QA/QC Determinísticas]
        RulesEval --> GenFindings[Generación de Hallazgos y Decision Traces]
    end
    
    subgraph CopilotHITL["Fase 3: Asistente Copilot & Triage Humano (HITL)"]
        GenFindings --> Copilot[Asistente Copilot: RAG Activo + Tareas Asistidas]
        Copilot --> AuditorTriage{Revisión del Auditor}
        AuditorTriage -- Aceptar Hallazgo --> MarkAccepted[Hallazgo Aceptado -> Observación Formal]
        AuditorTriage -- Falso Positivo --> LearnFP[Registrar Corrección -> Memoria de Aprendizaje]
        AuditorTriage -- Ajustar Geometría --> FixBBox[Actualizar Bounding Box en DB]
    end
    
    subgraph CierreEtapa["Fase 4: Cierre, Madurez y Emisión de Snapshot"]
        MarkAccepted & LearnFP & FixBBox --> ReevalMaturity[Reevaluación de Madurez y Veredicto Global]
        ReevalMaturity --> SnapshotEmit[Emisión de Snapshot de Etapa con Hash SHA-256]
        SnapshotEmit --> End([Fin de Revisión / Descarga de Acta PDF])
    end
```

---

## 2. Flujo de Intake e Incorporación de Fuentes

```mermaid
flowchart TD
    UserUpload[Usuario sube Archivo: PDF, DXF, Imagen o Texto] --> PostIntake[POST /api/v1/intake/sources o /documents/upload]
    
    PostIntake --> CheckType{¿Tipo de Documento?}
    
    CheckType -- Plano Técnico PDF --> SaveUpload["Guardar en /data/uploads/{uuid}.pdf"]
    SaveUpload --> CreateDoc[Crear Documento en DB: status='pending']
    CreateDoc --> RasterizeLoop[PyMuPDF: Rasterizar Láminas a PNG 150 DPI]
    RasterizeLoop --> SaveRaster["Guardar en /data/raster/{doc_id}_sheet_{num}.png"]
    SaveRaster --> RegSheets[Insertar registros en 'document_sheets']
    RegSheets --> DocReady[Documento Listo para Visor]
    
    CheckType -- Norma / Manual / Especificación --> SaveAsset[Crear registro 'source_assets']
    SaveAsset --> ExtractNorm[Extracción OCR / Texto de Artículos y Criterios]
    ExtractNorm --> NormItems[Crear NormativeDocument / NormativeClause]
    NormItems --> ModalReview[Modal de Revisión de Contenido Normativo]
    ModalReview --> UserApprove{¿Auditor Aprueba Criterio?}
    UserApprove -- Sí --> IngestKB[Ingestar en Base de Conocimiento: status='validated']
    UserApprove -- No --> RejectNorm[Marcar Descartado: status='rejected']
```

---

## 3. Flujo de Validación de Reglas y Paso hacia Baseline QA/QC

```mermaid
flowchart TD
    SheetSelected[Lámina Seleccionada en Visor] --> ExecRules[POST /api/v1/pipelines/execute-hybrid]
    
    subgraph PercepcionConsolidada["Extracción Perceptual"]
        ExecRules --> OCR[OCR: Bloques de Texto y Cotas]
        ExecRules --> Layout[Layout: Área de Dibujo y Viñeta]
        ExecRules --> Tables[Tablas: Cuadros de Vanos y Especificaciones]
        ExecRules --> Symbols[Símbolos: Puertas, Ventanas, Artefactos]
    end
    
    OCR & Layout & Tables & Symbols --> Consolidate[Consolidar Evidencias con Coordenadas Normalizadas 0..1]
    
    subgraph EvaluacionReglas["Motor Determinístico de Reglas"]
        Consolidate --> LoadRules[Cargar Reglas Activas de la Disciplina]
        LoadRules --> CrossCheck[Conciliación Geométrica vs Cuadros Tabulares]
        CrossCheck --> EvaluatePass{¿Cumple Criterio?}
        EvaluatePass -- Sí --> VerdictPass[Veredicto: 'Cumple Totalmente' o 'No Aplica']
        EvaluatePass -- No --> VerdictFail[Veredicto: 'No Cumple' o 'Cumple con Obs Menores']
    end
    
    VerdictPass --> TracePass[Registrar DecisionTrace Exitoso]
    VerdictFail --> CreateFinding[Crear RuleFinding con Severidad y Coordenadas de Recorte]
    CreateFinding --> LinkTrace[Vincular DecisionTrace con Justificación Matemática]
    LinkTrace --> ReviewQueue[Encolar en ReviewTasks para Triage HITL]
```

---

## 4. Flujo de Revisión Técnica por Etapas y Gatekeeper

```mermaid
flowchart TD
    SelectStage[Seleccionar Proyecto y Etapa de Revisión] --> FetchReqs[Obtener Matriz de Entregables de la Etapa]
    
    subgraph GatekeeperEval["Evaluación del Gatekeeper"]
        FetchReqs --> CheckDeliverables{¿Todos los Entregables Obligatorios Presentes?}
        CheckDeliverables -- No --> BlockStage[Estado: 'Bloqueada por Gatekeeper']
        BlockStage --> ListMissing[Listar Entregables Faltantes Críticos]
        ListMissing --> NotifyUser[Asistente Notifica Bloqueo y Genera Tarea de Carga]
        
        CheckDeliverables -- Sí --> PassGate[Gatekeeper Superado: 0 Bloqueos]
    end
    
    PassGate --> RunStageRules[Ejecutar Auditoría de Reglas QA/QC de la Etapa]
    RunStageRules --> AggregateFindings[Consolidar Hallazgos de Todas las Láminas]
    
    subgraph CalculoVeredictoGlobal["Cálculo del Veredicto Global de Etapa"]
        AggregateFindings --> CheckCritical{¿Existen Hallazgos Críticos No Resueltos?}
        CheckCritical -- Sí --> VNoAprobable[Veredicto Global: 'NO APROBABLE / BLOQUEADA']
        CheckCritical -- No --> CheckMinor{¿Existen Observaciones Menores?}
        CheckMinor -- Sí --> VAprobObs[Veredicto Global: 'APROBADA CON OBSERVACIONES MENORES']
        CheckMinor -- No --> VAprobTotal[Veredicto Global: 'APROBADA SIN OBSERVACIONES']
    end
```

---

## 5. Flujo de Uso de la Base de Conocimiento Operacional

```mermaid
flowchart TD
    QueryIn[Consulta de Usuario o Búsqueda del Asistente] --> FilterOrg[Filtrar por organization_id y project_id]
    
    FilterOrg --> FilterReuse[Filtro Estricto: is_active_for_reuse = True]
    FilterReuse --> FilterStatus[Filtro de Estado: 'approved_for_reuse' o 'validated']
    
    subgraph BusquedaVectorialContextual["Recuperación Contextual"]
        FilterStatus --> DomainFilter[Filtrar por Dominio: Normativa, Regla, Símbolo, etc.]
        DomainFilter --> DisciplineFilter[Filtrar por Disciplina: Arquitectura, Estructuras, etc.]
        DisciplineFilter --> TextScore[Calcular Similitud de Texto / Embeddings en Chunks]
    end
    
    TextScore --> MatchEval{¿Top Relevance Score >= 0.60?}
    MatchEval -- Sí --> ReturnApproved[Retornar Chunks Aprobados con Trazabilidad]
    MatchEval -- No --> FallbackAcq[Disparar Detección de Faltante en AcquisitionService]
```

---

## 6. Flujo RAG del Asistente Copilot

```mermaid
flowchart TD
    UserPrompt[Usuario ingresa Prompt o selecciona Tarea Asistida] --> ParseTask[Identificar task_type y Metadatos de Contexto]
    
    subgraph RAGGoverned["1. Recuperación Contextual RAG Gobernada"]
        ParseTask --> SearchKB[KnowledgeBaseService.search_knowledge]
        SearchKB --> MatchChunks[Recuperar Chunks Activos y Aprobados]
        MatchChunks --> InjectMaturity[Inyectar Score de Madurez y Gaps Críticos del Proyecto]
    end
    
    subgraph RoutingTier["2. Routing y Escalamiento de Motores IA"]
        InjectMaturity --> EvalTier[AiEngineRouter.evaluate_routing]
        EvalTier --> CheckTriggers{¿Activar Triggers de Escalamiento?}
        CheckTriggers -- Severidad Crítica / Bloqueo --> EscalateTier3[Escalar a Tier 3: GPT-4o]
        CheckTriggers -- RAG Débil (<0.40) --> EscalateTier2[Escalar a Tier 2: Gemini Flash]
        CheckTriggers -- Consulta Estándar --> KeepTier1[Mantener Tier 1: Local Reasoner]
    end
    
    subgraph InferenciaPersistencia["3. Inferencia y Trazabilidad"]
        EscalateTier3 & EscalateTier2 & KeepTier1 --> ExecModel[Ejecutar Inferencia del Motor Seleccionado]
        ExecModel --> GenResponse[Generar Respuesta Markdown + Salida Estructurada]
        GenResponse --> SaveInteraction[Insertar AssistantInteraction en DB con Chunks y Tier]
    end
    
    subgraph FeedbackHITL["4. Ciclo de Feedback Humano"]
        SaveInteraction --> ShowUI[Renderizar en Copilot Drawer con Fuentes y Confianza]
        ShowUI --> AuditorAction{Acción del Auditor}
        AuditorAction -- Aceptar --> StatusAccepted[feedback_status = 'accepted']
        AuditorAction -- Editar --> StatusEdited[feedback_status = 'edited' + Payload Modificado]
        AuditorAction -- Rechazar --> StatusRejected[feedback_status = 'rejected' + Nota Técnica]
    end
```

---

## 7. Flujo de Routing / Escalamiento entre Motores IA por Tiers

```mermaid
flowchart TD
    InRequest[Petición Asistida + Contexto de Proyecto] --> TaskLookup[Consultar TASK_BASE_POLICIES]
    
    TaskLookup --> BaseTier{¿Tier Base Asignado?}
    BaseTier -- Tareas Rápidas (Normativa, Símbolos, Clasificación) --> T1Base[Tier Base = 1]
    BaseTier -- Tareas Complejas (Redacción RFI, Apoyo Técnico, Síntesis) --> T2Base[Tier Base = 2]
    
    T1Base & T2Base --> CheckEscalation{¿Evaluar Triggers de Escalamiento?}
    
    CheckEscalation -- context.severity == 'critical' --> SetT3[Escalar a Tier 3: GPT-4o / Razón: critical_severity]
    CheckEscalation -- context.is_blocker == True --> SetT3_2[Escalar a Tier 3: GPT-4o / Razón: critical_document_blocker]
    CheckEscalation -- synthesis & verdict == 'no_aprobable' --> SetT3_3[Escalar a Tier 3: GPT-4o / Razón: blocked_stage_milestone]
    
    CheckEscalation -- Tier 1 y RAG Score < 0.40 --> SetT2[Escalar a Tier 2: Gemini Flash / Razón: insufficient_internal_rag]
    CheckEscalation -- Sin Triggers de Alarma --> KeepBase[Ejecutar en Tier Base sin Escalamiento]
    
    SetT3 & SetT3_2 & SetT3_3 --> ExecT3[Ejecutar Motor Tier 3: openai_gpt4o]
    SetT2 --> ExecT2[Ejecutar Motor Tier 2: google_gemini_flash]
    KeepBase --> ExecT1[Ejecutar Motor Tier 1: fastapi_rule_reasoner]
```

---

## 8. Flujo Web-First con Permiso Explícito

```mermaid
flowchart TD
    GapIn[Faltante Detectado en RAG Interno: Score < 0.60] --> CreateAcqReq[Crear InformationAcquisitionRequest: status='pending_permission']
    
    CreateAcqReq --> ShowPermissionModal[Mostrar Modal de Autorización de Búsqueda Web al Usuario]
    
    ShowPermissionModal --> UserDecision{¿Usuario Autoriza la Búsqueda?}
    
    UserDecision -- Rechazar --> MarkCancelled[permission_status = 'rejected' -> termination_reason = 'cancelled_by_user']
    MarkCancelled --> CloseReq[Cerrar Solicitud: Requiere Carga Manual de Documento]
    
    UserDecision -- Autorizar --> CheckLimits[Aplicar Límites: Max 3 Iteraciones / Max 5 Fuentes]
    CheckLimits --> ExecSearch[Ejecutar Google Search API con Términos Técnicos]
    ExecSearch --> ParseResults[Extraer Snippets, Títulos y Metadatos de Credibilidad]
    
    subgraph ScoringSuficiencia["Evaluación Matemática de Suficiencia"]
        ParseResults --> CalcRel[Relevance Score: Hits de Palabras Clave x 0.70 + 0.30]
        ParseResults --> CalcConf[Confidence Score: Promedio de Credibilidad de Fuentes]
        ParseResults --> CalcCov[Coverage Score: Aspectos Normativos Cubiertos / 6 + 0.25]
        CalcRel & CalcConf & CalcCov --> CalcAdequacy[Overall Adequacy = 0.40*Rel + 0.30*Conf + 0.30*Cov]
    end
    
    CalcAdequacy --> CheckAdequacy{¿Clasificación de Adecuación?}
    CheckAdequacy -- Sufficient (>=75% y Cov>=70%) --> SaveKnowledge[Guardar KnowledgeItem: status='extracted']
    CheckAdequacy -- Partially Sufficient (50-74%) --> SavePartial[Guardar KnowledgeItem Parcial -> Requiere Validación]
    CheckAdequacy -- Insufficient (<50% o Info Privada) --> EscalateDocReq[Escalar a Solicitud Documental de Proyecto]
```

---

## 9. Flujo de Solicitud de Documentación Adicional al Usuario

```mermaid
flowchart TD
    AcqFailed[Búsqueda Web Insuficiente o Necesidad Privada de Proyecto] --> BuildDiagnostic[Construir Diagnóstico de Escalamiento Documental]
    
    subgraph DiagnosticoEscalamiento["Estructura de la Solicitud"]
        BuildDiagnostic --> SetDocType[Tipo de Documento Requerido: ej. Memoria de Cálculo de Suelos]
        BuildDiagnostic --> SetResponsible[Responsable Sugerido: ej. Proyectista de Fundaciones]
        BuildDiagnostic --> SetImpact[Impacto en Auditoría: Bloqueo de Regla QA/QC Específica]
    end
    
    SetDocType & SetResponsible & SetImpact --> SaveEscalated[Actualizar InformationAcquisitionRequest: status='escalated']
    SaveEscalated --> UserAlert[Mostrar Alerta en UI y Copilot Drawer: 'Acción Requerida']
    
    UserAlert --> UserUploadNew[Usuario Sube Documento en Módulo Fuentes]
    UserUploadNew --> ProcessSource[IntakeService Procesa y Extrae Texto del Nuevo PDF]
    ProcessSource --> ReevaluateQuery[Reevaluar Consulta Original con Nuevo Documento]
    ReevaluateQuery --> ResolveGap[Faltante Resuelto -> Regla Desbloqueada]
```

---

## 10. Flujo de Captura desde el Visor hacia Conocimiento Reutilizable

```mermaid
flowchart TD
    ViewerBox[Usuario Dibuja Bounding Box en Visor de Planos] --> CropImage[Generar Recorte PNG Base64]
    
    CropImage --> FillMetadata[Modal: Asignar Nombre, Disciplina, Tipo y Leyenda Asociada]
    FillMetadata --> DeduplicationCheck[InformationAcquisitionService.check_visual_deduplication]
    
    subgraph DeduplicacionVisual["Motor de Deduplicación Visual"]
        DeduplicationCheck --> CompareSlugs[Comparar Slugs Canónicos y Similitud de Texto/Alias]
        CompareSlugs --> SimScore{¿Similitud con Catálogo Existente?}
        SimScore -- Similitud >= 85% --> SuggestLink[Sugerir: 'link_occurrence' a Ítem Existente]
        SimScore -- Similitud 70% a 84% --> SuggestVersion[Sugerir: 'new_version' del Ítem]
        SimScore -- Similitud < 70% --> SuggestNew[Sugerir: 'create_new' Entidad Canónica]
    end
    
    SuggestLink & SuggestVersion & SuggestNew --> UserChoice{Auditor Confirma Modo}
    
    UserChoice -- Vincular Ocurrencia --> AppendOcc[Añadir lámina y coordenadas a 'linked_occurrences' en ítem existente]
    UserChoice -- Nueva Versión --> CreateV2[Crear KnowledgeItem versión 2 vinculado a padre]
    UserChoice -- Crear Nuevo --> CreateNewItem[Crear nuevo KnowledgeItem: domain='symbol_knowledge']
    
    AppendOcc & CreateV2 & CreateNewItem --> SaveCropDisk["Guardar Archivo en /storage/crops/{doc}/{sheet}/{hash}.png"]
    SaveCropDisk --> SetActiveReuse[is_active_for_reuse = True -> Disponible para RAG Visual]
```

---

## 11. Flujo de Aprendizaje e Incorporación de Conocimiento Aprobado

```mermaid
flowchart TD
    AuditFeedback[Auditor Humano Corrige Falso Positivo o Ajusta Veredicto] --> CaptureLearning[Capturar Decisión en ReviewDecision y AssistantFeedback]
    
    CaptureLearning --> CreateKBEntry[Crear KnowledgeItem: domain='feedback_learning_knowledge']
    CreateKBEntry --> SetProvenance[Registrar Trazabilidad Completa: Autor, Fecha, Proyecto, Razón]
    
    subgraph IndexacionGobernada["Indexación y Gobernanza"]
        SetProvenance --> Chunking[KnowledgeBaseService._generate_chunks_for_item]
        Chunking --> TransitionVal[Transición de Estado: status='approved_for_reuse']
        TransitionVal --> UpdateReuseFlag[is_active_for_reuse = True]
    end
    
    UpdateReuseFlag --> FutureQueries[Disponible para el Motor RAG en Futuros Proyectos]
    FutureQueries --> AvoidRegression[El Asistente No Repite el Falso Positivo]
```

---

## 12. Flujo del Perfil de Madurez o Suficiencia Informacional por Proyecto

```mermaid
flowchart TD
    TriggerEval[Disparador: Cambio de Documentos, Aprobación de Reglas o Solicitud de Usuario] --> LoadProjectData[ProjectMaturityService.evaluate_project_maturity]
    
    subgraph CincoDimensiones["Evaluación de las 5 Dimensiones Ponderadas"]
        LoadProjectData --> D1[Dimensión 1: Documental & Planos (25%)\nLáminas, memorias, especificaciones]
        LoadProjectData --> D2[Dimensión 2: Completitud & Gatekeeper (25%)\nEntregables obligatorios y 0 bloqueos]
        LoadProjectData --> D3[Dimensión 3: Normativa & Criterios QA/QC (20%)\nCriterios aprobados y cobertura de reglas]
        LoadProjectData --> D4[Dimensión 4: Base de Conocimiento (15%)\nÍtems validados vs borradores]
        LoadProjectData --> D5[Dimensión 5: Observaciones & RFIs (15%)\nTasa de resolución y cierre]
    end
    
    D1 & D2 & D3 & D4 & D5 --> CalcOverallScore[Overall Score = Suma Ponderada (0 a 100%)]
    
    subgraph DiagnosticoYDelta["Diagnóstico, Gaps y Delta"]
        CalcOverallScore --> ClassifyLevel[Clasificar Nivel: initial, basic, intermediate, advanced, optimal]
        ClassifyLevel --> IdentifyGaps[Identificar Brechas Críticas y Rutas de Adquisición]
        IdentifyGaps --> ComparePrevious[Comparar con Perfil Anterior -> Calcular Delta Evolution]
    end
    
    ComparePrevious --> SaveMaturity[Guardar ProjectMaturityProfile en DB]
    SaveMaturity --> RenderMaturityBar[Renderizar Barra de Madurez y Tarjetas KPI en UI]
```

---

## 13. Flujo de Observaciones / RFIs / Cierre / Reapertura / Reutilización

```mermaid
flowchart TD
    Finding[RuleFinding Aceptado o Detección Manual de Auditor] --> CreateObs[Crear AuditObservation: status='open']
    
    CreateObs --> DraftRFI[Asistente redacta Borrador de RFI formal con justificación y solución sugerida]
    DraftRFI --> SendRFI[Emitir RFI al Proyectista / Contratista]
    
    SendRFI --> ResponseReceived[Recepción de Respuesta o Plano Rectificado]
    ResponseReceived --> AuditorVerify{¿Auditor Verifica Subsanación en Plano?}
    
    AuditorVerify -- Subsanado Correctamente --> CloseObs[AuditObservation: status='resolved' / 'closed']
    AuditorVerify -- Insuficiente o Nuevo Error --> ReopenObs[AuditObservation: status='reopened' -> Incrementar Contador]
    
    CloseObs --> ExtractLesson[Extraer Solución Aprobada como Lección Aprendida]
    ExtractLesson --> SaveLessonKB[Guardar en KnowledgeBase: domain='lesson_knowledge']
    SaveLessonKB --> TemplateReuse[Disponible como Plantilla de Solución en Futuras Revisiones]
```

---

## 14. Flujo de Snapshots / Reportes / Exportaciones Relevantes

```mermaid
flowchart TD
    RequestReport[Auditor solicita Emisión de Corte: POST /api/v1/consolidated-reports/emit] --> CompileData[ConsolidatedReportService.build_consolidated_data]
    
    subgraph ConsolidacionDeCorte["Compilación Integral de Corte"]
        CompileData --> SumCompleteness[Resumen de Completitud y Gatekeeper]
        CompileData --> SumVerdicts[Resumen de los 4 Veredictos QA/QC]
        CompileData --> SumObservations[Resumen de Observaciones Abiertas y Resueltas]
        CompileData --> SumDelta[Evolución Delta respecto a Snapshot Anterior]
        CompileData --> CalcGlobalVerdict[Determinación del Veredicto Global de Etapa]
    end
    
    CalcGlobalVerdict --> GenManifest[Calcular Hash Criptográfico SHA-256 del Manifiesto]
    
    subgraph PersistenciaInmutable["Persistencia Inmutable"]
        GenManifest --> SaveSnapshotDB[Crear registro 'project_stage_report_snapshots']
        SaveSnapshotDB --> GenPDF[Generar Informe Ejecutivo PDF con Sellos y Tablas]
        SaveSnapshotDB --> GenJSON[Generar Manifiesto Estructurado JSON/CSV]
    end
    
    GenPDF & GenJSON --> DeliverToUser[Entrega de URLs de Descarga al Usuario y Archivo Histórico]
```
