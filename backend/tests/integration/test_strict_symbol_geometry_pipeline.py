import os
import io
import re
import uuid
import tempfile
import pytest
import fitz  # PyMuPDF
from PIL import Image
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.services.symbols.geometric_validator import (
    GeometricEvidenceValidator,
    CellGeometricEvaluation,
    ALPHANUMERIC_TOKEN_REGEX
)
from app.services.tables.extractor import (
    TableExtractor,
    ExtractedCellDTO,
    ExtractedTableDTO,
    ExtractedSymbolCandidateDTO
)
from app.services.symbols.legend_table_extractor import (
    LegendTableExtractor,
    ExtractedPipingSymbolDTO
)
from app.services.extraction.candidate_generator_service import CandidateGeneratorService
from app.db.models.intake_extractions import SourceExtraction, ExtractedItem, StructuredSymbol
from app.db.models.core import Organization, Project


# ==============================================================================
# HELPERS PARA GENERAR ESCENARIOS PDF
# ==============================================================================

def create_isa51_alphanumeric_table_pdf() -> tuple[bytes, dict]:
    """
    Tabla ISA 5.1 con combinaciones alfanuméricas puras (A, B, C, X, O, 1, 0).
    Debe producir CERO símbolos candidatos.
    """
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)

    col_x = [50, 150, 450, 750]
    row_y = [50, 90, 130, 170, 210, 250, 290, 330, 370]

    # Cuadrícula
    for y in row_y:
        page.draw_line(fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y), color=(0, 0, 0), width=1.0)
    for x in col_x:
        page.draw_line(fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]), color=(0, 0, 0), width=1.0)

    # Headers
    page.insert_text(fitz.Point(col_x[0] + 10, row_y[0] + 25), "LETRA", fontsize=10, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[1] + 10, row_y[0] + 25), "VARIABLE MEDIDA", fontsize=10, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[2] + 10, row_y[0] + 25), "MODIFICADOR / FUNCIÓN", fontsize=10, fontname="helv", color=(0, 0, 0))

    data = [
        ("A", "Análisis (Analysis)", "Alarma (Alarm)"),
        ("B", "Combustión (Burner, Combustion)", "Elección del Usuario"),
        ("C", "Conductividad (Conductivity)", "Controlador (Controller)"),
        ("X", "No clasificado (Unclassified)", "Especial"),
        ("O", "Libre (User Choice)", "Paso Abierto (Open)"),
        ("1", "Estado Binario Activo", "Interlock Lógico"),
        ("0", "Estado Binario Inactivo", "Reset de Seguridad")
    ]

    for i, (letra, var, func) in enumerate(data):
        r = i + 1
        cy = (row_y[r] + row_y[r + 1]) / 2
        # Col 0: Letra/número aislado (glifo tipográfico)
        page.insert_text(fitz.Point(col_x[0] + 35, cy + 4), letra, fontsize=12, fontname="helv", color=(0, 0, 0))
        page.insert_text(fitz.Point(col_x[1] + 15, cy + 4), var, fontsize=9, fontname="helv", color=(0, 0, 0))
        page.insert_text(fitz.Point(col_x[2] + 15, cy + 4), func, fontsize=9, fontname="helv", color=(0, 0, 0))

    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes, {
        "table_bbox_norm": [col_x[0] / 800.0, row_y[0] / 600.0, col_x[-1] / 800.0, row_y[-1] / 600.0],
        "rows": len(data)
    }


def create_pure_text_table_pdf() -> tuple[bytes, dict]:
    """
    Tabla documental de especificaciones puramente textual.
    Debe producir CERO símbolos candidatos.
    """
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)

    col_x = [60, 140, 480, 620, 740]
    row_y = [60, 100, 150, 200, 250]

    for y in row_y:
        page.draw_line(fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y), color=(0, 0, 0), width=1.0)
    for x in col_x:
        page.draw_line(fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]), color=(0, 0, 0), width=1.0)

    headers = ["ITEM", "DESCRIPCIÓN TÉCNICA", "CANTIDAD", "NORMA"]
    for i, h in enumerate(headers):
        page.insert_text(fitz.Point(col_x[i] + 10, row_y[0] + 25), h, fontsize=9, fontname="helv", color=(0, 0, 0))

    rows_data = [
        ("01", "Tubería Acero Carbono ASTM A-106 Gr. B 4 pulg Sch 40", "150 m", "ASME B31.3"),
        ("02", "Codo 90 LR ASTM A234 WPB Soldable B16.9", "24 un", "ASME B16.9"),
        ("03", "Brida Slip-On ASME B16.5 150# Acero Forjado", "12 un", "ASME B16.5")
    ]

    for i, rdata in enumerate(rows_data):
        r = i + 1
        cy = (row_y[r] + row_y[r + 1]) / 2
        for c_idx, val in enumerate(rdata):
            page.insert_text(fitz.Point(col_x[c_idx] + 10, cy + 4), val, fontsize=8, fontname="helv", color=(0, 0, 0))

    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes, {
        "table_bbox_norm": [col_x[0] / 800.0, row_y[0] / 600.0, col_x[-1] / 800.0, row_y[-1] / 600.0]
    }


