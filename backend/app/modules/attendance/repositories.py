"""MongoDB persistence for attendance sessions and immutable roster membership."""
from datetime import date,datetime,timezone
from pymongo.errors import DuplicateKeyError
from app.core.errors import AppError
from app.db.mongo import mongo
from app.db.object_id import parse_object_id

def _date_time(value):
    return datetime.combine(value,datetime.min.time(),tzinfo=timezone.utc) if isinstance(value,date) and not isinstance(value,datetime) else value

class AttendanceSessionRepository:
    def __init__(self,database=None):self._database=database
    @property
    def collection(self):return (self._database or mongo.require_database()).attendance_sessions
    def insert(self,document):
        try:result=self.collection.insert_one(document)
        except DuplicateKeyError as exc:raise AppError("ATTENDANCE_SESSION_EXISTS","Attendance was already started for this scheduled lecture.",409) from exc
        return {**document,"_id":result.inserted_id}
    def find_by_id(self,session_id,institution_id):return self.collection.find_one({"_id":parse_object_id(session_id),"institution_id":parse_object_id(institution_id)})
    def find_scheduled(self,institution_id,entry_id,lecture_date):return self.collection.find_one({"institution_id":parse_object_id(institution_id),"timetable_entry_id":parse_object_id(entry_id),"lecture_date":_date_time(lecture_date)})
    def update(self,session_id,institution_id,changes):
        query={"_id":parse_object_id(session_id),"institution_id":parse_object_id(institution_id)};self.collection.update_one(query,{"$set":{**changes,"updated_at":datetime.now(timezone.utc)}});return self.collection.find_one(query)
    def list(self,institution_id,filters,page=1,size=20):
        query={"institution_id":parse_object_id(institution_id)}
        for key in ("faculty_id","class_division_id","subject_id"):
            if filters.get(key):query[key]=parse_object_id(filters[key],key)
        if filters.get("status"):query["status"]=filters["status"]
        if filters.get("lecture_date"):query["lecture_date"]=_date_time(filters["lecture_date"])
        total=self.collection.count_documents(query);items=list(self.collection.find(query).sort([("lecture_date",-1),("scheduled_start",-1)]).skip((page-1)*size).limit(size));return items,total
    def for_faculty(self,institution_id,faculty_id,status=None,limit=50):
        query={"institution_id":parse_object_id(institution_id),"faculty_id":parse_object_id(faculty_id)}
        if status:query["status"]={"$in":status} if isinstance(status,(list,tuple,set)) else status
        return list(self.collection.find(query).sort([("lecture_date",-1),("scheduled_start",-1)]).limit(limit))

class AttendanceRecordRepository:
    def __init__(self,database=None):self._database=database
    @property
    def collection(self):return (self._database or mongo.require_database()).attendance_records
    def initialize_roster(self,records):
        if not records:return []
        for record in records:
            self.collection.update_one({"session_id":record["session_id"],"student_id":record["student_id"]},{"$setOnInsert":record},upsert=True)
        return self.for_session(records[0]["session_id"],records[0]["institution_id"])
    def for_session(self,session_id,institution_id):return list(self.collection.find({"session_id":parse_object_id(session_id),"institution_id":parse_object_id(institution_id)}).sort("student_name",1))
    def save(self,session_id,institution_id,records,actor,source="manual"):
        now=datetime.now(timezone.utc)
        for item in records:
            result=self.collection.update_one({"session_id":parse_object_id(session_id),"institution_id":parse_object_id(institution_id),"student_id":parse_object_id(item["student_id"])},{"$set":{"status":item["status"],"remark":item.get("remark"),"source":source,"review_state":None if source=="manual" else "ai_suggested","marked_at":now,"marked_by":parse_object_id(actor,"actor_id"),"updated_at":now}})
            if result.matched_count!=1:raise AppError("STUDENT_NOT_IN_SESSION_ROSTER","A Student is not part of this attendance roster.",422)
        return self.for_session(session_id,institution_id)
    def for_student(self,institution_id,student_id,session_ids=None):
        query={"institution_id":parse_object_id(institution_id),"student_id":parse_object_id(student_id)}
        if session_ids is not None:query["session_id"]={"$in":[parse_object_id(x) for x in session_ids]}
        return list(self.collection.find(query).sort("marked_at",-1))

class AttendanceRosterRepository:
    def __init__(self,database=None):self._database=database
    @property
    def database(self):return self._database or mongo.require_database()
    def active_for_class(self,institution_id,academic_year_id,class_id,lecture_date):
        instant=_date_time(lecture_date)
        pipeline=[{"$match":{"institution_id":parse_object_id(institution_id),"academic_year_id":parse_object_id(academic_year_id),"class_division_id":parse_object_id(class_id),"enrollment_status":"active","start_date":{"$lte":instant},"$or":[{"end_date":None},{"end_date":{"$gte":instant}}]}},{"$lookup":{"from":"students","let":{"sid":"$student_id","tenant":"$institution_id"},"pipeline":[{"$match":{"$expr":{"$and":[{"$eq":["$_id","$$sid"]},{"$eq":["$institution_id","$$tenant"]},{"$eq":["$status","active"]}]}}}],"as":"students"}},{"$set":{"student":{"$first":"$students"}}},{"$match":{"student":{"$ne":None}}},{"$sort":{"roll_number":1}}]
        return list(self.database.student_academic_enrollments.aggregate(pipeline))
