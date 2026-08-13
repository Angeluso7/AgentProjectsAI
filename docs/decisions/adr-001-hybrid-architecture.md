# ADR-001 Arquitectura híbrida

Se adopta una arquitectura híbrida para evitar dependencia total del modelo.

## Decisión
Usar OCR + visión + base de conocimiento + reglas + revisión humana + active learning.

## Consecuencia
El sistema puede mejorar con datos nuevos sin requerir siempre reentrenamiento completo.
