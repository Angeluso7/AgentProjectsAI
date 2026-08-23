# MLOps & Active Learning Platform

Este módulo orquesta el ciclo de vida de los modelos de visión y NLP:
- `dvc/`: Versionado inmutable de datasets y pipelines de datos.
- `mlflow/`: Tracking de experimentos, hiperparámetros y registro de modelos (*Model Registry*).
- `evaluation/`: Scripts de benchmarking de precisión ($mAP@50$, Precision, Recall).
- `pipelines/`: Tareas de reentrenamiento continuo gatilladas por la cola de Active Learning.
