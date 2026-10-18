"""Cloud persistence/configuration contracts, without any real MongoDB client."""
import io
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock,patch

import cv2
import numpy as np
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import AppError
from app.main import app
from app.db.mongo import mongo
from app.modules.face_ai.storage import MongoEnrollmentImageStorage,EnrollmentImageStorage,configured_reference_storage,reference_response

IID="0123456789abcdef01234567";SID="89abcdef0123456701234567";OTHER="89abcdef0123456701234568"


class Manifests:
    def __init__(self):self.docs={};self.fail=False
    def find_one_and_replace(self,query,document,**_):
        if self.fail:raise OSError("private database details")
        previous=self.docs.get(query["_id"]);self.docs[query["_id"]]=deepcopy(document);return previous
    def find_one(self,query):return deepcopy(self.docs.get(query["_id"]))
    def find_one_and_delete(self,query):return self.docs.pop(query["_id"],None)


class Bucket:
    def __init__(self):self.files={};self.fail_after=None
    def upload_from_stream(self,name,source,metadata):
        if self.fail_after is not None and len(self.files)>=self.fail_after:raise OSError("upload failed")
        file_id=ObjectId();self.files[file_id]=(name,bytes(source),metadata);return file_id
    def open_download_stream(self,file_id):return io.BytesIO(self.files[file_id][1])
    def delete(self,file_id):self.files.pop(file_id,None)


def storage(tmp_path):
    db=SimpleNamespace(face_reference_sets=Manifests());bucket=Bucket()
    local=EnrollmentImageStorage(tmp_path,key_text="k"*32)
    return MongoEnrollmentImageStorage("k"*32,db,bucket,local),db,bucket,local


def frames(count=3):
    _,encoded=cv2.imencode(".jpg",np.full((40,40,3),120,np.uint8))
    return [(encoded.tobytes(),"image/jpeg") for _ in range(count)]


def test_gridfs_retains_only_encrypted_bytes_and_survives_storage_recreation(tmp_path):
    store,db,bucket,local=storage(tmp_path);store.save(IID,SID,frames())
    assert len(bucket.files)==3 and not list(tmp_path.rglob("*"))
    for name,data,metadata in bucket.files.values():
        assert name.endswith(".enc") and data.startswith(b"ATTENDAI-FRAME-1\n")
        assert frames(1)[0][0] not in data and metadata["encrypted"] is True
        assert "key" not in str(metadata)
    restarted=MongoEnrollmentImageStorage("k"*32,db,bucket,local)
    response=reference_response(restarted,IID,SID)
    assert response.body.startswith(b"\xff\xd8") and response.headers["cache-control"]=="private, no-store"
    assert store.read_reference(IID,OTHER) is None


def test_gridfs_tampering_and_cross_student_relocation_fail_authentication(tmp_path):
    store,db,bucket,_=storage(tmp_path);store.save(IID,SID,frames(1))
    original=db.face_reference_sets.find_one({"_id":f"{IID}:{SID}"})
    db.face_reference_sets.docs[f"{IID}:{OTHER}"]={"files":original["files"]}
    with pytest.raises(AppError):store.read_reference(IID,OTHER)
    file_id=original["files"][0];name,data,meta=bucket.files[file_id]
    bucket.files[file_id]=(name,data[:-1]+bytes([data[-1]^1]),meta)
    with pytest.raises(AppError):store.read_reference(IID,SID)


def test_partial_upload_and_manifest_failure_preserve_previous_reference(tmp_path):
    store,db,bucket,_=storage(tmp_path);store.save(IID,SID,frames(1));before=deepcopy(bucket.files)
    bucket.fail_after=2
    with pytest.raises(OSError):store.save(IID,SID,frames())
    assert bucket.files==before and store.read_reference(IID,SID).startswith(b"\xff\xd8")
    bucket.fail_after=None;db.face_reference_sets.fail=True
    with pytest.raises(OSError):store.save(IID,SID,frames())
    assert bucket.files==before


def test_gridfs_replacement_and_explicit_removal_clean_old_encrypted_files(tmp_path):
    store,db,bucket,_=storage(tmp_path);store.save(IID,SID,frames())
    before=set(bucket.files);store.save(IID,SID,frames(1))
    assert len(bucket.files)==1 and not before.intersection(bucket.files)
    store.remove(IID,SID)
    assert not bucket.files and not db.face_reference_sets.docs


