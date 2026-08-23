import os
import hmac
import hashlib
import base64
import json
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

from app.core.settings import settings

# ============================================================================
# ALMACENAMIENTO DE REVOCACIÓN DE TOKENS (DEV / SINGLE-NODE ONLY)
# ============================================================================
# ADVERTENCIA DE PRODUCCIÓN:
# Este conjunto en memoria (_REVOKED_JTIS) está estrictamente diseñado para
# entornos locales, de desarrollo y pruebas unitarias en un único nodo de proceso.
# Para despliegues multi-nodo y producción, esta estructura debe ser reemplazada
# por un cliente Redis distribuido con tiempo de expiración TTL igual al max exp del JWT.
# ============================================================================
_REVOKED_TOKENS: set[str] = set()

# Configuración de hashing
PBKDF2_ITERATIONS = 600000
SALT_SIZE = 32

def hash_password(password: str) -> str:
    """Genera hash seguro de contraseña usando Argon2id o PBKDF2-HMAC-SHA256 (600,000 iteraciones)."""
    # Intentar Argon2id si argon2-cffi está disponible
    try:
        from argon2 import PasswordHasher
        ph = PasswordHasher()
        return ph.hash(password)
    except ImportError:
        pass

    # Fallback robusto y estándar FIPS: PBKDF2-HMAC-SHA256 con 600,000 iteraciones
    salt = secrets.token_bytes(SALT_SIZE)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        PBKDF2_ITERATIONS
    )
    salt_b64 = base64.b64encode(salt).decode('ascii')
    key_b64 = base64.b64encode(key).decode('ascii')
    return f"$pbkdf2-sha256$i={PBKDF2_ITERATIONS}${salt_b64}${key_b64}"

def verify_password(plain_password: str, hashed_password: str) -> Tuple[bool, bool]:
    """
    Verifica la contraseña contra el hash.
    Retorna (es_valido, requiere_rehash).
    """
    if not hashed_password:
        return False, False

    # 1. Verificar si es Argon2id
    if hashed_password.startswith("$argon2id$") or hashed_password.startswith("$argon2i$"):
        try:
            from argon2 import PasswordHasher
            from argon2.exceptions import VerifyMismatchError
            ph = PasswordHasher()
            try:
                ph.verify(hashed_password, plain_password)
                return True, ph.check_needs_rehash(hashed_password)
            except VerifyMismatchError:
                return False, False
        except ImportError:
            pass

    # 2. Verificar si es PBKDF2 versionado
    if hashed_password.startswith("$pbkdf2-sha256$"):
        try:
            parts = hashed_password.split("$")
            # formato: ['', 'pbkdf2-sha256', 'i=600000', 'salt', 'hash']
            iter_part = parts[2]
            iterations = int(iter_part.split("=")[1])
            salt = base64.b64decode(parts[3].encode('ascii'))
            expected_key = base64.b64decode(parts[4].encode('ascii'))

            computed_key = hashlib.pbkdf2_hmac(
                'sha256',
                plain_password.encode('utf-8'),
                salt,
                iterations
            )
            is_valid = hmac.compare_digest(expected_key, computed_key)
            needs_rehash = iterations < PBKDF2_ITERATIONS
            return is_valid, needs_rehash
        except Exception:
            return False, False

    # 3. Fallback para hashes legados en desarrollo (SHA-256 simple)
    if len(hashed_password) == 64:
        legacy_hash = hashlib.sha256(plain_password.encode('utf-8')).hexdigest()
        if hmac.compare_digest(legacy_hash, hashed_password):
            return True, True  # Válido pero requiere rehash inmediato

    return False, False

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')

def _b64url_decode(data_str: str) -> bytes:
    padding = '=' * (4 - (len(data_str) % 4)) if len(data_str) % 4 != 0 else ''
    return base64.urlsafe_b64decode((data_str + padding).encode('ascii'))

def create_access_token(
    subject: str,
    email: str,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None
) -> str:
    """Crea token JWT firmado con HMAC-SHA256 con claims mínimas seguras."""
    now = datetime.utcnow()
    expire = now + (expires_delta or timedelta(minutes=30))
    jti = secrets.token_hex(16)

    payload = {
        "sub": subject,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": "plan-review-ai",
        "jti": jti
    }
    if extra_claims:
        for k, v in extra_claims.items():
            if k not in payload:
                payload[k] = v

    header = {"alg": "HS256", "typ": "JWT"}
    header_json = json.dumps(header, separators=(',', ':')).encode('utf-8')
    payload_json = json.dumps(payload, separators=(',', ':')).encode('utf-8')

    segments = f"{_b64url_encode(header_json)}.{_b64url_encode(payload_json)}"
    signature = hmac.new(
        settings.SECRET_KEY.encode('utf-8'),
        segments.encode('ascii'),
        hashlib.sha256
    ).digest()

    return f"{segments}.{_b64url_encode(signature)}"

def decode_access_token(token: str) -> Dict[str, Any]:
    """Decodifica y valida la firma y expiración del JWT."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            raise ValueError("Token JWT malformado.")

        header_b64, payload_b64, signature_b64 = parts
        segments = f"{header_b64}.{payload_b64}"

        expected_sig = hmac.new(
            settings.SECRET_KEY.encode('utf-8'),
            segments.encode('ascii'),
            hashlib.sha256
        ).digest()

        actual_sig = _b64url_decode(signature_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            raise ValueError("Firma del token inválida.")

        payload_bytes = _b64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode('utf-8'))

        # Verificar expiración
        exp = payload.get("exp")
        if not exp or datetime.utcnow().timestamp() > exp:
            raise ValueError("El token ha expirado.")

        # Verificar si el token fue revocado
        jti = payload.get("jti")
        if jti and jti in _REVOKED_TOKENS:
            raise ValueError("El token ha sido revocado.")

        return payload
    except Exception as e:
        raise ValueError(f"Token no válido: {str(e)}")

def revoke_token(jti: str) -> None:
    """Agrega un token JTI al conjunto de revocación."""
    if jti:
        _REVOKED_TOKENS.add(jti)
