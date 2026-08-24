"""Download checksum-pinned YuNet, SFace, and MediaPipe Face Landmarker assets."""
from __future__ import annotations
import hashlib,sys,urllib.error,urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];MODELS_DIR=ROOT/"models"
MODELS={
 "face_detection_yunet_2023mar.onnx":{"url":"https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx","sha256":"8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4","min_bytes":200_000},
 "face_recognition_sface_2021dec.onnx":{"url":"https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx","sha256":"0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79","min_bytes":30_000_000},
 "face_landmarker.task":{"url":"https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task","sha256":"64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff","min_bytes":3_000_000},
}
def digest(path):
    value=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):value.update(chunk)
    return value.hexdigest()
def valid(path,meta):
    if not path.is_file() or path.stat().st_size<int(meta["min_bytes"]):return False
    with path.open("rb") as stream:
        if stream.read(128).startswith(b"version https://git-lfs.github.com/spec"):return False
    return digest(path)==meta["sha256"]
def main():
    MODELS_DIR.mkdir(parents=True,exist_ok=True)
    for name,meta in MODELS.items():
        destination=MODELS_DIR/name
        if valid(destination,meta):print(f"Verified: {destination}");continue
        temporary=destination.with_suffix(destination.suffix+".download")
        try:
            print(f"Downloading {name} from official OpenCV Zoo...")
            with urllib.request.urlopen(meta["url"],timeout=60) as response,temporary.open("wb") as output:
                for chunk in iter(lambda:response.read(1024*1024),b""):output.write(chunk)
        except (OSError,TimeoutError,urllib.error.URLError) as exc:
            temporary.unlink(missing_ok=True);print(f"Download failed: {exc}",file=sys.stderr);return 1
        if not valid(temporary,meta):temporary.unlink(missing_ok=True);print(f"Checksum/size validation failed for {name}.",file=sys.stderr);return 1
        temporary.replace(destination);print(f"Saved: {destination}")
    return 0
if __name__=="__main__":raise SystemExit(main())
