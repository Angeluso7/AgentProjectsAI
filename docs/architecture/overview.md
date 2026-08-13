# Arquitectura híbrida

## Flujo extremo a extremo
1. Entrada de documentos: PDFs de planos, normas, simbologías, plantillas, tablas y anexos.
2. Ingesta: lectura, partición por hoja, rasterización, extracción textual/vectorial.
3. Detección: layout, viñetas, tablas, regiones, símbolos, referencias y tipos de vista.
4. Interpretación guiada: contraste con plantillas, esquemas, ontologías y librerías de símbolos.
5. Normalización semántica: mapeo a entidades estándar del dominio.
6. Persistencia en memorias: documental, normativa, de plantillas y de decisiones.
7. Verificación: reglas, consistencia cruzada, recuperación semántica y comparación entre versiones.
8. Revisión humana: validación, correcciones, aceptación o descarte de hallazgos.
9. Aprendizaje: active learning, weak labeling y reentrenamiento selectivo.
10. Salida: JSON, CSV, XLSX, HTML, PDF, imágenes anotadas y API.

## Principios
- La IA detecta y propone; la base recuerda; las reglas verifican; el humano confirma.
- Cada resultado debe ser trazable a documento, hoja, coordenada, evidencia y regla.
- El conocimiento externo se guarda en estructuras persistentes, no solo en prompts.
