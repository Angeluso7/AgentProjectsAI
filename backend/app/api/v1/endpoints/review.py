from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def list_review():
    return {"module": "review", "status": "placeholder"}
