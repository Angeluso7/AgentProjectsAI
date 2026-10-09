import re
from typing import Dict, Any, List, Optional
from app.services.rules.base import BaseRule
from app.services.rules.contracts import RuleInput, RuleResult


class SymUnknown001Rule(BaseRule):
    """SYM-UNKNOWN-001: Detecta símbolos no reconocidos o fuera del catálogo canónico ISA-5.1."""
    code = "SYM-UNKNOWN-001"
    name = "Detección de Símbolos No Reconocidos en P&ID"
    category = "normative_compliance"
    discipline = "PIPING"
    severity_default = "high"
    rule_logic_type = "symbol_recognition_validation"
    version = "1.0"
    description = "Identifica símbolos gráficos en el diagrama P&ID cuya geometría o descriptor no coincide con ninguna plantilla del catálogo canónico aprobado (ISA-5.1)."

    # Metadatos canónicos
    rule_scope = "specialty"
    execution_phase = 6
    priority = 20
    source_status = "approved"
    requires_data = ["detected_symbols"]
    applicable_document_types = ["P&ID", "DIAGRAM", "PLAN"]

    def evaluate(self, inputs: RuleInput) -> RuleResult:
        if not inputs.symbols:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="not_evaluable",
                severity="info",
                title="No se encontraron símbolos para revisar",
                description="No se detectaron dibujos de símbolos en este plano. / Detalle técnico: No se han extraído candidatos geométricos o símbolos gráficos en la lámina para verificar reconocimiento contra catálogo canónico ISA-5.1.",
                confidence=1.0,
                verdict="no_verificable",
                not_evaluable_reason_code="EXTRACTION_FAILED",
                not_evaluable_reason_message="La etapa de extracción de simbología no detectó símbolos en este documento.",
                missing_requirements=["detected_symbols"],
                recommended_action="Ejecutar o reintentar el procesamiento de detección de símbolos en el documento."
            )

        unknown_symbols = []
        for s in inputs.symbols:
            evidence = getattr(s, "match_evidence", {}) or {}
            is_rec = getattr(s, "is_recognized", None)
            if is_rec is None and isinstance(evidence, dict):
                is_rec = evidence.get("is_recognized")
            stype = getattr(s, "symbol_type", "") or getattr(s, "canonical_name", "") or (evidence.get("canonical_name", "") if isinstance(evidence, dict) else "") or ""
            confidence = getattr(s, "confidence", 1.0)
            tag = getattr(s, "tag_or_code", "") or (evidence.get("tag_or_code", "") if isinstance(evidence, dict) else "") or ""

            # Criterio de símbolo desconocido
            if is_rec is False or stype.lower() in ["unknown", "unknown_symbol", "sym-unknown-001"] or tag == "SYM-UNKNOWN-001":
                unknown_symbols.append(s)
            elif confidence is not None and confidence < 0.40 and not stype:
                unknown_symbols.append(s)

        total_detected = len(inputs.symbols)
        unknown_count = len(unknown_symbols)

        evidence = {
            "total_symbols_detected": total_detected,
            "unknown_symbols_count": unknown_count,
            "unknown_symbol_ids": [getattr(s, "id", str(idx)) for idx, s in enumerate(unknown_symbols)]
        }

        if unknown_count == 0:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="passed",
                severity="info",
                title="Todos los símbolos del plano fueron reconocidos",
                description=f"Todos los {total_detected} símbolos del plano coinciden con la lista oficial. / Detalle técnico: Los {total_detected} símbolos analizados en el plano están reconocidos en el catálogo canónico ISA-5.1.",
                evidence_refs=evidence,
                expected_value=0,
                observed_value=0,
                delta=0,
                confidence=0.95,
                verdict="cumple"
            )

        # Agrupar símbolos desconocidos por firma/tipo (Regla de negocio: un hallazgo por grupo, no uno por ocurrencia)
        unknown_groups_map: Dict[str, List[Any]] = {}
        for s in unknown_symbols:
            grp_key = getattr(s, "symbol_type", "unknown") or "unknown"
            if grp_key not in unknown_groups_map:
                unknown_groups_map[grp_key] = []
            unknown_groups_map[grp_key].append(s)

        findings = []
        for idx, (grp_key, sym_list) in enumerate(unknown_groups_map.items(), start=1):
            rep = sym_list[0]
            display_code = f"U-{idx:03d}"
            occ_count = len(sym_list)
            occ_ids = [getattr(s, "id", None) for s in sym_list if getattr(s, "id", None)]
            rep_id = getattr(rep, "id", None)
            bbox = getattr(rep, "bbox", None) or getattr(rep, "symbol_crop_bbox", None) or getattr(rep, "bounding_box", None)

            findings.append({
                "symbol_id": rep_id,
                "title": f"Símbolo {display_code}: {occ_count} dibujo(s) que no coinciden con la lista oficial",
                "description": f"Hay {occ_count} dibujo(s) en el plano que parecen símbolos pero no están en la lista oficial. / Detalle técnico: El grupo '{display_code}' cuenta con {occ_count} ocurrencias detectadas con geometría técnica válida sin plantilla aprobada en el catálogo canónico ISA-5.1.",
                "bbox": bbox,
                "severity": "high",
                "recommendation": "Revisar la imagen del símbolo para confirmar si es un componente válido y agregarlo a la biblioteca, o pedir aclaración al proyectista.",
                "evidence_refs": {
                    "display_code": display_code,
                    "total_occurrences": occ_count,
                    "occurrence_ids": occ_ids,
                    "representative_occurrence_id": rep_id
                }
            })

        return RuleResult(
            rule_code=self.code,
            rule_name=self.name,
            status="failed",
            severity="high",
            title=f"Hay {unknown_count} símbolo(s) en el plano que el sistema no pudo identificar todavía",
            description=f"Se encontraron {unknown_count} dibujos en el plano que no coinciden con los símbolos conocidos del catálogo. / Detalle técnico: Se detectaron {unknown_count} elementos gráficos de cañerías sin correspondencia en el catálogo ISA-5.1 aprobado.",
            recommendation="Revisar cada símbolo no identificado para incorporar a la biblioteca del proyecto o solicitar aclaración al proyectista.",
            evidence_refs=evidence,
            expected_value=0,
            observed_value=unknown_count,
            delta=unknown_count,
            confidence=0.90,
            verdict="no_cumple",
            requires_human_review=True,
            review_reason="UNKNOWN_SYMBOLS_DETECTED",
            review_task_type="symbol_unknown_review",
            findings_list=findings
        )


