import unittest
import os
import sys
import uuid
import hashlib

# Asegurar que backend esté en sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.db.models.core import Organization, User, OrganizationMembership
from app.db.models.evaluation import EvaluationDataset, EvaluationSample, AnnotationSet, EvaluationRun, EvaluationMetric
from app.db.models.decision_memory import RuleFinding
from app.db.models.document_memory import Document
from app.schemas.evaluation import (
    EvaluationDatasetCreate, EvaluationSampleCreate, AnnotationSetCreate,
    OcrAnnotationPayload, LayoutAnnotationPayload, TitleBlockAnnotationPayload,
    TableAnnotationPayload, SymbolAnnotationPayload, RuleFindingAnnotationPayload
)
from app.services.evaluation.metrics import MetricsCalculator, compute_box_iou
from app.services.evaluation.quality_gates import QualityGateEvaluator
from app.services.evaluation.service import EvaluationService

class TestEvaluationEngine(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine)
        self.db = Session()

        # Organigramas y usuarios de prueba
        self.org_a = Organization(id="org-a", name="Org Alpha", slug="org-a")
        self.org_b = Organization(id="org-b", name="Org Beta", slug="org-b")
        self.user_a = User(id="user-a", email="auditor_a@alpha.cl", full_name="Auditor Alpha")
        self.mem_a = OrganizationMembership(id="mem-a", user_id="user-a", organization_id="org-a", role="audit_lead")

        self.db.add_all([self.org_a, self.org_b, self.user_a, self.mem_a])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_annotation_schema_validation(self):
        """Valida que los schemas Pydantic acepten payloads válidos y rechacen malformados."""
        # OCR Válido
        ocr_valid = OcrAnnotationPayload(items=[
            {"text": "EJE A-1", "bbox": [0.1, 0.1, 0.2, 0.2], "criticality": "critical"}
        ])
        self.assertEqual(len(ocr_valid.items), 1)

        # Layout Válido
        layout_valid = LayoutAnnotationPayload(items=[
            {"region_type": "drawing_area", "bbox": [0.0, 0.0, 1.0, 1.0], "human_confidence": 1.0}
        ])
        self.assertEqual(layout_valid.items[0].region_type, "drawing_area")

        # Layout Inválido (Región desconocida)
        with self.assertRaises(Exception):
            LayoutAnnotationPayload(items=[
                {"region_type": "unknown_region", "bbox": [0.0, 0.0, 1.0, 1.0]}
            ])

        # Title Block Válido
        tb_valid = TitleBlockAnnotationPayload(items=[
            {"field_name": "sheet_code", "expected_value": "ARQ-01", "required": True}
        ])
        self.assertEqual(tb_valid.items[0].field_name, "sheet_code")

        # Símbolos Válido
        sym_valid = SymbolAnnotationPayload(items=[
            {"class_name": "door_single", "count": 5}
        ])
        self.assertEqual(sym_valid.items[0].count, 5)

        # Reglas QA/QC Válido
        rules_valid = RuleFindingAnnotationPayload(items=[
            {"rule_code": "RULE-001", "expected_outcome": "fail", "expected_severity": "critical"}
        ])
        self.assertEqual(rules_valid.items[0].expected_outcome, "fail")

    def test_annotation_lifecycle_and_superseding(self):
        """Verifica transiciones de estado y que una nueva aprobación marque la versión previa como superseded."""
        svc = EvaluationService(self.db)
        dataset = svc.create_dataset(
            EvaluationDatasetCreate(name="DS Test Lifecycle", dataset_type="golden", discipline="architecture"),
            organization_id="org-a"
        )
        sample = svc.add_sample(
            dataset.id,
            EvaluationSampleCreate(
                sample_key="SMP-01",
                source_checksum=hashlib.sha256(b"smp1").hexdigest(),
                split="test"
            ),
            organization_id="org-a"
        )

        # 1. Crear primera anotación en draft
        ann_v1 = svc.add_annotation(
            sample.id,
            AnnotationSetCreate(
                annotation_type="ocr",
                payload={"items": [{"text": "PISO 1", "bbox": [0.1, 0.1, 0.2, 0.2]}]}
            ),
            annotator_id="annotator_1"
        )
        self.assertEqual(ann_v1.status, "draft")

        # 2. Aprobar primera versión
        svc.update_annotation_status(ann_v1.id, "approved", reviewer_id="lead_1")
        self.db.refresh(ann_v1)
        self.assertEqual(ann_v1.status, "approved")

        # 3. Crear segunda versión por discrepancia (segundo anotador)
        ann_v2 = svc.add_annotation(
            sample.id,
            AnnotationSetCreate(
                annotation_type="ocr",
                payload={"items": [{"text": "PLANTA PRIMER PISO", "bbox": [0.1, 0.1, 0.3, 0.2]}]}
            ),
            annotator_id="annotator_2"
        )
        self.assertEqual(ann_v2.status, "draft")

        # 4. Aprobar versión 2 -> versión 1 debe pasar a superseded
        svc.update_annotation_status(ann_v2.id, "approved", reviewer_id="adjudicator")
        self.db.refresh(ann_v1)
        self.db.refresh(ann_v2)

        self.assertEqual(ann_v2.status, "approved")
        self.assertEqual(ann_v1.status, "superseded")
        self.assertEqual(ann_v1.superseded_by_id, ann_v2.id)

    def test_metrics_calculator_perceptual_and_decisional(self):
        """Valida los algoritmos de cálculo de CER, WER, IoU, exactitud y matrices de confusión."""
        # 1. OCR (CER & WER)
        preds = [{"text": "PLANTA PISO 1", "bbox": [0.1, 0.1, 0.3, 0.2]}]
        gt = [{"text": "PLANTA PISO 1", "bbox": [0.1, 0.1, 0.3, 0.2], "criticality": "critical"}]
        ocr_m = MetricsCalculator.calculate_ocr_metrics(preds, gt)
        self.assertEqual(ocr_m["cer"], 0.0)
        self.assertEqual(ocr_m["wer"], 0.0)
        self.assertEqual(ocr_m["critical_f1"], 1.0)

        # OCR con errores
        preds_err = [{"text": "PLANTA PISO 2", "bbox": [0.1, 0.1, 0.3, 0.2]}]
        ocr_err = MetricsCalculator.calculate_ocr_metrics(preds_err, gt)
        self.assertGreater(ocr_err["cer"], 0.0)
        self.assertGreater(ocr_err["wer"], 0.0)

        # 2. Layout (IoU)
        box1 = [0.0, 0.0, 1.0, 1.0]
        box2 = [0.0, 0.0, 1.0, 1.0]
        self.assertEqual(compute_box_iou(box1, box2), 1.0)

        box_disjoint = [2.0, 2.0, 3.0, 3.0]
        self.assertEqual(compute_box_iou(box1, box_disjoint), 0.0)

        # 3. Rules (Confusion Matrix)
        pred_findings = [
            {"rule_code": "RULE-DOORS", "severity": "high"},
            {"rule_code": "RULE-STAIRS", "severity": "critical"}
        ]
        gt_rules = [
            {"rule_code": "RULE-DOORS", "expected_outcome": "fail", "expected_severity": "high"},
            {"rule_code": "RULE-STAIRS", "expected_outcome": "fail", "expected_severity": "critical"},
            {"rule_code": "RULE-FIRE", "expected_outcome": "pass", "expected_severity": "medium"}
        ]
        rule_m = MetricsCalculator.calculate_rules_metrics(pred_findings, gt_rules)
        self.assertEqual(rule_m["precision"], 1.0)
        self.assertEqual(rule_m["recall"], 1.0)
        self.assertEqual(rule_m["f1_score"], 1.0)
        self.assertEqual(rule_m["severity_accuracy"], 1.0)
        self.assertEqual(rule_m["confusion_matrix"]["true_positive"], 2)
        self.assertEqual(rule_m["confusion_matrix"]["true_negative"], 1)

    def test_quality_gate_evaluator(self):
        """Valida los veredictos de Quality Gates (pass, warning, fail, insufficient_sample)."""
        metrics = {
            "ocr": {"cer": 0.05, "sample_count": 5},
            "layout": {"mean_iou": 0.85, "sample_count": 5},
            "title_block": {"required_completeness": 0.95, "sample_count": 5},
            "table": {"cell_accuracy": 0.90, "sample_count": 3},
            "rules": {"precision": 0.92, "sample_count": 5}
        }
        result = QualityGateEvaluator.evaluate(metrics)
        self.assertEqual(result["overall_status"], "pass")

        # Caso muestra insuficiente
        metrics_insufficient = {
            "ocr": {"cer": 0.05, "sample_count": 1}
        }
        res_insuf = QualityGateEvaluator.evaluate(metrics_insufficient)
        self.assertEqual(res_insuf["overall_status"], "insufficient_sample")

    def test_sandbox_isolation_and_multi_tenancy(self):
        """Verifica que la evaluación no inserte registros en tablas productivas y respete el scope de organización."""
        svc = EvaluationService(self.db)

        # Crear dataset privado de Org Alpha y dataset global
        ds_alpha = svc.create_dataset(
            EvaluationDatasetCreate(name="DS Alpha", dataset_type="golden"),
            organization_id="org-a"
        )
        ds_global = svc.create_dataset(
            EvaluationDatasetCreate(name="DS Global", dataset_type="benchmark"),
            organization_id=None
        )

        # Listar datasets desde Org Beta
        list_beta = svc.list_datasets(organization_id="org-b")
        beta_ids = [d.id for d in list_beta]
        self.assertNotIn(ds_alpha.id, beta_ids)
        self.assertIn(ds_global.id, beta_ids)

        # Agregar muestra y anotación aprobada a DS Alpha
        s = svc.add_sample(
            ds_alpha.id,
            EvaluationSampleCreate(sample_key="SMP-A1", source_checksum=hashlib.sha256(b"a1").hexdigest(), split="test"),
            organization_id="org-a"
        )
        ann = svc.add_annotation(
            s.id,
            AnnotationSetCreate(
                annotation_type="ocr",
                payload={"items": [{"text": "TEST OCR", "bbox": [0.1, 0.1, 0.2, 0.2]}]}
            )
        )
        svc.update_annotation_status(ann.id, "approved", reviewer_id="lead_a")

        # Contar registros productivos antes de correr evaluación
        findings_before = self.db.query(RuleFinding).count()
        docs_before = self.db.query(Document).count()

        # Ejecutar evaluación
        run = svc.run_evaluation(ds_alpha.id, split="test", created_by="evaluator_a", organization_id="org-a")
        self.assertEqual(run.status, "completed")
        self.assertEqual(run.summary["samples_evaluated_count"], 1)

        # Verificar que 0 registros productivos fueron creados
        self.assertEqual(self.db.query(RuleFinding).count(), findings_before)
        self.assertEqual(self.db.query(Document).count(), docs_before)

    def test_global_dataset_privacy_policy(self):
        """Verifica que datasets globales no permitan consented y exijan synthetic/anonymized/internal."""
        svc = EvaluationService(self.db)
        # Intentar crear dataset global con política consented -> Debe fallar
        with self.assertRaises(ValueError):
            svc.create_dataset(
                EvaluationDatasetCreate(name="DS Invalido", dataset_type="golden", source_policy="consented"),
                organization_id=None
            )

        # Crear dataset global con política synthetic -> Debe permitirse
        ds_ok = svc.create_dataset(
            EvaluationDatasetCreate(name="DS Valido", dataset_type="golden", source_policy="synthetic"),
            organization_id=None
        )
        self.assertIsNotNone(ds_ok.id)

    def test_per_class_symbols_and_reproducibility(self):
        """Valida desglose de símbolos por clase y persistencia de metadatos de reproducibilidad."""
        # 1. Validar desglose de símbolos
        pred_symbols = [
            {"symbol_type": "door_single", "bbox": [0.1, 0.1, 0.2, 0.2]},
            {"symbol_type": "door_single", "bbox": [0.3, 0.3, 0.4, 0.4]},
            {"symbol_type": "window_standard", "bbox": [0.5, 0.5, 0.6, 0.6]}
        ]
        gt_symbols = [
            {"class_name": "door_single", "count": 2, "bbox": [0.1, 0.1, 0.2, 0.2]},
            {"class_name": "window_standard", "count": 2, "bbox": [0.5, 0.5, 0.6, 0.6]}
        ]
        sym_metrics = MetricsCalculator.calculate_symbol_metrics(pred_symbols, gt_symbols)
        self.assertIn("by_class_metrics", sym_metrics)
        self.assertIn("door_single", sym_metrics["by_class_metrics"])
        self.assertIn("window_standard", sym_metrics["by_class_metrics"])
        self.assertEqual(sym_metrics["by_class_metrics"]["door_single"]["f1_score"], 1.0)
        self.assertEqual(sym_metrics["by_class_metrics"]["window_standard"]["pred_count"], 1)
        self.assertEqual(sym_metrics["by_class_metrics"]["window_standard"]["gt_count"], 2)

        # 2. Validar corrida con parámetros de reproducibilidad
        svc = EvaluationService(self.db)
        ds = svc.create_dataset(
            EvaluationDatasetCreate(name="DS Repro", dataset_type="golden", source_policy="synthetic"),
            organization_id=None
        )
        s = svc.add_sample(
            ds.id,
            EvaluationSampleCreate(sample_key="SMP-R1", source_checksum="abc123sha", split="test")
        )
        ann = svc.add_annotation(
            s.id,
            AnnotationSetCreate(
                annotation_type="symbol",
                payload={"items": gt_symbols}
            )
        )
        svc.update_annotation_status(ann.id, "approved", reviewer_id="lead")

        run = svc.run_evaluation(
            ds.id,
            split="test",
            config={
                "git_commit_hash": "commit_sha_123456",
                "ocr_raster_config": {"dpi": 300, "engine": "paddleocr-v4"},
                "inference_thresholds": {"symbol_confidence": 0.40}
            }
        )
        self.assertEqual(run.git_commit_hash, "commit_sha_123456")
        self.assertEqual(run.ocr_raster_config.get("dpi"), 300)
        self.assertEqual(run.inference_thresholds.get("symbol_confidence"), 0.40)

if __name__ == "__main__":
    unittest.main()

