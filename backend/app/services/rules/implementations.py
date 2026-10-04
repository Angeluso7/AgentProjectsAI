import re
from typing import Dict, Any, List, Optional
from app.services.rules.base import BaseRule
from app.services.rules.contracts import RuleInput, RuleResult

class DoorCountMatchRule(BaseRule):
    """RULE_DOOR_COUNT_MATCH_V1: Concilia la cantidad de símbolos de puertas detectados en drawing_area contra el cuadro de puertas."""
    code = "RULE_DOOR_COUNT_MATCH_V1"
    name = "Conciliación de Conteo de Puertas (Dibujo vs Cuadro)"
    category = "cross_reconciliation"
    discipline = "architecture"
    severity_default = "high"
    rule_logic_type = "count_reconciliation"
    version = "1.0"
    description = "Compara el total de door_symbol detectados en drawing_area con el total de vanos de puertas declarados en el cuadro técnico."

    def evaluate(self, inputs: RuleInput) -> RuleResult:
        doors = [s for s in inputs.symbols if s.symbol_type == "door_symbol"]
        door_tables = [t for t in inputs.tables if t.table_type in ["door_schedule", "window_schedule"]]

        # Si no hay cuadro de puertas ni símbolos
        if not door_tables and not doors:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="not_applicable",
                severity="info",
                title="Sin elementos de puertas evaluables",
                description="La lámina no contiene símbolos de puertas ni cuadros de vanos.",
                confidence=1.0
            )

        if not door_tables:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="insufficient_evidence",
                severity="medium",
                title="Falta Cuadro de Puertas para Conciliación",
                description=f"Se detectaron {len(doors)} símbolos de puertas pero no existe un cuadro de puertas para contrastar.",
                recommendation="Verificar si la lámina debe contener cuadro de vanos o si se encuentra en otra lámina del proyecto.",
                evidence_refs={"detected_doors_count": len(doors), "symbols": [d.id for d in doors]},
                observed_value={"detected_doors": len(doors)},
                confidence=0.85,
                requires_human_review=True,
                review_reason="MISSING_TABLE_FOR_RECONCILIATION",
                review_task_type="insufficient_evidence_review"
            )

        # Calcular total declarado en la tabla
        declared_count = 0
        table_ref = door_tables[0]
        cells = inputs.cells_by_table.get(table_ref.id, [])

        # Buscar si existe columna de 'CANTIDAD' o 'CANT'
        cant_col_idx = None
        for c in cells:
            if c.is_header and re.search(r"(CANT|CANTIDAD|QTY)", c.text.upper()):
                cant_col_idx = c.column_index
                break

        if cant_col_idx is not None:
            for c in cells:
                if not c.is_header and c.column_index == cant_col_idx:
                    try:
                        # Extraer entero
                        val_match = re.search(r"\d+", c.text)
                        if val_match:
                            declared_count += int(val_match.group())
                    except Exception:
                        pass
        else:
            # Fallback: total de filas no-header (asumiendo 1 por fila)
            declared_count = max(0, table_ref.row_count - 1)

        detected_count = len(doors)
        delta = detected_count - declared_count

        evidence = {
            "table_id": table_ref.id,
            "table_type": table_ref.table_type,
            "table_title": table_ref.title,
            "declared_doors_count": declared_count,
            "detected_doors_count": detected_count,
            "symbols": [d.id for d in doors]
        }

        if delta == 0:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="passed",
                severity="info",
                title="Conteo de Puertas Conciliado Exitosamente",
                description=f"El total de {detected_count} puertas detectadas en dibujo coincide exactamente con las {declared_count} declaradas en cuadro.",
                evidence_refs=evidence,
                expected_value=declared_count,
                observed_value=detected_count,
                delta=0,
                confidence=0.95
            )
        else:
            sev = "critical" if abs(delta) >= 3 else "high"
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="failed",
                severity=sev,
                title=f"Discrepancia en Conteo de Puertas (Delta: {delta:+d})",
                description=f"Se detectaron {detected_count} puertas en el dibujo pero el cuadro técnico declara {declared_count}. Discrepancia de {abs(delta)} unidad(es).",
                recommendation="Auditar si faltan vanos por rotular en el plano o si la tabla omite tipos de puertas.",
                evidence_refs=evidence,
                expected_value=declared_count,
                observed_value=detected_count,
                delta=delta,
                confidence=0.92,
                requires_human_review=True,
                review_reason=f"DOOR_COUNT_MISMATCH_DELTA_{delta}",
                review_task_type="rule_finding_review"
            )


