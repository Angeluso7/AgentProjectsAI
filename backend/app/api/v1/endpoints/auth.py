import secrets
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.core import (
    User, Organization, OrganizationMembership, AuditLog,
    PasswordResetToken, EmailChangeRequest
)
from app.schemas.auth import (
    LoginRequest, AuthTokenResponse, UserProfileRead, UserMembershipSummary,
    CurrentUserResponse, UpdateProfileRequest, ChangePasswordRequest,
    EmailChangeRequestSchema, EmailChangeConfirmSchema,
    PasswordResetRequestSchema, PasswordResetConfirmSchema, GenericMessageResponse
)
from app.core.security import (
    hash_password, verify_password, create_access_token, decode_access_token, revoke_token
)
from app.core.deps import get_current_user
from app.services.mail.service import MailService

router = APIRouter()

# Estructura en memoria para rate limiting básico de recuperación de contraseñas
_RESET_ATTEMPTS: dict[str, list[datetime]] = {}

def _check_rate_limit(key: str, max_requests: int = 5, window_minutes: int = 15) -> None:
    now = datetime.utcnow()
    window_start = now - timedelta(minutes=window_minutes)
    attempts = _RESET_ATTEMPTS.get(key, [])
    # Filtrar solo intentos en la ventana
    valid_attempts = [t for t in attempts if t > window_start]
    if len(valid_attempts) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes de recuperación. Intente nuevamente en 15 minutos."
        )
    valid_attempts.append(now)
    _RESET_ATTEMPTS[key] = valid_attempts


@router.post("/login", response_model=AuthTokenResponse)
def login(
    req: LoginRequest,
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-Id"),
    db: Session = Depends(get_db)
):
    """Autenticación de usuario con email y contraseña, retorna JWT y membresías activas."""
    user = db.query(User).filter(User.email == req.email.strip().lower()).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas o usuario no registrado."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario desactivado. Contacte a su administrador."
        )

    is_valid, needs_rehash = verify_password(req.password, user.password_hash)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas o usuario no registrado."
        )

    # Actualización transparente de hash a formato Argon2id/PBKDF2-600k si requiere rehash
    if needs_rehash:
        user.password_hash = hash_password(req.password)
        db.commit()

    # Obtener membresías activas del usuario
    memberships = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == user.id,
        OrganizationMembership.status == "active"
    ).all()

    if not memberships and not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario no pertenece a ninguna organización activa."
        )

    # Resolver organización activa inicial
    selected_membership = None
    if x_organization_id:
        for m in memberships:
            if m.organization_id == x_organization_id:
                selected_membership = m
                break
        if not selected_membership and not user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No posee membresía activa en la organización '{x_organization_id}'."
            )
    else:
        if memberships:
            selected_membership = memberships[0]

    active_org_id = selected_membership.organization_id if selected_membership else "default-org-uuid"
    active_role = selected_membership.role if selected_membership else ("admin" if user.is_superuser else "viewer")

    # Generar Token JWT de Identidad Pura (minimal claims: sub, email, jti, exp, iat, iss)
    token = create_access_token(
        subject=user.id,
        email=user.email,
        expires_delta=timedelta(minutes=180)
    )

    membership_summaries = []
    for m in memberships:
        org = db.query(Organization).filter(Organization.id == m.organization_id).first()
        if org:
            membership_summaries.append(
                UserMembershipSummary(
                    membership_id=m.id,
                    organization_id=org.id,
                    organization_name=org.name,
                    organization_slug=org.slug,
                    role=m.role,
                    status=m.status
                )
            )

    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_seconds=10800,
        user=UserProfileRead.model_validate(user),
        active_organization_id=active_org_id,
        active_role=active_role,
        memberships=membership_summaries
    )


