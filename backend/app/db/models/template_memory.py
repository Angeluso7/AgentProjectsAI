import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base

class TitleBlockTemplate(Base):
    """Plantilla geométrica y reglas de extracción para viñetas/rótulos técnicos."""
    __tablename__ = "title_block_templates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(150), unique=True, index=True, nullable=False) # e.g. "Standard-A0-BottomRight", "Cliente-X-Vertical"
    client_or_standard = Column(String(100), nullable=True)
    discipline = Column(String(50), default="general")
    
    relative_position = Column(String(50), default="bottom_right") # bottom_right, bottom_bar, right_vertical
    expected_bbox = Column(JSON, nullable=False) # [x0, y0, x1, y1] relativo aproximado
    
    # Mapeo de campos a anchors textuales
    # Ej: {"sheet_code": ["PLANO N°", "CODIGO", "LAMINA"], "scale": ["ESCALA", "ESC."], "revision": ["REV", "REVISION"]}
    field_anchors = Column(JSON, default=dict, nullable=False)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class SymbolLibrary(Base):
    """Biblioteca o catálogo de símbolos agrupados por disciplina y estándar."""
    __tablename__ = "symbol_libraries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(150), unique=True, index=True, nullable=False) # e.g. "ISO-128-Architecture", "NCh-Elec-Simbolos"
    discipline = Column(String(50), nullable=False) # architecture, electrical, plumbing, structural
    standard_name = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    symbols = relationship("SymbolTemplate", back_populates="library", cascade="all, delete-orphan")


class SymbolTemplate(Base):
    """Definición de un símbolo gráfico canónico para matching visual."""
    __tablename__ = "symbol_templates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    library_id = Column(String(36), ForeignKey("symbol_libraries.id", ondelete="CASCADE"), nullable=True)
    
    symbol_class = Column(String(100), index=True, nullable=False) # e.g. "door_single_swing_90", "outlet_grounded", "control_valve"
    display_name = Column(String(150), nullable=False)
    aliases = Column(JSON, default=list) # ["P1", "P-01", "Puerta de Paso"]
    
    image_template_path = Column(String(500), nullable=True) # PNG con fondo transparente / crop original
    normalized_mask_path = Column(String(500), nullable=True) # PNG binarizado cuadrado 128x128
    mask_hash = Column(String(64), nullable=True) # SHA-256 de la máscara binaria
    vector_svg_path = Column(String(500), nullable=True)
    
    # Descriptores de forma y momentos geométricos
    hu_moments = Column(JSON, default=list) # 7 Momentos de Hu invariantes a rotación/escala
    contour_signature = Column(JSON, default=list) # Perfil radial de 128 puntos
    canonical_width_mm = Column(Float, nullable=True)
    canonical_height_mm = Column(Float, nullable=True)
    aspect_ratio = Column(Float, nullable=True)
    primitive_signature = Column(JSON, default=dict) # Conteo de arcos, círculos, líneas
    
    # Configuración de detección y scoping
    rotation_invariance_mode = Column(String(30), default="orthogonal_4_rotations") # orthogonal_4_rotations (0, 90, 180, 270) o free_rotation
    is_active_for_detection = Column(Boolean, default=True, nullable=False, index=True)
    organization_id = Column(String(36), nullable=True, index=True)
    
    feature_descriptors = Column(JSON, default=dict) # ORB/SIFT/Embedding descriptor legado
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    library = relationship("SymbolLibrary", back_populates="symbols")


class TableSchemaTemplate(Base):
    """Definición esperada de columnas y tipos para cuadros técnicos típicos."""
    __tablename__ = "table_schema_templates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    schema_code = Column(String(100), unique=True, index=True, nullable=False) # e.g. "SCHEMA_DOOR_SCHEDULE"
    name = Column(String(150), nullable=False) # "Cuadro de Vanos de Puertas"
    discipline = Column(String(50), default="architecture")
    
    # Definición de columnas esperadas, sinónimos y tipos
    # Ej: [{"col_key": "door_id", "synonyms": ["CODIGO", "TIPO", "ITEM"], "data_type": "string", "required": True}, ...]
    columns_spec = Column(JSON, default=list, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class OntologyDictionary(Base):
    """Diccionario de ontologías, sinónimos y alias técnicos del dominio."""
    __tablename__ = "ontology_dictionaries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    domain = Column(String(50), index=True, nullable=False) # architecture, structural, electrical, mep
    canonical_term = Column(String(100), index=True, nullable=False) # e.g. "LEVEL_FINISHED_FLOOR"
    display_label = Column(String(150), nullable=False) # "Nivel de Piso Terminado"
    
    synonyms = Column(JSON, default=list, nullable=False) # ["NPT", "N.P.T.", "NIVEL PISO TERM.", "FFL"]
    unit = Column(String(20), nullable=True) # "m", "mm", "kW"
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
