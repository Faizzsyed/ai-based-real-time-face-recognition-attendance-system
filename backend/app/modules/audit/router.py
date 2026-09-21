from datetime import date,datetime,time,timezone
from typing import Annotated
from fastapi import APIRouter,Depends,Query
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.object_id import serialize_document
from app.modules.auth.dependencies import require_role
from app.modules.audit.service import AuditService
router=APIRouter(prefix="/audit",tags=["audit"])
def get_audit_service(): return AuditService()
def _size(value):
    if value>get_settings().max_page_size: raise AppError("VALIDATION_ERROR","pageSize exceeds the configured limit.",422)
    return value
def _start(value): return datetime.combine(value,time.min,tzinfo=timezone.utc) if value else None
def _end(value): return datetime.combine(value,time.max,tzinfo=timezone.utc) if value else None
@router.get("")
def list_audit(user:Annotated[dict,Depends(require_role("admin"))],service:Annotated[AuditService,Depends(get_audit_service)],action:str|None=None,actor:str|None=None,role:str|None=None,entity_type:str|None=Query(None,alias="entityType"),date_from:date|None=Query(None,alias="dateFrom"),date_to:date|None=Query(None,alias="dateTo"),search:str|None=None,page:int=Query(1,ge=1),page_size:int=Query(20,alias="pageSize",ge=1)):
    return service.list(user["institution_id"],{"action":action,"actor":actor,"actor_role":role,"entity_type":entity_type,"date_from":_start(date_from),"date_to":_end(date_to),"search":search},page,_size(page_size))
@router.get("/{event_id}")
def detail(event_id:str,user:Annotated[dict,Depends(require_role("admin"))],service:Annotated[AuditService,Depends(get_audit_service)]):
    item=service.get(event_id,user["institution_id"])
    if not item: raise AppError("AUDIT_EVENT_NOT_FOUND","Audit event was not found.",404)
    return serialize_document(item)
