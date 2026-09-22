from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, model_validator

class LanguageDetectionRequest(BaseModel):
    text: str = Field(..., description="Texto de entrada a analizar para detectar idioma")

class LanguageDetectionResponse(BaseModel):
    detected_language: str = Field(..., description="Código de idioma detectado (es, en, pt, fr, de, it, zh, ja, ko, ar, otro)")
    language_name: str = Field(..., description="Nombre del idioma detectado en español")
    confidence: float = Field(..., description="Nivel de confianza de la detección (0.0 a 1.0)")

class TranslationRequest(BaseModel):
    source_entity_type: str = Field(..., description="Tipo de entidad fuente (extracted_item, source_extraction, rule_document, table_cell)")
    source_entity_id: str = Field(..., description="ID de la entidad fuente")
    target_language: str = Field("es", description="Idioma de destino (default: es)")
    source_language: Optional[str] = Field("auto", description="Idioma de origen (default: auto)")
    fields_to_translate: Dict[str, str] = Field(..., description="Diccionario clave-valor con los campos textuales a traducir (title, description, content_text, etc.)")
    organization_id: Optional[str] = Field(None, description="ID de la organización para tenancy estricta")

    @model_validator(mode="before")
    @classmethod
    def map_legacy_and_alias_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Mapeo tolerante de nombres entre frontend y backend
            if "source_entity_type" not in data and "entity_type" in data:
                data["source_entity_type"] = data["entity_type"]
            if "source_entity_id" not in data and "entity_id" in data:
                data["source_entity_id"] = data["entity_id"]
            if "fields_to_translate" not in data and "source_fields" in data:
                data["fields_to_translate"] = data["source_fields"]
            # Si source_fields/fields_to_translate contiene valores no-string, convertirlos a string
            if "fields_to_translate" in data and isinstance(data["fields_to_translate"], dict):
                data["fields_to_translate"] = {
                    str(k): str(v) if v is not None else ""
                    for k, v in data["fields_to_translate"].items()
                }
        return data

class BatchTranslationRequest(BaseModel):
    target_language: str = Field("es", description="Idioma de destino")
    source_language: Optional[str] = Field("auto", description="Idioma de origen")
    items: List[TranslationRequest] = Field(..., description="Lista de solicitudes individuales a traducir")
    organization_id: Optional[str] = Field(None, description="ID de la organización")

class TranslationResponse(BaseModel):
    id: str
    organization_id: str
    source_entity_type: str
    source_entity_id: str
    source_language: str
    source_language_confidence: Optional[float]
    target_language: str
    source_text_hash: str
    translated_title: Optional[str] = None
    translated_content: Optional[str] = None
    translated_summary: Optional[str] = None
    translated_fields: Dict[str, str] = Field(default_factory=dict)
    provider: str
    model: str
    prompt_version: str
    translation_status: str
    error_message: Optional[str] = None
    cached: bool = False
    created_at: datetime
    updated_at: datetime

    # Propiedades para compatibilidad directa con contratos frontend heredados
    @property
    def entity_type(self) -> str:
        return self.source_entity_type

    @property
    def entity_id(self) -> str:
        return self.source_entity_id

    @property
    def status(self) -> str:
        return self.translation_status

    @property
    def model_id(self) -> str:
        return self.model

    class Config:
        from_attributes = True

class BatchTranslationResponse(BaseModel):
    total_requested: int
    total_completed: int
    total_cached: int
    total_processed: Optional[int] = None
    translations: List[TranslationResponse]

    @model_validator(mode="before")
    @classmethod
    def set_total_processed(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "total_processed" not in data or data["total_processed"] is None:
                data["total_processed"] = data.get("total_completed", 0)
        return data
