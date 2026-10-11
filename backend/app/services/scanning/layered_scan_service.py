import os
import math
import uuid
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
import fitz  # PyMuPDF

from app.core.settings import settings
from app.core.logging import logger
from app.db.models.document_memory import (
    DocumentSheet, SheetRegion, DetectedSymbol, ExtractedText,
    ExtractedTable, ExtractedTableCell, TitleBlockExtraction,
    PipingLine, PipingLineSegment
)
from app.db.models.template_memory import SymbolTemplate
from app.db.models.operations import ReviewTask
from app.services.symbols.vector_extractor import VectorSymbolExtractor, PipingLineCandidateDTO, PT_TO_MM
from app.services.layout.service import LayoutService
from app.services.tables.service import TableService


@dataclass
class LayeredScanResultDTO:
    """Resultado estructurado del escaneo por capas de una lámina."""
    sheet_id: str
    piping_lines: List[PipingLine] = field(default_factory=list)
    piping_segments: List[PipingLineSegment] = field(default_factory=list)
    symbols: List[DetectedSymbol] = field(default_factory=list)
    tables: List[ExtractedTable] = field(default_factory=list)
    notes: List[Dict[str, Any]] = field(default_factory=list)
    title_block: Optional[Dict[str, Any]] = None
    review_tasks: List[ReviewTask] = field(default_factory=list)
    layer_confidence: Dict[str, str] = field(default_factory=dict)