class WindowCountMatchRule(BaseRule):
    """RULE_WINDOW_COUNT_MATCH_V1: Concilia la cantidad de símbolos de ventanas contra el cuadro de ventanas."""
    code = "RULE_WINDOW_COUNT_MATCH_V1"
    name = "Conciliación de Conteo de Ventanas (Dibujo vs Cuadro)"
    category = "cross_reconciliation"
    discipline = "architecture"
    severity_default = "high"
    rule_logic_type = "count_reconciliation"
    version = "1.0"
    description = "Compara el total de window_symbol detectados en drawing_area con el total de vanos de ventanas declarados en el cuadro técnico."

    def evaluate(self, inputs: RuleInput) -> RuleResult:
        windows = [s for s in inputs.symbols if s.symbol_type == "window_symbol"]
        win_tables = [t for t in inputs.tables if t.table_type == "window_schedule"]

        if not win_tables and not windows:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="not_applicable",
                severity="info",
                title="Sin elementos de ventanas evaluables",
                description="La lámina no contiene símbolos de ventanas ni cuadros de ventanas.",
                confidence=1.0
            )

        if not win_tables:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="insufficient_evidence",
                severity="medium",
                title="Falta Cuadro de Ventanas para Conciliación",
                description=f"Se detectaron {len(windows)} símbolos de ventanas pero no existe un cuadro de ventanas en la lámina.",
                recommendation="Verificar si el cuadro de vanos se encuentra en una lámina separada.",
                evidence_refs={"detected_windows_count": len(windows), "symbols": [w.id for w in windows]},
                observed_value={"detected_windows": len(windows)},
                confidence=0.85,
                requires_human_review=True,
                review_reason="MISSING_WINDOW_TABLE",
                review_task_type="insufficient_evidence_review"
            )

        table_ref = win_tables[0]
        cells = inputs.cells_by_table.get(table_ref.id, [])
        declared_count = 0

        cant_col_idx = None
        for c in cells:
            if c.is_header and re.search(r"(CANT|CANTIDAD|QTY)", c.text.upper()):
                cant_col_idx = c.column_index
                break

        if cant_col_idx is not None:
            for c in cells:
                if not c.is_header and c.column_index == cant_col_idx:
                    val_match = re.search(r"\d+", c.text)
                    if val_match:
                        declared_count += int(val_match.group())
        else:
            declared_count = max(0, table_ref.row_count - 1)

        detected_count = len(windows)
        delta = detected_count - declared_count

        evidence = {
            "table_id": table_ref.id,
            "table_title": table_ref.title,
            "declared_windows_count": declared_count,
            "detected_windows_count": detected_count,
            "symbols": [w.id for w in windows]
        }

        if delta == 0:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="passed",
                severity="info",
                title="Conteo de Ventanas Conciliado Exitosamente",
                description=f"El total de {detected_count} ventanas detectadas coincide con las {declared_count} declaradas en cuadro.",
                evidence_refs=evidence,
                expected_value=declared_count,
                observed_value=detected_count,
                delta=0,
                confidence=0.95
            )
        else:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="failed",
                severity="high",
                title=f"Discrepancia en Conteo de Ventanas (Delta: {delta:+d})",
                description=f"Se detectaron {detected_count} ventanas en el plano pero el cuadro declara {declared_count}.",
                recommendation="Revisar numeración de tipos de ventana en planta versus cuadro de especificaciones.",
                evidence_refs=evidence,
                expected_value=declared_count,
                observed_value=detected_count,
                delta=delta,
                confidence=0.90,
                requires_human_review=True,
                review_reason=f"WINDOW_COUNT_MISMATCH_DELTA_{delta}",
                review_task_type="rule_finding_review"
            )


