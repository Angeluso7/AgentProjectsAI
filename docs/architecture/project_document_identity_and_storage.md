# Arquitectura: Identidad Documental y Aislamiento de Almacenamiento por Proyecto

## 1. Principio Fundamental: Documento Lógico vs. Archivo Físico

En **Plan Review AI Hybrid**, se establece una distinción explícita e inmutable entre el **Documento Lógico** y el **Archivo Físico (Binario)**:

1. **Documento Lógico (`Document`)**:
   - Es una entidad perteneciente estrictamente a un proyecto específico (`project_id`) y a una organización/tenant (`organization_id`).
   - Posee su propio ciclo de vida, trazabilidad, estado de procesamiento (`uploaded`, `queued`, `processing`, `processed`, `failed`), clasificación documental (`document_type`), disciplina técnica, número de páginas, láminas rasterizadas (`DocumentSheet`), nodos estructurales y hallazgos QA/QC asociados.
   - **Regla de Oro**: Ningún proyecto puede compartir o reutilizar la entidad lógica `Document` de otro proyecto. Un documento en el Proyecto A jamás debe ser retornado, modificado o mutado por una operación del Proyecto B.

2. **Archivo Físico (Almacenamiento en Disco / Blob Storage)**:
   - Es la secuencia de bytes (`raw_bytes`) persistida en disco local (`settings.RAW_DOCUMENTS_DIR`) o en buckets de almacenamiento (GCS/S3).
   - Su integridad criptográfica se valida mediante el digest SHA-256 (`file_hash_sha256`).

---

## 2. Aislamiento e Identidad Documental en el Modelo de Datos

### 2.1 Unicidad Compuesta por Proyecto
Para evitar el secuestro cruzado de documentos entre proyectos:
- Se elimina la restricción de unicidad global `UNIQUE(file_hash_sha256)`.
- Se establece una clave única compuesta:
  $$\text{UNIQUE}(\text{project\_id}, \text{file\_hash\_sha256})$$
- Se mantiene un índice secundario no único sobre `file_hash_sha256` para búsquedas analíticas y auditoría de procedencia.

### 2.2 Política de Carga y Deduplicación

| Escenario | Comportamiento del Sistema | Resultado |
| :--- | :--- | :--- |
| **Mismo archivo en Proyectos Distintos (A y B)** | Se crea un nuevo registro `Document` independiente con `project_id = B`. Se procesan sus láminas de forma aislada. | Ambos proyectos poseen su propio documento visible en su respectiva biblioteca. Eliminar el Proyecto A no afecta al Proyecto B. |
| **Mismo archivo cargado dos veces en el Mismo Proyecto (A y A)** | Comportamiento idempotente: Se retorna el registro `Document` existente del proyecto. Si el estado anterior fue `failed`, se permite relanzar el procesamiento sin duplicar filas. | No se crean duplicados fantasma en el listado del proyecto. |
| **Eliminación / Vaciar Contenido de Proyecto** | Se purgan los registros `Document` y los archivos asociados a ese proyecto. | Aislamiento garantizado: Los documentos de otros proyectos con el mismo hash binario continúan intactos. |

---

## 3. Hoja de Ruta y Evolución Futura (Almacenamiento Basado en Contenido)

Para este incremento operativo, la prioridad máxima es la **visibilidad inmediata y el aislamiento robusto**. El almacenamiento físico permite rutas asociadas a cada proyecto o nombres de archivo seguros (`{file_hash}_{filename}`).

En fases futuras de escalabilidad petabyte, se podrá evolucionar opcionalmente hacia una capa desacoplada de almacenamiento direccionable por contenido (**Content-Addressed Storage / CAS**):

```mermaid
graph TD
    subgraph Capa Lógica por Proyecto
        P1[Proyecto A] --> DocA[Document A - project_id: A]
        P2[Proyecto B] --> DocB[Document B - project_id: B]
    end

    subgraph Futura Capa de Blobs Desacoplada (Opcional)
        DocA -.->|Apunta a blob_id| BlobStore[(StoredBlob / CAS)]
        DocB -.->|Apunta a blob_id| BlobStore
        BlobStore --> DiskFile[data/raw/sha256_hash]
    end
```

### Directrices de la Futura Capa de Blobs (`StoredBlob`):
1. **Conteo de Referencias Seguro (`ref_count`)**: Un archivo físico sólo podrá eliminarse de disco cuando el contador de proyectos asociados llegue a cero.
2. **Control Estricto de Permisos y Tenant**: Ningún usuario podrá inspeccionar la existencia o metadata de un blob si no tiene permisos explícitos en al menos un proyecto que lo referencie.
3. **No Bloqueante**: La arquitectura actual no depende de CAS para funcionar; la corrección inmediata implementada garantiza 100% de aislamiento y visibilidad sin introducir complejidad prematura.