def create_col0_short_codes_pdf() -> tuple[bytes, dict]:
    """
    Tabla donde la columna 0 contiene códigos breves ("V-01", "MAT-01", "P-101").
    Ninguno tiene geometría visual, por lo que NO deben promoverse a símbolos.
    """
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)

    col_x = [50, 160, 520, 750]
    row_y = [70, 110, 160, 210, 260]

    for y in row_y:
        page.draw_line(fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y), color=(0, 0, 0), width=1.0)
    for x in col_x:
        page.draw_line(fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]), color=(0, 0, 0), width=1.0)

    page.insert_text(fitz.Point(col_x[0] + 10, row_y[0] + 25), "TAG / CÓDIGO", fontsize=9, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[1] + 10, row_y[0] + 25), "ESPECIFICACIÓN", fontsize=9, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[2] + 10, row_y[0] + 25), "PROVEEDOR / MODELO", fontsize=9, fontname="helv", color=(0, 0, 0))

    items = [
        ("V-01", "Válvula Esférica 2 pulg Clase 150 Paso Total", "Flowserve Mod. B-10"),
        ("P-101", "Bomba Centrífuga de Alimentación 15 HP", "KSB Meganorm"),
        ("MAT-02", "Junta Espirometálica 4 pulg 150# Grafito", "Garlock Flexseal")
    ]

    for i, (tag, spec, prov) in enumerate(items):
        r = i + 1
        cy = (row_y[r] + row_y[r + 1]) / 2
        page.insert_text(fitz.Point(col_x[0] + 15, cy + 4), tag, fontsize=9, fontname="helv", color=(0, 0, 0))
        page.insert_text(fitz.Point(col_x[1] + 15, cy + 4), spec, fontsize=8, fontname="helv", color=(0, 0, 0))
        page.insert_text(fitz.Point(col_x[2] + 15, cy + 4), prov, fontsize=8, fontname="helv", color=(0, 0, 0))

    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes, {
        "table_bbox_norm": [col_x[0] / 800.0, row_y[0] / 600.0, col_x[-1] / 800.0, row_y[-1] / 600.0]
    }


def create_page_with_foreign_image_and_text_table_pdf() -> tuple[bytes, dict]:
    """
    Página con una imagen incrustada ajena (ej. logo/fotografía al pie)
    y una tabla puramente textual arriba.
    Debe verificar que la presencia de page.get_images() NO contamine las celdas textuales.
    """
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)

    # 1. Tabla de texto arriba
    col_x = [50, 180, 500, 750]
    row_y = [50, 90, 140, 190]
    for y in row_y:
        page.draw_line(fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y), color=(0, 0, 0), width=1.0)
    for x in col_x:
        page.draw_line(fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]), color=(0, 0, 0), width=1.0)

    page.insert_text(fitz.Point(col_x[0] + 10, row_y[0] + 25), "REF", fontsize=9, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[1] + 10, row_y[0] + 25), "DOCUMENTO", fontsize=9, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[2] + 10, row_y[0] + 25), "REVISIÓN", fontsize=9, fontname="helv", color=(0, 0, 0))

    page.insert_text(fitz.Point(col_x[0] + 15, 115), "DOC-01", fontsize=8, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[1] + 15, 115), "Diagrama P&ID General", fontsize=8, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[2] + 15, 115), "Rev. B", fontsize=8, fontname="helv", color=(0, 0, 0))

    page.insert_text(fitz.Point(col_x[0] + 15, 165), "DOC-02", fontsize=8, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[1] + 15, 165), "Listado de Líneas de Proceso", fontsize=8, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[2] + 15, 165), "Rev. 0", fontsize=8, fontname="helv", color=(0, 0, 0))

    # 2. Imagen ajena incrustada en la esquina inferior derecha (lejos de la tabla)
    dummy_img = Image.new("RGB", (120, 80), color=(180, 40, 40))
    img_byte_arr = io.BytesIO()
    dummy_img.save(img_byte_arr, format='PNG')
    img_bytes = img_byte_arr.getvalue()

    img_rect = fitz.Rect(580, 450, 750, 550)
    page.insert_image(img_rect, stream=img_bytes)

    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes, {
        "table_bbox_norm": [col_x[0] / 800.0, row_y[0] / 600.0, col_x[-1] / 800.0, row_y[-1] / 600.0]
    }