class TitleBlockRequiredFieldsRule(BaseRule):
    """RULE_TITLE_BLOCK_REQUIRED_FIELDS_V1: Valida que la viñeta posea código de lámina, escala y revisión."""
    code = "RULE_TITLE_BLOCK_REQUIRED_FIELDS_V1"
    name = "Integridad de Campos Críticos de Viñeta"
    category = "document_integrity"
    discipline = "general"
    severity_default = "critical"
    rule_logic_type = "field_presence"
    version = "1.0"
    description = "Verifica la presencia obligatoria de sheet_code, revision y scale_text en la viñeta técnica."

    def evaluate(self, inputs: RuleInput) -> RuleResult:
        tb = inputs.title_block
        if not tb:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="failed",
                severity="critical",
                title="Viñeta Técnica No Detectada o Inexistente",
                description="La lámina no posee una viñeta técnica extraída válida.",
                recommendation="Verificar que el plano contenga rótulo normalizado en la esquina inferior derecha.",
                confidence=0.95,
                requires_human_review=True,
                review_reason="MISSING_TITLE_BLOCK",
                review_task_type="rule_finding_review"
            )

        missing_fields = []
        if not tb.sheet_code:
            missing_fields.append("sheet_code")
        if not tb.scale_text:
            missing_fields.append("scale_text")
        if not tb.revision:
            missing_fields.append("revision")

        evidence = {
            "title_block_id": tb.id,
            "sheet_code": tb.sheet_code,
            "scale_text": tb.scale_text,
            "revision": tb.revision,
            "match_score": tb.match_score
        }

        if not missing_fields:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="passed",
                severity="info",
                title="Campos Críticos de Viñeta Completos",
                description=f"La lámina contiene código ({tb.sheet_code}), escala ({tb.scale_text}) y revisión ({tb.revision}).",
                evidence_refs=evidence,
                confidence=0.98
            )
        else:
            sev = "critical" if "sheet_code" in missing_fields else "high"
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="failed",
                severity=sev,
                title=f"Campos Obligatorios de Viñeta Ausentes: {', '.join(missing_fields)}",
                description=f"La viñeta técnica carece de metadatos indispensables para control documental: {', '.join(missing_fields)}.",
                recommendation="Completar los campos faltantes en el rótulo técnico antes de la emisión oficial.",
                evidence_refs=evidence,
                expected_value=["sheet_code", "scale_text", "revision"],
                observed_value=[k for k in ["sheet_code", "scale_text", "revision"] if k not in missing_fields],
                delta=missing_fields,
                confidence=0.95,
                requires_human_review=True,
                review_reason=f"MISSING_TITLE_BLOCK_FIELDS_{'_'.join(missing_fields).upper()}",
                review_task_type="rule_finding_review"
            )


