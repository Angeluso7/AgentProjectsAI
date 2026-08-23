from typing import Generic, TypeVar, Type, Optional, List, Any
from sqlalchemy.orm import Session
from app.db.session import Base

ModelType = TypeVar("ModelType", bound=Base)

class BaseRepository(Generic[ModelType]):
    """Repositorio base con operaciones CRUD comunes en SQLAlchemy."""

    def __init__(self, model: Type[ModelType], db: Session):
        self.model = model
        self.db = db

    def get_by_id(self, id: str) -> Optional[ModelType]:
        return self.db.query(self.model).filter(self.model.id == id).first()

    def list_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        return self.db.query(self.model).offset(skip).limit(limit).all()

    def count(self) -> int:
        return self.db.query(self.model).count()

    def create(self, obj_in: ModelType) -> ModelType:
        self.db.add(obj_in)
        self.db.commit()
        self.db.refresh(obj_in)
        return obj_in

    def update(self, db_obj: ModelType, update_data: dict) -> ModelType:
        for field, value in update_data.items():
            if hasattr(db_obj, field) and value is not None:
                setattr(db_obj, field, value)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, id: str) -> bool:
        obj = self.get_by_id(id)
        if obj:
            self.db.delete(obj)
            self.db.commit()
            return True
        return False