def create_vectorized_font_glyphs_pdf() -> tuple[bytes, dict]:
    """
    Tabla donde las letras han sido vectorizadas como pequeñas curvas/trazos Bézier
    (glifos tipográficos de altura <= 4.5 mm).
    Debe ser descartado por el filtro anti-glifos y dar 0 símbolos.
    """
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)

    col_x = [60, 200, 650]
    row_y = [80, 120, 170, 220]

    for y in row_y:
        page.draw_line(fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y), color=(0, 0, 0), width=1.0)
    for x in col_x:
        page.draw_line(fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]), color=(0, 0, 0), width=1.0)

    page.insert_text(fitz.Point(col_x[0] + 15, row_y[0] + 25), "TIPO", fontsize=9, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[1] + 15, row_y[0] + 25), "DESCRIPCIÓN", fontsize=9, fontname="helv", color=(0, 0, 0))

    # En la celda (Fila 1, Col 0), dibujar trazos vectoriales diminutos que simulan una letra "A" o "O"
    # Altura de ~3 mm = ~8.5 pt
    cy = (row_y[1] + row_y[2]) / 2
    cx = (col_x[0] + col_x[1]) / 2
    # Dibujar letra "A" vectorizada diminuta (altura 9 pt, ancho 7 pt)
    page.draw_line(fitz.Point(cx - 3.5, cy + 4.5), fitz.Point(cx, cy - 4.5), color=(0, 0, 0), width=0.8)
    page.draw_line(fitz.Point(cx + 3.5, cy + 4.5), fitz.Point(cx, cy - 4.5), color=(0, 0, 0), width=0.8)
    page.draw_line(fitz.Point(cx - 2.0, cy + 1.0), fitz.Point(cx + 2.0, cy + 1.0), color=(0, 0, 0), width=0.8)
    page.insert_text(fitz.Point(col_x[1] + 15, cy + 4), "Línea de Proceso Principal", fontsize=9, fontname="helv", color=(0, 0, 0))

    # En la celda (Fila 2, Col 0), dibujar letra "O" vectorizada diminuta (diámetro 8 pt = 2.8 mm)
    cy2 = (row_y[2] + row_y[3]) / 2
    cx2 = (col_x[0] + col_x[1]) / 2
    page.draw_circle(fitz.Point(cx2, cy2), 4.0, color=(0, 0, 0), width=0.8)
    page.insert_text(fitz.Point(col_x[1] + 15, cy2 + 4), "Línea de Servicio Secundario", fontsize=9, fontname="helv", color=(0, 0, 0))

    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes, {
        "table_bbox_norm": [col_x[0] / 800.0, row_y[0] / 600.0, col_x[-1] / 800.0, row_y[-1] / 600.0]
    }


def create_empty_grid_pdf() -> tuple[bytes, dict]:
    """
    Grilla vacía de tabla: solo líneas perimetrales y divisorias, sin texto ni iconos.
    Debe producir CERO símbolos candidatos.
    """
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)

    col_x = [60, 200, 450, 700]
    row_y = [80, 130, 180, 230, 280]

    for y in row_y:
        page.draw_line(fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y), color=(0, 0, 0), width=1.0)
    for x in col_x:
        page.draw_line(fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]), color=(0, 0, 0), width=1.0)

    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes, {
        "table_bbox_norm": [col_x[0] / 800.0, row_y[0] / 600.0, col_x[-1] / 800.0, row_y[-1] / 600.0]
    }


