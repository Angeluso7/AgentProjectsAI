import logging
import os
import base64
from typing import Optional, Dict, Any
from app.core.settings import settings

logger = logging.getLogger(__name__)

# Normalización de alias comunes para modelos de Anthropic Claude
MODEL_ALIASES = {
    "claude-sonnet-5-5": "claude-3-5-sonnet-20241022",
    "claude-3-5-sonnet": "claude-3-5-sonnet-20241022",
    "claude-3.5-sonnet": "claude-3-5-sonnet-20241022",
    "claude-3-7-sonnet": "claude-3-7-sonnet-20250219",
}


class ClaudeClientError(Exception):
    """Excepción base para errores de llamada al cliente Claude."""
    pass


class ClaudeClientDisabledError(ClaudeClientError):
    """Lanzada cuando se intenta usar el cliente en modo deshabilitado (sin API key)."""
    pass


class ClaudeClient:
    """
    Cliente desacoplado para llamadas al SDK de Anthropic Claude.
    Permite llamadas de texto sin streaming, manejo transparente de modo disabled
    e inyección de dependencias para testing / mocks sin tocar la API real.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        client: Optional[Any] = None,
    ):
        self._raw_api_key = api_key if api_key is not None else settings.ANTHROPIC_API_KEY
        self.model = model or getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-5-5")
        self._client = client

        # Evaluar si está habilitado
        self.is_enabled = self._check_enabled()

        if self.is_enabled and self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self._raw_api_key)
            except Exception as e:
                logger.warning(f"No se pudo inicializar el cliente Anthropic: {e}")
                self.is_enabled = False
                self._client = None

    def _check_enabled(self) -> bool:
        if not self._raw_api_key:
            return False
        clean_key = str(self._raw_api_key).strip()
        if not clean_key or clean_key.startswith("sk-ant-xxxxx"):
            return False
        return True

    def is_available(self) -> bool:
        """Indica si el cliente cuenta con credenciales activas y cliente listo."""
        return self.is_enabled and self._client is not None

    def _resolve_model(self) -> str:
        """Resuelve el alias del modelo a un identificador reconocido por la API."""
        return MODEL_ALIASES.get(self.model, self.model)

    def complete(
        self,
        system_prompt: Optional[str] = None,
        user_prompt: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> str:
        """
        Ejecuta una completitud de texto usando Claude de Anthropic.
        Lanza ClaudeClientDisabledError si no hay API key configurada.
        Lanza ClaudeClientError si la llamada al SDK falla.
        """
        if not self.is_available():
            raise ClaudeClientDisabledError(
                "ClaudeClient está deshabilitado: ANTHROPIC_API_KEY no configurada o vacía."
            )

        target_model = self._resolve_model()

        try:
            kwargs: Dict[str, Any] = {
                "model": target_model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": user_prompt}],
            }
            if system_prompt:
                kwargs["system"] = system_prompt
            if temperature is not None:
                kwargs["extra_body"] = {"temperature": temperature}

            response = self._client.messages.create(**kwargs)

            # Extraer bloques de texto devueltos por Anthropic Messages API
            text_chunks = []
            for block in getattr(response, "content", []):
                if hasattr(block, "text"):
                    text_chunks.append(block.text)
                elif isinstance(block, dict) and "text" in block:
                    text_chunks.append(block["text"])

            return "".join(text_chunks)

        except Exception as e:
            # Nunca imprimir ni loguear la clave secreta
            err_msg = getattr(e, "message", str(e))
            logger.error(f"Error en llamada a Anthropic Claude ({target_model}): {err_msg}")
            raise ClaudeClientError(f"Error invocando Claude API: {err_msg}") from e

    def complete_vision(
        self,
        system_prompt: Optional[str] = None,
        user_prompt: str = "",
        image_path: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> str:
        """
        Ejecuta una completitud multimodal (imagen + texto) usando Claude de Anthropic.
        Lanza ClaudeClientDisabledError si no hay API key configurada.
        Lanza ClaudeClientError si el archivo no existe o la llamada al SDK falla.
        """
        if not self.is_available():
            raise ClaudeClientDisabledError(
                "ClaudeClient está deshabilitado: ANTHROPIC_API_KEY no configurada o vacía."
            )

        if not image_path or not os.path.exists(image_path):
            raise ClaudeClientError(f"No se encontró la imagen en la ruta especificada: {image_path}")

        ext = os.path.splitext(image_path)[1].lower()
        if ext in (".jpg", ".jpeg"):
            media_type = "image/jpeg"
        elif ext == ".png":
            media_type = "image/png"
        elif ext == ".webp":
            media_type = "image/webp"
        elif ext == ".gif":
            media_type = "image/gif"
        else:
            media_type = "image/png"

        try:
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            raise ClaudeClientError(f"Error al leer la imagen {image_path}: {e}") from e

        target_model = self._resolve_model()

        try:
            content_blocks = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data,
                    },
                },
                {
                    "type": "text",
                    "text": user_prompt,
                },
            ]

            kwargs: Dict[str, Any] = {
                "model": target_model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": content_blocks}],
            }
            if system_prompt:
                kwargs["system"] = system_prompt
            if temperature is not None:
                kwargs["extra_body"] = {"temperature": temperature}

            response = self._client.messages.create(**kwargs)

            text_chunks = []
            for block in getattr(response, "content", []):
                if hasattr(block, "text"):
                    text_chunks.append(block.text)
                elif isinstance(block, dict) and "text" in block:
                    text_chunks.append(block["text"])

            return "".join(text_chunks)

        except Exception as e:
            err_msg = getattr(e, "message", str(e))
            logger.error(f"Error en llamada de visión a Anthropic Claude ({target_model}): {err_msg}")
            raise ClaudeClientError(f"Error invocando Claude Vision API: {err_msg}") from e

