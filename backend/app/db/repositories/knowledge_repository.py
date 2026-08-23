from typing import Optional, List
from sqlalchemy.orm import Session
from app.db.models.knowledge_asset import KnowledgeAsset
from app.db.models.normative_memory import NormativeDocument, NormativeClause, NormativeCriterion
from app.db.models.template_memory import TitleBlockTemplate, SymbolLibrary, OntologyDictionary
from app.db.repositories.base import BaseRepository
from app.schemas.knowledge import KnowledgeAssetCreate

class KnowledgeRepository:
    """Repositorio unificado para consultar y persistir activos de conocimiento y plantillas."""

    def __init__(self, db: Session):
        self.db = db

    # Knowledge Assets
    def list_assets(self, asset_type: Optional[str] = None) -> List[KnowledgeAsset]:
        q = self.db.query(KnowledgeAsset).filter(KnowledgeAsset.is_active == True)
        if asset_type:
            q = q.filter(KnowledgeAsset.asset_type == asset_type)
        return q.all()

    def get_asset_by_code(self, code: str) -> Optional[KnowledgeAsset]:
        return self.db.query(KnowledgeAsset).filter(KnowledgeAsset.code == code).first()

    def create_asset(self, asset_in: KnowledgeAssetCreate) -> KnowledgeAsset:
        asset = KnowledgeAsset(
            code=asset_in.code,
            title=asset_in.title,
            asset_type=asset_in.asset_type,
            discipline=asset_in.discipline.value if hasattr(asset_in.discipline, "value") else str(asset_in.discipline),
            version=asset_in.version,
            description=asset_in.description,
            file_path=asset_in.file_path,
            content_payload=asset_in.content_payload,
            is_active=asset_in.is_active
        )
        self.db.add(asset)
        self.db.commit()
        self.db.refresh(asset)
        return asset

    # Normativas
    def list_standards(self) -> List[NormativeDocument]:
        return self.db.query(NormativeDocument).filter(NormativeDocument.is_active == True).all()

    def get_standard_by_code(self, code: str) -> Optional[NormativeDocument]:
        return self.db.query(NormativeDocument).filter(NormativeDocument.code == code).first()

    def create_standard(self, doc: NormativeDocument) -> NormativeDocument:
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    # Plantillas de viñeta
    def list_title_block_templates(self) -> List[TitleBlockTemplate]:
        return self.db.query(TitleBlockTemplate).filter(TitleBlockTemplate.is_active == True).all()

    def create_title_block_template(self, tpl: TitleBlockTemplate) -> TitleBlockTemplate:
        self.db.add(tpl)
        self.db.commit()
        self.db.refresh(tpl)
        return tpl

    # Librerías de símbolos
    def list_symbol_libraries(self) -> List[SymbolLibrary]:
        return self.db.query(SymbolLibrary).all()

    # Ontologías
    def list_ontologies(self, domain: Optional[str] = None) -> List[OntologyDictionary]:
        q = self.db.query(OntologyDictionary)
        if domain:
            q = q.filter(OntologyDictionary.domain == domain)
        return q.all()
