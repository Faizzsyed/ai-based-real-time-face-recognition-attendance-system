"""Tenant-bound AES-256-GCM encryption for biometric embeddings."""
import base64,json,os
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.errors import AppError

ENCRYPTION_VERSION="aes-256-gcm-v1"
def _key(raw:str)->bytes:
    if not raw:raise AppError("FACE_ENCRYPTION_NOT_CONFIGURED","Face embedding encryption is not configured.",503)
    candidates=[]
    try:
        if len(raw)==64:candidates.append(bytes.fromhex(raw))
    except ValueError:pass
    try:candidates.append(base64.b64decode(raw,validate=True))
    except ValueError:pass
    candidates.append(raw.encode())
    key=next((x for x in candidates if len(x)==32),None)
    if key is None:raise AppError("FACE_ENCRYPTION_KEY_INVALID","Face embedding encryption key must resolve to exactly 32 bytes.",503)
    return key
def _aad(institution_id,student_id,model_version):return f"AttendAI:{institution_id}:{student_id}:{model_version}".encode()
def encrypt_embedding(values,institution_id,student_id,model_version,key_text):
    numbers=[float(x) for x in values]
    if not numbers or any(not __import__("math").isfinite(x) for x in numbers):raise AppError("INVALID_EMBEDDING","Face embedding is invalid.",422)
    nonce=os.urandom(12);ciphertext=AESGCM(_key(key_text)).encrypt(nonce,json.dumps(numbers,separators=(",",":")).encode(),_aad(institution_id,student_id,model_version))
    return {"version":ENCRYPTION_VERSION,"algorithm":"AES-256-GCM","nonce":base64.b64encode(nonce).decode(),"ciphertext":base64.b64encode(ciphertext).decode()}
def decrypt_embedding(payload,institution_id,student_id,model_version,key_text):
    if not isinstance(payload,dict) or payload.get("version")!=ENCRYPTION_VERSION or payload.get("algorithm")!="AES-256-GCM":raise AppError("INVALID_ENCRYPTED_EMBEDDING","Encrypted embedding payload is invalid.",500)
    try:
        plaintext=AESGCM(_key(key_text)).decrypt(base64.b64decode(payload["nonce"],validate=True),base64.b64decode(payload["ciphertext"],validate=True),_aad(institution_id,student_id,model_version));values=json.loads(plaintext)
    except (KeyError,ValueError,InvalidTag,json.JSONDecodeError) as exc:raise AppError("FACE_EMBEDDING_DECRYPTION_FAILED","Encrypted face embedding authentication failed.",500) from exc
    if not isinstance(values,list) or not values:raise AppError("INVALID_ENCRYPTED_EMBEDDING","Decrypted embedding is invalid.",500)
    return [float(x) for x in values]
