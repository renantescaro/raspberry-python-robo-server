from __future__ import annotations

import sys
import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from robot_server.settings import CameraAxisSettings, Settings  # noqa: E402


class FakeBackend:
    """Backend de GPIO em memória que registra todas as operações."""

    name = "fake"

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.pins: dict[int, bool] = {}
        self.writes: list[tuple[int, bool]] = []
        self.servos: dict[int, int] = {}
        self.servo_writes: list[tuple[int, int]] = []
        self.inputs: set[int] = set()
        self.echo_s: float | None = None
        self.cleaned = False

    def setup_output(self, pin: int) -> None:
        with self.lock:
            self.pins[pin] = False

    def write(self, pin: int, value: bool) -> None:
        with self.lock:
            self.pins[pin] = bool(value)
            self.writes.append((pin, bool(value)))

    def servo_pulse(self, pin: int, pulse_us: int) -> None:
        with self.lock:
            self.servos[pin] = pulse_us
            self.servo_writes.append((pin, pulse_us))

    def setup_input(self, pin: int) -> None:
        self.inputs.add(pin)

    def measure_echo(self, trig_pin: int, echo_pin: int, timeout_s: float) -> float | None:
        time.sleep(0.001)
        return self.echo_s

    def cleanup(self) -> None:
        self.cleaned = True


DEFAULT_SETTINGS = Settings(
    host="127.0.0.1",
    port=0,
    gpio_backend="mock",
    gpio_chip=None,
    motor_right_forward_pin=27,
    motor_right_backward_pin=17,
    motor_left_forward_pin=4,
    motor_left_backward_pin=3,
    camera_vertical=CameraAxisSettings(pin=18, min_angle=5, max_angle=135, start_angle=70, invert=False),
    camera_horizontal=CameraAxisSettings(pin=23, min_angle=5, max_angle=175, start_angle=90, invert=True),
    camera_speed_dps=100,
    servo_release_after_s=0.5,
    control_tick_s=0.01,
    watchdog_timeout_s=0.3,
    ultrasonic_enabled=False,
    ultrasonic_trig_pin=19,
    ultrasonic_echo_pin=26,
    ultrasonic_rate_hz=100,
    ultrasonic_max_distance_m=4.0,
    speed_of_sound_mps=343.0,
    auto_update=False,
    auto_update_branch="master",
    stream_host="127.0.0.1",
    stream_port=0,
    stream_size=(640, 480),
    stream_fps=30,
    shutdown_enabled=True,
    shutdown_command=("true",),
)


@pytest.fixture
def backend() -> FakeBackend:
    return FakeBackend()


@pytest.fixture
def make_settings():
    def factory(**overrides) -> Settings:
        return replace(DEFAULT_SETTINGS, **overrides)

    return factory


def wait_until(condition, timeout: float = 2.0, interval: float = 0.005) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(interval)
    return condition()


@pytest.fixture
def wait():
    return wait_until
