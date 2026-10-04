import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base

class EvaluationDataset(Base):
    """Conjunto de datos estructurado de evaluación (Golden, Regression, Benchmark)."""
    __tablename__ = "evaluation_datasets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Nullable si es un dataset global / de sistema compartido; con organization_id si es privado de tenant
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)

    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    dataset_type = Column(String(50), default="golden", nullable=False) # golden, regression, benchmark, pilot
    discipline = Column(String(50), default="architecture", nullable=False) # architecture, structure, electrical, plumbing, hvac, mixed
    version = Column(String(30), default="1.0", nullable=False)
    status = Column(String(30), default="draft", nullable=False) # draft, active, frozen, archived
    source_policy = Column(String(50), default="consented", nullable=False) # consented, anonymized, synthetic, internal
    
    # Snapshot inmutable de integridad cuando el dataset está frozen
    snapshot_manifest_hash = Column(String(64), nullable=True) # SHA-256 del manifiesto de muestras y anotaciones aprobadas
    frozen_at = Column(DateTime, nullable=True)
    
    created_by = Column(String(100), default="system_evaluator", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    samples = relationship("EvaluationSample", back_populates="dataset", cascade="all, delete-orphan")
    evaluation_runs = relationship("EvaluationRun", back_populates="dataset")


class EvaluationSample(Base):
    """Muestra o lámina técnica individual dentro de un dataset de evaluación."""
    __tablename__ = "evaluation_samples"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dataset_id = Column(String(36), ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Referencias internas inmutables prioritarias (no solo rutas de archivos)
    source_asset_id = Column(String(36), ForeignKey("source_assets.id", ondelete="SET NULL"), nullable=True, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    sheet_id = Column(String(36), ForeignKey("document_sheets.id", ondelete="SET NULL"), nullable=True, index=True)
    
    sample_key = Column(String(150), nullable=False) # Identificador único dentro del dataset (e.g. "SAMPLE-ARQ-001")
    discipline = Column(String(50), default="architecture", nullable=False)
    drawing_type = Column(String(100), default="floor_plan", nullable=False) # floor_plan, elevation, section, schedule, single_line
    source_checksum = Column(String(64), nullable=False) # SHA-256 inmutable del archivo fuente
    
    # Split de evaluación prioritario (test / holdout / validation)
    split = Column(String(30), default="test", nullable=False) # test, holdout, validation
    annotation_status = Column(String(30), default="pending", nullable=False) # pending, in_progress, reviewed, approved, rejected
    
    approved_by = Column(String(100), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    metadata_json = Column(JSON, default=dict) # {"scale": "1:50", "complexity": "medium", "source_client_anonymized": true}
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    dataset = relationship("EvaluationDataset", back_populates="samples")
    annotations = relationship("AnnotationSet", back_populates="sample", cascade="all, delete-orphan")


class AnnotationSet(Base):
    """Conjunto de anotaciones Ground Truth versionado para un dominio específico."""
    __tablename__ = "annotation_sets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sample_id = Column(String(36), ForeignKey("evaluation_samples.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Tipo de anotación
    annotation_type = Column(String(50), nullable=False) # ocr, layout, title_block, table, symbol, rule_finding
    schema_version = Column(String(30), default="v1.0", nullable=False)
    status = Column(String(30), default="draft", nullable=False) # draft, submitted, reviewed, approved, superseded
    
    annotator_id = Column(String(100), nullable=True)
    reviewer_id = Column(String(100), nullable=True)
    source = Column(String(50), default="human", nullable=False) # human, imported, synthetic, system_bootstrap
    
    # Contenido estructurado validado contra JSON Schema
    payload = Column(JSON, nullable=False)
    
    # Referencia a versión que la reemplaza si fue superada tras nueva revisión
    superseded_by_id = Column(String(36), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)

    # Relaciones
    sample = relationship("EvaluationSample", back_populates="annotations")


class EvaluationRun(Base):
    """Ejecución de evaluación reproducible sobre un dataset y split determinado."""
    __tablename__ = "evaluation_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dataset_id = Column(String(36), ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    
    dataset_version = Column(String(30), default="1.0", nullable=False)
    pipeline_version = Column(String(50), default="v1.0", nullable=False)
    git_commit_hash = Column(String(40), nullable=True) # Commit exacto del repositorio para trazabilidad
    model_versions = Column(JSON, default=dict) # {"ocr": "paddleocr-v4", "layout": "macro-v1", "symbols": "yolo-sahi-v1"}
    rule_pack_version = Column(String(50), default="v1.0-oguc", nullable=False)
    
    # Parámetros exactos de inferencia y rasterización para reproducibilidad científica
    ocr_raster_config = Column(JSON, default=dict) # {"dpi": 300, "engine": "paddleocr-v4", "binarization": False}
    inference_thresholds = Column(JSON, default=dict) # {"symbol_conf": 0.35, "uncertainty_max": 0.70, "iou_thresh": 0.50}
    prompts_and_rules_config = Column(JSON, default=dict) # Reglas activas y prompts auxiliares si aplican
    
    split_evaluated = Column(String(30), default="test", nullable=False) # test, holdout, all
    status = Column(String(30), default="queued", nullable=False) # queued, running, completed, failed
    
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    config = Column(JSON, default=dict) # quality gates config, threshold tolerances
    summary = Column(JSON, default=dict) # resumen perceptual y decisional, veredictos de calidad
    artifact_paths = Column(JSON, default=dict) # {"report_json": "./data/evaluations/..."}
    
    created_by = Column(String(100), default="system_evaluator", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    dataset = relationship("EvaluationDataset", back_populates="evaluation_runs")
    metrics = relationship("EvaluationMetric", back_populates="evaluation_run", cascade="all, delete-orphan")


class EvaluationMetric(Base):
    """Métrica individual calculada durante una corrida de evaluación."""
    __tablename__ = "evaluation_metrics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    evaluation_run_id = Column(String(36), ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Categoría superior: perceptual vs decisional
    category = Column(String(30), default="perceptual", nullable=False) # perceptual, decisional
    component = Column(String(50), nullable=False) # ocr, layout, title_block, table, symbol, rules, hitl
    
    metric_name = Column(String(100), nullable=False) # cer, wer, mean_iou, exact_match, f1_score, etc.
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(30), default="ratio", nullable=False) # ratio, percent, count, seconds, error_rate
    
    scope = Column(JSON, default=dict) # {"discipline": "architecture", "class_name": "door_single", "sample_id": "..."}
    confidence_interval = Column(JSON, nullable=True) # {"low": 0.92, "high": 0.98, "ci_level": 0.95}
    sample_count = Column(Integer, default=1, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    evaluation_run = relationship("EvaluationRun", back_populates="metrics")
