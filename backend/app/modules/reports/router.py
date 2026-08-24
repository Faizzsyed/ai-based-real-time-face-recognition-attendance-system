"""Versioned, role-scoped reports APIs."""
from datetime import date
from typing import Annotated
from fastapi import APIRouter,Depends,Query
from fastapi.responses import Response
from app.modules.auth.dependencies import require_role
from app.modules.reports.service import ReportService

router=APIRouter(tags=["reports"])
def get_report_service():return ReportService()
def filters(date_from=None,date_to=None,academic_year_id=None,department_id=None,program_id=None,semester_id=None,class_division_id=None,subject_id=None,faculty_id=None):return {k:v for k,v in locals().items() if v is not None}

@router.get("/admin/reports/overview")
def admin_overview(user:Annotated[dict,Depends(require_role("admin"))],service:Annotated[ReportService,Depends(get_report_service)],date_from:date|None=Query(None,alias="dateFrom"),date_to:date|None=Query(None,alias="dateTo"),academic_year_id:str|None=Query(None,alias="academicYearId"),department_id:str|None=Query(None,alias="departmentId"),program_id:str|None=Query(None,alias="programId"),semester_id:str|None=Query(None,alias="semesterId"),class_division_id:str|None=Query(None,alias="classDivisionId"),subject_id:str|None=Query(None,alias="subjectId"),faculty_id:str|None=Query(None,alias="facultyId")):return service.overview(user,filters(date_from,date_to,academic_year_id,department_id,program_id,semester_id,class_division_id,subject_id,faculty_id))
@router.get("/admin/reports/trend")
def admin_trend(user:Annotated[dict,Depends(require_role("admin"))],service:Annotated[ReportService,Depends(get_report_service)],date_from:date|None=Query(None,alias="dateFrom"),date_to:date|None=Query(None,alias="dateTo")):return service.trend(user,filters(date_from,date_to))
@router.get("/admin/reports/departments")
def admin_departments(user:Annotated[dict,Depends(require_role("admin"))],service:Annotated[ReportService,Depends(get_report_service)]):return service.departments(user)
@router.get("/admin/reports/options")
def admin_options(user:Annotated[dict,Depends(require_role("admin"))],service:Annotated[ReportService,Depends(get_report_service)]):return service.options(user)
@router.get("/admin/reports/subjects")
def admin_subjects(user:Annotated[dict,Depends(require_role("admin"))],service:Annotated[ReportService,Depends(get_report_service)],class_division_id:str|None=Query(None,alias="classDivisionId"),subject_id:str|None=Query(None,alias="subjectId"),date_from:date|None=Query(None,alias="dateFrom"),date_to:date|None=Query(None,alias="dateTo")):return service.subjects(user,filters(date_from,date_to,class_division_id=class_division_id,subject_id=subject_id))
@router.get("/admin/reports/classes/{class_id}")
def admin_class(class_id:str,user:Annotated[dict,Depends(require_role("admin"))],service:Annotated[ReportService,Depends(get_report_service)],page:int=1,page_size:int=Query(25,alias="pageSize",ge=1,le=100)):return service.class_report(user,class_id,{"page":page,"page_size":page_size})
@router.get("/admin/reports/students/low-attendance")
def admin_low(user:Annotated[dict,Depends(require_role("admin"))],service:Annotated[ReportService,Depends(get_report_service)],department_id:str|None=Query(None,alias="departmentId"),program_id:str|None=Query(None,alias="programId"),semester_id:str|None=Query(None,alias="semesterId"),class_division_id:str|None=Query(None,alias="classDivisionId"),subject_id:str|None=Query(None,alias="subjectId"),search:str|None=None,page:int=Query(1,ge=1),page_size:int=Query(25,alias="pageSize",ge=1,le=100)):return service.low_attendance(user,{**filters(department_id=department_id,program_id=program_id,semester_id=semester_id,class_division_id=class_division_id,subject_id=subject_id),"search":search or "","page":page,"page_size":page_size})
@router.get("/admin/reports/students/{student_id}")
def admin_student(student_id:str,user:Annotated[dict,Depends(require_role("admin"))],service:Annotated[ReportService,Depends(get_report_service)]):return service.student_report(user,student_id)
@router.get("/admin/reports/sessions/{session_id}")
def admin_session(session_id:str,user:Annotated[dict,Depends(require_role("admin"))],service:Annotated[ReportService,Depends(get_report_service)]):return service.session_report(user,session_id)
@router.get("/admin/reports/exports/low-attendance.csv")
def admin_low_csv(user:Annotated[dict,Depends(require_role("admin"))],service:Annotated[ReportService,Depends(get_report_service)]):
    name,body=service.csv_export(service.low_attendance(user,{"page_size":100}),"Low_Attendance");return Response(body,media_type="text/csv",headers={"Content-Disposition":f'attachment; filename="{name}"'})
