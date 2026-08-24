"""Production Faculty management, assignment, import, and self-service API."""
import csv,io
from typing import Annotated
from fastapi import APIRouter,Depends,File,Query,UploadFile
from fastapi.responses import PlainTextResponse
from app.core.config import get_settings
from app.core.errors import AppError
from app.modules.auth.dependencies import require_role
from app.modules.faculty.schemas import AssignmentCreate,AssignmentUpdate,FacultyCreate,FacultyStatusUpdate,FacultyUpdate
from app.modules.faculty.service import FacultyService

router=APIRouter(tags=["faculty"])
CSV_FIELDS=["employee_id","name","email","username","phone","department_code","designation","temporary_password"]
CSV_REQUIRED=[x for x in CSV_FIELDS if x not in {"phone","designation"}]
def get_faculty_service(): return FacultyService()

async def csv_rows(file):
    if not (file.filename or "").lower().endswith(".csv"): raise AppError("CSV_IMPORT_INVALID","Only .csv files are accepted.",422)
    if file.content_type and file.content_type.casefold() not in {"text/csv","application/csv","application/vnd.ms-excel","text/plain","application/octet-stream"}: raise AppError("CSV_IMPORT_INVALID","CSV MIME type is not accepted.",422)
    data=await file.read(1_048_577)
    if len(data)>1_048_576: raise AppError("CSV_IMPORT_INVALID","CSV must not exceed 1 MB.",413)
    try: text=data.decode("utf-8-sig")
    except UnicodeDecodeError as exc: raise AppError("CSV_IMPORT_INVALID","CSV must use UTF-8.",422) from exc
    reader=csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or any(x not in reader.fieldnames for x in CSV_REQUIRED): raise AppError("CSV_IMPORT_INVALID","CSV headers are incomplete.",422)
    rows=list(reader)
    if not rows: raise AppError("CSV_IMPORT_INVALID","CSV must contain at least one Faculty row.",422)
    if len(rows)>500: raise AppError("CSV_IMPORT_INVALID","CSV is limited to 500 rows.",422)
    return rows
def csv_payload(row,service,iid):
    dept=service.academics["departments"].repository.find_one({"institution_id":iid,"code":row.get("department_code","").strip().upper()})
    if not dept: raise AppError("CSV_IMPORT_INVALID","Unknown department code.",422)
    return {"employee_id":row.get("employee_id"),"display_name":row.get("name"),"email":row.get("email"),"username":row.get("username"),"phone":row.get("phone") or None,"department_id":str(dept["_id"]),"designation":row.get("designation") or None,"temporary_password":row.get("temporary_password")}
def validate_rows(rows,service,iid):
    report=[]; seen={"employee_id":set(),"email":set(),"username":set()}
    for number,row in enumerate(rows,2):
        errors=[]; signature={"employee_id":row.get("employee_id","").upper(),"email":row.get("email","").casefold(),"username":row.get("username","").casefold()}
        for field,value in signature.items():
            if value and value in seen[field]: errors.append(f"Duplicate {field} within CSV.")
            if value: seen[field].add(value)
        if any(str(v).lstrip().startswith(("=","+","-","@")) for v in row.values()): errors.append("Spreadsheet formulas are not permitted.")
        try:
            model=FacultyCreate.model_validate(csv_payload(row,service,iid))
            if not errors: service.validate_create(model,iid)
        except Exception as exc: errors.append(getattr(exc,"message",str(exc)))
        report.append({"row":number,"valid":not errors,"errors":errors})
    return report

@router.get("/admin/faculty/import/template",response_class=PlainTextResponse)
def template(admin:Annotated[dict,Depends(require_role("admin"))]):
    out=io.StringIO(); csv.writer(out).writerow(CSV_FIELDS); return out.getvalue()
@router.post("/admin/faculty/import/preview")
async def preview(file:Annotated[UploadFile,File(...)],admin:Annotated[dict,Depends(require_role("admin"))],service:Annotated[FacultyService,Depends(get_faculty_service)]):
    rows=await csv_rows(file); report=validate_rows(rows,service,str(admin["institution_id"])); return {"total":len(report),"valid":sum(x["valid"] for x in report),"invalid":sum(not x["valid"] for x in report),"duplicates":sum(any("Duplicate" in e for e in x["errors"]) for x in report),"rows":report,"writesPerformed":False}
