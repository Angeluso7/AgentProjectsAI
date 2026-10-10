from enum import Enum
from typing import Generic, TypeVar, Optional, List, Any
from pydantic import BaseModel, Field

class DisciplineEnum(str, Enum):
    ARCHITECTURE = "architecture"
    ELECTRICAL = "electrical"
    STRUCTURAL = "structural"
    PLUMBING = "plumbing"
    HVAC = "hvac"
    MECHANICAL = "mechanical"
    FIRE_SAFETY = "fire_safety"
    FIRE_PROTECTION = "fire_protection"
    TELECOM = "telecom"
    GENERAL = "general"

class SeverityEnum(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class RegionTypeEnum(str, Enum):
    TITLE_BLOCK = "title_block"
    DRAWING_AREA = "drawing_area"
    NOTES = "notes"
    LEGEND = "legend"
    SCHEDULE = "schedule"
    REVISION_TABLE = "revision_table"

class ProjectStageEnum(str, Enum):
    CONCEPTUAL = "Ingeniería Conceptual"
    BASICA = "Ingeniería Básica"
    DETALLE = "Ingeniería de Detalle"
    FACTIBILIDAD = "Factibilidad"
    LICITACION = "Licitación"
    CONSTRUCCION = "Construcción"
    AS_BUILT = "As-Built"

class DeliverableTypeEnum(str, Enum):
    PLANO_GENERAL = "plano_general"
    PLANO_DETALLES = "plano_detalles"
    PLANO_ESTRUCTURAL = "plano_estructural"
    MEMORIA_CALCULO = "memoria_calculo"
    ESPECIFICACIONES_TECNICAS = "especificaciones_tecnicas"
    MECANICA_SUELOS = "mecanica_suelos"
    CUADRO_CARGAS = "cuadro_cargas"
    PLAN_SEGURIDAD = "plan_seguridad"
    OTRO_ENTREGABLE = "otro_entregable"
    # Nuevos tipos de entregable para Piping, Procesos, Instrumentación y Eléctrica
    PLANO_PLANTA = "plano_planta"
    PLANO_CORTE = "plano_corte"
    PLANO_ELEVACION = "plano_elevacion"
    PID_DIAGRAMA = "pid_diagrama"
    DIAGRAMA_UNILINEAL = "diagrama_unilineal"
    ISOMETRICO_TUBERIAS = "isometrico_tuberias"
    HOJA_DE_DATOS = "hoja_de_datos"

class EvidenceReadinessStatusEnum(str, Enum):
    UPLOADED = "uploaded"
    CLASSIFIED = "classified"
    VALIDATED = "validated"
    ELIGIBLE_AS_EVIDENCE = "eligible_as_evidence"
    REJECTED = "rejected"

class AuditVerdictEnum(str, Enum):
    CUMPLE = "cumple"
    NO_CUMPLE = "no_cumple"
    NO_VERIFICABLE = "no_verificable"
    NO_APLICA = "no_aplica"

class UnverifiableReasonEnum(str, Enum):
    MINOR_MISSING = "minor_missing"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    BLOCKED_BY_MISSING_DOC = "blocked_by_missing_doc"
    FORMAL_RFI_REQUIRED = "formal_rfi_required"

class ObservationTypeEnum(str, Enum):
    TECHNICAL_OBSERVATION = "technical_observation" # OBS
    INFORMATION_REQUEST = "information_request"     # RFI
    DOCUMENT_BLOCKER = "document_blocker"           # BLK
    MINOR_MISSING = "minor_missing"                 # MIN

class ObservationStatusEnum(str, Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    ANSWERED = "answered"
    PROVISIONED = "provisioned"
    VALIDATED = "validated"
    CLOSED = "closed"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"

class FindingStatusEnum(str, Enum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    ACCEPTED = "accepted"
    REJECTED_FALSE_POSITIVE = "rejected_false_positive"
    RESOLVED = "resolved"

class FeedbackActionEnum(str, Enum):
    ACCEPT_FINDING = "accept_finding"
    REJECT_FALSE_POSITIVE = "reject_false_positive"
    CORRECT_DETECTION = "correct_detection"
    MARK_EXCEPTION = "mark_exception"

T = TypeVar("T")

class ApiResponse(BaseModel, Generic[T]):
    """Envoltorio estándar de respuesta de la API."""
    success: bool = True
    message: Optional[str] = None
    data: Optional[T] = None
    error: Optional[str] = None

class PaginatedResponse(BaseModel, Generic[T]):
    """Respuesta paginada estándar."""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
