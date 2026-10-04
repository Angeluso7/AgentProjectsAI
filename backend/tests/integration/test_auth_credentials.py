import pytest
import uuid
from fastapi.testclient import TestClient
from app.db.models.core import User, Organization, OrganizationMembership, AuditLog, PasswordResetToken, EmailChangeRequest
from app.core.security import hash_password, create_access_token
from app.services.mail.service import MailService

def test_profile_and_credential_flows(client: TestClient, db_session):
    MailService.clear_outbox()

    # 1. Crear Organización y Usuario
    org_id = str(uuid.uuid4())
    org = Organization(id=org_id, name="Security Test Org", slug=f"sec-org-{uuid.uuid4().hex[:6]}")
    db_session.add(org)

    user = User(
        id=str(uuid.uuid4()),
        email="test_user@planreview.ai",
        display_name="Usuario de Prueba",
        password_hash=hash_password("OldPassword123!"),
        is_active=True,
        is_superuser=False
    )
    db_session.add(user)

    membership = OrganizationMembership(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        user_id=user.id,
        role="reviewer",
        status="active"
    )
    db_session.add(membership)
    db_session.commit()

    token = create_access_token(user.id, email=user.email, extra_claims={"role": "reviewer"})
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # 2. Probar GET /api/v1/auth/me y PUT /api/v1/auth/me
    res_me = client.get("/api/v1/auth/me", headers=headers)
    assert res_me.status_code == 200
    assert res_me.json()["user"]["email"] == "test_user@planreview.ai"

    res_update = client.put(
        "/api/v1/auth/me",
        headers=headers,
        json={"display_name": "Usuario Actualizado"}
    )
    assert res_update.status_code == 200
    assert res_update.json()["display_name"] == "Usuario Actualizado"

    # 3. Probar Cambio de Contraseña (POST /api/v1/auth/change-password)
    # Contraseña actual incorrecta
    res_bad_pwd = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "WrongPassword!", "new_password": "NewSecretPassword123!"}
    )
    assert res_bad_pwd.status_code == 400

    # Cambio exitoso
    res_change_pwd = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "OldPassword123!", "new_password": "NewSecretPassword123!"}
    )
    assert res_change_pwd.status_code == 200
    assert res_change_pwd.json()["success"] is True

    # 4. Probar Solicitud y Confirmación de Cambio de Correo
    res_email_req = client.post(
        "/api/v1/auth/email-change/request",
        headers=headers,
        json={"current_password": "NewSecretPassword123!", "new_email": "new_email@planreview.ai"}
    )
    assert res_email_req.status_code == 200
    
    # Verificar que se generó correo en el MailService outbox
    outbox = MailService.get_outbox()
    assert len(outbox) >= 1
    verify_msg = [m for m in outbox if m.to_email == "new_email@planreview.ai"][0]
    assert "token=" in verify_msg.action_url
    raw_token = verify_msg.action_url.split("token=")[1]

    # Confirmar cambio de correo
    res_email_conf = client.post(
        "/api/v1/auth/email-change/confirm",
        json={"token": raw_token}
    )
    assert res_email_conf.status_code == 200
    
    # Validar que el email cambió en la base de datos
    db_session.expire_all()
    user_after = db_session.query(User).filter(User.id == user.id).first()
    assert user_after.email == "new_email@planreview.ai"

    # 5. Probar Recuperación de Contraseña por Correo
    # Solicitud con correo no existente (respuesta neutra sin enumeración)
    res_reset_nonexistent = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "nonexistent@fake.com"}
    )
    assert res_reset_nonexistent.status_code == 200
    assert "recibirás un mensaje" in res_reset_nonexistent.json()["message"]

    # Solicitud con correo válido
    res_reset_req = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "new_email@planreview.ai"}
    )
    assert res_reset_req.status_code == 200
    
    # Verificar correo en outbox
    reset_msg = [m for m in MailService.get_outbox() if "reset-password" in (m.action_url or "")][-1]
    assert reset_msg.to_email == "new_email@planreview.ai"
    reset_raw_token = reset_msg.action_url.split("token=")[1]

    # Confirmar restablecimiento de contraseña
    res_reset_conf = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": reset_raw_token, "new_password": "BrandNewPassword999!"}
    )
    assert res_reset_conf.status_code == 200

    # Intentar reutilizar el mismo token (debe fallar)
    res_reuse = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": reset_raw_token, "new_password": "AnotherPassword123!"}
    )
    assert res_reuse.status_code == 400

    # Probar login con la nueva contraseña
    res_login_new = client.post(
        "/api/v1/auth/login",
        json={"email": "new_email@planreview.ai", "password": "BrandNewPassword999!"}
    )
    assert res_login_new.status_code == 200
    assert "access_token" in res_login_new.json()
