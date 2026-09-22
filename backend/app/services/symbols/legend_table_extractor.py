import os
import re
import uuid
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import fitz

from sqlalchemy.orm import Session

from app.core.settings import settings
from app.core.logging import logger
from app.db.models.intake_extractions import SourceExtraction, ExtractedItem, StructuredSymbol
from app.services.symbols.vector_extractor import VectorSymbolExtractor, VectorSymbolCandidateDTO
from app.services.symbols.raster_extractor import RasterSymbolExtractor, RasterSymbolCandidateDTO
from app.services.extraction.candidate_enrichment_service import CandidateEnrichmentService, TECHNICAL_KNOWLEDGE_CATALOG
from app.services.tables.extractor import TableExtractor


@dataclass
class ExtractedPipingSymbolDTO:
    """Símbolo de piping completamente contextualizado y listo para persistencia."""
    id: str
    symbol_name: str
    canonical_symbol_family: str
    standard_reference: Optional[str] = None
    discipline: str = "piping"
    category: str = "valvulas"
    source_render_mode: str = "vector"          # vector, raster, mixed
    layout_context: str = "inside_table"        # inside_table, semi_structured_legend, free_layout, manual_crop
    context_association_mode: str = "row_band"  # row_band, lateral_band, caption_band, manual_assignment
    bbox_normalized: List[float] = field(default_factory=list)
    estimated_physical_size_mm: Dict[str, Any] = field(default_factory=dict)
    crop_image_path: Optional[str] = None
    technical_function: Optional[str] = None
    aliases: List[str] = field(default_factory=list)
    confidence_score: float = 0.85
    human_validation_notes: Optional[str] = None
    visual_variant_group_id: Optional[str] = None
    # Linaje estructural tabla-fila-columna
    source_table_id: Optional[str] = None
    row_index: Optional[int] = None
    col_index: Optional[int] = None
    cell_bbox: Optional[List[float]] = None
    row_bbox: Optional[List[float]] = None
    tag_or_code: Optional[str] = None
    symbol_description: Optional[str] = None
    needs_visual_crop: bool = False
    crop_error_reason: Optional[str] = None
    inner_drawing_bbox: Optional[List[float]] = None
    reading_orientation: Optional[str] = "row_major"
    orientation_confidence: float = 1.0
    orientation_reason: Optional[str] = None
    requires_human_review: bool = False
    occurrences: List[Dict[str, Any]] = field(default_factory=list)
    # Auditoría geométrica obligatoria
    geometric_evidence: bool = True
    geometric_confidence: float = 0.0
    evidence_sources: List[str] = field(default_factory=list)
    shape_features: Dict[str, Any] = field(default_factory=dict)
    text_mask_overlap_ratio: float = 0.0
    rejection_reason: Optional[str] = None
    # Recorte ajustado a 3 mm y metadatos de grilla física
    symbol_crop_bbox: Optional[List[float]] = None
    crop_margin_mm: float = 3.0
    row_span: int = 1
    col_span: int = 1
    graphic_classification: str = "symbol"
    grid_source: str = "vector"
    grid_confidence: float = 1.0
    physical_grid_detected: bool = True
    x_boundaries: List[float] = field(default_factory=list)
    y_boundaries: List[float] = field(default_factory=list)
    table_bbox: Optional[List[float]] = None
    content_class: str = "symbol_only"
    boundary_evidence: Dict[str, Any] = field(default_factory=dict)
    border_coverage_ratio: float = 1.0


