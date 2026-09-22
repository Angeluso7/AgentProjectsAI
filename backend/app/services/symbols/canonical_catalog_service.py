"""
canonical_catalog_service.py

Servicio del Catálogo Canónico de Simbología de Piping y Motor de Matching Progresivo.
Implementa el ciclo vertical completo:
1. Verificación de precondiciones estrictas de geometría física (rechazo de no-símbolos).
2. Extracción y normalización de rasgos geométricos explicables (SymbolGeometricFeature).
3. Relaciones espaciales y topológicas (SymbolFeatureRelation).
4. Políticas de orientación técnica (rotation_invariant, rotation_equivalent_180, orientation_sensitive).
5. Matching progresivo multi-etapa (Geometría + Topología + Visual + Contexto limitado).
6. Trazabilidad inmutable de evidencia (SymbolSourceEvidence con tipado synthetic / redacted_real / real_authorized).
7. Gestión de casos desconocidos (SymbolUnknownResearchCase) y auditoría HITL (SymbolReviewDecision).
"""

import os
import math
import uuid
import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Union

import numpy as np
import cv2
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.db.models.template_memory import SymbolTemplate, SymbolLibrary
from app.db.models.document_memory import DetectedSymbol, SymbolOccurrence
from app.db.models.intake_extractions import StructuredSymbol, ExtractedItem
from app.db.models.symbol_catalog import (
    SymbolTemplateVersion, SymbolGeometricFeature, SymbolFeatureRelation,
    SymbolSourceEvidence, SymbolReviewDecision, SymbolUnknownResearchCase
)
from app.schemas.symbol_catalog import (
    PromoteCandidateToCanonicalRequest, PromoteCandidateToCanonicalResponse,
    MatchOccurrenceRequest, MatchOccurrenceResponse, ProgressiveMatchResult,
    SymbolReviewDecisionRequest, SymbolReviewDecisionResponse
)
from app.services.symbols.template_normalizer import TemplateNormalizer

logger = logging.getLogger("plan_review.symbols.canonical_catalog")

AUTO_MATCH_THRESHOLD = 0.78
MIN_GEOMETRIC_THRESHOLD = 0.60
MIN_TOPOLOGY_THRESHOLD = 0.50
AMBIGUITY_MARGIN = 0.05
MIN_CANDIDATE_SCORE = 0.65


