"""
Script de inicialización para el Primer Lote Canónico de Simbología de Piping e Instrumentación (Fase 2).
Normas de Referencia: ISA-5.1 / ASME B16.34 / API 609.
"""

import sys
import os
import uuid
from datetime import datetime, timezone

# Agregar directorio backend al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.db.session import SessionLocal
from app.db.models.template_memory import SymbolLibrary, SymbolTemplate

CANONICAL_BATCH = [
    {
        "symbol_class": "gate_valve",
        "display_name": "Válvula de Compuerta Manual ASME B16.34",
        "canonical_family": "valves",
        "discipline": "piping",
        "standard": "ASME B16.34 / API 600",
        "variant_group": "VVG-VALVE-GATE-01",
        "width_mm": 10.5,
        "height_mm": 8.0,
        "dhash": "e0e0f0f00f0f0707",
        "aliases": ["gate valve", "valvula compuerta", "valvula de compuerta"],
        "reviewer": "Ingeniero Revisor Piping (Senior HITL)",
        "notes": "Lote inicial canónico aprobado según ASME B16.34 Clase 150 RF."
    },
    {
        "symbol_class": "globe_valve",
        "display_name": "Válvula de Globo para Regulación de Caudal",
        "canonical_family": "valves",
        "discipline": "piping",
        "standard": "ASME B16.34",
        "variant_group": "VVG-VALVE-GLOBE-01",
        "width_mm": 10.5,
        "height_mm": 8.0,
        "dhash": "f0f0e0e007070f0f",
        "aliases": ["globe valve", "valvula globo", "valvula de globo"],
        "reviewer": "Ingeniero Revisor Piping (Senior HITL)",
        "notes": "Lote inicial canónico con tapón de regulación fina."
    },
    {
        "symbol_class": "check_valve",
        "display_name": "Válvula de Retención / Check Tipo Columpio",
        "canonical_family": "valves",
        "discipline": "piping",
        "standard": "ASME B16.34 / API 594",
        "variant_group": "VVG-VALVE-CHECK-01",
        "width_mm": 10.5,
        "height_mm": 7.0,
        "dhash": "cccc3333cccc3333",
        "aliases": ["check valve", "valvula check", "valvula retencion", "non-return valve"],
        "reviewer": "Ingeniero Revisor Piping (Senior HITL)",
        "notes": "Lote inicial canónico para prevención de flujo inverso."
    },
    {
        "symbol_class": "ball_valve",
        "display_name": "Válvula de Bola de Paso Total",
        "canonical_family": "valves",
        "discipline": "piping",
        "standard": "ASME B16.34 / API 608",
        "variant_group": "VVG-VALVE-BALL-01",
        "width_mm": 10.5,
        "height_mm": 8.0,
        "dhash": "a5a55a5aa5a55a5a",
        "aliases": ["ball valve", "valvula bola", "valvula de bola"],
        "reviewer": "Ingeniero Revisor Piping (Senior HITL)",
        "notes": "Lote inicial canónico de cierre rápido de 1/4 de vuelta."
    },
    {
        "symbol_class": "butterfly_valve",
        "display_name": "Válvula de Mariposa Wafer Tipo Eje Concéntrico",
        "canonical_family": "valves",
        "discipline": "piping",
        "standard": "API 609 / ASME B16.34",
        "variant_group": "VVG-VALVE-BUTTERFLY-01",
        "width_mm": 10.0,
        "height_mm": 8.0,
        "dhash": "1f1f8e8e1f1f8e8e",
        "aliases": ["butterfly valve", "valvula mariposa", "valvula de mariposa wafer"],
        "reviewer": "Ingeniero Revisor Piping (Senior HITL)",
        "notes": "Lote inicial canónico para montaje wafer entre bridas."
    },
    {
        "symbol_class": "control_valve",
        "display_name": "Válvula de Control con Actuador Neumático Diafragma",
        "canonical_family": "valves",
        "discipline": "piping",
        "standard": "ISA-5.1 / IEC 60534",
        "variant_group": "VVG-VALVE-CONTROL-01",
        "width_mm": 12.0,
        "height_mm": 18.0,
        "dhash": "7e7e81817e7e8181",
        "aliases": ["control valve", "valvula de control", "valvula automatica", "actuated valve"],
        "reviewer": "Ingeniero Revisor Piping (Senior HITL)",
        "notes": "Lote inicial canónico con sombrerete y actuador diafragma según ISA-5.1."
    },
    {
        "symbol_class": "pressure_transmitter",
        "display_name": "Transmisor de Presión Montado en Campo (PT-101)",
        "canonical_family": "instruments",
        "discipline": "piping",
        "standard": "ISA-5.1",
        "variant_group": "VVG-INST-PT-01",
        "width_mm": 9.0,
        "height_mm": 9.0,
        "dhash": "00ffff0000ffff00",
        "aliases": ["PT", "pressure transmitter", "transmisor de presion", "indicador presion"],
        "reviewer": "Ingeniero Revisor Instrumentación (Senior HITL)",
        "notes": "Lote inicial canónico: burbuja circular sin línea central (montaje en campo directo)."
    },
    {
        "symbol_class": "temperature_transmitter",
        "display_name": "Transmisor de Temperatura Montado en Campo (TT-102)",
        "canonical_family": "instruments",
        "discipline": "piping",
        "standard": "ISA-5.1",
        "variant_group": "VVG-INST-TT-01",
        "width_mm": 9.0,
        "height_mm": 9.0,
        "dhash": "00f00f0000f00f00",
        "aliases": ["TT", "temperature transmitter", "transmisor de temperatura", "termopozo"],
        "reviewer": "Ingeniero Revisor Instrumentación (Senior HITL)",
        "notes": "Lote inicial canónico: burbuja circular montada en campo con termopozo."
    }
]