class LegendTableExtractor:
    """
    Motor extractor de leyendas y tablas de simbología para piping e instrumentación.
    Ejecuta el flujo por capas:
    1. Decide estrategia dual: si hay trazos vectoriales (get_drawings) usa VectorSymbolExtractor.
       Si es escaneado o imagen pura, usa RasterSymbolExtractor como fallback.
    2. Detecta la estructura contextual (inside_table, semi_structured_legend o free_layout).
    3. Asocia cada símbolo con su texto explicativo (franja de fila row_band, banda lateral o caption).
    4. Cruza con el catálogo ontológico ISA 5.1 / ASME B16.34 para clasificar la familia canónica.
    5. Persiste en DB como ExtractedItem + StructuredSymbol.
    """

    def __init__(self, db: Session):
        self.db = db
        self.vector_extractor = VectorSymbolExtractor()
        self.raster_extractor = RasterSymbolExtractor()
        self.enricher = CandidateEnrichmentService(db)

    def extract_from_pdf_page(
        self,
        pdf_bytes: bytes,
        page_number: int = 1,
        extraction_id: Optional[str] = None,
        discipline: str = "piping",
        preferred_mode: str = "auto" # auto, vector_only, raster_only
    ) -> List[ExtractedPipingSymbolDTO]:
        """
        Extrae y contextualiza todos los símbolos de una página PDF de leyenda técnica.
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if page_number > len(doc) or page_number < 1:
            return []

        page = doc[page_number - 1]
        pw, ph = page.rect.width, page.rect.height

        # 1. Extraer todos los bloques de texto OCR de la página
        text_blocks = self._extract_page_text_blocks(page)
        text_bboxes_norm = [tb["bbox_norm"] for tb in text_blocks]

        # 2. Decisión de estrategia dual (Vectorial vs Raster)
        drawings = page.get_drawings()
        has_vector_drawings = len(drawings) >= 8

        raw_candidates = []
        render_mode = "vector"

        if preferred_mode == "vector_only" or (preferred_mode == "auto" and has_vector_drawings):
            logger.info(f"Pág {page_number}: usando pipeline VECTORIAL (PyMuPDF get_drawings, {len(drawings)} trazos).")
            raw_candidates = self.vector_extractor.extract_candidates_from_page(
                page=page,
                page_number=page_number,
                doc_uid=extraction_id[:8] if extraction_id else "doc"
            )
            render_mode = "vector"
        else:
            logger.info(f"Pág {page_number}: usando pipeline RASTER (OpenCV componentes conexos a 300 DPI).")
            # Renderizar página a 300 DPI para OpenCV
            pix = page.get_pixmap(dpi=300)
            img_bytes = pix.tobytes("png")
            raw_candidates = self.raster_extractor.extract_candidates_from_image(
                image_input=img_bytes,
                dpi=300,
                page_number=page_number,
                doc_uid=extraction_id[:8] if extraction_id else "doc",
                known_text_bboxes_norm=text_bboxes_norm,
                family_target="valves"
            )
            render_mode = "raster"

        # 3. Detección de Estructura Tabular Profunda y Rejilla con TableExtractor
        # Importante: Pasar siempre page=page y doc_uid para inspección visual de celdas
        table_extractor = TableExtractor(width_px=int(pw), height_px=int(ph))
        table_texts_input = [
            {"text": tb["text"], "bbox_normalized": tb["bbox_norm"], "id": f"tb_{i}"}
            for i, tb in enumerate(text_blocks)
        ]
        extracted_table = table_extractor.extract_from_region(
            region_bbox_norm=[0.0, 0.0, 1.0, 1.0],
            texts=table_texts_input,
            symbols=raw_candidates,
            page=page,
            doc_uid=extraction_id[:8] if extraction_id else "doc"
        )

        row_bands = self._detect_horizontal_row_bands(text_blocks, raw_candidates, ph)
        layout_context = "inside_table" if (extracted_table and extracted_table.row_count >= 2) or len(row_bands) >= 3 else "semi_structured_legend"

        # 4. Contextualización y Asociación Símbolo-Texto (Prioridad: 1. Misma fila, 2. Misma tabla, 3. Lateral/caption fallback)
        results: List[ExtractedPipingSymbolDTO] = []
        covered_cell_coords = set()

        # 4a. Incorporar primero los símbolos extraídos directamente desde celdas tabulares
        # Condición 2: Si la tabla no contiene símbolos (has_symbols=False), NO debe entrar al pipeline de simbología
        if extracted_table and extracted_table.has_symbols and extracted_table.extracted_symbols:
            logger.info(f"Pág {page_number}: TableExtractor extrajo {len(extracted_table.extracted_symbols)} símbolos directamente desde celdas tabulares.")
            for cell_sym in extracted_table.extracted_symbols:
                if cell_sym.graphic_classification in ["figure", "table_graphic", "not_symbol"]:
                    continue
                if getattr(cell_sym, "content_class", None) in ["text_only", "empty"]:
                    continue

                c_row = cell_sym.row_index
                c_col = cell_sym.col_index
                if c_row is not None and c_col is not None:
                    covered_cell_coords.add((c_row, c_col))

                piping_dto = ExtractedPipingSymbolDTO(
                    id=cell_sym.id,
                    symbol_name=cell_sym.symbol_name,
                    canonical_symbol_family=cell_sym.canonical_symbol_family,
                    standard_reference=cell_sym.standard_reference,
                    discipline=cell_sym.discipline or discipline,
                    category=cell_sym.category,
                    source_render_mode=cell_sym.source_render_mode,
                    layout_context="inside_table",
                    context_association_mode="row_band",
                    bbox_normalized=cell_sym.symbol_crop_bbox or cell_sym.bbox_normalized,
                    estimated_physical_size_mm=cell_sym.estimated_physical_size_mm,
                    crop_image_path=cell_sym.crop_image_path,
                    technical_function=cell_sym.technical_function,
                    aliases=cell_sym.aliases,
                    confidence_score=cell_sym.confidence_score,
                    human_validation_notes=cell_sym.human_validation_notes,
                    visual_variant_group_id=cell_sym.visual_variant_group_id,
                    source_table_id=cell_sym.source_table_id or f"table_p{page_number}",
                    row_index=cell_sym.row_index,
                    col_index=cell_sym.col_index,
                    cell_bbox=cell_sym.cell_bbox,
                    row_bbox=cell_sym.row_bbox,
                    tag_or_code=cell_sym.tag_or_code,
                    symbol_description=cell_sym.symbol_description,
                    needs_visual_crop=cell_sym.needs_visual_crop,
                    crop_error_reason=cell_sym.crop_error_reason,
                    inner_drawing_bbox=cell_sym.inner_drawing_bbox,
                    symbol_crop_bbox=cell_sym.symbol_crop_bbox,
                    crop_margin_mm=cell_sym.crop_margin_mm,
                    row_span=cell_sym.row_span,
                    col_span=cell_sym.col_span,
                    graphic_classification=cell_sym.graphic_classification,
                    grid_source=cell_sym.grid_source,
                    grid_confidence=cell_sym.grid_confidence,
                    physical_grid_detected=cell_sym.physical_grid_detected,
                    x_boundaries=cell_sym.x_boundaries,
                    y_boundaries=cell_sym.y_boundaries,
                    table_bbox=cell_sym.table_bbox,
                    reading_orientation=cell_sym.reading_orientation,
                    orientation_confidence=cell_sym.orientation_confidence,
                    orientation_reason=cell_sym.orientation_reason,
                    requires_human_review=cell_sym.requires_human_review,
                    geometric_evidence=cell_sym.geometric_evidence,
                    geometric_confidence=cell_sym.geometric_confidence,
                    evidence_sources=cell_sym.evidence_sources,
                    shape_features=cell_sym.shape_features,
                    text_mask_overlap_ratio=cell_sym.text_mask_overlap_ratio,
                    rejection_reason=cell_sym.rejection_reason,
                    content_class=getattr(cell_sym, "content_class", "symbol_only"),
                    boundary_evidence=getattr(cell_sym, "boundary_evidence", {}),
                    border_coverage_ratio=getattr(cell_sym, "border_coverage_ratio", 1.0)
                )
                results.append(piping_dto)
        elif extracted_table and not extracted_table.has_symbols:
            logger.info(f"Pág {page_number}: Tabla detectada sin celdas de símbolos. Descartada del pipeline de simbología (solo texto).")

        # 4b. Incorporar candidatos de página que no hayan caído en celdas ya cubiertas
        covered_ids = {s.id for s in results if s.id}
        for cand in raw_candidates:
            if getattr(cand, "id", None) in covered_ids:
                continue

            c_row_idx = getattr(cand, "row_index", None)
            c_col_idx = getattr(cand, "col_index", None)
            if c_row_idx is not None and c_col_idx is not None and (c_row_idx, c_col_idx) in covered_cell_coords:
                continue

            cb = cand.bbox_normalized # [x0, y0, x1, y1]
            cy = (cb[1] + cb[3]) / 2.0
            cx = (cb[0] + cb[2]) / 2.0

            # Si la tabla en la página fue descartada como no simbólica y el candidato cae dentro de ella, descartar
            if extracted_table and not extracted_table.has_symbols:
                tx0, ty0, tx1, ty1 = extracted_table.bbox_normalized
                if tx0 <= cx <= tx1 and ty0 <= cy <= ty1:
                    continue

            # Validación geométrica obligatoria: descartar glifos alfanuméricos aislados o líneas sueltas
            eval_res = table_extractor.geometric_validator.evaluate_cell(
                cell_bbox_norm=cb,
                cell_text="",
                page=page,
                drawings=drawings,
                crops_dir=os.path.join(settings.STORAGE_LOCAL_ROOT, "crops", "symbols"),
                doc_uid=extraction_id[:8] if extraction_id else "doc",
                row_index=c_row_idx or 0,
                col_index=c_col_idx or 0
            )
            if not eval_res.has_real_geometry:
                continue
            if eval_res.graphic_classification in ["figure", "table_graphic", "not_symbol"]:
                continue

            associated_text = ""
            assoc_mode = "lateral_band"

            c_cell_bbox = getattr(cand, "cell_bbox", None)
            c_row_bbox = getattr(cand, "row_bbox", None)
            source_table_id = f"table_p{page_number}" if extracted_table else None

            # Prioridad 1: Misma fila en la tabla estructurada
            if extracted_table and c_row_idx is not None:
                same_row_cells = [
                    c for c in extracted_table.cells
                    if c.row_index == c_row_idx and c.column_index != c_col_idx and c.text
                ]
                if same_row_cells:
                    associated_text = " ".join(c.text for c in same_row_cells).strip()
                    assoc_mode = "row_band"

            # Prioridad 1b: Franja de fila (row_band) detectada si no hubo match en celda de tabla
            if not associated_text:
                matching_row = next((r for r in row_bands if r["y0"] <= cy <= r["y1"]), None)
                if matching_row:
                    row_texts = [
                        t["text"] for t in matching_row["texts"]
                        if t["bbox_norm"][0] >= cb[0] - 0.02
                    ]
                    if row_texts:
                        associated_text = " ".join(row_texts).strip()
                        assoc_mode = "row_band"

            # Prioridad 2: Misma tabla (celdas adyacentes de la misma tabla si la fila estaba vacía de texto)
            if not associated_text and extracted_table and c_row_idx is not None:
                adjacent_table_cells = [
                    c for c in extracted_table.cells
                    if c.column_index != c_col_idx and c.text and abs(c.row_index - c_row_idx) <= 1
                ]
                if adjacent_table_cells:
                    associated_text = " ".join(c.text for c in adjacent_table_cells).strip()
                    assoc_mode = "same_table_context"

            # Prioridad 3: Fallback contextual lateral o caption
            if not associated_text:
                lat_texts = self._find_texts_in_lateral_band(cb, text_blocks)
                if lat_texts:
                    associated_text = " ".join(lat_texts).strip()
                    assoc_mode = "lateral_band"
                else:
                    cap_texts = self._find_texts_in_caption_band(cb, text_blocks)
                    if cap_texts:
                        associated_text = " ".join(cap_texts).strip()
                        assoc_mode = "caption_band"

            # 5. Limpieza, enriquecimiento y asignación de nombre
            parsed_info = self._resolve_symbol_semantics(associated_text, cand.canonical_family_hint)

            # Verificación de crop en disco
            crop_path_final = eval_res.crop_image_path or cand.crop_image_path
            has_valid_crop = bool(crop_path_final and (
                crop_path_final.startswith("http") or
                os.path.exists(os.path.join(settings.STORAGE_LOCAL_ROOT, crop_path_final.lstrip("/data/").lstrip("/")))
            ))

            sym_dto = ExtractedPipingSymbolDTO(
                id=cand.id,
                symbol_name=parsed_info["symbol_name"],
                canonical_symbol_family=parsed_info["canonical_family"],
                standard_reference=parsed_info["standard_reference"],
                discipline=discipline,
                category=parsed_info["category"],
                source_render_mode=render_mode,
                layout_context=layout_context,
                context_association_mode=assoc_mode,
                bbox_normalized=cand.bbox_normalized,
                estimated_physical_size_mm=cand.estimated_physical_size_mm,
                crop_image_path=crop_path_final,
                technical_function=parsed_info["technical_function"],
                aliases=parsed_info["aliases"],
                confidence_score=eval_res.geometric_confidence if has_valid_crop else 0.65,
                human_validation_notes=f"Extraído automáticamente vía pipeline {render_mode} ({assoc_mode})",
                visual_variant_group_id=str(uuid.uuid4()),
                source_table_id=source_table_id,
                row_index=c_row_idx,
                col_index=c_col_idx,
                cell_bbox=c_cell_bbox,
                row_bbox=c_row_bbox,
                needs_visual_crop=not has_valid_crop,
                crop_error_reason="Recorte no encontrado en disco" if not has_valid_crop else None,
                inner_drawing_bbox=eval_res.inner_drawing_bbox or cand.bbox_normalized,
                geometric_evidence=eval_res.has_real_geometry,
                geometric_confidence=eval_res.geometric_confidence,
                evidence_sources=eval_res.evidence_sources,
                shape_features=eval_res.shape_features,
                text_mask_overlap_ratio=eval_res.text_mask_overlap_ratio,
                rejection_reason=eval_res.rejection_reason,
                content_class="symbol_only",
                boundary_evidence={},
                border_coverage_ratio=1.0
            )
            results.append(sym_dto)

        # 6. Si se proporcionó extraction_id, persistir inmediatamente en base de datos
        if extraction_id and results:
            self._persist_symbols_to_db(extraction_id, results, page_number)

        logger.info(f"Pág {page_number}: {len(results)} símbolos estructurados y asociados.")
        return results

    def _extract_page_text_blocks(self, page: fitz.Page) -> List[Dict[str, Any]]:
        """Extrae palabras/bloques de texto normalizados."""
        pw, ph = page.rect.width, page.rect.height
        raw_blocks = page.get_text("blocks")
        texts = []
        for b in raw_blocks:
            if b[6] != 0:
                continue
            txt = b[4].strip()
            if not txt:
                continue
            texts.append({
                "text": txt,
                "bbox_pt": [b[0], b[1], b[2], b[3]],
                "bbox_norm": [round(b[0]/pw, 4), round(b[1]/ph, 4), round(b[2]/pw, 4), round(b[3]/ph, 4)]
            })
        return texts

    def _detect_horizontal_row_bands(
        self,
        texts: List[Dict[str, Any]],
        candidates: List[Any],
        page_height_pt: float
    ) -> List[Dict[str, Any]]:
        """
        Agrupa textos y candidatos en franjas horizontales de fila coherentes.
        """
        if not texts:
            return []

        # Ordenar textos por coordenada Y superior
        sorted_texts = sorted(texts, key=lambda t: t["bbox_norm"][1])
        rows = []
        tol = 0.025 # 2.5% de tolerancia de altura

        for t in sorted_texts:
            ty0 = t["bbox_norm"][1]
            ty1 = t["bbox_norm"][3]
            t_mid = (ty0 + ty1) / 2.0

            matched_row = None
            for r in rows:
                if abs(t_mid - r["mid"]) <= tol:
                    matched_row = r
                    break

            if matched_row:
                matched_row["texts"].append(t)
                matched_row["y0"] = min(matched_row["y0"], ty0)
                matched_row["y1"] = max(matched_row["y1"], ty1)
                matched_row["mid"] = (matched_row["y0"] + matched_row["y1"]) / 2.0
            else:
                rows.append({
                    "y0": ty0 - 0.005,
                    "y1": ty1 + 0.005,
                    "mid": t_mid,
                    "texts": [t]
                })

        return rows

    def _find_texts_in_lateral_band(self, bbox_norm: List[float], texts: List[Dict[str, Any]]) -> List[str]:
        """Busca texto en la franja derecha del símbolo."""
        bx0, by0, bx1, by1 = bbox_norm
        matched = []
        for t in texts:
            tx0, ty0, tx1, ty1 = t["bbox_norm"]
            # A la derecha, con altura solapada
            if tx0 >= bx0 and tx0 <= bx1 + 0.40:
                if not (ty1 < by0 - 0.02 or ty0 > by1 + 0.02):
                    matched.append(t["text"])
        return matched

    def _find_texts_in_caption_band(self, bbox_norm: List[float], texts: List[Dict[str, Any]]) -> List[str]:
        """Busca texto inmediatamente debajo del símbolo."""
        bx0, by0, bx1, by1 = bbox_norm
        matched = []
        for t in texts:
            tx0, ty0, tx1, ty1 = t["bbox_norm"]
            # Debajo, dentro de 5% de altura
            if ty0 >= by1 - 0.01 and ty0 <= by1 + 0.08:
                if abs((tx0 + tx1)/2.0 - (bx0 + bx1)/2.0) <= 0.15:
                    matched.append(t["text"])
        return matched

    def _resolve_symbol_semantics(self, raw_text: str, family_hint: str) -> Dict[str, Any]:
        """
        Resuelve nombre formal, familia canónica y referencias normativas usando catálogo ontológico.
        """
        clean = " ".join(raw_text.split())
        clean = re.sub(r"^(N[°o]\s*\d+|ITEM\s*\d+|[\d\.\-]+)\s*", "", clean, flags=re.IGNORECASE)

        # Buscar coincidencia en TECHNICAL_KNOWLEDGE_CATALOG
        matched_cat = None
        for entry in TECHNICAL_KNOWLEDGE_CATALOG:
            for kw in entry.get("keywords", []):
                if kw in clean.lower():
                    matched_cat = entry
                    break
            if matched_cat:
                break

        if matched_cat:
            return {
                "symbol_name": matched_cat["title"],
                "canonical_family": family_hint or "valves",
                "standard_reference": matched_cat.get("source_label", "Norma ISA 5.1 / ASME B16.34"),
                "category": matched_cat.get("properties", {}).get("category", "General Piping"),
                "technical_function": matched_cat.get("function"),
                "aliases": [clean] if clean and clean != matched_cat["title"] else []
            }
        else:
            # Fallback limpio
            fallback_title = clean[:50] if clean else f"Símbolo de {family_hint.capitalize()}"
            return {
                "symbol_name": fallback_title,
                "canonical_family": family_hint or "valves",
                "standard_reference": "Norma Técnica de Piping e Instrumentación",
                "category": family_hint.capitalize(),
                "technical_function": "Componente de control o paso en línea de piping",
                "aliases": [clean] if clean else []
            }

    def _persist_symbols_to_db(
        self,
        extraction_id: str,
        symbols: List[ExtractedPipingSymbolDTO],
        page_number: int
    ) -> None:
        """Persiste los símbolos extraídos en extracted_items y structured_symbols."""
        try:
            # Agrupar por clave canónica para deduplicar
            import re
            clusters: Dict[str, List[ExtractedPipingSymbolDTO]] = {}
            for s in symbols:
                # Clave canónica por tag limpio o nombre normalizado
                if s.tag_or_code and s.tag_or_code.strip() and not s.tag_or_code.startswith("SYM-"):
                    ckey = f"tag:{s.tag_or_code.strip().upper()}"
                elif s.symbol_name and s.symbol_name.strip():
                    norm_name = re.sub(r'[^a-zA-Z0-9áéíóúÁÉÍÓÚñÑ]', '', s.symbol_name.lower())
                    ckey = f"name:{norm_name}" if norm_name else f"cell:{s.row_index}:{s.col_index}"
                else:
                    ckey = f"family:{s.canonical_symbol_family}:{s.row_index}:{s.col_index}"
                clusters.setdefault(ckey, []).append(s)

            persisted_count = 0
            for ckey, group in clusters.items():
                # Ordenar: preferir candidato con crop válido y mayor confianza
                group.sort(key=lambda x: (1 if x.crop_image_path and not x.needs_visual_crop else 0, x.confidence_score), reverse=True)
                rep = group[0]

                # Construir ocurrencias multipágina / multicelda
                occurrences = []
                for idx, occ_s in enumerate(group):
                    occurrences.append({
                        "occurrence_id": str(uuid.uuid4()),
                        "page_number": page_number,
                        "bbox_normalized": occ_s.cell_bbox or occ_s.bbox_normalized,
                        "cell_bbox": occ_s.cell_bbox,
                        "inner_drawing_bbox": occ_s.inner_drawing_bbox,
                        "crop_image_path": occ_s.crop_image_path,
                        "source_reference": f"Pág. {page_number} (Fila {(occ_s.row_index or 0) + 1}, Col {(occ_s.col_index or 0) + 1})",
                        "source_table_id": occ_s.source_table_id,
                        "row_index": occ_s.row_index,
                        "col_index": occ_s.col_index,
                        "reading_orientation": occ_s.reading_orientation,
                        "orientation": occ_s.reading_orientation,
                        "orientation_confidence": occ_s.orientation_confidence,
                        "orientation_reason": occ_s.orientation_reason,
                        "title": occ_s.symbol_name,
                        "is_primary": (idx == 0)
                    })

                needs_review = rep.requires_human_review or (rep.orientation_confidence is not None and rep.orientation_confidence < 0.60) or rep.reading_orientation in ["undetermined", "unknown"]

                # 1. ExtractedItem (Representante canónico único)
                item = ExtractedItem(
                    id=str(uuid.uuid4()),
                    extraction_id=extraction_id,
                    item_type="symbol",
                    candidate_type="symbol_candidate",
                    title=rep.symbol_name,
                    code_or_number=rep.tag_or_code or rep.canonical_symbol_family.upper()[:10],
                    description=rep.symbol_description or rep.technical_function or f"Símbolo canónico de {rep.canonical_symbol_family}.",
                    content_text=rep.symbol_name,
                    discipline=rep.discipline,
                    page_number=page_number,
                    bbox_normalized=rep.cell_bbox or rep.bbox_normalized,
                    crop_image_path=rep.crop_image_path,
                    match_confidence=rep.confidence_score,
                    completeness_status="review_required" if needs_review else ("needs_visual_crop" if rep.needs_visual_crop else "complete"),
                    review_status="to_confirm",
                    requires_validation=needs_review,
                    source_origin="document",
                    governance_note=f"Requiere revisión humana obligatoria: {rep.orientation_reason}" if needs_review else (
                        f"Símbolo canónico con {len(occurrences)} ocurrencias en el documento." if len(occurrences) > 1 else None
                    ),
                    metadata_payload={
                        "canonical_symbol_family": rep.canonical_symbol_family,
                        "standard_reference": rep.standard_reference,
                        "source_render_mode": rep.source_render_mode,
                        "layout_context": rep.layout_context,
                        "context_association_mode": rep.context_association_mode,
                        "estimated_physical_size_mm": rep.estimated_physical_size_mm,
                        "aliases": rep.aliases,
                        "crop_image_path": rep.crop_image_path,
                        "needs_visual_crop": rep.needs_visual_crop,
                        "crop_error_reason": rep.crop_error_reason,
                        "source_table_id": rep.source_table_id,
                        "row_index": rep.row_index,
                        "col_index": rep.col_index,
                        "cell_bbox": rep.cell_bbox,
                        "row_bbox": rep.row_bbox,
                        "inner_drawing_bbox": rep.inner_drawing_bbox,
                        "reading_orientation": rep.reading_orientation,
                        "orientation": rep.reading_orientation,
                        "orientation_confidence": rep.orientation_confidence,
                        "orientation_reason": rep.orientation_reason,
                        "requires_human_review": needs_review,
                        "occurrences": occurrences,
                        "occurrences_count": len(occurrences),
                        "is_canonical_representative": True,
                        "geometric_evidence": rep.geometric_evidence,
                        "geometric_confidence": rep.geometric_confidence,
                        "evidence_sources": rep.evidence_sources,
                        "shape_features": rep.shape_features,
                        "text_mask_overlap_ratio": rep.text_mask_overlap_ratio,
                        "rejection_reason": rep.rejection_reason
                    }
                )
                self.db.add(item)
                self.db.flush()

                # 2. StructuredSymbol
                sym = StructuredSymbol(
                    id=rep.id if rep.id else str(uuid.uuid4()),
                    extracted_item_id=item.id,
                    symbol_name=rep.symbol_name,
                    standard_family=rep.standard_reference or "ISA-5.1",
                    discipline=rep.discipline,
                    category=rep.category,
                    crop_image_path=rep.crop_image_path,
                    confidence_score=rep.confidence_score,
                    source_render_mode=rep.source_render_mode,
                    layout_context=rep.layout_context,
                    context_association_mode=rep.context_association_mode,
                    standard_reference=rep.standard_reference,
                    canonical_symbol_family=rep.canonical_symbol_family,
                    visual_variant_group_id=rep.visual_variant_group_id,
                    estimated_physical_size_mm=rep.estimated_physical_size_mm,
                    reused_for_matching_count=0,
                    false_positive_count=0,
                    human_validation_notes=rep.human_validation_notes,
                    source_table_id=rep.source_table_id,
                    row_index=rep.row_index,
                    col_index=rep.col_index,
                    cell_bbox=rep.cell_bbox,
                    row_bbox=rep.row_bbox
                )
                self.db.add(sym)
                persisted_count += 1

            self.db.commit()
            logger.info(f"Persistidos {persisted_count} símbolos canónicos (de {len(symbols)} detecciones brutas) para extracción {extraction_id}.")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error persistiendo símbolos en DB: {e}", exc_info=True)
