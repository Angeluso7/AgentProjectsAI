# Plan Review AI

Monorepo para desarrollar un sistema de revisión de planos y documentos PDF asistido por IA.

## Objetivo
Procesar planos PDF y documentos auxiliares, estructurar la información detectada, contrastarla con normas, plantillas guía y reglas internas, y generar hallazgos e informes exportables.

## Módulos principales
- backend: API, lógica de negocio, pipeline y workers.
- frontend: interfaz para carga, configuración, revisión y reportes.
- knowledge: entradas guía como viñetas, simbologías, ontologías y esquemas de tablas.
- rules: reglas normativas y QA/QC versionadas.
- data: datasets, anotaciones y salidas controladas.
- docs: arquitectura, roadmap, entrenamiento y operación.

## Flujo general
1. Ingesta de PDFs y documentos guía.
2. Extracción vectorial, OCR e imagen.
3. Detección de layout, viñetas, tablas, símbolos y regiones.
4. Normalización semántica y construcción de base estructurada.
5. Cruce con conocimiento guía y reglas normativas.
6. Priorización de hallazgos.
7. Generación y exportación de informes.

## Stack sugerido
- Backend: FastAPI, SQLAlchemy, Alembic, Celery/RQ, PostgreSQL/PostGIS.
- IA/CV: PyTorch, Ultralytics, OpenCV, PaddleOCR/Tesseract, LayoutParser.
- Frontend: React + Vite.
- MLOps: MLflow, DVC, Label Studio/CVAT.
