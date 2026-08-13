from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def list_training():
    return {"module": "training", "status": "placeholder"}