class TitleBlockScaleValidRule(BaseRule):
    """RULE_TITLE_BLOCK_SCALE_VALID_V1: Valida que la escala declarada tenga un formato técnico permitido."""
    code = "RULE_TITLE_BLOCK_SCALE_VALID_V1"
    name = "Validez de Formato de Escala Técnica"
    category = "document_integrity"
    discipline = "general"
    severity_default = "medium"
    rule_logic_type = "scale_format"
    version = "1.0"
    description = "Valida que scale_text cumpla con formatos estándar (ej: 1:50, 1:100, 1:20, INDICADAS, S/E)."

    VALID_SCALE_PATTERN = r"^(1:\d+|INDICADAS?|S/E|SIN ESCALA|INDICADA|ESC\.\s*1:\d+)$"

    def evaluate(self, inputs: RuleInput) -> RuleResult:
        tb = inputs.title_block
        if not tb or not tb.scale_text:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="insufficient_evidence",
                severity="low",
                title="Sin Escala Para Validar Formato",
                description="No se dispone del texto de escala de la viñeta.",
                confidence=0.90
            )

        clean_scale = tb.scale_text.strip().upper()
        if re.match(self.VALID_SCALE_PATTERN, clean_scale):
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="passed",
                severity="info",
                title="Escala Técnica Válida",
                description=f"La escala '{tb.scale_text}' cumple con la convención estándar arquitectónica.",
                evidence_refs={"scale_text": tb.scale_text},
                observed_value=tb.scale_text,
                confidence=0.95
            )
        else:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="warning",
                severity="medium",
                title=f"Formato de Escala No Estándar: '{tb.scale_text}'",
                description=f"El texto de escala '{tb.scale_text}' no cumple con el formato estándar (1:50, 1:100, INDICADAS).",
                recommendation="Normalizar la rotulación de escala según convención NCh/ISO.",
                evidence_refs={"scale_text": tb.scale_text},
                expected_value="1:50, 1:100, INDICADAS",
                observed_value=tb.scale_text,
                confidence=0.88,
                requires_human_review=False
            )


class RequiredTablesRule(BaseRule):
    """RULE_REQUIRED_TABLES_BY_DOCUMENT_TYPE_V1: Verifica presencia de cuadros técnicos obligatorios según el plano."""
    code = "RULE_REQUIRED_TABLES_BY_DOCUMENT_TYPE_V1"
    name = "Presencia de Cuadros Técnicos Obligatorios"
    category = "document_integrity"
    discipline = "architecture"
    severity_default = "medium"
    rule_logic_type = "table_presence"
    version = "1.0"
    description = "Verifica que láminas de planta de arquitectura contengan cuadro de vanos o superficies."

    def evaluate(self, inputs: RuleInput) -> RuleResult:
        # Evaluar si la lámina es de arquitectura y tiene dibujo
        is_arch = (inputs.sheet and inputs.sheet.sheet_code and inputs.sheet.sheet_code.startswith("ARQ")) or \
                  (inputs.title_block and inputs.title_block.discipline == "architecture")

        if not is_arch:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="not_applicable",
                severity="info",
                title="No Aplica a Láminas No Arquitectónicas",
                description="La regla solo aplica a planos de la disciplina arquitectura.",
                confidence=1.0
            )

        table_types = [t.table_type for t in inputs.tables]
        has_vanos_or_area = any(t in ["door_schedule", "window_schedule", "area_schedule"] for t in table_types)

        evidence = {
            "tables_found_count": len(inputs.tables),
            "table_types": table_types
        }

        if has_vanos_or_area:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="passed",
                severity="info",
                title="Cuadros Técnicos Obligatorios Presentes",
                description=f"La lámina contiene cuadros técnicos esperados: {', '.join(set(table_types))}.",
                evidence_refs=evidence,
                confidence=0.92
            )
        else:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="warning",
                severity="medium",
                title="Lámina de Arquitectura Sin Cuadro de Vanos ni Superficies",
                description="No se detectaron tablas técnicas de vanos (puertas/ventanas) ni cuadro de superficies en la lámina.",
                recommendation="Verificar si la memoria explicativa o lámina general incluye estos cuadros.",
                evidence_refs=evidence,
                expected_value=["door_schedule", "window_schedule", "area_schedule"],
                observed_value=table_types,
                confidence=0.85,
                requires_human_review=False
            )


