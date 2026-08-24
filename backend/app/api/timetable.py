"""Admin timetable management and scoped Faculty/Student schedule APIs."""
from typing import Annotated
from fastapi import APIRouter,Depends,Query
from app.core.config import get_settings
from app.core.errors import AppError
from app.modules.auth.dependencies import require_role
from app.modules.timetable.schemas import TimetableEntryCreate,TimetableEntryUpdate,TimetableStatusUpdate
from app.modules.timetable.service import TimetableService

router=APIRouter(tags=["timetable"])
def get_timetable_service():return TimetableService()

@router.get("/admin/timetable")
def list_timetable(admin:Annotated[dict,Depends(require_role("admin"))],service:Annotated[TimetableService,Depends(get_timetable_service)],page:int=Query(1,ge=1),page_size:int=Query(20,alias="pageSize",ge=1),academic_year_id:str|None=None,department_id:str|None=None,program_id:str|None=None,semester_id:str|None=None,class_division_id:str|None=None,faculty_id:str|None=None,subject_id:str|None=None,day_of_week:str|None=Query(None,alias="day",pattern="^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$"),status:str|None=Query(None,pattern="^(active|inactive)$")):
    if page_size>get_settings().max_page_size:raise AppError("VALIDATION_ERROR","pageSize exceeds the configured limit.",422)
    filters={k:v for k,v in locals().items() if k in {"academic_year_id","department_id","program_id","semester_id","class_division_id","faculty_id","subject_id","day_of_week","status"} and v};return service.list(str(admin["institution_id"]),filters,page,page_size)
@router.post("/admin/timetable",status_code=201)
def create_timetable(payload:TimetableEntryCreate,admin:Annotated[dict,Depends(require_role("admin"))],service:Annotated[TimetableService,Depends(get_timetable_service)]):return service.create(payload,str(admin["institution_id"]),str(admin["_id"]))
@router.patch("/admin/timetable/{entry_id}")
def update_timetable(entry_id:str,payload:TimetableEntryUpdate,admin:Annotated[dict,Depends(require_role("admin"))],service:Annotated[TimetableService,Depends(get_timetable_service)]):return service.update(entry_id,payload,str(admin["institution_id"]),str(admin["_id"]))
@router.patch("/admin/timetable/{entry_id}/status")
def status_timetable(entry_id:str,payload:TimetableStatusUpdate,admin:Annotated[dict,Depends(require_role("admin"))],service:Annotated[TimetableService,Depends(get_timetable_service)]):return service.set_status(entry_id,payload.status,str(admin["institution_id"]),str(admin["_id"]))
@router.get("/faculty/timetable")
def faculty_timetable(faculty:Annotated[dict,Depends(require_role("faculty"))],service:Annotated[TimetableService,Depends(get_timetable_service)]):return service.faculty_schedule(faculty)
@router.get("/student/timetable")
def student_timetable(student:Annotated[dict,Depends(require_role("student"))],service:Annotated[TimetableService,Depends(get_timetable_service)]):return service.student_schedule(student)
