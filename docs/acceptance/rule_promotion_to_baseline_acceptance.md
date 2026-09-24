# Criterios de Aceptación y Validación: Promoción de Reglas Candidatas a Baseline QA/QC

## 1. Resumen Ejecutivo
Este documento certifica el cumplimiento de los requerimientos y condiciones de aceptación para la promoción de reglas normativas candidatas hacia el **Baseline QA/QC del Sistema** y su integración efectiva con el motor de auditoría ejecutado en **One-Click Review**.

- **Rama Base:** `feat/symbol-inventory-occurrence-reporting`
- **Rama de Trabajo:** `fix/rule-candidate-promotion-to-baseline`
- **PR Destino:** `feat/symbol-inventory-occurrence-reporting`

---

## 2. Matriz de Criterios de Aceptación

| # | Criterio de Aceptación | Estado | Evidencia de Verificación |
| :--- | :--- | :---: | :--- |
| **AC-01** | **Esquema Solo con Alembic:** Migración `0031` lineal desde `0030`, sin DDL en `main.py` ni startup hooks. | **CUMPLIDO** | `migrations/versions/0031_rule_candidate_promotion_and_lineage.py` implementa `upgrade()` y `downgrade()` reversibles. No hay DDL en `backend/app/main.py`. |
| **AC-02** | **Servicio Único de Dominio:** Promoción individual y masiva unificadas a través de `RulePromotionService.promote_candidate`. | **CUMPLIDO** | `RulePromotionService.promote_candidate(...)` centraliza RBAC, Tenant, taxonomía, linaje, colisión de códigos y transacciones. Utilizado por `rule_candidates.py`, `rules.py` y `intake_extraction_repository.py`. |
| **AC-03** | **Fuente Inmutable:** El frontend no envía campos de origen; el backend deriva `source_document_id`, `source_page`, `source_bbox`, `source_excerpt` y `source_hash` desde la base de datos. | **CUMPLIDO** | `RulePromotionService._derive_immutable_source(...)` lee de `rule_document_items` y `rule_documents`. Auditoría inmutable en `RuleReviewDecision` con `before_snapshot` y `after_snapshot`. |
| **AC-04** | **Taxonomía Validada y applicability_role Normalizado:** Validación estricta de disciplina activa, tópicos pertenecientes y compatibles. Rechazo `HTTP 422` ante combinaciones incompatibles. Vocabulario de rol normalizado (`primary`). | **CUMPLIDO** | Verificación en `RulePromotionService` con normalización de alias (`ARQUITECTURA` -> `ARCHITECTURE`) y auto-seeding. Generación de `RuleApplicability` con `role='primary'`. Pruebas B.1 a B.5 verificadas con HTTP 200 y HTTP 422. |
| **AC-05** | **Separación entre Validar y Promover:** Validar contenido documental no altera el catálogo de `RuleDefinition`. | **CUMPLIDO** | Test unitario e integración `test_validate_content_does_not_promote` verifica que solo cambia `item.status = 'validada'`, sin crear `RuleDefinition` ni `RuleApplicability`. |
| **AC-06** | **Integración con One-Click Review:** La regla promovida y activada es recuperada por el motor de evaluación. | **CUMPLIDO** | Test `test_one_click_review_includes_promoted_rule` confirma que `TaxonomyService.get_applicable_rules(...)` retorna la regla promovida. |
| **AC-07** | **Aislamiento Multi-Tenant & RBAC:** Reglas de otra organización no se pueden acceder; Viewer es rechazado (`403`); Auditor promueve en modo `draft/pending`; Admin activa directamente. | **CUMPLIDO** | Verificado con tests `test_tenant_isolation` y `test_rbac_by_role`. |
| **AC-08** | **Exclusión Estricta de Símbolos:** Un candidato de simbología no puede promoverse a `RuleDefinition`. | **CUMPLIDO** | Test `test_symbol_cannot_be_promoted_to_rule_definition` valida que la API responde `HTTP 400 Bad Request`. |
| **AC-09** | **Idempotencia y Manejo de Colisiones:** Códigos de regla normalizados (`UPPERCASE/TRIM`). La re-promoción actualiza la regla sin duplicarla. | **CUMPLIDO** | Test `test_idempotent_promotion` valida que promover dos veces el mismo candidato no genera duplicados en `rule_definitions`. |
| **AC-10** | **Experiencia de Usuario (UI):** Acciones inequívocas "Validar Contenido", "Promover a Baseline QA/QC" con diálogo modal completo y actualización reactiva de listas sin F5. | **CUMPLIDO** | Componente `DocumentContentReviewModal.tsx` y `RulesPage.tsx` actualizados con tipado TS verificado y compilación limpia (`npm run build` OK). |

---

## 3. Cobertura de Pruebas Automatizadas

Se ejecutó la suite de pruebas de integración con PostgreSQL/SQLite en `backend/tests/integration/`:

```
============================== test session starts ==============================
collected 15 items

backend/tests/integration/test_rule_candidate_promotion.py::test_validate_content_does_not_promote PASSED
backend/tests/integration/test_rule_candidate_promotion.py::test_individual_promotion_creates_rule_lineage PASSED
backend/tests/integration/test_rule_candidate_promotion.py::test_rule_applicability_approved_and_baseline_visible PASSED
backend/tests/integration/test_rule_candidate_promotion.py::test_one_click_review_includes_promoted_rule PASSED
backend/tests/integration/test_rule_candidate_promotion.py::test_idempotent_promotion PASSED
backend/tests/integration/test_rule_candidate_promotion.py::test_tenant_isolation PASSED
backend/tests/integration/test_rule_candidate_promotion.py::test_rbac_by_role PASSED
backend/tests/integration/test_rule_candidate_promotion.py::test_rejection_does_not_create_rule PASSED
backend/tests/integration/test_rule_candidate_promotion.py::test_symbol_cannot_be_promoted_to_rule_definition PASSED
backend/tests/integration/test_rule_candidate_promotion.py::test_taxonomy_piping_pid_symbols_valid PASSED
backend/tests/integration/test_rule_candidate_promotion.py::test_taxonomy_architecture_pid_symbols_invalid PASSED
backend/tests/integration/test_rule_candidate_promotion.py::test_taxonomy_general_document_completeness_valid PASSED
backend/tests/integration/test_rule_candidate_promotion.py::test_taxonomy_nonexistent_topic_invalid PASSED
backend/tests/integration/test_rule_candidate_promotion.py::test_taxonomy_inactive_discipline_invalid PASSED
backend/tests/integration/test_rules_document_content_and_baseline_promotion.py::test_rules_document_content_and_baseline_promotion_flow PASSED

====================== 15 passed in 14.2s ======================
```

---

## 4. Validación de Compilación Frontend

```bash
> tsc && vite build
✓ 1669 modules transformed.
dist/index.html                             0.83 kB │ gzip:   0.47 kB
dist/assets/pdf.worker.min-DKQKFyKK.js  1,087.21 kB
dist/assets/index-DjnSI5tX.css            104.34 kB │ gzip:  16.11 kB
dist/assets/index-D3_jxbvp.js           1,698.41 kB │ gzip: 383.31 kB
✓ built in 41.47s
```
Zero errores de tipos TypeScript (`tsc`) y artefactos listos para producción.
