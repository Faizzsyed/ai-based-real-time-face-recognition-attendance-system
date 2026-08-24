"""MongoDB persistence for Faculty and teaching assignments."""
from datetime import datetime,timezone
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from app.core.errors import AppError
from app.db.mongo import mongo
from app.db.object_id import parse_object_id

def duplicate(exc):
    text=str(exc)
    if "employee" in text: return AppError("DUPLICATE_EMPLOYEE_ID","Employee ID already exists.",409)
    return AppError("DUPLICATE_FACULTY_ASSIGNMENT","An equivalent active teaching assignment already exists.",409)

class FacultyRepository:
    def __init__(self,database=None): self._database=database
    @property
    def collection(self): return (self._database or mongo.require_database()).faculty
    def insert(self,d):
        try: result=self.collection.insert_one(d)
        except DuplicateKeyError as exc: raise duplicate(exc) from exc
        return {**d,"_id":result.inserted_id}
    def find_by_id(self,fid,iid): return self.collection.find_one({"_id":parse_object_id(fid),"institution_id":parse_object_id(iid)})
    def find_by_user(self,uid,iid): return self.collection.find_one({"user_id":parse_object_id(uid),"institution_id":parse_object_id(iid)})
    def find_by_employee(self,iid,eid): return self.collection.find_one({"institution_id":parse_object_id(iid),"employee_id":eid})
    def update(self,fid,iid,changes):
        query={"_id":parse_object_id(fid),"institution_id":parse_object_id(iid)}
        try: self.collection.update_one(query,{"$set":{**changes,"updated_at":datetime.now(timezone.utc)}})
        except DuplicateKeyError as exc: raise duplicate(exc) from exc
        return self.collection.find_one(query)
    def delete_created(self,fid): self.collection.delete_one({"_id":parse_object_id(fid)})
    def list(self,iid,filters,search,page,size):
        import re
        match={"institution_id":parse_object_id(iid)}
        if filters.get("status"): match["status"]=filters["status"]
        if filters.get("department_id"): match["department_id"]=parse_object_id(filters["department_id"],"department_id")
        pipeline=[{"$match":match},{"$lookup":{"from":"users","localField":"user_id","foreignField":"_id","as":"accounts"}},{"$set":{"account":{"$first":"$accounts"}}}]
        post=[]
        if filters.get("account_status"): post.append({"account.status":filters["account_status"]})
        if search:
            escaped=re.escape(search[:100]); post.append({"$or":[{x:{"$regex":escaped,"$options":"i"}} for x in ("display_name","employee_id","email")]})
        if post: pipeline.append({"$match":{"$and":post}})
        pipeline.append({"$facet":{"items":[{"$sort":{"created_at":-1}},{"$skip":(page-1)*size},{"$limit":size}],"count":[{"$count":"total"}]}})
        result=next(iter(self.collection.aggregate(pipeline)),{"items":[],"count":[]})
        return result["items"],result["count"][0]["total"] if result["count"] else 0

class AssignmentRepository:
    def __init__(self,database=None): self._database=database
    @property
    def collection(self): return (self._database or mongo.require_database()).faculty_assignments
    def insert(self,d):
        try: result=self.collection.insert_one(d)
        except DuplicateKeyError as exc: raise duplicate(exc) from exc
        return {**d,"_id":result.inserted_id}
    def find_by_id(self,aid,fid,iid): return self.collection.find_one({"_id":parse_object_id(aid),"faculty_id":parse_object_id(fid),"institution_id":parse_object_id(iid)})
    def find_scoped(self,aid,iid): return self.collection.find_one({"_id":parse_object_id(aid),"institution_id":parse_object_id(iid)})
    def duplicate_active(self,iid,fid,year,subject,class_id,kind,exclude=None):
        query={"institution_id":parse_object_id(iid),"faculty_id":parse_object_id(fid),"academic_year_id":parse_object_id(year),"subject_id":parse_object_id(subject),"class_division_id":parse_object_id(class_id),"assignment_type":kind,"status":"active"}
        if exclude: query["_id"]={"$ne":parse_object_id(exclude)}
        return self.collection.find_one(query) is not None
    def list_for_faculty(self,fid,iid,status=None):
        query={"faculty_id":parse_object_id(fid),"institution_id":parse_object_id(iid)}
        if status: query["status"]=status
        pipeline=[{"$match":query},
            {"$lookup":{"from":"academic_years","let":{"rid":"$academic_year_id","tenant":"$institution_id"},"pipeline":[{"$match":{"$expr":{"$and":[{"$eq":["$_id","$$rid"]},{"$eq":["$institution_id","$$tenant"]}]}}}],"as":"academic_years"}},
            {"$lookup":{"from":"subjects","let":{"rid":"$subject_id","tenant":"$institution_id"},"pipeline":[{"$match":{"$expr":{"$and":[{"$eq":["$_id","$$rid"]},{"$eq":["$institution_id","$$tenant"]}]}}}],"as":"subjects"}},
            {"$lookup":{"from":"class_divisions","let":{"rid":"$class_division_id","tenant":"$institution_id"},"pipeline":[{"$match":{"$expr":{"$and":[{"$eq":["$_id","$$rid"]},{"$eq":["$institution_id","$$tenant"]}]}}}],"as":"class_divisions"}},
            {"$set":{"academic_year":{"$first":"$academic_years"},"subject":{"$first":"$subjects"},"class_division":{"$first":"$class_divisions"}}},
            {"$unset":["academic_years","subjects","class_divisions"]},{"$sort":{"created_at":-1}}]
        return list(self.collection.aggregate(pipeline))
    def update(self,aid,fid,iid,changes):
        query={"_id":parse_object_id(aid),"faculty_id":parse_object_id(fid),"institution_id":parse_object_id(iid)}
        self.collection.update_one(query,{"$set":{**changes,"updated_at":datetime.now(timezone.utc)}}); return self.collection.find_one(query)
    def delete_created(self,aid): self.collection.delete_one({"_id":parse_object_id(aid)})
    def deactivate_for_faculty(self,fid,iid):
        now=datetime.now(timezone.utc)
        self.collection.update_many({"faculty_id":parse_object_id(fid),"institution_id":parse_object_id(iid),"status":"active"},{"$set":{"status":"inactive","end_date":now,"updated_at":now}})
