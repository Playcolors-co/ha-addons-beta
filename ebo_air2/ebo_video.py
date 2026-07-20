"""
ebo_video.py — receive the robot's Agora RTC video (encoded H.264/H.265 frames) and
republish it as RTSP so Home Assistant can show it as a camera.

Pipeline:  Agora encoded-frame observer  ->  ffmpeg (-c copy, no transcode)  ->  RTSP (mediamtx)

The RTSP stream is served at  rtsp://<add-on host>:8554/ebo  (port exposed by the add-on).
In Home Assistant add a *Generic Camera* pointing at that URL.
"""
import os
import subprocess
import threading
import time

from agora.rtc.video_encoded_frame_observer import IVideoEncodedFrameObserver


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


class VideoPipeline(IVideoEncodedFrameObserver):
    def __init__(self, rtsp_port=8554, path="ebo"):
        super().__init__()
        self.rtsp_port = rtsp_port
        self.rtsp_url = f"rtsp://127.0.0.1:{rtsp_port}/{path}"
        self.ff = None
        self.codec = None
        self.frames = 0
        self.lock = threading.Lock()
        self._start_mediamtx()

    # ---- RTSP server ----
    def _start_mediamtx(self):
        # A config file is more reliable than env vars across mediamtx versions.
        cfg = "/tmp/mediamtx.yml"
        with open(cfg, "w") as f:
            f.write("logLevel: error\n"
                    f"rtspAddress: :{self.rtsp_port}\n"
                    "paths:\n  all_others:\n")
        try:
            self.mediamtx = subprocess.Popen(
                ["/usr/local/bin/mediamtx", cfg],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1)
            log("[video] mediamtx RTSP server on :%d" % self.rtsp_port)
        except FileNotFoundError:
            log("[video] mediamtx not found — video disabled")
            self.mediamtx = None

    # ---- ffmpeg (started on first frame, once codec is known) ----
    def _start_ffmpeg(self, codec_type):
        # codec_type: 2 = H264, 3 = H265 (VideoCodecType)
        fmt = "hevc" if codec_type == 3 else "h264"
        log("[video] first frame, codec=%s -> starting ffmpeg" % fmt)
        self.ff = subprocess.Popen([
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-fflags", "+genpts", "-f", fmt, "-i", "pipe:0",
            "-c", "copy", "-f", "rtsp", "-rtsp_transport", "tcp", self.rtsp_url,
        ], stdin=subprocess.PIPE)

    # ---- Agora callback: one encoded frame ----
    def on_encoded_video_frame(self, uid, image_buffer, length, video_encoded_frame_info):
        try:
            with self.lock:
                if self.ff is None:
                    self.codec = getattr(video_encoded_frame_info, "codec_type", 3)
                    try:
                        self.codec = int(self.codec)
                    except Exception:
                        self.codec = 3
                    self._start_ffmpeg(self.codec)
                self.frames += 1
                if self.frames == 1 or self.frames % 300 == 0:
                    log("[video] %d frames received (%dx%d)" % (
                        self.frames,
                        getattr(video_encoded_frame_info, "width", 0),
                        getattr(video_encoded_frame_info, "height", 0)))
                try:
                    self.ff.stdin.write(bytes(image_buffer))
                except (BrokenPipeError, ValueError):
                    pass
        except Exception as e:
            log("[video] frame error:", e)
        return 0

    def stop(self):
        for p in (self.ff, getattr(self, "mediamtx", None)):
            try:
                if p:
                    p.terminate()
            except Exception:
                pass
