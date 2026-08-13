from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def list_exports():
    return {"module": "exports", "status": "placeholder"}
