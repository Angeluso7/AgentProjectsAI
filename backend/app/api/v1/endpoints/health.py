from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def list_health():
    return {"module": "health", "status": "placeholder"}
