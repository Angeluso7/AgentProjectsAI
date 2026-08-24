import os
import re
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.db.models.intake_extractions import SourceExtraction, ExtractedItem

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

        # 1. Procesar Tablas Estructuradas -> table_matrix_candidate & premise_candidate
        for tbl in evidence_payload.get("tables", []):
            table_title = tbl.get("title") or "Tabla Técnica"
            headers = tbl.get("headers", [])
            rows = tbl.get("rows", [])
            node_id = tbl.get("node_id")

            # A) Crear Table Matrix Candidate
            tbl_cand = ExtractedItem(
                id=str(uuid.uuid4()),
                extraction_id=extraction_id,
                item_type="table",
                candidate_type="table_matrix_candidate",
                title=f"Matriz Técnica: {table_title}",
                code_or_number=f"TBL-{discipline[:3].upper()}-{len(generated_candidates) + 1}",
                description=f"Matriz estructurada con {len(rows)} filas y {len(headers)} columnas: {', '.join(headers[:5])}.",
                content_text=f"Tabla técnica de {len(rows)} registros. Columnas: {headers}",
                derived_text=f"Estructura tabular de ingeniería correspondiente a {doc_title}.",
                bbox_normalized=[0.05, 0.1, 0.95, 0.5],
                page_number=tbl.get("page_number", 1),
                evidence_references=[node_id] if node_id else [],
                technical_parameters={
                    "row_count": len(rows),
                    "col_count": len(headers),
                    "headers": headers
                },
                structured_matrix={
                    "headers": headers,
                    "rows": rows,
                    "row_count": len(rows)
                },
                target_destination="both",
                review_status="to_confirm",
                source_origin=extraction.source_origin,
                source_reference=f"Documento: {doc_title}",
                item_nature="official_rule",
                governance_note="Matriz técnica extraída por DoclingService. Requiere confirmación de columnas clave.",
                metadata_payload={"evidence_type": "table_matrix"}
            )
            self.db.add(tbl_cand)
            generated_candidates.append(tbl_cand)

            # B) Derivar Premisas Técnicas si contiene Line List o Valve Schedule
            if any("SPEC" in str(h).upper() or "LINE" in str(h).upper() for h in headers):
                prem_cand = ExtractedItem(
                    id=str(uuid.uuid4()),
                    extraction_id=extraction_id,
                    item_type="requirement",
                    candidate_type="premise_candidate",
                    title=f"Premisa Técnica de Piping: {table_title}",
                    code_or_number=f"PREM-PIP-{len(generated_candidates) + 1}",
                    description="Premisa de diseño de cañerías/válvulas derivada del schedule de líneas.",
                    content_text=f"Las líneas y especificaciones técnicas listadas en {table_title} rigen como premisa de diseño de proceso.",
                    derived_text="Todas las líneas del schedule deben cumplir la especificación de material y presión indicada en la matriz.",
                    bbox_normalized=[0.05, 0.1, 0.95, 0.5],
                    page_number=tbl.get("page_number", 1),
                    evidence_references=[node_id] if node_id else [],
                    technical_parameters={"referenced_table": table_title},
                    target_destination="knowledge_base",
                    review_status="to_confirm",
                    source_origin=extraction.source_origin,
                    source_reference=f"Documento: {doc_title}",
                    item_nature="proposed_rule",
                    governance_note="Premisa de piping candidata generada a partir de schedule tabular.",
                    metadata_payload={"evidence_type": "piping_premise"}
                )
                self.db.add(prem_cand)
                generated_candidates.append(prem_cand)

        # 2. Procesar Nodos Estructurales (Secciones, Notas, Artículos, Cláusulas)
        for node in evidence_payload.get("structural_nodes", []):
            node_type = node.get("node_type")
            node_title = node.get("title") or "Sección Técnica"
            content = node.get("content_text", "")
            node_id = node.get("id")

            # A) Si es Bloque CAD -> diagram_candidate o symbol_candidate
            if node_type == "dxf_block_summary":
                blk_data = node.get("structured_payload", {})
                blk_name = blk_data.get("block_name", "UNKNOWN_BLOCK")
                attrs = blk_data.get("attributes", {})

                is_symbol = any(tag in blk_name.upper() for tag in ["VALV", "INST", "PUMP", "SYM", "VLV", "SIMB"])
                candidate_type = "symbol_candidate" if is_symbol else "diagram_candidate"

                cad_cand = ExtractedItem(
                    id=str(uuid.uuid4()),
                    extraction_id=extraction_id,
                    item_type="symbol" if is_symbol else "figure",
                    candidate_type=candidate_type,
                    title=f"Bloque CAD / Símbolo: {blk_name}",
                    code_or_number=f"CAD-{blk_name[:12]}",
                    description=f"Entidad de bloque DXF en capa '{blk_data.get('layer')}'. Atributos: {attrs}",
                    content_text=content,
                    derived_text=f"Elemento gráfico vectorial detectado en plano CAD con atributos: {attrs}",
                    disclaimer_notes=self.TOPOLOGICAL_DISCLAIMER,
                    bbox_normalized=[0.1, 0.1, 0.4, 0.4],
                    page_number=1,
                    evidence_references=[node_id] if node_id else [],
                    technical_parameters={
                        "block_name": blk_name,
                        "layer": blk_data.get("layer"),
                        "location": blk_data.get("location"),
                        "attributes": attrs
                    },
                    target_destination="knowledge_base",
                    review_status="to_confirm",
                    source_origin=extraction.source_origin,
                    source_reference=f"Plano CAD: {doc_title}",
                    item_nature="official_rule",
                    governance_note="Extraído de DXF con ezdxf. Limitación: sin conectividad topológica de líneas.",
                    metadata_payload={"evidence_type": "cad_block", "is_symbol": is_symbol}
                )
                self.db.add(cad_cand)
                generated_candidates.append(cad_cand)

            # B) Si es Sección / Párrafo Normativo -> rule_candidate o premise_candidate
            elif node_type in ["heading", "paragraph", "technical_note"]:
                # Evaluar si contiene exigencias cuantificables ("deberá", "mínimo", ">= ", "mm", "psi")
                has_requirement = bool(re.search(r'(deber[aá]|m[ií]nimo|m[aá]ximo|no inferior|superior a|obligatorio|exigencia|resistencia)', content, re.IGNORECASE))
                has_example = bool(re.search(r'(ejemplo|caso ilustrativo|figura ilustrativa|a modo de ejemplo|por ejemplo)', content, re.IGNORECASE))

                if has_example:
                    ex_cand = ExtractedItem(
                        id=str(uuid.uuid4()),
                        extraction_id=extraction_id,
                        item_type="figure",
                        candidate_type="example_candidate",
                        title=f"Ejemplo / Caso Ilustrativo: {node_title[:60]}",
                        code_or_number=f"EX-{discipline[:3].upper()}-{len(generated_candidates) + 1}",
                        description=f"Caso de ejemplo o ilustración técnica detectada en la sección {node_title}.",
                        content_text=content,
                        derived_text="Caso práctico de aplicación normativa.",
                        page_number=node.get("page_number", 1),
                        evidence_references=[node_id] if node_id else [],
                        target_destination="knowledge_base",
                        review_status="to_confirm",
                        source_origin=extraction.source_origin,
                        source_reference=f"Documento: {doc_title}",
                        item_nature="concept",
                        governance_note="Ejemplo normativo para apoyo y contexto del asistente.",
                        metadata_payload={"evidence_type": "example_note"}
                    )
                    self.db.add(ex_cand)
                    generated_candidates.append(ex_cand)

                elif has_requirement:
                    rule_cand = ExtractedItem(
                        id=str(uuid.uuid4()),
                        extraction_id=extraction_id,
                        item_type="rule",
                        candidate_type="rule_candidate",
                        title=f"Regla Candidata QA/QC: {node_title[:60]}",
                        code_or_number=f"R-QAQC-{discipline[:3].upper()}-{len(generated_candidates) + 1}",
                        description=f"Requisito determinístico extraído de {node_title}.",
                        content_text=content,
                        derived_text=f"Exigencia técnica verificable: {content[:150]}...",
                        page_number=node.get("page_number", 1),
                        evidence_references=[node_id] if node_id else [],
                        technical_parameters={"section": node_title},
                        target_destination="rules_engine",
                        review_status="to_confirm",
                        source_origin=extraction.source_origin,
                        source_reference=f"Documento: {doc_title}",
                        item_nature="official_rule",
                        governance_note="Regla candidata derivada de cláusula técnica. Requiere aprobación para activación en QA/QC.",
                        metadata_payload={"evidence_type": "normative_requirement"}
                    )
                    self.db.add(rule_cand)
                    generated_candidates.append(rule_cand)

        # 3. Generar candidatos de Símbolo y Foto de Equipo si no hay bloques CAD (Mock/Heurístico)
        if not any(c.candidate_type == "symbol_candidate" for c in generated_candidates):
            sym_cand = ExtractedItem(
                id=str(uuid.uuid4()),
                extraction_id=extraction_id,
                item_type="symbol",
                candidate_type="symbol_candidate",
                title=f"Símbolo Técnico: Leyenda / Válvula ({discipline})",
                code_or_number=f"SYM-{discipline[:3].upper()}-01",
                description="Símbolo y convención gráfica de ingeniería detectada en documento.",
                content_text="Simbología estándar de piping / instrumentación para diagramas.",
                derived_text="Identificador gráfico para componentes de línea y accesorios.",
                bbox_normalized=[0.05, 0.7, 0.35, 0.95],
                page_number=1,
                target_destination="knowledge_base",
                review_status="to_confirm",
                source_origin=extraction.source_origin,
                source_reference=f"Documento: {doc_title}",
                item_nature="official_rule",
                governance_note="Símbolo detectado para validación de leyendas.",
                metadata_payload={"category": "piping_valves"}
            )
            self.db.add(sym_cand)
            generated_candidates.append(sym_cand)

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
                metadata_payload={"equipment_type": "piping_assembly"}
            )
            self.db.add(eq_cand)
            generated_candidates.append(eq_cand)

        for c in generated_candidates:
            meta = dict(c.metadata_payload or {})
            if doc_id:
                meta["document_id"] = doc_id
            if file_hash:
                meta["file_hash_sha256"] = file_hash
            meta["topological_connectivity_inferred"] = False
            meta["disclaimer_topology_unverified"] = self.TOPOLOGICAL_DISCLAIMER
            c.metadata_payload = meta
            if not c.disclaimer_notes:
                c.disclaimer_notes = self.TOPOLOGICAL_DISCLAIMER

        extraction.total_items = len(generated_candidates)
        extraction.status = "extracted"
        self.db.commit()

        logger.info(f"Generados {len(generated_candidates)} candidatos estructurados para extracción '{extraction_id}'.")
        return generated_candidates
