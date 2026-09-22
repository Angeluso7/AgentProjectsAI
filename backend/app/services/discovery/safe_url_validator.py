import re
import socket
import ipaddress
import logging
from typing import Tuple, Optional, Dict, Any, List
from urllib.parse import urlparse, urljoin
import httpx

logger = logging.getLogger(__name__)

class SafeUrlValidator:
    """
    Validador de Seguridad y Prevención de SSRF (Server-Side Request Forgery):
    1. Esquemas permitidos: únicamente 'http' y 'https'.
    2. Bloqueo estricto de localhost, loopback (127.0.0.0/8, ::1), IPs privadas (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16).
    3. Bloqueo de endpoints de metadata de nubes (169.254.169.254, metadata.google.internal).
    4. Resolución DNS preventiva para evitar DNS rebinding a direcciones internas.
    5. Seguimiento manual y seguro de redirecciones (máximo 5 saltos) revalidando cada salto antes de solicitarlo.
    """

    BLOCKED_HOSTNAMES = {
        "localhost", "localhost.localdomain", "broadcasthost", "ip6-localhost", "ip6-loopback",
        "metadata.google.internal", "metadata.google", "instance-data", "169.254.169.254"
    }

    PRIVATE_NETWORKS = [
        ipaddress.ip_network("0.0.0.0/8"),
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("100.64.0.0/10"),
        ipaddress.ip_network("127.0.0.0/8"),
        ipaddress.ip_network("169.254.0.0/16"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.0.0.0/24"),
        ipaddress.ip_network("192.0.2.0/24"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("198.18.0.0/15"),
        ipaddress.ip_network("198.51.100.0/24"),
        ipaddress.ip_network("203.0.113.0/24"),
        ipaddress.ip_network("224.0.0.0/4"), # Multicast
        ipaddress.ip_network("240.0.0.0/4"), # Reserved
        ipaddress.ip_network("255.255.255.255/32"),
        # IPv6
        ipaddress.ip_network("::1/128"),
        ipaddress.ip_network("::/128"),
        ipaddress.ip_network("fc00::/7"), # Unique local
        ipaddress.ip_network("fe80::/10"), # Link local
        ipaddress.ip_network("ff00::/8") # Multicast
    ]

    @classmethod
    def is_safe_url(cls, url: str) -> Tuple[bool, Optional[str]]:
        """
        Verifica que una URL sea sintácticamente válida y no apunte a infraestructura interna o privada.
        Retorna (is_safe, error_reason_if_unsafe).
        """
        if not url or not isinstance(url, str):
            return False, "URL vacía o no es una cadena válida"

        url_clean = url.strip()
        try:
            parsed = urlparse(url_clean)
        except Exception as e:
            return False, f"Formato de URL inválido: {str(e)}"

        # 1. Esquema permitido
        if parsed.scheme.lower() not in ["http", "https"]:
            return False, f"Esquema no permitido '{parsed.scheme}'. Solo se aceptan http y https"

        hostname = parsed.hostname
        if not hostname:
            return False, "URL no contiene un nombre de host válido"

        hostname_lower = hostname.lower()

        # 2. Nombres de host bloqueados directamente
        if hostname_lower in cls.BLOCKED_HOSTNAMES or hostname_lower.endswith(".local") or hostname_lower.endswith(".internal"):
            return False, f"Host bloqueado por seguridad: {hostname}"

        # 3. Comprobar si el hostname es una IP literal
        try:
            ip_obj = ipaddress.ip_address(hostname_lower)
            if any(ip_obj in net for net in cls.PRIVATE_NETWORKS):
                return False, f"Dirección IP privada o de loopback bloqueada: {hostname_lower}"
        except ValueError:
            # Es un nombre de dominio (no una IP literal), resolver DNS
            try:
                addr_info = socket.getaddrinfo(hostname_lower, None)
                for family, socktype, proto, canonname, sockaddr in addr_info:
                    ip_str = sockaddr[0]
                    resolved_ip = ipaddress.ip_address(ip_str)
                    if any(resolved_ip in net for net in cls.PRIVATE_NETWORKS):
                        return False, f"El dominio {hostname} resuelve a una dirección privada/interna ({ip_str})"
            except socket.gaierror:
                # Si falla DNS, la petición HTTP fallará luego legítimamente
                pass
            except Exception as e:
                logger.warning(f"Error al verificar DNS para {hostname}: {e}")

        return True, None

    @classmethod
    def safe_fetch_html(
        cls,
        initial_url: str,
        timeout: float = 8.0,
        max_hops: int = 5,
        headers: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Realiza una petición HTTP segura controlando cada salto de redirección de manera manual.
        Retorna (is_success, error_reason, response_data).
        """
        # Validar URL inicial
        is_safe, reason = cls.is_safe_url(initial_url)
        if not is_safe:
            return False, f"ssrf_security_block: {reason}", {"submitted_url": initial_url, "resolved_url": initial_url}

        req_headers = headers or {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 PlanReviewAiBot/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-CL,es;q=0.9,en-US;q=0.8,en;q=0.7"
        }

        current_url = initial_url
        hops_history: List[str] = [current_url]

        try:
            with httpx.Client(timeout=timeout, verify=False, follow_redirects=False, headers=req_headers) as client:
                for hop in range(max_hops):
                    resp = client.get(current_url)

                    # Si es una redirección 3xx
                    if resp.status_code in [301, 302, 303, 307, 308]:
                        loc = resp.headers.get("Location")
                        if not loc:
                            return False, "redirect_missing_location", {"resolved_url": current_url}

                        next_url = urljoin(current_url, loc.strip())
                        hops_history.append(next_url)

                        # Validar de forma obligatoria el siguiente salto
                        is_next_safe, next_reason = cls.is_safe_url(next_url)
                        if not is_next_safe:
                            return False, f"ssrf_redirect_block: {next_reason}", {
                                "submitted_url": initial_url,
                                "blocked_redirect_url": next_url,
                                "hops_history": hops_history
                            }

                        current_url = next_url
                        continue

                    # Si no es redirect, procesar respuesta final
                    if resp.status_code != 200:
                        return False, f"http_status_{resp.status_code}", {
                            "status_code": resp.status_code,
                            "submitted_url": initial_url,
                            "resolved_url": current_url,
                            "hops_history": hops_history
                        }

                    raw_html = resp.text
                    return True, None, {
                        "status_code": 200,
                        "submitted_url": initial_url,
                        "resolved_url": current_url,
                        "hops_history": hops_history,
                        "raw_html": raw_html,
                        "headers": dict(resp.headers)
                    }

                return False, f"max_redirect_hops_exceeded_{max_hops}", {
                    "submitted_url": initial_url,
                    "resolved_url": current_url,
                    "hops_history": hops_history
                }

        except httpx.TimeoutException:
            return False, "timeout_exceeded", {"submitted_url": initial_url, "resolved_url": current_url}
        except httpx.RequestError as req_err:
            return False, f"connection_error: {str(req_err)}", {"submitted_url": initial_url, "resolved_url": current_url}
        except Exception as e:
            return False, f"fetch_exception: {str(e)}", {"submitted_url": initial_url, "resolved_url": current_url}
