"""MongoDB repository for recurring timetable entries."""
from datetime import datetime,timezone
from app.db.mongo import mongo
from app.db.object_id import parse_object_id

class TimetableRepository:
    def __init__(self,database=None): self._database=database
    @property
    def collection(self): return (self._database or mongo.require_database()).timetable_entries
    def insert(self,document):
        result=self.collection.insert_one(document); return {**document,"_id":result.inserted_id}
    def find_by_id(self,entry_id,institution_id): return self.collection.find_one({"_id":parse_object_id(entry_id),"institution_id":parse_object_id(institution_id)})
    def update(self,entry_id,institution_id,changes):
        query={"_id":parse_object_id(entry_id),"institution_id":parse_object_id(institution_id)};self.collection.update_one(query,{"$set":{**changes,"updated_at":datetime.now(timezone.utc)}});return self.collection.find_one(query)
    def conflicts(self,institution_id,candidate,exclude_id=None):
        query={"institution_id":parse_object_id(institution_id),"status":"active","day_of_week":candidate["day_of_week"],"start_time":{"$lt":candidate["end_time"]},"end_time":{"$gt":candidate["start_time"]},"effective_from":{"$lte":candidate.get("effective_until") or datetime.max.replace(tzinfo=timezone.utc)},"$or":[{"effective_until":None},{"effective_until":{"$gte":candidate["effective_from"]}}]}
        if exclude_id: query["_id"]={"$ne":parse_object_id(exclude_id)}
        return list(self.collection.find(query).limit(50))
    @staticmethod
    def _lookup(from_collection,local_field,alias):
        return {"$lookup":{"from":from_collection,"let":{"rid":f"${local_field}","tenant":"$institution_id"},"pipeline":[{"$match":{"$expr":{"$and":[{"$eq":["$_id","$$rid"]},{"$eq":["$institution_id","$$tenant"]}]}}}],"as":alias}}
    def list(self,institution_id,filters,page,page_size):
        match={"institution_id":parse_object_id(institution_id)}
        direct={"academic_year_id":"academic_year_id","faculty_id":"faculty_id","class_division_id":"class_division_id","subject_id":"subject_id"}
        for key,target in direct.items():
            if filters.get(key): match[target]=parse_object_id(filters[key],key)
        if filters.get("day_of_week"): match["day_of_week"]=filters["day_of_week"]
        if filters.get("status"): match["status"]=filters["status"]
        pipeline=[{"$match":match},self._lookup("subjects","subject_id","subjects"),self._lookup("class_divisions","class_division_id","classes"),self._lookup("faculty","faculty_id","faculty_records"),self._lookup("academic_years","academic_year_id","years"),{"$set":{"subject":{"$first":"$subjects"},"class_division":{"$first":"$classes"},"faculty":{"$first":"$faculty_records"},"academic_year":{"$first":"$years"}}},{"$unset":["subjects","classes","faculty_records","years"]}]
        hierarchy={"department_id":"class_division.department_id","program_id":"class_division.program_id","semester_id":"class_division.semester_id"};post={}
        for key,target in hierarchy.items():
            if filters.get(key): post[target]=parse_object_id(filters[key],key)
        if post:pipeline.append({"$match":post})
        pipeline.append({"$facet":{"items":[{"$sort":{"day_index":1,"start_time":1}},{"$skip":(page-1)*page_size},{"$limit":page_size}],"count":[{"$count":"total"}]}})
        result=next(iter(self.collection.aggregate(pipeline)),{"items":[],"count":[]});return result["items"],result["count"][0]["total"] if result["count"] else 0
    def active_for_faculty(self,institution_id,faculty_id): return self.list(institution_id,{"faculty_id":faculty_id,"status":"active"},1,100)[0]
    def active_for_class(self,institution_id,class_id): return self.list(institution_id,{"class_division_id":class_id,"status":"active"},1,100)[0]
