"""Append-only, tenant-scoped audit recording with safe metadata."""
from datetime import datetime, timezone
from app.db.mongo import mongo
from app.db.object_id import parse_object_id, serialize_document

_SENSITIVE={"password","password_hash","token","access_token","refresh_token","authorization","embedding","face_embedding","image","image_bytes","encryption_key","secret","environment"}

def _safe(value, key=""):
    if any(word in key.casefold() for word in _SENSITIVE): return "[redacted]"
    if isinstance(value,dict): return {str(k):_safe(v,str(k)) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [_safe(v,key) for v in value]
    if isinstance(value,bytes): return "[redacted binary]"
    return value

class AuditService:
    def __init__(self,database=None): self._database=database
    @property
    def collection(self): return (self._database or mongo.require_database()).audit_events
    def record(self,actor,action,entity_type,entity_id,metadata=None):
        document={"institution_id":parse_object_id(actor["institution_id"]),"actor_user_id":parse_object_id(actor["_id"]),"actor_role":actor.get("role"),"action":action,"entity_type":entity_type,"entity_id":parse_object_id(entity_id,"entity_id"),"metadata":_safe(metadata or {}),"created_at":datetime.now(timezone.utc)}
        result=self.collection.insert_one(document)
        return {**document,"_id":result.inserted_id}
    def list(self,institution_id,filters,page,size):
        query={"institution_id":parse_object_id(institution_id)}
        for key in ("action","actor_role","entity_type"):
            if filters.get(key): query[key]=filters[key]
        if filters.get("actor"): query["actor_user_id"]=parse_object_id(filters["actor"],"actor")
        if filters.get("date_from") or filters.get("date_to"):
            dates={}
            if filters.get("date_from"): dates["$gte"]=filters["date_from"]
            if filters.get("date_to"): dates["$lte"]=filters["date_to"]
            query["created_at"]=dates
        if filters.get("search"):
            import re
            query["$or"]=[{"action":{"$regex":re.escape(filters["search"][:100]),"$options":"i"}},{"entity_type":{"$regex":re.escape(filters["search"][:100]),"$options":"i"}}]
        total=self.collection.count_documents(query);items=list(self.collection.find(query).sort("created_at",-1).skip((page-1)*size).limit(size))
        return {"items":[serialize_document(x) for x in items],"pagination":{"page":page,"pageSize":size,"total":total,"pages":(total+size-1)//size}}
    def get(self,event_id,institution_id):
        return self.collection.find_one({"_id":parse_object_id(event_id,"event_id"),"institution_id":parse_object_id(institution_id)})
