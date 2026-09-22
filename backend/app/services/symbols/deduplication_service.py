import os
import re
import uuid
import difflib
import logging
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
import numpy as np
from sqlalchemy.orm import Session

from app.db.models.intake_extractions import StructuredSymbol, ExtractedItem
from app.db.models.template_memory import SymbolTemplate, SymbolLibrary
from app.schemas.symbol import (
    DeduplicateSymbolsRequest, DeduplicateSymbolsResponse,
    DeduplicationCluster, VariantClusterItem
)

logger = logging.getLogger("plan_review.symbols.deduplication")


class SymbolDeduplicationService:
    """
    Motor de deduplicación multi-factor y agrupamiento de variantes para simbología técnica.
    Cumple con la condición de Fase 2:
    - dHash 64-bit se utiliza como señal perceptual, NO como identidad única.
    - Se combina de forma ponderada con aspect-ratio, tamaño físico en mm,
      familia canónica, normalización semántica de nombres, ontología ISA 5.1
      y coincidencia con plantillas existentes en template_memory.
    """

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------------
    # 1. CÁLCULO DE DHASH VISUAL (64-BIT HORIZONTAL DIFFERENCE)
    # ------------------------------------------------------------------------
    @staticmethod
    def compute_dhash(image_path: str, hash_size: int = 8) -> Optional[int]:
        """
        Calcula el Difference Hash (dHash) horizontal de 64 bits.
        Redimensiona a (hash_size + 1, hash_size) en escala de grises y compara
        píxeles adyacentes horizontalmente.
        """
        if not image_path or not os.path.exists(image_path):
            return None
        try:
            with Image.open(image_path) as img:
                img = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.BILINEAR)
                pixels = np.array(img, dtype=np.int32)
                diff = pixels[:, :-1] > pixels[:, 1:]
                decimal_value = 0
                for bit in diff.flatten():
                    decimal_value = (decimal_value << 1) | int(bit)
                return decimal_value
        except Exception as e:
            logger.warning(f"Error calculando dHash para {image_path}: {e}")
            return None

    @staticmethod
    def hamming_distance(hash1: int, hash2: int) -> int:
        """Calcula la distancia de Hamming entre dos hashes enteros."""
        x = hash1 ^ hash2
        return bin(x).count("1")

    def compute_visual_similarity(self, path1: Optional[str], path2: Optional[str]) -> float:
        """
        Calcula la similitud visual normalizada [0.0, 1.0] entre dos imágenes usando dHash.
        """
        if not path1 or not path2:
            return 0.50
        h1 = self.compute_dhash(path1)
        h2 = self.compute_dhash(path2)
        if h1 is None or h2 is None:
            return 0.50
        dist = self.hamming_distance(h1, h2)
        return max(0.0, 1.0 - (dist / 64.0))

    # ------------------------------------------------------------------------
    # 2. COMPARACIÓN GEOMÉTRICA (ASPECT RATIO + TAMAÑO FÍSICO ESTIMADO)
    # ------------------------------------------------------------------------
    @staticmethod
    def compute_geometric_similarity(sym1: StructuredSymbol, sym2: StructuredSymbol) -> float:
        """
        Compara el aspect ratio y el tamaño físico estimado en milímetros.
        """
        score = 0.5
        size1 = sym1.estimated_physical_size_mm or {}
        size2 = sym2.estimated_physical_size_mm or {}

        w1 = size1.get("width_mm", 0)
        h1 = size1.get("height_mm", 0)
        w2 = size2.get("width_mm", 0)
        h2 = size2.get("height_mm", 0)

        if w1 > 0 and h1 > 0 and w2 > 0 and h2 > 0:
            ar1 = w1 / max(h1, 0.001)
            ar2 = w2 / max(h2, 0.001)
            ar_diff = abs(ar1 - ar2) / max(ar1, ar2, 0.01)
            ar_sim = max(0.0, 1.0 - ar_diff)

            area1 = w1 * h1
            area2 = w2 * h2
            area_ratio = min(area1, area2) / max(area1, area2, 0.01)

            score = (ar_sim * 0.6) + (area_ratio * 0.4)
        return score

    # ------------------------------------------------------------------------
    # 3. NORMALIZACIÓN Y SIMILITUD SEMÁNTICA (ONTOLOGÍA ISA 5.1 / ASME)
    # ------------------------------------------------------------------------
    @staticmethod
    def normalize_name(name: Optional[str]) -> str:
        if not name:
            return ""
        text = name.lower()
        replacements = (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n"))
        for a, b in replacements:
            text = text.replace(a, b)
        stop_words = ["valvula", "de", "para", "tipo", "clase", "rf", "150", "300", "600", "pn", "asme", "isa", "norma"]
        tokens = [t for t in re.findall(r"[a-z0-9]+", text) if t not in stop_words]
        return " ".join(tokens)

    def compute_semantic_similarity(self, name1: Optional[str], name2: Optional[str], fam1: str, fam2: str) -> float:
        """
        Calcula similitud semántica y ontológica entre nombres y familias.
        """
        if fam1 and fam2 and fam1 != "general" and fam2 != "general" and fam1 != fam2:
            return 0.10

        n1 = self.normalize_name(name1)
        n2 = self.normalize_name(name2)

        if not n1 and not n2:
            return 0.60
        if n1 == n2:
            return 1.0

        ratio = difflib.SequenceMatcher(None, n1, n2).ratio()
        t1 = set(n1.split())
        t2 = set(n2.split())
        jaccard = len(t1 & t2) / max(len(t1 | t2), 1)

        # Si los tokens de uno están contenidos en el otro (ej. 'compuerta' dentro de 'compuerta manual')
        # indica que comparten el núcleo técnico (variante directa)
        containment = 1.0 if (t1 and t2 and (t1.issubset(t2) or t2.issubset(t1))) else 0.0

        return (ratio * 0.4) + (jaccard * 0.3) + (containment * 0.3)

    # ------------------------------------------------------------------------
    # 4. PUNTUACIÓN HÍBRIDA MULTI-FACTOR
    # ------------------------------------------------------------------------
    def compute_combined_similarity(
        self,
        sym1: StructuredSymbol,
        sym2: StructuredSymbol
    ) -> Tuple[float, float, float, float]:
        """
        Retorna (combined_score, visual_sim, semantic_sim, geometric_sim).
        """
        visual_sim = self.compute_visual_similarity(sym1.crop_image_path, sym2.crop_image_path)
        geometric_sim = self.compute_geometric_similarity(sym1, sym2)
        semantic_sim = self.compute_semantic_similarity(
            sym1.symbol_name, sym2.symbol_name,
            sym1.canonical_symbol_family, sym2.canonical_symbol_family
        )

        combined = (0.40 * visual_sim) + (0.40 * semantic_sim) + (0.20 * geometric_sim)

        if sym1.canonical_symbol_family == sym2.canonical_symbol_family and sym1.canonical_symbol_family != "general":
            combined = min(1.0, combined + 0.05)

        return combined, visual_sim, semantic_sim, geometric_sim

    # ------------------------------------------------------------------------
    # 5. MATCHER CON TEMPLATES EXISTENTES EN TEMPLATE_MEMORY
    # ------------------------------------------------------------------------
    def find_best_existing_template(self, sym: StructuredSymbol) -> Optional[Dict[str, Any]]:
        """
        Busca si el candidato tiene una plantilla afín ya registrada en SymbolTemplate.
        """
        try:
            templates = self.db.query(SymbolTemplate).filter(
                SymbolTemplate.symbol_class == sym.canonical_symbol_family
            ).all()

            best_match = None
            best_score = 0.0

            for t in templates:
                sem_sim = self.compute_semantic_similarity(
                    sym.symbol_name, t.display_name,
                    sym.canonical_symbol_family, t.symbol_class
                )
                vis_sim = self.compute_visual_similarity(sym.crop_image_path, t.image_template_path)
                score = (0.5 * sem_sim) + (0.5 * vis_sim)

                if score > best_score and score >= 0.70:
                    best_score = score
                    best_match = {
                        "template_id": t.id,
                        "display_name": t.display_name,
                        "symbol_class": t.symbol_class,
                        "similarity": round(best_score, 2),
                        "library_name": t.library.name if t.library else "General"
                    }

            return best_match
        except Exception as e:
            logger.debug(f"No se pudo consultar templates existentes: {e}")
            return None

    # ------------------------------------------------------------------------
    # 6. MOTOR DE CLUSTERING DE VARIANTES Y DEDUPLICACIÓN
    # ------------------------------------------------------------------------
    def run_deduplication(self, request: DeduplicateSymbolsRequest) -> DeduplicateSymbolsResponse:
        """
        Ejecuta deduplicación sobre candidatos persistidos, asignando visual_variant_group_id
        a clusters de candidatos que representan variantes del mismo símbolo.
        """
        query = self.db.query(StructuredSymbol)
        if request.extraction_id:
            query = query.join(ExtractedItem, StructuredSymbol.extracted_item_id == ExtractedItem.id)\
                         .filter(ExtractedItem.extraction_id == request.extraction_id)
        if request.canonical_symbol_family:
            query = query.filter(StructuredSymbol.canonical_symbol_family == request.canonical_symbol_family)

        candidates: List[StructuredSymbol] = query.all()
        n = len(candidates)
        if n == 0:
            return DeduplicateSymbolsResponse(
                total_evaluated=0,
                clusters_count=0,
                duplicates_detected=0,
                clusters=[]
            )

        parent = list(range(n))

        def find(i):
            if parent[i] == i:
                return i
            parent[i] = find(parent[i])
            return parent[i]

        def union(i, j):
            root_i = find(i)
            root_j = find(j)
            if root_i != root_j:
                parent[root_i] = root_j

        similarity_cache: Dict[Tuple[int, int], Tuple[float, float, float, float]] = {}

        for i in range(n):
            for j in range(i + 1, n):
                c1 = candidates[i]
                c2 = candidates[j]
                comb, vis, sem, geo = self.compute_combined_similarity(c1, c2)
                similarity_cache[(i, j)] = (comb, vis, sem, geo)

                has_crops = bool(c1.crop_image_path and c2.crop_image_path and os.path.exists(c1.crop_image_path) and os.path.exists(c2.crop_image_path))
                vis_ok = (vis >= request.visual_threshold) if has_crops else True

                if (comb >= 0.70 and
                    vis_ok and
                    sem >= request.semantic_threshold and
                    c1.canonical_symbol_family == c2.canonical_symbol_family):
                    union(i, j)

        groups: Dict[int, List[int]] = {}
        for idx in range(n):
            r = find(idx)
            groups.setdefault(r, []).append(idx)

        clusters_result: List[DeduplicationCluster] = []
        duplicates_count = 0

        for root, member_indices in groups.items():
            existing_group_ids = [candidates[i].visual_variant_group_id for i in member_indices if candidates[i].visual_variant_group_id]
            group_id = existing_group_ids[0] if existing_group_ids else f"VVG-{uuid.uuid4().hex[:8].upper()}"

            member_indices.sort(key=lambda idx: candidates[idx].confidence_score or 0.0, reverse=True)
            rep_idx = member_indices[0]
            rep_sym = candidates[rep_idx]

            members_list: List[VariantClusterItem] = []
            for m_idx in member_indices:
                m_sym = candidates[m_idx]
                m_sym.visual_variant_group_id = group_id

                if m_idx == rep_idx:
                    comb, vis, sem = 1.0, 1.0, 1.0
                else:
                    pair_key = (min(rep_idx, m_idx), max(rep_idx, m_idx))
                    comb, vis, sem, _ = similarity_cache.get(pair_key, (0.8, 0.8, 0.8, 0.8))
                    duplicates_count += 1

                members_list.append(VariantClusterItem(
                    symbol_id=m_sym.id,
                    symbol_name=m_sym.symbol_name,
                    canonical_symbol_family=m_sym.canonical_symbol_family,
                    crop_image_path=m_sym.crop_image_path,
                    confidence_score=m_sym.confidence_score or 0.0,
                    source_render_mode=m_sym.source_render_mode or "vector",
                    visual_similarity=round(vis, 3),
                    semantic_similarity=round(sem, 3),
                    combined_score=round(comb, 3),
                    is_canonical_representative=(m_idx == rep_idx)
                ))

            clusters_result.append(DeduplicationCluster(
                group_id=group_id,
                canonical_symbol_family=rep_sym.canonical_symbol_family,
                canonical_name=rep_sym.symbol_name,
                representative_id=rep_sym.id,
                members_count=len(members_list),
                members=members_list
            ))

        self.db.commit()
        logger.info(f"Deduplicación completada: {n} evaluados, {len(clusters_result)} clusters, {duplicates_count} duplicados.")

        return DeduplicateSymbolsResponse(
            total_evaluated=n,
            clusters_count=len(clusters_result),
            duplicates_detected=duplicates_count,
            clusters=clusters_result
        )

    # ------------------------------------------------------------------------
    # 7. GESTIÓN MANUAL DE GRUPOS: FUSIONAR Y SEPARAR VARIANTES (HITL)
    # ------------------------------------------------------------------------
    def merge_symbol_into_group(self, symbol_id: str, target_group_id: str) -> bool:
        """Fusiona manualmente un candidato con un grupo de variantes existente."""
        sym = self.db.query(StructuredSymbol).filter(StructuredSymbol.id == symbol_id).first()
        if not sym:
            return False
        sym.visual_variant_group_id = target_group_id
        if sym.human_validation_notes:
            sym.human_validation_notes += f" | Fusionado a grupo {target_group_id}"
        else:
            sym.human_validation_notes = f"Fusionado a grupo {target_group_id}"
        self.db.commit()
        return True

    def split_symbol_from_group(self, symbol_id: str) -> str:
        """Separa manualmente un candidato de su grupo, asignándole uno nuevo e independiente."""
        sym = self.db.query(StructuredSymbol).filter(StructuredSymbol.id == symbol_id).first()
        if not sym:
            raise ValueError("Símbolo no encontrado")
        new_group_id = f"VVG-{uuid.uuid4().hex[:8].upper()}"
        sym.visual_variant_group_id = new_group_id
        if sym.human_validation_notes:
            sym.human_validation_notes += " | Separado como variante independiente"
        else:
            sym.human_validation_notes = "Separado como variante independiente"
        self.db.commit()
        return new_group_id
