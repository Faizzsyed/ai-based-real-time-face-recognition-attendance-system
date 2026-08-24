"""Central safe runtime logging with context-local request correlation."""
from __future__ import annotations
import contextvars,json,logging,re
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

request_id_var=contextvars.ContextVar("request_id",default="-")
SENSITIVE=("password","password_hash","authorization","access_token","refreshtoken","refresh_token","jwt","jwt_secret","mongodb_uri","embedding","encrypted_embedding","encryption_key","face_image","image_bytes","file_bytes","ciphertext","nonce")
def _sensitive(key:str)->bool:
    normalized=key.casefold().replace("-","_");return any(term in normalized for term in SENSITIVE)
def sanitize(value:Any,key:str=""):
    if _sensitive(key):return "[REDACTED]"
    if isinstance(value,dict):return {str(k):sanitize(v,str(k)) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [sanitize(x,key) for x in value]
    if isinstance(value,bytes):return "[REDACTED BYTES]"
    text=str(value);text=re.sub(r"(?i)(mongodb(?:\+srv)?://)[^\s]+",r"\1[REDACTED]",text);return re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]+",r"\1[REDACTED]",text)
class ContextFilter(logging.Filter):
    def filter(self,record):record.request_id=request_id_var.get();record.component=getattr(record,"component",record.name.rsplit(".",1)[-1].upper());return True
def configure_logging(settings=None)->None:
    level_name=str(getattr(settings,"log_level","INFO")).upper();level=getattr(logging,level_name,logging.INFO)
    if getattr(settings,"app_env","development").casefold()=="production" and level<logging.INFO:level=logging.INFO
    root=logging.getLogger();root.setLevel(level);formatter=logging.Formatter("%(asctime)s %(levelname)-8s [%(component)s] [req=%(request_id)s] %(message)s",datefmt="%H:%M:%S")
    if not any(getattr(x,"_attendai",False) for x in root.handlers):
        console=logging.StreamHandler();console._attendai=True;console.setFormatter(formatter);console.addFilter(ContextFilter());root.addHandler(console)
        if settings and settings.app_env.casefold()=="development" and getattr(settings,"enable_file_logging",False):
            path=Path(__file__).resolve().parents[3]/"logs"/"attendai-backend.log";path.parent.mkdir(exist_ok=True);handler=RotatingFileHandler(path,maxBytes=2_000_000,backupCount=3,encoding="utf-8");handler._attendai=True;handler.setFormatter(formatter);handler.addFilter(ContextFilter());root.addHandler(handler)
def safe_log(logger,level:int,message:str,**fields):
    safe=sanitize(fields);suffix=" ".join(f"{k}={json.dumps(v,separators=(',',':'))}" for k,v in safe.items());logger.log(level,f"{message}{' '+suffix if suffix else ''}")
