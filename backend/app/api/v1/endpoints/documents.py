from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def list_documents():
    return {"module": "documents", "status": "placeholder"}
