# Arquitectura propuesta

## Capas
1. Entrada documental: PDF, imágenes, Excel/CSV, plantillas guía, normas.
2. Ingesta: partición por hoja, rasterizado, extracción textual/vectorial.
3. Comprensión documental: clasificación de hoja, layout, viñeta, tablas, leyendas.
4. Comprensión técnica: símbolos, regiones, relaciones espaciales, referencias cruzadas.
5. Conocimiento guiado: plantillas de viñeta, bibliotecas de símbolos, esquemas de tablas, ontologías.
6. Normalización semántica: mapeo a entidades estándar del dominio.
7. Reglas y comparación: verificación normativa, QA/QC, consistencia documental.
8. Ranking: severidad, confianza, disciplina, criticidad.
9. Reporte y exportación: JSON, CSV, HTML, PDF, imágenes anotadas.

## Tipos de input adicionales
- title_blocks: plantillas de viñetas con campos esperados.
- symbol_libraries: catálogos de símbolos por disciplina.
- table_schemas: estructura y significado de tablas.
- ontologies: equivalencias de términos y relaciones.
- standards: normas técnicas y criterios internos.
- templates: patrones reutilizables de extracción.

## Principios
- Arquitectura híbrida: modelos ML/DL + OCR + reglas determinísticas.
- Trazabilidad total: cada hallazgo debe enlazar a hoja, coordenada, evidencia y regla.
- Datos primero: los modelos alimentan una base estructurada; no validan normas por sí solos.
- Despliegue incremental: MVP documental primero, detección visual después.
