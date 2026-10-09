import os
import textwrap
from typing import List, Dict, Any, Optional
from app.services.reporting.contracts import AuditReportData

class SimplePdfCanvas:
    """Generador vectorial estándar PDF 1.4 sin dependencias externas binarias."""

    def __init__(self, width: float = 595.28, height: float = 841.89): # A4 en puntos
        self.width = width
        self.height = height
        self.pages: List[str] = []
        self.current_page_commands: List[str] = []

    def new_page(self):
        if self.current_page_commands:
            self.pages.append("\n".join(self.current_page_commands))
            self.current_page_commands = []
        # Margen y fondo por defecto
        self._draw_page_decorations()

    def _draw_page_decorations(self):
        # Barra superior azul oscuro (primary)
        self.draw_rect(0, self.height - 24, self.width, 24, fill_color=(0.06, 0.09, 0.16))
        # Línea de pie de página
        self.draw_line(40, 35, self.width - 40, 35, stroke_color=(0.8, 0.85, 0.9), line_width=0.75)
        # Texto pie de página
        self.draw_text("Plan Review AI Hybrid • Technical QA/QC Audit Report • Hash-Based Integrity", 40, 22, font_size=8, font="Helvetica", color=(0.4, 0.45, 0.5))

    def draw_text(
        self,
        text: str,
        x: float,
        y: float,
        font_size: float = 10,
        font: str = "Helvetica",
        color: tuple = (0.1, 0.15, 0.2)
    ):
        r, g, b = color
        replacements = {
            "•": "-",
            "→": "->",
            "—": "--",
            "–": "-",
            "“": '"',
            "”": '"',
            "‘": "'",
            "’": "'",
            "⚡": "[LIVE]",
            "📦": "[REV]",
            "…": "...",
        }
        sanitized = text or ""
        for k, v in replacements.items():
            sanitized = sanitized.replace(k, v)

        safe_text = (
            sanitized.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
            .encode("latin-1", "replace")
            .decode("latin-1")
        )
        font_alias = "/F2" if "Bold" in font else "/F1"
        cmd = f"q {r:.2f} {g:.2f} {b:.2f} rg BT {font_alias} {font_size:.1f} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm ({safe_text}) Tj ET Q"
        self.current_page_commands.append(cmd)

    @staticmethod
    def wrap_text(text: Optional[str], max_chars_per_line: int = 95) -> List[str]:
        """Divide un texto potencialmente largo en líneas de longitud máxima sin cortar palabras."""
        if not text:
            return []
        lines: List[str] = []
        for paragraph in str(text).splitlines():
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            wrapped = textwrap.wrap(paragraph, width=max_chars_per_line, break_long_words=True)
            if wrapped:
                lines.extend(wrapped)
            else:
                lines.append(paragraph)
        return lines

    def draw_line(
        self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        stroke_color: tuple = (0.7, 0.7, 0.7),
        line_width: float = 1.0
    ):
        r, g, b = stroke_color
        cmd = f"q {r:.2f} {g:.2f} {b:.2f} RG {line_width:.2f} w {x0:.2f} {y0:.2f} m {x1:.2f} {y1:.2f} l S Q"
        self.current_page_commands.append(cmd)

    def draw_rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        fill_color: Optional[tuple] = None,
        stroke_color: Optional[tuple] = None,
        line_width: float = 1.0
    ):
        ops = []
        if fill_color:
            r, g, b = fill_color
            ops.append(f"{r:.2f} {g:.2f} {b:.2f} rg")
        if stroke_color:
            r, g, b = stroke_color
            ops.append(f"{r:.2f} {g:.2f} {b:.2f} RG {line_width:.2f} w")
        
        ops.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re")
        if fill_color and stroke_color:
            ops.append("B")
        elif fill_color:
            ops.append("f")
        else:
            ops.append("S")
        
        self.current_page_commands.append(f"q {' '.join(ops)} Q")

    def build_pdf_bytes(self) -> bytes:
        if self.current_page_commands:
            self.pages.append("\n".join(self.current_page_commands))
            self.current_page_commands = []

        total_pages = len(self.pages)
        objects = []
        offsets = []

        # Header PDF
        body = bytearray(b"%PDF-1.4\n")

        # Object 1: Catalog
        offsets.append(len(body))
        body.extend(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

        # Object 2: Pages (Kids)
        offsets.append(len(body))
        kids_refs = " ".join([f"{3 + i*2} 0 R" for i in range(total_pages)])
        pages_obj = f"2 0 obj\n<< /Type /Pages /Kids [{kids_refs}] /Count {total_pages} >>\nendobj\n"
        body.extend(pages_obj.encode("latin-1"))

        # Objects for each page (Page Obj + Stream Obj)
        for i, page_content in enumerate(self.pages):
            page_obj_id = 3 + i * 2
            stream_obj_id = 4 + i * 2

            # Page Object
            offsets.append(len(body))
            page_dict = (
                f"{page_obj_id} 0 obj\n"
                f"<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 {self.width} {self.height}] "
                f"/Contents {stream_obj_id} 0 R "
                f"/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >> "
                f"/F2 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >> >> >> >>\n"
                f"endobj\n"
            )
            body.extend(page_dict.encode("latin-1"))

            # Stream Object
            stream_bytes = page_content.encode("latin-1")
            offsets.append(len(body))
            stream_dict = (
                f"{stream_obj_id} 0 obj\n"
                f"<< /Length {len(stream_bytes)} >>\n"
                f"stream\n"
            )
            body.extend(stream_dict.encode("latin-1"))
            body.extend(stream_bytes)
            body.extend(b"\nendstream\nendobj\n")

        # XREF table
        xref_offset = len(body)
        total_objects = 1 + len(offsets)
        body.extend(f"xref\n0 {total_objects}\n0000000000 65535 f \n".encode("latin-1"))
        for off in offsets:
            body.extend(f"{off:010d} 00000 n \n".encode("latin-1"))

        # Trailer
        trailer = (
            f"trailer\n"
            f"<< /Size {total_objects} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        )
        body.extend(trailer.encode("latin-1"))
        return bytes(body)


class TechnicalAuditPdfRenderer:
    """Renderizador de informes técnicos ejecutivos y detallados de auditoría QA/QC."""

    @classmethod
    def render_pdf(cls, data: AuditReportData, output_file_path: str) -> str:
        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
        canvas = SimplePdfCanvas()

        # =========================================================================
        # PÁGINA 1: PORTADA Y RESUMEN EJECUTIVO
        # =========================================================================
        canvas.new_page()

        # Encabezado Principal
        canvas.draw_rect(40, 720, 515, 80, fill_color=(0.96, 0.97, 0.99), stroke_color=(0.85, 0.89, 0.95))
        canvas.draw_text("PLAN REVIEW AI HYBRID • INFORME TÉCNICO DE AUDITORÍA QA/QC", 55, 775, font_size=11, font="Helvetica-Bold", color=(0.2, 0.5, 0.8))
        canvas.draw_text(f"Auditoría Técnica: {data.sheet_code or data.document_filename}", 55, 750, font_size=18, font="Helvetica-Bold", color=(0.06, 0.09, 0.16))
        canvas.draw_text(f"Alcance: {data.report_scope.upper()} • Tipo: {data.report_type} • Fecha UTC: {data.generated_at_utc}", 55, 732, font_size=9, font="Helvetica", color=(0.4, 0.45, 0.5))

        # Metadatos del Documento Auditado
        canvas.draw_rect(40, 610, 515, 95, fill_color=(1.0, 1.0, 1.0), stroke_color=(0.88, 0.9, 0.94))
        canvas.draw_text("1. METADATOS DEL DOCUMENTO & VIÑETA", 55, 688, font_size=11, font="Helvetica-Bold", color=(0.06, 0.09, 0.16))
        canvas.draw_text(f"Archivo Origen: {data.document_filename} (ID: {data.document_id[:8]}...)", 55, 670, font_size=9, font="Helvetica")
        canvas.draw_text(f"Código Lámina: {data.sheet_code or 'N/A'} • Título: {data.sheet_title or 'Plano Técnico'}", 55, 654, font_size=9, font="Helvetica")
        canvas.draw_text(f"Escala Declarada: {data.scale_text or 'N/A'} • Revisión: {data.revision or '0'} • Disciplina: {(data.discipline or 'general').upper()}", 55, 638, font_size=9, font="Helvetica")
        canvas.draw_text(f"Generado por: {data.generated_by} • Versión Motor: {data.engine_version}", 55, 622, font_size=9, font="Helvetica", color=(0.4, 0.45, 0.5))

        # Métricas de Resumen Ejecutivo (Badges de Severidad)
        canvas.draw_rect(40, 480, 515, 115, fill_color=(0.98, 0.98, 0.99), stroke_color=(0.88, 0.9, 0.94))
        canvas.draw_text("2. RESUMEN EJECUTIVO DE HALLAZGOS", 55, 575, font_size=11, font="Helvetica-Bold", color=(0.06, 0.09, 0.16))
        
        crit = data.by_severity.get("critical", 0)
        high = data.by_severity.get("high", 0)
        med = data.by_severity.get("medium", 0)
        low = data.by_severity.get("low", 0)
        
        # Tarjeta Critical
        canvas.draw_rect(55, 500, 110, 60, fill_color=(0.99, 0.92, 0.92), stroke_color=(0.95, 0.4, 0.4))
        canvas.draw_text("CRÍTICO", 65, 545, font_size=9, font="Helvetica-Bold", color=(0.8, 0.1, 0.1))
        canvas.draw_text(str(crit), 65, 515, font_size=22, font="Helvetica-Bold", color=(0.8, 0.1, 0.1))

        # Tarjeta High
        canvas.draw_rect(175, 500, 110, 60, fill_color=(1.0, 0.96, 0.9), stroke_color=(0.95, 0.6, 0.2))
        canvas.draw_text("ALTO", 185, 545, font_size=9, font="Helvetica-Bold", color=(0.85, 0.4, 0.0))
        canvas.draw_text(str(high), 185, 515, font_size=22, font="Helvetica-Bold", color=(0.85, 0.4, 0.0))

        # Tarjeta Medium
        canvas.draw_rect(295, 500, 110, 60, fill_color=(0.92, 0.96, 1.0), stroke_color=(0.3, 0.6, 0.95))
        canvas.draw_text("MEDIO", 305, 545, font_size=9, font="Helvetica-Bold", color=(0.1, 0.4, 0.8))
        canvas.draw_text(str(med), 305, 515, font_size=22, font="Helvetica-Bold", color=(0.1, 0.4, 0.8))

        # Tarjeta Total
        canvas.draw_rect(415, 500, 125, 60, fill_color=(0.94, 0.95, 0.97), stroke_color=(0.6, 0.65, 0.75))
        canvas.draw_text("TOTAL HALLAZGOS", 425, 545, font_size=8, font="Helvetica-Bold", color=(0.2, 0.25, 0.3))
        canvas.draw_text(str(data.total_findings), 425, 515, font_size=22, font="Helvetica-Bold", color=(0.1, 0.15, 0.2))

        # Tabla de Reglas Evaluadas
        canvas.draw_rect(40, 200, 515, 265, fill_color=(1.0, 1.0, 1.0), stroke_color=(0.88, 0.9, 0.94))
        canvas.draw_text("3. REGLAS DETERMINÍSTICAS EVALUADAS", 55, 445, font_size=11, font="Helvetica-Bold", color=(0.06, 0.09, 0.16))
        
        y_tbl = 425
        canvas.draw_text("Código Regla", 55, y_tbl, font_size=8, font="Helvetica-Bold", color=(0.4, 0.45, 0.5))
        canvas.draw_text("Nombre / Descripción", 190, y_tbl, font_size=8, font="Helvetica-Bold", color=(0.4, 0.45, 0.5))
        canvas.draw_text("Disciplina", 450, y_tbl, font_size=8, font="Helvetica-Bold", color=(0.4, 0.45, 0.5))
        canvas.draw_text("Sev.", 510, y_tbl, font_size=8, font="Helvetica-Bold", color=(0.4, 0.45, 0.5))
        canvas.draw_line(55, y_tbl - 4, 540, y_tbl - 4, stroke_color=(0.8, 0.85, 0.9))

        for r_item in data.rules_evaluated[:7]:
            y_tbl -= 26
            canvas.draw_text(r_item.get("code", "")[:22], 55, y_tbl, font_size=8, font="Helvetica-Bold", color=(0.2, 0.4, 0.8))
            canvas.draw_text(r_item.get("name", "")[:45], 190, y_tbl, font_size=8, font="Helvetica")
            canvas.draw_text(r_item.get("discipline", "")[:12], 450, y_tbl, font_size=8, font="Helvetica")
            canvas.draw_text(r_item.get("severity_default", "")[:4].upper(), 510, y_tbl, font_size=8, font="Helvetica-Bold", color=(0.8, 0.3, 0.1))

        # Nota de Certificación e Integridad
        canvas.draw_rect(40, 55, 515, 130, fill_color=(0.96, 0.98, 0.96), stroke_color=(0.6, 0.85, 0.6))
        canvas.draw_text("4. TRAZABILIDAD & DECLARACIÓN DE INTEGRIDAD", 55, 165, font_size=10, font="Helvetica-Bold", color=(0.1, 0.5, 0.2))
        canvas.draw_text("• Este informe fue generado por el motor híbrido determinístico Plan Review AI Hybrid.", 55, 148, font_size=8, font="Helvetica")
        canvas.draw_text("• Toda discrepancia incluye evidencia relacional indexada en el paquete de evidencias.", 55, 134, font_size=8, font="Helvetica")
        canvas.draw_text("• Las resoluciones humanas asociadas quedan vinculadas con sello de tiempo inmutable.", 55, 120, font_size=8, font="Helvetica")
        canvas.draw_text(f"• ID Único de Reporte: {data.report_id}", 55, 102, font_size=8, font="Helvetica-Bold", color=(0.15, 0.3, 0.2))
        canvas.draw_text(f"• Hash de Integridad Manifiesto: {data.report_id[:16]}... (ver manifest.json)", 55, 88, font_size=8, font="Helvetica", color=(0.3, 0.4, 0.3))

        # =========================================================================
        # PÁGINAS SIGUIENTES: DETALLE DE HALLAZGOS Y EVIDENCIAS
        # =========================================================================
        if data.findings:
            canvas.new_page()
            canvas.draw_text("5. DETALLE DE HALLAZGOS AUDITADOS", 40, 785, font_size=14, font="Helvetica-Bold", color=(0.06, 0.09, 0.16))
            canvas.draw_line(40, 775, 555, 775, stroke_color=(0.8, 0.85, 0.9), line_width=1.0)

            y_f = 750
            for idx, f in enumerate(data.findings):
                # Si nos quedamos sin espacio vertical, abrir nueva página
                if y_f < 220:
                    canvas.new_page()
                    canvas.draw_text("5. DETALLE DE HALLAZGOS AUDITADOS (CONT.)", 40, 785, font_size=14, font="Helvetica-Bold", color=(0.06, 0.09, 0.16))
                    canvas.draw_line(40, 775, 555, 775, stroke_color=(0.8, 0.85, 0.9), line_width=1.0)
                    y_f = 750

                box_height = 145
                border_col = (0.85, 0.2, 0.2) if f.severity in ["critical", "high"] else (0.2, 0.5, 0.8)
                bg_col = (1.0, 0.98, 0.98) if f.severity in ["critical", "high"] else (0.98, 0.99, 1.0)

                canvas.draw_rect(40, y_f - box_height, 515, box_height, fill_color=bg_col, stroke_color=border_col)
                
                # Header del Finding Card
                canvas.draw_text(f"Hallazgo #{idx+1}: {f.title[:65]}", 55, y_f - 18, font_size=11, font="Helvetica-Bold", color=(0.06, 0.09, 0.16))
                canvas.draw_text(f"Severidad: {f.severity.upper()}  |  Estado: {f.status.upper()}  |  Regla: {f.rule_code}", 55, y_f - 32, font_size=8, font="Helvetica-Bold", color=border_col)

                # Descripción
                canvas.draw_text(f"Descripción: {f.description[:95]}", 55, y_f - 50, font_size=8, font="Helvetica")
                if len(f.description) > 95:
                    canvas.draw_text(f.description[95:190], 55, y_f - 62, font_size=8, font="Helvetica")

                # Valores cuantitativos (Esperado vs Observado vs Delta)
                if f.expected_value is not None or f.observed_value is not None:
                    canvas.draw_text(f"Esperado: {f.expected_value}  |  Observado: {f.observed_value}  |  Delta: {f.delta}", 55, y_f - 78, font_size=8, font="Helvetica-Bold", color=(0.2, 0.3, 0.4))

                # Recomendación
                if f.recommendation:
                    canvas.draw_text(f"Recomendación: {f.recommendation[:90]}", 55, y_f - 94, font_size=8, font="Helvetica", color=(0.1, 0.4, 0.6))

                # Resoluciones humanas si existen
                if f.resolutions:
                    latest_res = f.resolutions[-1]
                    canvas.draw_text(f"Resolución Humana: {latest_res.get('resolution_type', '').upper()} por {latest_res.get('resolved_by', '')}", 55, y_f - 110, font_size=8, font="Helvetica-Bold", color=(0.1, 0.5, 0.2))
                    if latest_res.get("notes"):
                        canvas.draw_text(f"Dictamen: {latest_res['notes'][:80]}", 55, y_f - 122, font_size=7, font="Helvetica")

                # ID del finding
                canvas.draw_text(f"UUID: {f.id}", 55, y_f - 136, font_size=7, font="Helvetica", color=(0.5, 0.55, 0.6))

                y_f -= (box_height + 15)

        pdf_bytes = canvas.build_pdf_bytes()
        with open(output_file_path, "wb") as f_out:
            f_out.write(pdf_bytes)

        return output_file_path