@router.post("/admin/faculty/import/confirm")
async def confirm(file:Annotated[UploadFile,File(...)],confirm:bool,admin:Annotated[dict,Depends(require_role("admin"))],service:Annotated[FacultyService,Depends(get_faculty_service)]):
    if not confirm: raise AppError("IMPORT_CONFIRMATION_REQUIRED","Explicit confirmation is required.",422)
    rows=await csv_rows(file); report=validate_rows(rows,service,str(admin["institution_id"]))
    if any(not x["valid"] for x in report): return {"imported":0,"rejected":len(report),"rows":report}
    made=[]
    for batch_start in range(0,len(rows),100):
        for offset,row in enumerate(rows[batch_start:batch_start+100],batch_start):
            number=offset+2
            try:
                payload=csv_payload(row,service,str(admin["institution_id"])); result=service.create(FacultyCreate.model_validate(payload),str(admin["institution_id"]),str(admin["_id"])); made.append({"row":number,"facultyId":result["_id"],"username":payload["username"],"temporaryPassword":payload["temporary_password"]})
            except Exception as exc:
                failed=next(item for item in report if item["row"]==number); failed["valid"]=False; failed["errors"]=[getattr(exc,"message",str(exc))]
    return {"imported":len(made),"rejected":len(rows)-len(made),"credentials":made,"rows":report}

@router.get("/admin/faculty")
def list_faculty(admin:Annotated[dict,Depends(require_role("admin"))],service:Annotated[FacultyService,Depends(get_faculty_service)],page:int=Query(1,ge=1),page_size:int=Query(20,alias="pageSize",ge=1),search:str|None=Query(None,max_length=100),status:str|None=Query(None,pattern="^(active|inactive|suspended|resigned|archived)$"),department_id:str|None=None,account_status:str|None=Query(None,pattern="^(active|inactive|suspended)$")):
    if page_size>get_settings().max_page_size: raise AppError("VALIDATION_ERROR","pageSize exceeds the configured limit.",422)
    return service.list(str(admin["institution_id"]),{"status":status,"department_id":department_id,"account_status":account_status},search,page,page_size)
@router.post("/admin/faculty",status_code=201)
def create_faculty(payload:FacultyCreate,admin:Annotated[dict,Depends(require_role("admin"))],service:Annotated[FacultyService,Depends(get_faculty_service)]): return service.create(payload,str(admin["institution_id"]),str(admin["_id"]))
@router.get("/admin/faculty/{faculty_id}")
def get_faculty(faculty_id:str,admin:Annotated[dict,Depends(require_role("admin"))],service:Annotated[FacultyService,Depends(get_faculty_service)]): return service.get(faculty_id,str(admin["institution_id"]))
@router.patch("/admin/faculty/{faculty_id}")
def update_faculty(faculty_id:str,payload:FacultyUpdate,admin:Annotated[dict,Depends(require_role("admin"))],service:Annotated[FacultyService,Depends(get_faculty_service)]): return service.update(faculty_id,payload,str(admin["institution_id"]),str(admin["_id"]))
@router.patch("/admin/faculty/{faculty_id}/status")
def status_faculty(faculty_id:str,payload:FacultyStatusUpdate,admin:Annotated[dict,Depends(require_role("admin"))],service:Annotated[FacultyService,Depends(get_faculty_service)]): return service.set_status(faculty_id,payload,str(admin["institution_id"]),str(admin["_id"]))
@router.get("/admin/faculty/{faculty_id}/assignments")
def assignments(faculty_id:str,admin:Annotated[dict,Depends(require_role("admin"))],service:Annotated[FacultyService,Depends(get_faculty_service)]): return service.get(faculty_id,str(admin["institution_id"]))["assignments"]
@router.post("/admin/faculty/{faculty_id}/assignments",status_code=201)
def create_assignment(faculty_id:str,payload:AssignmentCreate,admin:Annotated[dict,Depends(require_role("admin"))],service:Annotated[FacultyService,Depends(get_faculty_service)]): return service.create_assignment(faculty_id,payload,str(admin["institution_id"]),str(admin["_id"]))
@router.patch("/admin/faculty/{faculty_id}/assignments/{assignment_id}")
def update_assignment(faculty_id:str,assignment_id:str,payload:AssignmentUpdate,admin:Annotated[dict,Depends(require_role("admin"))],service:Annotated[FacultyService,Depends(get_faculty_service)]): return service.update_assignment(faculty_id,assignment_id,payload,str(admin["institution_id"]),str(admin["_id"]))
@router.delete("/admin/faculty/{faculty_id}/assignments/{assignment_id}")
def deactivate_assignment(faculty_id:str,assignment_id:str,admin:Annotated[dict,Depends(require_role("admin"))],service:Annotated[FacultyService,Depends(get_faculty_service)]): return service.deactivate_assignment(faculty_id,assignment_id,str(admin["institution_id"]),str(admin["_id"]))
@router.get("/faculty/profile")
def self_profile(faculty:Annotated[dict,Depends(require_role("faculty"))],service:Annotated[FacultyService,Depends(get_faculty_service)]): return service.self_profile(faculty)
@router.get("/faculty/assignments")
def own_assignments(faculty:Annotated[dict,Depends(require_role("faculty"))],service:Annotated[FacultyService,Depends(get_faculty_service)]): return service.own_assignments(faculty)