@router.get("/me", response_model=CurrentUserResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retorna el perfil del usuario autenticado y su lista de organizaciones asociadas."""
    memberships = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == current_user.id,
        OrganizationMembership.status == "active"
    ).all()

    summaries = []
    for m in memberships:
        org = db.query(Organization).filter(Organization.id == m.organization_id).first()
        if org:
            summaries.append(
                UserMembershipSummary(
                    membership_id=m.id,
                    organization_id=org.id,
                    organization_name=org.name,
                    organization_slug=org.slug,
                    role=m.role,
                    status=m.status
                )
            )

    return CurrentUserResponse(
        user=UserProfileRead.model_validate(current_user),
        memberships=summaries
    )


@router.put("/me", response_model=UserProfileRead)
def update_current_user_profile(
    req: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Actualiza la información de perfil básica del usuario actual (nombre para mostrar)."""
    old_name = current_user.display_name
    current_user.display_name = req.display_name.strip()
    current_user.updated_at = datetime.utcnow()

    # Auditoría
    audit = AuditLog(
        entity_type="user",
        entity_id=current_user.id,
        action="update_profile",
        user_id=current_user.id,
        details={"old_name": old_name, "new_name": current_user.display_name}
    )
    db.add(audit)
    db.commit()
    db.refresh(current_user)
    return UserProfileRead.model_validate(current_user)



@router.post("/change-password", response_model=GenericMessageResponse)
def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cambia la contraseña del usuario previa verificación de su contraseña actual."""
    is_valid, _ = verify_password(req.current_password, current_user.password_hash)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual ingresada es incorrecta."
        )

    if req.new_password == req.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña debe ser distinta a la contraseña actual."
        )

    if len(req.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña debe tener al menos 8 caracteres."
        )

    # Actualizar hash de forma segura
    current_user.password_hash = hash_password(req.new_password)
    current_user.updated_at = datetime.utcnow()

    # Auditoría sin exponer secretos
    audit = AuditLog(
        entity_type="user",
        entity_id=current_user.id,
        action="change_password",
        user_id=current_user.id,
        details={"status": "success", "hash_algo": "pbkdf2-600k"}
    )
    db.add(audit)
    db.commit()

    return GenericMessageResponse(message="Contraseña actualizada exitosamente.")


@router.post("/email-change/request", response_model=GenericMessageResponse)
def request_email_change(
    req: EmailChangeRequestSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Solicita el cambio de correo electrónico, enviando un token de verificación al nuevo correo."""
    is_valid, _ = verify_password(req.current_password, current_user.password_hash)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual ingresada es incorrecta."
        )

    target_email = req.new_email.strip().lower()
    if target_email == current_user.email.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El nuevo correo no puede ser idéntico al correo actual."
        )

    existing_user = db.query(User).filter(User.email == target_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La dirección de correo electrónico ingresada ya se encuentra en uso por otra cuenta."
        )

    # Generar token criptográfico
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

    # Invalidar solicitudes anteriores
    db.query(EmailChangeRequest).filter(
        EmailChangeRequest.user_id == current_user.id,
        EmailChangeRequest.used_at.is_(None)
    ).delete(synchronize_session=False)

    change_req = EmailChangeRequest(
        user_id=current_user.id,
        new_email=target_email,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(hours=24)
    )
    db.add(change_req)

    # Auditoría
    audit = AuditLog(
        entity_type="user",
        entity_id=current_user.id,
        action="request_email_change",
        user_id=current_user.id,
        details={"requested_email": target_email}
    )
    db.add(audit)
    db.commit()

    # Enviar correo de confirmación
    MailService.send_email_change_confirmation(
        to_email=target_email,
        token=raw_token,
        user_name=current_user.display_name
    )

    return GenericMessageResponse(
        message=f"Se ha enviado un enlace de confirmación a '{target_email}'. El cambio se completará al hacer clic en el enlace."
    )


