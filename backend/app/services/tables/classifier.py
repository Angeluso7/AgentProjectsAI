import re
from typing import List, Dict, Any, Tuple

class TableClassifier:
    """Clasificador heurístico y trazable del tipo de tabla técnica."""

    KEYWORDS = {
        "window_schedule": [
            r"CUADRO.*VENTANA", r"CUADRO.*VANOS.*V", r"VENTANAS?", r"TIPO\s*V",
            r"ANTEPECHO", r"VIDRIO", r"TERMOPANEL", r"CRISTAL"
        ],
        "door_schedule": [
            r"CUADRO.*PUERTA", r"CUADRO.*VANOS.*P", r"PUERTAS?", r"TIPO\s*P",
            r"HOJA", r"MARCO", r"CERRADURA", r"SENTIDO.*APERTURA"
        ],
        "area_schedule": [
            r"CUADRO.*SUPERFICIE", r"CUADRO.*AREA", r"SUPERFICIE\s*UTIL",
            r"SUPERFICIE\s*CONSTRUIDA", r"SUPERFICIE\s*TOTAL", r"M2", r"M²",
            r"SUPERFICIE.*PREDIO", r"COEF.*CONSTRUCTIBILIDAD"
        ],
        "load_schedule": [
            r"CUADRO.*CARGA", r"CUADRO.*CIRCUITO", r"TABLERO.*GENERAL",
            r"POTENCIA", r"DISYUNTOR", r"DIFERENCIAL", r"KW", r"KVA", r"FASE"
        ],
        "material_list": [
            r"LISTA.*MATERIAL", r"ESPECIFICACI.*MATERIAL", r"PARTIDA",
            r"CANTIDAD", r"UNIDAD", r"PROVEEDOR", r"CODIGO.*ITEM"
        ]
    }

    def classify_table(
        self,
        title: str,
        headers: List[str],
        sample_cells: List[str]
    ) -> Tuple[str, float, str]:
        """Clasifica el tipo de tabla retornando (table_type, confidence, explanation)."""
        combined_text = f"{title.upper()} {' '.join(h.upper() for h in headers)} {' '.join(c.upper() for c in sample_cells)}"
        
        scores: Dict[str, float] = {}

        for table_type, patterns in self.KEYWORDS.items():
            match_count = 0
            for pat in patterns:
                if re.search(pat, combined_text):
                    match_count += 1
            if match_count > 0:
                # Si el título coincide directamente, da un gran boost
                title_match = any(re.search(pat, title.upper()) for pat in patterns)
                base_score = 0.60 + (match_count * 0.10)
                if title_match:
                    base_score += 0.25
                scores[table_type] = min(base_score, 0.98)

        if not scores:
            return "unknown_table", 0.40, "No se encontraron patrones léxicos suficientes para clasificar la tabla."

        best_type = max(scores, key=scores.get)
        best_conf = scores[best_type]
        explanation = f"Clasificada como '{best_type}' con confianza {best_conf:.2f} basada en coincidencia de título y encabezados."
        return best_type, best_conf, explanation
