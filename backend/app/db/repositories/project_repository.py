import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.models.core import Project, ProjectVersion
from app.db.models.document_memory import Document, DocumentSheet
from app.db.models.active_learning import ManualAnnotation
from app.db.models.decision_memory import ReviewRun, RuleFinding
from app.db.models.reporting import AuditReport
from app.db.models.intake import SourceAsset
from app.db.repositories.base import BaseRepository
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectVersionCreate, ProjectRead, ProjectExportPayload, ProjectExportSummary

class ProjectRepository(BaseRepository[Project]):
    def __init__(self, db: Session):
        super().__init__(Project, db)

    def _to_read_schema(self, project: Project) -> ProjectRead:
        """Convierte una entidad Project a ProjectRead con contadores y etapa derivados."""
        settings = project.settings or {}
        stage = settings.get("stage", "Ingeniería de Detalle")
        project_type = settings.get("project_type", "edificacion")
        
        # Calcular contadores activos
        docs = [d for d in (project.documents or []) if getattr(d, "status", "") not in ["deleted", "archived"]]
        documents_count = len(docs)
        sheets_count = sum(len(d.sheets) for d in docs if hasattr(d, "sheets") and d.sheets)
        
        # Hallazgos
        findings_count = 0
        try:
            findings_count = self.db.query(RuleFinding).join(ReviewRun).filter(
                ReviewRun.project_id == project.id
            ).count()
        except Exception:
            findings_count = 0

        read_obj = ProjectRead(
            id=project.id,
            organization_id=project.organization_id,
            code=project.code,
            name=project.name,
            description=project.description,
            client_name=project.client_name,
            discipline=project.discipline,
            stage=stage,
            project_type=project_type,
            status=project.status or "active",
            is_active=project.is_active if project.is_active is not None else True,
            settings=settings,
            created_at=project.created_at or datetime.utcnow(),
            updated_at=project.updated_at or datetime.utcnow(),
            versions=[],
            documents_count=documents_count,
            sheets_count=sheets_count,
            findings_count=findings_count
        )
        return read_obj

    def list_by_organization(
        self,
        organization_id: str,
        include_archived: bool = True,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[ProjectRead]:
        query = self.db.query(Project).filter(
            Project.organization_id == organization_id,
            Project.status != "deleted"
        )
        
        if not include_archived:
            query = query.filter(Project.status != "archived")
            
        if status and status != "all":
            query = query.filter(Project.status == status)

        query = query.order_by(desc(Project.updated_at)).offset(skip).limit(limit)
        projects = query.all()
        return [self._to_read_schema(p) for p in projects]

    def get_by_id_and_organization(self, project_id: str, organization_id: str) -> Optional[Project]:
        return self.db.query(Project).filter(
            Project.id == project_id,
            Project.organization_id == organization_id,
            Project.status != "deleted"
        ).first()

    def get_by_code(self, code: str, organization_id: Optional[str] = None) -> Optional[Project]:
        query = self.db.query(Project).filter(Project.code == code, Project.status != "deleted")
        if organization_id:
            query = query.filter(Project.organization_id == organization_id)
        return query.first()

    def create_project(self, project_in: ProjectCreate, organization_id: str) -> ProjectRead:
        settings = project_in.settings or {}
        if project_in.stage:
            settings["stage"] = project_in.stage
        if project_in.project_type:
            settings["project_type"] = project_in.project_type

        db_project = Project(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            code=project_in.code,
            name=project_in.name,
            description=project_in.description,
            client_name=project_in.client_name,
            discipline=project_in.discipline.value if hasattr(project_in.discipline, "value") else str(project_in.discipline),
            status=project_in.status or "active",
            settings=settings,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        created = self.create(db_project)
        return self._to_read_schema(created)

    def update_project(self, project: Project, data: Dict[str, Any]) -> ProjectRead:
        settings = dict(project.settings or {})
        
        if "stage" in data and data["stage"] is not None:
            settings["stage"] = data.pop("stage")
        if "project_type" in data and data["project_type"] is not None:
            settings["project_type"] = data.pop("project_type")
        if "settings" in data and data["settings"] is not None:
            settings.update(data["settings"])
            
        data["settings"] = settings
        data["updated_at"] = datetime.utcnow()

        if "discipline" in data and data["discipline"] is not None:
            disc = data["discipline"]
            data["discipline"] = disc.value if hasattr(disc, "value") else str(disc)

        for key, value in data.items():
            if hasattr(project, key) and value is not None:
                setattr(project, key, value)

        self.db.commit()
        self.db.refresh(project)
        return self._to_read_schema(project)

    def archive_project(self, project_id: str, organization_id: str) -> Optional[ProjectRead]:
        project = self.get_by_id_and_organization(project_id, organization_id)
        if not project:
            return None
        project.status = "archived"
        project.is_active = False
        project.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(project)
        return self._to_read_schema(project)

    def unarchive_project(self, project_id: str, organization_id: str) -> Optional[ProjectRead]:
        project = self.get_by_id_and_organization(project_id, organization_id)
        if not project:
            return None
        project.status = "active"
        project.is_active = True
        project.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(project)
        return self._to_read_schema(project)

    def delete_project(self, project_id: str, organization_id: str, hard_delete: bool = False) -> bool:
        project = self.get_by_id_and_organization(project_id, organization_id)
        if not project:
            return False

        if not hard_delete:
            # Soft delete seguro
            project.status = "deleted"
            project.is_active = False
            project.updated_at = datetime.utcnow()
            self.db.commit()
            return True

        # Hard delete protegido en cascada
        # 1. Eliminar anotaciones manuales del proyecto
        self.db.query(ManualAnnotation).filter(
            ManualAnnotation.project_id == project_id,
            ManualAnnotation.organization_id == organization_id
        ).delete(synchronize_session=False)

        # 2. Desvincular o eliminar fuentes de intake vinculadas
        self.db.query(SourceAsset).filter(
            SourceAsset.project_id == project_id,
            SourceAsset.organization_id == organization_id
        ).update({"project_id": None}, synchronize_session=False)

        # 3. Eliminar el proyecto (cascada automática a Document, Version, ReviewRun)
        self.db.delete(project)
        self.db.commit()
        return True

    def add_version(self, project_id: str, version_in: ProjectVersionCreate) -> ProjectVersion:
        db_version = ProjectVersion(
            id=str(uuid.uuid4()),
            project_id=project_id,
            version_tag=version_in.version_tag,
            description=version_in.description,
            status=version_in.status,
            created_at=datetime.utcnow()
        )
        self.db.add(db_version)
        self.db.commit()
        self.db.refresh(db_version)
        return db_version

    def export_project_data(self, project_id: str, organization_id: str) -> Optional[ProjectExportPayload]:
        project = self.get_by_id_and_organization(project_id, organization_id)
        if not project:
            return None

        project_read = self._to_read_schema(project)
        
        # Versiones
        versions = self.db.query(ProjectVersion).filter(ProjectVersion.project_id == project_id).all()
        versions_list = [{
            "id": v.id,
            "version_tag": v.version_tag,
            "description": v.description,
            "status": v.status,
            "created_at": v.created_at.isoformat() if v.created_at else None
        } for v in versions]

        # Documentos y Láminas
        docs = self.db.query(Document).filter(
            Document.project_id == project_id,
            Document.organization_id == organization_id
        ).all()
        docs_list = []
        total_sheets = 0
        for d in docs:
            sheets_data = []
            for s in (d.sheets or []):
                total_sheets += 1
                sheets_data.append({
                    "id": s.id,
                    "sheet_number": s.sheet_number,
                    "title": s.title,
                    "discipline": s.discipline,
                    "width": s.width,
                    "height": s.height,
                    "dpi": s.dpi,
                    "scale": s.scale
                })
            docs_list.append({
                "id": d.id,
                "filename": d.filename,
                "title": d.title,
                "document_type": d.document_type,
                "discipline": d.discipline,
                "status": d.status,
                "total_sheets": d.total_sheets,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "sheets": sheets_data
            })

        # Anotaciones / Selecciones manuales
        annotations = self.db.query(ManualAnnotation).filter(
            ManualAnnotation.project_id == project_id,
            ManualAnnotation.organization_id == organization_id
        ).all()
        annotations_list = [{
            "id": a.id,
            "document_id": a.document_id,
            "sheet_id": a.sheet_id,
            "element_type": a.element_type,
            "name": a.name,
            "description": a.description,
            "discipline": a.discipline,
            "bbox_normalized": a.bbox_normalized,
            "ocr_text": a.ocr_text,
            "status": a.status,
            "created_at": a.created_at.isoformat() if hasattr(a, "created_at") and a.created_at else None
        } for a in annotations]

        # Corridas de Auditoría y Hallazgos
        review_runs = self.db.query(ReviewRun).filter(
            ReviewRun.project_id == project_id,
            ReviewRun.organization_id == organization_id
        ).all()
        runs_list = []
        total_findings = 0
        for r in review_runs:
            findings_data = []
            findings = self.db.query(RuleFinding).filter(RuleFinding.review_run_id == r.id).all()
            for f in findings:
                total_findings += 1
                findings_data.append({
                    "id": f.id,
                    "rule_id": f.rule_id,
                    "rule_code": f.rule_code,
                    "title": f.title,
                    "severity": f.severity,
                    "status": f.status,
                    "primary_location": f.primary_location
                })
            runs_list.append({
                "id": r.id,
                "run_name": r.run_name,
                "status": r.status,
                "rules_applied_count": r.rules_applied_count,
                "findings_count": r.findings_count,
                "findings": findings_data,
                "created_at": r.created_at.isoformat() if r.created_at else None
            })

        # Reportes generados vinculados a documentos del proyecto
        reports = self.db.query(AuditReport).join(Document).filter(
            Document.project_id == project_id,
            AuditReport.organization_id == organization_id
        ).all()
        reports_list = [{
            "id": rep.id,
            "document_id": rep.document_id,
            "sheet_id": rep.sheet_id,
            "report_type": rep.report_type,
            "status": rep.status,
            "summary": rep.summary,
            "created_at": rep.created_at.isoformat() if rep.created_at else None
        } for rep in reports]

        summary = ProjectExportSummary(
            versions_count=len(versions_list),
            documents_count=len(docs_list),
            sheets_count=total_sheets,
            annotations_count=len(annotations_list),
            findings_count=total_findings,
            reports_count=len(reports_list)
        )

        return ProjectExportPayload(
            schema_version="1.0",
            exported_at=datetime.utcnow(),
            project_id=project.id,
            stage=project_read.stage or "Ingeniería de Detalle",
            summary=summary,
            project=project_read,
            entities={
                "versions": versions_list,
                "documents": docs_list,
                "manual_annotations": annotations_list,
                "review_runs": runs_list,
                "reports": reports_list
            }
        )