@router.post("/email-change/confirm", response_model=GenericMessageResponse)
def confirm_email_change(
    req: EmailChangeConfirmSchema,
    db: Session = Depends(get_db)
):
    """Confirma el cambio de correo electrónico validando el token criptográfico."""
    token_hash = hashlib.sha256(req.token.strip().encode('utf-8')).hexdigest()
    change_req = db.query(EmailChangeRequest).filter(
        EmailChangeRequest.token_hash == token_hash,
        EmailChangeRequest.used_at.is_(None)
    ).first()

    if not change_req:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El token de confirmación es inválido o ya ha sido utilizado."
        )

    if datetime.utcnow() > change_req.expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El token de confirmación ha expirado. Por favor, solicita el cambio nuevamente."
        )

    user = db.query(User).filter(User.id == change_req.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario asociado no encontrado.")

    # Verificar unicidad final
    existing = db.query(User).filter(User.email == change_req.new_email, User.id != user.id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La dirección de correo electrónico ya ha sido registrada por otra cuenta."
        )

    old_email = user.email
    user.email = change_req.new_email
    user.updated_at = datetime.utcnow()
    change_req.used_at = datetime.utcnow()

    # Auditoría
    audit = AuditLog(
        entity_type="user",
        entity_id=user.id,
        action="confirm_email_change",
        user_id=user.id,
        details={"old_email": old_email, "new_email": user.email}
    )
    db.add(audit)
    db.commit()

    return GenericMessageResponse(message=f"Correo electrónico actualizado exitosamente a '{user.email}'.")


@router.post("/password-reset/request", response_model=GenericMessageResponse)
def request_password_reset(
    req: PasswordResetRequestSchema,
    db: Session = Depends(get_db)
):
    """
    Solicita restablecimiento de contraseña.
    Respuesta neutra para prevenir enumeración de usuarios.
    """
    email_clean = req.email.strip().lower()
    _check_rate_limit(f"pwd_reset_{email_clean}", max_requests=5, window_minutes=15)

    user = db.query(User).filter(User.email == email_clean, User.is_active == True).first()
    if user:
        # Generar token seguro de un solo uso
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

        # Invalidar tokens activos anteriores
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None)
        ).delete(synchronize_session=False)

        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(minutes=15)
        )
        db.add(reset_token)

        audit = AuditLog(
            entity_type="user",
            entity_id=user.id,
            action="request_password_reset",
            user_id=user.id,
            details={"email": email_clean}
        )
        db.add(audit)
        db.commit()

        # Enviar correo
        MailService.send_password_reset_email(
            to_email=user.email,
            token=raw_token,
            user_name=user.display_name
        )

    # Respuesta neutra obligatoria de seguridad
    return GenericMessageResponse(
        message="Si existe una cuenta asociada a ese correo electrónico, recibirás un mensaje con las instrucciones para restablecer tu contraseña."
    )


@router.post("/password-reset/confirm", response_model=GenericMessageResponse)
def confirm_password_reset(
    req: PasswordResetConfirmSchema,
    db: Session = Depends(get_db)
):
    """Restablece la contraseña validando el token de un solo uso."""
    token_hash = hashlib.sha256(req.token.strip().encode('utf-8')).hexdigest()
    reset_entry = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.used_at.is_(None)
    ).first()

    if not reset_entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de recuperación es inválido o ya ha sido utilizado."
        )

    if datetime.utcnow() > reset_entry.expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de recuperación ha expirado (validez de 15 minutos). Por favor solicita uno nuevo."
        )

    user = db.query(User).filter(User.id == reset_entry.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La cuenta asociada al token se encuentra inactiva o no existe."
        )

    if len(req.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña debe tener al menos 8 caracteres."
        )

    user.password_hash = hash_password(req.new_password)
    user.updated_at = datetime.utcnow()
    reset_entry.used_at = datetime.utcnow()

    # Auditoría
    audit = AuditLog(
        entity_type="user",
        entity_id=user.id,
        action="confirm_password_reset",
        user_id=user.id,
        details={"status": "success"}
    )
    db.add(audit)
    db.commit()

    return GenericMessageResponse(
        message="Tu contraseña ha sido restablecida exitosamente. Ahora puedes iniciar sesión con tu nueva clave."
    )


@router.post("/logout")
def logout(
    auth_header: Optional[str] = Header(None, alias="Authorization")
):
    """Invalida el token actual agregando su JTI al conjunto de revocación."""
    if auth_header and auth_header.startswith("Bearer "):
        token_str = auth_header.split(" ")[1]
        try:
            payload = decode_access_token(token_str)
            jti = payload.get("jti")
            if jti:
                revoke_token(jti)
        except Exception:
            pass
    return {"message": "Sesión cerrada exitosamente."}

