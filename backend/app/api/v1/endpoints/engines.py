from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from app.services.engines.registry import engine_registry, EngineDefinition, TaskAIPolicy

router = APIRouter()

class SetActiveEngineRequest(BaseModel):
    engine_id: str

class UpdateEngineConfigRequest(BaseModel):
    parameters: Dict[str, Any]

class UpdateCredentialsRequest(BaseModel):
    credentials: Dict[str, str]

class UpdateTaskPolicyRequest(BaseModel):
    active_mode: Optional[str] = None
    fallback_criteria: Optional[str] = None
    escalation_conditions: Optional[str] = None

@router.get("/policies", response_model=List[TaskAIPolicy])
def list_task_ai_policies():
    """Retorna la matriz de políticas de IA definidas por tarea técnica (opción gratuita, opción paga, fallback y escalamiento)."""
    return engine_registry.list_task_policies()

@router.get("/policies/{task_id}", response_model=TaskAIPolicy)
def get_task_ai_policy(task_id: str):
    """Obtiene la política de IA para una tarea específica."""
    policy = engine_registry.get_task_policy(task_id)
    if not policy:
        raise HTTPException(status_code=404, detail=f"Política para tarea '{task_id}' no encontrada.")
    return policy

@router.put("/policies/{task_id}", response_model=TaskAIPolicy)
def update_task_ai_policy(task_id: str, req: UpdateTaskPolicyRequest):
    """Actualiza el modo activo o criterios de escalamiento/fallback para una tarea técnica."""
    try:
        updated = engine_registry.update_task_policy(
            task_id=task_id,
            active_mode=req.active_mode,
            fallback_criteria=req.fallback_criteria,
            escalation_conditions=req.escalation_conditions
        )
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[EngineDefinition])
def list_all_engines(category: Optional[str] = None):
    """Lista todos los motores de IA registrados en el sistema, opcionalmente filtrados por categoría."""
    return engine_registry.list_engines(category=category)

@router.get("/summary")
def get_engines_summary():
    """Retorna un resumen de motores por categoría, activos, costos y estado de salud."""
    all_engines = engine_registry.list_engines()
    categories = ["ocr", "symbols", "layout", "tables", "embeddings", "llm", "rules"]
    
    summary_by_cat = {}
    for cat in categories:
        cat_engines = [e for e in all_engines if e.category == cat]
        active = next((e for e in cat_engines if e.is_active), None)
        summary_by_cat[cat] = {
            "total_engines": len(cat_engines),
            "active_engine_id": active.id if active else None,
            "active_engine_name": active.model_name if active else "Ninguno",
            "active_provider": active.provider if active else None,
            "active_type": active.engine_type if active else None,
            "active_cost": active.cost_tier if active else None
        }

    return {
        "total_engines": len(all_engines),
        "free_engines": sum(1 for e in all_engines if e.cost_tier == "gratis"),
        "paid_engines": sum(1 for e in all_engines if e.cost_tier == "pago"),
        "mixed_engines": sum(1 for e in all_engines if e.cost_tier == "mixto"),
        "categories": summary_by_cat
    }

@router.get("/{category}", response_model=List[EngineDefinition])
def list_category_engines(category: str):
    """Lista los motores disponibles para una categoría específica."""
    engines = engine_registry.list_engines(category=category)
    if not engines:
        raise HTTPException(status_code=404, detail=f"Categoría '{category}' no encontrada.")
    return engines

@router.post("/{category}/active", response_model=EngineDefinition)
def set_active_engine(category: str, req: SetActiveEngineRequest):
    """Selecciona y activa el motor que usará el pipeline para la categoría dada."""
    try:
        updated = engine_registry.set_active_engine(category=category, engine_id=req.engine_id)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{category}/{engine_id}/config", response_model=EngineDefinition)
def update_engine_config(category: str, engine_id: str, req: UpdateEngineConfigRequest):
    """Actualiza parámetros operacionales del motor (thresholds, dpi, max_tokens, etc.)."""
    try:
        updated = engine_registry.update_engine_config(category=category, engine_id=engine_id, parameters=req.parameters)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{category}/{engine_id}/credentials", response_model=EngineDefinition)
def update_engine_credentials(category: str, engine_id: str, req: UpdateCredentialsRequest):
    """Registra o actualiza de forma segura credenciales de API para el motor."""
    try:
        updated = engine_registry.update_credentials(category=category, engine_id=engine_id, credentials=req.credentials)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{category}/{engine_id}/test")
def test_engine(category: str, engine_id: str):
    """Ejecuta una prueba de conectividad y latencia sobre el motor."""
    try:
        result = engine_registry.test_engine_health(category=category, engine_id=engine_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
