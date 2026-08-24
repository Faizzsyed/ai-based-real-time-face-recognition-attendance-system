"""Bulk, institution-scoped MongoDB reads for reporting."""
from datetime import datetime,time,timezone
from app.db.mongo import mongo
from app.db.object_id import parse_object_id
from app.modules.reports.schemas import FINAL_SESSION_STATES

class ReportRepository:
    def __init__(self,database=None):self.database=database
    @property
    def db(self):return self.database or mongo.require_database()
    def institution(self,iid):return self.db.institutions.find_one({"_id":parse_object_id(iid)}) or {}
    def faculty_for_user(self,iid,uid):return self.db.faculty.find_one({"institution_id":parse_object_id(iid),"user_id":parse_object_id(uid),"status":"active"})
    def student_for_user(self,iid,uid):return self.db.students.find_one({"institution_id":parse_object_id(iid),"user_id":parse_object_id(uid)})
    def _oid(self,value):return parse_object_id(value) if value else None
    def dataset(self,iid,filters=None,faculty_id=None,student_id=None):
        filters=filters or {};match={"institution_id":parse_object_id(iid),"status":{"$in":list(FINAL_SESSION_STATES)}}
        mapping={"academic_year_id":"academic_year_id","class_division_id":"class_division_id","subject_id":"subject_id","faculty_id":"faculty_id"}
        for source,target in mapping.items():
            if filters.get(source):match[target]=self._oid(filters[source])
        if faculty_id:match["faculty_id"]=self._oid(faculty_id)
        if filters.get("date_from") or filters.get("date_to"):
            dates={}
            if filters.get("date_from"):dates["$gte"]=datetime.combine(filters["date_from"],time.min,tzinfo=timezone.utc)
            if filters.get("date_to"):dates["$lte"]=datetime.combine(filters["date_to"],time.max,tzinfo=timezone.utc)
            match["lecture_date"]=dates
        sessions=list(self.db.attendance_sessions.find(match).sort("lecture_date",1));ids=[x["_id"] for x in sessions]
        record_match={"institution_id":parse_object_id(iid),"session_id":{"$in":ids}}
        if student_id:record_match["student_id"]=self._oid(student_id)
        records=list(self.db.attendance_records.find(record_match)) if ids else []
        def keyed(collection,ids):
            unique=list({x for x in ids if x is not None});return {str(x["_id"]):x for x in self.db[collection].find({"institution_id":parse_object_id(iid),"_id":{"$in":unique}})} if unique else {}
        classes=keyed("class_divisions",[x.get("class_division_id") for x in sessions]);subjects=keyed("subjects",[x.get("subject_id") for x in sessions]);faculty=keyed("faculty",[x.get("faculty_id") for x in sessions]);students=keyed("students",[x.get("student_id") for x in records]);years=keyed("academic_years",[x.get("academic_year_id") for x in sessions])
        programs=keyed("programs",[x.get("program_id") for x in classes.values()]);departments=keyed("departments",[x.get("department_id") for x in programs.values()]);semesters=keyed("semesters",[x.get("semester_id") for x in classes.values()])
        return {"sessions":sessions,"records":records,"classes":classes,"subjects":subjects,"faculty":faculty,"students":students,"programs":programs,"departments":departments,"semesters":semesters,"years":years}
    def draft_count(self,iid):return self.db.attendance_sessions.count_documents({"institution_id":parse_object_id(iid),"status":{"$in":["draft","reopened"]}})
