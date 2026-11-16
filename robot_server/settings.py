"""Configurações do servidor, lidas uma única vez do arquivo .env."""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_DIR / ".env"

# Nomes antigos (em português) continuam aceitos para não quebrar .env existentes
_LEGACY_KEYS = {
    "MOTOR_RIGHT_FORWARD_PIN": "PORTA_MOTOR_DIREITA_FRENTE",
    "MOTOR_RIGHT_BACKWARD_PIN": "PORTA_MOTOR_DIREITA_TRAS",
    "MOTOR_LEFT_FORWARD_PIN": "PORTA_MOTOR_ESQUERDA_FRENTE",
    "MOTOR_LEFT_BACKWARD_PIN": "PORTA_MOTOR_ESQUERDA_TRAS",
    "SERVO_VERTICAL_PIN": "PORTA_SERVO_VERTICAL",
    "SERVO_HORIZONTAL_PIN": "PORTA_SERVO_HORIZONTAL",
    "ULTRASONIC_TRIG_PIN": "PORTA_ULTRASSONICO_TRIG",
    "ULTRASONIC_ECHO_PIN": "PORTA_ULTRASSONICO_ECHO",
}


def _raw(key: str) -> str | None:
    value = os.getenv(key)
    if value is None and key in _LEGACY_KEYS:
        value = os.getenv(_LEGACY_KEYS[key])
    if value is None or not value.strip():
        return None
    return value.strip()


def _str(key: str, default: str) -> str:
    return _raw(key) or default


def _int(key: str, default: int) -> int:
    value = _raw(key)
    return default if value is None else int(value)


def _float(key: str, default: float) -> float:
    value = _raw(key)
    return default if value is None else float(value)


def _bool(key: str, default: bool) -> bool:
    value = _raw(key)
    return default if value is None else value.lower() in {"1", "true", "yes", "on", "sim"}


def _size(key: str, default: tuple[int, int]) -> tuple[int, int]:
    value = _raw(key)
    if value is None:
        return default
    width, _, height = value.lower().partition("x")
    return int(width), int(height)


@dataclass(frozen=True)
class CameraAxisSettings:
    pin: int
    min_angle: float
    max_angle: float
    start_angle: float
    invert: bool


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    gpio_backend: str
    gpio_chip: int | None

    motor_right_forward_pin: int
    motor_right_backward_pin: int
    motor_left_forward_pin: int
    motor_left_backward_pin: int

    camera_vertical: CameraAxisSettings
    camera_horizontal: CameraAxisSettings
    camera_speed_dps: float
    servo_release_after_s: float

    control_tick_s: float
    watchdog_timeout_s: float

    ultrasonic_enabled: bool
    ultrasonic_trig_pin: int
    ultrasonic_echo_pin: int
    ultrasonic_rate_hz: float
    ultrasonic_max_distance_m: float
    speed_of_sound_mps: float

    auto_update: bool
    auto_update_branch: str

    stream_host: str
    stream_port: int
    stream_size: tuple[int, int]
    stream_fps: float

    shutdown_enabled: bool
    shutdown_command: tuple[str, ...]


def load_settings() -> Settings:
    load_dotenv(ENV_FILE)

    v_min = _float("CAMERA_V_MIN_ANGLE", 5)
    v_max = _float("CAMERA_V_MAX_ANGLE", 135)
    h_min = _float("CAMERA_H_MIN_ANGLE", 5)
    h_max = _float("CAMERA_H_MAX_ANGLE", 175)

    return Settings(
        host=_str("SERVER_HOST", "0.0.0.0"),
        port=_int("SERVER_PORT", 5001),
        gpio_backend=_str("GPIO_BACKEND", "auto").lower(),
        # None = detecta o chip do processador automaticamente (só lgpio)
        gpio_chip=None if _raw("GPIO_CHIP") is None else _int("GPIO_CHIP", 0),
        motor_right_forward_pin=_int("MOTOR_RIGHT_FORWARD_PIN", 27),
        motor_right_backward_pin=_int("MOTOR_RIGHT_BACKWARD_PIN", 17),
        motor_left_forward_pin=_int("MOTOR_LEFT_FORWARD_PIN", 4),
        motor_left_backward_pin=_int("MOTOR_LEFT_BACKWARD_PIN", 3),
        camera_vertical=CameraAxisSettings(
            pin=_int("SERVO_VERTICAL_PIN", 18),
            min_angle=v_min,
            max_angle=v_max,
            start_angle=_float("CAMERA_V_START_ANGLE", (v_min + v_max) / 2),
            invert=_bool("CAMERA_V_INVERT", False),
        ),
        camera_horizontal=CameraAxisSettings(
            pin=_int("SERVO_HORIZONTAL_PIN", 23),
            min_angle=h_min,
            max_angle=h_max,
            start_angle=_float("CAMERA_H_START_ANGLE", (h_min + h_max) / 2),
            invert=_bool("CAMERA_H_INVERT", True),
        ),
        camera_speed_dps=_float("CAMERA_SPEED_DPS", 100),
        servo_release_after_s=_float("SERVO_RELEASE_AFTER_S", 0.5),
        control_tick_s=_float("CONTROL_TICK_S", 0.02),
        watchdog_timeout_s=_float("WATCHDOG_TIMEOUT_S", 1.0),
        ultrasonic_enabled=_bool("ULTRASONIC_ENABLED", False),
        ultrasonic_trig_pin=_int("ULTRASONIC_TRIG_PIN", 19),
        ultrasonic_echo_pin=_int("ULTRASONIC_ECHO_PIN", 26),
        ultrasonic_rate_hz=_float("ULTRASONIC_RATE_HZ", 20),
        ultrasonic_max_distance_m=_float("ULTRASONIC_MAX_DISTANCE_M", 4.0),
        speed_of_sound_mps=_float("SPEED_OF_SOUND_MPS", 343.0),
        auto_update=_bool("AUTO_UPDATE", True),
        auto_update_branch=_str("AUTO_UPDATE_BRANCH", "master"),
        stream_host=_str("STREAM_HOST", "0.0.0.0"),
        stream_port=_int("STREAM_PORT", 8080),
        stream_size=_size("STREAM_SIZE", (640, 480)),
        stream_fps=_float("STREAM_FPS", 30),
        shutdown_enabled=_bool("SHUTDOWN_ENABLED", True),
        shutdown_command=tuple(shlex.split(_str("SHUTDOWN_COMMAND", "sudo -n /usr/bin/systemctl poweroff"))),
    )