class SymAmbiguous001Rule(BaseRule):
    """SYM-AMBIGUOUS-001: Detecta símbolos con conflicto de clasificación (margen top-1 vs top-2 < 15%)."""
    code = "SYM-AMBIGUOUS-001"
    name = "Conflicto de Clasificación de Símbolos Ambiguos"
    category = "normative_compliance"
    discipline = "PIPING"
    severity_default = "medium"
    rule_logic_type = "classification_ambiguity"
    version = "1.0"
    description = "Detecta símbolos con conflicto de clasificación donde la diferencia de confianza entre la primera y segunda alternativa es inferior al margen de certidumbre (< 15%)."

    rule_scope = "specialty"
    execution_phase = 6
    priority = 25
    source_status = "approved"
    requires_data = ["detected_symbols"]
    applicable_document_types = ["P&ID", "DIAGRAM"]

    def evaluate(self, inputs: RuleInput) -> RuleResult:
        if not inputs.symbols:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="not_evaluable",
                severity="info",
                title="No se encontraron símbolos para evaluar dudas",
                description="No hay símbolos extraídos en el plano para analizar si son dudosos. / Detalle técnico: No se dispone de símbolos extraídos para análisis de ambigüedad clasificatoria.",
                confidence=1.0,
                verdict="no_verificable",
                not_evaluable_reason_code="EXTRACTION_FAILED",
                not_evaluable_reason_message="No hay símbolos extraídos en el plano.",
                missing_requirements=["detected_symbols"],
                recommended_action="Completar la extracción de simbología."
            )

        ambiguous = []
        for s in inputs.symbols:
            metadata = getattr(s, "metadata_info", {}) or {}
            is_ambiguous = metadata.get("is_ambiguous", False) or getattr(s, "is_ambiguous", False)
            top1_conf = metadata.get("top1_confidence")
            top2_conf = metadata.get("top2_confidence")

            if is_ambiguous:
                ambiguous.append(s)
            elif top1_conf is not None and top2_conf is not None:
                if abs(float(top1_conf) - float(top2_conf)) < 0.15:
                    ambiguous.append(s)

        if not ambiguous:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="passed",
                severity="info",
                title="Todos los símbolos se identificaron con total claridad",
                description=f"Cada uno de los {len(inputs.symbols)} símbolos tiene una forma clara sin confusión con otros componentes. / Detalle técnico: Los {len(inputs.symbols)} símbolos poseen clasificación unívoca sin ambigüedad relevante (margen de confianza >= 15%).",
                evidence_refs={"total_symbols": len(inputs.symbols), "ambiguous_count": 0},
                confidence=0.95,
                verdict="cumple"
            )

        findings = []
        for s in ambiguous:
            s_id = getattr(s, "id", None)
            bbox = getattr(s, "bbox", None) or getattr(s, "bounding_box", None)
            findings.append({
                "symbol_id": s_id,
                "title": f"Símbolo con dibujo dudoso (ID: {s_id or 'N/A'})",
                "description": "El dibujo se parece a dos tipos de componentes al mismo tiempo. / Detalle técnico: Existe solape o proximidad estrecha de probabilidades (< 15%) entre dos clases de símbolos.",
                "bbox": bbox,
                "severity": "medium",
                "recommendation": "Mirar el dibujo para confirmar qué tipo de válvula es (por ejemplo, si es compuerta o globo con flecha de flujo)."
            })

        return RuleResult(
            rule_code=self.code,
            rule_name=self.name,
            status="warning",
            severity="medium",
            title=f"Hay {len(ambiguous)} símbolo(s) que se parecen a más de un componente a la vez",
            description=f"{len(ambiguous)} componentes en el plano tienen una forma que genera dudas entre dos opciones posibles. / Detalle técnico: {len(ambiguous)} símbolo(s) tienen una diferencia de confianza < 15% entre sus principales alternativas clasificatorias.",
            recommendation="Confirmar visualmente las ocurrencias dudosas para asegurar que se identifique la válvula o equipo correcto.",
            evidence_refs={"total_symbols": len(inputs.symbols), "ambiguous_count": len(ambiguous)},
            confidence=0.85,
            verdict="no_cumple",
            requires_human_review=True,
            review_reason="SYMBOL_CLASSIFICATION_AMBIGUITY",
            findings_list=findings
        )


