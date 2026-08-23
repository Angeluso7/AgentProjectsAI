# Capa de Memorias Persistentes

Este directorio documenta y almacena las 4 memorias clave del sistema:
1. `document_memory/`: Hojas, textos, regiones, tablas, símbolos y evidencias visuales.
2. `normative_memory/`: Normas, cláusulas, criterios y relaciones normativas.
3. `template_memory/`: Viñetas, simbologías, esquemas de tablas y ontologías.
4. `decision_memory/`: Hallazgos previos, excepciones, validaciones y feedback humano.

Todas estas memorias se persisten formalmente en PostgreSQL + PostGIS a través de los modelos ORM de SQLAlchemy ubicados en `backend/app/db/models/`.
