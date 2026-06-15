from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

try:
    import RPi.GPIO as GPIO
except Exception:
    GPIO = None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class MotorConfig:
    stby: int
    left_in1: int
    left_in2: int
    left_pwm: int
    right_in1: int
    right_in2: int
    right_pwm: int
    pwm_frequency: int = 1000
    default_speed: int = 45

    @classmethod
    def from_yaml(cls, path: str | Path) -> "MotorConfig":
        with open(path, "r", encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
        tb = data.get("tb6612", {})
        left = tb.get("left", {})
        right = tb.get("right", {})
        return cls(
            stby=int(tb.get("stby", 17)),
            left_in1=int(left.get("in1", 27)),
            left_in2=int(left.get("in2", 22)),
            left_pwm=int(left.get("pwm", 18)),
            right_in1=int(right.get("in1", 23)),
            right_in2=int(right.get("in2", 24)),
            right_pwm=int(right.get("pwm", 13)),
            pwm_frequency=int(data.get("pwm_frequency", 1000)),
            default_speed=int(data.get("default_speed", 45)),
        )


class TB6612FNG:
    def __init__(self, config: MotorConfig):
        self.cfg = config
        self._enabled = GPIO is not None
        self._pwm_left = None
        self._pwm_right = None
        if self._enabled:
            self._setup_gpio()

    @classmethod
    def from_config_file(cls, path: str | Path) -> "TB6612FNG":
        return cls(MotorConfig.from_yaml(path))

    def _setup_gpio(self) -> None:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.cfg.stby, GPIO.OUT)
        GPIO.setup(self.cfg.left_in1, GPIO.OUT)
        GPIO.setup(self.cfg.left_in2, GPIO.OUT)
        GPIO.setup(self.cfg.right_in1, GPIO.OUT)
        GPIO.setup(self.cfg.right_in2, GPIO.OUT)
        GPIO.setup(self.cfg.left_pwm, GPIO.OUT)
        GPIO.setup(self.cfg.right_pwm, GPIO.OUT)

        self._pwm_left = GPIO.PWM(self.cfg.left_pwm, self.cfg.pwm_frequency)
        self._pwm_right = GPIO.PWM(self.cfg.right_pwm, self.cfg.pwm_frequency)
        self._pwm_left.start(0)
        self._pwm_right.start(0)
        GPIO.output(self.cfg.stby, GPIO.HIGH)
        self.stop()

    def _set_motor(self, in1: int, in2: int, pwm: Any, speed: float) -> None:
        if not self._enabled or pwm is None:
            return
        speed = _clamp(speed, -100.0, 100.0)
        duty = abs(speed)
        if speed > 0:
            GPIO.output(in1, GPIO.HIGH)
            GPIO.output(in2, GPIO.LOW)
        elif speed < 0:
            GPIO.output(in1, GPIO.LOW)
            GPIO.output(in2, GPIO.HIGH)
        else:
            GPIO.output(in1, GPIO.LOW)
            GPIO.output(in2, GPIO.LOW)
        pwm.ChangeDutyCycle(duty)

    def set_speeds(self, left_speed: float, right_speed: float) -> None:
        self._set_motor(self.cfg.left_in1, self.cfg.left_in2, self._pwm_left, left_speed)
        self._set_motor(self.cfg.right_in1, self.cfg.right_in2, self._pwm_right, right_speed)

    def forward(self, speed: float | None = None) -> None:
        s = self.cfg.default_speed if speed is None else speed
        self.set_speeds(s, s)

    def backward(self, speed: float | None = None) -> None:
        s = self.cfg.default_speed if speed is None else speed
        self.set_speeds(-s, -s)

    def left(self, speed: float | None = None) -> None:
        s = self.cfg.default_speed if speed is None else speed
        self.set_speeds(-s, s)

    def right(self, speed: float | None = None) -> None:
        s = self.cfg.default_speed if speed is None else speed
        self.set_speeds(s, -s)

    def stop(self) -> None:
        self.set_speeds(0, 0)

    def cleanup(self) -> None:
        if self._enabled:
            self.stop()
            if self._pwm_left is not None:
                self._pwm_left.stop()
            if self._pwm_right is not None:
                self._pwm_right.stop()
            GPIO.output(self.cfg.stby, GPIO.LOW)
            GPIO.cleanup()

