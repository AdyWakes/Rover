from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml

if __package__:
    from .camera import Camera
else:
    from camera import Camera


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class TrackConfig:
    hsv_lower: tuple[int, int, int]
    hsv_upper: tuple[int, int, int]
    min_area: int = 800
    deadband_px: int = 40
    base_speed: float = 35.0
    turn_gain: float = 45.0
    max_speed: float = 70.0
    lost_stop_frames: int = 4

    @classmethod
    def from_yaml(cls, path: str | Path) -> "TrackConfig":
        with open(path, "r", encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
        hsv = data.get("hsv", {})
        lower = hsv.get("lower", [35, 80, 60])
        upper = hsv.get("upper", [85, 255, 255])
        steer = data.get("steering", {})
        return cls(
            hsv_lower=(int(lower[0]), int(lower[1]), int(lower[2])),
            hsv_upper=(int(upper[0]), int(upper[1]), int(upper[2])),
            min_area=int(data.get("min_area", 800)),
            deadband_px=int(steer.get("deadband_px", 40)),
            base_speed=float(steer.get("base_speed", 35.0)),
            turn_gain=float(steer.get("turn_gain", 45.0)),
            max_speed=float(steer.get("max_speed", 70.0)),
            lost_stop_frames=int(data.get("lost_stop_frames", 4)),
        )


class VisionTracker:
    def __init__(self, camera: Camera, config: TrackConfig):
        self.camera = camera
        self.cfg = config
        self._lost_frames = 0

    @classmethod
    def from_config_file(cls, camera: Camera, path: str | Path) -> "VisionTracker":
        return cls(camera, TrackConfig.from_yaml(path))

    def _extract_target(self, frame: Any) -> tuple[float | None, float, Any]:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array(self.cfg.hsv_lower), np.array(self.cfg.hsv_upper))
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None, 0.0, mask

        largest = max(contours, key=cv2.contourArea)
        area = float(cv2.contourArea(largest))
        if area < float(self.cfg.min_area):
            return None, area, mask

        moments = cv2.moments(largest)
        if moments["m00"] == 0:
            return None, area, mask

        cx = moments["m10"] / moments["m00"]
        return cx, area, mask

    def control_from_frame(self, frame: Any) -> tuple[str, float, float]:
        h, w = frame.shape[:2]
        cx, area, _ = self._extract_target(frame)
        if cx is None:
            self._lost_frames += 1
            if self._lost_frames >= self.cfg.lost_stop_frames:
                return "stop", 0.0, 0.0
            return "search", 0.0, 0.0

        self._lost_frames = 0
        error_px = cx - (w / 2.0)
        if abs(error_px) <= float(self.cfg.deadband_px):
            speed = _clamp(self.cfg.base_speed, -self.cfg.max_speed, self.cfg.max_speed)
            return "forward", speed, speed

        norm = _clamp(error_px / (w / 2.0), -1.0, 1.0)
        turn = norm * self.cfg.turn_gain
        left = _clamp(self.cfg.base_speed + turn, -self.cfg.max_speed, self.cfg.max_speed)
        right = _clamp(self.cfg.base_speed - turn, -self.cfg.max_speed, self.cfg.max_speed)
        cmd = "right" if error_px > 0 else "left"
        return cmd, left, right

    def next_control(self) -> tuple[str, float, float]:
        ok, frame = self.camera.read()
        if not ok or frame is None:
            self._lost_frames += 1
            return "stop", 0.0, 0.0
        return self.control_from_frame(frame)
