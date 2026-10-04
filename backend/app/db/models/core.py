import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, JSON, Boolean, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship, validates
from app.db.session import Base

class Organization(Base):
    """Entidad principal que representa a un tenant/organización aislada."""
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=False)
    status = Column(String(30), default="active", nullable=False, index=True) # active, suspended, archived
    settings = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    memberships = relationship("OrganizationMembership", back_populates="organization", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    """Usuario del sistema para autenticación y trazabilidad."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(150), unique=True, index=True, nullable=False)
    display_name = Column(String(150), nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    memberships = relationship("OrganizationMembership", back_populates="user", cascade="all, delete-orphan")


class OrganizationMembership(Base):
    """Vínculo de membresía y rol de un usuario dentro de una organización (RBAC)."""
    __tablename__ = "organization_memberships"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    role = Column(String(30), default="reviewer", nullable=False, index=True)
    # admin, audit_lead, reviewer, contributor, viewer
    
    status = Column(String(30), default="active", nullable=False, index=True)
    # active, invited, disabled
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    organization = relationship("Organization", back_populates="memberships")
    user = relationship("User", back_populates="memberships")


class Project(Base):
    """Entidad que agrupa un conjunto de planos y auditorías dentro de un tenant."""
    __tablename__ = "projects"
    __table_args__ = (
        Index(
            "uq_project_org_active_code",
            "organization_id",
            "normalized_code",
            unique=True,
            sqlite_where=text("status != 'deleted'"),
            postgresql_where=text("status != 'deleted'")
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    code = Column(String(50), index=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    client_name = Column(String(150), nullable=True)
    discipline = Column(String(50), default="architecture", nullable=False)
    discipline_scope = Column(JSON, default=list) # ["architecture", "structural", "electrical"]
    status = Column(String(30), default="active", nullable=False)
    settings = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    normalized_code = Column(String(50), nullable=False, index=True)
    
    cleanup_status = Column(String(30), default="none", nullable=True) # none, in_progress, completed, failed
    cleanup_error = Column(Text, nullable=True)
    deletion_job_id = Column(String(36), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @validates("code")
    def validate_code(self, key, value):
        if value:
            self.normalized_code = str(value).strip().upper()
            return str(value).strip()
        return value

    # Relaciones
    organization = relationship("Organization", back_populates="projects")
    versions = relationship("ProjectVersion", back_populates="project", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    review_runs = relationship("ReviewRun", back_populates="project", cascade="all, delete-orphan")


class ProjectVersion(Base):
    """Control de versión o entrega de un proyecto (ej: Rev 0, Rev A, As-Built)."""
    __tablename__ = "project_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    version_tag = Column(String(20), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(30), default="draft")
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    project = relationship("Project", back_populates="versions")
    documents = relationship("Document", back_populates="project_version")


class AuditLog(Base):
    """Bitácora inmutable de acciones en el sistema con contexto de tenant."""
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), nullable=True, index=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(36), nullable=False)
    action = Column(String(50), nullable=False)
    user_id = Column(String(36), nullable=True)
    details = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)


class PasswordResetToken(Base):
    """Token criptográfico de un solo uso para recuperación de contraseña."""
    __tablename__ = "password_reset_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")


class EmailChangeRequest(Base):
    """Solicitud de cambio de correo con confirmación por token criptográfico."""
    __tablename__ = "email_change_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    new_email = Column(String(150), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")

