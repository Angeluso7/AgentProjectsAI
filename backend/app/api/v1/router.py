from fastapi import APIRouter
from app.api.v1.endpoints import (
    health, auth, organizations, jobs, review_tasks, policies, traces, pipelines,
    projects, documents, ocr, layout, tables, symbols, intake, knowledge, review_runs, findings,
    memories, rules, review, training, reports, exports, evaluations, engines, annotations,
    intake_extractions, completeness, observations, consolidated_reports, assistant,
    maturity, acquisition, dashboard, translations, symbol_catalog
)

api_router = APIRouter()
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])

# 0. Identidad, Autenticación y Organizaciones (Fase 3)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(evaluations.router, prefix="/evaluations", tags=["evaluations"])
api_router.include_router(engines.router, prefix="/engines", tags=["engines"])
api_router.include_router(annotations.router, prefix="/annotations", tags=["annotations"])
api_router.include_router(intake_extractions.router, prefix="/intake/extractions", tags=["intake-extractions"])
api_router.include_router(completeness.router, prefix="/completeness", tags=["completeness"])
api_router.include_router(observations.router, prefix="/observations", tags=["observations"])
api_router.include_router(consolidated_reports.router, prefix="/reports/consolidated", tags=["consolidated-reports"])
api_router.include_router(assistant.router, prefix="/assistant", tags=["assistant"])
api_router.include_router(maturity.router, prefix="", tags=["maturity"])
api_router.include_router(acquisition.router, prefix="/acquisition", tags=["acquisition"])
api_router.include_router(translations.router, prefix="/translations", tags=["translations"])

# 1. Operaciones, Jobs Asíncronos y Pipelines

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(pipelines.router, prefix="/pipelines", tags=["pipelines"])
api_router.include_router(review_tasks.router, prefix="/review-tasks", tags=["review-tasks"])
api_router.include_router(policies.router, prefix="/policies", tags=["policies"])
api_router.include_router(traces.router, prefix="/traces", tags=["traces"])

# 2. Intake y Gestión de Entidades
api_router.include_router(intake.router, prefix="/intake", tags=["intake"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(ocr.router, prefix="/ocr", tags=["ocr"])
api_router.include_router(layout.router, prefix="/layout", tags=["layout"])
api_router.include_router(tables.router, prefix="/tables", tags=["tables"])
api_router.include_router(symbols.router, prefix="/symbols", tags=["symbols"])
api_router.include_router(symbol_catalog.router, prefix="/symbol-catalog", tags=["symbol-catalog"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(review_runs.router, prefix="/review-runs", tags=["review-runs"])
api_router.include_router(findings.router, prefix="/findings", tags=["findings"])

# 3. Soporte y Dominio
api_router.include_router(rules.router, prefix="/rules", tags=["rules"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(memories.router, prefix="/memories", tags=["memories"])
api_router.include_router(review.router, prefix="/review", tags=["review"])
api_router.include_router(training.router, prefix="/training", tags=["training"])
api_router.include_router(exports.router, prefix="/exports", tags=["exports"])
