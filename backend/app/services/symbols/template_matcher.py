"""
template_matcher.py

Motor de matching geométrico determinista para SymbolTemplate:
- Admisión estricta: solo evalúa candidatos con evidencia geométrica.
- Filtro preliminar de disciplina, aspect ratio y primitivas.
- Correlación cruzada normalizada (OpenCV NCC TM_CCOEFF_NORMED) en 0°, 90°, 180° y 270°.
- Comparación euclidiana de vectores de Momentos de Hu logarítmicos.
- Ponderación de score compuesto: 0.65 * NCC + 0.35 * Hu.
- Umbrales de clasificación: Auto-Match (>= 0.82), Sugerencia HITL (0.68 - 0.82), Descarte/Unknown (< 0.68).
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import cv2
from sqlalchemy.orm import Session

from app.db.models.template_memory import SymbolTemplate
from app.services.symbols.template_normalizer import TemplateNormalizer

logger = logging.getLogger(__name__)

# Umbrales canónicos de decisión
AUTO_MATCH_THRESHOLD = 0.82
HITL_SUGGESTION_THRESHOLD = 0.68

ORTHOGONAL_ROTATIONS = [0, 90, 180, 270]


class TemplateMatcher:
    """Motor de reconocimiento visual determinista basado en NCC y Momentos de Hu."""

    def __init__(self, db: Session, normalizer: Optional[TemplateNormalizer] = None):
        self.db = db
        self.normalizer = normalizer or TemplateNormalizer()

    def match_candidate_image(
        self,
        candidate_img: np.ndarray,
        discipline: Optional[str] = None,
        organization_id: Optional[str] = None,
        allowed_rotations: Optional[List[int]] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Normaliza el candidato y lo compara contra todos los SymbolTemplate activos en BD.
        """
        cand_features = self.normalizer.normalize_image(candidate_img)
        return self.match_candidate_features(
            cand_features=cand_features,
            discipline=discipline,
            organization_id=organization_id,
            allowed_rotations=allowed_rotations,
            top_k=top_k
        )

    def match_candidate_features(
        self,
        cand_features: Dict[str, Any],
        discipline: Optional[str] = None,
        organization_id: Optional[str] = None,
        allowed_rotations: Optional[List[int]] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Realiza el matching a partir de los features normalizados del candidato.
        """
        rotations = allowed_rotations or ORTHOGONAL_ROTATIONS
        cand_mask = cand_features.get("normalized_mask")
        cand_hu = np.array(cand_features.get("hu_moments") or [0.0] * 7, dtype=np.float32)
        cand_ar = float(cand_features.get("aspect_ratio") or 1.0)
        cand_primitives = cand_features.get("primitive_signature") or {}

        if cand_mask is None or np.count_nonzero(cand_mask) < 20:
            # Máscara vacía o insignificante
            return []

        # 1. Consultar plantillas activas de la BD con filtrado de tenant/global
        query = self.db.query(SymbolTemplate).filter(SymbolTemplate.is_active_for_detection == True)
        if organization_id:
            query = query.filter(
                (SymbolTemplate.organization_id == organization_id) | (SymbolTemplate.organization_id == None)
            )
        else:
            query = query.filter(SymbolTemplate.organization_id == None)

        templates = query.all()
        if not templates:
            return []

        scored_matches: List[Dict[str, Any]] = []

        for tmpl in templates:
            # Descriptores de la plantilla
            tmpl_hu = np.array(tmpl.hu_moments or [0.0] * 7, dtype=np.float32)
            tmpl_ar = float(tmpl.aspect_ratio or 1.0)
            tmpl_mask_path = tmpl.normalized_mask_path

            # Reconstruir o cargar la máscara normalizada de la plantilla
            tmpl_mask = self._load_or_create_template_mask(tmpl)
            if tmpl_mask is None:
                continue

            # 2. Filtro preliminar de aspect ratio para rotación 0/180 y 90/270
            # Si el AR es drásticamente distinto (factor > 3.0), no puede ser la misma forma
            ar_diff_direct = abs(cand_ar - tmpl_ar) / max(tmpl_ar, 0.01)
            ar_diff_perp = abs(cand_ar - (1.0 / max(tmpl_ar, 0.01))) / max(1.0 / max(tmpl_ar, 0.01), 0.01)
            if min(ar_diff_direct, ar_diff_perp) > 2.5:
                continue

            # 3. Comparación Multi-Rotación (OpenCV NCC)
            best_ncc = 0.0
            best_rot = 0

            for rot_deg in rotations:
                rotated_tmpl = self._rotate_mask(tmpl_mask, rot_deg)
                ncc_val = self._compute_ncc(cand_mask, rotated_tmpl)
                if ncc_val > best_ncc:
                    best_ncc = ncc_val
                    best_rot = rot_deg

            # 4. Distancia de Momentos de Hu
            hu_dist = float(np.linalg.norm(cand_hu - tmpl_hu))
            # Normalización del score Hu a [0.0, 1.0] (distancia típica entre símbolos distintos es 4 - 15)
            hu_score = max(0.0, min(1.0, 1.0 - (hu_dist / 8.0)))

            # 5. Score Compuesto Puro
            composite_score = round(0.65 * best_ncc + 0.35 * hu_score, 4)

            # Clasificación de política
            if composite_score >= AUTO_MATCH_THRESHOLD:
                decision = "auto_match"
            elif composite_score >= HITL_SUGGESTION_THRESHOLD:
                decision = "hitl_suggestion"
            else:
                decision = "unknown"

            scored_matches.append({
                "template_id": tmpl.id,
                "symbol_class": tmpl.symbol_class,
                "display_name": tmpl.display_name,
                "score": composite_score,
                "ncc_score": round(best_ncc, 4),
                "hu_score": round(hu_score, 4),
                "best_rotation_deg": best_rot,
                "decision_policy": decision,
                "match_evidence": {
                    "ncc_score": round(best_ncc, 4),
                    "hu_score": round(hu_score, 4),
                    "hu_distance": round(hu_dist, 4),
                    "rotation_deg": best_rot,
                    "aspect_ratio_candidate": round(cand_ar, 3),
                    "aspect_ratio_template": round(tmpl_ar, 3)
                }
            })

        # Ordenar de mayor a menor score y retornar top-k
        scored_matches.sort(key=lambda x: x["score"], reverse=True)
        return scored_matches[:top_k]

    def _rotate_mask(self, mask: np.ndarray, rot_deg: int) -> np.ndarray:
        """Rota la máscara cuadrada ortogonalmente en 0, 90, 180 o 270 grados."""
        if rot_deg == 0:
            return mask
        elif rot_deg == 90:
            return cv2.rotate(mask, cv2.ROTATE_90_CLOCKWISE)
        elif rot_deg == 180:
            return cv2.rotate(mask, cv2.ROTATE_180)
        elif rot_deg == 270:
            return cv2.rotate(mask, cv2.ROTATE_90_COUNTERCLOCKWISE)
        else:
            # Rotación libre arbitraria
            center = (mask.shape[1] // 2, mask.shape[0] // 2)
            M = cv2.getRotationMatrix2D(center, -rot_deg, 1.0)
            return cv2.warpAffine(mask, M, (mask.shape[1], mask.shape[0]), flags=cv2.INTER_NEAREST)

    def _compute_ncc(self, img1: np.ndarray, img2: np.ndarray) -> float:
        """Calcula el coeficiente de correlación cruzada normalizada entre dos imágenes 128x128."""
        res = cv2.matchTemplate(img1, img2, cv2.TM_CCOEFF_NORMED)
        val = float(res[0][0])
        # Limitar al rango [0.0, 1.0]
        return max(0.0, min(1.0, val))

    def _load_or_create_template_mask(self, tmpl: SymbolTemplate) -> Optional[np.ndarray]:
        """Recupera la máscara 128x128 de la plantilla desde disco o la genera desde el crop original."""
        import os
        if tmpl.normalized_mask_path and os.path.exists(tmpl.normalized_mask_path):
            mask = cv2.imread(tmpl.normalized_mask_path, cv2.IMREAD_GRAYSCALE)
            if mask is not None:
                return mask

        # Fallback: si existe el crop original en image_template_path, normalizarlo
        if tmpl.image_template_path and os.path.exists(tmpl.image_template_path):
            try:
                norm_res = self.normalizer.normalize_from_path(
                    tmpl.image_template_path,
                    output_mask_path=tmpl.normalized_mask_path
                )
                return norm_res["normalized_mask"]
            except Exception as e:
                logger.warning(f"Error normalizando crop de plantilla {tmpl.id}: {e}")
                return None

        return None
