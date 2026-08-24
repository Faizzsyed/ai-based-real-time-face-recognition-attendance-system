"""Create missing local-only verification configuration without revealing secrets."""
from __future__ import annotations
import base64,secrets
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];target=ROOT/".env"
APPROVED_DATABASE="attendai_python_dev"
defaults={
    "APP_ENV":"development","APP_NAME":"AI Based Real-Time Face Recognition Attendance System","API_HOST":"127.0.0.1","API_PORT":"8000",
    "MONGODB_URI":"mongodb://127.0.0.1:27017/","MONGODB_DATABASE":APPROVED_DATABASE,
    "ENABLE_DEV_ACADEMIC_API":"false","ENABLE_DEV_ROLE_PREVIEW":"true","CORS_ORIGINS":"",
    "FACE_AI_ENABLED":"false","FACE_DETECTION_MODEL_PATH":"models/face_detection_yunet_2023mar.onnx",
    "FACE_RECOGNITION_MODEL_PATH":"models/face_recognition_sface_2021dec.onnx","FACE_DETECTION_THRESHOLD":"0.90",
    "FACE_MATCH_THRESHOLD":"0.363","FACE_IDENTIFICATION_MIN_MARGIN":"0.08","FACE_RECOGNITION_COOLDOWN_SECONDS":"8",
    "FACE_MAX_IMAGE_BYTES":"5242880","API_BASE_URL":"http://127.0.0.1:8000",
}
def main():
    existing=target.read_text(encoding="utf-8").splitlines() if target.exists() else []
    values={};order=[]
    for line in existing:
        if line and not line.lstrip().startswith("#") and "=" in line:
            key,value=line.split("=",1);values[key]=value;order.append(key)
    configured_database=values.get("MONGODB_DATABASE",APPROVED_DATABASE).strip()
    if configured_database!=APPROVED_DATABASE or not configured_database.startswith("attendai_python"):
        raise SystemExit("Refusing unsafe database target; no configuration written.")
    for key,value in defaults.items():
        if key not in values:values[key]=value;order.append(key)
    if not values.get("MONGODB_URI","").strip():values["MONGODB_URI"]=defaults["MONGODB_URI"]
    if not values.get("JWT_SECRET","").strip():values["JWT_SECRET"]=secrets.token_urlsafe(48);order.append("JWT_SECRET") if "JWT_SECRET" not in order else None
    if not values.get("FACE_EMBEDDING_ENCRYPTION_KEY","").strip():values["FACE_EMBEDDING_ENCRYPTION_KEY"]=base64.b64encode(secrets.token_bytes(32)).decode();order.append("FACE_EMBEDDING_ENCRYPTION_KEY") if "FACE_EMBEDDING_ENCRYPTION_KEY" not in order else None
    target.write_text("\n".join(f"{key}={values[key]}" for key in dict.fromkeys(order))+"\n",encoding="utf-8")
    print("Local verification configuration ready; secret values were not displayed.")
if __name__=="__main__":main()
