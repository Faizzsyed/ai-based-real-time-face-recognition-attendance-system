"""Private in-app notification persistence."""
from datetime import datetime,timezone
from app.db.mongo import mongo
from app.db.object_id import parse_object_id,serialize_document
from app.core.errors import AppError

class NotificationService:
    def __init__(self,database=None): self._database=database
    @property
    def collection(self): return (self._database or mongo.require_database()).notifications
    def create(self,institution_id,recipient_user_id,type,title,message,entity_type,entity_id):
        now=datetime.now(timezone.utc);document={"institution_id":parse_object_id(institution_id),"recipient_user_id":parse_object_id(recipient_user_id),"type":type,"title":title[:160],"message":message[:1000],"entity_type":entity_type,"entity_id":parse_object_id(entity_id,"entity_id"),"read_at":None,"created_at":now}
        result=self.collection.insert_one(document);return {**document,"_id":result.inserted_id}
    def list(self,user,page,size):
        query={"institution_id":parse_object_id(user["institution_id"]),"recipient_user_id":parse_object_id(user["_id"])};total=self.collection.count_documents(query);items=list(self.collection.find(query).sort("created_at",-1).skip((page-1)*size).limit(size))
        return {"items":[serialize_document(x) for x in items],"pagination":{"page":page,"pageSize":size,"total":total,"pages":(total+size-1)//size}}
    def unread_count(self,user): return {"count":self.collection.count_documents({"institution_id":parse_object_id(user["institution_id"]),"recipient_user_id":parse_object_id(user["_id"]),"read_at":None})}
    def read(self,notification_id,user):
        query={"_id":parse_object_id(notification_id,"notification_id"),"institution_id":parse_object_id(user["institution_id"]),"recipient_user_id":parse_object_id(user["_id"])}
        result=self.collection.update_one({**query,"read_at":None},{"$set":{"read_at":datetime.now(timezone.utc)}})
        item=self.collection.find_one(query)
        if not item: raise AppError("NOTIFICATION_NOT_FOUND","Notification was not found.",404)
        return serialize_document(item)
    def read_all(self,user):
        query={"institution_id":parse_object_id(user["institution_id"]),"recipient_user_id":parse_object_id(user["_id"]),"read_at":None};return {"updated":self.collection.update_many(query,{"$set":{"read_at":datetime.now(timezone.utc)}}).modified_count}
