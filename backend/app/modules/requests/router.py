from datetime import date,datetime,time,timezone
from typing import Annotated
from fastapi import APIRouter,Depends,Query
from app.core.config import get_settings
from app.core.errors import AppError
from app.modules.auth.dependencies import require_role,require_roles
from app.modules.requests.schemas import AttendanceRequestCreate,Resolution
from app.modules.requests.service import AttendanceRequestService
router=APIRouter(prefix="/requests",tags=["attendance requests"])
def get_request_service(): return AttendanceRequestService()
def _size(value):
    if value>get_settings().max_page_size: raise AppError("VALIDATION_ERROR","pageSize exceeds the configured limit.",422)
    return value
@router.post("/attendance",status_code=201)
def create(payload:AttendanceRequestCreate,user:Annotated[dict,Depends(require_role("student"))],service:Annotated[AttendanceRequestService,Depends(get_request_service)]): return service.create(payload,user)
@router.get("/mine")
def mine(user:Annotated[dict,Depends(require_role("student"))],service:Annotated[AttendanceRequestService,Depends(get_request_service)],status:str|None=Query(None,pattern="^(pending|approved|rejected|cancelled)$"),page:int=Query(1,ge=1),page_size:int=Query(20,alias="pageSize",ge=1)): return service.mine(user,status,page,_size(page_size))
@router.get("/attendance")
def queue(user:Annotated[dict,Depends(require_roles("faculty","admin"))],service:Annotated[AttendanceRequestService,Depends(get_request_service)],status:str|None=Query(None,pattern="^(pending|approved|rejected|cancelled)$"),student:str|None=None,class_:str|None=Query(None,alias="class"),subject:str|None=None,date_value:date|None=Query(None,alias="date"),page:int=Query(1,ge=1),page_size:int=Query(20,alias="pageSize",ge=1)):
    date_dt=datetime.combine(date_value,time.min,tzinfo=timezone.utc) if date_value else None;return service.queue(user,{"status":status,"student":student,"class":class_,"subject":subject,"date":date_dt},page,_size(page_size))
@router.get("/{request_id}")
def detail(request_id:str,user:Annotated[dict,Depends(require_roles("student","faculty","admin"))],service:Annotated[AttendanceRequestService,Depends(get_request_service)]): return service.get(request_id,user)
@router.post("/{request_id}/cancel")
def cancel(request_id:str,user:Annotated[dict,Depends(require_role("student"))],service:Annotated[AttendanceRequestService,Depends(get_request_service)]): return service.cancel(request_id,user)
@router.post("/{request_id}/approve")
def approve(request_id:str,payload:Resolution,user:Annotated[dict,Depends(require_roles("faculty","admin"))],service:Annotated[AttendanceRequestService,Depends(get_request_service)]): return service.resolve(request_id,"approved",payload.resolution_note,user)
@router.post("/{request_id}/reject")
def reject(request_id:str,payload:Resolution,user:Annotated[dict,Depends(require_roles("faculty","admin"))],service:Annotated[AttendanceRequestService,Depends(get_request_service)]): return service.resolve(request_id,"rejected",payload.resolution_note,user)
