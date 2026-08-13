# Plan Review AI Hybrid

Monorepo para revisión de planos y documentos PDF asistida por IA, reglas y base de conocimiento acumulativa.

## Enfoque
Sistema híbrido: OCR + visión + reglas + memoria estructurada + active learning + reentrenamiento selectivo.

## Memorias del sistema
- document_memory: documentos procesados, hojas, regiones, textos y evidencias.
- normative_memory: normas, cláusulas, criterios, fragmentos y relaciones.
- template_memory: viñetas, simbologías, esquemas de tablas, ontologías y plantillas.
- decision_memory: hallazgos, validaciones humanas, excepciones y precedentes.

## Objetivo
Disminuir la dependencia total de la IA generativa o perceptual, consolidando conocimiento reutilizable dentro de una base persistente y versionada.
