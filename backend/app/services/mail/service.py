import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.core.logging import logger
from app.core.settings import settings

class MailMessage:
    def __init__(self, to_email: str, subject: str, body_text: str, body_html: str, action_url: Optional[str] = None):
        self.to_email = to_email
        self.subject = subject
        self.body_text = body_text
        self.body_html = body_html
        self.action_url = action_url
        self.sent_at = datetime.utcnow()

class MailService:
    """
    Servicio desacoplado para el envío transaccional de correos electrónicos.
    - Modo 'development' / 'testing': Registra los correos estructuradamente en consola y memoria sin exponer secretos.
    - Modo 'smtp' / 'production': Realiza el envío real mediante servidor SMTP configurado por variables de entorno.
    """
    _outbox: List[MailMessage] = []

    @classmethod
    def get_outbox(cls) -> List[MailMessage]:
        return cls._outbox

    @classmethod
    def clear_outbox(cls) -> None:
        cls._outbox.clear()

    @classmethod
    def is_smtp_configured(cls) -> bool:
        smtp_host = os.environ.get("SMTP_HOST") or getattr(settings, "SMTP_HOST", None)
        return bool(smtp_host and smtp_host != "localhost_dummy")

    @classmethod
    def send_password_reset_email(cls, to_email: str, token: str, user_name: str = "Usuario") -> bool:
        """Envía el enlace de recuperación de contraseña de un solo uso."""
        frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173")
        reset_link = f"{frontend_url}/reset-password?token={token}"

        subject = "Recuperación de Contraseña - Plan Review AI Hybrid"
        body_text = f"""Hola {user_name},

Hemos recibido una solicitud para restablecer la contraseña de tu cuenta en Plan Review AI Hybrid.

Para establecer una nueva contraseña, haz clic en el siguiente enlace o cópialo en tu navegador:
{reset_link}

Este enlace es de un solo uso y expirará en 15 minutos.

Si tú no realizaste esta solicitud, puedes ignorar este mensaje; tu contraseña actual continuará siendo segura.
"""
        body_html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0f172a; color: #e2e8f0; padding: 24px; margin: 0;">
  <div style="max-width: 540px; margin: 0 auto; background-color: #1e293b; border: 1px solid #334155; border-radius: 16px; padding: 32px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.5);">
    <h2 style="color: #38bdf8; margin-top: 0; font-size: 20px;">Restablecer Contraseña</h2>
    <p style="color: #cbd5e1; font-size: 14px; line-height: 1.6;">Hola <strong>{user_name}</strong>,</p>
    <p style="color: #cbd5e1; font-size: 14px; line-height: 1.6;">Recibimos una solicitud para restablecer tu acceso a la plataforma <strong>Plan Review AI Hybrid</strong>.</p>
    <div style="text-align: center; margin: 28px 0;">
      <a href="{reset_link}" style="background-color: #0284c7; color: #ffffff; padding: 12px 28px; text-decoration: none; border-radius: 10px; font-weight: 600; font-size: 14px; display: inline-block;">
        Establecer Nueva Contraseña
      </a>
    </div>
    <p style="color: #94a3b8; font-size: 12px; line-height: 1.5;">
      Este enlace es criptográficamente seguro, de un solo uso y expira en <strong>15 minutos</strong>.
    </p>
    <hr style="border: none; border-top: 1px solid #334155; margin: 24px 0;" />
    <p style="color: #64748b; font-size: 11px; margin-bottom: 0;">
      Si no solicitaste este cambio, ignora este correo.
    </p>
  </div>
</body>
</html>
"""
        message = MailMessage(to_email, subject, body_text, body_html, action_url=reset_link)
        cls._outbox.append(message)

        if cls.is_smtp_configured():
            return cls._send_via_smtp(message)
        else:
            cls._log_dev_mail(message)
            return True

    @classmethod
    def send_email_change_confirmation(cls, to_email: str, token: str, user_name: str = "Usuario") -> bool:
        """Envía el enlace de verificación para cambio de correo electrónico."""
        frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173")
        verify_link = f"{frontend_url}/verify-email?token={token}"

        subject = "Confirmación de Nuevo Correo - Plan Review AI Hybrid"
        body_text = f"""Hola {user_name},

