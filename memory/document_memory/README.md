# document_memory (Memoria Documental)

Persiste la descomposición estructural y espacial de los planos procesados:
- **Hojas (`document_sheets`)**: Metadatos físicos (DPI, dimensiones mm/px, rotación).
- **Regiones (`sheet_regions`)**: Polígonos de viñetas, áreas de dibujo, notas, leyendas y cuadros.
- **Textos (`extracted_texts`)**: Cajas de texto posicionales normalizadas $[x_0, y_0, x_1, y_1]$ y ángulos.
- **Tablas (`extracted_tables`)**: Matrices de filas y columnas extraídas.
- **Símbolos (`detected_symbols`)**: Bounding boxes, clases y confianza de elementos de visión.
- **Evidencias (`visual_evidences`)**: Recortes de alta resolución vinculados a hallazgos.
