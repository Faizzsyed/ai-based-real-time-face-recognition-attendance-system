"""Latest-frame OpenCV capture; capture never waits for JPEG, UI, or AI work."""
from __future__ import annotations
import logging,threading,time
from dataclasses import dataclass
import cv2
logger=logging.getLogger("CAMERA");perf_logger=logging.getLogger("PERF")
class CameraUnavailable(RuntimeError):pass
@dataclass(frozen=True)
class CameraFrame:image:object;sequence:int;captured_at:float
class LatestFrameBuffer:
    def __init__(self):self._lock=threading.Lock();self._frame=None;self.published=0;self.dropped=0
    def publish(self,image,captured_at=None):
        with self._lock:
            if self._frame is not None:self.dropped+=1
            self.published+=1;self._frame=CameraFrame(image,self.published,captured_at or time.monotonic());return self._frame
    def latest(self,after_sequence=-1,copy=True):
        with self._lock:
            item=self._frame
            if item is None or item.sequence<=after_sequence:return None
            image=item.image.copy() if copy and hasattr(item.image,"copy") else item.image;return CameraFrame(image,item.sequence,item.captured_at)
    @property
    def queued(self):return int(self._frame is not None)
    def clear(self):
        with self._lock:self._frame=None
class CameraService:
    def __init__(self,index=0,capture_factory=None,preview_fps=24,width=1280,height=720):
        self.index=index;self.capture_factory=capture_factory or cv2.VideoCapture;self.preview_fps=max(1,min(int(preview_fps),30));self.width=int(width);self.height=int(height);self.frames=LatestFrameBuffer();self._capture=None;self._thread=None;self._stop=threading.Event();self._release_lock=threading.Lock();self._last_perf=0.;self._perf_frames=0;self.capture_fps=0.
    @property
    def running(self):return bool(self._thread and self._thread.is_alive())
    def start(self):
        if self.running:return
        logger.info("[CAMERA] open requested index=%s",self.index);capture=self.capture_factory(self.index)
        if not capture or not capture.isOpened():
            if capture:capture.release()
            raise CameraUnavailable("Camera is unavailable or permission was denied.")
        for prop,value in ((cv2.CAP_PROP_FRAME_WIDTH,self.width),(cv2.CAP_PROP_FRAME_HEIGHT,self.height),(cv2.CAP_PROP_BUFFERSIZE,1)):
            try:capture.set(prop,value)
            except Exception:pass
        self._capture=capture;self.frames.clear();self._stop.clear();self._last_perf=time.monotonic();self._perf_frames=0;self._thread=threading.Thread(target=self._loop,name="AttendAI-Camera-Capture",daemon=True);self._thread.start();logger.info("[CAMERA] opened index=%s",self.index)
    def _loop(self):
        failures=0
        try:
            while not self._stop.is_set():
                capture=self._capture
                if capture is None:break
                ok,frame=capture.read();now=time.monotonic()
                if not ok or frame is None:
                    failures+=1;logger.warning("[CAMERA] frame read failed consecutive=%s; retaining last valid frame",failures)
                    if failures>=5:logger.error("[CAMERA] disconnected after repeated read failures");break
                    time.sleep(.02);continue
                failures=0;self.frames.publish(frame,now);self._perf_frames+=1;elapsed=now-self._last_perf
                if elapsed>=2:
                    self.capture_fps=self._perf_frames/elapsed;perf_logger.info("[PERF] camera_capture_fps=%.1f frames_queued=%s frames_dropped=%s",self.capture_fps,self.frames.queued,self.frames.dropped);self._perf_frames=0;self._last_perf=now
        except Exception:logger.exception("[CAMERA] capture loop failed")
        finally:self._release()
    def raw_snapshot(self,after_sequence=-1):return self.frames.latest(after_sequence)
    def _encode(self,frame,max_width,quality):
        started=time.perf_counter();image=frame.image;height,width=image.shape[:2]
        if width>max_width:
            scale=max_width/width;image=cv2.resize(image,(max_width,max(1,int(height*scale))),interpolation=cv2.INTER_AREA)
        ok,encoded=cv2.imencode(".jpg",image,[int(cv2.IMWRITE_JPEG_QUALITY),int(quality)]);perf_logger.debug("[PERF] jpeg_encode_ms=%.2f",(time.perf_counter()-started)*1000);return encoded.tobytes() if ok else None
    def encode_preview(self,frame,max_width=960,quality=78):return self._encode(frame,max_width,quality)
    def encode_analysis(self,frame,max_width=640,quality=88):return self._encode(frame,max_width,quality)
    def snapshot(self):
        item=self.raw_snapshot();return (self.encode_preview(item),item.sequence) if item else (None,0)
    def stop(self):
        self._stop.set();thread=self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=1.5)
            if thread.is_alive():self._release();thread.join(timeout=1)
        self._release();self._thread=thread if thread and thread.is_alive() else None;logger.info("[CAMERA] stopped")
    def _release(self):
        with self._release_lock:
            capture,self._capture=self._capture,None
            if capture:
                try:capture.release()
                finally:logger.info("[CAMERA] released")
    def __enter__(self):self.start();return self
    def __exit__(self,*_):self.stop()
