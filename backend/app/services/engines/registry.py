import os
import json
import time
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from app.core.settings import settings
from app.core.logging import logger

CONFIG_FILE_PATH = os.path.join(settings.BASE_DIR, "data", "config", "ai_engines_config.json")

class EngineDefinition(BaseModel):
    id: str
    category: str  # ocr, symbols, layout, tables, embeddings, llm, rules
    provider: str  # PyMuPDF, Tesseract, Baidu, Ultralytics, OpenAI, Google, Anthropic, Local Deterministic
    model_name: str
    version: str
    engine_type: str  # local, open_source, api_cloud, paid_saas
    cost_tier: str    # gratis, pago, mixto
    status: str       # active, inactive, experimental, fallback
    is_active: bool = False
    is_installed: bool = True
    required_credentials: List[str] = []
    has_credentials: bool = True
    disciplines: List[str] = ["all"]
    description: str
    notes: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    latency_ms: Optional[float] = None
    last_tested: Optional[str] = None
    last_error: Optional[str] = None

class EngineRegistry:
    """Registro y orquestador central de motores de IA y pipelines."""

    _DEFAULT_ENGINES: List[Dict[str, Any]] = [
        # --- 1. OCR ---
        {
            "id": "vector_pdf",
            "category": "ocr",
            "provider": "PyMuPDF / Fitz",
            "model_name": "Native PDF Text Layer Extractor",
            "version": "1.28.2",
            "engine_type": "local",
            "cost_tier": "gratis",
            "status": "active",
            "is_active": True,
            "is_installed": True,
            "required_credentials": [],
            "has_credentials": True,
            "disciplines": ["all"],
            "description": "Extracción vectorial nativa directa de texto, rotaciones y cotas de PDFs CAD/BIM.",
            "notes": "Recomendado para planos exportados directamente de Revit, AutoCAD o ArchiCAD (precisión 100%, 0 CER).",
            "parameters": {"scale_dpi": 300, "extract_embedded_fonts": True, "clean_whitespace": True}
        },
        {
            "id": "tesseract",
            "category": "ocr",
            "provider": "Google / Tesseract OCR",
            "model_name": "Tesseract PSM 11 (Sparse Text)",
            "version": "5.5.0",
            "engine_type": "open_source",
            "cost_tier": "gratis",
            "status": "fallback",
            "is_active": False,
            "is_installed": True,
            "required_credentials": [],
            "has_credentials": True,
            "disciplines": ["all"],
            "description": "Motor de OCR clásico para planos escaneados con segmentación de texto disperso (PSM 11).",
            "notes": "Ideal como fallback cuando el plano es una imagen raster o escaneo sin capa vectorial.",
            "parameters": {"psm": 11, "oem": 3, "lang": "spa+eng", "dpi": 300}
        },
        {
            "id": "paddleocr",
            "category": "ocr",
            "provider": "Baidu / PaddlePaddle",
            "model_name": "PP-OCRv4 Multilingual",
            "version": "3.7.0",
            "engine_type": "open_source",
            "cost_tier": "gratis",
            "status": "experimental",
            "is_active": False,
            "is_installed": False,
            "required_credentials": [],
            "has_credentials": True,
            "disciplines": ["all"],
            "description": "Deep Learning OCR con clasificación de orientación angular (0°, 90°, 180°, 270°).",
            "notes": "Requiere instalar el runtime paddlepaddle para aceleración GPU/CPU.",
            "parameters": {"use_angle_cls": True, "lang": "es", "det_db_thresh": 0.3}
        },
        {
            "id": "google_vision_ocr",
            "category": "ocr",
            "provider": "Google Cloud",
            "model_name": "Cloud Vision Document Text Detection",
            "version": "v1",
            "engine_type": "api_cloud",
            "cost_tier": "pago",
            "status": "inactive",
            "is_active": False,
            "is_installed": True,
            "required_credentials": ["GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_API_KEY"],
            "has_credentials": False,
            "disciplines": ["all"],
            "description": "OCR en la nube de alta precisión para documentos complejos y tipografías manuscritas.",
            "notes": "Requiere cuenta GCP activa y credenciales en variables de entorno.",
            "parameters": {"language_hints": ["es", "en"], "enable_symbol_confidence": True}
        },

        # --- 2. SÍMBOLOS ---
        {
            "id": "yolo_sahi_hybrid",
            "category": "symbols",
            "provider": "Ultralytics / SAHI",
            "model_name": "YOLOv11 Object Detection + Sliced Inference",
            "version": "v11.0",
            "engine_type": "local",
            "cost_tier": "gratis",
            "status": "active",
            "is_active": True,
            "is_installed": True,
            "required_credentials": [],
            "has_credentials": True,
            "disciplines": ["architecture", "electrical", "sanitary"],
            "description": "Detección visual de vanos (puertas, ventanas), luminarias, tableros y artefactos por ventanas deslizantes.",
            "notes": "Si los pesos fine-tuned 'yolo_symbols.pt' no están cargados, conmuta automáticamente a template matching.",
            "parameters": {"confidence_threshold": 0.50, "iou_threshold": 0.45, "slice_height": 1024, "slice_width": 1024}
        },
        {
            "id": "template_matcher",
            "category": "symbols",
            "provider": "PlanReview Geometric Engine",
            "model_name": "Canonical Template Matcher & Vector Geometry",
            "version": "v1.0",
            "engine_type": "local",
            "cost_tier": "gratis",
            "status": "fallback",
            "is_active": False,
            "is_installed": True,
            "required_credentials": [],
            "has_credentials": True,
            "disciplines": ["architecture", "structures"],
            "description": "Comparación directa de contornos y geometrías contra librerías de template_memory.",
            "notes": "Motor 100% determinístico sin requerir pesos neuronales externos.",
            "parameters": {"matching_threshold": 0.70, "rotation_invariance": True}
        },
        {
            "id": "openai_vision_symbols",
            "category": "symbols",
            "provider": "OpenAI",
            "model_name": "GPT-4o Vision Zero-Shot Visual Auditor",
            "version": "2024-11-20",
            "engine_type": "api_cloud",
            "cost_tier": "pago",
            "status": "inactive",
            "is_active": False,
            "is_installed": True,
            "required_credentials": ["OPENAI_API_KEY"],
            "has_credentials": False,
            "disciplines": ["all"],
            "description": "Reconocimiento visual multimodal zero-shot para simbología técnica no estándar.",
            "notes": "Requiere API key de OpenAI. Costo por llamada de tokens de imagen.",
            "parameters": {"temperature": 0.0, "max_tokens": 1500, "detail": "high"}
        },

        # --- 3. LAYOUT & REGIONES ---
        {
            "id": "spatial_density",
            "category": "layout",
            "provider": "PlanReview Layout Analyzer",
            "model_name": "Spatial Density & Bounding Box Heuristics",
            "version": "v1.0",
            "engine_type": "local",
            "cost_tier": "gratis",
            "status": "active",
            "is_active": True,
            "is_installed": True,
            "required_credentials": [],
            "has_credentials": True,
            "disciplines": ["all"],
            "description": "Segmenta macro-regiones (área de dibujo, viñeta, notas, cuadros y leyendas) por distribución espacial.",
            "notes": "Altamente eficiente (latencia <10ms) y robusto para láminas DIN A0 a A3.",
            "parameters": {"min_drawing_area_ratio": 0.50, "title_block_bottom_corner": True}
        },
        {
            "id": "layoutlm_v3",
            "category": "layout",
            "provider": "Microsoft / HuggingFace",
            "model_name": "LayoutLMv3 Technical Document Segmentation",
            "version": "v3.0",
            "engine_type": "open_source",
            "cost_tier": "gratis",
            "status": "experimental",
            "is_active": False,
            "is_installed": False,
            "required_credentials": [],
            "has_credentials": True,
            "disciplines": ["all"],
            "description": "Modelo multimodal multimodal de texto + layout + imagen para clasificación fina de bloques.",
            "notes": "Requiere GPU dedicada para inferencia en tiempo real en planos de alta resolución.",
            "parameters": {"confidence_threshold": 0.80}
        },

        # --- 4. TABLAS ---
        {
            "id": "geometric_grid",
            "category": "tables",
            "provider": "PlanReview Morphology Parser",
            "model_name": "Geometric Grid & Line Extractor",
            "version": "v1.0",
            "engine_type": "local",
            "cost_tier": "gratis",
            "status": "active",
            "is_active": True,
            "is_installed": True,
            "required_credentials": [],
            "has_credentials": True,
            "disciplines": ["all"],
            "description": "Detección de rejillas ortogonales y segmentación estructurada de celdas y filas.",
            "notes": "Especializado en cuadros de vanos, cuadros de superficies y tablas de armaduras.",
            "parameters": {"min_cell_area_px": 50, "line_kernel_size": 25, "header_detection": True}
        },
        {
            "id": "table_transformer",
            "category": "tables",
            "provider": "Microsoft / TATR",
            "model_name": "Table Transformer (TATR-v1.1-PubTables)",
            "version": "v1.1",
            "engine_type": "open_source",
            "cost_tier": "gratis",
            "status": "experimental",
            "is_active": False,
            "is_installed": False,
            "required_credentials": [],
            "has_credentials": True,
            "disciplines": ["all"],
            "description": "Deep Learning transformer para tablas sin bordes o tablas con celdas fusionadas complejas.",
            "notes": "Requiere PyTorch y pesos preentrenados de Hugging Face.",
            "parameters": {"structure_threshold": 0.75}
        },

        # --- 5. EMBEDDINGS & BÚSQUEDA ---
        {
            "id": "ontology_lexicon",
            "category": "embeddings",
            "provider": "PlanReview Lexicon Matcher",
            "model_name": "Ontology & Canonical Lexicon Matcher",
            "version": "v1.0",
            "engine_type": "local",
            "cost_tier": "gratis",
            "status": "active",
            "is_active": True,
            "is_installed": True,
            "required_credentials": [],
            "has_credentials": True,
            "disciplines": ["all"],
            "description": "Normalización determinística y sinonimia ontológica (ej: P1 -> DOOR_SINGLE, V1 -> WINDOW).",
            "notes": "Indexado directamente sobre template_memory y ontology_dictionary en PostgreSQL.",
            "parameters": {"case_sensitive": False, "strip_accents": True}
        },
        {
            "id": "openai_embeddings",
            "category": "embeddings",
            "provider": "OpenAI",
            "model_name": "text-embedding-3-small (1536 dims)",
            "version": "v3",
            "engine_type": "api_cloud",
            "cost_tier": "pago",
            "status": "inactive",
            "is_active": False,
            "is_installed": True,
            "required_credentials": ["OPENAI_API_KEY"],
            "has_credentials": False,
            "disciplines": ["all"],
            "description": "Búsqueda semántica vectorial densa para cláusulas normativas y especificaciones técnicas.",
            "notes": "Requiere API key de OpenAI. Integrable con pgvector.",
            "parameters": {"dimensions": 1536}
        },

        # --- 6. LLM / ASISTENTE ---
        {
            "id": "fastapi_rule_reasoner",
            "category": "llm",
            "provider": "PlanReview Logic Engine",
            "model_name": "Deterministic Rule Reasoner & Formatter",
            "version": "v1.0",
            "engine_type": "local",
            "cost_tier": "gratis",
            "status": "active",
            "is_active": True,
            "is_installed": True,
            "required_credentials": [],
            "has_credentials": True,
            "disciplines": ["all"],
            "description": "Motor de explicación estructurada local para hallazgos QA/QC sin dependencias externas.",
            "notes": "Funciona 100% offline y sin costo de inferencia.",
            "parameters": {"strict_formatting": True}
        },
        {
            "id": "google_gemini_flash",
            "category": "llm",
            "provider": "Google DeepMind",
            "model_name": "Gemini 2.0 Flash / Pro",
            "version": "2.0",
            "engine_type": "api_cloud",
            "cost_tier": "mixto",
            "status": "inactive",
            "is_active": False,
            "is_installed": True,
            "required_credentials": ["GEMINI_API_KEY"],
            "has_credentials": False,
            "disciplines": ["all"],
            "description": "Razonamiento multimodal avanzado, auditoría de discrepancias complejas y síntesis ejecutiva.",
            "notes": "Tier gratuito disponible y bajo costo por millón de tokens en tier de pago.",
            "parameters": {"temperature": 0.1, "max_output_tokens": 2048}
        },
        {
            "id": "openai_gpt4o",
            "category": "llm",
            "provider": "OpenAI",
            "model_name": "GPT-4o / GPT-4o-mini",
            "version": "2024-11",
            "engine_type": "api_cloud",
            "cost_tier": "pago",
            "status": "inactive",
            "is_active": False,
            "is_installed": True,
            "required_credentials": ["OPENAI_API_KEY"],
            "has_credentials": False,
            "disciplines": ["all"],
            "description": "Modelo de lenguaje avanzado para análisis de memorias explicativas y resolución de conflictos.",
            "notes": "Requiere suscripción o créditos activos en OpenAI Platform.",
            "parameters": {"temperature": 0.2, "max_tokens": 2000}
        },

        # --- 7. REGLAS QA/QC ---
        {
            "id": "qa_qc_deterministic_engine",
            "category": "rules",
            "provider": "PlanReview QA/QC Core",
            "model_name": "Deterministic Cross-Discipline Geometric Validator",
            "version": "v1.0",
            "engine_type": "local",
            "cost_tier": "gratis",
            "status": "active",
            "is_active": True,
            "is_installed": True,
            "required_credentials": [],
            "has_credentials": True,
            "disciplines": ["architecture", "structures", "general"],
            "description": "Evaluador determinístico de 6 reglas de control de calidad (vanos, anchos, viñeta, tablas).",
            "notes": "Garantiza trazabilidad matemática y reproducibilidad 100% estricta de auditorías.",
            "parameters": {"min_door_width_m": 0.80, "auto_escalate_critical": True, "strict_title_block": True}
        }
    ]

    def __init__(self):
        self._engines: Dict[str, Dict[str, EngineDefinition]] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        """Carga la configuración de motores desde archivo persistente o valores por defecto."""
        # Inicializar estructura vacía por categoría
        categories = ["ocr", "symbols", "layout", "tables", "embeddings", "llm", "rules"]
        for cat in categories:
            self._engines[cat] = {}

        # Cargar valores por defecto
        for d in self._DEFAULT_ENGINES:
            eng = EngineDefinition(**d)
            # Validar si tiene credenciales en variables de entorno
            if eng.required_credentials:
                has_all = all(bool(os.getenv(k)) for k in eng.required_credentials)
                eng.has_credentials = has_all
            self._engines[eng.category][eng.id] = eng

        # Cargar sobrescrituras de configuración guardadas
        if os.path.exists(CONFIG_FILE_PATH):
            try:
                with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                    saved_data = json.load(f)
                    for cat, engines_dict in saved_data.items():
                        if cat in self._engines:
                            for eng_id, overrides in engines_dict.items():
                                if eng_id in self._engines[cat]:
                                    current = self._engines[cat][eng_id]
                                    if "is_active" in overrides:
                                        current.is_active = overrides["is_active"]
                                    if "parameters" in overrides:
                                        current.parameters.update(overrides["parameters"])
                                    if "status" in overrides:
                                        current.status = overrides["status"]
            except Exception as e:
                logger.warning(f"Error cargando archivo de configuración de motores: {e}")

    def _save_registry(self) -> None:
        """Persiste la configuración de motores seleccionados y parámetros en disco."""
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE_PATH), exist_ok=True)
            export_data: Dict[str, Dict[str, Any]] = {}
            for cat, engines_dict in self._engines.items():
                export_data[cat] = {}
                for eng_id, eng in engines_dict.items():
                    export_data[cat][eng_id] = {
                        "is_active": eng.is_active,
                        "status": eng.status,
                        "parameters": eng.parameters
                    }
            with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            logger.info("Configuración de motores de IA guardada exitosamente.")
        except Exception as e:
            logger.error(f"Error al guardar configuración de motores: {e}")

    def list_engines(self, category: Optional[str] = None) -> List[EngineDefinition]:
        """Lista todos los motores registrados, opcionalmente filtrados por categoría."""
        if category:
            if category not in self._engines:
                return []
            return list(self._engines[category].values())
        
        all_engines: List[EngineDefinition] = []
        for cat_dict in self._engines.values():
            all_engines.extend(cat_dict.values())
        return all_engines

    def get_engine(self, category: str, engine_id: str) -> Optional[EngineDefinition]:
        if category in self._engines and engine_id in self._engines[category]:
            return self._engines[category][engine_id]
        return None

    def get_active_engine(self, category: str) -> Optional[EngineDefinition]:
        """Obtiene el motor actualmente activo para una categoría."""
        if category not in self._engines:
            return None
        for eng in self._engines[category].values():
            if eng.is_active:
                return eng
        # Fallback al primero si ninguno está marcado activo
        first = next(iter(self._engines[category].values()), None)
        if first:
            first.is_active = True
            return first
        return None

    def set_active_engine(self, category: str, engine_id: str) -> EngineDefinition:
        """Conmuta el motor activo para una categoría y desactiva los demás."""
        if category not in self._engines:
            raise ValueError(f"Categoría '{category}' no existe.")
        if engine_id not in self._engines[category]:
            raise ValueError(f"Motor '{engine_id}' no registrado en categoría '{category}'.")

        target = self._engines[category][engine_id]
        
        # Desactivar los otros motores de la categoría
        for eid, eng in self._engines[category].items():
            eng.is_active = (eid == engine_id)
            if eid != engine_id and eng.status == "active":
                eng.status = "inactive"

        target.is_active = True
        target.status = "active"
        self._save_registry()
        logger.info(f"Motor '{engine_id}' activado para categoría '{category}'.")
        return target

    def update_engine_config(self, category: str, engine_id: str, parameters: Dict[str, Any]) -> EngineDefinition:
        """Actualiza los parámetros de configuración de un motor."""
        eng = self.get_engine(category, engine_id)
        if not eng:
            raise ValueError(f"Motor '{engine_id}' en categoría '{category}' no encontrado.")

        eng.parameters.update(parameters)
        self._save_registry()
        return eng

    def update_credentials(self, category: str, engine_id: str, credentials: Dict[str, str]) -> EngineDefinition:
        """Guarda credenciales de API en el entorno para el motor especificado."""
        eng = self.get_engine(category, engine_id)
        if not eng:
            raise ValueError(f"Motor '{engine_id}' en categoría '{category}' no encontrado.")

        for key, val in credentials.items():
            if key in eng.required_credentials and val:
                os.environ[key] = val

        # Re-evaluar has_credentials
        eng.has_credentials = all(bool(os.getenv(k)) for k in eng.required_credentials)
        self._save_registry()
        return eng

    def test_engine_health(self, category: str, engine_id: str) -> Dict[str, Any]:
        """Ejecuta una prueba de conectividad y latencia sobre el motor."""
        eng = self.get_engine(category, engine_id)
        if not eng:
            raise ValueError(f"Motor '{engine_id}' en categoría '{category}' no encontrado.")

        t0 = time.time()
        success = True
        err_msg = None

        if eng.category == "ocr":
            if eng.id == "vector_pdf":
                try:
                    import fitz
                except Exception as e:
                    success, err_msg = False, str(e)
            elif eng.id == "tesseract":
                try:
                    import pytesseract
                    pytesseract.get_tesseract_version()
                except Exception as e:
                    success, err_msg = False, str(e)
            elif eng.id == "paddleocr":
                try:
                    import paddleocr
                    import paddle
                except Exception as e:
                    success, err_msg = False, "PaddlePaddle runtime no instalado."

        elif eng.category == "symbols":
            if eng.id == "yolo_sahi_hybrid":
                weights_path = os.path.join(settings.BASE_DIR, "data", "models", "yolo_symbols.pt")
                if not os.path.exists(weights_path):
                    err_msg = "Pesos 'yolo_symbols.pt' no encontrados. Operando en modo fallback heurístico."

        elif eng.category in ["llm", "embeddings"] and eng.engine_type == "api_cloud":
            if not eng.has_credentials:
                success = False
                err_msg = f"Faltan credenciales requeridas: {eng.required_credentials}"

        latency = round((time.time() - t0) * 1000, 1)
        eng.latency_ms = max(latency, 1.0)
        eng.last_tested = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        eng.last_error = err_msg

        return {
            "engine_id": eng.id,
            "category": eng.category,
            "status": "OK" if success and not err_msg else ("FALLBACK" if not success or err_msg else "ERROR"),
            "latency_ms": eng.latency_ms,
            "last_tested": eng.last_tested,
            "error": err_msg
        }

# Instancia Singleton
engine_registry = EngineRegistry()