class SymLegendConsistency001Rule(BaseRule):
    """SYM-LEGEND-CONSISTENCY-001: Valida que los símbolos en P&ID figuren en el cuadro de leyendas."""
    code = "SYM-LEGEND-CONSISTENCY-001"
    name = "Consistencia entre Símbolos en Dibujo y Cuadro de Leyenda"
    category = "cross_reconciliation"
    discipline = "PIPING"
    severity_default = "high"
    rule_logic_type = "legend_reconciliation"
    version = "1.0"
    description = "Comprueba que cada clase o tipo de símbolo de válvula/equipo presente en el diagrama P&ID se encuentre formalmente definido en el cuadro de leyendas del proyecto."

    rule_scope = "specialty"
    execution_phase = 6
    priority = 30
    source_status = "approved"
    requires_data = ["detected_symbols", "legend_table"]
    applicable_document_types = ["P&ID", "LEGEND"]

    def evaluate(self, inputs: RuleInput) -> RuleResult:
        # Verificar presencia de tabla de leyenda
        legend_tables = [
            t for t in inputs.tables
            if getattr(t, "table_type", "") in ["legend_table", "symbol_legend", "legend", "cuadro_simbologia"]
            or "LEYENDA" in (getattr(t, "title", "") or "").upper()
            or "SIMBOLOG" in (getattr(t, "title", "") or "").upper()
        ]

        if not legend_tables:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="not_evaluable",
                severity="medium",
                title="No se encontró la tabla de leyenda en el plano",
                description="El plano no incluye un cuadro explicativo de símbolos para comparar. / Detalle técnico: La entrega no contiene un cuadro técnico de leyendas de simbología (legend_table) en los documentos seleccionados.",
                confidence=1.0,
                verdict="no_verificable",
                not_evaluable_reason_code="REQUIRED_DOCUMENT_TYPE_MISSING",
                not_evaluable_reason_message="Falta el cuadro de leyenda de simbología (legend_table) en los documentos seleccionados.",
                missing_requirements=["legend_table"],
                recommended_action="Incorporar la lámina de leyenda de piping (o cuadro de notas y símbolos) a la selección de documentos."
            )

        if not inputs.symbols:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="not_applicable",
                severity="info",
                title="Sin símbolos en el plano para comparar",
                description="No hay símbolos en el dibujo para contrastar contra la tabla de leyendas. / Detalle técnico: No hay símbolos extraídos en el plano para verificar contra la leyenda.",
                confidence=1.0,
                verdict="no_aplica"
            )

        # Extraer nombres o descripciones declaradas en la leyenda
        declared_legend_terms = set()
        for lt in legend_tables:
            cells = inputs.cells_by_table.get(getattr(lt, "id", ""), [])
            for c in cells:
                txt = (getattr(c, "text", "") or "").strip().upper()
                if txt:
                    declared_legend_terms.add(txt)

        # Verificar si las clases de los símbolos detectados están en los términos de leyenda
        unreferenced_symbols = []
        for s in inputs.symbols:
            s_type = (getattr(s, "symbol_type", "") or getattr(s, "canonical_name", "") or "").strip().upper()
            if not s_type or s_type in ["UNKNOWN", "UNKNOWN_SYMBOL"]:
                continue

            # Buscar si el tipo o una subcadena del tipo coincide con la leyenda
            matched = any(s_type in term or term in s_type for term in declared_legend_terms if len(term) >= 3)
            if not matched and declared_legend_terms:
                unreferenced_symbols.append(s)

        if not unreferenced_symbols:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="passed",
                severity="info",
                title="Todos los símbolos usados están explicados en la tabla de leyenda",
                description="Cada componente dibujado en el plano tiene su explicación en la tabla de leyendas. / Detalle técnico: Conciliación exitosa: todos los tipos de símbolos detectados en el plano cuentan con definición en el cuadro de leyendas.",
                evidence_refs={"legend_tables_count": len(legend_tables), "symbols_checked": len(inputs.symbols)},
                confidence=0.90,
                verdict="cumple"
            )

        findings = []
        for s in unreferenced_symbols:
            s_id = getattr(s, "id", None)
            s_type = getattr(s, "symbol_type", "") or getattr(s, "canonical_name", "")
            bbox = getattr(s, "bbox", None) or getattr(s, "bounding_box", None)
            findings.append({
                "symbol_id": s_id,
                "title": f"El componente '{s_type}' está dibujado pero falta en la tabla de leyenda",
                "description": f"Se dibujó '{s_type}' en el plano, pero no figura en la lista explicativa de símbolos. / Detalle técnico: El componente '{s_type}' se utiliza en el diagrama P&ID pero no está listado en la leyenda oficial.",
                "bbox": bbox,
                "severity": "high",
                "recommendation": "Agregar la definición y dibujo del símbolo a la tabla de leyendas del plano."
            })

        return RuleResult(
            rule_code=self.code,
            rule_name=self.name,
            status="failed",
            severity="high",
            title=f"Hay {len(unreferenced_symbols)} símbolo(s) usados en el plano que no están en la tabla de leyenda",
            description=f"{len(unreferenced_symbols)} componentes se dibujaron en el plano pero no figuran en el cuadro explicativo de símbolos. / Detalle técnico: {len(unreferenced_symbols)} componentes en el diagrama P&ID carecen de correspondencia con las entradas declaradas en las tablas de leyenda del proyecto.",
            recommendation="Actualizar la tabla de símbolos del plano para incluir los elementos que faltan y evitar confusiones en obra o compras.",
            evidence_refs={"unreferenced_count": len(unreferenced_symbols), "legend_terms_count": len(declared_legend_terms)},
            expected_value=0,
            observed_value=len(unreferenced_symbols),
            delta=len(unreferenced_symbols),
            confidence=0.88,
            verdict="no_cumple",
            requires_human_review=True,
            review_reason="SYMBOLS_MISSING_IN_LEGEND",
            findings_list=findings
        )


