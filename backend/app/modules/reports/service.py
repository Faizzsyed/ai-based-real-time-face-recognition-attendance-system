"""Attendance calculations, role scoping, drill-downs, and safe exports."""
from collections import Counter,defaultdict
from datetime import datetime,timezone
import csv,io,re
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.object_id import serialize_document
from app.modules.reports.repository import ReportRepository
from app.modules.reports.schemas import ELIGIBLE_STATUSES,PRESENT_EQUIVALENT

def attendance_counts(records):
    raw=Counter(x.get("status") for x in records);present=sum(raw[x] for x in PRESENT_EQUIVALENT);eligible=sum(raw[x] for x in ELIGIBLE_STATUSES)
    return {"present":present,"absent":raw["absent"],"late":raw["late"],"excused":raw["excused"],"eligible":eligible,"percentage":round(present*100/eligible,2) if eligible else None}

class ReportService:
    def __init__(self,repository=None,threshold=None):self.repository=repository or ReportRepository();self.threshold=float(get_settings().attendance_low_threshold_percent if threshold is None else threshold)
    @staticmethod
    def _sid(value):return str(value) if value is not None else ""
    def _faculty(self,user):
        row=self.repository.faculty_for_user(user["institution_id"],user["_id"])
        if not row:raise AppError("FACULTY_NOT_FOUND","An active Faculty profile is required.",404)
        return row
    def _student(self,user):
        row=self.repository.student_for_user(user["institution_id"],user["_id"])
        if not row:raise AppError("STUDENT_NOT_FOUND","Student was not found.",404)
        return row
    def _data(self,user,filters=None,faculty=False,student_id=None):
        fid=self._faculty(user)["_id"] if faculty else None;data=self.repository.dataset(user["institution_id"],filters or {},fid,student_id)
        requested=filters or {};allowed=[]
        for session in data["sessions"]:
            cls=data["classes"].get(self._sid(session.get("class_division_id")),{});program=data["programs"].get(self._sid(cls.get("program_id")),{})
            if requested.get("program_id") and self._sid(cls.get("program_id"))!=requested["program_id"]:continue
            if requested.get("semester_id") and self._sid(cls.get("semester_id"))!=requested["semester_id"]:continue
            if requested.get("department_id") and self._sid(program.get("department_id"))!=requested["department_id"]:continue
            allowed.append(session)
        ids={x["_id"] for x in allowed};data["sessions"]=allowed;data["records"]=[x for x in data["records"] if x.get("session_id") in ids];return data
    @staticmethod
    def _records_by_session(data):
        grouped=defaultdict(list)
        for row in data["records"]:grouped[str(row["session_id"])].append(row)
        return grouped
    def _student_rows(self,data):
        rows=[]
        for sid,records in self._group(data["records"],"student_id").items():
            stats=attendance_counts(records);student=data["students"].get(sid,{})
            if stats["eligible"]:rows.append({"studentId":sid,"student":student.get("display_name") or records[0].get("student_name","Student"),"studentNumber":student.get("admission_number") or records[0].get("admission_number"),**stats})
        return rows
    @staticmethod
    def _group(items,key):
        result=defaultdict(list)
        for item in items:result[str(item.get(key))].append(item)
        return result
    def overview(self,user,filters=None,faculty=False):
        data=self._data(user,filters,faculty);stats=attendance_counts(data["records"]);students=self._student_rows(data);sources=Counter(x.get("source") or "other" for x in data["records"] if x.get("status") in ELIGIBLE_STATUSES)
        total=sum(sources.values());dist=[{"source":"face_assisted" if k=="face_recognition" else k,"count":v,"percentage":round(v*100/total,2) if total else None} for k,v in sorted(sources.items())]
        recent=[]
        for session in sorted(data["sessions"],key=lambda x:x.get("lecture_date"),reverse=True)[:8]:
            recent.append({"sessionId":self._sid(session["_id"]),"date":serialize_document(session).get("lecture_date"),"subject":data["subjects"].get(self._sid(session.get("subject_id")),{}).get("name","Subject"),"class":data["classes"].get(self._sid(session.get("class_division_id")),{}).get("name") or data["classes"].get(self._sid(session.get("class_division_id")),{}).get("division","Class")})
        result={"attendance":stats,"finalizedSessions":len(data["sessions"]),"classesConducted":len(data["sessions"]),"studentsBelowThreshold":sum(1 for x in students if x["percentage"] is not None and x["percentage"]<self.threshold),"threshold":self.threshold,"sourceDistribution":dist,"recentSessions":recent}
        if not faculty:result["draftSessions"]=self.repository.draft_count(user["institution_id"])
        return result
    def options(self,user,faculty=False):
        data=self._data(user,{},faculty)
        def items(mapping,label):return [{"id":key,"label":value.get(label) or value.get("name") or value.get("division") or "—"} for key,value in sorted(mapping.items(),key=lambda x:str(x[1].get(label) or x[1].get("name") or ""))]
        classes=[]
        for key,value in data["classes"].items():classes.append({"id":key,"label":value.get("name") or f"Division {value.get('division','—')}","programId":self._sid(value.get("program_id")),"semesterId":self._sid(value.get("semester_id"))})
        programs=[{"id":k,"label":v.get("name","Program"),"departmentId":self._sid(v.get("department_id"))} for k,v in data["programs"].items()]
        return {"academicYears":items(data.get("years",{}),"name"),"departments":items(data["departments"],"name"),"programs":programs,"semesters":items(data["semesters"],"name"),"classes":classes,"subjects":items(data["subjects"],"name")}
    def trend(self,user,filters=None,faculty=False,student_id=None):
        data=self._data(user,filters,faculty,student_id);by_session=self._records_by_session(data);daily=defaultdict(list)
        for session in data["sessions"]:daily[session["lecture_date"].date().isoformat()].extend(by_session[str(session["_id"])])
        return {"items":[{"date":day,**attendance_counts(rows)} for day,rows in sorted(daily.items())],"message":None if len(daily)>=2 else "Not enough attendance data yet."}
    def departments(self,user,filters=None):
        data=self._data(user,filters);by_session=self._records_by_session(data);buckets=defaultdict(lambda:{"sessions":[],"records":[]})
        for session in data["sessions"]:
            cls=data["classes"].get(self._sid(session.get("class_division_id")),{});program=data["programs"].get(self._sid(cls.get("program_id")),{});did=self._sid(program.get("department_id"));buckets[did]["sessions"].append(session);buckets[did]["records"].extend(by_session[str(session["_id"])])
        items=[]
        for did,bucket in buckets.items():
            student_rows=self._student_rows({**data,"records":bucket["records"]});items.append({"departmentId":did,"department":data["departments"].get(did,{}).get("name","Unknown"),"totalStudents":len(student_rows),"finalizedSessions":len(bucket["sessions"]),"studentsBelowThreshold":sum(1 for x in student_rows if x["percentage"] is not None and x["percentage"]<self.threshold),**attendance_counts(bucket["records"])})
        return {"items":sorted(items,key=lambda x:(-(x["percentage"] or -1),x["department"]))}
    def subjects(self,user,filters=None,faculty=False):
        data=self._data(user,filters,faculty);by_session=self._records_by_session(data);buckets=defaultdict(lambda:{"sessions":[],"records":[],"faculty":set()})
        for session in data["sessions"]:
            key=(self._sid(session.get("subject_id")),self._sid(session.get("class_division_id")));bucket=buckets[key];bucket["sessions"].append(session);bucket["records"].extend(by_session[str(session["_id"])]);bucket["faculty"].add(self._sid(session.get("faculty_id")))
        items=[]
        for (sid,cid),bucket in buckets.items():
            stats=attendance_counts(bucket["records"]);low=sum(1 for x in self._student_rows({**data,"records":bucket["records"]}) if x["percentage"] is not None and x["percentage"]<self.threshold);names=[data["faculty"].get(x,{}).get("display_name","Faculty") for x in bucket["faculty"]]
            items.append({"subjectId":sid,"classDivisionId":cid,"subject":data["subjects"].get(sid,{}).get("name","Subject"),"faculty":", ".join(sorted(names)),"classesConducted":len(bucket["sessions"]),"studentsBelowThreshold":low,**stats})
        return {"items":items}
    def class_report(self,user,class_id,filters=None,faculty=False):
        filters={**(filters or {}),"class_division_id":class_id};data=self._data(user,filters,faculty)
        if faculty and not data["sessions"]:raise AppError("FORBIDDEN_REPORT_SCOPE","Faculty may view only assigned class reports.",403)
        rows=self._student_rows(data);page=int((filters or {}).get("page",1));size=int((filters or {}).get("page_size",25));return {"classDivisionId":class_id,"attendance":attendance_counts(data["records"]),"finalizedSessions":len(data["sessions"]),"totalStudents":len(rows),"subjects":self.subjects(user,filters,faculty)["items"],"students":rows[(page-1)*size:page*size],"pagination":{"page":page,"pageSize":size,"total":len(rows),"pages":max(1,(len(rows)+size-1)//size)}}
    def low_attendance(self,user,filters=None,faculty=False):
        data=self._data(user,filters,faculty);rows=[];session_map={str(x["_id"]):x for x in data["sessions"]}
        for student in self._student_rows(data):
            if student["percentage"] is None or student["percentage"]>=self.threshold:continue
            records=[x for x in data["records"] if self._sid(x.get("student_id"))==student["studentId"]]
            subject_groups=defaultdict(list)
            for record in records:
                session=session_map.get(self._sid(record.get("session_id")));subject_groups[self._sid(session.get("subject_id")) if session else ""].append(record)
            subjects=[data["subjects"].get(sid,{}).get("name","Subject") for sid,group in subject_groups.items() if attendance_counts(group)["percentage"] is not None and attendance_counts(group)["percentage"]<self.threshold]
            student_sessions=[session_map.get(self._sid(x.get("session_id")),{}) for x in records];class_id=self._sid(next((x.get("class_division_id") for x in student_sessions if x),None));cls=data["classes"].get(class_id,{})
            rows.append({**student,"classDivisionId":class_id,"class":cls.get("name") or cls.get("division") or "—","subjectsBelowThreshold":subjects})
        query=str((filters or {}).get("search","")).casefold().strip();rows=sorted(rows,key=lambda x:x["percentage"])
        if query:rows=[x for x in rows if query in f"{x.get('student','')} {x.get('studentNumber','')} {x.get('class','')}".casefold()]
        page=max(1,int((filters or {}).get("page",1)));size=max(1,min(100,int((filters or {}).get("page_size",25))));return {"threshold":self.threshold,"items":rows[(page-1)*size:page*size],"pagination":{"page":page,"pageSize":size,"total":len(rows),"pages":max(1,(len(rows)+size-1)//size)}}
    def student_report(self,user,student_id=None,faculty=False):
        if user.get("role")=="student":student=self._student(user);student_id=self._sid(student["_id"])
        elif not student_id:raise AppError("STUDENT_REQUIRED","A Student is required.",422)
        data=self._data(user,{},faculty,student_id);authorized_ids={self._sid(x.get("student_id")) for x in data["records"]}
        if faculty and student_id not in authorized_ids:raise AppError("FORBIDDEN_REPORT_SCOPE","Faculty may view only Students in assigned submitted sessions.",403)
        session_map={str(x["_id"]):x for x in data["sessions"]};subject_groups=defaultdict(list)
        for record in data["records"]:
            session=session_map.get(self._sid(record.get("session_id")));subject_groups[self._sid(session.get("subject_id")) if session else ""].append(record)
        subjects=[]
        for sid,records in subject_groups.items():
            stats=attendance_counts(records);subjects.append({"subjectId":sid,"subject":data["subjects"].get(sid,{}).get("name","Subject"),"classesHeld":stats["eligible"],"status":"No data" if stats["percentage"] is None else "Good" if stats["percentage"]>=self.threshold+10 else "Needs Attention" if stats["percentage"]>=self.threshold else "Below Required Attendance",**stats})
        history=[]
        for record in sorted(data["records"],key=lambda x:session_map.get(self._sid(x.get("session_id")),{}).get("lecture_date",datetime.min.replace(tzinfo=timezone.utc)),reverse=True)[:20]:
            session=session_map.get(self._sid(record.get("session_id")),{});history.append({"sessionId":self._sid(record.get("session_id")),"date":serialize_document(session).get("lecture_date"),"subject":data["subjects"].get(self._sid(session.get("subject_id")),{}).get("name","Subject"),"status":record.get("status"),"source":"face_assisted" if record.get("source")=="face_recognition" else record.get("source")})
        profile=data["students"].get(student_id,{})
        return {"studentId":student_id,"student":profile.get("display_name") or (data["records"][0].get("student_name") if data["records"] else "Student"),"studentNumber":profile.get("admission_number") or (data["records"][0].get("admission_number") if data["records"] else None),"attendance":attendance_counts(data["records"]),"threshold":self.threshold,"subjects":subjects,"recentHistory":history,"trend":self.trend(user,{},faculty,student_id)}
    def session_report(self,user,session_id,faculty=False):
        data=self._data(user,{},faculty);session=next((x for x in data["sessions"] if self._sid(x["_id"])==session_id),None)
        if not session:raise AppError("ATTENDANCE_SESSION_NOT_FOUND","A finalized attendance session was not found in your authorized scope.",404)
        records=[x for x in data["records"] if self._sid(x.get("session_id"))==session_id];stats=attendance_counts(records);sid=self._sid(session.get("subject_id"));cid=self._sid(session.get("class_division_id"));fid=self._sid(session.get("faculty_id"))
        rows=[{"student":x.get("student_name","Student"),"studentNumber":x.get("admission_number") or x.get("roll_number"),"status":x.get("status"),"source":"face_assisted" if x.get("source")=="face_recognition" else x.get("source"),"reviewState":x.get("review_state")} for x in records]
        return {"sessionId":session_id,"date":serialize_document(session).get("lecture_date"),"subject":data["subjects"].get(sid,{}).get("name","Subject"),"class":data["classes"].get(cid,{}).get("name") or data["classes"].get(cid,{}).get("division","Class"),"faculty":data["faculty"].get(fid,{}).get("display_name","Faculty"),"scheduledStart":session.get("scheduled_start"),"scheduledEnd":session.get("scheduled_end"),"totalRoster":len(records),"attendance":stats,"students":rows}
    @staticmethod
    def csv_export(report,title):
        output=io.StringIO(newline="");rows=report.get("items") or report.get("students") or []
        safe=[{k:v for k,v in row.items() if k not in {"studentId","subjectId","classDivisionId"} and not isinstance(v,(list,dict))} for row in rows];headers=list(dict.fromkeys(k for row in safe for k in row))
        writer=csv.DictWriter(output,fieldnames=headers);writer.writeheader();writer.writerows(safe);filename="AttendAI_"+re.sub(r"[^A-Za-z0-9_-]+","_",title).strip("_")+"_"+datetime.now(timezone.utc).date().isoformat()+".csv";return filename,output.getvalue()
