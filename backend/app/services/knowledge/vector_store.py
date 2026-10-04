import os
import hashlib
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.core.logging import logger
from app.db.models.knowledge_base import KnowledgeItem, KnowledgeChunk

class VectorStore:
    """
    Cliente y orquestador de indexación vectorial híbrida con Qdrant.
    Gobernanza estricta: Únicamente almacena fragmentos validados y aprobados para reutilización.
    Fallback automático: Si Qdrant no está disponible, no interrumpe los flujos del sistema.
    """

    COLLECTION_NAME = "approved_knowledge"
    VECTOR_DIM = 128 # Dimensión estándar para embeddings normalizados en Fase 1

    def __init__(self, in_memory: bool = False):
        self.client = None
        self._is_available = False
        self._init_qdrant(in_memory=in_memory)

    def _init_qdrant(self, in_memory: bool = False):
        """Inicializa la conexión con Qdrant Client (in-memory para tests o servidor remoto)."""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http import models as qmodels

            qdrant_url = os.getenv("QDRANT_URL")
            qdrant_host = os.getenv("QDRANT_HOST", "localhost")
            qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))

            if in_memory or os.getenv("ENVIRONMENT") == "test":
                self.client = QdrantClient(location=":memory:")
            elif qdrant_url:
                self.client = QdrantClient(url=qdrant_url)
            else:
                self.client = QdrantClient(host=qdrant_host, port=qdrant_port, timeout=2.0)

            # Verificar / Crear colección de conocimiento aprobado
            self._ensure_collection()
            self._is_available = True
            logger.info("Qdrant VectorStore conectado y disponible.")
        except Exception as e:
            self._is_available = False
            self.client = None
            logger.info(f"Qdrant no disponible ({str(e)}). Operando con fallback nativo SQL.")

    def is_available(self) -> bool:
        return self._is_available and self.client is not None

    def _ensure_collection(self):
        """Asegura la existencia de la colección en Qdrant y crea payload indexes para filtros frecuentes."""
        if not self.client:
            return
        from qdrant_client.http import models as qmodels

        collections = self.client.get_collections().collections
        exists = any(c.name == self.COLLECTION_NAME for c in collections)
        if not exists:
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=qmodels.VectorParams(
                    size=self.VECTOR_DIM,
                    distance=qmodels.Distance.COSINE
                )
            )

        # Crear payload indexes para filtros frecuentes (optimización de búsqueda)
        payload_fields = [
            ("organization_id", qmodels.PayloadSchemaType.KEYWORD),
            ("tenant_id", qmodels.PayloadSchemaType.KEYWORD),
            ("project_id", qmodels.PayloadSchemaType.KEYWORD),
            ("discipline", qmodels.PayloadSchemaType.KEYWORD),
            ("governance_status", qmodels.PayloadSchemaType.KEYWORD),
            ("is_active_for_reuse", qmodels.PayloadSchemaType.KEYWORD)
        ]
        for field_name, field_type in payload_fields:
            try:
                self.client.create_payload_index(
                    collection_name=self.COLLECTION_NAME,
                    field_name=field_name,
                    field_schema=field_type
                )
            except Exception:
                pass # Ya existe o in-memory mock sin soporte estricto de schema

    def _generate_dense_vector(self, text: str) -> List[float]:
        """
        Genera un vector denso determinista normalizado de dimensión VECTOR_DIM
        a partir del contenido textual (Fase 1).
        """
        vec = [0.0] * self.VECTOR_DIM
        if not text:
            return vec

        words = text.lower().split()
        for idx, word in enumerate(words):
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            pos = h % self.VECTOR_DIM
            weight = 1.0 / (1.0 + 0.1 * (idx % 10))
            vec[pos] += weight

        # Normalizar L2
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [round(v / norm, 5) for v in vec]
        return vec

    def upsert_approved_chunks(
        self,
        organization_id: str,
        project_id: Optional[str],
        chunks: List[KnowledgeChunk],
        item: KnowledgeItem
    ) -> bool:
        """
        Indexa chunks en Qdrant aplicando REGLA DE GOBERNANZA ESTRICTA:
        Solo se indexan ítems con is_active_for_reuse=True y status in ('validated', 'approved_for_reuse').
        """
        if not self.is_available() or not chunks:
            return False

        # REGLA ESTRICTA DE GOBERNANZA:
        if not item.is_active_for_reuse or item.status not in ["validated", "approved_for_reuse"]:
            logger.debug(f"Ítem '{item.id}' no cumple gobernanza para indexación vectorial (status={item.status}, active={item.is_active_for_reuse}).")
            return False

        from qdrant_client.http import models as qmodels

        try:
            points = []
            for chunk in chunks:
                vector = self._generate_dense_vector(chunk.chunk_text)
                point_id = hashlib.md5(chunk.id.encode("utf-8")).hexdigest()

                payload = {
                    "chunk_id": chunk.id,
                    "item_id": item.id,
                    "organization_id": organization_id,
                    "project_id": project_id,
                    "domain": item.domain,
                    "discipline": item.discipline,
                    "stage": item.stage,
                    "title": item.title,
                    "chunk_title": chunk.chunk_title,
                    "chunk_type": getattr(chunk, "chunk_type", "general"),
                    "hierarchy_path": getattr(chunk, "hierarchy_path", None),
                    "chunk_text": chunk.chunk_text,
                    "structured_data": getattr(chunk, "structured_data", {}),
                    "is_active_for_reuse": True,
                    "governance_status": item.status,
                    "version_number": item.version_number
                }

                points.append(
                    qmodels.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload
                    )
                )

            if points:
                self.client.upsert(
                    collection_name=self.COLLECTION_NAME,
                    points=points
                )
                logger.info(f"Indexados {len(points)} chunks aprobados en Qdrant para item '{item.id}'.")
                return True
        except Exception as e:
            logger.error(f"Error indexando en Qdrant: {str(e)}", exc_info=True)
            return False

        return False

    def delete_item_vectors(self, item_id: str) -> bool:
        """Elimina todos los vectores asociados a un item_id cuando se retira de reutilización o edita."""
        if not self.is_available():
            return False
        from qdrant_client.http import models as qmodels

        try:
            self.client.delete(
                collection_name=self.COLLECTION_NAME,
                points_selector=qmodels.FilterSelector(
                    filter=qmodels.Filter(
                        must=[
                            qmodels.FieldCondition(
                                key="item_id",
                                match=qmodels.MatchValue(value=item_id)
                            )
                        ]
                    )
                )
            )
            return True
        except Exception as e:
            logger.warning(f"No se pudieron eliminar vectores en Qdrant para '{item_id}': {e}")
            return False

    def hybrid_search(
        self,
        organization_id: str,
        query_text: str,
        project_id: Optional[str] = None,
        discipline: Optional[str] = None,
        secondary_disciplines: Optional[List[str]] = None,
        stage: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Búsqueda vectorial en Qdrant con filtros estrictos de tenant, gobernanza y proyecto.
        Soporta filtrado multidisciplinario con primary_discipline y secondary_disciplines.
        Retorna lista de resultados con metadatos estructurados o lista vacía para fallback SQL.
        """
        if not self.is_available() or not query_text.strip():
            return []

        from qdrant_client.http import models as qmodels

        try:
            query_vector = self._generate_dense_vector(query_text)

            # Filtros estrictos de aislamiento y gobernanza
            must_conditions = [
                qmodels.FieldCondition(
                    key="organization_id",
                    match=qmodels.MatchValue(value=organization_id)
                ),
                qmodels.FieldCondition(
                    key="is_active_for_reuse",
                    match=qmodels.MatchValue(value=True)
                )
            ]

            # Filtro de proyecto (proyecto actual + conocimiento global donde project_id es None)
            if project_id:
                should_proj = [
                    qmodels.FieldCondition(key="project_id", match=qmodels.MatchValue(value=project_id)),
                    qmodels.IsNullCondition(is_null=qmodels.PayloadField(key="project_id"))
                ]
                must_conditions.append(qmodels.Filter(should=should_proj))

            # Filtrado multidisciplinario (disciplina primaria + disciplinas secundarias + 'general')
            all_target_disciplines = set()
            if discipline and discipline != "general":
                all_target_disciplines.add(discipline)
            if secondary_disciplines:
                for sd in secondary_disciplines:
                    if sd and sd != "general":
                        all_target_disciplines.add(sd)

            if all_target_disciplines:
                # Permitir matches con cualquiera de las disciplinas solicitadas o con reglas 'general'
                must_conditions.append(
                    qmodels.Filter(
                        should=[
                            qmodels.FieldCondition(
                                key="discipline",
                                match=qmodels.MatchAny(any=list(all_target_disciplines) + ["general"])
                            )
                        ]
                    )
                )

            query_filter = qmodels.Filter(must=must_conditions)

            if hasattr(self.client, "query_points"):
                response = self.client.query_points(
                    collection_name=self.COLLECTION_NAME,
                    query=query_vector,
                    query_filter=query_filter,
                    limit=top_k
                )
                search_result = response.points
            elif hasattr(self.client, "search"):
                search_result = self.client.search(
                    collection_name=self.COLLECTION_NAME,
                    query_vector=query_vector,
                    query_filter=query_filter,
                    limit=top_k
                )
            else:
                search_result = []

            formatted_results = []
            for hit in search_result:
                payload = hit.payload or {}
                formatted_results.append({
                    "score": round(hit.score, 4),
                    "chunk_id": payload.get("chunk_id"),
                    "item_id": payload.get("item_id"),
                    "title": payload.get("title"),
                    "chunk_title": payload.get("chunk_title"),
                    "chunk_type": payload.get("chunk_type", "general"),
                    "hierarchy_path": payload.get("hierarchy_path"),
                    "domain": payload.get("domain"),
                    "snippet": payload.get("chunk_text", "")[:350],
                    "structured_data": payload.get("structured_data", {}),
                    "provenance": {
                        "governance_status": payload.get("governance_status"),
                        "version_number": payload.get("version_number"),
                        "discipline": payload.get("discipline")
                    }
                })

            return formatted_results
        except Exception as e:
            logger.warning(f"Fallo en consulta Qdrant: {e}. Activando fallback SQL.")
            return []
