from fastapi import APIRouter
from app.api.v1.endpoints import health, projects, documents, knowledge, rules, reports

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(rules.router, prefix="/rules", tags=["rules"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
