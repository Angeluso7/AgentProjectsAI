from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def list_knowledge():
    return {"module": "knowledge", "status": "placeholder"}
