"""seed_golden_dataset.py

Inicializa un Golden Dataset institucional de referencia con muestras técnicas y
anotaciones Ground Truth aprobadas para los 6 dominios de evaluación.
"""
import os
import sys
import hashlib
import json

# Asegurar path del backend (soporta ejecución en contenedor /app y local)
sys.path.insert(0, "/app")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models.evaluation import EvaluationDataset, EvaluationSample, AnnotationSet
from app.schemas.evaluation import EvaluationDatasetCreate, EvaluationSampleCreate, AnnotationSetCreate
from app.services.evaluation.service import EvaluationService
from app.core.logging import logger

def seed_golden_dataset():
    db: Session = SessionLocal()
    try:
        svc = EvaluationService(db)
        
        # Verificar si ya existe el dataset institucional
        existing = db.query(EvaluationDataset).filter(EvaluationDataset.name == "Golden Dataset Arquitectura & Estructura OGUC v1.0").first()
        if existing:
            logger.info(f"Dataset de evaluación '{existing.name}' ya existe con ID: {existing.id}")
            return existing.id

        logger.info("Creando Golden Dataset institucional...")
        dataset = svc.create_dataset(
            data=EvaluationDatasetCreate(
                name="Golden Dataset Arquitectura & Estructura OGUC v1.0",
                description="Dataset institucional de referencia para evaluación perceptual y decisional de planos técnicos bajo norma OGUC.",
                dataset_type="golden",
                discipline="architecture",
                version="1.0",
                source_policy="synthetic"
            ),
            created_by="system_admin",
            organization_id=None # Dataset Global de Sistema
        )

        # Muestra 1: Planta Arquitectura Nivel 1 (Test)
        sample1_data = "dummy_content_pdf_sample_arq_001".encode("utf-8")
        s1 = svc.add_sample(
            dataset_id=dataset.id,
            sample_in=EvaluationSampleCreate(
                sample_key="SAMPLE-ARQ-001-P1",
                discipline="architecture",
                drawing_type="floor_plan",
                source_checksum=hashlib.sha256(sample1_data).hexdigest(),
                split="test",
                metadata_json={"scale": "1:50", "project": "Edificio Alerce", "complexity": "high"}
            )
        )

        # Anotaciones Muestra 1: OCR
        a1_ocr = svc.add_annotation(
            sample_id=s1.id,
            ann_in=AnnotationSetCreate(
                annotation_type="ocr",
                source="human",
                payload={
                    "items": [
                        {"text": "PLANTA PRIMER PISO", "bbox": [0.10, 0.90, 0.35, 0.95], "criticality": "critical"},
                        {"text": "ACCESO PRINCIPAL", "bbox": [0.45, 0.30, 0.55, 0.33], "criticality": "critical"},
                        {"text": "ESCALERA DE EVACUACION", "bbox": [0.70, 0.40, 0.88, 0.43], "criticality": "critical"},
                        {"text": "ESC: 1:50", "bbox": [0.85, 0.05, 0.95, 0.08], "criticality": "normal"}
                    ]
                }
            )
        )
        svc.update_annotation_status(a1_ocr.id, "approved", reviewer_id="audit_lead")

        # Anotaciones Muestra 1: Layout
        a1_lay = svc.add_annotation(
            sample_id=s1.id,
            ann_in=AnnotationSetCreate(
                annotation_type="layout",
                source="human",
                payload={
                    "items": [
                        {"region_type": "drawing_area", "bbox": [0.05, 0.15, 0.75, 0.95], "human_confidence": 1.0},
                        {"region_type": "title_block", "bbox": [0.78, 0.02, 0.98, 0.25], "human_confidence": 1.0},
                        {"region_type": "table_candidate", "bbox": [0.78, 0.28, 0.98, 0.65], "human_confidence": 1.0},
                        {"region_type": "notes_area", "bbox": [0.05, 0.02, 0.75, 0.12], "human_confidence": 1.0}
                    ]
                }
            )
        )
        svc.update_annotation_status(a1_lay.id, "approved", reviewer_id="audit_lead")

        # Anotaciones Muestra 1: Title Block
        a1_tb = svc.add_annotation(
            sample_id=s1.id,
            ann_in=AnnotationSetCreate(
                annotation_type="title_block",
                source="human",
                payload={
                    "items": [
                        {"field_name": "sheet_code", "expected_value": "ARQ-01", "required": True},
                        {"field_name": "sheet_title", "expected_value": "Planta Primer Piso", "required": True},
                        {"field_name": "scale", "expected_value": "1:50", "required": True},
                        {"field_name": "revision", "expected_value": "0", "required": True}
                    ]
                }
            )
        )
        svc.update_annotation_status(a1_tb.id, "approved", reviewer_id="audit_lead")

        # Anotaciones Muestra 1: Tables
        a1_tbl = svc.add_annotation(
            sample_id=s1.id,
            ann_in=AnnotationSetCreate(
                annotation_type="table",
                source="human",
                payload={
                    "items": [
                        {
                            "table_type": "door_schedule",
                            "bbox": [0.78, 0.28, 0.98, 0.65],
                            "total_rows": 3,
                            "total_cols": 3,
                            "headers": ["TIPO", "ANCHO", "CANT"],
                            "cells": [
                                {"row_index": 1, "col_index": 0, "cell_text": "P-1", "normalized_unit": None},
                                {"row_index": 1, "col_index": 1, "cell_text": "0.90 m", "normalized_unit": "m"},
                                {"row_index": 1, "col_index": 2, "cell_text": "12", "normalized_unit": "units"},
                                {"row_index": 2, "col_index": 0, "cell_text": "P-2", "normalized_unit": None},
                                {"row_index": 2, "col_index": 1, "cell_text": "0.80 m", "normalized_unit": "m"},
                                {"row_index": 2, "col_index": 2, "cell_text": "8", "normalized_unit": "units"}
                            ]
                        }
                    ]
                }
            )
        )
        svc.update_annotation_status(a1_tbl.id, "approved", reviewer_id="audit_lead")

        # Anotaciones Muestra 1: Symbols
        a1_sym = svc.add_annotation(
            sample_id=s1.id,
            ann_in=AnnotationSetCreate(
                annotation_type="symbol",
                source="human",
                payload={
                    "items": [
                        {"class_name": "door_single", "bbox": [0.45, 0.30, 0.50, 0.35], "count": 12, "human_confidence": 1.0},
                        {"class_name": "window_standard", "bbox": [0.15, 0.85, 0.25, 0.88], "count": 6, "human_confidence": 1.0}
                    ]
                }
            )
        )
        svc.update_annotation_status(a1_sym.id, "approved", reviewer_id="audit_lead")

        # Anotaciones Muestra 1: Rules
        a1_rf = svc.add_annotation(
            sample_id=s1.id,
            ann_in=AnnotationSetCreate(
                annotation_type="rule_finding",
                source="human",
                payload={
                    "items": [
                        {
                            "rule_code": "RULE-DOOR-COUNT-001",
                            "expected_outcome": "pass",
                            "expected_severity": "info",
                            "evidence_refs": {"table": "door_schedule", "symbol_count": 12}
                        },
                        {
                            "rule_code": "RULE-ESC-WIDTH-002",
                            "expected_outcome": "fail",
                            "expected_severity": "high",
                            "evidence_refs": {"stair_width_measured": 1.05, "stair_width_required": 1.20},
                            "notes": "Ancho de escalera no cumple mínimo de evacuación según OGUC 4.2.4"
                        }
                    ]
                }
            )
        )
        svc.update_annotation_status(a1_rf.id, "approved", reviewer_id="audit_lead")

        # Muestra 2: Fundaciones y Estructura (Test)
        sample2_data = "dummy_content_pdf_sample_est_002".encode("utf-8")
        s2 = svc.add_sample(
            dataset_id=dataset.id,
            sample_in=EvaluationSampleCreate(
                sample_key="SAMPLE-EST-002-FUND",
                discipline="structure",
                drawing_type="section",
                source_checksum=hashlib.sha256(sample2_data).hexdigest(),
                split="test",
                metadata_json={"scale": "1:25", "project": "Edificio Alerce", "complexity": "high"}
            )
        )
        a2_ocr = svc.add_annotation(
            sample_id=s2.id,
            ann_in=AnnotationSetCreate(
                annotation_type="ocr",
                source="human",
                payload={
                    "items": [
                        {"text": "DETALLE DE FUNDACIONES", "bbox": [0.10, 0.90, 0.40, 0.95], "criticality": "critical"},
                        {"text": "HORMIGON H-30", "bbox": [0.45, 0.30, 0.60, 0.33], "criticality": "critical"}
                    ]
                }
            )
        )
        svc.update_annotation_status(a2_ocr.id, "approved", reviewer_id="audit_lead")

        # Congelar dataset inicial para establecer baseline reproducible
        svc.freeze_dataset(dataset.id)
        logger.info(f"Golden Dataset '{dataset.name}' creado y congelado exitosamente.")

        # Ejecutar corrida de evaluación baseline inicial
        run = svc.run_evaluation(dataset.id, split="test", created_by="seed_script")
        logger.info(f"Corrida de evaluación inicial {run.id} completada exitosamente.")
        return dataset.id

    finally:
        db.close()

if __name__ == "__main__":
    seed_golden_dataset()