Has solicitado actualizar tu dirección de correo electrónico en Plan Review AI Hybrid a: {to_email}.

Para confirmar este cambio, ingresa al siguiente enlace:
{verify_link}

Este enlace expirará en 24 horas.
"""
        body_html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0f172a; color: #e2e8f0; padding: 24px; margin: 0;">
  <div style="max-width: 540px; margin: 0 auto; background-color: #1e293b; border: 1px solid #334155; border-radius: 16px; padding: 32px;">
    <h2 style="color: #10b981; margin-top: 0; font-size: 20px;">Confirmar Nuevo Correo Electrónico</h2>
    <p style="color: #cbd5e1; font-size: 14px; line-height: 1.6;">Hola <strong>{user_name}</strong>,</p>
    <p style="color: #cbd5e1; font-size: 14px; line-height: 1.6;">Has solicitado asociar esta dirección de correo ({to_email}) a tu cuenta en <strong>Plan Review AI Hybrid</strong>.</p>
    <div style="text-align: center; margin: 28px 0;">
      <a href="{verify_link}" style="background-color: #059669; color: #ffffff; padding: 12px 28px; text-decoration: none; border-radius: 10px; font-weight: 600; font-size: 14px; display: inline-block;">
        Confirmar Dirección de Correo
      </a>
    </div>
    <p style="color: #94a3b8; font-size: 12px; line-height: 1.5;">
      El cambio no surtirá efecto hasta que confirmes este enlace. Expira en 24 horas.
    </p>
  </div>
</body>
</html>
"""
        message = MailMessage(to_email, subject, body_text, body_html, action_url=verify_link)
        cls._outbox.append(message)

        if cls.is_smtp_configured():
            return cls._send_via_smtp(message)
        else:
            cls._log_dev_mail(message)
            return True

    @classmethod
    def _log_dev_mail(cls, msg: MailMessage) -> None:
        """Registra el correo en consola y logger de forma estructurada para desarrollo local."""
        print(f"\n" + "="*80)
        print(f" [MAIL SERVICE - DEV MODE] Transacción de Correo Electrónico")
        print(f" Para: {msg.to_email}")
        print(f" Asunto: {msg.subject}")
        if msg.action_url:
            print(f" Enlace de Acción: {msg.action_url}")
        print(f" Fecha/Hora UTC: {msg.sent_at.isoformat()}Z")
        print("="*80 + "\n")
        logger.info(f"[MAIL-DEV] Enlace para {msg.to_email}: {msg.action_url}")

    @classmethod
    def _send_via_smtp(cls, msg: MailMessage) -> bool:
        """Envía el correo mediante conexión SMTP protegida."""
        smtp_host = os.environ.get("SMTP_HOST", "localhost")
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        smtp_user = os.environ.get("SMTP_USER", "")
        smtp_password = os.environ.get("SMTP_PASSWORD", "")
        from_email = os.environ.get("EMAILS_FROM_EMAIL", "noreply@planreview.ai")
        use_tls = os.environ.get("SMTP_TLS", "true").lower() in ("true", "1", "yes")

        try:
            mime_msg = MIMEMultipart("alternative")
            mime_msg["Subject"] = msg.subject
            mime_msg["From"] = from_email
            mime_msg["To"] = msg.to_email

            part1 = MIMEText(msg.body_text, "plain", "utf-8")
            part2 = MIMEText(msg.body_html, "html", "utf-8")
            mime_msg.attach(part1)
            mime_msg.attach(part2)

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                if use_tls:
                    server.starttls()
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)
                server.sendmail(from_email, [msg.to_email], mime_msg.as_string())
            logger.info(f"Correo enviado exitosamente a {msg.to_email} vía SMTP.")
            return True
        except Exception as e:
            logger.error(f"Fallo al enviar correo a {msg.to_email} vía SMTP: {e}")
            return False