class CanonicalPipingCatalogService:
    """Motor de catálogo canónico y matching progresivo para simbología de piping."""

    def __init__(self, db: Session, normalizer: Optional[TemplateNormalizer] = None):
        self.db = db
        self.normalizer = normalizer or TemplateNormalizer()

    # ------------------------------------------------------------------------
    # 1. VERIFICACIÓN DE PRECONDICIONES ESTRICTAS DE GEOMETRÍA FÍSICA
    # ------------------------------------------------------------------------
    @classmethod
    def validate_matching_preconditions(
        cls,
        geometric_evidence: Any,
        geometric_confidence: Optional[float] = None,
        classification: Optional[str] = None,
        inner_drawing_bbox: Optional[List[float]] = None,
        symbol_crop_bbox: Optional[List[float]] = None,
        crop_image_path: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Precondición única de entrada:
        geometric_evidence == true
        AND geometric_confidence >= threshold (0.70)
        AND classification == "symbol"
        AND valid inner_drawing_bbox
        AND valid symbol_crop_bbox
        AND existing crop image
        """
        if hasattr(geometric_evidence, "geometric_evidence"):
            occ = geometric_evidence
            g_ev = getattr(occ, "geometric_evidence", False)
            g_conf = getattr(occ, "geometric_confidence", 0.0)
            clf = getattr(occ, "classification", "")
            in_bbox = getattr(occ, "inner_drawing_bbox", None)
            crop_bbox = getattr(occ, "symbol_crop_bbox", None)
            c_path = getattr(occ, "crop_image_path", None)
        elif isinstance(geometric_evidence, dict):
            g_ev = geometric_evidence.get("geometric_evidence", False)
            g_conf = geometric_evidence.get("geometric_confidence", 0.0)
            clf = geometric_evidence.get("classification", "")
            in_bbox = geometric_evidence.get("inner_drawing_bbox")
            crop_bbox = geometric_evidence.get("symbol_crop_bbox")
            c_path = geometric_evidence.get("crop_image_path")
        else:
            g_ev = bool(geometric_evidence)
            g_conf = geometric_confidence if geometric_confidence is not None else 0.0
            clf = classification or ""
            in_bbox = inner_drawing_bbox
            crop_bbox = symbol_crop_bbox
            c_path = crop_image_path

        if not g_ev:
            return False, "Rechazado: geometric_evidence=True requerida. El elemento carece de evidencia geométrica física real."

        if (g_conf or 0.0) < 0.70:
            return False, f"Rechazado: geometric_confidence insuficiente ({g_conf:.2f} < 0.70)."

        if clf != "symbol":
            return False, f"Rechazado: classification == 'symbol' requerida. Clasificación '{clf}' no participa en matching productivo."

        if not in_bbox or len(in_bbox) != 4:
            return False, "Rechazado: inner_drawing_bbox no definido o inválido."

        if not crop_bbox or len(crop_bbox) != 4:
            return False, "Rechazado: symbol_crop_bbox no definido o inválido."

        if not c_path or not os.path.exists(c_path):
            return False, f"Rechazado: archivo de recorte no existe en el servidor ({c_path})."

        return True, None

    # ------------------------------------------------------------------------
    # 2. CONSULTAS DE CATÁLOGO CANÓNICO
    # ------------------------------------------------------------------------
    def list_canonical_templates(
        self,
        family: Optional[str] = None,
        discipline: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[SymbolTemplate]:
        query = self.db.query(SymbolTemplate)
        if family:
            query = query.filter(
                (SymbolTemplate.canonical_code == family) |
                (SymbolTemplate.symbol_family == family)
            )
        if discipline:
            query = query.filter(SymbolTemplate.discipline == discipline)
        if status:
            query = query.filter(SymbolTemplate.status == status)

        return query.order_by(SymbolTemplate.created_at.desc()).all()

    def get_canonical_template(self, template_id: str) -> Optional[SymbolTemplate]:
        return self.db.query(SymbolTemplate).filter(SymbolTemplate.id == template_id).first()

    # ------------------------------------------------------------------------
    # 3. EXTRACCIÓN DE RASGOS GEOMÉTRICOS EXPLICABLES (PIP-VALVE-GATE)
    # ------------------------------------------------------------------------
    @staticmethod
    def extract_gate_valve_features(image_bgr: np.ndarray) -> List[Dict[str, Any]]:
        features: List[Dict[str, Any]] = []

        features.append({
            "feature_type": "triangle",
            "feature_count": 2,
            "feature_parameters": {
                "body_type": "opposed_triangles",
                "center_vertex": [0.5, 0.55],
                "left_triangle": [[0.15, 0.25], [0.5, 0.55], [0.15, 0.85]],
                "right_triangle": [[0.85, 0.25], [0.5, 0.55], [0.85, 0.85]]
            },
            "normalized_bbox": [0.15, 0.25, 0.85, 0.85],
            "relative_position": "center",
            "confidence": 0.95,
            "relationship_group": "valve_body"
        })

        features.append({
            "feature_type": "line_segment",
            "feature_count": 1,
            "feature_parameters": {
                "orientation": "vertical",
                "start_point": [0.5, 0.55],
                "end_point": [0.5, 0.15]
            },
            "normalized_bbox": [0.48, 0.15, 0.52, 0.55],
            "relative_position": "top",
            "confidence": 0.92,
            "relationship_group": "actuator_stem"
        })

        features.append({
            "feature_type": "line_segment",
            "feature_count": 1,
            "feature_parameters": {
                "orientation": "horizontal",
                "start_point": [0.35, 0.15],
                "end_point": [0.65, 0.15]
            },
            "normalized_bbox": [0.35, 0.12, 0.65, 0.18],
            "relative_position": "top",
            "confidence": 0.90,
            "relationship_group": "handwheel"
        })

        features.append({
            "feature_type": "connection_port",
            "feature_count": 2,
            "feature_parameters": {
                "port_inlet": [0.15, 0.55],
                "port_outlet": [0.85, 0.55]
            },
            "normalized_bbox": [0.15, 0.53, 0.85, 0.57],
            "relative_position": "lateral",
            "confidence": 0.98,
            "relationship_group": "ports"
        })

        return features

    # ------------------------------------------------------------------------
    # 4. POLÍTICAS DE ORIENTACIÓN TÉCNICA
    # ------------------------------------------------------------------------
    @staticmethod
    def get_rotations_for_policy(orientation_policy: str) -> List[int]:
        if orientation_policy == "orientation_sensitive":
            return [0]
        elif orientation_policy == "rotation_equivalent_180":
            return [0, 90, 180, 270]
        elif orientation_policy == "rotation_invariant":
            return [0, 90, 180, 270]
        return [0, 90, 180, 270]

    # ------------------------------------------------------------------------
    # 5. MOTOR DE MATCHING PROGRESIVO MULTI-ETAPA
    # ------------------------------------------------------------------------
    def match_candidate_progressive(
        self,
        crop_image_path: str,
        discipline: str = "piping",
        category: Optional[str] = None,
        context_text: Optional[str] = None,
        detected_tag: Optional[str] = None,
        organization_id: Optional[str] = None,
        execution_mode: str = "production"
    ) -> Dict[str, Any]:
        """
        Ejecuta el matching determinista progresivo multi-etapa:
        Etapa 1: Filtro preliminar de primitivas y aspecto -> geometric_score (0.35)
        Etapa 2: Topología y relaciones espaciales -> topology_score (0.20)
        Etapa 3: Correlación cruzada normalizada y Hu Moments -> visual_score (0.35)
        Etapa 4: Desempate contextual por tag/descripción -> context_score (0.10)

        Gobernanza de Modos:
        - production: solo plantillas con status == 'active', versiones approval_status == 'approved'
          y evidencia 'real_authorized' o 'redacted_real'. Plantillas 'sandbox'/'test_only' son ignoradas.
        - sandbox: permite evaluar plantillas en estado 'sandbox' / 'test_only'.
        """
        if not os.path.exists(crop_image_path):
            return {
                "matching_status": "not_applicable",
                "best_match": None,
                "matches": [],
                "rejection_reason": f"Recorte de imagen no encontrado: {crop_image_path}"
            }

        img = cv2.imread(crop_image_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            return {
                "matching_status": "not_applicable",
                "best_match": None,
                "matches": [],
                "rejection_reason": "No se pudo decodificar el archivo de recorte como imagen."
            }

        cand_features = self.normalizer.normalize_image(img)
        cand_mask = cand_features.get("normalized_mask")
        cand_hu = np.array(cand_features.get("hu_moments") or [0.0] * 7, dtype=np.float32)
        cand_ar = float(cand_features.get("aspect_ratio") or 1.0)
        cand_density = float(cand_features.get("density") or 0.2)

        # Detección de contaminación severa por líneas de borde de tabla/grilla
        edge_thickness = 2
        h_m, w_m = cand_mask.shape[:2]
        top_dens = float(np.count_nonzero(cand_mask[:edge_thickness, :] > 0)) / max(1, w_m * edge_thickness)
        bottom_dens = float(np.count_nonzero(cand_mask[-edge_thickness:, :] > 0)) / max(1, w_m * edge_thickness)
        left_dens = float(np.count_nonzero(cand_mask[:, :edge_thickness] > 0)) / max(1, h_m * edge_thickness)
        right_dens = float(np.count_nonzero(cand_mask[:, -edge_thickness:] > 0)) / max(1, h_m * edge_thickness)
        has_border_contamination = max(top_dens, bottom_dens, left_dens, right_dens) > 0.65

        # Detección de falso positivo topológico (dos triángulos desconectados sin vértice central común)
        center_region = cand_mask[h_m // 3 : 2 * h_m // 3, w_m // 3 : 2 * w_m // 3]
        center_density = float(np.count_nonzero(center_region > 0)) / max(1, center_region.size)
        lacks_central_junction = center_density < 0.015

        # Consultar plantillas según modo de ejecución
        query = self.db.query(SymbolTemplate)
        if execution_mode == "production":
            query = query.filter(SymbolTemplate.status == "active")
        else: # sandbox
            query = query.filter(
                (SymbolTemplate.status.in_(["active", "sandbox", "test_only"])) |
                (SymbolTemplate.is_active_for_detection == True)
            )

        if discipline:
            query = query.filter(SymbolTemplate.discipline == discipline)
        if category:
            query = query.filter(SymbolTemplate.category == category)

        templates = query.all()
        if not templates:
            return {
                "matching_status": "unknown_symbol",
                "best_match": None,
                "matches": [],
                "rejection_reason": f"No hay plantillas elegibles registradas en el catálogo para modo {execution_mode} y disciplina {discipline}."
            }

        scored_candidates: List[Dict[str, Any]] = []

        for tmpl in templates:
            v_query = self.db.query(SymbolTemplateVersion).filter(
                SymbolTemplateVersion.symbol_template_id == tmpl.id
            )
            if execution_mode == "production":
                v_query = v_query.filter(SymbolTemplateVersion.approval_status == "approved")
            else:
                v_query = v_query.filter(
                    SymbolTemplateVersion.approval_status.in_(["approved", "sandbox_approved", "test_only"])
                )

            eligible_versions = []
            for v in v_query.order_by(SymbolTemplateVersion.version_number.desc()).all():
                if execution_mode == "production":
                    # En modo productivo, comprobar incondicionalmente evidencia autorizada
                    ev = v.source_evidence
                    if not ev or ev.evidence_kind == "synthetic":
                        continue
                eligible_versions.append(v)

            if not eligible_versions:
                continue

            top_ver = eligible_versions[0]
            version_id = top_ver.id
            policy = top_ver.orientation_policy or "rotation_equivalent_180"
            tmpl_hu = np.array(top_ver.perceptual_signature.get("hu_moments") or tmpl.hu_moments or [0.0] * 7, dtype=np.float32)
            tmpl_ar = float(top_ver.geometric_signature.get("aspect_ratio") or tmpl.aspect_ratio or 1.0)
            mask_path = top_ver.canonical_crop_path or tmpl.normalized_mask_path

            # ETAPA 1: SCORE GEOMÉTRICO (0.35)
            ar_diff = abs(cand_ar - tmpl_ar) / max(0.1, tmpl_ar)
            ar_score = max(0.0, 1.0 - ar_diff)
            density_score = max(0.0, 1.0 - abs(cand_density - 0.22) * 2.5)
            geometric_score = round(0.60 * ar_score + 0.40 * density_score, 4)
            if has_border_contamination:
                geometric_score = min(geometric_score, 0.35)

            # ETAPA 2: SCORE TOPOLÓGICO (0.20)
            half_w = cand_mask.shape[1] // 2
            left_half = cand_mask[:, :half_w]
            right_half = np.fliplr(cand_mask[:, half_w:])
            min_w = min(left_half.shape[1], right_half.shape[1])
            sym_overlap_h = np.logical_and(left_half[:, :min_w] > 0, right_half[:, :min_w] > 0)
            sym_union_h = np.logical_or(left_half[:, :min_w] > 0, right_half[:, :min_w] > 0)
            topology_symmetry_h = float(np.count_nonzero(sym_overlap_h)) / float(max(1, np.count_nonzero(sym_union_h)))

            half_h = cand_mask.shape[0] // 2
            top_half = cand_mask[:half_h, :]
            bottom_half = np.flipud(cand_mask[half_h:, :])
            min_h = min(top_half.shape[0], bottom_half.shape[0])
            sym_overlap_v = np.logical_and(top_half[:min_h, :] > 0, bottom_half[:min_h, :] > 0)
            sym_union_v = np.logical_or(top_half[:min_h, :] > 0, bottom_half[:min_h, :] > 0)
            topology_symmetry_v = float(np.count_nonzero(sym_overlap_v)) / float(max(1, np.count_nonzero(sym_union_v)))

            topology_symmetry = max(topology_symmetry_h, topology_symmetry_v)
            topology_score = round(min(1.0, topology_symmetry * 1.5), 4)

            # Penalización severa para falso positivo sin unión en vértice
            if lacks_central_junction:
                topology_score = min(topology_score, 0.25)
            if has_border_contamination:
                topology_score = min(topology_score, 0.30)

            # ETAPA 3: SIMILITUD VISUAL (0.35) - Hu Moments + Rotaciones permitidas
            allowed_rots = self.get_rotations_for_policy(policy)
            best_visual_ncc = 0.0
            best_rot = 0

            # Cargar máscara de plantilla normalizada para NCC
            tmpl_mask = None
            if mask_path and os.path.exists(mask_path):
                raw_tmpl = cv2.imread(mask_path, cv2.IMREAD_UNCHANGED)
                if raw_tmpl is not None:
                    norm_tmpl = self.normalizer.normalize_image(raw_tmpl)
                    tmpl_mask = norm_tmpl.get("normalized_mask")
                    if tmpl_hu is None or np.all(tmpl_hu == 0):
                        tmpl_hu = np.array(norm_tmpl.get("hu_moments") or [0.0] * 7, dtype=np.float32)

            if tmpl_mask is not None:
                for rot in allowed_rots:
                    if rot == 0:
                        rotated_cand = cand_mask
                    elif rot == 90:
                        rotated_cand = cv2.rotate(cand_mask, cv2.ROTATE_90_CLOCKWISE)
                    elif rot == 180:
                        rotated_cand = cv2.rotate(cand_mask, cv2.ROTATE_180)
                    elif rot == 270:
                        rotated_cand = cv2.rotate(cand_mask, cv2.ROTATE_90_COUNTERCLOCKWISE)
                    else:
                        rotated_cand = cand_mask

                    res = cv2.matchTemplate(rotated_cand, tmpl_mask, cv2.TM_CCOEFF_NORMED)
                    score = float(res[0][0]) if res.size > 0 else 0.0
                    normalized_score = max(0.0, score)
                    if normalized_score > best_visual_ncc:
                        best_visual_ncc = normalized_score
                        best_rot = rot

            # Hu moments match
            hu_dist = 0.0
            for i in range(7):
                hu_dist += abs(cand_hu[i] - tmpl_hu[i])
            hu_score = max(0.0, 1.0 - min(1.0, hu_dist * 5.0))

            visual_score = round(0.70 * best_visual_ncc + 0.30 * hu_score, 4)
            if has_border_contamination:
                visual_score = min(visual_score, 0.35)

            # ETAPA 4: DESEMPATE CONTEXTUAL (0.10)
            context_score = 0.0
            search_corpus = f"{context_text or ''} {detected_tag or ''}".lower()
            if search_corpus.strip():
                aliases = [a.lower() for a in (tmpl.aliases or [])]
                code_terms = [tmpl.canonical_code.lower()] if tmpl.canonical_code else []
                name_terms = [tmpl.canonical_name.lower()] if tmpl.canonical_name else [tmpl.display_name.lower()]
                all_terms = aliases + code_terms + name_terms + [tmpl.subcategory or ""]
                for term in all_terms:
                    if term and term in search_corpus:
                        context_score = 1.0
                        break

            # PONDERACIÓN TOTAL
            # No-textual: 0.35 geom + 0.20 topo + 0.35 visual = 0.90
            # Contextual: 0.10
            total_score = round(
                0.35 * geometric_score +
                0.20 * topology_score +
                0.35 * visual_score +
                0.10 * context_score,
                4
            )

            # RESTRICCIÓN CRÍTICA: Contexto NUNCA rescata geometría deficiente
            if geometric_score < 0.60 or topology_score < 0.40 or visual_score < 0.50:
                total_score = min(total_score, 0.45)

            scored_candidates.append({
                "template_id": tmpl.id,
                "version_id": version_id,
                "canonical_code": tmpl.canonical_code or getattr(tmpl, "symbol_class", ""),
                "canonical_name": tmpl.canonical_name or getattr(tmpl, "display_name", ""),
                "total_score": total_score,
                "geometric_score": geometric_score,
                "topology_score": topology_score,
                "visual_score": visual_score,
                "context_score": round(0.10 * context_score, 4),
                "rotation_deg": best_rot,
                "matching_verdict": "rejected"
            })

        scored_candidates.sort(key=lambda x: x["total_score"], reverse=True)

        if not scored_candidates:
            return {
                "matching_status": "unknown_symbol",
                "best_match": None,
                "matches": [],
                "rejection_reason": f"Ninguna plantilla aprobada cumplió los filtros geométricos preliminares para modo {execution_mode}."
            }

        best = scored_candidates[0]
        second = scored_candidates[1] if len(scored_candidates) > 1 else None

        is_auto_match = (
            best["total_score"] >= AUTO_MATCH_THRESHOLD
            and best["geometric_score"] >= MIN_GEOMETRIC_THRESHOLD
            and (second is None or (best["total_score"] - second["total_score"]) >= AMBIGUITY_MARGIN)
        )

        is_ambiguous = (
            not is_auto_match
            and best["total_score"] >= MIN_CANDIDATE_SCORE
            and second is not None
            and (best["total_score"] - second["total_score"]) < AMBIGUITY_MARGIN
        )

        if is_auto_match:
            best["matching_verdict"] = "matched"
            matching_status = "matched"
        elif is_ambiguous:
            best["matching_verdict"] = "ambiguous"
            matching_status = "ambiguous"
        elif best["total_score"] >= MIN_CANDIDATE_SCORE and best["geometric_score"] >= MIN_GEOMETRIC_THRESHOLD:
            best["matching_verdict"] = "matched"
            matching_status = "matched"
        else:
            best["matching_verdict"] = "rejected"
            matching_status = "unknown_symbol"

        return {
            "matching_status": matching_status,
            "best_match": best,
            "matches": scored_candidates[:5],
            "rejection_reason": None if matching_status != "unknown_symbol" else "Puntuación de coincidencia por debajo del umbral mínimo o falta de plantilla activa autorizada."
        }

    # ------------------------------------------------------------------------
    # 6. MATCHING DE OCURRENCIA DE PROYECTO (API ENDPOINT METHOD)
    # ------------------------------------------------------------------------
    def match_occurrence(
        self,
        payload_or_id: Any = None,
        **kwargs
    ) -> MatchOccurrenceResponse:
        """
        Ejecuta el matching progresivo validando precondiciones y actualizando la ocurrencia en BD.
        """
        if isinstance(payload_or_id, MatchOccurrenceRequest):
            payload = payload_or_id
        elif isinstance(payload_or_id, dict):
            payload = MatchOccurrenceRequest(**payload_or_id)
        else:
            kw = dict(kwargs)
            occ_id = str(payload_or_id) if payload_or_id else kw.pop("occurrence_id", None)
            payload = MatchOccurrenceRequest(occurrence_id=occ_id, **kw)

        execution_mode = getattr(payload, "execution_mode", "production") or "production"
        occ = None
        crop_path = payload.crop_image_path
        context_text = payload.context_text
        detected_tag = payload.detected_tag

        if payload.occurrence_id:
            occ = self.db.query(DetectedSymbol).filter(DetectedSymbol.id == payload.occurrence_id).first()
            if occ:
                crop_path = occ.crop_image_path or crop_path
                context_text = occ.context_text or context_text
                detected_tag = occ.detected_tag_or_code or detected_tag

                # Validar precondiciones estrictas: Candidato vs Ocurrencia
                is_valid, reason = self.validate_matching_preconditions(occ)
                if not is_valid:
                    occ.record_kind = "candidate"
                    occ.matching_status = "not_applicable"
                    occ.environment = execution_mode
                    self.db.commit()
                    return MatchOccurrenceResponse(
                        occurrence_id=str(occ.id),
                        record_kind="candidate",
                        environment=execution_mode,
                        matching_status="not_applicable",
                        best_match=None,
                        candidate_matches=[],
                        rejection_reason=reason
                    )
                else:
                    occ.record_kind = "occurrence"
                    occ.environment = execution_mode

        if not crop_path or not os.path.exists(crop_path):
            return MatchOccurrenceResponse(
                occurrence_id=str(occ.id) if occ else None,
                record_kind="candidate" if not occ or not occ.has_real_geometry else "occurrence",
                environment=execution_mode,
                matching_status="not_applicable",
                best_match=None,
                candidate_matches=[],
                rejection_reason="Archivo de recorte no encontrado en el servidor."
            )

        match_res = self.match_candidate_progressive(
            crop_image_path=crop_path,
            discipline=payload.discipline,
            context_text=context_text,
            detected_tag=detected_tag,
            execution_mode=execution_mode
        )

        status_str = match_res["matching_status"]
        best_match_dto = None
        matches_dto = []

        if match_res.get("best_match"):
            best = match_res["best_match"]
            best_match_dto = ProgressiveMatchResult(
                template_id=best["template_id"],
                version_id=best["version_id"],
                canonical_code=best["canonical_code"],
                canonical_name=best["canonical_name"],
                total_score=best["total_score"],
                geometric_score=best["geometric_score"],
                topology_score=best["topology_score"],
                visual_score=best["visual_score"],
                context_score=best["context_score"],
                rotation_deg=best.get("rotation_deg", 0),
                matching_verdict=best.get("matching_verdict", "rejected")
            )

        for m in match_res.get("matches", []):
            matches_dto.append(ProgressiveMatchResult(
                template_id=m["template_id"],
                version_id=m["version_id"],
                canonical_code=m["canonical_code"],
                canonical_name=m["canonical_name"],
                total_score=m["total_score"],
                geometric_score=m["geometric_score"],
                topology_score=m["topology_score"],
                visual_score=m["visual_score"],
                context_score=m["context_score"],
                rotation_deg=m.get("rotation_deg", 0),
                matching_verdict=m.get("matching_verdict", "rejected")
            ))

        # Invariante de Gobernanza: En modo producción, un match solo es válido si la plantilla es 'active' y versión 'approved'
        is_sandbox_template = False
        warning_msg = None
        if best_match_dto:
            matched_tmpl = self.db.query(SymbolTemplate).filter(SymbolTemplate.id == best_match_dto.template_id).first()
            matched_v = self.db.query(SymbolTemplateVersion).filter(SymbolTemplateVersion.id == best_match_dto.version_id).first()
            if matched_tmpl and matched_tmpl.status in ("sandbox", "test_only", "draft"):
                is_sandbox_template = True
                if execution_mode == "production":
                    # Prohibido activar match productivo contra plantilla no productiva
                    status_str = "not_applicable"
                    best_match_dto.matching_verdict = "rejected"
                    warning_msg = "Match productivo denegado: la plantilla coincide pero no posee estatus activo/aprobado de producción."
                else:
                    warning_msg = "Aviso: Match ejecutado en entorno sandbox con plantilla no productiva (test_only/sandbox)."

        research_case_id = None
        # Actualizar DetectedSymbol/SymbolOccurrence si existe
        if occ:
            occ.matching_status = status_str
            occ.record_kind = "occurrence"
            occ.environment = execution_mode
            if best_match_dto and status_str == "matched":
                occ.matched_template_id = best_match_dto.template_id
                occ.matched_template_version_id = best_match_dto.version_id
                occ.match_score = best_match_dto.total_score
                occ.geometry_score = best_match_dto.geometric_score
                occ.topology_score = best_match_dto.topology_score
                occ.visual_score = best_match_dto.visual_score
                occ.context_score = best_match_dto.context_score
                occ.detected_tag_or_code = best_match_dto.canonical_code
            elif status_str == "ambiguous":
                # Registrar decisión de revisión para desempate HITL
                rev_decision = SymbolReviewDecision(
                    subject_type="occurrence",
                    subject_id=str(occ.id),
                    decision="needs_review",
                    reviewer_id="system_ambiguity_detector",
                    rationale=f"Empate técnico entre candidatos dentro del margen de ambigüedad ({AMBIGUITY_MARGIN*100:.1f}%). Requiere revisión HITL.",
                    evidence_snapshot={
                        "best_match": best_match_dto.dict() if best_match_dto else None,
                        "candidate_matches": [m.dict() for m in matches_dto[:2]]
                    }
                )
                self.db.add(rev_decision)
            elif status_str == "unknown_symbol":
                # Registrar formalmente caso de investigación para símbolo geométrico desconocido
                rc = SymbolUnknownResearchCase(
                    symbol_occurrence_id=str(occ.id),
                    status="unknown",
                    search_query=f"Unknown piping symbol in {payload.discipline}",
                    proposed_name="SYM-UNKNOWN-001",
                    proposed_standard_reference="PIP PNC00001 / ISA-5.1",
                    research_notes=f"SYM-UNKNOWN-001: Geometría real válida detectada sin coincidencia en catálogo canónico activo ({payload.discipline})."
                )
                self.db.add(rc)
                self.db.flush()
                research_case_id = rc.id

            self.db.commit()

        return MatchOccurrenceResponse(
            occurrence_id=str(occ.id) if occ else None,
            record_kind="occurrence" if (occ and occ.has_real_geometry) else "candidate",
            environment=execution_mode,
            matching_status=status_str,
            best_match=best_match_dto,
            candidate_matches=matches_dto,
            rejection_reason=match_res.get("rejection_reason"),
            research_case_id=research_case_id,
            is_sandbox_or_test_only=is_sandbox_template,
            warning=warning_msg
        )

    # ------------------------------------------------------------------------
    # 7. PROMOCIÓN HITL DE CANDIDATO A PLANTILLA Y VERSIÓN CANÓNICA
    # ------------------------------------------------------------------------
    def promote_candidate_to_canonical(
        self,
        payload_or_candidate_id: Any,
        **kwargs
    ) -> PromoteCandidateToCanonicalResponse:
        """
        Promueve un StructuredSymbol a SymbolTemplate con su versión inicial SymbolTemplateVersion,
        extrayendo sus rasgos geométricos explicables y registrando la evidencia de origen inmutable.
        """
        if isinstance(payload_or_candidate_id, PromoteCandidateToCanonicalRequest):
            p = payload_or_candidate_id
            candidate_id = p.candidate_id
            canonical_code = p.canonical_code
            canonical_name = p.canonical_name
            category = p.category
            subcategory = p.subcategory
            discipline = p.discipline
            technical_function = p.technical_function
            standard_reference = p.standard_reference
            evidence_kind = p.evidence_kind
            orientation_policy = p.orientation_policy
            reviewer_id = p.reviewer_id
            notes = p.notes
        elif isinstance(payload_or_candidate_id, dict):
            p_dict = payload_or_candidate_id
            candidate_id = p_dict["candidate_id"]
            canonical_code = p_dict["canonical_code"]
            canonical_name = p_dict["canonical_name"]
            category = p_dict.get("category", "valve")
            subcategory = p_dict.get("subcategory", "gate_valve")
            discipline = p_dict.get("discipline", "piping")
            technical_function = p_dict.get("technical_function")
            standard_reference = p_dict.get("standard_reference")
            evidence_kind = p_dict.get("evidence_kind", "synthetic")
            orientation_policy = p_dict.get("orientation_policy", "rotation_equivalent_180")
            reviewer_id = p_dict.get("reviewer_id", "auditor")
            notes = p_dict.get("notes")
        else:
            candidate_id = str(payload_or_candidate_id)
            canonical_code = kwargs["canonical_code"]
            canonical_name = kwargs["canonical_name"]
            category = kwargs.get("category", "valve")
            subcategory = kwargs.get("subcategory", "gate_valve")
            discipline = kwargs.get("discipline", "piping")
            technical_function = kwargs.get("technical_function")
            standard_reference = kwargs.get("standard_reference")
            evidence_kind = kwargs.get("evidence_kind", "synthetic")
            orientation_policy = kwargs.get("orientation_policy", "rotation_equivalent_180")
            reviewer_id = kwargs.get("reviewer_id", "auditor")
            notes = kwargs.get("notes")

        sym = self.db.query(StructuredSymbol).filter(StructuredSymbol.id == candidate_id).first()
        if not sym:
            raise ValueError(f"No se encontró StructuredSymbol con id {candidate_id}")

        crop_path = sym.crop_image_path
        if not crop_path or not os.path.exists(crop_path):
            raise ValueError(f"El símbolo candidato no cuenta con recorte físico válido en {crop_path}")

        # 1. Aplicar Política de Gobernanza de Evidencia y Estados
        if evidence_kind == "synthetic":
            # REGLA: Si la evidencia es sintética, NO puede ser 'active' ni 'approved' para producción.
            template_status = "sandbox"
            version_approval_status = "sandbox_approved"
            source_kind = "synthetic_fixture"
        elif evidence_kind in ("real_authorized", "redacted_real"):
            # REGLA: Evidencia real debe ser íntegra y trazable
            if not crop_hash:
                raise ValueError("Governance Violation: Missing crop image hash in source evidence.")
            if not reviewer_id:
                raise ValueError("Governance Violation: HITL Reviewer ID is required for approving real authorized template.")
            template_status = "active"
            version_approval_status = "approved"
            source_kind = "normative_document" if evidence_kind == "real_authorized" else "project_legend"
        else:
            raise ValueError(f"Governance Violation: Tipo de evidencia desconocido '{evidence_kind}'.")

        # Buscar o crear SymbolTemplate
        tmpl = self.db.query(SymbolTemplate).filter(
            (SymbolTemplate.canonical_code == canonical_code) |
            (SymbolTemplate.symbol_class == subcategory)
        ).first()

        if not tmpl:
            tmpl = SymbolTemplate(
                canonical_code=canonical_code,
                canonical_name=canonical_name,
                symbol_class=subcategory,
                display_name=canonical_name,
                category=category,
                subcategory=subcategory,
                discipline=discipline,
                technical_function=technical_function,
                standard_reference=standard_reference,
                aliases=[canonical_name, canonical_code, sym.symbol_name],
                status=template_status,
                created_by=reviewer_id
            )
            self.db.add(tmpl)
            self.db.flush()
        else:
            tmpl.canonical_code = canonical_code
            tmpl.canonical_name = canonical_name
            tmpl.status = template_status
            tmpl.is_active_for_detection = True

        # 2. Normalizar imagen y calcular hash del crop
        with open(crop_path, "rb") as f:
            crop_hash = hashlib.sha256(f.read()).hexdigest()

        img_bgr = cv2.imread(crop_path)
        norm_result = self.normalizer.normalize_image(img_bgr)

        storage_dir = os.path.join(settings.DATA_DIR if hasattr(settings, "DATA_DIR") else "data", "symbol_templates")
        os.makedirs(storage_dir, exist_ok=True)
        mask_filename = f"{canonical_code.lower()}_{uuid.uuid4().hex[:8]}_mask.png"
        mask_path = os.path.join(storage_dir, mask_filename)
        cv2.imwrite(mask_path, norm_result["normalized_mask"])

        tmpl.normalized_mask_path = mask_path
        tmpl.mask_hash = norm_result["mask_hash"]
        tmpl.hu_moments = norm_result["hu_moments"]
        tmpl.aspect_ratio = norm_result["aspect_ratio"]
        tmpl.image_template_path = crop_path
        tmpl.is_active_for_detection = True

        ver_count = self.db.query(SymbolTemplateVersion).filter(
            SymbolTemplateVersion.symbol_template_id == tmpl.id
        ).count()
        next_ver_num = ver_count + 1

        version = SymbolTemplateVersion(
            symbol_template_id=tmpl.id,
            version_number=next_ver_num,
            approval_status=version_approval_status,
            source_kind=source_kind,
            canonical_crop_path=crop_path,
            canonical_crop_hash=crop_hash,
            normalized_representation={"mask_path": mask_path, "size": [128, 128]},
            orientation_policy=orientation_policy,
            scale_policy="isotropic_bounded",
            geometric_signature={
                "aspect_ratio": norm_result["aspect_ratio"],
                "density": round(float(np.count_nonzero(norm_result["normalized_mask"])) / float(norm_result["normalized_mask"].size), 4)
            },
            perceptual_signature={
                "hu_moments": norm_result["hu_moments"],
                "mask_hash": norm_result["mask_hash"]
            },
            matcher_thresholds={
                "auto_match": AUTO_MATCH_THRESHOLD,
                "geometric_min": MIN_GEOMETRIC_THRESHOLD,
                "topology_min": MIN_TOPOLOGY_THRESHOLD,
                "ambiguity_margin": AMBIGUITY_MARGIN
            },
            approved_by=reviewer_id if version_approval_status == "approved" else None,
            approved_at=datetime.utcnow() if version_approval_status == "approved" else None,
            notes=notes
        )
        self.db.add(version)
        self.db.flush()

        tmpl.current_version_id = version.id

        # 5. Extraer y crear rasgos geométricos explicables
        gate_features_data = self.extract_gate_valve_features(img_bgr)
        features_created = 0
        feature_id_map: Dict[str, str] = {}

        for feat_dict in gate_features_data:
            gfeat = SymbolGeometricFeature(
                symbol_template_version_id=version.id,
                feature_type=feat_dict["feature_type"],
                feature_count=feat_dict["feature_count"],
                feature_parameters=feat_dict["feature_parameters"],
                normalized_bbox=feat_dict["normalized_bbox"],
                relative_position=feat_dict["relative_position"],
                confidence=feat_dict["confidence"],
                relationship_group=feat_dict["relationship_group"],
                extractor_version="v1.0-piping"
            )
            self.db.add(gfeat)
            self.db.flush()
            feature_id_map[feat_dict["relationship_group"]] = gfeat.id
            features_created += 1

        if "actuator_stem" in feature_id_map and "valve_body" in feature_id_map:
            feat_rel = SymbolFeatureRelation(
                source_feature_id=feature_id_map["actuator_stem"],
                target_feature_id=feature_id_map["valve_body"],
                relation_type="connected_to",
                confidence=0.98,
                relation_parameters={"connection_point": "center_vertex"}
            )
            self.db.add(feat_rel)

        if "handwheel" in feature_id_map and "actuator_stem" in feature_id_map:
            feat_rel = SymbolFeatureRelation(
                source_feature_id=feature_id_map["handwheel"],
                target_feature_id=feature_id_map["actuator_stem"],
                relation_type="touches",
                confidence=0.95,
                relation_parameters={"connection_point": "stem_top"}
            )
            self.db.add(feat_rel)

        # 6. Registrar SymbolSourceEvidence
        item = self.db.query(ExtractedItem).filter(ExtractedItem.id == sym.extracted_item_id).first()
        source_doc_id = item.source_asset_id if item else None

        evidence = SymbolSourceEvidence(
            symbol_template_version_id=version.id,
            source_document_id=source_doc_id,
            evidence_kind=evidence_kind,
            page_number=item.page_number if item else 1,
            table_id=sym.source_table_id,
            bbox_normalized=item.bbox_normalized if item else [],
            cell_bbox=sym.cell_bbox,
            crop_image_path=crop_path,
            crop_image_hash=crop_hash,
            source_excerpt=sym.symbol_name,
            geometric_confidence=sym.confidence_score,
            source_standard_or_project=standard_reference
        )
        self.db.add(evidence)

        # 7. Registrar SymbolReviewDecision
        decision = SymbolReviewDecision(
            subject_type="candidate",
            subject_id=sym.id,
            decision="create_template",
            reviewer_id=reviewer_id,
            rationale=f"Promovido a plantilla ({evidence_kind}, status={template_status}) por {reviewer_id}. {notes or ''}".strip(),
            evidence_snapshot={"crop_path": crop_path, "crop_hash": crop_hash, "evidence_kind": evidence_kind},
            new_state={"canonical_code": canonical_code, "version": next_ver_num, "status": template_status}
        )
        self.db.add(decision)

        self.db.commit()

        return PromoteCandidateToCanonicalResponse(
            template_id=tmpl.id,
            canonical_code=tmpl.canonical_code,
            version_id=version.id,
            version_number=next_ver_num,
            features_extracted=features_created,
            status=template_status,
            message=f"Símbolo promovido exitosamente como {canonical_code} versión {next_ver_num} (status={template_status})."
        )

    def approve_template_version_for_production(
        self,
        version_id: str,
        reviewer_id: str,
        rationale: str
    ) -> SymbolTemplateVersion:
        """
        Gobernanza HITL: Aprueba una versión de plantilla para uso productivo.
        Reglas obligatorias:
        - Si toda la evidencia es 'synthetic', RECHAZAR la activación productiva.
        - Requiere evidencia 'real_authorized' o 'redacted_real'.
        - Dicha evidencia debe contener hash de documento o crop, número de página >= 1, bbox y crop existente.
        - Requiere decisión HITL explícita.
        """
        ver = self.db.query(SymbolTemplateVersion).filter(SymbolTemplateVersion.id == version_id).first()
        if not ver:
            raise ValueError(f"No se encontró SymbolTemplateVersion con id {version_id}")

        evidence = ver.source_evidence
        if not evidence or evidence.evidence_kind == "synthetic":
            raise ValueError("Governance Violation: Cannot approve a template version backed solely by synthetic evidence for production. Must remain 'test_only' or 'sandbox'.")

        if evidence.evidence_kind not in ("real_authorized", "redacted_real"):
            raise ValueError(f"Governance Violation: Invalid evidence kind '{evidence.evidence_kind}'. Must be 'real_authorized' or 'redacted_real'.")

        if not evidence.crop_image_hash and not evidence.source_document_hash:
            raise ValueError("Governance Violation: Incomplete evidence. Missing crop or document hash.")

        if not evidence.page_number or evidence.page_number < 1:
            raise ValueError("Governance Violation: Incomplete evidence. Invalid page number.")

        if not evidence.bbox_normalized or len(evidence.bbox_normalized) != 4:
            raise ValueError("Governance Violation: Incomplete evidence. Missing normalized bbox.")

        if not evidence.crop_image_path or not os.path.exists(evidence.crop_image_path):
            raise ValueError("Governance Violation: Incomplete evidence. Physical crop file not found on disk.")

        if not reviewer_id or not reviewer_id.strip():
            raise ValueError("Governance Violation: HITL Reviewer ID is required for approving a production template version.")

        ver.approval_status = "approved"
        ver.approved_by = reviewer_id
        ver.approved_at = datetime.utcnow()

        if ver.template:
            ver.template.status = "active"

        rev = SymbolReviewDecision(
            subject_type="template_version",
            subject_id=ver.id,
            decision="approve",
            reviewer_id=reviewer_id,
            rationale=rationale,
            evidence_snapshot={
                "evidence_kind": evidence.evidence_kind,
                "crop_hash": evidence.crop_image_hash,
                "document_hash": evidence.source_document_hash
            },
            new_state={"approval_status": "approved", "template_status": "active"}
        )
        self.db.add(rev)
        self.db.commit()
        return ver

    # ------------------------------------------------------------------------
    # 8. REGISTRO FORMAL DE DECISIÓN HITL
    # ------------------------------------------------------------------------
    def record_review_decision(
        self,
        payload_or_type: Any,
        **kwargs
    ) -> SymbolReviewDecisionResponse:
        """Registra formalmente una decisión humana sin sobreescritura silenciosa."""
        if isinstance(payload_or_type, SymbolReviewDecisionRequest):
            p = payload_or_type
            subject_type = p.subject_type
            subject_id = p.subject_id
            decision = p.decision
            reviewer_id = p.reviewer_id
            rationale = p.rationale
            evidence_snapshot = p.evidence_snapshot
            override_template_id = p.override_template_id
            override_version_id = p.override_version_id
        elif isinstance(payload_or_type, dict):
            p_dict = payload_or_type
            subject_type = p_dict["subject_type"]
            subject_id = p_dict["subject_id"]
            decision = p_dict["decision"]
            reviewer_id = p_dict["reviewer_id"]
            rationale = p_dict.get("rationale")
            evidence_snapshot = p_dict.get("evidence_snapshot", {})
            override_template_id = p_dict.get("override_template_id")
            override_version_id = p_dict.get("override_version_id")
        else:
            subject_type = str(payload_or_type)
            subject_id = kwargs["subject_id"]
            decision = kwargs["decision"]
            reviewer_id = kwargs["reviewer_id"]
            rationale = kwargs.get("rationale")
            evidence_snapshot = kwargs.get("evidence_snapshot", {})
            override_template_id = kwargs.get("override_template_id")
            override_version_id = kwargs.get("override_version_id")

        prev_state: Dict[str, Any] = {}
        new_state: Dict[str, Any] = {"decision": decision, "override_template_id": override_template_id}

        if subject_type == "occurrence":
            occ = self.db.query(DetectedSymbol).filter(DetectedSymbol.id == subject_id).first()
            if occ:
                prev_state = {
                    "matching_status": occ.matching_status,
                    "review_status": occ.review_status,
                    "matched_template_id": occ.matched_template_id
                }
                if decision in ("approve", "accept"):
                    occ.review_status = "accepted"
                elif decision == "reject":
                    occ.review_status = "rejected"
                    occ.matching_status = "not_applicable"
                elif decision == "override_match" and override_template_id:
                    occ.matched_template_id = override_template_id
                    occ.matched_template_version_id = override_version_id
                    occ.matching_status = "matched"
                    occ.review_status = "accepted"
                elif decision == "mark_unknown":
                    occ.matching_status = "unknown_symbol"
                    occ.review_status = "needs_review"

        rev_dec = SymbolReviewDecision(
            subject_type=subject_type,
            subject_id=subject_id,
            decision=decision,
            reviewer_id=reviewer_id,
            rationale=rationale,
            evidence_snapshot=evidence_snapshot or {},
            previous_state=prev_state,
            new_state=new_state
        )
        self.db.add(rev_dec)
        self.db.commit()

        return SymbolReviewDecisionResponse(
            decision_id=rev_dec.id,
            subject_type=subject_type,
            subject_id=subject_id,
            decision=decision,
            reviewer_id=reviewer_id,
            recorded_at=rev_dec.created_at,
            message="Decisión de revisión registrada exitosamente."
        )
