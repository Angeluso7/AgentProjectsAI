import os
from typing import Dict, Any, List
from app.services.reporting.pdf_renderer import SimplePdfCanvas

class ConsolidatedStagePdfRenderer:
    """Renderizador PDF multi-página para el Reporte Consolidado Final por Etapa."""

    @classmethod
    def render_report(cls, data: Dict[str, Any], output_path: str) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        canvas = SimplePdfCanvas()

        # ==========================================
        # PÁGINA 1: PORTADA & VEREDICTO GLOBAL
        # ==========================================
        canvas.new_page()

        # Título y Header
        canvas.draw_text("PLAN REVIEW AI HYBRID — INFORME CONSOLIDADO POR ETAPA", 40, 780, font_size=15, font="Helvetica-Bold", color=(0.08, 0.12, 0.22))
        canvas.draw_line(40, 770, 555, 770, stroke_color=(0.3, 0.4, 0.6), line_width=1.5)

        # Contexto del Proyecto
        canvas.draw_rect(40, 680, 515, 80, fill_color=(0.95, 0.97, 1.0), stroke_color=(0.7, 0.8, 0.9))
        canvas.draw_text(f"PROYECTO: {data.get('project_name', 'N/A')} ({data.get('project_code', 'N/A')})", 55, 740, font_size=11, font="Helvetica-Bold", color=(0.1, 0.2, 0.35))
        canvas.draw_text(f"ETAPA DE AUDITORÍA: {data.get('stage', 'N/A')}", 55, 722, font_size=10, font="Helvetica-Bold", color=(0.2, 0.3, 0.4))
        canvas.draw_text(f"REVISIÓN / EMISIÓN: Rev {data.get('revision_number', 1)}  •  EMITIDO POR: {data.get('issued_by', 'Auditor Lead')}", 55, 704, font_size=9, font="Helvetica", color=(0.35, 0.4, 0.45))
        canvas.draw_text(f"FECHA UTC: {data.get('issued_at', '')[:19] if data.get('issued_at') else 'N/A'}", 55, 690, font_size=8, font="Helvetica", color=(0.4, 0.45, 0.5))

        # Veredicto Global de la Etapa
        verdict = data.get("global_stage_verdict", "parcial_incompleta")
        rationale = data.get("verdict_rationale", "")
        
        v_colors = {
            "aprobable": ((0.88, 0.98, 0.92), (0.15, 0.6, 0.35), "ETAPA APROBABLE"),
            "aprobable_con_observaciones": ((1.0, 0.97, 0.88), (0.75, 0.5, 0.1), "ETAPA APROBABLE CON OBSERVACIONES"),
            "parcial_incompleta": ((0.94, 0.93, 1.0), (0.45, 0.3, 0.8), "ETAPA PARCIAL / EN REVISIÓN"),
            "no_aprobable_bloqueada": ((1.0, 0.9, 0.9), (0.8, 0.2, 0.2), "ETAPA NO APROBABLE / BLOQUEADA")
        }
        bg_col, border_col, v_title = v_colors.get(verdict, ((0.95, 0.95, 0.95), (0.5, 0.5, 0.5), verdict.upper()))

        canvas.draw_rect(40, 595, 515, 70, fill_color=bg_col, stroke_color=border_col, line_width=1.5)
        canvas.draw_text("ESTADO GLOBAL DE LA REVISIÓN:", 55, 645, font_size=9, font="Helvetica-Bold", color=border_col)
        canvas.draw_text(v_title, 55, 627, font_size=13, font="Helvetica-Bold", color=border_col)
        canvas.draw_text(rationale[:140] + ("..." if len(rationale) > 140 else ""), 55, 607, font_size=8.5, font="Helvetica", color=(0.2, 0.25, 0.3))

        # Cuadros KPI Resumen
        comp = data.get("completeness", {})
        verd = data.get("audit_verdicts", {})
        obs = data.get("observations", {})

        # KPI 1: Completitud
        canvas.draw_rect(40, 485, 165, 95, fill_color=(0.96, 0.98, 0.96), stroke_color=(0.8, 0.88, 0.8))
        canvas.draw_text("COMPLETITUD", 50, 560, font_size=8.5, font="Helvetica-Bold", color=(0.2, 0.4, 0.25))
        canvas.draw_text(f"{comp.get('completeness_percentage', 0.0):.1f}%", 50, 535, font_size=18, font="Helvetica-Bold", color=(0.15, 0.55, 0.3))
        canvas.draw_text(f"Gatekeeper: {'APROBADO' if comp.get('is_gate_passed') else 'BLOQUEADO'}", 50, 515, font_size=8, font="Helvetica", color=(0.3, 0.4, 0.3))
        canvas.draw_text(f"Bloqueos Activos: {comp.get('blocked_rules_count', 0)}", 50, 498, font_size=8, font="Helvetica", color=(0.7, 0.2, 0.2))

        # KPI 2: Auditoría QA/QC (4 Veredictos)
        canvas.draw_rect(215, 485, 165, 95, fill_color=(0.96, 0.97, 1.0), stroke_color=(0.8, 0.85, 0.95))
        canvas.draw_text("4 VEREDICTOS QA/QC", 225, 560, font_size=8.5, font="Helvetica-Bold", color=(0.15, 0.25, 0.45))
        canvas.draw_text(f"{verd.get('total_rules_evaluated', 0)} Reglas", 225, 538, font_size=13, font="Helvetica-Bold", color=(0.1, 0.2, 0.4))
        canvas.draw_text(f"CUMPLE: {verd.get('cumple_count', 0)}  •  NO CUMPLE: {verd.get('no_cumple_count', 0)}", 225, 515, font_size=8, font="Helvetica", color=(0.2, 0.3, 0.4))
        canvas.draw_text(f"NO VERIFICABLE: {verd.get('no_verificable_count', 0)}  •  N/A: {verd.get('no_aplica_count', 0)}", 225, 498, font_size=8, font="Helvetica", color=(0.4, 0.3, 0.6))

        # KPI 3: Observaciones & RFIs
        canvas.draw_rect(390, 485, 165, 95, fill_color=(1.0, 0.97, 0.95), stroke_color=(0.95, 0.85, 0.8))
        canvas.draw_text("OBSERVACIONES & RFIs", 400, 560, font_size=8.5, font="Helvetica-Bold", color=(0.5, 0.25, 0.1))
        canvas.draw_text(f"Abiertas: {obs.get('open_obs', 0) + obs.get('open_rfi', 0) + obs.get('active_blk', 0)}", 400, 538, font_size=13, font="Helvetica-Bold", color=(0.75, 0.3, 0.1))
        canvas.draw_text(f"OBS: {obs.get('total_obs', 0)} (Crit/Alt: {obs.get('critical_obs', 0) + obs.get('high_obs', 0)})", 400, 515, font_size=8, font="Helvetica", color=(0.3, 0.3, 0.3))
        canvas.draw_text(f"RFIs: {obs.get('total_rfi', 0)}  •  Bloqueos: {obs.get('total_blk', 0)}", 400, 498, font_size=8, font="Helvetica", color=(0.4, 0.4, 0.4))

        # Evolución Delta Preview en Portada
        delta = data.get("delta_evolution", {})
        canvas.draw_rect(40, 390, 515, 75, fill_color=(0.98, 0.98, 0.98), stroke_color=(0.85, 0.85, 0.85))
        canvas.draw_text("EVOLUCIÓN INCREMENTAL / DELTA RESPECTO A REVISIÓN PREVIA:", 55, 445, font_size=9, font="Helvetica-Bold", color=(0.2, 0.25, 0.3))
        canvas.draw_text(delta.get("summary_narrative", "Sin datos comparativos."), 55, 428, font_size=8.5, font="Helvetica", color=(0.25, 0.3, 0.35))
        canvas.draw_text(f"Hallazgos Resueltos: {len(delta.get('resolved_since_last_rev', []))}   •   Nuevas Observaciones: {len(delta.get('new_since_last_rev', []))}   •   Reglas Desbloqueadas: {len(delta.get('unblocked_rules_since_last_rev', []))}", 55, 408, font_size=8, font="Helvetica", color=(0.15, 0.45, 0.25))

        # Footer Portada
        canvas.draw_text("Plan Review AI Hybrid • Sistema Integrado de Auditoría Técnica y Control Documental", 40, 60, font_size=8, font="Helvetica", color=(0.5, 0.5, 0.5))

        # ==========================================
        # PÁGINA 2: COMPLETITUD DOCUMENTAL & ENTREGABLES
        # ==========================================
        canvas.new_page()
        canvas.draw_text("1. MATRIZ DE COMPLETITUD DOCUMENTAL & GATEKEEPER", 40, 780, font_size=13, font="Helvetica-Bold", color=(0.08, 0.12, 0.22))
        canvas.draw_line(40, 770, 555, 770, stroke_color=(0.3, 0.4, 0.6), line_width=1.0)

        matrix = comp.get("deliverables_matrix", [])
        y = 740
        canvas.draw_rect(40, y, 515, 20, fill_color=(0.15, 0.2, 0.3))
        canvas.draw_text("ENTREGABLE REQUERIDO", 45, y + 6, font_size=8, font="Helvetica-Bold", color=(1.0, 1.0, 1.0))
        canvas.draw_text("TIPO", 240, y + 6, font_size=8, font="Helvetica-Bold", color=(1.0, 1.0, 1.0))
        canvas.draw_text("CARÁCTER", 340, y + 6, font_size=8, font="Helvetica-Bold", color=(1.0, 1.0, 1.0))
        canvas.draw_text("ESTADO EVIDENCIA", 440, y + 6, font_size=8, font="Helvetica-Bold", color=(1.0, 1.0, 1.0))
        y -= 18

        for d in matrix[:15]:
            is_m = d.get("is_mandatory", False)
            canvas.draw_rect(40, y, 515, 18, fill_color=(0.97, 0.97, 0.98) if y % 36 == 0 else (1.0, 1.0, 1.0), stroke_color=(0.9, 0.9, 0.9), line_width=0.5)
            canvas.draw_text(d.get("title", "")[:35], 45, y + 5, font_size=7.5, font="Helvetica", color=(0.1, 0.15, 0.2))
            canvas.draw_text(d.get("deliverable_type", "")[:18], 240, y + 5, font_size=7.5, font="Helvetica", color=(0.3, 0.3, 0.3))
            canvas.draw_text("Obligatorio" if is_m else "Opcional", 340, y + 5, font_size=7.5, font="Helvetica-Bold" if is_m else "Helvetica", color=(0.7, 0.1, 0.1) if is_m else (0.4, 0.4, 0.4))
            status_text = d.get("readiness_status", "missing")
            canvas.draw_text(status_text.upper(), 440, y + 5, font_size=7.5, font="Helvetica-Bold", color=(0.1, 0.55, 0.2) if status_text == "eligible_as_evidence" else (0.8, 0.3, 0.1))
            y -= 18

        # Bloqueos y Reglas Afectadas
        y -= 15
        canvas.draw_text("REGLAS TÉCNICAS BLOQUEADAS PREVENTIVAMENTE:", 40, y, font_size=10, font="Helvetica-Bold", color=(0.7, 0.15, 0.15))
        y -= 15
        blocked_rules = comp.get("blocked_rules", [])
        if blocked_rules:
            for b in blocked_rules[:6]:
                canvas.draw_text(f"• Regla {b.get('rule_code', '')}: Bloqueada por falta de {b.get('deliverable_title', '')}", 50, y, font_size=8, font="Helvetica", color=(0.3, 0.3, 0.3))
                y -= 12
        else:
            canvas.draw_text("No existen reglas bloqueadas. Todos los entregables obligatorios han sido provisionados.", 50, y, font_size=8, font="Helvetica", color=(0.15, 0.5, 0.2))

        # ==========================================
        # PÁGINA 3: AUDITORÍA QA/QC & OBSERVACIONES
        # ==========================================
        canvas.new_page()
        canvas.draw_text("2. AUDITORÍA TÉCNICA Y TABLA DE OBSERVACIONES & RFIs", 40, 780, font_size=13, font="Helvetica-Bold", color=(0.08, 0.12, 0.22))
        canvas.draw_line(40, 770, 555, 770, stroke_color=(0.3, 0.4, 0.6), line_width=1.0)

        # Tabla de Observaciones
        obs_items = obs.get("items", [])
        y = 740
        canvas.draw_rect(40, y, 515, 20, fill_color=(0.15, 0.2, 0.3))
        canvas.draw_text("CÓDIGO", 45, y + 6, font_size=8, font="Helvetica-Bold", color=(1.0, 1.0, 1.0))
        canvas.draw_text("TIPO", 115, y + 6, font_size=8, font="Helvetica-Bold", color=(1.0, 1.0, 1.0))
        canvas.draw_text("TÍTULO / DESCRIPCIÓN", 165, y + 6, font_size=8, font="Helvetica-Bold", color=(1.0, 1.0, 1.0))
        canvas.draw_text("SEV", 380, y + 6, font_size=8, font="Helvetica-Bold", color=(1.0, 1.0, 1.0))
        canvas.draw_text("ESTADO", 440, y + 6, font_size=8, font="Helvetica-Bold", color=(1.0, 1.0, 1.0))
        y -= 18

        if obs_items:
            for item in obs_items[:22]:
                canvas.draw_rect(40, y, 515, 18, fill_color=(0.97, 0.97, 0.98) if y % 36 == 0 else (1.0, 1.0, 1.0), stroke_color=(0.9, 0.9, 0.9), line_width=0.5)
                canvas.draw_text(item.get("code", "")[:12], 45, y + 5, font_size=7.5, font="Helvetica-Bold", color=(0.1, 0.2, 0.4))
                canvas.draw_text(item.get("item_type", "")[:10], 115, y + 5, font_size=7, font="Helvetica", color=(0.3, 0.3, 0.3))
                canvas.draw_text(item.get("title", "")[:45], 165, y + 5, font_size=7.5, font="Helvetica", color=(0.1, 0.1, 0.1))
                canvas.draw_text(item.get("severity", "")[:4].upper(), 380, y + 5, font_size=7, font="Helvetica", color=(0.7, 0.2, 0.1))
                canvas.draw_text(item.get("status", "").upper(), 440, y + 5, font_size=7.5, font="Helvetica-Bold", color=(0.15, 0.5, 0.2) if item.get("status") in ["closed", "validated"] else (0.8, 0.4, 0.1))
                y -= 18
        else:
            canvas.draw_text("No hay observaciones ni RFIs emitidos.", 45, y - 10, font_size=8, font="Helvetica", color=(0.4, 0.4, 0.4))

        # ==========================================
        # PÁGINA 4: EVOLUCIÓN DELTA & FIRMAS
        # ==========================================
        canvas.new_page()
        canvas.draw_text("3. REGISTRO DE EVOLUCIÓN INCREMENTAL & TRAZABILIDAD", 40, 780, font_size=13, font="Helvetica-Bold", color=(0.08, 0.12, 0.22))
        canvas.draw_line(40, 770, 555, 770, stroke_color=(0.3, 0.4, 0.6), line_width=1.0)

        canvas.draw_text("CAMBIOS REGISTRADOS RESPECTO A LA REVISIÓN PREVIA:", 40, 745, font_size=10, font="Helvetica-Bold", color=(0.15, 0.25, 0.4))
        
        y = 720
        status_changes = delta.get("status_changes", [])
        if status_changes:
            for sc in status_changes[:15]:
                canvas.draw_text(f"• [{sc.get('code', '')}] {sc.get('from', '')} → {sc.get('to', '')}: {sc.get('notes', '')[:80]}", 50, y, font_size=8, font="Helvetica", color=(0.2, 0.2, 0.2))
                y -= 15
        else:
            canvas.draw_text("No se registran cambios de estado o es la primera versión consolidada de esta etapa.", 50, y, font_size=8.5, font="Helvetica", color=(0.4, 0.4, 0.4))
            y -= 25

        # Bloque de Integridad y Hash SHA-256
        y = 200
        canvas.draw_rect(40, y, 515, 90, fill_color=(0.95, 0.97, 1.0), stroke_color=(0.7, 0.8, 0.9))
        canvas.draw_text("INTEGRIDAD DIGITAL Y MANIFIESTO SHA-256", 55, y + 68, font_size=9.5, font="Helvetica-Bold", color=(0.1, 0.2, 0.35))
        canvas.draw_text(f"Hash del Reporte (SHA-256): {data.get('manifest_hash', 'PENDING_ON_EMIT')}", 55, y + 48, font_size=7.5, font="Helvetica", color=(0.3, 0.35, 0.4))
        canvas.draw_text(f"Emitido formalmente en plataforma Plan Review AI Hybrid para el proyecto {data.get('project_code', '')}.", 55, y + 30, font_size=8, font="Helvetica", color=(0.3, 0.35, 0.4))
        canvas.draw_text(f"Auditor Responsable: {data.get('issued_by', 'Auditor Lead')}   •   Fecha: {data.get('issued_at', '')[:19] if data.get('issued_at') else ''}", 55, y + 15, font_size=8, font="Helvetica-Bold", color=(0.15, 0.2, 0.3))

        # Escribir archivo en disco
        pdf_bytes = canvas.build_pdf_bytes()
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

        return output_path
