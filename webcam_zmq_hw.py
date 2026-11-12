import json
import threading
import time
from typing import Optional, Tuple

import cv2
import numpy as np
import zmq
from ScopeFoundry import HardwareComponent


class WebcamZmqHW(HardwareComponent):
    """
    ScopeFoundry HardwareComponent that captures frames from a webcam (via OpenCV)
    and streams them out over a ZeroMQ PUB socket as multipart messages:
        [topic_bytes, json_metadata_bytes, raw_numpy_frame_bytes]
    """

    name = "webcam_zmq"

    def setup(self):
        S = self.settings

        S.New(
            "camera_index",
            dtype=int,
            initial=0,
            vmin=0,
            description="OpenCV VideoCapture camera index",
        )
        S.New(
            "width",
            dtype=int,
            initial=640,
            vmin=16,
            vmax=7680,
            unit="px",
            description="Requested capture frame width",
        )
        S.New(
            "height",
            dtype=int,
            initial=480,
            vmin=16,
            vmax=4320,
            unit="px",
            description="Requested capture frame height",
        )
        S.New(
            "fps_target",
            dtype=float,
            initial=30.0,
            vmin=0.5,
            vmax=240.0,
            unit="Hz",
            spinbox_decimals=1,
            description="Target capture and publish frame rate",
        )
        S.New(
            "fps_measured",
            dtype=float,
            initial=0.0,
            ro=True,
            unit="Hz",
            spinbox_decimals=1,
            description="Measured capture/streaming rate",
        )
        S.New(
            "color_mode",
            dtype=str,
            initial="RGB",
            choices=("RGB", "BGR", "GRAY"),
            description="Output frame color format",
        )
        S.New(
            "zmq_bind_address",
            dtype=str,
            initial="tcp://*:5556",
            description="ZMQ PUB socket bind address (e.g. tcp://*:5556)",
        )
        S.New(
            "zmq_topic",
            dtype=str,
            initial="frame",
            description="Multipart topic prefix for published frames",
        )
        S.New(
            "zmq_hwm",
            dtype=int,
            initial=60,
            vmin=1,
            vmax=1000,
            description="ZMQ SNDHWM (send high-water mark) to bound queue latency",
        )
        S.New(
            "stream_enabled",
            dtype=bool,
            initial=True,
            description="Publish captured frames over ZMQ PUB when True",
        )
        S.New(
            "frame_count",
            dtype=int,
            initial=0,
            ro=True,
            description="Total frames captured since connect",
        )

        self._frame_lock = threading.Lock()
        self.latest_frame: Optional[np.ndarray] = None
        self.latest_meta: Optional[dict] = None
        self.cap: Optional[cv2.VideoCapture] = None
        self.zmq_ctx: Optional[zmq.Context] = None
        self.pub_socket: Optional[zmq.Socket] = None

    def connect(self):
        S = self.settings

        # 1. Open webcam via OpenCV
        cam_idx = int(S["camera_index"])
        self.cap = cv2.VideoCapture(cam_idx)
        if not self.cap.isOpened():
            self.cap.release()
            self.cap = None
            raise RuntimeError(f"Could not open webcam at camera_index={cam_idx}")

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(S["width"]))
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(S["height"]))
        self.cap.set(cv2.CAP_PROP_FPS, float(S["fps_target"]))

        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if actual_w > 0:
            S["width"] = actual_w
        if actual_h > 0:
            S["height"] = actual_h

        # 2. Setup ZMQ PUB socket
        self.zmq_ctx = zmq.Context.instance()
        self.pub_socket = self.zmq_ctx.socket(zmq.PUB)
        self.pub_socket.setsockopt(zmq.SNDHWM, int(S["zmq_hwm"]))
        self.pub_socket.setsockopt(zmq.LINGER, 0)
        self.pub_socket.bind(S["zmq_bind_address"])

        S["frame_count"] = 0
        S["fps_measured"] = 0.0
        self._last_frame_time = time.perf_counter()
        self._fps_ema = 0.0

        self.log.info(
            f"Connected webcam #{cam_idx} ({S['width']}x{S['height']}) "
            f"publishing on {S['zmq_bind_address']} topic='{S['zmq_topic']}'"
        )

    def disconnect(self):
        self.settings.disconnect_all_from_hardware()

        if getattr(self, "pub_socket", None) is not None:
            try:
                self.pub_socket.close(linger=0)
            except Exception as err:
                self.log.warning(f"Error closing ZMQ PUB socket: {err}")
            finally:
                self.pub_socket = None

        if getattr(self, "cap", None) is not None:
            try:
                self.cap.release()
            except Exception as err:
                self.log.warning(f"Error releasing VideoCapture: {err}")
            finally:
                self.cap = None

    def threaded_update(self):
        """
        Called repeatedly in HardwareComponent's background thread while connected.
        Captures a frame from the webcam and publishes it over ZMQ PUB.
        """
        if self.cap is None or not self.cap.isOpened():
            time.sleep(0.05)
            return

        t_loop_start = time.perf_counter()
        ok, frame_bgr = self.cap.read()
        if not ok or frame_bgr is None:
            time.sleep(0.01)
            return

        timestamp = time.time()
        color_mode = self.settings["color_mode"]
        if color_mode == "RGB":
            frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        elif color_mode == "GRAY":
            frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        else:
            frame = frame_bgr

        frame = np.ascontiguousarray(frame)
        frame_id = int(self.settings["frame_count"]) + 1
        self.settings["frame_count"] = frame_id

        # Update smoothed FPS measurement
        now = time.perf_counter()
        dt = now - self._last_frame_time
        self._last_frame_time = now
        if dt > 0:
            inst_fps = 1.0 / dt
            self._fps_ema = (
                inst_fps
                if self._fps_ema == 0.0
                else (0.85 * self._fps_ema + 0.15 * inst_fps)
            )
            self.settings["fps_measured"] = self._fps_ema

        meta = {
            "frame_id": frame_id,
            "timestamp": timestamp,
            "dtype": str(frame.dtype),
            "shape": list(frame.shape),
            "color_mode": color_mode,
        }

        with self._frame_lock:
            self.latest_frame = frame
            self.latest_meta = meta

        if self.settings["stream_enabled"] and self.pub_socket is not None:
            topic_bytes = self.settings["zmq_topic"].encode("utf-8")
            meta_bytes = json.dumps(meta).encode("utf-8")
            try:
                self.pub_socket.send_multipart(
                    [topic_bytes, meta_bytes, frame],
                    flags=zmq.NOBLOCK,
                    copy=False,
                )
            except zmq.Again:
                if self.settings["debug_mode"]:
                    self.log.debug("ZMQ PUB high-water mark reached; dropping frame")

        # Pace loop if camera read returned faster than target FPS
        target_fps = float(self.settings["fps_target"])
        if target_fps > 0:
            target_period = 1.0 / target_fps
            elapsed = time.perf_counter() - t_loop_start
            remaining = target_period - elapsed
            if remaining > 0.001:
                time.sleep(remaining)

    def get_latest_frame(self) -> Tuple[Optional[np.ndarray], Optional[dict]]:
        """Thread-safe accessor for the most recently captured frame and metadata."""
        with self._frame_lock:
            if self.latest_frame is None:
                return None, None
            return self.latest_frame.copy(), dict(self.latest_meta)