def create_real_technical_legend_pdf() -> tuple[bytes, dict]:
    """
    Leyenda técnica real con geometrías simbólicas válidas:
    - Válvula de compuerta (dos triángulos opuestos / líneas cruzadas con vástago)
    - Válvula de retención (check) con flecha
    - Pulsador de alarma (círculos concéntricos)
    - Extintor (rectángulo con cuello y vástago)
    Debe generar 4 símbolos candidatos con evidencia geométrica y recortes válidos.
    """
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)

    col_x = [50, 180, 520, 750]
    row_y = [60, 100, 170, 240, 310, 380]

    for y in row_y:
        page.draw_line(fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y), color=(0, 0, 0), width=1.0)
    for x in col_x:
        page.draw_line(fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]), color=(0, 0, 0), width=1.0)

    page.insert_text(fitz.Point(col_x[0] + 15, row_y[0] + 25), "SÍMBOLO", fontsize=10, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[1] + 15, row_y[0] + 25), "DENOMINACIÓN / ESPECIFICACIÓN", fontsize=10, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[2] + 15, row_y[0] + 25), "NORMA / CÓDIGO", fontsize=10, fontname="helv", color=(0, 0, 0))

    symbols_data = [
        {
            "name": "Válvula de Compuerta Bridada",
            "norm": "ASME B16.34",
            "tag": "VLV-GATE-01",
            "draw": lambda p, cx, cy: (
                p.draw_line(fitz.Point(cx - 18, cy - 12), fitz.Point(cx + 18, cy + 12), color=(0, 0, 0), width=2.0),
                p.draw_line(fitz.Point(cx - 18, cy + 12), fitz.Point(cx + 18, cy - 12), color=(0, 0, 0), width=2.0),
                p.draw_line(fitz.Point(cx - 18, cy - 12), fitz.Point(cx - 18, cy + 12), color=(0, 0, 0), width=2.0),
                p.draw_line(fitz.Point(cx + 18, cy - 12), fitz.Point(cx + 18, cy + 12), color=(0, 0, 0), width=2.0),
                p.draw_line(fitz.Point(cx, cy), fitz.Point(cx, cy - 16), color=(0, 0, 0), width=1.5),
                p.draw_line(fitz.Point(cx - 8, cy - 16), fitz.Point(cx + 8, cy - 16), color=(0, 0, 0), width=2.0)
            )
        },
        {
            "name": "Pulsador de Alarma de Incendio",
            "norm": "NFPA 72",
            "tag": "ALM-PB-01",
            "draw": lambda p, cx, cy: (
                p.draw_circle(fitz.Point(cx, cy), 18, color=(0, 0, 0), width=1.8),
                p.draw_circle(fitz.Point(cx, cy), 7, color=(0, 0, 0), fill=(0, 0, 0))
            )
        },
        {
            "name": "Extintor de Polvo Químico Seco PQS 10kg",
            "norm": "DS 594 Art. 45",
            "tag": "EXT-PQS-10",
            "draw": lambda p, cx, cy: (
                p.draw_rect(fitz.Rect(cx - 12, cy - 14, cx + 12, cy + 18), color=(0, 0, 0), fill=(0.1, 0.1, 0.1), width=1.5),
                p.draw_line(fitz.Point(cx, cy - 14), fitz.Point(cx, cy - 22), color=(0, 0, 0), width=2.0),
                p.draw_line(fitz.Point(cx - 5, cy - 22), fitz.Point(cx + 5, cy - 22), color=(0, 0, 0), width=2.0)
            )
        },
        {
            "name": "Válvula de Retención Check Swing",
            "norm": "API 6D / ISA 5.1",
            "tag": "VLV-CHK-01",
            "draw": lambda p, cx, cy: (
                p.draw_line(fitz.Point(cx - 18, cy - 12), fitz.Point(cx + 18, cy + 12), color=(0, 0, 0), width=2.0),
                p.draw_line(fitz.Point(cx - 18, cy + 12), fitz.Point(cx + 18, cy - 12), color=(0, 0, 0), width=2.0),
                p.draw_line(fitz.Point(cx - 18, cy - 12), fitz.Point(cx - 18, cy + 12), color=(0, 0, 0), width=2.0),
                p.draw_line(fitz.Point(cx + 18, cy - 12), fitz.Point(cx + 18, cy + 12), color=(0, 0, 0), width=2.0),
                p.draw_line(fitz.Point(cx - 6, cy - 4), fitz.Point(cx + 6, cy - 4), color=(0, 0, 0), width=2.0)
            )
        }
    ]

    for i, s in enumerate(symbols_data):
        r = i + 1
        cy = (row_y[r] + row_y[r + 1]) / 2
        cx = (col_x[0] + col_x[1]) / 2
        s["draw"](page, cx, cy)
        page.insert_text(fitz.Point(col_x[1] + 15, cy + 4), s["name"], fontsize=9, fontname="helv", color=(0, 0, 0))
        page.insert_text(fitz.Point(col_x[2] + 15, cy + 4), f"{s['norm']} ({s['tag']})", fontsize=9, fontname="helv", color=(0, 0, 0))

    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes, {
        "table_bbox_norm": [col_x[0] / 800.0, row_y[0] / 600.0, col_x[-1] / 800.0, row_y[-1] / 600.0],
        "symbols_count": len(symbols_data)
    }


