"""
Script to validate Canonical Piping Symbol Catalog (Increment 01)
on a real PostgreSQL database with Alembic migration upgrade, downgrade,
and complete vertical slice entity lifecycle testing.
"""

import os
import sys
import uuid
import hashlib
import subprocess
import tempfile
import cv2
import numpy as np
from datetime import datetime

# Add backend directory to sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
root_dir = os.path.abspath(os.path.join(backend_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.db.models import *
from app.db.models.symbol_catalog import (
    SymbolTemplateVersion,
    SymbolGeometricFeature,
    SymbolFeatureRelation,
    SymbolSourceEvidence,
    SymbolReviewDecision,
    SymbolUnknownResearchCase,
)
from app.db.models.template_memory import SymbolTemplate, SymbolLibrary
from app.db.models.document_memory import DetectedSymbol, DocumentSheet, Document
from app.services.symbols.canonical_catalog_service import CanonicalPipingCatalogService


def run_cmd(cmd, cwd=root_dir):
    print(f"Executing: {cmd}")
    res = subprocess.run(cmd, shell=True, cwd=cwd, text=True, capture_output=True)
    if res.returncode != 0:
        print(f"STDOUT:\n{res.stdout}")
        print(f"STDERR:\n{res.stderr}")
        raise RuntimeError(f"Command failed with code {res.returncode}: {cmd}")
    print(res.stdout.strip())
    return res.stdout


def validate_postgres(db_url: str):
    print(f"Connecting to PostgreSQL: {db_url}")
    engine = sa.create_engine(db_url)
    
    # 1. Initialize Baseline Schema
    print("\n--- 1. Initializing baseline schema via Base.metadata.create_all ---")
    Base.metadata.create_all(bind=engine)
    
    # 2. Stamp at 0024_symbol_governance
    print("\n--- 2. Stamping Alembic at 0024_symbol_governance ---")
    run_cmd(f'alembic -x url="{db_url}" stamp 0024_symbol_governance')
    
    # 3. Test Downgrade -1 (reverting to 0023_piping_canonical_catalog)
    print("\n--- 3. Testing Alembic Downgrade -1 (reverting to 0023_piping_canonical_catalog) ---")
    run_cmd(f'alembic -x url="{db_url}" downgrade -1')
    
    # Verify columns dropped
    insp = sa.inspect(engine)
    det_cols = [c["name"] for c in insp.get_columns("detected_symbols")]
    assert "record_kind" not in det_cols, "record_kind should be dropped in 0023"
    assert "environment" not in det_cols, "environment should be dropped in 0023"
    print("Downgrade to 0023 verified: record_kind and environment columns dropped cleanly.")

    # 4. Test Downgrade -1 (reverting to 0022_expand_symbol_templates)
    print("\n--- 4. Testing Alembic Downgrade -1 (reverting to 0022_expand_symbol_templates) ---")
    run_cmd(f'alembic -x url="{db_url}" downgrade -1')
    
    # Verify tables dropped
    insp = sa.inspect(engine)
    existing_tables = set(insp.get_table_names())
    assert "symbol_template_versions" not in existing_tables, "symbol_template_versions should be dropped"
    assert "symbol_geometric_features" not in existing_tables, "symbol_geometric_features should be dropped"
    print("Downgrade to 0022 verified: canonical catalog tables dropped cleanly.")
    
    # 5. Test Upgrade to Head (0024)
    print("\n--- 5. Testing Alembic Upgrade to Head (0024_symbol_governance) ---")
    run_cmd(f'alembic -x url="{db_url}" upgrade head')
    
    insp = sa.inspect(engine)
    existing_tables = set(insp.get_table_names())
    expected_tables = {
        "symbol_template_versions",
        "symbol_geometric_features",
        "symbol_feature_relations",
        "symbol_source_evidences",
        "symbol_review_decisions",
        "symbol_unknown_research_cases",
    }
    for tbl in expected_tables:
        assert tbl in existing_tables, f"Expected table {tbl} was not found after upgrade"
    det_cols = [c["name"] for c in insp.get_columns("detected_symbols")]
    assert "record_kind" in det_cols, "record_kind should be present in 0024"
    assert "environment" in det_cols, "environment should be present in 0024"
    print("Upgrade verified: all 6 canonical catalog tables and columns recreated successfully.")
    
    # 6. Entity Lifecycle & Governance Validation on PostgreSQL
    print("\n--- 6. Validating Entity Lifecycle, Governance & CRUD on PostgreSQL ---")
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        # Create library
        lib_id = str(uuid.uuid4())
        lib = SymbolLibrary(
            id=lib_id,
            name=f"PIP-PNC00001-Lib-{lib_id[:8]}",
            discipline="piping",
            standard_name="PIP PNC00001",
            description="Piping and Instrumentation Diagrams library"
        )
        db.add(lib)
        db.flush()
        
        # Create canonical SymbolTemplate
        tmpl_id = str(uuid.uuid4())
        tmpl = SymbolTemplate(
            id=tmpl_id,
            library_id=lib.id,
            symbol_class="gate_valve",
            display_name="Gate Valve Manual",
            canonical_code="PIP-VALVE-GATE",
            canonical_name="Manual Gate Valve",
            discipline="piping",
            subcategory="valves",
            technical_function="isolation",
            standard_reference="PIP PNC00001 / ISA-5.1 Section 5.4",
            status="active"
        )
        db.add(tmpl)
        db.flush()
        
        # Create SymbolTemplateVersion
        ver_id = str(uuid.uuid4())
        version = SymbolTemplateVersion(
            id=ver_id,
            symbol_template_id=tmpl.id,
            version_number=1,
            approval_status="approved",
            source_kind="normative_document",
            orientation_policy="rotation_equivalent_180",
            scale_policy="isotropic_bounded",
            geometric_signature={"primitives": ["triangle_left", "triangle_right", "stem", "handwheel"]},
            approved_by="lead_piping_engineer",
            approved_at=datetime.utcnow()
        )
        db.add(version)
        db.flush()
        
        tmpl.current_version_id = version.id
        db.flush()
        
        # Create Geometric Features
        feat1 = SymbolGeometricFeature(
            id=str(uuid.uuid4()),
            symbol_template_version_id=version.id,
            feature_type="triangle",
            feature_count=2,
            feature_parameters={"opposed": True, "apex_concurrent": True},
            normalized_bbox=[0.1, 0.3, 0.9, 0.9],
            relative_position="bottom",
            relationship_group="valve_body"
        )
        feat2 = SymbolGeometricFeature(
            id=str(uuid.uuid4()),
            symbol_template_version_id=version.id,
            feature_type="line_segment",
            feature_count=2,
            feature_parameters={"stem": "vertical", "handwheel": "horizontal"},
            normalized_bbox=[0.25, 0.05, 0.75, 0.35],
            relative_position="top",
            relationship_group="actuator_manual"
        )
        db.add_all([feat1, feat2])
        db.flush()
        
        # Create Feature Relation
        rel = SymbolFeatureRelation(
            id=str(uuid.uuid4()),
            source_feature_id=feat1.id,
            target_feature_id=feat2.id,
            relation_type="connected_to",
            confidence=0.98,
            relation_parameters={"connection_point": "apex_center"}
        )
        db.add(rel)
        db.flush()
        
        # Create Source Evidence
        crop_bytes = b"synthetic_crop_bytes_pip_valve_gate_001"
        evidence = SymbolSourceEvidence(
            id=str(uuid.uuid4()),
            symbol_template_version_id=version.id,
            evidence_kind="synthetic",
            source_document_id="PIP-PNC00001-REV-2024",
            source_document_hash=hashlib.sha256(b"PIP_DOC_RAW").hexdigest(),
            source_revision="Rev 3",
            source_date="2024-03-15",
            page_number=14,
            crop_image_path="/storage/crops/pip_gate_valve_v1.png",
            crop_image_hash=hashlib.sha256(crop_bytes).hexdigest(),
            bbox_normalized=[120.0, 340.0, 180.0, 400.0]
        )
        db.add(evidence)
        db.flush()
        
        # Create Document & Sheet for Occurrence
        org = Organization(id=str(uuid.uuid4()), name="Test Org", slug=f"org-{uuid.uuid4().hex[:6]}")
        proj = Project(id=str(uuid.uuid4()), organization_id=org.id, name="Test Project", code=f"PRJ-{uuid.uuid4().hex[:6]}")
        doc = Document(
            id=str(uuid.uuid4()),
            organization_id=org.id,
            project_id=proj.id,
            filename="PID-1001.pdf",
            file_path="/tmp/PID-1001.pdf",
            file_hash_sha256=f"hash_{uuid.uuid4().hex}",
            file_size_bytes=1024,
            status="uploaded"
        )
        sheet = DocumentSheet(
            id=str(uuid.uuid4()),
            document_id=doc.id,
            sheet_number=1,
            title="P&ID Sheet 01",
            width_px=1000,
            height_px=1000
        )
        db.add_all([org, proj, doc, sheet])
        db.flush()

        # Create Occurrence (DetectedSymbol with record_kind='occurrence')
        occ_id = str(uuid.uuid4())
        occ = DetectedSymbol(
            id=occ_id,
            document_id=doc.id,
            sheet_id=sheet.id,
            symbol_type="valve",
            bbox=[200, 200, 280, 280],
            bbox_normalized=[0.2, 0.2, 0.28, 0.28],
            confidence=0.96,
            inner_drawing_bbox=[190.0, 190.0, 270.0, 270.0],
            symbol_crop_bbox=[200.0, 200.0, 260.0, 260.0],
            crop_image_path="/storage/crops/occ_gate_valve_01.png",
            crop_image_hash=hashlib.sha256(b"occ_gate_crop").hexdigest(),
            record_kind="occurrence",
            environment="production",
            classification="symbol",
            geometric_evidence=True,
            geometric_confidence=0.95,
            matching_status="matched",
            matched_template_id=tmpl.id,
            matched_template_version_id=version.id,
            match_score=0.91,
            geometry_score=0.95,
            topology_score=0.90,
            visual_score=0.88,
            context_score=0.10,
            detected_tag_or_code="HV-101",
            context_text="HV-101 TO REACTION VESSEL",
            review_status="pending_review"
        )
        db.add(occ)
        
        # Create unvalidated Candidate (DetectedSymbol with record_kind='candidate', classification='figure')
        cand_id = str(uuid.uuid4())
        cand = DetectedSymbol(
            id=cand_id,
            document_id=doc.id,
            sheet_id=sheet.id,
            symbol_type="valve",
            bbox=[300, 300, 400, 400],
            bbox_normalized=[0.3, 0.3, 0.4, 0.4],
            confidence=0.80,
            record_kind="candidate",
            environment="production",
            classification="figure",
            geometric_evidence=False,
            geometric_confidence=0.20,
            matching_status="not_applicable",
            review_status="unreviewed"
        )
        db.add(cand)
        db.flush()
        
        # Create Human Review Decision
        decision_id = str(uuid.uuid4())
        dec = SymbolReviewDecision(
            id=decision_id,
            subject_type="occurrence",
            subject_id=occ.id,
            decision="approve",
            reviewer_id="reviewer_senior_eng",
            rationale="Confirmed as manual gate valve on horizontal feed line."
        )
        db.add(dec)
        db.flush()
        
        # Create Unknown Research Case for valid unknown geometry
        case_id = str(uuid.uuid4())
        case = SymbolUnknownResearchCase(
            id=case_id,
            symbol_occurrence_id=occ.id,
            status="unknown",
            search_query="gate valve variation PIP PNC00001",
            proposed_name="SYM-UNKNOWN-001",
            proposed_standard_reference="PIP PNC00001",
            research_notes="SYM-UNKNOWN-001: Unknown check-valve variation with internal flow arrow."
        )
        db.add(case)
        db.commit()
        
        # Query Verification: Template & Evidence
        q_tmpl = db.query(SymbolTemplate).filter(SymbolTemplate.canonical_code == "PIP-VALVE-GATE").first()
        assert q_tmpl is not None
        assert len(q_tmpl.versions) == 1
        assert q_tmpl.versions[0].orientation_policy == "rotation_equivalent_180"
        assert len(q_tmpl.versions[0].geometric_features) == 2
        assert q_tmpl.versions[0].source_evidence is not None
        assert q_tmpl.versions[0].source_evidence.evidence_kind == "synthetic"
        
        # Query Verification: Candidate vs Occurrence Separation on PostgreSQL
        q_occ = db.query(DetectedSymbol).filter(DetectedSymbol.id == occ_id).first()
        assert q_occ is not None
        assert q_occ.has_real_geometry is True
        assert q_occ.matching_status == "matched"
        assert q_occ.record_kind == "occurrence"
        assert q_occ.is_occurrence is True

        q_cand = db.query(DetectedSymbol).filter(DetectedSymbol.id == cand_id).first()
        assert q_cand is not None
        assert q_cand.record_kind == "candidate"
        assert q_cand.is_occurrence is False

        # Invariant: filtering by record_kind='occurrence' yields only valid occurrences
        occurrences_only = db.query(DetectedSymbol).filter(
            DetectedSymbol.sheet_id == sheet.id,
            DetectedSymbol.record_kind == "occurrence"
        ).all()
        assert len(occurrences_only) == 1
        assert occurrences_only[0].id == occ_id
        print("Candidate vs Occurrence separation verified on PostgreSQL.")

        # Governance Policy Verification on PostgreSQL
        catalog_service = CanonicalPipingCatalogService(db)
        # 1. Attempting to approve synthetic evidence version for production MUST FAIL
        try:
            catalog_service.approve_template_version_for_production(
                version_id=version.id,
                reviewer_id="auditor_lead",
                rationale="Intento de activar sintético en producción"
            )
            assert False, "Violation: Synthetic version was approved for production on PostgreSQL!"
        except ValueError as e:
            assert "Governance Violation" in str(e)
            print("Governance verified: synthetic version correctly blocked from production approval.")

        # 2. Real authorized evidence version CAN be approved for production
        temp_crop_dir = tempfile.mkdtemp()
        real_crop_path = os.path.join(temp_crop_dir, "real_pnc00001_p14.png")
        img_dummy = np.ones((80, 80, 3), dtype=np.uint8) * 255
        cv2.imwrite(real_crop_path, img_dummy)
        with open(real_crop_path, "rb") as f:
            real_crop_hash = hashlib.sha256(f.read()).hexdigest()

        real_ver_id = str(uuid.uuid4())
        real_ver = SymbolTemplateVersion(
            id=real_ver_id,
            symbol_template_id=tmpl.id,
            version_number=2,
            approval_status="pending_review",
            canonical_crop_path=real_crop_path
        )
        db.add(real_ver)
        real_ev = SymbolSourceEvidence(
            symbol_template_version_id=real_ver.id,
            evidence_kind="real_authorized",
            source_standard_or_project="PIP PNC00001 Rev 2024",
            source_document_hash="sha256_hash_real_pnc00001",
            page_number=14,
            bbox_normalized=[0.1, 0.1, 0.9, 0.9],
            crop_image_path=real_crop_path,
            crop_image_hash=real_crop_hash
        )
        db.add(real_ev)
        db.commit()

        approved_real = catalog_service.approve_template_version_for_production(
            version_id=real_ver.id,
            reviewer_id="lead_hitl_engineer",
            rationale="Approved with real authorized evidence from PIP PNC00001."
        )
        assert approved_real.approval_status == "approved"
        db.refresh(tmpl)
        assert tmpl.status == "active"
        print("Governance verified: real authorized evidence approved for production with HITL decision.")
        
        print("\n>>> ALL ENTITY CRUD, GOVERNANCE INVARIANTS, MIGRATION UPGRADE & DOWNGRADE VERIFIED ON POSTGRESQL! <<<")
    finally:
        db.close()


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
        "TEST_DATABASE_URL",
        os.environ.get("DATABASE_URL", "postgresql+psycopg://postgres_migrator:migrator_secure_pass_123@localhost:5433/planreview_test")
    )
    validate_postgres(url)