class SymTagMissing001Rule(BaseRule):
    """SYM-TAG-MISSING-001: Valida que toda válvula/equipo en P&ID posea tag de identificación asociado."""
    code = "SYM-TAG-MISSING-001"
    name = "Presencia Obligatoria de Tags en Válvulas y Equipos"
    category = "document_integrity"
    discipline = "PIPING"
    severity_default = "medium"
    rule_logic_type = "tag_presence_validation"
    version = "1.0"
    description = "Valida que toda válvula o instrumento en línea en el plano P&ID posea un tag de identificación único asociado conforme a la norma de rotulado."

    rule_scope = "specialty"
    execution_phase = 6
    priority = 35
    source_status = "approved"
    requires_data = ["detected_symbols"]
    applicable_document_types = ["P&ID", "DIAGRAM"]

    def evaluate(self, inputs: RuleInput) -> RuleResult:
        if not inputs.symbols:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="not_evaluable",
                severity="info",
                title="No se encontraron componentes para verificar etiquetas",
                description="No hay símbolos en el plano para comprobar si tienen código o etiqueta. / Detalle técnico: No se detectaron símbolos de cañería o instrumentación en la lámina para validar rotulado de tags de ingeniería.",
                confidence=1.0,
                verdict="no_verificable",
                not_evaluable_reason_code="EXTRACTION_FAILED",
                not_evaluable_reason_message="No se encontraron símbolos extraídos en la lámina.",
                missing_requirements=["detected_symbols"],
                recommended_action="Procesar la lámina para extracción de simbología."
            )

        untagged = []
        for s in inputs.symbols:
            evidence = getattr(s, "match_evidence", {}) or {}
            tag = getattr(s, "tag_or_code", None)
            if tag is None and isinstance(evidence, dict):
                tag = evidence.get("tag_or_code") or evidence.get("tag")
            stype = getattr(s, "symbol_type", "") or getattr(s, "canonical_name", "") or (evidence.get("canonical_name", "") if isinstance(evidence, dict) else "") or ""

            # Validar si el tag es nulo, vacío o un placeholder genérico sin tag de ingeniería real
            if not tag or not str(tag).strip():
                untagged.append(s)
            elif re.match(r"^SYM-[A-Z0-9\-]+$", str(tag).strip(), re.IGNORECASE) and not re.search(r"\b(V|CV|PV|FV|HV|XV|TI|PI|FI|PSV|RV)-\d+", str(tag).strip()):
                # Es solo un ID de detección artificial, sin tag de proceso asociado
                metadata = getattr(s, "metadata_info", {}) or (evidence if isinstance(evidence, dict) else {}) or {}
                if not metadata.get("process_tag"):
                    untagged.append(s)

        total = len(inputs.symbols)
        if not untagged:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="passed",
                severity="info",
                title="Todos los componentes tienen su etiqueta identificatoria",
                description=f"Cada uno de los {total} componentes del plano tiene su código identificador al lado. / Detalle técnico: Todos los {total} símbolos evaluados en el plano poseen tag de ingeniería asociado conforme a la norma de rotulado.",
                evidence_refs={"total_symbols": total, "untagged_count": 0},
                confidence=0.92,
                verdict="cumple"
            )

        findings = []
        for s in untagged:
            s_id = getattr(s, "id", None)
            stype = getattr(s, "symbol_type", "") or getattr(s, "canonical_name", "") or "Válvula/Equipo"
            bbox = getattr(s, "bbox", None) or getattr(s, "bounding_box", None)
            findings.append({
                "symbol_id": s_id,
                "title": f"Componente '{stype}' sin etiqueta de identificación",
                "description": "Se encontró un componente en el plano que no tiene su código o número de etiqueta al lado. / Detalle técnico: Se detectó componente de cañería en coordenadas de plano sin tag de línea/instrumento asociado.",
                "bbox": bbox,
                "severity": "medium",
                "recommendation": "Escribir el código o etiqueta correspondiente junto a este componente en el plano según el listado de líneas o instrumentos."
            })

        return RuleResult(
            rule_code=self.code,
            rule_name=self.name,
            status="failed" if len(untagged) > 3 else "warning",
            severity="medium",
            title=f"Hay {len(untagged)} componente(s) sin código o etiqueta en el plano",
            description=f"{len(untagged)} componentes en el plano no tienen escrita su etiqueta de identificación o la tienen incompleta. / Detalle técnico: {len(untagged)} componentes en el plano carecen de tag de ingeniería o poseen rotulado incompleto.",
            recommendation="Escribir las etiquetas o códigos faltantes junto a cada válvula o equipo en el plano P&ID.",
            evidence_refs={"total_symbols": total, "untagged_count": len(untagged)},
            expected_value=0,
            observed_value=len(untagged),
            delta=len(untagged),
            confidence=0.88,
            verdict="no_cumple",
            requires_human_review=True,
            review_reason="MISSING_ENGINEERING_TAGS",
            findings_list=findings
        )


