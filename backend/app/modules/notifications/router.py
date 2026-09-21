from typing import Annotated
from fastapi import APIRouter,Depends,Query
from app.core.config import get_settings
from app.core.errors import AppError
from app.modules.auth.dependencies import require_authenticated_user
from app.modules.notifications.service import NotificationService
router=APIRouter(prefix="/notifications",tags=["notifications"])
def get_notification_service(): return NotificationService()
def _size(value):
    if value>get_settings().max_page_size: raise AppError("VALIDATION_ERROR","pageSize exceeds the configured limit.",422)
    return value
@router.get("")
def list_notifications(user:Annotated[dict,Depends(require_authenticated_user)],service:Annotated[NotificationService,Depends(get_notification_service)],page:int=Query(1,ge=1),page_size:int=Query(20,alias="pageSize",ge=1)): return service.list(user,page,_size(page_size))
@router.get("/unread-count")
def unread_count(user:Annotated[dict,Depends(require_authenticated_user)],service:Annotated[NotificationService,Depends(get_notification_service)]): return service.unread_count(user)
@router.post("/{notification_id}/read")
def read(notification_id:str,user:Annotated[dict,Depends(require_authenticated_user)],service:Annotated[NotificationService,Depends(get_notification_service)]): return service.read(notification_id,user)
@router.post("/read-all")
def read_all(user:Annotated[dict,Depends(require_authenticated_user)],service:Annotated[NotificationService,Depends(get_notification_service)]): return service.read_all(user)
