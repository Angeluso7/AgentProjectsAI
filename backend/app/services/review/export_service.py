import os
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.db.models.decision_memory import (
    ReviewRun,
    ReviewReport,
    RuleExecution,
    RuleFinding,
    ReviewRunStep,
    ReviewRunDocument
)
from app.db.models.document_memory import (
    Document, DocumentSheet, PipingLine, PipingLineSegment,
    ExtractedTable, ExtractedText, DetectedSymbol, TitleBlockExtraction
)
from app.services.reporting.pdf_renderer import SimplePdfCanvas
from app.core.logging import logger

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False


class ReviewExportService:
    """Servicio de generación y persistencia de reportes de auditoría en JSON, XLSX y PDF."""

    BASE_STORAGE_DIR = os.environ.get("REPORTS_STORAGE_PATH", os.path.join(os.getcwd(), "storage", "reports"))

    @classmethod
    def _compute_sha256(cls, file_path: str) -> str:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def _ensure_dir(cls, directory: str) -> None:
        os.makedirs(directory, exist_ok=True)

    @classmethod
    def create_report(
        cls,
        db: Session,
        review_run_id: str,
        export_format: str = "json"
    ) -> ReviewReport:
        export_format = export_format.lower().strip()
        if export_format not in ["json", "xlsx", "pdf"]:
            raise ValueError(f"Formato no soportado: '{export_format}'. Formatos válidos: json, xlsx, pdf.")

        run = db.query(ReviewRun).filter(ReviewRun.id == review_run_id).first()
        if not run:
            raise ValueError(f"ReviewRun '{review_run_id}' no encontrado.")

        # Recopilar datos completos de la corrida
        steps = db.query(ReviewRunStep).filter(ReviewRunStep.review_run_id == run.id).order_by(ReviewRunStep.phase).all()
        executions = db.query(RuleExecution).filter(RuleExecution.review_run_id == run.id).order_by(RuleExecution.phase).all()
        findings = db.query(RuleFinding).filter(RuleFinding.review_run_id == run.id).all()
        run_docs = db.query(ReviewRunDocument).filter(ReviewRunDocument.review_run_id == run.id).all()

        doc_ids = [rd.document_id for rd in run_docs]
        docs = db.query(Document).filter(Document.id.in_(doc_ids)).all() if doc_ids else []
        doc_map = {d.id: d for d in docs}

        documents_snapshot = []
        for rd in run_docs:
            d = doc_map.get(rd.document_id)
            documents_snapshot.append({
                "document_id": rd.document_id,
                "filename": getattr(d, "filename", "N/A"),
                "file_hash_sha256": getattr(d, "file_hash_sha256", None),
                "inclusion_reason": rd.inclusion_reason,
                "document_role": rd.document_role,
                "status": rd.status
            })

        disc_code = run.discipline.code if run.discipline else "GENERAL"
        disc_name = run.discipline.name if run.discipline else "General"
        topic_code = run.topic.code if run.topic else "ALL"
        topic_name = run.topic.name if run.topic else "General"

        stats = run.summary_stats or {}
        run_data = {
            "review_run_id": run.id,
            "project_id": run.project_id,
            "project_name": getattr(run.project, "name", "Proyecto"),
            "project_code": getattr(run.project, "code", "PRJ"),
            "run_name": run.run_name,
            "execution_mode": run.execution_mode,
            "discipline_code": disc_code,
            "discipline_name": disc_name,
            "topic_code": topic_code,
            "topic_name": topic_name,
            "status": run.status,
            "requested_by": run.requested_by,
            "requested_at": run.requested_at.isoformat() if run.requested_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "execution_time_sec": run.execution_time_sec,
            "stats_summary": stats,
            "baseline_catalog_version": "ISA-5.1-2009-CANONICAL-V1",
            "documents": documents_snapshot,
            "steps": [
                {
                    "phase": s.phase,
                    "phase_name": s.phase_name,
                    "step_type": s.step_type,
                    "status": s.status,
                    "input_summary": s.input_summary,
                    "output_summary": s.output_summary,
                    "error_summary": s.error_summary
                }
                for s in steps
            ],
            "executions": [
                {
                    "id": ex.id,
                    "rule_code": ex.rule.code if ex.rule else "N/A",
                    "rule_name": ex.rule.name if ex.rule else "N/A",
                    "phase": ex.phase,
                    "status": ex.execution_status,
                    "confidence": ex.confidence,
                    "not_evaluable_reason_code": ex.not_evaluable_reason_code,
                    "not_evaluable_reason_message": ex.not_evaluable_reason_message,
                    "missing_requirements": ex.missing_requirements,
                    "recommended_action": ex.recommended_action,
                    "result_summary": ex.result_summary
                }
                for ex in executions
            ],
            "findings": [
                {
                    "id": f.id,
                    "rule_code": f.rule_code,
                    "rule_name": f.rule_name,
                    "severity": f.severity,
                    "status": f.status,
                    "title": f.title,
                    "description": f.description,
                    "recommendation": f.recommendation,
                    "bbox": f.bbox,
                    "navigation_context": f.navigation_context,
                    "execution_mode": (f.evidence_refs or {}).get("execution_mode", run.execution_mode),
                    "is_exploratory": (f.evidence_refs or {}).get("is_exploratory", run.execution_mode == "sandbox"),
                    "warning": (f.evidence_refs or {}).get("warning")
                }
                for f in findings
            ]
        }

        # Cargar inventario técnico de simbología (Tabla 1 y Tabla 2)
        from app.services.symbols.symbol_inventory_service import SymbolInventoryService
        inv_groups, inv_metrics = SymbolInventoryService.build_run_inventory(db, run, force_rebuild=False)
        inv_meta = (run.summary or {}).get("symbol_inventory_meta", {})
        inventory_version = inv_meta.get("inventory_version", "v1")

        all_occurrences = []
        groups_summary = []
        for g in inv_groups:
            occ_list = SymbolInventoryService.get_group_occurrences_summary(db, g.id)
            for o in occ_list:
                o["group_display_code"] = g.display_code
                o["group_canonical_name"] = g.canonical_name
                o["catalog_status"] = g.catalog_status
            all_occurrences.extend(occ_list)

            group_tags: List[str] = []
            for o in occ_list:
                t_val = o.get("detected_tag_or_code")
                if t_val and str(t_val).strip() and str(t_val).strip() not in group_tags:
                    group_tags.append(str(t_val).strip())

            groups_summary.append({
                "id": g.id,
                "display_code": g.display_code,
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
                "tags": group_tags
            })

        run_data["symbol_inventory"] = {
            "version": inventory_version,
            "metrics": inv_metrics,
            "groups": groups_summary,
            "occurrences": all_occurrences
        }

        # Cargar entidades de piping y capas complementarias
        sheet_ids = [s.id for s in db.query(DocumentSheet).filter(DocumentSheet.document_id.in_(doc_ids)).all()] if doc_ids else []

        # 1. Line List (PipingLine)
        piping_lines_data = []
        if run.project_id:
            p_lines = db.query(PipingLine).filter(PipingLine.project_id == run.project_id).all()
            all_syms = db.query(DetectedSymbol).filter(DetectedSymbol.sheet_id.in_(sheet_ids)).all() if sheet_ids else []
            for pl in p_lines:
                sheet_names = set()
                connected_sym_ids = set()
                for seg in pl.segments:
                    if seg.sheet:
                        sheet_names.add(seg.sheet.sheet_code or str(seg.sheet.sheet_number))
                    for csid in (seg.connected_symbol_ids or []):
                        connected_sym_ids.add(csid)

                for sym in all_syms:
                    if (sym.attributes or {}).get("piping_line_id") == pl.id:
                        connected_sym_ids.add(sym.id)

                piping_lines_data.append({
                    "id": pl.id,
                    "line_number": pl.line_number or "S/N",
                    "nominal_size": pl.nominal_size or "-",
                    "service_fluid": pl.service_fluid or "-",
                    "spec_class": pl.spec_class or "-",
                    "insulation": pl.insulation or "No",
                    "from_to": f"{pl.from_equipment_tag or '-'} -> {pl.to_equipment_tag or '-'}",
                    "from_equipment_tag": pl.from_equipment_tag or "-",
                    "to_equipment_tag": pl.to_equipment_tag or "-",
                    "flow_direction": pl.flow_direction or "unconfirmed",
                    "sheets": ", ".join(sorted(sheet_names)) or "-",
                    "valves_count": len(connected_sym_ids),
                    "source": "manual" if pl.source in ("manual_trace", "manual_corrected") else "auto",
                    "confidence_status": pl.confidence_status or "-"
                })
        run_data["piping_lines"] = piping_lines_data

        # 2. Leyendas de Símbolos (Capa 5)
        legends_data = []
        if sheet_ids:
            tables = db.query(ExtractedTable).filter(ExtractedTable.sheet_id.in_(sheet_ids)).all()
            for tbl in tables:
                is_leg = tbl.table_type == "leyenda_simbolos" or (tbl.raw_structure or {}).get("is_symbol_legend") is True
                if is_leg:
                    legends_data.append({
                        "id": tbl.id,
                        "title": tbl.title or "Leyenda de Símbolos",
                        "sheet_name": tbl.sheet.sheet_code or str(tbl.sheet.sheet_number) if tbl.sheet else "-",
                        "dimensions": f"{tbl.row_count}x{tbl.column_count}",
                        "classification": "Tabla identificada como leyenda de símbolos",
                        "description": (tbl.raw_structure or {}).get("description") or "-"
                    })
        run_data["legends"] = legends_data

        # 3. Notas Técnicas Vinculadas (Capa 6)
        notes_data = []
        if sheet_ids:
            raw_texts = db.query(ExtractedText).filter(ExtractedText.sheet_id.in_(sheet_ids)).all()
            for txt in raw_texts:
                t_content = txt.text or ""
                txt_attrs = getattr(txt, "attributes", None) or {}
                is_note = txt_attrs.get("is_technical_note") or "NOTA" in t_content.upper()
                if is_note and len(t_content.strip()) > 5:
                    notes_data.append({
                        "id": txt.id,
                        "sheet_name": txt.sheet.sheet_code or str(txt.sheet.sheet_number) if txt.sheet else "-",
                        "text": t_content.strip(),
                        "confidence": round(txt.confidence or 1.0, 2)
                    })
        run_data["technical_notes"] = notes_data

        # 4. Metadatos de Cajetín Extraídos (Capa 7)
        title_blocks_data = []
        if sheet_ids:
            tb_list = db.query(TitleBlockExtraction).filter(TitleBlockExtraction.sheet_id.in_(sheet_ids)).all()
            for tb in tb_list:
                title_blocks_data.append({
                    "id": tb.id,
                    "sheet_code": tb.sheet_code or (tb.sheet.sheet_code if tb.sheet else "-"),
                    "sheet_title": tb.sheet_title or "-",
                    "project_name": tb.project_name or "-",
                    "revision": tb.revision or "-",
                    "scale_text": tb.scale_text or "-",
                    "discipline": tb.discipline or "-",
                    "date_text": tb.date_text or "-",
                    "drawn_by": tb.drawn_by or "-",
                    "checked_by": tb.checked_by or "-",
                    "approved_by": tb.approved_by or "-",
                    "revisions_summary": (tb.raw_fields or {}).get("revisions") or []
                })
        run_data["title_blocks"] = title_blocks_data

        # Directorio destino
        target_dir = os.path.join(cls.BASE_STORAGE_DIR, run.project_id)
        cls._ensure_dir(target_dir)

        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        report_filename = f"report_{run.id[:8]}_{disc_code}_{topic_code}_{timestamp_str}.{export_format}"
        artifact_path = os.path.join(target_dir, report_filename)

        # Generar archivo físico
        if export_format == "json":
            cls._generate_json(run_data, artifact_path)
        elif export_format == "xlsx":
            cls._generate_xlsx(run_data, artifact_path)
        elif export_format == "pdf":
            cls._generate_pdf(run_data, artifact_path)

        # Calcular SHA-256
        sha256_hash = cls._compute_sha256(artifact_path)

        report = ReviewReport(
            organization_id=run.organization_id,
            project_id=run.project_id,
            review_run_id=run.id,
            discipline_id=run.discipline_id,
            topic_id=run.topic_id,
            report_name=f"Reporte {disc_code} - {topic_name} ({export_format.upper()})",
            format=export_format,
            artifact_path=artifact_path,
            sha256=sha256_hash,
            status="ready",
            documents_snapshot=documents_snapshot,
            baseline_catalog_version="ISA-5.1-2009-CANONICAL-V1",
            stats_summary={**stats, "inventory_version": inventory_version}
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        logger.info(f"Reporte persistido creado ID={report.id} path={artifact_path} sha256={sha256_hash}")
        return report

    @classmethod
    def _generate_json(cls, run_data: Dict[str, Any], output_path: str) -> None:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(run_data, f, indent=2, ensure_ascii=False)

    @classmethod
    def _generate_xlsx(cls, run_data: Dict[str, Any], output_path: str) -> None:
        if not OPENPYXL_AVAILABLE:
            # Fallback a JSON dump con sufijo si no está openpyxl
            cls._generate_json(run_data, output_path)
            return

        wb = openpyxl.Workbook()
        # Sheet 1: Resumen General
        ws_resumen = wb.active
        ws_resumen.title = "Resumen General"

        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
        title_font = Font(name="Arial", size=14, bold=True, color="0F172A")
        bold_font = Font(name="Arial", size=10, bold=True)

        ws_resumen["A1"] = "INFORME DE AUDITORÍA TÉCNICA QA/QC"
        ws_resumen["A1"].font = title_font
        ws_resumen["A2"] = f"Plan Review AI Hybrid - {run_data.get('baseline_catalog_version', 'V1')}"
        ws_resumen["A2"].font = Font(name="Arial", size=10, italic=True, color="64748B")

        summary_rows = [
            ("ID Corrida", run_data.get("review_run_id")),
            ("Proyecto", f"{run_data.get('project_code')} - {run_data.get('project_name')}"),
            ("Especialidad", f"{run_data.get('discipline_code')} ({run_data.get('discipline_name')})"),
            ("Punto de Revisión", f"{run_data.get('topic_code')} ({run_data.get('topic_name')})"),
            ("Modo de Ejecución", run_data.get("execution_mode", "").upper()),
            ("Estado Final", run_data.get("status", "").upper()),
            ("Solicitado Por", run_data.get("requested_by")),
            ("Fecha Ejecución", run_data.get("requested_at")),
            ("Tiempo Ejecución (seg)", run_data.get("execution_time_sec")),
            ("Reglas Evaluadas", len(run_data.get("executions", []))),
            ("Total Hallazgos", len(run_data.get("findings", []))),
        ]

        row_idx = 4
        for label, val in summary_rows:
            ws_resumen[f"A{row_idx}"] = label
            ws_resumen[f"A{row_idx}"].font = bold_font
            ws_resumen[f"B{row_idx}"] = str(val or "")
            row_idx += 1

        # Tabla de KPIs
        stats = run_data.get("stats_summary", {})
        row_idx += 1
        ws_resumen[f"A{row_idx}"] = "Métrica"
        ws_resumen[f"B{row_idx}"] = "Cantidad"
        ws_resumen[f"A{row_idx}"].fill = header_fill
        ws_resumen[f"A{row_idx}"].font = header_font
        ws_resumen[f"B{row_idx}"].fill = header_fill
        ws_resumen[f"B{row_idx}"].font = header_font

        kpis = [
            ("Passed", stats.get("passed", 0)),
            ("Failed", stats.get("failed", 0)),
            ("Warning", stats.get("warning", 0)),
            ("Not Evaluable", stats.get("not_evaluable", 0)),
            ("Critical Findings", stats.get("critical", 0)),
            ("High Findings", stats.get("high", 0)),
            ("Medium Findings", stats.get("medium", 0)),
        ]
        for k_name, k_val in kpis:
            row_idx += 1
            ws_resumen[f"A{row_idx}"] = k_name
            ws_resumen[f"B{row_idx}"] = k_val

        ws_resumen.column_dimensions["A"].width = 30
        ws_resumen.column_dimensions["B"].width = 50

        # Sheet 2: Reglas Evaluadas
        ws_reglas = wb.create_sheet(title="Reglas Evaluadas")
        headers_reglas = [
            "Fase", "Código Regla", "Nombre Regla", "Estado",
            "Confianza", "Razón Not Evaluable", "Mensaje", "Acción Recomendada"
        ]
        ws_reglas.append(headers_reglas)
        for col in range(1, len(headers_reglas) + 1):
            cell = ws_reglas.cell(row=1, column=col)
            cell.fill = header_fill
            cell.font = header_font

        for ex in run_data.get("executions", []):
            ws_reglas.append([
                ex.get("phase"),
                ex.get("rule_code"),
                ex.get("rule_name"),
                ex.get("status"),
                ex.get("confidence"),
                ex.get("not_evaluable_reason_code") or "-",
                ex.get("not_evaluable_reason_message") or "-",
                ex.get("recommended_action") or "-"
            ])

        for col_letter in ["A", "B", "C", "D", "E", "F", "G", "H"]:
            ws_reglas.column_dimensions[col_letter].width = 25

        # Sheet 3: Hallazgos QA-QC
        ws_findings = wb.create_sheet(title="Hallazgos QA-QC")
        headers_findings = [
            "ID Hallazgo", "Código Regla", "Nombre Regla", "Severidad",
            "Estado", "Título", "Descripción", "Recomendación", "Coordenadas BBox",
            "Modo Ejecución", "Exploratorio"
        ]
        ws_findings.append(headers_findings)
        for col in range(1, len(headers_findings) + 1):
            cell = ws_findings.cell(row=1, column=col)
            cell.fill = header_fill
            cell.font = header_font

        for f in run_data.get("findings", []):
            ws_findings.append([
                f.get("id"),
                f.get("rule_code"),
                f.get("rule_name"),
                f.get("severity"),
                f.get("status"),
                f.get("title"),
                f.get("description"),
                f.get("recommendation") or "-",
                str(f.get("bbox") or "-"),
                str(f.get("execution_mode") or run_data.get("execution_mode", "production")).upper(),
                "SÍ (Exploratorio)" if f.get("is_exploratory") else "NO (Productivo)"
            ])

        for col_letter in ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"]:
            ws_findings.column_dimensions[col_letter].width = 25

        # Sheet 4: Documentos Auditados
        ws_docs = wb.create_sheet(title="Documentos Auditados")
        headers_docs = ["ID Documento", "Nombre de Archivo", "Hash SHA-256", "Motivo de Inclusión", "Rol", "Estado"]
        ws_docs.append(headers_docs)
        for col in range(1, len(headers_docs) + 1):
            cell = ws_docs.cell(row=1, column=col)
            cell.fill = header_fill
            cell.font = header_font

        for d in run_data.get("documents", []):
            ws_docs.append([
                d.get("document_id"),
                d.get("filename"),
                d.get("file_hash_sha256") or "-",
                d.get("inclusion_reason"),
                d.get("document_role"),
                d.get("status")
            ])

        for col_letter in ["A", "B", "C", "D", "E", "F"]:
            ws_docs.column_dimensions[col_letter].width = 25

        # Sheet 5: Tabla 1 - Resumen de Inventario Consolidado de Simbología
        inventory = run_data.get("symbol_inventory", {})
        groups = inventory.get("groups", [])
        occurrences = inventory.get("occurrences", [])

        ws_inv = wb.create_sheet(title="Resumen de Inventario")
        headers_inv = [
            "Código Visual", "Nombre Canónico / Identidad", "Estado de Catálogo",
            "Norma / Referencia", "Conteo por Documento", "Total Ocurrencias",
            "Confianza Promedio", "Requiere Revisión", "Explicación Técnica"
        ]
        ws_inv.append(headers_inv)
        for col in range(1, len(headers_inv) + 1):
            cell = ws_inv.cell(row=1, column=col)
            cell.fill = header_fill
            cell.font = header_font

        for g in groups:
            by_doc_str = "; ".join([f"{k}: {v}" for k, v in (g.get("occurrences_by_document") or {}).items()])
            conf_avg = (g.get("confidence_summary") or {}).get("avg", 1.0)
            ws_inv.append([
                g.get("display_code"),
                g.get("canonical_name") or "-",
                g.get("catalog_status"),
                g.get("standard_reference") or "-",
                by_doc_str or "-",
                g.get("total_occurrences", 0),
                conf_avg,
                "SÍ" if g.get("requires_human_review") else "NO",
                g.get("explanation") or "-"
            ])

        for col_letter in ["A", "B", "C", "D", "E", "F", "G", "H", "I"]:
            ws_inv.column_dimensions[col_letter].width = 25

        # Sheet 6: Tabla 2 - Ocurrencias y Localizaciones
        ws_occ = wb.create_sheet(title="Ocurrencias y Localizaciones")
        headers_occ = [
            "ID Ocurrencia", "Código Grupo", "Identidad", "Estado Catálogo",
            "Documento", "Lámina / Hoja", "Página", "BBox Símbolo (3mm)",
            "BBox Contexto (15mm)", "Margen mm", "Confianza Geométrica",
            "Tag / Código", "Calidad Recorte", "Ruta Recorte Símbolo", "Ruta Recorte Contexto"
        ]
        ws_occ.append(headers_occ)
        for col in range(1, len(headers_occ) + 1):
            cell = ws_occ.cell(row=1, column=col)
            cell.fill = header_fill
            cell.font = header_font

        for o in occurrences:
            ws_occ.append([
                o.get("occurrence_id"),
                o.get("group_display_code") or "-",
                o.get("group_canonical_name") or "-",
                o.get("catalog_status") or "-",
                o.get("document_name") or "-",
                o.get("sheet_name") or "-",
                o.get("page_number", 1),
                str(o.get("symbol_crop_bbox") or o.get("bbox_normalized") or "-"),
                str(o.get("occurrence_context_crop_bbox") or "-"),
                o.get("context_margin_mm", 15.0),
                round(o.get("geometric_confidence", 1.0), 3),
                o.get("detected_tag_or_code") or "-",
                o.get("crop_quality_status") or "valid",
                o.get("symbol_crop_path") or "-",
                o.get("occurrence_context_crop_path") or "-"
            ])

        for col_letter in ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O"]:
            ws_occ.column_dimensions[col_letter].width = 22

        # Sheet 7: Tabla Line List
        piping_lines = run_data.get("piping_lines", [])
        ws_lines = wb.create_sheet(title="Line List")
        headers_lines = [
            "N° de Línea", "Tamaño (DN)", "Servicio / Fluido", "Spec / Clase",
            "Aislación", "Desde - Hasta", "Dirección de Flujo", "Hojas / Láminas",
            "Válvulas / Instrumentos", "Origen del Dato", "Estado Confianza"
        ]
        ws_lines.append(headers_lines)
        for col in range(1, len(headers_lines) + 1):
            cell = ws_lines.cell(row=1, column=col)
            cell.fill = header_fill
            cell.font = header_font

        for pl in piping_lines:
            ws_lines.append([
                pl.get("line_number"),
                pl.get("nominal_size"),
                pl.get("service_fluid"),
                pl.get("spec_class"),
                pl.get("insulation"),
                pl.get("from_to"),
                pl.get("flow_direction"),
                pl.get("sheets"),
                pl.get("valves_count", 0),
                pl.get("source", "auto").upper(),
                pl.get("confidence_status")
            ])

        for col_letter in ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"]:
            ws_lines.column_dimensions[col_letter].width = 22

        # Sheet 8: Leyendas de Símbolos
        legends = run_data.get("legends", [])
        ws_leg = wb.create_sheet(title="Leyendas de Símbolos")
        headers_leg = ["ID Tabla", "Título / Nombre", "Lámina / Hoja", "Dimensiones", "Clasificación", "Descripción"]
        ws_leg.append(headers_leg)
        for col in range(1, len(headers_leg) + 1):
            cell = ws_leg.cell(row=1, column=col)
            cell.fill = header_fill
            cell.font = header_font

        for lg in legends:
            ws_leg.append([
                lg.get("id"),
                lg.get("title"),
                lg.get("sheet_name"),
                lg.get("dimensions"),
                lg.get("classification"),
                lg.get("description")
            ])

        for col_letter in ["A", "B", "C", "D", "E", "F"]:
            ws_leg.column_dimensions[col_letter].width = 25

        # Sheet 9: Notas Técnicas
        notes = run_data.get("technical_notes", [])
        ws_notes = wb.create_sheet(title="Notas Técnicas")
        headers_notes = ["ID Texto", "Lámina", "Contenido de Nota", "Confianza"]
        ws_notes.append(headers_notes)
        for col in range(1, len(headers_notes) + 1):
            cell = ws_notes.cell(row=1, column=col)
            cell.fill = header_fill
            cell.font = header_font

        for nt in notes:
            ws_notes.append([
                nt.get("id"),
                nt.get("sheet_name"),
                nt.get("text"),
                nt.get("confidence", 1.0)
            ])

        for col_letter in ["A", "B", "C", "D"]:
            ws_notes.column_dimensions[col_letter].width = 30

        # Sheet 10: Metadatos Cajetín
        title_blocks = run_data.get("title_blocks", [])
        ws_tb = wb.create_sheet(title="Metadatos Cajetín")
        headers_tb = [
            "Lámina / Código", "Título del Plano", "Proyecto", "Revisión",
            "Escala", "Especialidad", "Fecha", "Dibujó", "Revisó", "Aprobó"
        ]
        ws_tb.append(headers_tb)
        for col in range(1, len(headers_tb) + 1):
            cell = ws_tb.cell(row=1, column=col)
            cell.fill = header_fill
            cell.font = header_font

        for tb in title_blocks:
            ws_tb.append([
                tb.get("sheet_code"),
                tb.get("sheet_title"),
                tb.get("project_name"),
                tb.get("revision"),
                tb.get("scale_text"),
                tb.get("discipline"),
                tb.get("date_text"),
                tb.get("drawn_by"),
                tb.get("checked_by"),
                tb.get("approved_by")
            ])

        for col_letter in ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]:
            ws_tb.column_dimensions[col_letter].width = 22

        wb.save(output_path)

    @classmethod
    def _generate_pdf(cls, run_data: Dict[str, Any], output_path: str) -> None:
        pdf = SimplePdfCanvas()
        pdf.new_page()

        y = pdf.height - 50

        # Header Title
        pdf.draw_text(
            "INFORME OFICIAL DE AUDITORÍA QA/QC",
            40, y, font_size=16, font="Helvetica-Bold", color=(0.06, 0.09, 0.16)
        )
        y -= 20
        pdf.draw_text(
            f"Plan Review AI Hybrid - Catálogo {run_data.get('baseline_catalog_version', 'V1')}",
            40, y, font_size=10, font="Helvetica-Oblique", color=(0.4, 0.45, 0.5)
        )
        y -= 25

        # Sandbox Warning si aplica
        if run_data.get("execution_mode") == "sandbox":
            pdf.draw_rect(40, y - 10, pdf.width - 80, 24, fill_color=(1.0, 0.95, 0.8), stroke_color=(0.9, 0.6, 0.1), line_width=1.0)
            pdf.draw_text(
                "ADVERTENCIA SANDBOX: Resultado exploratorio -- no constituye validación productiva oficial.",
                50, y - 4, font_size=9, font="Helvetica-Bold", color=(0.7, 0.35, 0.0)
            )
            y -= 35

        # Metadata Box
        pdf.draw_rect(40, y - 90, pdf.width - 80, 95, fill_color=(0.96, 0.97, 0.99), stroke_color=(0.85, 0.88, 0.92), line_width=0.75)
        my = y - 15
        pdf.draw_text(f"Proyecto: {run_data.get('project_code')} - {run_data.get('project_name')}", 50, my, font_size=9, font="Helvetica-Bold")
        pdf.draw_text(f"Especialidad: {run_data.get('discipline_code')} ({run_data.get('discipline_name')})", 300, my, font_size=9)
        my -= 16
        pdf.draw_text(f"Punto de Revisión: {run_data.get('topic_code')}", 50, my, font_size=9)
        pdf.draw_text(f"Modo: {run_data.get('execution_mode', '').upper()}", 300, my, font_size=9)
        my -= 16
        pdf.draw_text(f"Corrida ID: {run_data.get('review_run_id')}", 50, my, font_size=8, color=(0.3, 0.35, 0.4))
        pdf.draw_text(f"Fecha: {run_data.get('requested_at', '')[:19]}", 300, my, font_size=8, color=(0.3, 0.35, 0.4))
        my -= 16
        stats = run_data.get("stats_summary", {})
        pdf.draw_text(
            f"Resultados: {stats.get('passed', 0)} Cumple | {stats.get('failed', 0)} Falla | {stats.get('warning', 0)} Advertencia | {stats.get('not_evaluable', 0)} No Evaluable",
            50, my, font_size=9, font="Helvetica-Bold", color=(0.1, 0.3, 0.6)
        )
        y -= 110

        # Resumen de Fases
        pdf.draw_text("1. Resumen de Fases de Orquestación", 40, y, font_size=12, font="Helvetica-Bold")
        y -= 18

        for s in run_data.get("steps", []):
            st_color = (0.1, 0.6, 0.2) if s.get("status") == "succeeded" else (0.8, 0.2, 0.1) if s.get("status") == "failed" else (0.4, 0.4, 0.5)
            pdf.draw_text(
                f"Fase {s.get('phase')}: {s.get('phase_name')} [{s.get('step_type').upper()}]",
                45, y, font_size=8.5, font="Helvetica"
            )
            pdf.draw_text(
                s.get("status", "").upper(),
                pdf.width - 120, y, font_size=8.5, font="Helvetica-Bold", color=st_color
            )
            y -= 14
            if y < 70:
                pdf.new_page()
                y = pdf.height - 50

        # =====================================================================
        # Sección 2: Tabla 1 - Inventario Consolidado de Simbología
        # =====================================================================
        inventory = run_data.get("symbol_inventory", {})
        metrics = inventory.get("metrics", {})
        groups = inventory.get("groups", [])
        occurrences = inventory.get("occurrences", [])

        pdf.new_page()
        y = pdf.height - 50

        pdf.draw_text("2. Inventario Consolidado de Simbología (Tabla 1)", 40, y, font_size=12, font="Helvetica-Bold")
        y -= 16

        # Cuadro de Métricas de Cobertura
        pdf.draw_rect(40, y - 36, pdf.width - 80, 40, fill_color=(0.95, 0.97, 1.0), stroke_color=(0.7, 0.8, 0.95), line_width=0.75)
        my = y - 12
        pdf.draw_text(
            f"Ocurrencias Válidas: {metrics.get('valid_symbol_occurrences', 0)} | Grupos: {metrics.get('inventory_groups', 0)} | Figuras Excluidas: {metrics.get('figures_excluded', 0)}",
            48, my, font_size=8.5, font="Helvetica-Bold", color=(0.1, 0.25, 0.5)
        )
        my -= 14
        prod_cov = round(metrics.get("production_coverage", 0.0) * 100, 1)
        sand_cov = round(metrics.get("sandbox_coverage", 0.0) * 100, 1)
        unk_rate = round(metrics.get("unknown_rate", 0.0) * 100, 1)
        pdf.draw_text(
            f"Cob. Productiva: {prod_cov}% | Cob. Sandbox: {sand_cov}% | Tasa Desconocidos: {unk_rate}% | Rec. Prod: {metrics.get('recognized_production', 0)} | Rec. Sandbox: {metrics.get('recognized_sandbox', 0)} | Desconocidos: {metrics.get('unknown', 0)}",
            48, my, font_size=8, font="Helvetica", color=(0.2, 0.3, 0.4)
        )
        y -= 48

        if not groups:
            pdf.draw_text("No se registraron grupos de simbología identificados.", 45, y, font_size=9, font="Helvetica-Oblique", color=(0.5, 0.5, 0.5))
            y -= 15
        else:
            headers_inv = [
                "Código", "Nombre Canónico / Identidad", "Catálogo", "Norma / Ref.",
                "Conteo Doc.", "Total", "Conf.", "HITL", "Explicación Técnica"
            ]
            col_widths_inv = [72, 105, 52, 50, 48, 28, 28, 26, 106]
            rows_inv = []
            for g in groups:
                by_doc_str = "; ".join([f"{k}: {v}" for k, v in (g.get("occurrences_by_document") or {}).items()])
                conf_avg = round((g.get("confidence_summary") or {}).get("avg", 1.0), 2)
                rows_inv.append([
                    g.get("display_code") or "-",
                    g.get("canonical_name") or "-",
                    (g.get("catalog_status") or "-").upper(),
                    g.get("standard_reference") or "-",
                    by_doc_str or "-",
                    g.get("total_occurrences", 0),
                    f"{conf_avg:.2f}",
                    "SÍ" if g.get("requires_human_review") else "NO",
                    g.get("explanation") or "-"
                ])
            y = pdf.draw_table(headers_inv, rows_inv, col_widths_inv, start_y=y, font_size=7.0)

        # =====================================================================
        # Sección 3: Tabla 2 - Anexo de Ubicaciones y Ocurrencias Técnicas
        # =====================================================================
        y -= 20
        if y < 140:
            pdf.new_page()
            y = pdf.height - 50

        pdf.draw_text("3. Anexo de Ubicaciones y Ocurrencias Técnicas (Tabla 2)", 40, y, font_size=12, font="Helvetica-Bold")
        y -= 16

        if not occurrences:
            pdf.draw_text("No se registraron ocurrencias específicas en este informe.", 45, y, font_size=9, font="Helvetica-Oblique", color=(0.5, 0.5, 0.5))
            y -= 15
        else:
            headers_occ = ["Documento", "Lámina / Pág", "Código", "BBox / Contexto", "Tag", "Conf."]
            col_widths_occ = [110, 80, 60, 145, 70, 50]
            rows_occ = []
            for o in occurrences[:50]:
                sym_b = str(o.get('symbol_crop_bbox') or o.get('bbox_normalized') or '-')
                sheet_label = f"{o.get('sheet_name') or '-'} (p.{o.get('page_number', 1)})"
                rows_occ.append([
                    o.get('document_name') or "-",
                    sheet_label,
                    o.get('group_display_code') or "-",
                    sym_b,
                    o.get('detected_tag_or_code') or "-",
                    round(o.get('geometric_confidence', 1.0), 2)
                ])
            y = pdf.draw_table(headers_occ, rows_occ, col_widths_occ, start_y=y)

            if len(occurrences) > 50:
                y -= 8
                pdf.draw_text(
                    f"... y {len(occurrences) - 50} ocurrencias adicionales disponibles en la exportación XLSX.",
                    45, y, font_size=8, font="Helvetica-Oblique", color=(0.2, 0.4, 0.7)
                )
                y -= 14

        # =====================================================================
        # Sección 4: Hallazgos Técnicos Registrados
        # =====================================================================
        y -= 20
        if y < 140:
            pdf.new_page()
            y = pdf.height - 50

        findings = run_data.get("findings", [])
        pdf.draw_text(f"4. Hallazgos Técnicos Registrados ({len(findings)})", 40, y, font_size=12, font="Helvetica-Bold")
        y -= 18

        if not findings:
            pdf.draw_text("No se registraron hallazgos ni discrepancias críticas en esta revisión.", 45, y, font_size=9, font="Helvetica-Oblique", color=(0.3, 0.5, 0.3))
            y -= 15
        else:
            for f in findings:
                sev = f.get("severity", "").upper()
                s_col = (0.8, 0.1, 0.1) if sev == "CRITICAL" else (0.9, 0.4, 0.0) if sev == "HIGH" else (0.2, 0.4, 0.7)
                for t_line in SimplePdfCanvas.wrap_text(f"[{sev}] {f.get('title')}", max_chars_per_line=90):
                    pdf.draw_text(t_line, 45, y, font_size=8.5, font="Helvetica-Bold", color=s_col)
                    y -= 11
                    if y < 70:
                        pdf.new_page()
                        y = pdf.height - 50
                y -= 2
                for d_line in SimplePdfCanvas.wrap_text(f"Descripción: {f.get('description')}", max_chars_per_line=95):
                    pdf.draw_text(d_line, 55, y, font_size=8, color=(0.2, 0.2, 0.2))
                    y -= 11
                    if y < 70:
                        pdf.new_page()
                        y = pdf.height - 50
                if f.get("recommendation"):
                    for r_line in SimplePdfCanvas.wrap_text(f"Recomendación: {f.get('recommendation')}", max_chars_per_line=95):
                        pdf.draw_text(r_line, 55, y, font_size=8, font="Helvetica-Oblique", color=(0.3, 0.3, 0.4))
                        y -= 11
                        if y < 70:
                            pdf.new_page()
                            y = pdf.height - 50
                if f.get("bbox"):
                    pdf.draw_text(f"BBox: {f.get('bbox')}", 55, y, font_size=7.5, color=(0.5, 0.5, 0.5))
                    y -= 10
                y -= 4

                if y < 70:
                    pdf.new_page()
                    y = pdf.height - 50

        # =====================================================================
        # Sección 5: Evaluaciones de Reglas y Estado Normativo
        # =====================================================================
        pdf.new_page()
        y = pdf.height - 50

        executions = run_data.get("executions", [])
        evaluated_rules = [ex for ex in executions if (ex.get("status") or "").upper() != "NOT_EVALUABLE"]
        not_eval_rules = [ex for ex in executions if (ex.get("status") or "").upper() == "NOT_EVALUABLE"]

        pdf.draw_text("5. Evaluaciones de Reglas y Estado Normativo", 40, y, font_size=12, font="Helvetica-Bold")
        y -= 18

        # 5.1 Reglas Evaluadas Activas
        if evaluated_rules:
            pdf.draw_text(f"Reglas Evaluadas Activas ({len(evaluated_rules)})", 45, y, font_size=10, font="Helvetica-Bold", color=(0.1, 0.2, 0.35))
            y -= 14
            for ex in evaluated_rules:
                status = ex.get("status", "").upper()
                color = (0.1, 0.6, 0.2) if status == "PASSED" else (0.8, 0.2, 0.1) if status == "FAILED" else (0.8, 0.5, 0.0)
                pdf.draw_text(f"{ex.get('rule_code')} - {ex.get('rule_name')}", 45, y, font_size=8.5, font="Helvetica-Bold")
                pdf.draw_text(status, pdf.width - 120, y, font_size=8.5, font="Helvetica-Bold", color=color)
                y -= 13
                if y < 70:
                    pdf.new_page()
                    y = pdf.height - 50
            y -= 8
        else:
            pdf.draw_text("No se ejecutaron reglas activas deterministas en esta corrida.", 45, y, font_size=8.5, font="Helvetica-Oblique", color=(0.4, 0.4, 0.4))
            y -= 16

        # 5.2 Resumen Agrupado de Reglas Not Evaluable
        if not_eval_rules:
            if y < 180:
                pdf.new_page()
                y = pdf.height - 50

            reasons_count: Dict[str, int] = {}
            for ex in not_eval_rules:
                cause = ex.get("not_evaluable_reason_code") or "NO_APPROVED_RULES"
                reasons_count[cause] = reasons_count.get(cause, 0) + 1

            pdf.draw_text(f"Resumen de Reglas Sin Ejecutor Activo ({len(not_eval_rules)} reglas)", 45, y, font_size=10, font="Helvetica-Bold", color=(0.5, 0.3, 0.1))
            y -= 16

            causes_summary = " | ".join([f"{c}: {n}" for c, n in reasons_count.items()])
            pdf.draw_rect(40, y - 24, pdf.width - 80, 26, fill_color=(0.98, 0.96, 0.93), stroke_color=(0.85, 0.75, 0.6), line_width=0.5)
            pdf.draw_text(
                f"Causa principal: {causes_summary}",
                50, y - 10, font_size=8, font="Helvetica", color=(0.45, 0.25, 0.05)
            )
            y -= 36

            headers_ne = ["Código Regla", "Nombre / Título", "Causa", "Acción Recomendada"]
            col_widths_ne = [95, 170, 110, 140]
            rows_ne = []
            for ex in not_eval_rules[:20]:
                rows_ne.append([
                    ex.get("rule_code") or "-",
                    ex.get("rule_name") or "-",
                    ex.get("not_evaluable_reason_code") or "SIN_EJECUTOR",
                    ex.get("recommended_action") or "-"
                ])
            y = pdf.draw_table(headers_ne, rows_ne, col_widths_ne, start_y=y)

            if len(not_eval_rules) > 20:
                y -= 8
                pdf.draw_text(
                    f"+{len(not_eval_rules) - 20} reglas adicionales sin ejecutor activo disponibles en la exportación XLSX completa.",
                    45, y, font_size=8, font="Helvetica-Oblique", color=(0.4, 0.45, 0.5)
                )
                y -= 14

        # =====================================================================
        # Sección 6: Line List (Listado de Líneas de Piping)
        # =====================================================================
        piping_lines = run_data.get("piping_lines", [])
        if piping_lines:
            pdf.new_page()
            y = pdf.height - 50
            pdf.draw_text(f"6. Line List - Trazado y Continuidad de Tuberías ({len(piping_lines)} líneas)", 40, y, font_size=12, font="Helvetica-Bold")
            y -= 16

            headers_ll = ["N° Línea", "DN", "Serv.", "Spec", "Aisl.", "Desde - Hasta", "Flujo", "Láminas", "Válv.", "Origen"]
            col_widths_ll = [80, 35, 40, 45, 35, 110, 50, 60, 30, 45]
            rows_ll = []
            for pl in piping_lines:
                rows_ll.append([
                    pl.get("line_number") or "S/N",
                    pl.get("nominal_size") or "-",
                    pl.get("service_fluid") or "-",
                    pl.get("spec_class") or "-",
                    pl.get("insulation") or "-",
                    pl.get("from_to") or "-",
                    pl.get("flow_direction") or "unconfirmed",
                    pl.get("sheets") or "-",
                    pl.get("valves_count", 0),
                    pl.get("source", "auto").upper()
                ])
            y = pdf.draw_table(headers_ll, rows_ll, col_widths_ll, start_y=y, font_size=7.5)

        # =====================================================================
        # Sección 7: Leyendas de Símbolos Técnicos (Capa 5)
        # =====================================================================
        legends = run_data.get("legends", [])
        if legends:
            y -= 20
            if y < 140:
                pdf.new_page()
                y = pdf.height - 50
            pdf.draw_text(f"7. Leyendas de Símbolos Técnicos ({len(legends)} identificadas)", 40, y, font_size=12, font="Helvetica-Bold")
            y -= 14
            headers_leg = ["Título / Cuadro", "Lámina", "Dimensiones", "Clasificación"]
            col_widths_leg = [160, 100, 70, 200]
            rows_leg = [
                [l.get("title") or "Leyenda", l.get("sheet_name") or "-", l.get("dimensions") or "-", "Tabla identificada como leyenda de símbolos"]
                for l in legends
            ]
            y = pdf.draw_table(headers_leg, rows_leg, col_widths_leg, start_y=y, font_size=7.5)

        # =====================================================================
        # Sección 8: Notas Técnicas y Referencias Vinculadas (Capa 6)
        # =====================================================================
        notes = run_data.get("technical_notes", [])
        if notes:
            y -= 20
            if y < 140:
                pdf.new_page()
                y = pdf.height - 50
            pdf.draw_text(f"8. Notas Técnicas y Referencias Vinculadas ({len(notes)} notas)", 40, y, font_size=12, font="Helvetica-Bold")
            y -= 14
            for n in notes[:15]:
                for nl in SimplePdfCanvas.wrap_text(f"[{n.get('sheet_name')}] {n.get('text')}", max_chars_per_line=95):
                    pdf.draw_text(nl, 45, y, font_size=8, color=(0.15, 0.2, 0.25))
                    y -= 11
                    if y < 70:
                        pdf.new_page()
                        y = pdf.height - 50
                y -= 2

        # =====================================================================
        # Sección 9: Metadatos del Cajetín y Registro de Revisiones (Capa 7)
        # =====================================================================
        title_blocks = run_data.get("title_blocks", [])
        if title_blocks:
            y -= 20
            if y < 140:
                pdf.new_page()
                y = pdf.height - 50
            pdf.draw_text("9. Metadatos del Cajetín y Registro de Revisiones", 40, y, font_size=12, font="Helvetica-Bold")
            y -= 14
            headers_tb = ["Lámina / Código", "Título del Plano", "Rev.", "Escala", "Especialidad", "Fecha"]
            col_widths_tb = [90, 190, 40, 60, 80, 70]
            rows_tb = [
                [tb.get("sheet_code") or "-", tb.get("sheet_title") or "-", tb.get("revision") or "-", tb.get("scale_text") or "-", tb.get("discipline") or "-", tb.get("date_text") or "-"]
                for tb in title_blocks
            ]
            y = pdf.draw_table(headers_tb, rows_tb, col_widths_tb, start_y=y, font_size=7.5)

        with open(output_path, "wb") as out_f:
            out_f.write(pdf.build_pdf_bytes())

    @classmethod
    def get_report(cls, db: Session, report_id: str) -> Optional[ReviewReport]:
        return db.query(ReviewReport).filter(ReviewReport.id == report_id).first()

    @classmethod
    def get_report_file(cls, db: Session, report_id: str) -> Tuple[str, str, str]:
        report = cls.get_report(db, report_id)
        if not report:
            raise ValueError(f"Reporte '{report_id}' no encontrado.")

        if not os.path.exists(report.artifact_path):
            raise FileNotFoundError(f"Archivo de reporte físico no existe en '{report.artifact_path}'.")

        media_types = {
            "json": "application/json",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "pdf": "application/pdf"
        }
        media_type = media_types.get(report.format, "application/octet-stream")
        filename = os.path.basename(report.artifact_path)
        return report.artifact_path, filename, media_type
