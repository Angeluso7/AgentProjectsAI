import os
import re
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.db.models.intake_extractions import SourceExtraction, ExtractedItem
from app.services.rules.deduplication_service import RuleDeduplicationService

class CandidateGeneratorService:
    """
    Capa 2: Technical Interpretation Candidates.
    Transforma la evidencia técnica multimodal estructurada (Capa 1)
    en 7 tipos canónicos de candidatos interpretativos listos para revisión y validación humana:
    1. premise_candidate: Premisas técnicas y condiciones de diseño.
    2. rule_candidate: Reglas determinísticas QA/QC con parámetros cuantificables.
    3. symbol_candidate: Símbolos técnicos y leyendas con crop y categoría.
    4. table_matrix_candidate: Matrices tabulares (Line lists, Valve schedules, Specs).
    5. equipment_image_candidate: Fotos y figuras de equipos con caption y contexto.
    6. diagram_candidate: Diagramas y esquemas con delimitación espacial y nota de limitación no topológica.
    7. example_candidate: Casos ilustrativos y ejemplos normativos.
    """

    TOPOLOGICAL_DISCLAIMER = (
        "Extracción semántica regional realizada sin inferencia de conectividad topológica "
        "ni grafo P&ID en esta fase."
    )

    def __init__(self, db: Session):
        self.db = db

    def generate_candidates_from_evidence(
        self,
        extraction_id: str,
        evidence_payload: Dict[str, Any],
        discipline: str = "general",
        document_title: Optional[str] = None
    ) -> List[ExtractedItem]:
        """
        Genera y persiste en BD todos los candidatos técnicos derivados a partir del payload de evidencia.
        Cada candidato queda en estado 'to_confirm' o 'draft' (NUNCA aprobado automáticamente).
        """
        extraction = self.db.query(SourceExtraction).filter(SourceExtraction.id == extraction_id).first()
        if not extraction:
            raise ValueError(f"Sesión de extracción '{extraction_id}' no encontrada.")

        doc_title = document_title or extraction.title
        doc_id = evidence_payload.get("document_id") or extraction.source_asset_id
        prov_data = evidence_payload.get("provenance", {})
        file_hash = prov_data.get("file_hash_sha256") or extraction.metadata_info.get("file_hash_sha256")
        generated_candidates: List[ExtractedItem] = []
        raw_symbol_candidates: List[ExtractedItem] = []

        # 1. Procesar Tablas Estructuradas -> table_matrix_candidate & premise_candidate
        for tbl in evidence_payload.get("tables", []):
            table_title = tbl.get("title") or "Tabla Técnica"
            headers = tbl.get("headers", [])
            rows = tbl.get("rows", [])
            node_id = tbl.get("node_id")
            crop_path = tbl.get("crop_image_path")
            bbox_norm = tbl.get("bbox_normalized", [0.05, 0.1, 0.95, 0.5])
            page_no = tbl.get("page_number", 1)

            # A) Crear Table Matrix Candidate
            tbl_cand = ExtractedItem(
                id=str(uuid.uuid4()),
                extraction_id=extraction_id,
                item_type="table",
                candidate_type="table_matrix_candidate",
                title=f"Matriz Técnica: {table_title}",
                code_or_number=f"TBL-{discipline[:3].upper()}-{len(generated_candidates) + 1}",
                description=f"Matriz estructurada con {len(rows)} filas y {len(headers)} columnas: {', '.join(headers[:5])}.",
                content_text=tbl.get("markdown_repr") or f"Tabla técnica de {len(rows)} registros. Columnas: {headers}",
                derived_text=f"Estructura tabular de ingeniería correspondiente a {doc_title}.",
                crop_image_path=crop_path,
                bbox_normalized=bbox_norm,
                page_number=page_no,
                evidence_references=[node_id] if node_id else [],
                technical_parameters={
                    "row_count": len(rows),
                    "col_count": len(headers),
                    "headers": headers,
                    "primary_discipline": discipline,
                    "function_or_role": "Matriz técnica de verificación tabular"
                },
                structured_matrix={
                    "headers": headers,
                    "rows": rows,
                    "row_count": len(rows)
                },
                target_destination="both",
                review_status="to_confirm",
                source_origin=extraction.source_origin,
                source_reference=f"Documento: {doc_title} (Pág. {page_no})",
                item_nature="official_rule",
                governance_note="Matriz técnica extraída por DoclingService. Requiere confirmación de columnas clave.",
                metadata_payload={
                    "evidence_type": "table_matrix",
                    "primary_discipline": discipline,
                    "has_symbols": tbl.get("has_symbols", bool(tbl.get("extracted_symbols"))),
                    "reading_orientation": tbl.get("reading_orientation", "row_major"),
                    "orientation": tbl.get("orientation") or tbl.get("reading_orientation", "row_major"),
                    "orientation_confidence": tbl.get("orientation_confidence", 1.0),
                    "orientation_reason": tbl.get("orientation_reason", ""),
                    "grid_source": tbl.get("grid_source", "vector"),
                    "grid_confidence": tbl.get("grid_confidence", 1.0),
                    "physical_grid_detected": tbl.get("physical_grid_detected", True),
                    "x_boundaries": tbl.get("x_boundaries", []),
                    "y_boundaries": tbl.get("y_boundaries", []),
                    "table_bbox": tbl.get("table_bbox", bbox_norm),
                }
            )
            self.db.add(tbl_cand)
            generated_candidates.append(tbl_cand)

            # B) Materializar Símbolos detectados en celdas de la tabla (Capa 1 -> Capa 2)
            # Condición 2: Si la tabla no tiene símbolos (has_symbols=False o vacía), NO entra al pipeline de simbología
            tbl_has_symbols = tbl.get("has_symbols", bool(tbl.get("extracted_symbols")))
            if tbl_has_symbols:
                for sym_info in tbl.get("extracted_symbols", []):
                    # Condición obligatoria 1: Descarte estricto si no hay evidencia geométrica válida
                    if sym_info.get("geometric_evidence") is False:
                        continue

                    # Condición obligatoria 6: Clasificación gráfica explícita
                    # Si fue clasificado como figure o table_graphic, se enruta a diagram/figure candidate, NO a symbol_candidate
                    graphic_class = sym_info.get("graphic_classification", "symbol")
                    if graphic_class in ["figure", "table_graphic"]:
                        fig_cand = ExtractedItem(
                            id=str(uuid.uuid4()),
                            extraction_id=extraction_id,
                            item_type="figure",
                            candidate_type="diagram_candidate",
                            title=f"Figura Técnica: {sym_info.get('symbol_name') or 'Gráfico de Celda'}",
                            code_or_number=f"FIG-{discipline[:3].upper()}-{len(generated_candidates) + 1}",
                            description=sym_info.get("symbol_description") or "Gráfico técnico / forma de onda extraído de celda de tabla.",
                            content_text=sym_info.get("symbol_name") or "Gráfico técnico",
                            derived_text=f"Forma de onda o diagrama en celda tabular (Fila {sym_info.get('row_index')}, Col {sym_info.get('col_index')}).",
                            caption_or_context=f"Gráfico en Tabla {table_title}",
                            crop_image_path=sym_info.get("crop_image_path"),
                            bbox_normalized=sym_info.get("symbol_crop_bbox") or sym_info.get("bbox_normalized") or bbox_norm,
                            page_number=page_no,
                            parent_item_id=tbl_cand.id,
                            is_derived=True,
                            split_mode="inside_table_cell",
                            evidence_references=[node_id] if node_id else [],
                            technical_parameters={
                                "graphic_classification": graphic_class,
                                "primary_discipline": discipline,
                                "source_table": table_title
                            },
                            target_destination="both",
                            review_status="to_confirm",
                            source_origin=extraction.source_origin,
                            source_reference=f"Documento: {doc_title} (Pág. {page_no})",
                            item_nature="proposed_rule",
                            governance_note="Gráfico técnico clasificado como figura/diagrama en lugar de símbolo canónico.",
                            metadata_payload={
                                "graphic_classification": graphic_class,
                                "source_table_id": tbl_cand.id,
                                "cell_bbox": sym_info.get("cell_bbox"),
                                "inner_drawing_bbox": sym_info.get("inner_drawing_bbox"),
                                "crop_image_path": sym_info.get("crop_image_path")
                            }
                        )
                        self.db.add(fig_cand)
                        generated_candidates.append(fig_cand)
                        continue

                    sym_title = sym_info.get("symbol_name") or "Símbolo Tabular"
                    crop_p = sym_info.get("crop_image_path")
                    needs_crop = sym_info.get("needs_visual_crop", False) or not bool(crop_p)

                    # Condición obligatoria 4: El crop final es symbol_crop_bbox (inner_drawing + 3mm) limitado a cell_bbox
                    cell_bb = sym_info.get("cell_bbox") or sym_info.get("bbox_normalized") or bbox_norm
                    inner_bb = sym_info.get("inner_drawing_bbox")
                    symbol_crop_bb = sym_info.get("symbol_crop_bbox") or cell_bb
                    crop_margin_mm = sym_info.get("crop_margin_mm", 3.0)
                    row_span = sym_info.get("row_span", 1)
                    col_span = sym_info.get("col_span", 1)
                    grid_src = sym_info.get("grid_source") or tbl.get("grid_source", "vector")
                    grid_conf = sym_info.get("grid_confidence", tbl.get("grid_confidence", 1.0))
                    phys_grid = sym_info.get("physical_grid_detected", tbl.get("physical_grid_detected", True))
                    x_bounds = sym_info.get("x_boundaries") or tbl.get("x_boundaries", [])
                    y_bounds = sym_info.get("y_boundaries") or tbl.get("y_boundaries", [])
                    tbl_bb = sym_info.get("table_bbox") or tbl.get("table_bbox") or bbox_norm

                    read_orient = sym_info.get("reading_orientation") or tbl.get("reading_orientation", "row_major")
                    orient_conf = sym_info.get("orientation_confidence", tbl.get("orientation_confidence", 1.0))
                    orient_reason = sym_info.get("orientation_reason", tbl.get("orientation_reason", ""))
                    is_logical_low_conf = (grid_src == "logical_alignment" and grid_conf < 0.60)
                    req_review = (
                        sym_info.get("requires_human_review", False)
                        or (orient_conf is not None and orient_conf < 0.60)
                        or read_orient in ["undetermined", "unknown"]
                        or is_logical_low_conf
                        or graphic_class == "requires_human_review"
                    )

                    cell_sym_cand = ExtractedItem(
                        id=str(uuid.uuid4()),
                        extraction_id=extraction_id,
                        item_type="symbol",
                        candidate_type="symbol_candidate",
                        title=sym_title,
                        code_or_number=sym_info.get("tag_or_code") or f"SYM-{discipline[:3].upper()}-{len(generated_candidates) + len(raw_symbol_candidates) + 1}",
                        description=sym_info.get("symbol_description") or sym_info.get("technical_function") or f"Símbolo técnico de {sym_info.get('canonical_symbol_family', 'piping')}.",
                        content_text=sym_title,
                        derived_text=f"Símbolo extraído de celda tabular (Fila {sym_info.get('row_index')}, Col {sym_info.get('col_index')}).",
                        caption_or_context=sym_info.get("symbol_description") or f"Tabla {table_title}",
                        crop_image_path=crop_p,
                        bbox_normalized=symbol_crop_bb, # Crop final ajustado a 3 mm
                        page_number=page_no,
                        parent_item_id=tbl_cand.id,
                        is_derived=True,
                        split_mode="inside_table_cell",
                        evidence_references=[node_id] if node_id else [],
                        technical_parameters={
                            "standard": sym_info.get("standard_reference"),
                            "standard_family": sym_info.get("canonical_symbol_family"),
                            "category": sym_info.get("category"),
                            "function": sym_info.get("technical_function"),
                            "primary_discipline": discipline,
                            "tag_or_code": sym_info.get("tag_or_code"),
                            "reading_orientation": read_orient,
                            "orientation": read_orient,
                            "orientation_confidence": orient_conf,
                            "orientation_reason": orient_reason,
                            "inner_drawing_bbox": inner_bb,
                            "symbol_crop_bbox": symbol_crop_bb,
                            "crop_margin_mm": crop_margin_mm,
                            "row_span": row_span,
                            "col_span": col_span,
                            "graphic_classification": graphic_class,
                            "grid_source": grid_src,
                            "grid_confidence": grid_conf,
                            "physical_grid_detected": phys_grid,
                            "x_boundaries": x_bounds,
                            "y_boundaries": y_bounds,
                            "table_bbox": tbl_bb,
                            "requires_human_review": req_review,
                            "geometric_evidence": sym_info.get("geometric_evidence", True),
                            "geometric_confidence": sym_info.get("geometric_confidence", 1.0),
                            "evidence_sources": sym_info.get("evidence_sources", []),
                            "shape_features": sym_info.get("shape_features", {}),
                            "text_mask_overlap_ratio": sym_info.get("text_mask_overlap_ratio", 0.0)
                        },
                        target_destination="both",
                        completeness_status="needs_visual_crop" if needs_crop else "complete",
                        review_status="to_confirm",
                        source_origin=extraction.source_origin,
                        source_reference=f"Documento: {doc_title} (Pág. {page_no}, Tabla Fila {sym_info.get('row_index')})",
                        item_nature="official_rule",
                        governance_note="Símbolo extraído mediante inspección visual geométrica de celda tabular con margen de 3mm.",
                        metadata_payload={
                            "category": sym_info.get("category") or "symbol_convention",
                            "canonical_symbol_family": sym_info.get("canonical_symbol_family"),
                            "standard_reference": sym_info.get("standard_reference"),
                            "source_table_id": tbl_cand.id,
                            "row_index": sym_info.get("row_index"),
                            "col_index": sym_info.get("col_index"),
                            "cell_bbox": cell_bb,
                            "row_bbox": sym_info.get("row_bbox"),
                            "inner_drawing_bbox": inner_bb,
                            "symbol_crop_bbox": symbol_crop_bb,
                            "crop_margin_mm": crop_margin_mm,
                            "row_span": row_span,
                            "col_span": col_span,
                            "graphic_classification": graphic_class,
                            "grid_source": grid_src,
                            "grid_confidence": grid_conf,
                            "physical_grid_detected": phys_grid,
                            "x_boundaries": x_bounds,
                            "y_boundaries": y_bounds,
                            "table_bbox": tbl_bb,
                            "reading_orientation": read_orient,
                            "orientation": read_orient,
                            "orientation_confidence": orient_conf,
                            "orientation_reason": orient_reason,
                            "requires_human_review": req_review,
                            "layout_context": "inside_table",
                            "context_association_mode": sym_info.get("context_association_mode", "directional_reading"),
                            "crop_image_path": crop_p,
                            "needs_visual_crop": needs_crop,
                            "crop_error_reason": sym_info.get("crop_error_reason"),
                            "aliases": sym_info.get("aliases", []),
                            "estimated_physical_size_mm": sym_info.get("estimated_physical_size_mm", {}),
                            "geometric_evidence": sym_info.get("geometric_evidence", True),
                            "geometric_confidence": sym_info.get("geometric_confidence", 1.0),
                            "evidence_sources": sym_info.get("evidence_sources", []),
                            "shape_features": sym_info.get("shape_features", {}),
                            "text_mask_overlap_ratio": sym_info.get("text_mask_overlap_ratio", 0.0),
                            "rejection_reason": sym_info.get("rejection_reason")
                        }
                    )
                    raw_symbol_candidates.append(cell_sym_cand)

            # C) Derivar Premisas Técnicas si contiene Line List, Valve Schedule o especificaciones
            if any(k in str(h).upper() for h in headers for k in ["SPEC", "LINE", "VALV", "TAG", "DIAM", "PRES", "TEMP", "MATERIAL"]):
                prem_cand = ExtractedItem(
                    id=str(uuid.uuid4()),
                    extraction_id=extraction_id,
                    item_type="requirement",
                    candidate_type="premise_candidate",
                    title=f"Premisa Técnica: {table_title}",
                    code_or_number=f"PREM-{discipline[:3].upper()}-{len(generated_candidates) + 1}",
                    description=f"Premisa de diseño/especificación derivada de matriz {table_title}.",
                    content_text=f"Las especificaciones técnicas listadas en {table_title} rigen como premisa de diseño.",
                    derived_text="Todas las líneas y componentes deben cumplir la especificación indicada en la matriz.",
                    crop_image_path=crop_path,
                    bbox_normalized=bbox_norm,
                    page_number=page_no,
                    evidence_references=[node_id] if node_id else [],
                    technical_parameters={"referenced_table": table_title, "primary_discipline": discipline},
                    target_destination="knowledge_base",
                    review_status="to_confirm",
                    source_origin=extraction.source_origin,
                    source_reference=f"Documento: {doc_title}",
                    item_nature="proposed_rule",
                    governance_note="Premisa candidata generada a partir de matriz tabular.",
                    metadata_payload={"evidence_type": "tabular_premise", "primary_discipline": discipline}
                )
                self.db.add(prem_cand)
                generated_candidates.append(prem_cand)

        # 2. Procesar Símbolos Técnicos Detectados (Capa 1 -> Capa 2)
        # Evitar duplicar símbolos que ya fueron materializados desde las tablas arriba
        processed_table_cells = {
            (c.metadata_payload.get("source_table_id"), c.metadata_payload.get("row_index"), c.metadata_payload.get("col_index"))
            for c in raw_symbol_candidates
            if c.metadata_payload and c.metadata_payload.get("row_index") is not None
        }

        for sym in evidence_payload.get("symbols", []):
            s_tid = sym.get("source_table_id")
            s_row = sym.get("row_index")
            s_col = sym.get("col_index")
            if s_row is not None and s_col is not None and (s_tid, s_row, s_col) in processed_table_cells:
                continue

            graphic_class = sym.get("graphic_classification", "symbol")
            if graphic_class in ["figure", "table_graphic"]:
                fig_cand = ExtractedItem(
                    id=str(uuid.uuid4()),
                    extraction_id=extraction_id,
                    item_type="figure",
                    candidate_type="diagram_candidate",
                    title=f"Figura Técnica: {sym.get('title') or 'Gráfico Técnico'}",
                    code_or_number=f"FIG-{discipline[:3].upper()}-{len(generated_candidates) + 1}",
                    description=sym.get("symbol_description") or "Gráfico técnico / figura regional.",
                    content_text=sym.get("content_text") or "Gráfico técnico",
                    derived_text=f"Gráfico técnico detectado en pág {sym.get('page_number', 1)}.",
                    caption_or_context=sym.get("caption_or_context") or sym.get("content_text"),
                    crop_image_path=sym.get("crop_image_path"),
                    bbox_normalized=sym.get("symbol_crop_bbox") or sym.get("bbox_normalized") or [0, 0, 1, 1],
                    page_number=sym.get("page_number", 1),
                    evidence_references=[sym.get("node_id")] if sym.get("node_id") else [],
                    technical_parameters={"graphic_classification": graphic_class, "primary_discipline": discipline},
                    target_destination="both",
                    review_status="to_confirm",
                    source_origin=extraction.source_origin,
                    source_reference=f"Documento: {doc_title} (Pág. {sym.get('page_number', 1)})",
                    item_nature="proposed_rule",
                    governance_note="Gráfico clasificado como figura/diagrama en lugar de símbolo.",
                    metadata_payload={
                        "graphic_classification": graphic_class,
                        "crop_image_path": sym.get("crop_image_path")
                    }
                )
                self.db.add(fig_cand)
                generated_candidates.append(fig_cand)
                continue

            sym_title = sym.get("title") or "Símbolo Técnico"
            crop_p = sym.get("crop_image_path")
            needs_crop = sym.get("needs_visual_crop", False) or not bool(crop_p)
            cell_bb = sym.get("cell_bbox") or sym.get("bbox_normalized", [])
            inner_bb = sym.get("inner_drawing_bbox")
            symbol_crop_bb = sym.get("symbol_crop_bbox") or cell_bb
            read_orient = sym.get("reading_orientation") or "row_major"
            orient_conf = sym.get("orientation_confidence", 1.0)
            orient_reason = sym.get("orientation_reason", "")
            req_review = sym.get("requires_human_review", False) or (orient_conf is not None and orient_conf < 0.60) or read_orient in ["undetermined", "unknown"]

            sym_cand = ExtractedItem(
                id=str(uuid.uuid4()),
                extraction_id=extraction_id,
                item_type="symbol",
                candidate_type="symbol_candidate",
                title=sym_title,
                code_or_number=sym.get("tag_or_code") or f"SYM-{discipline[:3].upper()}-{len(generated_candidates) + len(raw_symbol_candidates) + 1}",
                description=sym.get("symbol_description") or sym.get("technical_function") or f"Símbolo y convención gráfica de ingeniería detectada en pág {sym.get('page_number', 1)}.",
                content_text=sym.get("content_text") or sym_title,
                derived_text=f"Identificador gráfico normalizado para planos ({discipline}).",
                caption_or_context=sym.get("caption_or_context") or sym.get("content_text"),
                crop_image_path=crop_p,
                bbox_normalized=symbol_crop_bb, # Crop ajustado a 3 mm
                page_number=sym.get("page_number", 1),
                evidence_references=[sym.get("node_id")] if sym.get("node_id") else [],
                technical_parameters={
                    "detected_name": sym_title,
                    "context": sym.get("caption_or_context"),
                    "primary_discipline": discipline,
                    "function_or_role": sym.get("technical_function") or "Identificación de componente / tag en diagramas",
                    "standard": sym.get("standard_reference"),
                    "standard_family": sym.get("canonical_symbol_family"),
                    "category": sym.get("category"),
                    "tag_or_code": sym.get("tag_or_code"),
                    "reading_orientation": read_orient,
                    "orientation": read_orient,
                    "orientation_confidence": orient_conf,
                    "orientation_reason": orient_reason,
                    "inner_drawing_bbox": inner_bb,
                    "symbol_crop_bbox": symbol_crop_bb,
                    "crop_margin_mm": sym.get("crop_margin_mm", 3.0),
                    "row_span": sym.get("row_span", 1),
                    "col_span": sym.get("col_span", 1),
                    "graphic_classification": graphic_class,
                    "grid_source": sym.get("grid_source", "vector"),
                    "grid_confidence": sym.get("grid_confidence", 1.0),
                    "physical_grid_detected": sym.get("physical_grid_detected", True),
                    "x_boundaries": sym.get("x_boundaries", []),
                    "y_boundaries": sym.get("y_boundaries", []),
                    "table_bbox": sym.get("table_bbox"),
                    "requires_human_review": req_review
                },
                target_destination="both",
                completeness_status="needs_visual_crop" if needs_crop else "complete",
                review_status="to_confirm",
                source_origin=extraction.source_origin,
                source_reference=f"Documento: {doc_title} (Pág. {sym.get('page_number', 1)})",
                item_nature="official_rule",
                governance_note="Símbolo detectado para validación de leyendas y diagramas con recorte de 3mm.",
                metadata_payload={
                    "category": sym.get("category") or "symbol_convention",
                    "primary_discipline": discipline,
                    "canonical_symbol_family": sym.get("canonical_symbol_family"),
                    "standard_reference": sym.get("standard_reference"),
                    "source_table_id": sym.get("source_table_id"),
                    "row_index": sym.get("row_index"),
                    "col_index": sym.get("col_index"),
                    "cell_bbox": cell_bb,
                    "row_bbox": sym.get("row_bbox"),
                    "inner_drawing_bbox": inner_bb,
                    "symbol_crop_bbox": symbol_crop_bb,
                    "crop_margin_mm": sym.get("crop_margin_mm", 3.0),
                    "row_span": sym.get("row_span", 1),
                    "col_span": sym.get("col_span", 1),
                    "graphic_classification": graphic_class,
                    "grid_source": sym.get("grid_source", "vector"),
                    "grid_confidence": sym.get("grid_confidence", 1.0),
                    "physical_grid_detected": sym.get("physical_grid_detected", True),
                    "x_boundaries": sym.get("x_boundaries", []),
                    "y_boundaries": sym.get("y_boundaries", []),
                    "table_bbox": sym.get("table_bbox"),
                    "reading_orientation": read_orient,
                    "orientation": read_orient,
                    "orientation_confidence": orient_conf,
                    "orientation_reason": orient_reason,
                    "requires_human_review": req_review,
                    "layout_context": sym.get("layout_context") or "inside_table",
                    "context_association_mode": sym.get("context_association_mode", "two_sources_right_top"),
                    "crop_image_path": crop_p,
                    "needs_visual_crop": needs_crop,
                    "crop_error_reason": sym.get("crop_error_reason"),
                    "aliases": sym.get("aliases", [])
                }
            )
            raw_symbol_candidates.append(sym_cand)

        # 2b. Deduplicación Canónica de Símbolos (Condición 4: Un solo representante canónico en UI con ocurrencias)
        canonical_symbols = self._deduplicate_symbol_candidates(raw_symbol_candidates)
        generated_candidates.extend(canonical_symbols)

        # 3. Procesar Figuras y Diagramas Técnicos Detectados
        for fig in evidence_payload.get("figures", []):
            fig_title = fig.get("title") or "Diagrama / Esquema Técnico"
            fig_cand = ExtractedItem(
                id=str(uuid.uuid4()),
                extraction_id=extraction_id,
                item_type="figure",
                candidate_type="diagram_candidate",
                title=fig_title,
                code_or_number=f"FIG-{discipline[:3].upper()}-{len(generated_candidates) + 1}",
                description=f"Diagrama o esquema técnico regional en pág {fig.get('page_number', 1)}.",
                content_text=fig.get("content_text") or fig_title,
                derived_text=f"Esquema de detalle constructivo o diagrama de proceso: {fig_title}.",
                caption_or_context=fig.get("caption_or_context") or fig.get("content_text"),
                disclaimer_notes=self.TOPOLOGICAL_DISCLAIMER,
                crop_image_path=fig.get("crop_image_path"),
                bbox_normalized=fig.get("bbox_normalized", []),
                page_number=fig.get("page_number", 1),
                evidence_references=[fig.get("node_id")] if fig.get("node_id") else [],
                technical_parameters={
                    "detected_name": fig_title,
                    "caption": fig.get("caption_or_context"),
                    "primary_discipline": discipline,
                    "function_or_role": "Diagrama de flujo, P&ID o esquema regional"
                },
                target_destination="knowledge_base",
                review_status="to_confirm",
                source_origin=extraction.source_origin,
                source_reference=f"Documento: {doc_title} (Pág. {fig.get('page_number', 1)})",
                item_nature="official_rule",
                governance_note="Diagrama técnico regional. Nota: sin conectividad topológica de líneas.",
                metadata_payload={"evidence_type": "technical_diagram", "primary_discipline": discipline}
            )
            self.db.add(fig_cand)
            generated_candidates.append(fig_cand)

        # 4. Procesar Fotos e Imágenes de Equipos / Materiales Detectados
        for img_item in evidence_payload.get("images", []):
            img_title = img_item.get("title") or "Imagen / Equipo Técnico"
            img_cand = ExtractedItem(
                id=str(uuid.uuid4()),
                extraction_id=extraction_id,
                item_type="image",
                candidate_type="equipment_image_candidate",
                title=img_title,
                code_or_number=f"EQ-{discipline[:3].upper()}-{len(generated_candidates) + 1}",
                description=f"Registro visual o fotografía de equipo/dispositivo en pág {img_item.get('page_number', 1)}.",
                content_text=img_item.get("content_text") or img_title,
                derived_text=f"Referencia visual de equipo/montaje: {img_title}.",
                caption_or_context=img_item.get("caption_or_context") or img_item.get("content_text"),
                crop_image_path=img_item.get("crop_image_path"),
                bbox_normalized=img_item.get("bbox_normalized", []),
                page_number=img_item.get("page_number", 1),
                evidence_references=[img_item.get("node_id")] if img_item.get("node_id") else [],
                technical_parameters={
                    "detected_name": img_title,
                    "caption": img_item.get("caption_or_context"),
                    "primary_discipline": discipline,
                    "function_or_role": "Registro de equipo, material o dispositivo físico"
                },
                target_destination="knowledge_base",
                review_status="to_confirm",
                source_origin=extraction.source_origin,
                source_reference=f"Documento: {doc_title} (Pág. {img_item.get('page_number', 1)})",
                item_nature="concept",
                governance_note="Imagen de equipo para apoyo y contextualización técnica.",
                metadata_payload={"evidence_type": "equipment_image", "primary_discipline": discipline}
            )
            self.db.add(img_cand)
            generated_candidates.append(img_cand)

        # 5. Procesar Nodos Estructurales (Secciones, Notas, Artículos, Cláusulas, Bloques CAD)
        for node in evidence_payload.get("structural_nodes", []):
            node_type = node.get("node_type")
            node_title = node.get("title") or "Sección Técnica"
            content = node.get("content_text", "")
            node_id = node.get("id")
            page_no = node.get("page_number", 1)
            bbox_norm = node.get("bbox_normalized", [])
            s_payload = node.get("structured_payload", {})

            # A) Bloques CAD
            if node_type == "dxf_block_summary":
                blk_name = s_payload.get("block_name", "UNKNOWN_BLOCK")
                attrs = s_payload.get("attributes", {})
                is_symbol = any(tag in blk_name.upper() for tag in ["VALV", "INST", "PUMP", "SYM", "VLV", "SIMB"])
                candidate_type = "symbol_candidate" if is_symbol else "diagram_candidate"

                cad_cand = ExtractedItem(
                    id=str(uuid.uuid4()),
                    extraction_id=extraction_id,
                    item_type="symbol" if is_symbol else "figure",
                    candidate_type=candidate_type,
                    title=f"Bloque CAD / Símbolo: {blk_name}",
                    code_or_number=f"CAD-{blk_name[:12]}",
                    description=f"Entidad de bloque DXF en capa '{s_payload.get('layer')}'. Atributos: {attrs}",
                    content_text=content,
                    derived_text=f"Elemento gráfico vectorial detectado en plano CAD con atributos: {attrs}",
                    disclaimer_notes=self.TOPOLOGICAL_DISCLAIMER,
                    bbox_normalized=bbox_norm or [0.1, 0.1, 0.4, 0.4],
                    page_number=page_no,
                    evidence_references=[node_id] if node_id else [],
                    technical_parameters={
                        "block_name": blk_name,
                        "layer": s_payload.get("layer"),
                        "location": s_payload.get("location"),
                        "attributes": attrs,
                        "primary_discipline": discipline
                    },
                    target_destination="knowledge_base",
                    review_status="to_confirm",
                    source_origin=extraction.source_origin,
                    source_reference=f"Plano CAD: {doc_title}",
                    item_nature="official_rule",
                    governance_note="Extraído de DXF con ezdxf. Limitación: sin conectividad topológica de líneas.",
                    metadata_payload={"evidence_type": "cad_block", "is_symbol": is_symbol, "primary_discipline": discipline}
                )
                self.db.add(cad_cand)
                generated_candidates.append(cad_cand)

            # B) Capítulos y Títulos Principales (H1)
            elif node_type == "heading" and s_payload.get("header_level") == 1:
                chap_cand = ExtractedItem(
                    id=str(uuid.uuid4()),
                    extraction_id=extraction_id,
                    item_type="chapter",
                    candidate_type="premise_candidate",
                    title=f"Capítulo: {node_title[:80]}",
                    code_or_number=f"CAP-{len(generated_candidates) + 1}",
                    description=f"Capítulo o división temática principal detectada en página {page_no}.",
                    content_text=content,
                    derived_text=f"Marco temático y alcance del capítulo {node_title}.",
                    bbox_normalized=bbox_norm,
                    page_number=page_no,
                    evidence_references=[node_id] if node_id else [],
                    technical_parameters={"primary_discipline": discipline, "function_or_role": "Estructura capitular"},
                    target_destination="knowledge_base",
                    review_status="to_confirm",
                    source_origin=extraction.source_origin,
                    source_reference=f"Documento: {doc_title} (Pág. {page_no})",
                    item_nature="official_rule",
                    governance_note="Capítulo temático extraído del documento.",
                    metadata_payload={"evidence_type": "chapter_header", "primary_discipline": discipline}
                )
                self.db.add(chap_cand)
                generated_candidates.append(chap_cand)

            # C) Artículos y Cláusulas Específicas (H2)
            elif node_type == "heading" and (s_payload.get("is_clause") or s_payload.get("header_level") == 2):
                has_req = s_payload.get("has_requirement", False)
                art_cand = ExtractedItem(
                    id=str(uuid.uuid4()),
                    extraction_id=extraction_id,
                    item_type="article" if not has_req else "rule",
                    candidate_type="rule_candidate" if has_req else "premise_candidate",
                    title=f"Cláusula / Artículo: {node_title[:80]}",
                    code_or_number=f"ART-{len(generated_candidates) + 1}",
                    description=f"Cláusula técnica o artículo normativo extraído de página {page_no}.",
                    content_text=content,
                    derived_text=f"Exigencia técnica / cláusula de aplicación: {content[:120]}...",
                    bbox_normalized=bbox_norm,
                    page_number=page_no,
                    evidence_references=[node_id] if node_id else [],
                    technical_parameters={"section": node_title, "primary_discipline": discipline, "function_or_role": "Cláusula normativa"},
                    target_destination="rules_engine" if has_req else "both",
                    review_status="to_confirm",
                    source_origin=extraction.source_origin,
                    source_reference=f"Documento: {doc_title} (Pág. {page_no})",
                    item_nature="official_rule",
                    governance_note="Cláusula oficial del documento. Requiere aprobación para activación en QA/QC.",
                    metadata_payload={"evidence_type": "normative_clause", "primary_discipline": discipline}
                )
                self.db.add(art_cand)
                generated_candidates.append(art_cand)

            # D) Notas Técnicas
            elif node_type == "technical_note":
                note_cand = ExtractedItem(
                    id=str(uuid.uuid4()),
                    extraction_id=extraction_id,
                    item_type="text_note",
                    candidate_type="premise_candidate",
                    title=f"Nota Técnica: {node_title[:60]}",
                    code_or_number=f"NOTE-{len(generated_candidates) + 1}",
                    description=f"Nota técnica o advertencia de diseño en página {page_no}.",
                    content_text=content,
                    derived_text=f"Criterio y consideración especial: {content[:120]}...",
                    bbox_normalized=bbox_norm,
                    page_number=page_no,
                    evidence_references=[node_id] if node_id else [],
                    technical_parameters={"primary_discipline": discipline, "function_or_role": "Nota técnica de precaución"},
                    target_destination="knowledge_base",
                    review_status="to_confirm",
                    source_origin=extraction.source_origin,
                    source_reference=f"Documento: {doc_title} (Pág. {page_no})",
                    item_nature="concept",
                    governance_note="Nota técnica complementaria para contexto del auditor.",
                    metadata_payload={"evidence_type": "technical_note", "primary_discipline": discipline}
                )
                self.db.add(note_cand)
                generated_candidates.append(note_cand)

            # E) Ejemplos Ilustrativos
            elif node_type == "example":
                ex_cand = ExtractedItem(
                    id=str(uuid.uuid4()),
                    extraction_id=extraction_id,
                    item_type="figure",
                    candidate_type="example_candidate",
                    title=f"Ejemplo Ilustrativo (Pág. {page_no})",
                    code_or_number=f"EX-{discipline[:3].upper()}-{len(generated_candidates) + 1}",
                    description=f"Caso de ejemplo o aplicación ilustrativa detectada en página {page_no}.",
                    content_text=content,
                    derived_text="Caso práctico de aplicación normativa.",
                    bbox_normalized=bbox_norm,
                    page_number=page_no,
                    evidence_references=[node_id] if node_id else [],
                    technical_parameters={"primary_discipline": discipline, "function_or_role": "Ejemplo práctico"},
                    target_destination="knowledge_base",
                    review_status="to_confirm",
                    source_origin=extraction.source_origin,
                    source_reference=f"Documento: {doc_title} (Pág. {page_no})",
                    item_nature="concept",
                    governance_note="Ejemplo normativo para apoyo y contexto del asistente.",
                    metadata_payload={"evidence_type": "example_note", "primary_discipline": discipline}
                )
                self.db.add(ex_cand)
                generated_candidates.append(ex_cand)

            # F) Párrafos con Requisitos Cuantificables
            elif node_type == "paragraph":
                has_requirement = s_payload.get("has_requirement") or bool(re.search(r'(deber[aá]|m[ií]nimo|m[aá]ximo|no inferior|superior a|obligatorio|exigencia|tolerancia|resistencia)', content, re.IGNORECASE))
                has_example = bool(re.search(r'(ejemplo|caso ilustrativo|figura ilustrativa|a modo de ejemplo|por ejemplo)', content[:80], re.IGNORECASE))

                if has_example:
                    ex_cand = ExtractedItem(
                        id=str(uuid.uuid4()),
                        extraction_id=extraction_id,
                        item_type="figure",
                        candidate_type="example_candidate",
                        title=f"Ejemplo / Caso: {content[:50]}...",
                        code_or_number=f"EX-{discipline[:3].upper()}-{len(generated_candidates) + 1}",
                        description=f"Caso de ejemplo en página {page_no}.",
                        content_text=content,
                        derived_text="Caso práctico de aplicación normativa.",
                        bbox_normalized=bbox_norm,
                        page_number=page_no,
                        evidence_references=[node_id] if node_id else [],
                        technical_parameters={"primary_discipline": discipline},
                        target_destination="knowledge_base",
                        review_status="to_confirm",
                        source_origin=extraction.source_origin,
                        source_reference=f"Documento: {doc_title} (Pág. {page_no})",
                        item_nature="concept",
                        governance_note="Ejemplo normativo para apoyo y contexto del asistente.",
                        metadata_payload={"evidence_type": "example_note", "primary_discipline": discipline}
                    )
                    self.db.add(ex_cand)
                    generated_candidates.append(ex_cand)

                elif has_requirement and len(content) > 35:
                    rule_cand = ExtractedItem(
                        id=str(uuid.uuid4()),
                        extraction_id=extraction_id,
                        item_type="rule",
                        candidate_type="rule_candidate",
                        title=f"Regla Candidata: {content[:60]}...",
                        code_or_number=f"R-QAQC-{discipline[:3].upper()}-{len(generated_candidates) + 1}",
                        description=f"Requisito determinístico extraído de página {page_no}.",
                        content_text=content,
                        derived_text=f"Exigencia técnica verificable: {content[:150]}...",
                        bbox_normalized=bbox_norm,
                        page_number=page_no,
                        evidence_references=[node_id] if node_id else [],
                        technical_parameters={"page": page_no, "primary_discipline": discipline},
                        target_destination="rules_engine",
                        review_status="to_confirm",
                        source_origin=extraction.source_origin,
                        source_reference=f"Documento: {doc_title} (Pág. {page_no})",
                        item_nature="official_rule",
                        governance_note="Regla candidata derivada de cláusula técnica. Requiere aprobación para activación en QA/QC.",
                        metadata_payload={"evidence_type": "normative_requirement", "primary_discipline": discipline}
                    )
                    self.db.add(rule_cand)
                    generated_candidates.append(rule_cand)

        # 6. Símbolos: NUNCA inyectar fallbacks sintéticos sin evidencia geométrica real validada
        # Si no hay geometría suficiente, no se genera ningún symbol_candidate.

        if not any(c.candidate_type == "equipment_image_candidate" for c in generated_candidates):
            eq_cand = ExtractedItem(
                id=str(uuid.uuid4()),
                extraction_id=extraction_id,
                item_type="image",
                candidate_type="equipment_image_candidate",
                title=f"Foto / Esquema de Equipo Técnico ({discipline})",
                code_or_number=f"EQ-IMG-{discipline[:3].upper()}-01",
                description="Imagen ilustrativa o fotografía de equipo/ensamble mecánico en planta.",
                caption_or_context="Disposición física y vista isométrica de ensamble de válvulas.",
                content_text="Fotografía y contexto de equipo mecánico según catálogo del fabricante.",
                derived_text="Detalle de montaje y espacio de mantenimiento requerido.",
                bbox_normalized=[0.6, 0.6, 0.95, 0.95],
                page_number=1,
                target_destination="knowledge_base",
                review_status="to_confirm",
                source_origin=extraction.source_origin,
                source_reference=f"Documento: {doc_title}",
                item_nature="concept",
                governance_note="Imagen de equipo de apoyo para contextualización técnica.",
                metadata_payload={"equipment_type": "piping_assembly", "primary_discipline": discipline}
            )
            self.db.add(eq_cand)
            generated_candidates.append(eq_cand)

        for c in generated_candidates:
            meta = dict(c.metadata_payload or {})
            if doc_id:
                meta["document_id"] = doc_id
            if file_hash:
                meta["file_hash_sha256"] = file_hash
            meta["primary_discipline"] = discipline
            meta["topological_connectivity_inferred"] = False
            meta["disclaimer_topology_unverified"] = self.TOPOLOGICAL_DISCLAIMER
            c.metadata_payload = meta
            if not c.disclaimer_notes:
                c.disclaimer_notes = self.TOPOLOGICAL_DISCLAIMER

        # Deduplicación y Matching Estricto contra Motor de Reglas QA/QC
        try:
            dedup_service = RuleDeduplicationService(self.db)
            dedup_service.evaluate_and_tag_items(
                organization_id=extraction.organization_id,
                project_id=extraction.project_id,
                items=generated_candidates
            )
        except Exception as dedup_err:
            logger.warning(f"Error en evaluación de duplicados contra Motor QA/QC: {str(dedup_err)}")

        extraction.total_items = len(generated_candidates)
        extraction.status = "extracted"
        self.db.commit()

        logger.info(f"Generados {len(generated_candidates)} candidatos estructurados para extracción '{extraction_id}'.")
        return generated_candidates

    def _deduplicate_symbol_candidates(
        self,
        raw_candidates: List[ExtractedItem]
    ) -> List[ExtractedItem]:
        """
        Deduplica candidatos a símbolos agrupándolos por identidad canónica.
        Produce un único representante canónico por símbolo con todas sus ocurrencias
        multipágina y multicelda registradas para navegación y ampliación contextual en UI.
        """
        if not raw_candidates:
            return []

        import re
        clusters: Dict[str, List[ExtractedItem]] = {}
        for c in raw_candidates:
            tag = (c.technical_parameters or {}).get("tag_or_code") or (c.metadata_payload or {}).get("tag_or_code") or c.code_or_number
            clean_title = (c.title or "").strip()
            
            # 1. Si tiene tag o código específico (no SYM-GENÉRICO)
            if tag and tag.strip() and not tag.startswith("SYM-"):
                ckey = f"tag:{tag.strip().upper()}"
            elif clean_title and clean_title.lower() not in ["símbolo tabular", "simbolo tabular", "símbolo técnico", "simbolo tecnico"]:
                norm_name = re.sub(r'[^a-zA-Z0-9áéíóúÁÉÍÓÚñÑ]', '', clean_title.lower())
                ckey = f"name:{norm_name}" if norm_name else f"p{c.page_number}_b{round(c.bbox_normalized[0] if c.bbox_normalized else 0, 2)}"
            else:
                fam = (c.metadata_payload or {}).get("canonical_symbol_family", "piping")
                r = (c.metadata_payload or {}).get("row_index", 0)
                col = (c.metadata_payload or {}).get("col_index", 0)
                ckey = f"family_pos:{fam}:p{c.page_number}_r{r}_c{col}"
            clusters.setdefault(ckey, []).append(c)

        canonical_representatives: List[ExtractedItem] = []
        for ckey, group in clusters.items():
            # Ordenar para elegir el mejor representante:
            # 1. Crop visual comprobado
            # 2. Mayor confianza
            # 3. Menor número de página
            group.sort(
                key=lambda x: (
                    1 if x.crop_image_path and x.completeness_status != "needs_visual_crop" else 0,
                    x.match_confidence or 0.8,
                    -(x.page_number or 1)
                ),
                reverse=True
            )
            canonical = group[0]

            # Construir lista de todas las ocurrencias para navegación multipágina y multicelda en UI
            occurrences = []
            for idx, member in enumerate(group):
                is_primary = (idx == 0)
                m_meta = member.metadata_payload or {}
                cell_bb = m_meta.get("cell_bbox") or member.bbox_normalized
                inner_bb = m_meta.get("inner_drawing_bbox")
                r_idx = m_meta.get("row_index")
                c_idx = m_meta.get("col_index")
                src_ref = member.source_reference or f"Pág. {member.page_number}"
                if r_idx is not None and c_idx is not None:
                    src_ref = f"Pág. {member.page_number} (Fila {r_idx + 1}, Col {c_idx + 1})"

                occ = {
                    "occurrence_id": str(uuid.uuid4()),
                    "page_number": member.page_number or 1,
                    "bbox_normalized": cell_bb,
                    "cell_bbox": cell_bb,
                    "inner_drawing_bbox": inner_bb,
                    "crop_image_path": member.crop_image_path,
                    "source_reference": src_ref,
                    "source_table_id": m_meta.get("source_table_id"),
                    "row_index": r_idx,
                    "col_index": c_idx,
                    "reading_orientation": m_meta.get("reading_orientation"),
                    "orientation": m_meta.get("orientation") or m_meta.get("reading_orientation"),
                    "orientation_confidence": m_meta.get("orientation_confidence", 1.0),
                    "orientation_reason": m_meta.get("orientation_reason", ""),
                    "title": member.title,
                    "is_primary": is_primary
                }
                occurrences.append(occ)

            can_meta = dict(canonical.metadata_payload or {})
            can_meta["occurrences"] = occurrences
            can_meta["occurrences_count"] = len(occurrences)
            can_meta["is_canonical_representative"] = True

            # Sincronizar en technical_parameters para máxima interoperabilidad
            can_tech = dict(canonical.technical_parameters or {})
            can_tech["occurrences"] = occurrences
            can_tech["occurrences_count"] = len(occurrences)
            can_tech["reading_orientation"] = can_meta.get("reading_orientation")
            can_tech["orientation"] = can_meta.get("orientation") or can_meta.get("reading_orientation")
            can_tech["orientation_confidence"] = can_meta.get("orientation_confidence", 1.0)
            can_tech["orientation_reason"] = can_meta.get("orientation_reason", "")
            can_tech["inner_drawing_bbox"] = can_meta.get("inner_drawing_bbox")
            canonical.technical_parameters = can_tech

            # Orientación y validación humana obligatoria si confianza < 0.60 (Condición 5)
            orient_conf = can_meta.get("orientation_confidence", 1.0)
            orient_val = can_meta.get("reading_orientation") or can_meta.get("orientation")
            requires_review = can_meta.get("requires_human_review", False) or (orient_conf is not None and orient_conf < 0.60) or orient_val in ["undetermined", "unknown"]

            can_meta["requires_human_review"] = requires_review
            canonical.metadata_payload = can_meta

            if requires_review:
                canonical.review_status = "to_confirm"
                canonical.completeness_status = "review_required"
                canonical.requires_validation = True
                orient_reason = can_meta.get("orientation_reason") or "Orientación tabular no determinada con suficiente confianza (<60%)"
                canonical.governance_note = f"Requiere revisión humana obligatoria: {orient_reason}"
            elif len(occurrences) > 1:
                canonical.governance_note = (canonical.governance_note or "") + f" Símbolo canónico consolidado con {len(occurrences)} ocurrencias en el documento."

            self.db.add(canonical)
            canonical_representatives.append(canonical)

        return canonical_representatives
