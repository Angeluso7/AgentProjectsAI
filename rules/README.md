# Motor de Reglas Determinísticas (Rules Engine)

Este directorio contiene las definiciones modulares y tipadas del motor de reglas determinísticas por especialidad:

## Organización
- `shared/`: Interfaces base (`BaseRule`, `RuleContext`, `RuleResult`).
- `qa_qc/`: Reglas generales de integridad de planos (completitud de viñeta, formato de escala, fechas y códigos únicos).
- `architecture/`: Reglas normativas y dimensionales de arquitectura (anchos de vanos, alturas libres, vías de evacuación).
- `electrical/`: Reglas de seguridad e instalaciones eléctricas (zonas de despeje, capacidades y simbología).

Todas las reglas extienden de `BaseRule` e implementan el método `evaluate(context: RuleContext) -> RuleResult`, garantizando una evaluación determinística sin alucinaciones.
