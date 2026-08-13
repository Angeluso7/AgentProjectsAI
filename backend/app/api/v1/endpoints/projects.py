from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def list_projects():
    return {"module": "projects", "status": "placeholder"}
