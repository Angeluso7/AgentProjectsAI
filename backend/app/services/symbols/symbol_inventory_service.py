import os
import uuid
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.models.document_memory import DetectedSymbol, Document, DocumentSheet
from app.db.models.decision_memory import ReviewRun, SymbolInventoryGroup, ReviewRunDocument, RuleFinding, ReviewRunStep
from app.db.models.template_memory import SymbolTemplate
from app.db.models.symbol_catalog import SymbolTemplateVersion
from app.services.symbols.geometric_validator import (
    compute_symbol_crop_bbox,
    compute_occurrence_context_crop_bbox
)
from app.core.logging import logger

try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False


class SymbolInventoryService:
    """
    Servicio integral de inventario visual, conteo, doble recorte y localización de simbología.
    Cumple con los invariantes fundamentales:
    1. Geometría visual precede a OCR.
    2. Dos recortes estrictamente separados:
       - symbol_crop: identidad visual, 3 mm de margen, usado para matching y catálogo.
       - occurrence_context_crop: contexto y localización, 15 mm de margen, NUNCA para matching.
    3. Agrupación segura por plantilla o por similitud geométrica sobre umbral estricto.
    4. Símbolos desconocidos nunca se ocultan por falta de catálogo productivo.
    """

    CROPS_BASE_PATH = os.environ.get("SYMBOL_CROPS_STORAGE_PATH", os.path.join(os.getcwd(), "storage", "crops"))
    ALGORITHM_VERSION = "v1.0"

    @classmethod
    def compute_source_snapshot_hash(cls, db: Session, review_run: ReviewRun) -> str:
        """Calcula un hash determinista e inmutable del snapshot de datos fuente para la corrida."""
        run_docs = db.query(ReviewRunDocument).filter(
            ReviewRunDocument.review_run_id == review_run.id,
            ReviewRunDocument.status == "included"
        ).order_by(ReviewRunDocument.document_id.asc()).all()
        doc_ids = [rd.document_id for rd in run_docs]

        symbols = db.query(
            DetectedSymbol.id,
            DetectedSymbol.sheet_id,
            DetectedSymbol.classification,
            DetectedSymbol.matching_status,
            DetectedSymbol.matched_template_id,
            DetectedSymbol.matched_template_version_id
        ).filter(
            DetectedSymbol.document_id.in_(doc_ids)
        ).order_by(DetectedSymbol.id.asc()).all() if doc_ids else []

        hasher = hashlib.sha256()
        hasher.update(cls.ALGORITHM_VERSION.encode("utf-8"))
        for d_id in doc_ids:
            hasher.update(str(d_id).encode("utf-8"))
        for s in symbols:
            hasher.update(str(s.id).encode("utf-8"))
            hasher.update(str(s.sheet_id or "").encode("utf-8"))
            hasher.update(str(s.classification or "").encode("utf-8"))
            hasher.update(str(s.matching_status or "").encode("utf-8"))
            hasher.update(str(s.matched_template_id or "").encode("utf-8"))
            hasher.update(str(s.matched_template_version_id or "").encode("utf-8"))
        return hasher.hexdigest()

    @classmethod
    def _ensure_dir(cls, directory: str) -> None:
        os.makedirs(directory, exist_ok=True)

    @classmethod
    def _compute_sha256(cls, file_path: str) -> str:
        if not os.path.exists(file_path):
            return ""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def ensure_crops_for_symbol(
        cls,
        sym: DetectedSymbol,
        raster_image_path: Optional[str] = None,
        page_width_pt: float = 800.0,
        page_height_pt: float = 600.0
    ) -> None:
        """
        Asegura que el DetectedSymbol disponga tanto de symbol_crop_bbox como de occurrence_context_crop_bbox.
        Si se provee la imagen rasterizada de la lámina, extrae y persiste físicamente ambos recortes.
        """
        # 1. symbol_crop_bbox (inner_drawing_bbox + 3 mm limitado a cell_bbox si aplica)
        if not sym.symbol_crop_bbox:
            inner_box = sym.inner_drawing_bbox or sym.bbox_normalized
            cell_box = sym.cell_bbox or sym.bbox_normalized
            sym.symbol_crop_bbox = compute_symbol_crop_bbox(
                cell_bbox_norm=cell_box,
                inner_drawing_bbox=inner_box,
                margin_mm=3.0,
                pw=page_width_pt,
                ph=page_height_pt
            )

        # 2. occurrence_context_crop_bbox (symbol_crop_bbox + 15 mm limitado a page_bbox)
        if not sym.occurrence_context_crop_bbox:
            sym.occurrence_context_crop_bbox = compute_occurrence_context_crop_bbox(
                symbol_crop_bbox_norm=sym.symbol_crop_bbox,
                margin_mm=sym.context_margin_mm or 15.0,
                page_bbox_norm=[0.0, 0.0, 1.0, 1.0],
                pw=page_width_pt,
                ph=page_height_pt
            )

        # 3. Extracción física de recortes si se dispone de raster
        if raster_image_path and os.path.exists(raster_image_path) and OPENCV_AVAILABLE:
            try:
                img = cv2.imread(raster_image_path)
                if img is not None:
                    h, w = img.shape[:2]
                    target_dir = os.path.join(cls.CROPS_BASE_PATH, sym.sheet_id or "general")
                    cls._ensure_dir(target_dir)

                    # A. Guardar symbol_crop físico si no existe
                    if not sym.crop_image_path or not os.path.exists(sym.crop_image_path):
                        sb = sym.symbol_crop_bbox
                        sx0 = max(0, min(w - 1, int(sb[0] * w)))
                        sy0 = max(0, min(h - 1, int(sb[1] * h)))
                        sx1 = max(sx0 + 1, min(w, int(sb[2] * w)))
                        sy1 = max(sy0 + 1, min(h, int(sb[3] * h)))
                        crop_sym = img[sy0:sy1, sx0:sx1]

                        if crop_sym.size > 0:
                            sym_path = os.path.join(target_dir, f"sym_{sym.id}.png")
                            cv2.imwrite(sym_path, crop_sym)
                            sym.crop_image_path = sym_path
                            sym.crop_image_hash = cls._compute_sha256(sym_path)

                    # B. Guardar occurrence_context_crop físico si no existe
                    if not sym.occurrence_context_crop_path or not os.path.exists(sym.occurrence_context_crop_path):
                        cb = sym.occurrence_context_crop_bbox
                        cx0 = max(0, min(w - 1, int(cb[0] * w)))
                        cy0 = max(0, min(h - 1, int(cb[1] * h)))
                        cx1 = max(cx0 + 1, min(w, int(cb[2] * w)))
                        cy1 = max(cy0 + 1, min(h, int(cb[3] * h)))
                        crop_ctx = img[cy0:cy1, cx0:cx1]

                        if crop_ctx.size > 0:
                            ctx_path = os.path.join(target_dir, f"ctx_{sym.id}.png")
                            cv2.imwrite(ctx_path, crop_ctx)
                            sym.occurrence_context_crop_path = ctx_path
                            sym.occurrence_context_crop_hash = cls._compute_sha256(ctx_path)
            except Exception as ex:
                logger.warning(f"Error generando recortes raster para DetectedSymbol {sym.id}: {ex}")

    @classmethod
    def build_run_inventory(
        cls,
        db: Session,
        review_run: ReviewRun,
        force_rebuild: bool = False,
        requested_by: str = "system"
    ) -> Tuple[List[SymbolInventoryGroup], Dict[str, Any]]:
        """
        Construye y persiste el inventario consolidado de simbología para una corrida de revisión.
        Identifica grupos de catálogo, desconocidos, ambiguos y figuras excluidas.
        """
        # Si ya existen grupos y no se fuerza recálculo, retornarlos
        if not force_rebuild:
            existing = db.query(SymbolInventoryGroup).filter(
                SymbolInventoryGroup.review_run_id == review_run.id
            ).order_by(SymbolInventoryGroup.display_code.asc()).all()
            if existing:
                metrics = cls.compute_inventory_metrics(db, review_run, existing)
                return existing, metrics

        # Recopilar documentos y láminas incluidas en la corrida
        run_docs = db.query(ReviewRunDocument).filter(
            ReviewRunDocument.review_run_id == review_run.id,
            ReviewRunDocument.status == "included"
        ).all()
        doc_ids = [rd.document_id for rd in run_docs]

        # Desvincular ocurrencias y eliminar grupos previos si force_rebuild
        if doc_ids:
            db.query(DetectedSymbol).filter(DetectedSymbol.document_id.in_(doc_ids)).update(
                {DetectedSymbol.inventory_group_id: None},
                synchronize_session=False
            )
        db.query(SymbolInventoryGroup).filter(SymbolInventoryGroup.review_run_id == review_run.id).delete(synchronize_session=False)
        db.flush()

        docs = db.query(Document).filter(Document.id.in_(doc_ids)).all() if doc_ids else []
        doc_name_map = {d.id: d.filename for d in docs}

        sheets = db.query(DocumentSheet).filter(DocumentSheet.document_id.in_(doc_ids)).all() if doc_ids else []
        sheet_map = {s.id: s for s in sheets}

        # Obtener todas las geometrías / símbolos detectados en estos documentos
        symbols = db.query(DetectedSymbol).filter(
            DetectedSymbol.document_id.in_(doc_ids)
        ).all() if doc_ids else []

        # Asegurar bboxes de doble recorte para cada símbolo
        for sym in symbols:
            s_obj = sheet_map.get(sym.sheet_id)
            if s_obj:
                pw = float(getattr(s_obj, "width_pt", None) or (s_obj.width_px * 72.0 / (s_obj.dpi or 150) if getattr(s_obj, "width_px", None) else 800.0))
                ph = float(getattr(s_obj, "height_pt", None) or (s_obj.height_px * 72.0 / (s_obj.dpi or 150) if getattr(s_obj, "height_px", None) else 600.0))
            else:
                pw, ph = 800.0, 600.0
            cls.ensure_crops_for_symbol(sym, None, pw, ph)

        # Separar por clasificación
        # Classification: symbol, figure, table_graphic, not_symbol, requires_human_review
        active_symbols: List[DetectedSymbol] = []
        excluded_elements: List[DetectedSymbol] = []

        for sym in symbols:
            if sym.classification in ["figure", "table_graphic", "not_symbol"]:
                excluded_elements.append(sym)
            else:
                active_symbols.append(sym)

        # Estructura temporal de grupos: key -> list of symbols
        grouped_candidates: Dict[str, Dict[str, Any]] = {}
        unknown_counter = 1
        fig_counter = 1

        is_sandbox_mode = (review_run.execution_mode == "sandbox")

        for sym in active_symbols:
            # Caso 1: Tiene match con plantilla canónica
            if sym.matched_template_id or sym.matched_template_version_id:
                tmpl = db.query(SymbolTemplate).filter(SymbolTemplate.id == sym.matched_template_id).first() if sym.matched_template_id else None
                tmpl_ver = db.query(SymbolTemplateVersion).filter(SymbolTemplateVersion.id == sym.matched_template_version_id).first() if sym.matched_template_version_id else None

                key = f"TMPL_{sym.matched_template_id}_{sym.matched_template_version_id}"
                if key not in grouped_candidates:
                    # Determinar estado de catálogo
                    if is_sandbox_mode:
                        cat_status = "recognized_sandbox"
                    else:
                        is_approved = (tmpl_ver.approval_status == "approved") if tmpl_ver else (tmpl.status == "active" if tmpl else False)
                        cat_status = "recognized_production" if is_approved else "recognized_sandbox"

                    grouped_candidates[key] = {
                        "grouping_key": key,
                        "grouping_method": "template_match",
                        "grouping_confidence": 0.95,
                        "display_code": (tmpl.canonical_code if tmpl and tmpl.canonical_code else f"SYM-{sym.symbol_type}"),
                        "matched_template_id": sym.matched_template_id,
                        "matched_template_version_id": sym.matched_template_version_id,
                        "canonical_name": tmpl.canonical_name if tmpl else sym.symbol_type,
                        "description": tmpl.technical_function if tmpl else "Símbolo técnico identificado mediante catálogo normativo.",
                        "technical_function": tmpl.technical_function if tmpl else None,
                        "standard_reference": tmpl.standard_reference if tmpl else "Norma ISA-5.1 / PIP PNC00001",
                        "catalog_status": cat_status,
                        "requires_human_review": False,
                        "explanation": f"Símbolo catalogado con coincidencia de plantilla versión {getattr(tmpl_ver, 'version_number', 1)}.",
                        "symbols": []
                    }
                grouped_candidates[key]["symbols"].append(sym)

            # Caso 2: Símbolo con coincidencia ambigua
            elif sym.matching_status == "ambiguous":
                # Agrupar por aspecto y tipo para mantener consistencia
                key = f"AMB_{sym.symbol_type}"
                if key not in grouped_candidates:
                    grouped_candidates[key] = {
                        "grouping_key": key,
                        "grouping_method": "geometry_signature",
                        "grouping_confidence": 0.65,
                        "display_code": f"AMB-{sym.symbol_type[:8].upper()}",
                        "matched_template_id": None,
                        "matched_template_version_id": None,
                        "canonical_name": f"Símbolo Ambiguo: {sym.symbol_type}",
                        "description": "Candidato geométrico con múltiples plantillas compatibles sin resolución unívoca.",
                        "technical_function": None,
                        "standard_reference": "Revisión técnica requerida",
                        "catalog_status": "ambiguous_symbol",
                        "requires_human_review": True,
                        "explanation": "Presenta similitud con dos o más familias de símbolos del catálogo. Requiere confirmación de contexto.",
                        "symbols": []
                    }
                grouped_candidates[key]["symbols"].append(sym)

            # Caso 3: Desconocido o sin plantilla (unknown_symbol)
            else:
                # Agrupación visual/geométrica segura basada en firma de forma
                # No mezclar símbolos visualmente distintos por conveniencia
                aspect_ratio = 1.0
                if sym.symbol_crop_bbox and len(sym.symbol_crop_bbox) >= 4:
                    w_box = max(0.001, sym.symbol_crop_bbox[2] - sym.symbol_crop_bbox[0])
                    h_box = max(0.001, sym.symbol_crop_bbox[3] - sym.symbol_crop_bbox[1])
                    aspect_ratio = round(w_box / h_box, 1)

                # Clave de geometría discriminante (tipo + relación de aspecto discretizada)
                geom_signature = f"{sym.symbol_type}_AR{int(aspect_ratio * 10)}"
                key = f"UNKNOWN_{geom_signature}"

                if key not in grouped_candidates:
                    u_code = f"U-{unknown_counter:03d}"
                    unknown_counter += 1
                    u_group_id = str(uuid.uuid4())

                    grouped_candidates[key] = {
                        "grouping_key": key,
                        "grouping_method": "visual_similarity",
                        "grouping_confidence": 0.88,
                        "display_code": u_code,
                        "unknown_group_id": u_group_id,
                        "matched_template_id": None,
                        "matched_template_version_id": None,
                        "canonical_name": f"Símbolo desconocido {u_code}",
                        "description": "Geometría técnica válida; no existe plantilla compatible en catálogo.",
                        "technical_function": None,
                        "standard_reference": "Sin plantilla aprobada",
                        "catalog_status": "unknown_symbol",
                        "requires_human_review": True,
                        "explanation": "Elemento vectorial con trazo cerrado o curvas conectadas que no empareja con la línea base activa.",
                        "symbols": []
                    }
                grouped_candidates[key]["symbols"].append(sym)

        # Procesar elementos excluidos (figuras y gráficos de tabla)
        for fig in excluded_elements:
            fig_type = fig.classification or "figure"
            key = f"EXCL_{fig_type}_{fig.symbol_type}"
            if key not in grouped_candidates:
                f_code = f"FIG-{fig_counter:03d}" if fig_type == "figure" else f"GRF-{fig_counter:03d}"
                fig_counter += 1
                grouped_candidates[key] = {
                    "grouping_key": key,
                    "grouping_method": "geometry_signature",
                    "grouping_confidence": 0.95,
                    "display_code": f_code,
                    "matched_template_id": None,
                    "matched_template_version_id": None,
                    "canonical_name": f"Figura/Gráfico técnico: {fig.symbol_type}",
                    "description": "Elemento gráfico clasificado fuera de la taxonomía de simbología de proceso.",
                    "technical_function": None,
                    "standard_reference": "Excluido de verificación normativa de símbolos",
                    "catalog_status": "figure_excluded" if fig_type == "figure" else "not_symbol",
                    "requires_human_review": False,
                    "explanation": "Elemento excluido del conteo de simbología canónica (bloque decorativo, diagrama de flujo general o tabla).",
                    "symbols": []
                }
            grouped_candidates[key]["symbols"].append(fig)

        # Persistir entidades SymbolInventoryGroup y vincular DetectedSymbols
        created_groups: List[SymbolInventoryGroup] = []

        for g_data in grouped_candidates.values():
            sym_list: List[DetectedSymbol] = g_data["symbols"]
            total_occ = len(sym_list)

            # Conteo por documento y hoja
            occ_by_doc: Dict[str, int] = {}
            occ_by_sheet: Dict[str, int] = {}
            confidences: List[float] = []

            best_rep: Optional[DetectedSymbol] = None
            best_rep_score: float = -1.0

            for s in sym_list:
                d_name = doc_name_map.get(s.document_id, s.document_id[:8])
                occ_by_doc[d_name] = occ_by_doc.get(d_name, 0) + 1

                sh_obj = sheet_map.get(s.sheet_id)
                sh_name = getattr(sh_obj, "title", None) or getattr(sh_obj, "sheet_name", None) or (f"Lámina {getattr(sh_obj, 'sheet_number', 1)}" if sh_obj else (s.sheet_id[:8] if s.sheet_id else "Hoja 1"))
                occ_by_sheet[sh_name] = occ_by_sheet.get(sh_name, 0) + 1

                conf = float(s.confidence or 1.0)
                confidences.append(conf)

                # Selección de ocurrencia representativa (mayor nitidez/confianza con crop válido)
                rep_score = conf + (0.2 if s.crop_image_path else 0.0)
                if rep_score > best_rep_score:
                    best_rep_score = rep_score
                    best_rep = s

            conf_summary = {
                "min": round(min(confidences), 3) if confidences else 1.0,
                "max": round(max(confidences), 3) if confidences else 1.0,
                "avg": round(sum(confidences) / max(1, len(confidences)), 3) if confidences else 1.0
            }

            rep_id = best_rep.id if best_rep else (sym_list[0].id if sym_list else None)

            group_record = SymbolInventoryGroup(
                review_run_id=review_run.id,
                grouping_key=g_data["grouping_key"],
                grouping_method=g_data["grouping_method"],
                grouping_confidence=g_data["grouping_confidence"],
                grouping_version=g_data.get("grouping_version", "v1.0"),
                display_code=g_data["display_code"],
                unknown_group_id=g_data.get("unknown_group_id"),
                representative_occurrence_id=rep_id,
                representative_selection_reason="Mayor confianza geométrica y recorte nítido",
                matched_template_id=g_data["matched_template_id"],
                matched_template_version_id=g_data["matched_template_version_id"],
                canonical_name=g_data["canonical_name"],
                description=g_data["description"],
                technical_function=g_data["technical_function"],
                standard_reference=g_data["standard_reference"],
                catalog_status=g_data["catalog_status"],
                confidence_summary=conf_summary,
                total_occurrences=total_occ,
                occurrences_by_document=occ_by_doc,
                occurrences_by_sheet=occ_by_sheet,
                requires_human_review=g_data["requires_human_review"],
                explanation=g_data["explanation"]
            )
            db.add(group_record)
            db.flush()

            # Vincular ocurrencias con el grupo
            for s in sym_list:
                s.inventory_group_id = group_record.id

            created_groups.append(group_record)

        # Persistir metadatos versionados del inventario en review_run.summary
        source_snapshot_hash = cls.compute_source_snapshot_hash(db, review_run)
        run_summary = dict(review_run.summary or {})
        old_meta = run_summary.get("symbol_inventory_meta", {})
        recalc_count = old_meta.get("inventory_recalculation_count", 0) + (1 if force_rebuild and old_meta else 0)
        version_num = f"v{recalc_count + 1}"
        now_iso = datetime.utcnow().isoformat()

        audit_entry = {
            "action": "recalculated" if force_rebuild and old_meta else "initial_build",
            "version": version_num,
            "recalculation_count": recalc_count,
            "generated_at": now_iso,
            "generated_by": requested_by,
            "source_snapshot_hash": source_snapshot_hash,
            "groups_count": len(created_groups)
        }
        history = list(old_meta.get("audit_history", []))
        history.append(audit_entry)

        new_meta = {
            "status": "available",
            "inventory_build_completed": True,
            "inventory_version": version_num,
            "inventory_generated_at": now_iso,
            "inventory_generated_by": requested_by,
            "inventory_source_snapshot_hash": source_snapshot_hash,
            "inventory_recalculation_count": recalc_count,
            "inventory_algorithm_version": cls.ALGORITHM_VERSION,
            "audit_history": history
        }
        run_summary["symbol_inventory_meta"] = new_meta
        review_run.summary = run_summary
        flag_modified(review_run, "summary")
        db.add(review_run)

        # Actualizar paso 4 si existe
        step4 = db.query(ReviewRunStep).filter(
            ReviewRunStep.review_run_id == review_run.id,
            ReviewRunStep.phase == 4
        ).first()
        if step4:
            s4_out = dict(step4.output_summary or {})
            s4_out["symbol_inventory_version"] = version_num
            s4_out["symbol_inventory_built"] = True
            step4.output_summary = s4_out
            db.add(step4)

        db.commit()

        # Calcular métricas globales del inventario
        metrics = cls.compute_inventory_metrics(db, review_run, created_groups)
        return created_groups, metrics

    @classmethod
    def compute_inventory_metrics(
        cls,
        db: Session,
        review_run: ReviewRun,
        groups: List[SymbolInventoryGroup]
    ) -> Dict[str, Any]:
        """Calcula todas las métricas obligatorias de cobertura, conteo y tasas de desconocidos."""
        run_docs = db.query(ReviewRunDocument).filter(
            ReviewRunDocument.review_run_id == review_run.id,
            ReviewRunDocument.status == "included"
        ).all()
        doc_ids = [rd.document_id for rd in run_docs]

        docs_count = len(doc_ids)
        sheets_count = db.query(DocumentSheet).filter(DocumentSheet.document_id.in_(doc_ids)).count() if doc_ids else 0

        # Totales por categoría de estado
        rec_prod = sum(g.total_occurrences for g in groups if g.catalog_status == "recognized_production")
        rec_sand = sum(g.total_occurrences for g in groups if g.catalog_status == "recognized_sandbox")
        rec_ref = sum(g.total_occurrences for g in groups if g.catalog_status == "recognized_reference_only")
        unk_count = sum(g.total_occurrences for g in groups if g.catalog_status == "unknown_symbol")
        amb_count = sum(g.total_occurrences for g in groups if g.catalog_status == "ambiguous_symbol")
        req_rev = sum(g.total_occurrences for g in groups if g.catalog_status == "requires_review")
        fig_excl = sum(g.total_occurrences for g in groups if g.catalog_status == "figure_excluded")
        not_sym = sum(g.total_occurrences for g in groups if g.catalog_status == "not_symbol")

        valid_symbol_occurrences = rec_prod + rec_sand + rec_ref + unk_count + amb_count + req_rev
        geometric_candidates = valid_symbol_occurrences + fig_excl + not_sym

        inventory_groups_count = len([g for g in groups if g.catalog_status not in ["figure_excluded", "not_symbol"]])

        inv_coverage = round((rec_prod + rec_sand) / max(1, valid_symbol_occurrences), 3)
        prod_coverage = round(rec_prod / max(1, valid_symbol_occurrences), 3)
        sand_coverage = round(rec_sand / max(1, valid_symbol_occurrences), 3)
        unk_rate = round(unk_count / max(1, valid_symbol_occurrences), 3)
        rev_rate = round((unk_count + amb_count + req_rev) / max(1, valid_symbol_occurrences), 3)
        excl_rate = round(fig_excl / max(1, geometric_candidates), 3)

        # Desglose por documento
        by_doc: Dict[str, Dict[str, Any]] = {}
        for g in groups:
            for d_name, count in (g.occurrences_by_document or {}).items():
                if d_name not in by_doc:
                    by_doc[d_name] = {
                        "total_occurrences": 0,
                        "recognized_production": 0,
                        "recognized_sandbox": 0,
                        "unknown": 0,
                        "ambiguous": 0
                    }
                by_doc[d_name]["total_occurrences"] += count
                if g.catalog_status == "recognized_production":
                    by_doc[d_name]["recognized_production"] += count
                elif g.catalog_status == "recognized_sandbox":
                    by_doc[d_name]["recognized_sandbox"] += count
                elif g.catalog_status == "unknown_symbol":
                    by_doc[d_name]["unknown"] += count
                elif g.catalog_status == "ambiguous_symbol":
                    by_doc[d_name]["ambiguous"] += count

        return {
            "documents_reviewed": docs_count,
            "sheets_reviewed": sheets_count,
            "geometric_candidates": geometric_candidates,
            "valid_symbol_occurrences": valid_symbol_occurrences,
            "inventory_groups": inventory_groups_count,
            "recognized_production": rec_prod,
            "recognized_sandbox": rec_sand,
            "recognized_reference_only": rec_ref,
            "unknown": unk_count,
            "ambiguous": amb_count,
            "requires_review": req_rev,
            "figures_excluded": fig_excl,
            "not_symbols": not_sym,
            "inventory_coverage": inv_coverage,
            "production_coverage": prod_coverage,
            "sandbox_coverage": sand_coverage,
            "unknown_rate": unk_rate,
            "review_required_rate": rev_rate,
            "exclusion_rate": excl_rate,
            "by_document": by_doc
        }

    @classmethod
    def get_group_occurrences_summary(
        cls,
        db: Session,
        group_id: str
    ) -> List[Dict[str, Any]]:
        """Devuelve el desglose detallado de ocurrencias (SymbolOccurrenceSummary) para un grupo de inventario."""
        group = db.query(SymbolInventoryGroup).filter(SymbolInventoryGroup.id == group_id).first()
        if not group:
            return []

        occurrences = db.query(DetectedSymbol).filter(
            DetectedSymbol.inventory_group_id == group.id
        ).all()

        results = []
        for occ in occurrences:
            doc_obj = occ.document
            d_name = getattr(doc_obj, "filename", None) or f"Doc {occ.document_id}"
            sh_obj = occ.sheet
            sh_name = getattr(sh_obj, "title", None) or getattr(sh_obj, "sheet_name", None) or (f"Lámina {getattr(sh_obj, 'sheet_number', 1)}" if sh_obj else "Hoja 1")
            page_num = getattr(sh_obj, "sheet_number", None) or getattr(sh_obj, "page_number", 1) or 1

            nav_context = {
                "project_id": occ.project_id or occ.document.project_id if occ.document else None,
                "document_id": occ.document_id,
                "sheet_id": occ.sheet_id,
                "page_number": page_num,
                "bbox": occ.symbol_crop_bbox or occ.bbox_normalized
            }

            results.append({
                "occurrence_id": occ.id,
                "inventory_group_id": group.id,
                "project_id": occ.project_id,
                "document_id": occ.document_id,
                "document_name": d_name,
                "sheet_id": occ.sheet_id,
                "sheet_name": sh_name,
                "page_number": page_num,
                "bbox_normalized": occ.bbox_normalized,
                "inner_drawing_bbox": occ.inner_drawing_bbox,
                "symbol_crop_bbox": occ.symbol_crop_bbox,
                "symbol_crop_path": occ.crop_image_path,
                "symbol_crop_hash": occ.crop_image_hash,
                "occurrence_context_crop_bbox": occ.occurrence_context_crop_bbox,
                "occurrence_context_crop_path": occ.occurrence_context_crop_path,
                "occurrence_context_crop_hash": occ.occurrence_context_crop_hash,
                "context_margin_mm": occ.context_margin_mm or 15.0,
                "geometric_confidence": occ.geometric_confidence or 1.0,
                "geometry_score": occ.geometry_score,
                "topology_score": occ.topology_score,
                "visual_score": occ.visual_score,
                "context_score": occ.context_score,
                "match_score": occ.match_score,
                "classification": occ.classification,
                "matching_status": occ.matching_status,
                "orientation": (occ.attributes or {}).get("orientation_deg"),
                "crop_quality_status": "valid" if (occ.geometric_confidence or 1.0) >= 0.70 else "suboptimal",
                "text_mask_overlap_ratio": (occ.attributes or {}).get("text_mask_overlap_ratio", 0.0),
                "detected_tag_or_code": occ.detected_tag_or_code,
                "table_id": occ.table_id,
                "cell_id": occ.cell_id,
                "cell_bbox": occ.cell_bbox,
                "navigation_context": nav_context
            })

        return results

    @classmethod
    def create_grouped_unknown_findings(
        cls,
        db: Session,
        review_run: ReviewRun,
        unknown_groups: List[SymbolInventoryGroup]
    ) -> List[RuleFinding]:
        """
        Regla de negocio 6: NO crear un hallazgo individual por cada ocurrencia desconocida.
        Crea UN único hallazgo agrupado por grupo de símbolos desconocidos (ej. U-001)
        vinculando la lista completa de occurrence_ids y su contexto.
        """
        findings: List[RuleFinding] = []
        for grp in unknown_groups:
            if grp.catalog_status != "unknown_symbol":
                continue

            occurrences = db.query(DetectedSymbol).filter(
                DetectedSymbol.inventory_group_id == grp.id
            ).all()

            if not occurrences:
                continue

            occ_ids = [o.id for o in occurrences]
            rep_occ = next((o for o in occurrences if o.id == grp.representative_occurrence_id), occurrences[0])

            title = f"Grupo {grp.display_code}: {grp.total_occurrences} ocurrencias con geometría válida sin plantilla aprobada"
            desc = (
                f"El grupo de simbología no catalogada '{grp.display_code}' cuenta con {grp.total_occurrences} "
                f"ocurrencias detectadas en {len(grp.occurrences_by_document or {})} documentos. "
                f"Presenta trazo geométrico consistente pero carece de versión aprobada en el Catálogo de Simbología."
            )
            rec = "Auditar el recorte representativo e incorporar la plantilla canónica a la biblioteca de símbolos o validar si corresponde a una excepción de proyecto."

            finding = RuleFinding(
                organization_id=review_run.organization_id,
                review_run_id=review_run.id,
                document_id=rep_occ.document_id,
                sheet_id=rep_occ.sheet_id,
                rule_code="SYM-UNKNOWN-001",
                rule_name="Símbolos sin Plantilla Canónica Aprobada",
                category="normative_compliance",
                severity="high",
                status="open",
                confidence=grp.grouping_confidence,
                finding_type="unregistered_symbol_group",
                title=title,
                description=desc,
                recommendation=rec,
                bbox=rep_occ.symbol_crop_bbox or rep_occ.bbox_normalized,
                evidence_refs={
                    "inventory_group_id": grp.id,
                    "display_code": grp.display_code,
                    "unknown_group_id": grp.unknown_group_id,
                    "total_occurrences": grp.total_occurrences,
                    "occurrence_ids": occ_ids,
                    "representative_occurrence_id": rep_occ.id,
                    "representative_crop_path": rep_occ.crop_image_path or rep_occ.occurrence_context_crop_path
                },
                navigation_context={
                    "project_id": review_run.project_id,
                    "document_id": rep_occ.document_id,
                    "sheet_id": rep_occ.sheet_id,
                    "page_number": getattr(rep_occ.sheet, "sheet_number", None) or getattr(rep_occ.sheet, "page_number", 1) if rep_occ.sheet else 1,
                    "bbox": rep_occ.symbol_crop_bbox or rep_occ.bbox_normalized
                }
            )
            db.add(finding)
            findings.append(finding)

        db.flush()
        return findings

    @classmethod
    def get_default_metrics(cls) -> Dict[str, Any]:
        """Retorna la estructura de métricas de inventario inicializada con ceros seguros."""
        return {
            "documents_reviewed": 0,
            "sheets_reviewed": 0,
            "geometric_candidates": 0,
            "valid_symbol_occurrences": 0,
            "inventory_groups": 0,
            "recognized_production": 0,
            "recognized_sandbox": 0,
            "recognized_reference_only": 0,
            "unknown": 0,
            "ambiguous": 0,
            "requires_review": 0,
            "figures_excluded": 0,
            "not_symbols": 0,
            "inventory_coverage": 0.0,
            "production_coverage": 0.0,
            "sandbox_coverage": 0.0,
            "unknown_rate": 0.0,
            "review_required_rate": 0.0,
            "exclusion_rate": 0.0,
            "by_document": {}
        }

    @classmethod
    def format_group_item(cls, db: Session, g: SymbolInventoryGroup) -> Dict[str, Any]:
        """Formatea un grupo persistido SymbolInventoryGroup a diccionario seguro."""
        rep_crop = None
        if g.representative_occurrence_id:
            rep_occ = db.query(DetectedSymbol).filter(DetectedSymbol.id == g.representative_occurrence_id).first()
            if rep_occ:
                rep_crop = rep_occ.crop_image_path or rep_occ.occurrence_context_crop_path

        return {
            "id": g.id,
            "review_run_id": g.review_run_id,
            "grouping_key": g.grouping_key,
            "grouping_method": g.grouping_method,
            "grouping_confidence": g.grouping_confidence,
            "grouping_version": g.grouping_version,
            "display_code": g.display_code,
            "unknown_group_id": g.unknown_group_id,
            "representative_occurrence_id": g.representative_occurrence_id,
            "representative_selection_reason": g.representative_selection_reason,
            "representative_crop_path": rep_crop,
            "matched_template_id": g.matched_template_id,
            "matched_template_version_id": g.matched_template_version_id,
            "canonical_name": g.canonical_name,
            "description": g.description,
            "technical_function": g.technical_function,
            "standard_reference": g.standard_reference,
            "catalog_status": g.catalog_status,
            "confidence_summary": g.confidence_summary or {},
            "total_occurrences": g.total_occurrences,
            "occurrences_by_document": g.occurrences_by_document or {},
            "occurrences_by_sheet": g.occurrences_by_sheet or {},
            "requires_human_review": g.requires_human_review,
            "explanation": g.explanation,
            "created_at": g.created_at.isoformat() if g.created_at else None
        }

    @classmethod
    def simplify_symbol_description(cls, name: Optional[str], description: Optional[str], code: Optional[str]) -> str:
        """Convierte términos técnicos de piping a lenguaje cotidiano comprensible para no expertos."""
        raw = f"{name or ''} {description or ''} {code or ''}".lower()
        if "gate" in raw or "compuerta" in raw:
            return "Válvula de compuerta (bloquea o permite el paso total del fluido en la cañería)"
        if "globe" in raw or "globo" in raw:
            return "Válvula de globo (regula el paso y cantidad de fluido con precisión)"
        if "check" in raw or "retención" in raw or "retencion" in raw:
            return "Válvula check (permite el avance del fluido en un solo sentido y evita retornos)"
        if "ball" in raw or "bola" in raw:
            return "Válvula de bola (apertura o corte rápido de un cuarto de vuelta)"
        if "butterfly" in raw or "mariposa" in raw:
            return "Válvula mariposa (disco giratorio para corte y regulación en tuberías grandes)"
        if "relief" in raw or "safety" in raw or "seguridad" in raw or "alivio" in raw or "psv" in raw:
            return "Válvula de seguridad o alivio (libera presión automáticamente para proteger el sistema)"
        if "control" in raw:
            return "Válvula de control automático (regula caudal o presión según señales del sistema)"
        if "needle" in raw or "aguja" in raw:
            return "Válvula de aguja (regulación muy fina de pequeños caudales)"
        if "diaphragm" in raw or "diafragma" in raw:
            return "Válvula de diafragma (aísla el fluido de piezas mecánicas, ideal para fluidos corrosivos)"
        if "plug" in raw or "macho" in raw:
            return "Válvula macho (bloqueo mediante obturador cilíndrico o cónico)"
        if "instrument" in raw or "transmisor" in raw or "indicador" in raw:
            return "Instrumento de medición (registra presión, temperatura o nivel en la línea)"
        if "bomba" in raw or "pump" in raw:
            return "Bomba de impulsión (mueve el fluido a lo largo de las cañerías)"
        if "filtro" in raw or "strainer" in raw:
            return "Filtro de cañería (retiene partículas e impurezas en el flujo)"
        if "unknown" in raw or "desconocid" in raw or (code and str(code).startswith("U-")):
            return "Símbolo técnico no identificado (figura en el plano pero falta en el catálogo)"
        if "ambiguo" in raw:
            return "Símbolo con lectura dudosa (requiere confirmación visual de cuál componente es)"

        if name:
            clean_name = name.strip()
            return f"{clean_name} (componente de piping identificado en el plano)"
        return "Componente técnico de piping"

    @classmethod
    def generate_executive_summary(
        cls,
        db: Session,
        review_run: ReviewRun,
        groups: List[SymbolInventoryGroup]
    ) -> List[Dict[str, Any]]:
        """
        Produce el Resumen Gráfico de Simbología por Punto de Revisión con las columnas:
        ITEM | Símbolo | Descripción | Encontrado (Sí/No) | Cantidad | Página/Lámina
        """
        standard_expected = [
            {
                "code": "PIP-VALVE-GATE",
                "name": "Válvula de Compuerta",
                "description": "Válvula de compuerta (bloquea o permite el paso total del fluido en la cañería)"
            },
            {
                "code": "PIP-VALVE-GLOBE",
                "name": "Válvula de Globo",
                "description": "Válvula de globo (regula el paso y cantidad de fluido con precisión)"
            },
            {
                "code": "PIP-VALVE-CHECK",
                "name": "Válvula Check / Retención",
                "description": "Válvula check (permite el avance del fluido en un solo sentido y evita retornos)"
            },
            {
                "code": "PIP-VALVE-BALL",
                "name": "Válvula de Bola",
                "description": "Válvula de bola (apertura o corte rápido de un cuarto de vuelta)"
            },
            {
                "code": "PIP-VALVE-BUTTERFLY",
                "name": "Válvula Mariposa",
                "description": "Válvula mariposa (disco giratorio para corte y regulación en tuberías grandes)"
            },
            {
                "code": "PIP-VALVE-RELIEF",
                "name": "Válvula de Alivio y Seguridad",
                "description": "Válvula de seguridad o alivio (libera presión automáticamente para proteger el sistema)"
            },
            {
                "code": "PIP-VALVE-CONTROL",
                "name": "Válvula de Control",
                "description": "Válvula de control automático (regula caudal o presión según señales del sistema)"
            }
        ]

        sheet_ids = set()
        for g in groups:
            if g.occurrences_by_sheet:
                sheet_ids.update(g.occurrences_by_sheet.keys())

        sheet_map: Dict[str, DocumentSheet] = {}
        if sheet_ids:
            sheets = db.query(DocumentSheet).filter(DocumentSheet.id.in_(list(sheet_ids))).all()
            sheet_map = {str(s.id): s for s in sheets}

        found_items: List[Dict[str, Any]] = []
        represented_codes = set()

        for g in groups:
            if g.catalog_status in ["figure_excluded", "not_symbol"]:
                continue

            code = g.display_code or "S-001"
            name = g.canonical_name or code
            desc = cls.simplify_symbol_description(name, g.description or g.technical_function, code)

            sheet_labels: List[str] = []
            if g.occurrences_by_sheet:
                for s_id, cnt in sorted(g.occurrences_by_sheet.items()):
                    if cnt > 0:
                        s_obj = sheet_map.get(str(s_id))
                        if s_obj:
                            s_code = getattr(s_obj, "sheet_code", None)
                            s_num = getattr(s_obj, "sheet_number", None)
                            s_title = getattr(s_obj, "title", None) or getattr(s_obj, "sheet_name", None)
                            if s_code and str(s_code).strip():
                                label = f"Lámina {str(s_code).strip()}"
                            elif s_num is not None:
                                label = f"Lámina {s_num:02d}" if isinstance(s_num, int) else f"Lámina {s_num}"
                            elif s_title and str(s_title).strip():
                                label = str(s_title).strip()
                            else:
                                label = f"Lámina {str(s_id)[:6]}"
                            if label not in sheet_labels:
                                sheet_labels.append(label)

            if not sheet_labels and g.total_occurrences > 0 and g.representative_occurrence_id:
                rep = db.query(DetectedSymbol).filter(DetectedSymbol.id == g.representative_occurrence_id).first()
                if rep and rep.sheet_id:
                    s_obj = sheet_map.get(str(rep.sheet_id)) or db.query(DocumentSheet).filter(DocumentSheet.id == rep.sheet_id).first()
                    if s_obj:
                        s_code = getattr(s_obj, "sheet_code", None)
                        s_num = getattr(s_obj, "sheet_number", None)
                        if s_code:
                            sheet_labels.append(f"Lámina {s_code}")
                        elif s_num is not None:
                            sheet_labels.append(f"Lámina {s_num:02d}" if isinstance(s_num, int) else f"Lámina {s_num}")

            qty = g.total_occurrences or 0
            is_found = qty > 0

            found_items.append({
                "symbol_code": code,
                "description": desc,
                "found": is_found,
                "quantity": qty,
                "sheet_labels": sheet_labels,
                "sheets_display": ", ".join(sheet_labels) if sheet_labels else ("Lámina 01" if is_found else "-")
            })

            represented_codes.add(code.upper())
            if g.canonical_name:
                represented_codes.add(g.canonical_name.upper())

        missing_items: List[Dict[str, Any]] = []
        for std in standard_expected:
            std_code = std["code"].upper()
            std_name = std["name"].upper()
            already_present = any(
                std_code in rep or std_name in rep or rep in std_name
                for rep in represented_codes
            )
            if not already_present:
                missing_items.append({
                    "symbol_code": std["code"],
                    "description": std["description"],
                    "found": False,
                    "quantity": 0,
                    "sheet_labels": [],
                    "sheets_display": "-"
                })

        all_summary = sorted(found_items, key=lambda x: (-x["quantity"], x["symbol_code"])) + missing_items

        executive_rows = []
        for idx, row in enumerate(all_summary, start=1):
            executive_rows.append({
                "item_index": idx,
                "symbol_code": row["symbol_code"],
                "description": row["description"],
                "found": row["found"],
                "quantity": row["quantity"],
                "sheet_labels": row["sheet_labels"],
                "sheets_display": row["sheets_display"]
            })

        return executive_rows

    @classmethod
    def format_run_inventory(cls, db: Session, review_run: ReviewRun) -> Dict[str, Any]:
        """
        Retorna la estructura segura de inventario de simbología garantizando el contrato de API:
        - status: available | pending | unavailable | failed
        - metrics con defaults seguros
        - groups y excluded_groups como listas
        - executive_summary estructurado para lectura ejecutiva
        - versionado e historial de snapshot
        """
        default_metrics = cls.get_default_metrics()
        run_summary = dict(review_run.summary or {})
        inv_meta = run_summary.get("symbol_inventory_meta", {})

        # Caso 1: Corrida en proceso
        if review_run.status in ["pending", "running"]:
            return {
                "status": "pending",
                "metrics": default_metrics,
                "groups": [],
                "excluded_groups": [],
                "executive_summary": [],
                "reason_code": "RUN_IN_PROGRESS",
                "reason_message": "La corrida de revisión está en ejecución.",
                "can_generate": False,
                "inventory_version": None,
                "inventory_generated_at": None,
                "inventory_source_snapshot_hash": None
            }

        # Consultar grupos persistidos
        existing_groups = db.query(SymbolInventoryGroup).filter(
            SymbolInventoryGroup.review_run_id == review_run.id
        ).order_by(SymbolInventoryGroup.display_code.asc()).all()

        if existing_groups:
            metrics = cls.compute_inventory_metrics(db, review_run, existing_groups)
            active_groups = []
            excluded_groups = []
            for g in existing_groups:
                item = cls.format_group_item(db, g)
                if g.catalog_status in ["figure_excluded", "not_symbol"]:
                    excluded_groups.append(item)
                else:
                    active_groups.append(item)

            gen_at = inv_meta.get("inventory_generated_at") or (
                existing_groups[0].created_at.isoformat() if existing_groups and existing_groups[0].created_at else None
            )

            executive_summary = cls.generate_executive_summary(db, review_run, existing_groups)

            return {
                "status": "available",
                "metrics": metrics,
                "groups": active_groups,
                "excluded_groups": excluded_groups,
                "executive_summary": executive_summary,
                "reason_code": None,
                "reason_message": None,
                "can_generate": True,
                "inventory_version": inv_meta.get("inventory_version", "v1"),
                "inventory_generated_at": gen_at,
                "inventory_source_snapshot_hash": inv_meta.get("inventory_source_snapshot_hash")
            }

        # Caso sin grupos: ¿Se completó el build o es corrida histórica o corrida fallida?
        if inv_meta.get("inventory_build_completed") is True:
            executive_summary = cls.generate_executive_summary(db, review_run, [])
            return {
                "status": "available",
                "metrics": default_metrics,
                "groups": [],
                "excluded_groups": [],
                "executive_summary": executive_summary,
                "reason_code": None,
                "reason_message": None,
                "can_generate": True,
                "inventory_version": inv_meta.get("inventory_version", "v1"),
                "inventory_generated_at": inv_meta.get("inventory_generated_at"),
                "inventory_source_snapshot_hash": inv_meta.get("inventory_source_snapshot_hash")
            }

        if inv_meta.get("status") == "failed":
            return {
                "status": "failed",
                "metrics": default_metrics,
                "groups": [],
                "excluded_groups": [],
                "executive_summary": [],
                "reason_code": inv_meta.get("reason_code", "INVENTORY_BUILD_FAILED"),
                "reason_message": inv_meta.get("reason_message", "Error al procesar inventario."),
                "can_generate": True,
                "inventory_version": None,
                "inventory_generated_at": None,
                "inventory_source_snapshot_hash": None
            }

        # Corrida histórica (previa al inventario o sin generación)
        has_docs = db.query(ReviewRunDocument).filter(
            ReviewRunDocument.review_run_id == review_run.id
        ).count() > 0

        return {
            "status": "unavailable",
            "metrics": default_metrics,
            "groups": [],
            "excluded_groups": [],
            "executive_summary": [],
            "reason_code": "INVENTORY_NOT_GENERATED",
            "reason_message": "Esta corrida fue creada antes del inventario de simbología.",
            "can_generate": has_docs,
            "inventory_version": None,
            "inventory_generated_at": None,
            "inventory_source_snapshot_hash": None
        }