class GenDoc001Rule(BaseRule):
    """GEN-DOC-001: Integridad y trazabilidad documental básica del plano/proyecto."""
    code = "GEN-DOC-001"
    name = "Integridad y Trazabilidad Documental Base"
    category = "document_integrity"
    discipline = "GENERAL"
    severity_default = "critical"
    rule_logic_type = "title_block_integrity"
    version = "1.0"
    description = "Verifica los atributos mínimos de trazabilidad del plano: código de lámina, revisión técnica, título formal de entrega y escala/fecha."

    rule_scope = "general"
    execution_phase = 5
    priority = 10
    source_status = "approved"
    requires_data = ["title_block"]
    applicable_document_types = ["P&ID", "PLAN", "DIAGRAM", "DRAWING"]

    def evaluate(self, inputs: RuleInput) -> RuleResult:
        tb = inputs.title_block

        if not tb:
            # Si no hay viñeta extraída
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="not_evaluable",
                severity="critical",
                title="No se encontró la viñeta o carátula del plano",
                description="El sistema no pudo leer la carátula de datos del plano. / Detalle técnico: No se ha extraído la viñeta técnica (title block) del plano para auditar su trazabilidad documental.",
                confidence=1.0,
                verdict="no_verificable",
                not_evaluable_reason_code="DOCUMENT_NOT_PROCESSED",
                not_evaluable_reason_message="La lámina carece de extracción de viñeta técnica en base de datos.",
                missing_requirements=["title_block"],
                recommended_action="Verificar que el plano incluya su viñeta técnica estándar en el borde inferior o lateral."
            )

        missing_fields = []
        sheet_code = getattr(tb, "sheet_code", None) or getattr(tb, "drawing_number", None)
        title = getattr(tb, "sheet_title", None) or getattr(tb, "title", None) or getattr(tb, "sheet_name", None)
        rev = getattr(tb, "revision", None) or getattr(tb, "current_revision", None)

        if not sheet_code or not str(sheet_code).strip():
            missing_fields.append("sheet_code")
        if not title or not str(title).strip():
            missing_fields.append("title")
        if not rev or not str(rev).strip():
            missing_fields.append("revision")

        evidence = {
            "sheet_code": str(sheet_code) if sheet_code else None,
            "title": str(title) if title else None,
            "revision": str(rev) if rev else None,
            "missing_fields": missing_fields
        }

        if not missing_fields:
            return RuleResult(
                rule_code=self.code,
                rule_name=self.name,
                status="passed",
                severity="info",
                title="Los datos principales de la carátula están completos",
                description=f"La lámina {sheet_code} (Revisión {rev}) tiene código, título y número de revisión completos. / Detalle técnico: Lámina {sheet_code} (Rev {rev}): campos críticos de viñeta completos y consistentes.",
                evidence_refs=evidence,
                confidence=0.98,
                verdict="cumple"
            )

        return RuleResult(
            rule_code=self.code,
            rule_name=self.name,
            status="failed",
            severity="critical",
            title=f"A la carátula del plano le faltan datos obligatorios ({', '.join(missing_fields)})",
            description=f"La carátula del plano no indica los siguientes datos clave: {', '.join(missing_fields)}. / Detalle técnico: La viñeta técnica del documento no declara los campos normativos: {', '.join(missing_fields)}.",
            recommendation="Completar los datos que faltan en la carátula del plano (código, título o número de revisión) antes de la entrega formal.",
            evidence_refs=evidence,
            confidence=0.95,
            verdict="no_cumple",
            requires_human_review=True,
            review_reason="MISSING_CRITICAL_TITLE_BLOCK_FIELDS"
        )
