from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def list_memories():
    return {"module": "memories", "status": "placeholder"}