def test_mongodb_mode_reads_legacy_local_reference_without_migrating_it(tmp_path):
    store,db,bucket,local=storage(tmp_path)
    path=local.directory(IID,SID)/"frame_01.jpg";path.parent.mkdir(parents=True);path.write_bytes(b"legacy-photo")
    before=path.stat().st_mtime_ns
    assert store.read_reference(IID,SID)==b"legacy-photo"
    assert path.stat().st_mtime_ns==before and not bucket.files and not db.face_reference_sets.docs


def production(**overrides):
    return Settings(_env_file=None,**{"app_env":"production","cloud_test_mode":True,"mongodb_database":"attendai_cloud_test",
                    "mongodb_uri":"mongodb+srv://atlas.example.mongodb.net/attendai_cloud_test","jwt_secret":"j"*48,
                    "face_ai_enabled":True,"face_embedding_encryption_key":"k"*32,"cors_origins":"",**overrides})


def test_production_uses_gridfs_and_native_clients_need_no_browser_cors():
    configured=production()
    assert isinstance(configured_reference_storage(configured),MongoEnrollmentImageStorage)
    assert configured.cors_origins==""
    assert isinstance(configured_reference_storage(SimpleNamespace(app_env="development",face_reference_storage="auto",face_embedding_encryption_key="k"*32)),EnrollmentImageStorage)


@pytest.mark.parametrize("overrides",[
    {"mongodb_database":"attendai_python_dev"},
    {"mongodb_uri":"mongodb://localhost:27017/"},
    {"mongodb_uri":"mongodb+srv://atlas.example.mongodb.net/attendai_python_dev"},
    {"mongodb_uri":"mongodb+srv://atlas.example.mongodb.net/?tls=false"},
    {"mongodb_uri":"mongodb+srv://atlas.example.mongodb.net/?tlsAllowInvalidCertificates=true"},
    {"face_reference_storage":"local"},
    {"cors_origins":"*"},
    {"cors_origins":"http://browser.example"},
])
def test_cloud_configuration_rejects_local_targets_and_insecure_storage_or_transport(overrides):
    with pytest.raises(ValidationError):production(**overrides)


def test_readiness_checks_live_database_and_missing_face_models(monkeypatch):
    monkeypatch.setattr("app.api.router.get_settings",lambda:production())
    monkeypatch.setattr(mongo,"status","connected");database=Mock();monkeypatch.setattr(mongo,"database",database)
    with patch("app.modules.face_ai.engine.shared_engine") as engine:
        engine.return_value._models.side_effect=AppError("FACE_MODEL_UNAVAILABLE","private path",503)
        response=TestClient(app).get("/api/v1/ready")
        assert response.status_code==503 and response.json()["detail"]=="Face models not ready"
        assert "private path" not in response.text
        engine.return_value._models.side_effect=None
        assert TestClient(app).get("/api/v1/ready").json()["faceModels"]=="loaded"
        database.command.side_effect=OSError("private host")
        response=TestClient(app).get("/api/v1/ready")
        assert response.status_code==503 and response.json()["detail"]=="Database not ready"


def test_docker_build_inputs_and_free_blueprint_are_explicit():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    docker=(root/"Dockerfile").read_text();blueprint=(root/"render.yaml").read_text()
    assert "COPY backend/requirements.txt" in docker and "RUN python /app/scripts/download_face_models.py" in docker
    assert "${PORT:-${API_PORT:-8000}}" in docker and "--host 0.0.0.0" in docker
    assert "plan: free" in blueprint and "branch: demo-cloud" in blueprint and "value: attendai_cloud_test" in blueprint
    assert "disk:" not in blueprint and "databases:" not in blueprint


def test_external_verifier_requires_real_cloud_dependencies_and_authentication():
    import runpy,httpx
    from pathlib import Path
    verify=runpy.run_path(str(Path(__file__).resolve().parents[2]/"scripts/verify_cloud_api.py"))["verify"]
    def response(request):
        status,data={"/api/v1/health":(200,{"success":True,"database":"connected","databaseName":"attendai_cloud_test"}),
                     "/api/v1/ready":(200,{"status":"ready","faceModels":"loaded"}),
                     "/api/v1/admin/students":(401,{"error":{"code":"AUTH_REQUIRED"}})}.get(request.url.path,(404,{"detail":"Not Found"}))
        return httpx.Response(status,json=data)
    with __import__("httpx").Client(transport=httpx.MockTransport(response)) as client:
        assert verify("https://fixture.onrender.com",client)["passed"]
        with pytest.raises(ValueError):verify("http://fixture.onrender.com",client)