def create_mixed_cell_pdf() -> tuple[bytes, dict]:
    """
    PDF con una celda que contiene tanto un símbolo geométrico (círculo) como texto (tag "TCV-101")
    dentro de la misma celda de la tabla.
    Debe ser clasificada como 'mixed' y promover el símbolo enriquecido.
    """
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)

    col_x = [60, 240, 720]
    row_y = [80, 120, 220]

    for y in row_y:
        page.draw_line(fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y), color=(0, 0, 0), width=1.0)
    for x in col_x:
        page.draw_line(fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]), color=(0, 0, 0), width=1.0)

    page.insert_text(fitz.Point(col_x[0] + 15, row_y[0] + 25), "SÍMBOLO Y TAG", fontsize=9, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[1] + 15, row_y[0] + 25), "DESCRIPCIÓN DE LAZO DE CONTROL", fontsize=9, fontname="helv", color=(0, 0, 0))

    cy = (row_y[1] + row_y[2]) / 2
    cx = (col_x[0] + col_x[1]) / 2

    # Símbolo geométrico real (círculo con línea horizontal de instrumento compartido)
    page.draw_circle(fitz.Point(cx, cy - 10), 16, color=(0, 0, 0), width=1.8)
    page.draw_line(fitz.Point(cx - 16, cy - 10), fitz.Point(cx + 16, cy - 10), color=(0, 0, 0), width=1.5)
    # Texto en la misma celda
    page.insert_text(fitz.Point(cx - 24, cy + 22), "TCV-101", fontsize=9, fontname="helv", color=(0, 0, 0))

    # Descripción en columna adyacente
    page.insert_text(fitz.Point(col_x[1] + 15, cy), "Válvula de Control de Temperatura Enfriador Principal según ISA 5.1", fontsize=9, fontname="helv", color=(0, 0, 0))

    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes, {
        "table_bbox_norm": [col_x[0] / 800.0, row_y[0] / 600.0, col_x[-1] / 800.0, row_y[-1] / 600.0]
    }


# ==============================================================================
# PRUEBAS NEGATIVAS OBLIGATORIAS
# ==============================================================================

