# Módulo Knowledge (Base de Conocimiento Guía)

Este directorio contiene las definiciones declarativas estáticas de apoyo que nutren las memorias del sistema:

## Estructura
- `standards/`: Normativas nacionales e internacionales estructuradas en JSON/YAML con cláusulas y criterios parametrizados.
- `ontologies/`: Diccionarios de términos canónicos, abreviaturas y sinónimos técnicos por disciplina.
- `title_blocks/`: Plantillas geométricas y anclas posicionales para extracción automática de viñetas.
- `symbol_libraries/`: Catálogos de simbología gráfica normalizada.
- `table_schemas/`: Esquemas esperados de columnas y tipos para cuadros de especificaciones técnicas (cuadros de vanos, cuadros de cargas, etc.).

## Sincronización
Para sincronizar estos archivos estáticos con la base de datos PostgreSQL, ejecuta el endpoint:
`POST /api/v1/knowledge/sync-seed` o el script `python scripts/seed_data.py`.
