"""Tenant-scoped Faculty identity and teaching-assignment orchestration."""
from datetime import date,datetime,timezone
from types import SimpleNamespace
from app.core.errors import AppError
from app.core.security import PasswordService
from app.db.object_id import parse_object_id,serialize_document
from app.modules.academic_common.services import build_services
from app.modules.auth.repositories import UserRepository
from app.modules.faculty.repositories import AssignmentRepository,FacultyRepository
import logging
from app.core.logging import safe_log
logger=logging.getLogger("FACULTY")

def dt(value): return datetime.combine(value,datetime.min.time(),tzinfo=timezone.utc) if isinstance(value,date) and not isinstance(value,datetime) else value
def missing(): return AppError("FACULTY_NOT_FOUND","Faculty was not found.",404)

class FacultyService:
    def __init__(self,faculty=None,assignments=None,users=None,academics=None,passwords=None):
        self.faculty=faculty or FacultyRepository(); self.assignments=assignments or AssignmentRepository(); self.users=users or UserRepository(); self.academics=academics or build_services(); self.passwords=passwords or PasswordService()
    def academic(self,resource,value,iid):
        doc=self.academics[resource].repository.find_by_id(value)
        if not doc or str(doc.get("institution_id"))!=str(iid): raise AppError("CROSS_INSTITUTION_REFERENCE","Academic reference is outside this Institution.",422)
        if doc.get("status","active")!="active": raise AppError("INACTIVE_ACADEMIC_REFERENCE","Academic reference is inactive.",422)
        return doc
    def validate_create(self,model,iid):
        if self.faculty.find_by_employee(iid,model.employee_id): raise AppError("DUPLICATE_EMPLOYEE_ID","Employee ID already exists.",409)
        duplicate=self.users.find_scoped_duplicate(iid,model.email,model.username)
        if duplicate:
            raise AppError("USER_EMAIL_ALREADY_EXISTS" if duplicate.get("email")==model.email else "USER_USERNAME_ALREADY_EXISTS","Faculty account email or username already exists.",409)
        self.academic("departments",model.department_id,iid)
    def validate_assignment(self,fid,model,iid,exclude=None):
        faculty=self.faculty.find_by_id(fid,iid)
        if not faculty: raise missing()
        if faculty.get("status")!="active": raise AppError("FACULTY_INACTIVE","Only active Faculty can receive teaching assignments.",409)
        year=self.academic("academic-years",model.academic_year_id,iid); subject=self.academic("subjects",model.subject_id,iid); division=self.academic("classes",model.class_division_id,iid)
        if str(division.get("academic_year_id"))!=str(year["_id"]) or str(subject.get("program_id"))!=str(division.get("program_id")) or str(subject.get("semester_id"))!=str(division.get("semester_id")) or str(subject.get("department_id"))!=str(division.get("department_id")):
            raise AppError("INVALID_FACULTY_ASSIGNMENT","Subject and Class do not belong to the selected academic hierarchy.",422)
        if str(faculty.get("department_id"))!=str(subject.get("department_id")): raise AppError("INVALID_FACULTY_ASSIGNMENT","Faculty Department does not own the selected Subject.",422)
        if model.status=="active" and self.assignments.duplicate_active(iid,fid,model.academic_year_id,model.subject_id,model.class_division_id,model.assignment_type,exclude): raise AppError("DUPLICATE_FACULTY_ASSIGNMENT","Equivalent active assignment already exists.",409)
    def create(self,model,iid,actor):
        self.validate_create(model,iid); now=datetime.now(timezone.utc); ioid=parse_object_id(iid,"institution_id"); user=profile=None; made=[]
        try:
            user=self.users.insert({"institution_id":ioid,"role":"faculty","username":model.username,"email":model.email,"display_name":model.display_name,"password_hash":self.passwords.hash_password(model.temporary_password),"status":"active","must_change_password":True,"token_version":0,"failed_login_attempts":0,"locked_until":None,"last_login_at":None,"created_at":now,"updated_at":now,"created_by":parse_object_id(actor,"actor_id")})
            doc=model.model_dump(exclude={"username","temporary_password","assignments"}); doc.update({"institution_id":ioid,"user_id":user["_id"],"department_id":parse_object_id(model.department_id,"department_id"),"status":"active","joining_date":dt(model.joining_date),"created_at":now,"updated_at":now,"created_by":parse_object_id(actor,"actor_id")})
            profile=self.faculty.insert(doc); self.users.update(user["_id"],{"faculty_id":profile["_id"]})
            for assignment in model.assignments: made.append(self.create_assignment(str(profile["_id"]),assignment,iid,actor))
            safe_log(logger,logging.INFO,"Faculty created",faculty_id=str(profile["_id"]));return self.get(str(profile["_id"]),iid)
        except Exception:
            for assignment in made: self.assignments.delete_created(assignment["_id"])
            if profile: self.faculty.delete_created(profile["_id"])
            if user: self.users.delete_created(user["_id"])
            raise
    def list(self,iid,filters,search,page,size):
        items,total=self.faculty.list(iid,filters,search,page,size)
        return {"items":[serialize_document(x) for x in items],"pagination":{"page":page,"pageSize":size,"total":total,"pages":(total+size-1)//size}}
    def get(self,fid,iid):
        profile=self.faculty.find_by_id(fid,iid)
        if not profile: raise missing()
        user=self.users.find_by_id(profile["user_id"]); account={k:user.get(k) for k in ("_id","username","email","display_name","status","must_change_password","last_login_at")} if user else None
        department=self.academics["departments"].repository.find_by_id(profile["department_id"])
        if department and str(department.get("institution_id"))!=str(iid): department=None
        return serialize_document({**profile,"department":department,"account":account,"assignments":self.assignments.list_for_faculty(fid,iid)})
    def update(self,fid,model,iid,actor):
        current=self.faculty.find_by_id(fid,iid)
        if not current: raise missing()
        changes=model.model_dump(exclude_unset=True)
        if changes.get("department_id"):
            self.academic("departments",changes["department_id"],iid)
            if str(changes["department_id"])!=str(current.get("department_id")) and self.assignments.list_for_faculty(fid,iid,"active"):
                raise AppError("ACTIVE_ASSIGNMENTS_CONFLICT","Deactivate or reassign active teaching assignments before changing Department.",409)
            changes["department_id"]=parse_object_id(changes["department_id"],"department_id")
        if changes.get("email") and changes["email"]!=current.get("email") and self.users.find_by_email(iid,changes["email"]): raise AppError("USER_EMAIL_ALREADY_EXISTS","Faculty email already exists.",409)
        if "joining_date" in changes: changes["joining_date"]=dt(changes["joining_date"])
        changes["updated_by"]=parse_object_id(actor,"actor_id"); self.faculty.update(fid,iid,changes)
        sync={k:changes[k] for k in ("display_name","email") if k in changes}
        if sync: self.users.update(current["user_id"],sync)
        return self.get(fid,iid)
    def set_status(self,fid,model,iid,actor):
        profile=self.faculty.find_by_id(fid,iid)
        if not profile: raise missing()
        self.faculty.update(fid,iid,{"status":model.status,"updated_by":parse_object_id(actor,"actor_id")})
        account_status="active" if model.status=="active" else "suspended" if model.status=="suspended" else "inactive"; user=self.users.find_by_id(profile["user_id"]); changes={"status":account_status}
        if user and account_status!="active": changes["token_version"]=int(user.get("token_version",0))+1
        self.users.update(profile["user_id"],changes)
        if model.status!="active": self.assignments.deactivate_for_faculty(fid,iid)
        return self.get(fid,iid)
    def create_assignment(self,fid,model,iid,actor):
        self.validate_assignment(fid,model,iid); now=datetime.now(timezone.utc)
        doc={"institution_id":parse_object_id(iid),"faculty_id":parse_object_id(fid),"academic_year_id":parse_object_id(model.academic_year_id),"subject_id":parse_object_id(model.subject_id),"class_division_id":parse_object_id(model.class_division_id),"assignment_type":model.assignment_type,"status":model.status,"start_date":dt(model.start_date),"end_date":dt(model.end_date),"created_at":now,"updated_at":now,"created_by":parse_object_id(actor)}
        created=self.assignments.insert(doc);safe_log(logger,logging.INFO,"Faculty assignment created",faculty_id=str(fid),assignment_id=str(created.get("_id")));return serialize_document(created)
    def update_assignment(self,fid,aid,model,iid,actor):
        current=self.assignments.find_by_id(aid,fid,iid)
        if not current: raise AppError("FACULTY_ASSIGNMENT_NOT_FOUND","Teaching assignment was not found.",404)
        changes=model.model_dump(exclude_unset=True); merged=SimpleNamespace(**{**current,**changes})
        self.validate_assignment(fid,merged,iid,exclude=aid)
        if merged.start_date and merged.end_date and merged.end_date < merged.start_date: raise AppError("INVALID_ASSIGNMENT_DATES","Assignment end date cannot precede start date.",422)
        for key in ("academic_year_id","subject_id","class_division_id"):
            if key in changes: changes[key]=parse_object_id(changes[key],key)
        for key in ("start_date","end_date"):
            if key in changes: changes[key]=dt(changes[key])
        if changes.get("status")=="inactive" and "end_date" not in changes: changes["end_date"]=datetime.now(timezone.utc)
        changes["updated_by"]=parse_object_id(actor); return serialize_document(self.assignments.update(aid,fid,iid,changes))
    def deactivate_assignment(self,fid,aid,iid,actor):
        if not self.assignments.find_by_id(aid,fid,iid): raise AppError("FACULTY_ASSIGNMENT_NOT_FOUND","Teaching assignment was not found.",404)
        return serialize_document(self.assignments.update(aid,fid,iid,{"status":"inactive","end_date":datetime.now(timezone.utc),"updated_by":parse_object_id(actor)}))
    def self_profile(self,user):
        profile=self.faculty.find_by_user(user["_id"],user["institution_id"])
        if not profile: raise missing()
        return self.get(str(profile["_id"]),str(user["institution_id"]))
    def own_assignments(self,user):
        profile=self.faculty.find_by_user(user["_id"],user["institution_id"])
        if not profile: raise missing()
        return [serialize_document(x) for x in self.assignments.list_for_faculty(profile["_id"],user["institution_id"],"active")]
