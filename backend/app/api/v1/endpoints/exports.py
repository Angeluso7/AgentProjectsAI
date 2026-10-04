from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("/runs/{run_id}/json")
def export_run_json(run_id: str):
    """Exporta los hallazgos en formato JSON estructurado."""
    return {
        "review_run_id": run_id,
        "format": "json_v1",
        "findings": []
    }