class DocumentLayeredScanService:
    """
    Orquestador de escaneo por capas para planos técnicos y diagramas P&ID.
    Ejecuta 7 capas de análisis geométrico y semántico sobre la geometría vectorial y textual:
    - Capa 1: Trazado automático de líneas + franja de buffer (10mm).
    - Capa 2: Símbolos dentro de franja, dirección de flujo y orden secuencial.
    - Capa 3: Resolución de líneas líder (callouts) contra texto técnico.
    - Capa 4: Símbolos restantes fuera de franja (from/to equipment).
    - Capa 5: Clasificación de tablas (leyenda vs datos) y candidatos a catálogo.
    - Capa 6: Extracción y vinculación de notas técnicas.
    - Capa 7: Extracción de metadatos de cajetín y tabla de revisiones.
    """

    def __init__(self, db: Session):
        self.db = db
        self.vector_extractor = VectorSymbolExtractor()
        self.layout_service = LayoutService(db)
        self.table_service = TableService(db)

    def scan_sheet(
        self,
        sheet_id: str,
        page: Optional[fitz.Page] = None,
        cached_drawings: Optional[List[Dict[str, Any]]] = None,
        force_reprocess: bool = False
    ) -> LayeredScanResultDTO:
        """
        Ejecuta las 7 capas de escaneo sobre una lámina técnica.
        Cachea page.get_drawings() una sola vez por hoja y lo reutiliza en todas las capas.
        """
        sheet = self.db.query(DocumentSheet).filter(DocumentSheet.id == sheet_id).first()
        if not sheet:
            raise ValueError(f"Lámina con ID '{sheet_id}' no encontrada.")

        doc_record = sheet.document
        project_id = doc_record.project_id if doc_record else None

        # 0. Obtener PyMuPDF page y cachear drawings
        fitz_doc = None
        if page is None and doc_record and doc_record.file_path and os.path.exists(doc_record.file_path):
            try:
                fitz_doc = fitz.open(doc_record.file_path)
                page_idx = max(0, (sheet.sheet_number or 1) - 1)
                if page_idx < len(fitz_doc):
                    page = fitz_doc[page_idx]
            except Exception as e:
                logger.warning(f"No se pudo abrir documento físico para lámina {sheet_id}: {e}")

        pw = page.rect.width if page else (sheet.width_px or 3000) * (25.4 / 150.0) / PT_TO_MM
        ph = page.rect.height if page else (sheet.height_px or 2000) * (25.4 / 150.0) / PT_TO_MM

        if cached_drawings is None and page is not None:
            cached_drawings = page.get_drawings()
        elif cached_drawings is None:
            cached_drawings = []

        result = LayeredScanResultDTO(sheet_id=sheet_id)

        try:
            # ==============================================================
            # CAPA 1 — Trazado automático de líneas + franja (buffer 10mm)
            # ==============================================================
            lines, segments, layer1_tasks, layer1_conf = self._layer_1_piping_lines(
                sheet=sheet,
                project_id=project_id,
                page=page,
                cached_drawings=cached_drawings,
                pw=pw,
                ph=ph
            )
            result.piping_lines = lines
            result.piping_segments = segments
            result.review_tasks.extend(layer1_tasks)
            result.layer_confidence["layer_1_lines"] = layer1_conf

            # ==============================================================
            # CAPA 2 — Símbolos dentro de franja + Flow Direction + Orden Secuencial
            # ==============================================================
            symbols, layer2_conf = self._layer_2_symbols_in_corridor(
                sheet=sheet,
                piping_lines=lines,
                pw=pw,
                ph=ph
            )
            result.symbols = symbols
            result.layer_confidence["layer_2_corridor_symbols"] = layer2_conf

            # ==============================================================
            # CAPA 3 — Resolución de llamados (leader lines)
            # ==============================================================
            layer3_conf = self._layer_3_resolve_callouts(
                sheet=sheet,
                symbols=symbols,
                cached_drawings=cached_drawings,
                pw=pw,
                ph=ph
            )
            result.layer_confidence["layer_3_callouts"] = layer3_conf

            # ==============================================================
            # CAPA 4 — Símbolos restantes fuera de franja (from/to equipment)
            # ==============================================================
            layer4_conf = self._layer_4_outside_symbols_endpoints(
                symbols=symbols,
                piping_lines=lines,
                pw=pw,
                ph=ph
            )
            result.layer_confidence["layer_4_equipment_endpoints"] = layer4_conf

            # ==============================================================
            # CAPA 5 — Tablas y leyendas (clasificación + candidatos de catálogo)
            # ==============================================================
            tables, layer5_tasks, layer5_conf = self._layer_5_tables_and_legends(
                sheet=sheet,
                project_id=project_id
            )
            result.tables = tables
            result.review_tasks.extend(layer5_tasks)
            result.layer_confidence["layer_5_tables"] = layer5_conf

            # ==============================================================
            # CAPA 6 — Notas y referencias
            # ==============================================================
            notes, layer6_conf = self._layer_6_notes_and_references(
                sheet=sheet,
                symbols=symbols,
                piping_lines=lines
            )
            result.notes = notes
            result.layer_confidence["layer_6_notes"] = layer6_conf

            # ==============================================================
            # CAPA 7 — Metadatos del cajetín (title block)
            # ==============================================================
            title_block_meta, layer7_conf = self._layer_7_title_block(sheet=sheet)
            result.title_block = title_block_meta
            result.layer_confidence["layer_7_title_block"] = layer7_conf

            self.db.commit()

        finally:
            if fitz_doc is not None:
                try:
                    fitz_doc.close()
                except Exception:
                    pass

        return result

    # --------------------------------------------------------------------------
    # IMPLEMENTACIÓN DE CAPAS INDIVIDUALES
    # --------------------------------------------------------------------------

    def _layer_1_piping_lines(
        self,
        sheet: DocumentSheet,
        project_id: Optional[str],
        page: Optional[fitz.Page],
        cached_drawings: List[Dict[str, Any]],
        pw: float,
        ph: float
    ) -> Tuple[List[PipingLine], List[PipingLineSegment], List[ReviewTask], str]:
        """
        Capa 1: Extrae trazos largos, agrupa segmentos contiguos en PipingLine lógicas
        y genera la franja de cápsula de buffer de 10mm.
        """
        line_candidates: List[PipingLineCandidateDTO] = []
        if page is not None:
            line_candidates = self.vector_extractor.extract_piping_lines_from_page(
                page=page,
                page_number=sheet.sheet_number or 1,
                min_length_mm=40.0
            )

        if not line_candidates:
            # Consultar segmentos pre-persistidos en la lámina si existen
            existing_segs = self.db.query(PipingLineSegment).filter(PipingLineSegment.sheet_id == sheet.id).all()
            if existing_segs:
                # Agrupar segmentos existentes en una o más PipingLine si no tienen
                created_lines = []
                for seg in existing_segs:
                    if not seg.piping_line_id and project_id:
                        pline = PipingLine(
                            project_id=project_id,
                            line_number=None,
                            source="auto_vector_extraction",
                            confidence_status="auto_low_needs_review",
                            flow_direction="unconfirmed",
                            attributes={"total_length_mm": seg.length_mm}
                        )
                        self.db.add(pline)
                        self.db.commit()
                        self.db.refresh(pline)
                        seg.piping_line_id = pline.id
                        self.db.add(seg)
                        created_lines.append(pline)
                self.db.commit()
                all_lines = self.db.query(PipingLine).filter(PipingLine.project_id == project_id).all() if project_id else created_lines
                return all_lines, existing_segs, [], "auto_high" if len(existing_segs) > 0 else "auto_low_needs_review"
            return [], [], [], "auto_low_needs_review"

        tol_mm = 5.0

        groups: List[List[PipingLineCandidateDTO]] = []
        used = set()

        for i, c_a in enumerate(line_candidates):
            if i in used:
                continue
            group = [c_a]
            used.add(i)

            p_a_start = c_a.polyline_points[0]
            p_a_end = c_a.polyline_points[-1]

            for j, c_b in enumerate(line_candidates):
                if j in used or c_b.line_style != c_a.line_style:
                    continue

                p_b_start = c_b.polyline_points[0]
                p_b_end = c_b.polyline_points[-1]

                # Distancia física en mm entre extremos
                d_ee = math.hypot((p_a_end[0] - p_b_start[0]) * pw, (p_a_end[1] - p_b_start[1]) * ph) * PT_TO_MM
                d_ss = math.hypot((p_a_start[0] - p_b_end[0]) * pw, (p_a_start[1] - p_b_end[1]) * ph) * PT_TO_MM
                d_cross1 = math.hypot((p_a_end[0] - p_b_end[0]) * pw, (p_a_end[1] - p_b_end[1]) * ph) * PT_TO_MM
                d_cross2 = math.hypot((p_a_start[0] - p_b_start[0]) * pw, (p_a_start[1] - p_b_start[1]) * ph) * PT_TO_MM

                min_d_mm = min(d_ee, d_ss, d_cross1, d_cross2)
                if min_d_mm <= tol_mm:
                    group.append(c_b)
                    used.add(j)

            groups.append(group)

        created_lines: List[PipingLine] = []
        created_segments: List[PipingLineSegment] = []
        review_tasks: List[ReviewTask] = []
        overall_confidence = "auto_high"

        for grp in groups:
            tot_len = sum(c.length_mm for c in grp)
            is_high_conf = tot_len >= 80.0 and len(grp) >= 1
            conf_status = "auto_high" if is_high_conf else "auto_low_needs_review"

            if conf_status == "auto_low_needs_review":
                overall_confidence = "auto_low_needs_review"

            # Crear o asignar PipingLine lógica
            pline = None
            if project_id:
                pline = PipingLine(
                    project_id=project_id,
                    line_number=None,
                    flow_direction="unconfirmed",
                    source="auto_vector_extraction",
                    confidence_status=conf_status,
                    attributes={
                        "total_length_mm": round(tot_len, 2),
                        "segments_count": len(grp),
                        "buffer_margin_mm": 10.0
                    }
                )
                self.db.add(pline)
                self.db.commit()
                self.db.refresh(pline)
                created_lines.append(pline)

                # Generar ReviewTask si la confianza es baja
                if conf_status == "auto_low_needs_review":
                    task = ReviewTask(
                        task_type="line_trace_review",
                        reason_code="low_confidence_line_trace",
                        reason_message=f"El trazado automático agrupó {len(grp)} segmento(s) con longitud {tot_len:.1f} mm pero requiere confirmación humana.",
                        sheet_id=sheet.id,
                        project_id=project_id,
                        status="open",
                        priority="medium",
                        payload={"line_id": pline.id, "sheet_id": sheet.id, "total_length_mm": tot_len},
                        evidence_refs={"line_id": pline.id}
                    )
                    self.db.add(task)
                    review_tasks.append(task)

            # Persistir segmentos
            for c in grp:
                seg = PipingLineSegment(
                    sheet_id=sheet.id,
                    piping_line_id=pline.id if pline else None,
                    polyline_points=c.polyline_points,
                    bbox_normalized=c.bbox_normalized,
                    line_style=c.line_style,
                    length_mm=c.length_mm,
                    stroke_width_pt=c.stroke_width_pt,
                    connected_symbol_ids=[],
                    is_main_process_line=c.is_main_process_line,
                    attributes=c.attributes
                )
                self.db.add(seg)
                created_segments.append(seg)

        self.db.commit()
        for s in created_segments:
            self.db.refresh(s)

        return created_lines, created_segments, review_tasks, overall_confidence

    def _layer_2_symbols_in_corridor(
        self,
        sheet: DocumentSheet,
        piping_lines: List[PipingLine],
        pw: float,
        ph: float
    ) -> Tuple[List[DetectedSymbol], str]:
        """
        Capa 2: Prueba inclusión de símbolos contra el polígono de franja real de 10mm de cada línea.
        Calcula la proyección paramétrica t (0->1) para secuencia de símbolos y detecta flechas de flujo.
        """
        symbols = self.db.query(DetectedSymbol).filter(DetectedSymbol.sheet_id == sheet.id).all()
        if not symbols or not piping_lines:
            return symbols, "auto_high"

        # Buffer real de 10mm a cada lado
        buffer_mm = 10.0

        for sym in symbols:
            if not sym.bbox_normalized or len(sym.bbox_normalized) != 4:
                continue

            bx0, by0, bx1, by2 = sym.bbox_normalized
            cx = (bx0 + bx1) / 2.0
            cy = (by0 + by2) / 2.0

            best_line = None
            min_dist_to_line = float("inf")
            best_t_param = 0.0

            for pline in piping_lines:
                # Evaluar contra todos los segmentos de la línea
                for seg in pline.segments:
                    pts = seg.polyline_points or []
                    if len(pts) < 2:
                        continue

                    dist_mm, t_norm = self._compute_point_to_polyline_distance_and_t(
                        px=cx, py=cy, polyline=pts, pw=pw, ph=ph
                    )
                    if dist_mm < min_dist_to_line:
                        min_dist_to_line = dist_mm
                        best_line = pline
                        best_t_param = t_norm

            attrs = dict(sym.attributes or {})

            if best_line and min_dist_to_line <= buffer_mm:
                # Símbolo dentro de la franja de 10mm
                attrs["piping_line_relation"] = "inline"
                attrs["piping_line_id"] = best_line.id
                attrs["sequence_position"] = round(best_t_param, 4)
                attrs["corridor_distance_mm"] = round(min_dist_to_line, 2)

                # Detección de flecha de flujo
                sym_type_lower = (sym.symbol_type or "").lower()
                is_flow_arrow = any(k in sym_type_lower for k in ("arrow", "flecha", "flow_dir", "flow_direction"))
                if is_flow_arrow:
                    # Inferencia de orientación respecto al trazo
                    rot_deg = sym.match_rotation_deg or attrs.get("rotation_deg", 0)
                    if rot_deg in (0, 90, 360):
                        best_line.flow_direction = "forward"
                    elif rot_deg in (180, 270):
                        best_line.flow_direction = "reverse"
                    else:
                        best_line.flow_direction = "forward"
                    self.db.add(best_line)

            else:
                # Fuera de la franja: candidato a callout o equipo
                if attrs.get("piping_line_relation") != "inline":
                    attrs["piping_line_relation"] = "callout_candidate"
                    attrs["callout_leader_line_status"] = "unresolved_trace"

            sym.attributes = attrs
            self.db.add(sym)

        self.db.commit()
        return symbols, "auto_high"

    def _layer_3_resolve_callouts(
        self,
        sheet: DocumentSheet,
        symbols: List[DetectedSymbol],
        cached_drawings: List[Dict[str, Any]],
        pw: float,
        ph: float
    ) -> str:
        """
        Capa 3: Para símbolos callout_candidate, busca trazos cortos (líneas líder < 40mm)
        en radios expandibles de 20mm -> 30mm -> 40mm que terminen cerca de un bloque de texto.
        """
        callout_syms = [
            s for s in symbols
            if (s.attributes or {}).get("piping_line_relation") == "callout_candidate"
        ]
        if not callout_syms:
            return "auto_high"

        # Recuperar textos OCR de la lámina
        texts = self.db.query(ExtractedText).filter(ExtractedText.sheet_id == sheet.id).all()

        # Filtrar trazos cortos en cached_drawings (< 40mm) que no sean piping segments largos
        short_strokes = []
        for d in cached_drawings:
            r = d.get("rect")
            if not r:
                continue
            w_mm = r.width * PT_TO_MM
            h_mm = r.height * PT_TO_MM
            diag_mm = math.hypot(w_mm, h_mm)
            if 1.0 <= diag_mm <= 40.0:
                short_strokes.append({
                    "rect": r,
                    "diag_mm": diag_mm,
                    "x_mid": (r.x0 + r.x1) / 2.0,
                    "y_mid": (r.y0 + r.y1) / 2.0
                })

        for sym in callout_syms:
            attrs = dict(sym.attributes or {})
            bx0, by0, bx1, by1 = sym.bbox_normalized
            scx = (bx0 + bx1) / 2.0 * pw
            scy = (by0 + by1) / 2.0 * ph

            leader_found = False
            target_text = None

            # Búsqueda iterativa en radios crecientes: 20mm, 30mm, 40mm
            for radius_mm in (20.0, 30.0, 40.0):
                radius_pt = radius_mm / PT_TO_MM

                for stroke in short_strokes:
                    dist_to_sym_pt = math.hypot(stroke["x_mid"] - scx, stroke["y_mid"] - scy)
                    if dist_to_sym_pt <= radius_pt:
                        # Comprobar si el otro extremo del trazo termina cerca de un bloque de texto
                        for txt in texts:
                            if not txt.bbox_normalized or len(txt.bbox_normalized) != 4:
                                continue
                            tx_mid = (txt.bbox_normalized[0] + txt.bbox_normalized[2]) / 2.0 * pw
                            ty_mid = (txt.bbox_normalized[1] + txt.bbox_normalized[3]) / 2.0 * ph
                            dist_to_txt_pt = math.hypot(stroke["x_mid"] - tx_mid, stroke["y_mid"] - ty_mid)
                            if dist_to_txt_pt <= (15.0 / PT_TO_MM):
                                leader_found = True
                                target_text = txt
                                break
                    if leader_found:
                        break
                if leader_found:
                    break

            if leader_found and target_text:
                attrs["callout_leader_line_status"] = "resolved"
                attrs["callout_target_text"] = target_text.text
                attrs["callout_target_text_id"] = target_text.id
            else:
                attrs["callout_leader_line_status"] = "no_leader_found"

            sym.attributes = attrs
            self.db.add(sym)

        self.db.commit()
        return "auto_high"

    def _layer_4_outside_symbols_endpoints(
        self,
        symbols: List[DetectedSymbol],
        piping_lines: List[PipingLine],
        pw: float,
        ph: float
    ) -> str:
        """
        Capa 4: Asocia símbolos restantes fuera de la franja como from_equipment_tag
        o to_equipment_tag si están cerca (<=15mm) de los extremos de la polilínea.
        """
        outside_syms = [
            s for s in symbols
            if (s.attributes or {}).get("piping_line_relation") in ("callout_candidate", "outside_corridor")
            and (s.attributes or {}).get("callout_leader_line_status") != "resolved"
        ]
        if not outside_syms or not piping_lines:
            return "auto_high"

        tol_15mm = 15.0

        for sym in outside_syms:
            bx0, by0, bx1, by1 = sym.bbox_normalized
            cx = (bx0 + bx1) / 2.0
            cy = (by0 + by1) / 2.0

            for pline in piping_lines:
                segs = pline.segments or []
                if not segs:
                    continue

                first_pts = segs[0].polyline_points or []
                last_pts = segs[-1].polyline_points or []
                if not first_pts or not last_pts:
                    continue

                p_start = first_pts[0]
                p_end = last_pts[-1]

                d_start_mm = math.hypot((cx - p_start[0]) * pw, (cy - p_start[1]) * ph) * PT_TO_MM
                d_end_mm = math.hypot((cx - p_end[0]) * pw, (cy - p_end[1]) * ph) * PT_TO_MM

                attrs = dict(sym.attributes or {})
                tag_name = sym.detected_tag_or_code or sym.symbol_type

                if d_start_mm <= tol_15mm:
                    if not pline.from_equipment_tag:
                        pline.from_equipment_tag = tag_name
                        self.db.add(pline)
                    attrs["piping_line_endpoint"] = "from_equipment"
                    attrs["connected_line_id"] = pline.id
                    sym.attributes = attrs
                    self.db.add(sym)
                    break

                elif d_end_mm <= tol_15mm:
                    if not pline.to_equipment_tag:
                        pline.to_equipment_tag = tag_name
                        self.db.add(pline)
                    attrs["piping_line_endpoint"] = "to_equipment"
                    attrs["connected_line_id"] = pline.id
                    sym.attributes = attrs
                    self.db.add(sym)
                    break

        self.db.commit()
        return "auto_high"

    def _layer_5_tables_and_legends(
        self,
        sheet: DocumentSheet,
        project_id: Optional[str]
    ) -> Tuple[List[ExtractedTable], List[ReviewTask], str]:
        """
        Capa 5: Reutiliza la extracción de tablas, clasifica en leyenda_simbolos vs tabla_de_datos,
        y genera candidatos a SymbolTemplate específicos del proyecto enrutados por HITL.
        """
        tables = self.table_service.extract_tables_from_sheet(sheet_id=sheet.id, force_reprocess=False)
        review_tasks: List[ReviewTask] = []

        for tbl in tables:
            # Heurística de clasificación: proporción de celdas con símbolos o título con leyenda
            title_upper = (tbl.title or "").upper()
            cells = tbl.cells or []
            symbol_cell_count = sum(1 for c in cells if c.has_symbol or c.cell_type == "symbol_cell")
            is_legend = (
                any(k in title_upper for k in ("LEYENDA", "SIMBOLOG", "LEGEND"))
                or (len(cells) > 0 and (symbol_cell_count / len(cells)) >= 0.25)
            )

            tbl_attrs = dict(tbl.raw_structure or {})
            if is_legend:
                tbl.table_type = "leyenda_simbolos"
                tbl_attrs["is_symbol_legend"] = True

                # Generar candidatos a plantilla de símbolo para revisión humana HITL
                if project_id and cells:
                    # Agrupar celdas por fila para asociar celda de símbolo con celda de texto descriptivo
                    rows: Dict[int, List[ExtractedTableCell]] = {}
                    for c in cells:
                        rows.setdefault(c.row_index, []).append(c)

                    for r_idx, row_cells in rows.items():
                        sym_cell = next((c for c in row_cells if c.has_symbol or c.cell_type == "symbol_cell"), None)
                        txt_cell = next((c for c in row_cells if c.text and not c.is_header), None)

                        if sym_cell and txt_cell and txt_cell.text:
                            candidate_name = txt_cell.text.strip().title()
                            candidate_code = f"PRJ_CAND_{sheet.id[:4]}_R{r_idx}"

                            # Crear tarea de revisión de símbolo
                            rt = ReviewTask(
                                task_type="symbol_detection_review",
                                reason_code="legend_symbol_candidate",
                                reason_message=f"Detectado en tabla de leyenda de lámina {sheet.sheet_number}. Requiere validación para incorporación canónica.",
                                sheet_id=sheet.id,
                                project_id=project_id,
                                status="open",
                                priority="medium",
                                payload={
                                    "suggested_name": candidate_name,
                                    "suggested_code": candidate_code,
                                    "table_id": tbl.id,
                                    "row_index": r_idx
                                },
                                evidence_refs={"table_id": tbl.id}
                            )
                            self.db.add(rt)
                            review_tasks.append(rt)

            else:
                tbl.table_type = "tabla_de_datos"
                tbl_attrs["is_symbol_legend"] = False

            tbl.raw_structure = tbl_attrs
            self.db.add(tbl)

        self.db.commit()
        return tables, review_tasks, "auto_high"

    def _layer_6_notes_and_references(
        self,
        sheet: DocumentSheet,
        symbols: List[DetectedSymbol],
        piping_lines: List[PipingLine]
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Capa 6: Extrae notas técnicas (numeradas o no) y vincula notas referenciadas
        (ej. 'NOTA 3') con símbolos o líneas técnicas.
        """
        texts = self.db.query(ExtractedText).filter(ExtractedText.sheet_id == sheet.id).all()
        extracted_notes: List[Dict[str, Any]] = []

        note_markers = {}
        for t in texts:
            content = (t.text or "").strip()
            upper_c = content.upper()
            if any(upper_c.startswith(k) for k in ("NOTA", "NOTE", "NOTAS GENERALES")):
                note_id = str(uuid.uuid4())[:8]
                # Extraer número si existe (ej. 'NOTA 1', 'NOTA 2')
                num = None
                tokens = content.split()
                if len(tokens) >= 2 and tokens[1].replace(".", "").replace(":", "").isdigit():
                    num = tokens[1].replace(".", "").replace(":", "")

                note_data = {
                    "id": note_id,
                    "number": num,
                    "text": content,
                    "bbox_normalized": t.bbox_normalized
                }
                extracted_notes.append(note_data)
                if num:
                    note_markers[f"NOTA {num}"] = note_data
                    note_markers[f"N° {num}"] = note_data

        # Vincular símbolos o líneas si hay referencia de nota adyacente
        if note_markers:
            for sym in symbols:
                # Comprobar si algún texto cercano hace referencia a una nota
                if not sym.bbox_normalized:
                    continue
                sx0, sy0, sx1, sy1 = sym.bbox_normalized
                for t in texts:
                    t_upper = (t.text or "").strip().upper()
                    for marker_key, n_data in note_markers.items():
                        if marker_key in t_upper:
                            tb = t.bbox_normalized or [0, 0, 0, 0]
                            dist_to_sym = math.hypot(tb[0] - sx0, tb[1] - sy0)
                            if dist_to_sym <= 0.05:  # muy cercano
                                s_attrs = dict(sym.attributes or {})
                                refs = s_attrs.get("referenced_notes", [])
                                refs.append({"note_number": n_data["number"], "note_text": n_data["text"]})
                                s_attrs["referenced_notes"] = refs
                                sym.attributes = s_attrs
                                self.db.add(sym)

        self.db.commit()
        return extracted_notes, "auto_high"

    def _layer_7_title_block(self, sheet: DocumentSheet) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Capa 7: Extrae metadatos del cajetín y tabla de revisiones, persistiendo en DocumentSheet.
        """
        try:
            tb_extr = self.db.query(TitleBlockExtraction).filter(TitleBlockExtraction.sheet_id == sheet.id).first()
            if not tb_extr:
                tb_extr = self.layout_service.match_and_extract_title_block(sheet_id=sheet.id, force_reprocess=False)

            if tb_extr:
                if tb_extr.sheet_code:
                    sheet.sheet_code = tb_extr.sheet_code
                if tb_extr.sheet_title:
                    sheet.title = tb_extr.sheet_title
                if tb_extr.scale_text:
                    sheet.scale = tb_extr.scale_text
                if tb_extr.revision:
                    sheet.revision = tb_extr.revision
                if tb_extr.date_text:
                    sheet.date_str = tb_extr.date_text

                meta = {
                    "sheet_code": tb_extr.sheet_code,
                    "sheet_title": tb_extr.sheet_title,
                    "scale": tb_extr.scale_text,
                    "revision": tb_extr.revision,
                    "date": tb_extr.date_text,
                    "project_name": tb_extr.project_name,
                    "discipline": tb_extr.discipline,
                    "drawn_by": tb_extr.drawn_by,
                    "checked_by": tb_extr.checked_by,
                    "approved_by": tb_extr.approved_by,
                    "raw_fields": tb_extr.raw_fields or {}
                }
                self.db.add(sheet)
                self.db.commit()
                return meta, "auto_high"
        except Exception as e:
            logger.warning(f"Error extrayendo cajetín para lámina {sheet.id}: {e}")

        return None, "auto_low_needs_review"

    # --------------------------------------------------------------------------
    # MÉTODOS AUXILIARES GEOMÉTRICOS
    # --------------------------------------------------------------------------

    def _compute_point_to_polyline_distance_and_t(
        self,
        px: float,
        py: float,
        polyline: List[List[float]],
        pw: float,
        ph: float
    ) -> Tuple[float, float]:
        """
        Calcula la distancia mínima física en mm desde un punto normalizado a una polilínea,
        y proyecta el punto sobre el parámetro paramétrico t (0.0 -> 1.0) acumulado.
        """
        if len(polyline) < 2:
            return float("inf"), 0.0

        # Longitud total en mm de cada segmento
        seg_lengths_mm = []
        total_len_mm = 0.0

        for i in range(len(polyline) - 1):
            p1 = polyline[i]
            p2 = polyline[i + 1]
            dx_mm = (p2[0] - p1[0]) * pw * PT_TO_MM
            dy_mm = (p2[1] - p1[1]) * ph * PT_TO_MM
            seg_len = math.hypot(dx_mm, dy_mm)
            seg_lengths_mm.append(seg_len)
            total_len_mm += seg_len

        min_dist_mm = float("inf")
        best_t_cum = 0.0
        cum_len = 0.0

        # Punto a proyectar en mm
        target_x_mm = px * pw * PT_TO_MM
        target_y_mm = py * ph * PT_TO_MM

        for i in range(len(polyline) - 1):
            p1 = polyline[i]
            p2 = polyline[i + 1]
            seg_l = seg_lengths_mm[i]

            x1_mm = p1[0] * pw * PT_TO_MM
            y1_mm = p1[1] * ph * PT_TO_MM
            x2_mm = p2[0] * pw * PT_TO_MM
            y2_mm = p2[1] * ph * PT_TO_MM

            dx = x2_mm - x1_mm
            dy = y2_mm - y1_mm
            l2 = dx * dx + dy * dy

            if l2 == 0:
                d = math.hypot(target_x_mm - x1_mm, target_y_mm - y1_mm)
                seg_t = 0.0
            else:
                seg_t = max(0.0, min(1.0, ((target_x_mm - x1_mm) * dx + (target_y_mm - y1_mm) * dy) / l2))
                proj_x = x1_mm + seg_t * dx
                proj_y = y1_mm + seg_t * dy
                d = math.hypot(target_x_mm - proj_x, target_y_mm - proj_y)

            if d < min_dist_mm:
                min_dist_mm = d
                if total_len_mm > 0:
                    best_t_cum = (cum_len + seg_t * seg_l) / total_len_mm
                else:
                    best_t_cum = 0.0

            cum_len += seg_l

        return min_dist_mm, best_t_cum

    def get_ordered_symbols_for_line(
        self,
        piping_line_id: str,
        flow_direction: Optional[str] = None
    ) -> List[DetectedSymbol]:
        """
        Retorna la lista de símbolos 'inline' ordenados secuencialmente a lo largo de la tubería
        (aguas arriba -> aguas abajo).
        Si flow_direction es 'reverse', invierte el orden (descendente por sequence_position).
        """
        pline = self.db.query(PipingLine).filter(PipingLine.id == piping_line_id).first()
        direction = flow_direction or (pline.flow_direction if pline else "unconfirmed")

        seg_ids = [s.id for s in pline.segments] if pline else []
        all_syms = self.db.query(DetectedSymbol).all()

        matching_syms: List[DetectedSymbol] = []
        for sym in all_syms:
            attrs = sym.attributes or {}
            if attrs.get("piping_line_relation") != "inline":
                continue
            is_match = (
                attrs.get("piping_line_id") == piping_line_id or
                any(sid in attrs.get("connected_line_segment_ids", []) for sid in seg_ids)
            )
            if is_match:
                matching_syms.append(sym)

        def get_t(s: DetectedSymbol) -> float:
            return float((s.attributes or {}).get("sequence_position", 0.0))

        matching_syms.sort(key=get_t, reverse=(direction == "reverse"))
        return matching_syms