class NormativeMinDoorWidthRule(BaseRule):
    """RULE_NORMATIVE_MIN_WIDTH_DOOR_V1: Valida ancho mínimo libre de puertas según criterio normativo de normative_memory."""
    code = "RULE_NORMATIVE_MIN_WIDTH_DOOR_V1"
    name = "Validación Normativa de Ancho Mínimo de Puertas (OGUC 4.1.7)"
    category = "normative_compliance"
    discipline = "architecture"
    severity_default = "critical"
    rule_logic_type = "normative_threshold"
    version = "1.0"
    description = "Compara el ancho de las puertas extraídas contra el estándar normativo aprobado (mínimo 0.80 m)."

    def evaluate(self, inputs: RuleInput) -> RuleResult:
        # Buscar criterio en normative_criteria si existe
        min_width_limit = 0.80 # 80 cm estándar OGUC para puertas de paso principal
        normative_ref = {
            "normative_document": "OGUC (Ordenanza General de Urbanismo y Construcciones)",
            "clause": "Artículo 4.1.7",
            "criterion": "Ancho libre mínimo de puertas de escape y recintos habitables: 0.80 m"
        }

        door_symbols = [s for s in inputs.symbols if s.symbol_type == "door_symbol"]
        door_tables = [t for t in inputs.tables if t.table_type in ["door_schedule", "window_schedule"]]

        # Extraer anchos observados
        widths: List[Dict[str, Any]] = []

        # 1. Desde atributos de símbolos
        for s in door_symbols:
            if s.attributes and "width_m" in s.attributes:
                widths.append({
                    "source": "symbol_attribute",
                    "symbol_id": s.id,
                    "width": float(s.attributes["width_m"])
                })

        # 2. Desde celdas de cuadro de puertas si existen
        for t in door_tables:
            cells = inputs.cells_by_table.get(t.id, [])
            ancho_col = None
            for c in cells:
                if c.is_header and re.search(r"(ANCHO|WIDTH|L)", c.text.upper()):
                    ancho_col = c.column_index
                    break
            if ancho_col is not None:
                for c in cells:
                    if not c.is_header and c.column_index == ancho_col:
                        val_m = re.search(r"(\d+(\.\d+)?)", c.text)
                        if val_m:
                            widths.append({
                                "source": "table_cell",
                                "table_id": t.id,
                                "cell_id": c.id,
                                "width": float(val_m.group(1))
                            })

        if not widths:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="insufficient_evidence",
                severity="low",
                title="Sin Datos Dimensionales Suficientes de Puertas",
                description="No se dispone de cotas de ancho de puertas en símbolos ni en cuadro para verificar el criterio normativo.",
                evidence_refs={"normative": normative_ref},
                confidence=0.80
            )

        violating_doors = [w for w in widths if w["width"] < min_width_limit]

        evidence = {
            "normative": normative_ref,
            "min_width_required_m": min_width_limit,
            "evaluated_doors_count": len(widths),
            "violating_doors": violating_doors
        }

        if not violating_doors:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="passed",
                severity="info",
                title="Cumplimiento Normativo de Ancho Mínimo de Puertas",
                description=f"Todas las {len(widths)} puertas evaluadas cumplen con el ancho mínimo de {min_width_limit:.2f} m.",
                evidence_refs=evidence,
                expected_value=f">= {min_width_limit} m",
                confidence=0.94
            )
        else:
            min_found = min(w["width"] for w in violating_doors)
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="failed",
                severity="critical",
                title=f"Incumplimiento Normativo: {len(violating_doors)} Puerta(s) con Ancho < {min_width_limit} m (Mínimo: {min_found} m)",
                description=f"Se detectaron puertas con ancho inferior a los {min_width_limit} m exigidos por {normative_ref['clause']} de la {normative_ref['normative_document']}.",
                recommendation=f"Ajustar vanos a un ancho libre no menor a {min_width_limit} m.",
                evidence_refs=evidence,
                expected_value=f">= {min_width_limit} m",
                observed_value=f"{min_found} m",
                delta=round(min_found - min_width_limit, 2),
                confidence=0.92,
                requires_human_review=True,
                review_reason="NORMATIVE_VIOLATION_DOOR_WIDTH",
                review_task_type="normative_rule_review"
            )
