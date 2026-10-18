"""Tenant-scoped face enrollment persistence."""
from datetime import datetime,timezone
from app.db.mongo import mongo
from app.db.object_id import parse_object_id
from pymongo.errors import DuplicateKeyError
from app.core.errors import AppError
class FaceEnrollmentRepository:
    def __init__(self,database=None):self._database=database
    @property
    def collection(self):return (self._database or mongo.require_database()).face_enrollments
    def find(self,student_id,institution_id):return self.collection.find_one({"student_id":parse_object_id(student_id),"institution_id":parse_object_id(institution_id),"status":"active"})
    def active_for_students(self,student_ids,institution_id):
        ids=[parse_object_id(x) for x in student_ids]
        if not ids:return []
        return list(self.collection.find({"institution_id":parse_object_id(institution_id),"student_id":{"$in":ids},"status":"active"}))
    def upsert(self,student_id,institution_id,document):
        query={"student_id":parse_object_id(student_id),"institution_id":parse_object_id(institution_id)};self.collection.update_one(query,{"$set":{**document,"updated_at":datetime.now(timezone.utc)}},upsert=True);return self.collection.find_one(query)
    def create(self,document):
        stored={**document,"updated_at":datetime.now(timezone.utc)}
        try:result=self.collection.insert_one(stored)
        except DuplicateKeyError as exc:raise AppError("FACE_ALREADY_ENROLLED","Face already enrolled. Choose Re-enroll Face to replace it explicitly.",409) from exc
        return {**stored,"_id":result.inserted_id}
    def remove(self,student_id,institution_id):return self.collection.delete_one({"student_id":parse_object_id(student_id),"institution_id":parse_object_id(institution_id)}).deleted_count