class TestStrictSymbolGeometryNegativePipeline:
    """
    Pruebas negativas obligatorias para garantizar que el sistema NUNCA genere
    candidatos a símbolos a partir de texto OCR o cuadrículas sin geometría real.
    """

    def test_negative_isa51_alphanumeric_combinations(self, tmp_path):
        """1. Tabla ISA 5.1 con letras (A, B, C, X, O) y números (1, 0) debe producir 0 símbolos."""
        pdf_bytes, meta = create_isa51_alphanumeric_table_pdf()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]

        table_extractor = TableExtractor(width_px=800, height_px=600)
        table_extractor.crops_dir = str(tmp_path / "crops")
        os.makedirs(table_extractor.crops_dir, exist_ok=True)

        raw_blocks = page.get_text("blocks")
        texts = [
            {"text": b[4].strip(), "bbox_normalized": [b[0] / 800, b[1] / 600, b[2] / 800, b[3] / 600], "id": f"t_{i}"}
            for i, b in enumerate(raw_blocks) if b[6] == 0 and b[4].strip()
        ]

        extracted_table = table_extractor.extract_from_region(
            region_bbox_norm=meta["table_bbox_norm"],
            texts=texts,
            page=page,
            doc_uid="test_isa51"
        )

        assert extracted_table is not None
        # Condición estricta: has_symbols DEBE ser False y extracted_symbols vacío
        assert extracted_table.has_symbols is False
        assert len(extracted_table.extracted_symbols) == 0
        assert extracted_table.reading_orientation == "none"

        # Todas las celdas con texto deben ser 'text_only', no 'symbol_only' ni 'mixed'
        for cell in extracted_table.cells:
            assert cell.has_symbol is False
            if cell.text.strip():
                assert cell.cell_type in ("text_only", "text_cell"), f"Celda '{cell.text}' marcada erróneamente como {cell.cell_type}"

        doc.close()

    def test_negative_pure_text_table(self, tmp_path):
        """2. Tabla de especificaciones de solo texto debe producir 0 símbolos."""
        pdf_bytes, meta = create_pure_text_table_pdf()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]

        table_extractor = TableExtractor(width_px=800, height_px=600)
        table_extractor.crops_dir = str(tmp_path / "crops")
        os.makedirs(table_extractor.crops_dir, exist_ok=True)

        raw_blocks = page.get_text("blocks")
        texts = [
            {"text": b[4].strip(), "bbox_normalized": [b[0] / 800, b[1] / 600, b[2] / 800, b[3] / 600], "id": f"t_{i}"}
            for i, b in enumerate(raw_blocks) if b[6] == 0 and b[4].strip()
        ]

        extracted_table = table_extractor.extract_from_region(
            region_bbox_norm=meta["table_bbox_norm"],
            texts=texts,
            page=page,
            doc_uid="test_pure_text"
        )

        assert extracted_table is not None
        assert extracted_table.has_symbols is False
        assert len(extracted_table.extracted_symbols) == 0
        assert extracted_table.reading_orientation == "none"
        doc.close()

    def test_negative_column_0_short_codes(self, tmp_path):
        """3. Columna 0 con códigos breves (V-01, MAT-01) debe producir 0 símbolos."""
        pdf_bytes, meta = create_col0_short_codes_pdf()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]

        table_extractor = TableExtractor(width_px=800, height_px=600)
        table_extractor.crops_dir = str(tmp_path / "crops")
        os.makedirs(table_extractor.crops_dir, exist_ok=True)

        raw_blocks = page.get_text("blocks")
        texts = [
            {"text": b[4].strip(), "bbox_normalized": [b[0] / 800, b[1] / 600, b[2] / 800, b[3] / 600], "id": f"t_{i}"}
            for i, b in enumerate(raw_blocks) if b[6] == 0 and b[4].strip()
        ]

        extracted_table = table_extractor.extract_from_region(
            region_bbox_norm=meta["table_bbox_norm"],
            texts=texts,
            page=page,
            doc_uid="test_col0_codes"
        )

        assert extracted_table is not None
        assert extracted_table.has_symbols is False
        assert len(extracted_table.extracted_symbols) == 0
        doc.close()

    def test_negative_foreign_image_on_page(self, tmp_path):
        """4. Imagen ajena en la página NO debe contaminar celdas textuales con has_raster."""
        pdf_bytes, meta = create_page_with_foreign_image_and_text_table_pdf()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]

        # Verificar que la página efectivamente tiene una imagen incrustada
        assert len(page.get_images()) >= 1

        table_extractor = TableExtractor(width_px=800, height_px=600)
        table_extractor.crops_dir = str(tmp_path / "crops")
        os.makedirs(table_extractor.crops_dir, exist_ok=True)

        raw_blocks = page.get_text("blocks")
        texts = [
            {"text": b[4].strip(), "bbox_normalized": [b[0] / 800, b[1] / 600, b[2] / 800, b[3] / 600], "id": f"t_{i}"}
            for i, b in enumerate(raw_blocks) if b[6] == 0 and b[4].strip()
        ]

        extracted_table = table_extractor.extract_from_region(
            region_bbox_norm=meta["table_bbox_norm"],
            texts=texts,
            page=page,
            doc_uid="test_foreign_img"
        )

        assert extracted_table is not None
        assert extracted_table.has_symbols is False
        assert len(extracted_table.extracted_symbols) == 0
        doc.close()

    def test_negative_vectorized_typography_glyphs(self, tmp_path):
        """5. Letras/números vectorizados (glifos tipográficos) deben ser descartados: 0 símbolos."""
        pdf_bytes, meta = create_vectorized_font_glyphs_pdf()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]

        table_extractor = TableExtractor(width_px=800, height_px=600)
        table_extractor.crops_dir = str(tmp_path / "crops")
        os.makedirs(table_extractor.crops_dir, exist_ok=True)

        raw_blocks = page.get_text("blocks")
        texts = [
            {"text": b[4].strip(), "bbox_normalized": [b[0] / 800, b[1] / 600, b[2] / 800, b[3] / 600], "id": f"t_{i}"}
            for i, b in enumerate(raw_blocks) if b[6] == 0 and b[4].strip()
        ]

        extracted_table = table_extractor.extract_from_region(
            region_bbox_norm=meta["table_bbox_norm"],
            texts=texts,
            page=page,
            doc_uid="test_glyphs"
        )

        assert extracted_table is not None
        assert extracted_table.has_symbols is False
        assert len(extracted_table.extracted_symbols) == 0
        doc.close()

    def test_negative_empty_grid(self, tmp_path):
        """6. Grilla vacía sin contenido debe producir 0 símbolos y celdas 'empty'."""
        pdf_bytes, meta = create_empty_grid_pdf()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]

        table_extractor = TableExtractor(width_px=800, height_px=600)
        table_extractor.crops_dir = str(tmp_path / "crops")
        os.makedirs(table_extractor.crops_dir, exist_ok=True)

        extracted_table = table_extractor.extract_from_region(
            region_bbox_norm=meta["table_bbox_norm"],
            texts=[],
            page=page,
            doc_uid="test_empty_grid"
        )

        if extracted_table is not None:
            assert extracted_table.has_symbols is False
            assert len(extracted_table.extracted_symbols) == 0
            for cell in extracted_table.cells:
                assert cell.cell_type == "empty"
        doc.close()