@router.get("/admin/reports/exports/classes/{class_id}.csv")
def admin_class_csv(class_id:str,user:Annotated[dict,Depends(require_role("admin"))],service:Annotated[ReportService,Depends(get_report_service)]):
    name,body=service.csv_export(service.class_report(user,class_id,{"page":1,"page_size":100}),f"Class_{class_id}");return Response(body,media_type="text/csv",headers={"Content-Disposition":f'attachment; filename="{name}"'})
@router.get("/admin/reports/exports/sessions/{session_id}.csv")
def admin_session_csv(session_id:str,user:Annotated[dict,Depends(require_role("admin"))],service:Annotated[ReportService,Depends(get_report_service)]):
    name,body=service.csv_export(service.session_report(user,session_id),f"Session_{session_id}");return Response(body,media_type="text/csv",headers={"Content-Disposition":f'attachment; filename="{name}"'})
@router.get("/admin/reports/exports/subjects/{subject_id}.csv")
def admin_subject_csv(subject_id:str,user:Annotated[dict,Depends(require_role("admin"))],service:Annotated[ReportService,Depends(get_report_service)]):
    name,body=service.csv_export(service.subjects(user,{"subject_id":subject_id}),f"Subject_{subject_id}");return Response(body,media_type="text/csv",headers={"Content-Disposition":f'attachment; filename="{name}"'})

@router.get("/faculty/reports/overview")
def faculty_overview(user:Annotated[dict,Depends(require_role("faculty"))],service:Annotated[ReportService,Depends(get_report_service)],date_from:date|None=Query(None,alias="dateFrom"),date_to:date|None=Query(None,alias="dateTo"),class_division_id:str|None=Query(None,alias="classDivisionId"),subject_id:str|None=Query(None,alias="subjectId")):return service.overview(user,filters(date_from,date_to,class_division_id=class_division_id,subject_id=subject_id),True)
@router.get("/faculty/reports/subjects")
def faculty_subjects(user:Annotated[dict,Depends(require_role("faculty"))],service:Annotated[ReportService,Depends(get_report_service)],class_division_id:str|None=Query(None,alias="classDivisionId"),subject_id:str|None=Query(None,alias="subjectId"),date_from:date|None=Query(None,alias="dateFrom"),date_to:date|None=Query(None,alias="dateTo")):return service.subjects(user,filters(date_from,date_to,class_division_id=class_division_id,subject_id=subject_id),True)
@router.get("/faculty/reports/options")
def faculty_options(user:Annotated[dict,Depends(require_role("faculty"))],service:Annotated[ReportService,Depends(get_report_service)]):return service.options(user,True)
@router.get("/faculty/reports/classes/{class_id}")
def faculty_class(class_id:str,user:Annotated[dict,Depends(require_role("faculty"))],service:Annotated[ReportService,Depends(get_report_service)]):return service.class_report(user,class_id,{},True)
@router.get("/faculty/reports/students/{student_id}")
def faculty_student(student_id:str,user:Annotated[dict,Depends(require_role("faculty"))],service:Annotated[ReportService,Depends(get_report_service)]):return service.student_report(user,student_id,True)
@router.get("/faculty/reports/sessions/{session_id}")
def faculty_session(session_id:str,user:Annotated[dict,Depends(require_role("faculty"))],service:Annotated[ReportService,Depends(get_report_service)]):return service.session_report(user,session_id,True)
@router.get("/faculty/reports/exports/classes/{class_id}.csv")
def faculty_class_csv(class_id:str,user:Annotated[dict,Depends(require_role("faculty"))],service:Annotated[ReportService,Depends(get_report_service)]):
    name,body=service.csv_export(service.class_report(user,class_id,{"page":1,"page_size":100},True),f"Class_{class_id}");return Response(body,media_type="text/csv",headers={"Content-Disposition":f'attachment; filename="{name}"'})

@router.get("/student/reports/attendance")
def student_attendance(user:Annotated[dict,Depends(require_role("student"))],service:Annotated[ReportService,Depends(get_report_service)]):return service.student_report(user)