def seed_canonical_batch():
    print("Iniciando sembrado del Primer Lote Canónico de Piping e Instrumentación (Fase 2)...")
    db = SessionLocal()
    try:
        # 1. Obtener o crear librería de piping e instrumentación
        library_name = "Librería Canónica Oficial ISA-5.1 / ASME (Fase 2)"
        lib = db.query(SymbolLibrary).filter(SymbolLibrary.name == library_name).first()
        if not lib:
            lib = SymbolLibrary(
                id=str(uuid.uuid4()),
                name=library_name,
                discipline="piping",
                standard="ISA-5.1 / ASME B16.34",
                description="Colección gobernada de símbolos técnicos de cañerías e instrumentación curados por HITL.",
                status="published"
            )
            db.add(lib)
            db.flush()
            print(f"Librería creada: {lib.name} ({lib.id})")
        else:
            print(f"Librería existente: {lib.name} ({lib.id})")

        now_str = datetime.now(timezone.utc).isoformat()
        inserted = 0

        for item in CANONICAL_BATCH:
            existing = db.query(SymbolTemplate).filter(
                SymbolTemplate.library_id == lib.id,
                SymbolTemplate.symbol_class == item["symbol_class"]
            ).first()

            descriptors = {
                "source": "canonical_batch_phase2",
                "canonical_symbol_family": item["canonical_family"],
                "discipline": item["discipline"],
                "reference_standard": item["standard"],
                "visual_variant_group_id": item["variant_group"],
                "dhash_64": item["dhash"],
                "aliases": item["aliases"],
                "estimated_physical_size_mm": {
                    "width_mm": item["width_mm"],
                    "height_mm": item["height_mm"]
                },
                "aspect_ratio": round(item["width_mm"] / max(item["height_mm"], 0.01), 2),
                "approval_audit": {
                    "approved_by": item["reviewer"],
                    "approved_at": now_str,
                    "validation_notes": item["notes"]
                }
            }

            if existing:
                existing.display_name = item["display_name"]
                existing.feature_descriptors = descriptors
                print(f"  [Actualizado] {item['display_name']} ({item['symbol_class']})")
            else:
                tpl = SymbolTemplate(
                    id=str(uuid.uuid4()),
                    library_id=lib.id,
                    symbol_class=item["symbol_class"],
                    display_name=item["display_name"],
                    feature_descriptors=descriptors
                )
                db.add(tpl)
                inserted += 1
                print(f"  [Insertado] {item['display_name']} ({item['symbol_class']})")

        db.commit()
        print(f"\nSembrado completado exitosamente: {inserted} nuevos templates insertados.")
    except Exception as e:
        db.rollback()
        print(f"Error durante el sembrado del lote canónico: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_canonical_batch()