# ==============================================================================
# PRUEBAS POSITIVAS
# ==============================================================================

class TestStrictSymbolGeometryPositivePipeline:
    """
    Pruebas positivas que verifican que cuando hay geometría visual real
    (círculos, líneas, arcos, flechas) sí se detectan símbolos con evidencia auditable.
    """

    def test_positive_technical_legend_real_geometries(self, tmp_path):
        """7. Leyenda técnica real con geometrías debe extraer símbolos con crops y evidencia auditable."""
        pdf_bytes, meta = create_real_technical_legend_pdf()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]

        table_extractor = TableExtractor(width_px=800, height_px=600)
        table_extractor.crops_dir = str(tmp_path / "crops")
        os.makedirs(table_extractor.crops_dir, exist_ok=True)

        raw_blocks = page.get_text("blocks")
        texts = [
            {"text": b[4].strip(), "bbox_normalized": [b[0] / 800, b[1] / 600, b[2] / 800, b[3] / 600], "id": f"t_{i}"}
            for i, b in enumerate(raw_blocks) if b[6] == 0 and b[4].strip()
        ]

        extracted_table = table_extractor.extract_from_region(
            region_bbox_norm=meta["table_bbox_norm"],
            texts=texts,
            page=page,
            doc_uid="test_legend_real"
        )

        assert extracted_table is not None
        assert extracted_table.has_symbols is True
        assert len(extracted_table.extracted_symbols) == meta["symbols_count"]
        assert extracted_table.reading_orientation == "row_major"

        for sym in extracted_table.extracted_symbols:
            # Requisitos auditables obligatorios
            assert sym.geometric_evidence is True
            assert sym.geometric_confidence >= 0.70
            assert len(sym.evidence_sources) > 0
            assert isinstance(sym.shape_features, dict)
            assert sym.cell_bbox is not None and len(sym.cell_bbox) == 4
            assert sym.crop_image_path is not None
            # Verificar que el recorte visual físico exista en disco y tenga peso > 0
            full_crop = os.path.join(table_extractor.crops_dir, os.path.basename(sym.crop_image_path))
            assert os.path.exists(full_crop), f"El recorte {full_crop} no existe en disco"
            assert os.path.getsize(full_crop) > 0

            # Verificar que los metadatos semánticos se hayan enriquecido desde OCR de la fila
            assert sym.symbol_name != "Símbolo Desconocido"
            assert sym.technical_function is not None

        doc.close()

    def test_positive_mixed_cell_symbol_and_text(self, tmp_path):
        """8. Celda con símbolo + texto (tag) debe clasificarse como 'mixed' y extraer el símbolo."""
        pdf_bytes, meta = create_mixed_cell_pdf()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]

        table_extractor = TableExtractor(width_px=800, height_px=600)
        table_extractor.crops_dir = str(tmp_path / "crops")
        os.makedirs(table_extractor.crops_dir, exist_ok=True)

        raw_blocks = page.get_text("blocks")
        texts = [
            {"text": b[4].strip(), "bbox_normalized": [b[0] / 800, b[1] / 600, b[2] / 800, b[3] / 600], "id": f"t_{i}"}
            for i, b in enumerate(raw_blocks) if b[6] == 0 and b[4].strip()
        ]

        extracted_table = table_extractor.extract_from_region(
            region_bbox_norm=meta["table_bbox_norm"],
            texts=texts,
            page=page,
            doc_uid="test_mixed"
        )

        assert extracted_table is not None
        assert extracted_table.has_symbols is True
        assert len(extracted_table.extracted_symbols) >= 1

        mixed_cell = next(c for c in extracted_table.cells if c.row_index == 1 and c.column_index == 0)
        assert mixed_cell.cell_type == "mixed"
        assert mixed_cell.has_symbol is True
        assert mixed_cell.geometric_evidence is True

        doc.close()

    def test_positive_candidate_generator_without_synthetic_fallback(self, db_session, tmp_path):
        """9. CandidateGeneratorService NO genera símbolos si la tabla es sólo texto, y sí genera si hay geometría."""
        org_id = str(uuid.uuid4())
        proj_id = str(uuid.uuid4())
        org = Organization(id=org_id, name="Test Org Pipeline", slug=f"slug-{uuid.uuid4().hex[:6]}")
        db_session.add(org)
        project = Project(id=proj_id, organization_id=org_id, code=f"PRJ-{uuid.uuid4().hex[:4].upper()}", name="Test Project Pipeline", status="active")
        db_session.add(project)

        extraction = SourceExtraction(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            project_id=project.id,
            title="Test Extraction Pipeline",
            source_origin="document",
            status="completed"
        )
        db_session.add(extraction)
        db_session.commit()

        generator = CandidateGeneratorService(db_session)

        # Caso A: Tabla puramente textual (ISA 5.1 alfanumérico) -> 0 symbol_candidate
        text_table_payload = {
            "tables": [{
                "title": "Tabla ISA 5.1 Alfanumérica",
                "has_symbols": False,
                "extracted_symbols": [],
                "bbox_normalized": [0.1, 0.1, 0.9, 0.5],
                "reading_orientation": "none",
                "headers": ["LETRA", "FUNCIÓN"],
                "rows": [["A", "Alarma"], ["B", "Quemador"]]
            }],
            "symbols": []
        }

        cands_text = generator.generate_candidates_from_evidence(
            extraction_id=extraction.id,
            evidence_payload=text_table_payload,
            discipline="piping"
        )

        symbol_cands_text = [c for c in cands_text if c.candidate_type == "symbol_candidate"]
        # REGLA FUNDAMENTAL: 0 símbolos candidates para tabla de texto
        assert len(symbol_cands_text) == 0, f"Se generaron símbolos sintéticos espurios: {[s.title for s in symbol_cands_text]}"

        # Caso B: Tabla con geometría real -> Genera symbol_candidate con campos auditables
        geo_sym = {
            "symbol_name": "Válvula de Compuerta",
            "canonical_symbol_family": "valves",
            "standard_reference": "ASME B16.34",
            "discipline": "piping",
            "category": "Válvulas",
            "crop_image_path": "/data/crops/symbols/sym_valid.png",
            "technical_function": "Seccionamiento de flujo",
            "geometric_evidence": True,
            "geometric_confidence": 0.94,
            "evidence_sources": ["vector_circle_or_arc", "vector_multi_stroke_structure"],
            "shape_features": {"circle_count": 1, "line_count": 4},
            "text_mask_overlap_ratio": 0.05,
            "cell_bbox": [0.1, 0.15, 0.3, 0.25],
            "inner_drawing_bbox": [0.12, 0.16, 0.28, 0.24],
            "row_index": 1,
            "col_index": 0
        }

        real_table_payload = {
            "tables": [{
                "title": "Leyenda de Válvulas",
                "has_symbols": True,
                "extracted_symbols": [geo_sym],
                "bbox_normalized": [0.1, 0.1, 0.9, 0.5],
                "reading_orientation": "row_major",
                "headers": ["SÍMBOLO", "DESCRIPCIÓN"]
            }],
            "symbols": []
        }

        cands_real = generator.generate_candidates_from_evidence(
            extraction_id=extraction.id,
            evidence_payload=real_table_payload,
            discipline="piping"
        )

        symbol_cands_real = [c for c in cands_real if c.candidate_type == "symbol_candidate"]
        assert len(symbol_cands_real) == 1
        sym = symbol_cands_real[0]
        assert sym.title == "Válvula de Compuerta"
        assert sym.metadata_payload["geometric_evidence"] is True
        assert sym.metadata_payload["geometric_confidence"] == 0.94
        assert "vector_circle_or_arc" in sym.metadata_payload["evidence_sources"]
        assert sym.metadata_payload["inner_drawing_bbox"] == [0.12, 0.16, 0.28, 0.24]
