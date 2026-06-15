import time
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Tuple

import cv2
import yaml


@dataclass
class CameraConfig:
    index: int = 0
    width: int = 640
    height: int = 480
    fps: int = 30

    @classmethod
    def from_yaml(cls, path: str | Path) -> "CameraConfig":
        with open(path, "r", encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
        return cls(
            index=int(data.get("index", cls.index)),
            width=int(data.get("width", cls.width)),
            height=int(data.get("height", cls.height)),
            fps=int(data.get("fps", cls.fps)),
        )


class Camera:
    def __init__(
        self,
        index: int = 0,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
        reconnect_delay_s: float = 0.5,
    ) -> None:
        self.index = index
        self.width = width
        self.height = height
        self.fps = fps
        self.reconnect_delay_s = reconnect_delay_s
        self._lock = threading.RLock()
        self._reconnect_lock = threading.Lock()
        self.cap: cv2.VideoCapture | None = None
        self._open()

    @classmethod
    def from_config_file(cls, path: str | Path) -> "Camera":
        cfg = CameraConfig.from_yaml(path)
        return cls(
            index=cfg.index,
            width=cfg.width,
            height=cfg.height,
            fps=cfg.fps,
        )

    def _open(self) -> None:
        with self._lock:
            self.release()
            self.cap = cv2.VideoCapture(self.index)
            if self.cap is None:
                return
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)

    def _reconnect(self) -> bool:
        with self._reconnect_lock:
            with self._lock:
                if self.cap is not None and self.cap.isOpened():
                    return True
            self.release()
            time.sleep(self.reconnect_delay_s)
            self._open()
            with self._lock:
                return bool(self.cap is not None and self.cap.isOpened())

    def read(self) -> Tuple[bool, Any]:
        with self._lock:
            if self.cap is not None and self.cap.isOpened():
                ok, frame = self.cap.read()
                if ok:
                    return True, frame
        if not self._reconnect():
            return False, None
        with self._lock:
            if self.cap is None or not self.cap.isOpened():
                return False, None
            return self.cap.read()

    def release(self) -> None:
        with self._lock:
            if self.cap is not None:
                self.cap.release()
                self.cap = None
