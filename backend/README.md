# Backend - Plan Review AI Hybrid

Servicio central construido con **Python 3.11 + FastAPI + SQLAlchemy 2.0 + PostgreSQL/PostGIS**.

## Módulos Principales (`app/services/`)
- `ingest`: Ingesta y normalización de PDFs.
- `ocr`: OCR espacial posicional y corrección de rotación.
- `layout`: Segmentación de viñetas, notas y áreas de dibujo.
- `symbols`: Inferencia visual de simbología (YOLO v11 / SAHI).
- `semantics`: Mapeo a términos canónicos y ontologías.
- `knowledge`: Gestor de normas y plantillas.
- `rules`: Motor de reglas determinísticas (QA/QC, dimensionales).
- `decision_engine`: Orquestador híbrido de dictamen.
- `human_review`: Triage y supervisión experta (HITL).
- `active_learning`: Cola de reentrenamiento por incertidumbre.

## Ejecución Local
```bash
cd backend
pip install -e ..
uvicorn app.main:app --reload --port 8000
```
API Docs interactiva: `http://localhost:8000/docs`.
