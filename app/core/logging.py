"""Flet-side safe developer logging."""
from __future__ import annotations
import logging,re
from typing import Any
SENSITIVE=("password","authorization","access_token","refresh_token","refreshtoken","jwt","mongodb_uri","embedding","encryption_key","image_bytes","file_bytes")
def sanitize(value:Any,key=""):
    if any(x in key.casefold().replace("-","_") for x in SENSITIVE):return "[REDACTED]"
    if isinstance(value,dict):return {k:sanitize(v,str(k)) for k,v in value.items()}
    if isinstance(value,bytes):return "[REDACTED BYTES]"
    return re.sub(r"(?i)(bearer\s+)\S+",r"\1[REDACTED]",str(value))
def configure_logging(settings):
    level=getattr(logging,str(settings.log_level).upper(),logging.INFO)
    if settings.app_env.casefold()=="production" and level<logging.INFO:level=logging.INFO
    logging.basicConfig(level=level,format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",datefmt="%H:%M:%S")
def log_ui_event(action:str,**fields):
    from app.core.config import get_settings
    if not get_settings().enable_ui_event_logging:return
    safe=sanitize(fields);logging.getLogger("UI").info("%s%s",action," "+" ".join(f"{k}={v}" for k,v in safe.items()) if safe else "")
