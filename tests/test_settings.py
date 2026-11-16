import os
import sys

import pytest

from robot_server import settings as settings_module
from robot_server.gpio_backend import MockBackend, create_backend
from robot_server.settings import load_settings

_PREFIXES = (
    "SERVER_", "GPIO_", "MOTOR_", "SERVO_", "CAMERA_", "CONTROL_", "WATCHDOG_",
    "ULTRASONIC_", "SPEED_OF_SOUND", "AUTO_UPDATE", "PORTA_",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    for key in list(os.environ):
        if key.startswith(_PREFIXES):
            monkeypatch.delenv(key)
    monkeypatch.setattr(settings_module, "ENV_FILE", tmp_path / ".env")


def test_defaults():
    s = load_settings()
    assert (s.host, s.port, s.gpio_backend) == ("0.0.0.0", 5001, "auto")
    assert (s.motor_right_forward_pin, s.motor_right_backward_pin) == (27, 17)
    assert (s.motor_left_forward_pin, s.motor_left_backward_pin) == (4, 3)
    assert s.camera_vertical.pin == 18 and s.camera_horizontal.pin == 23
    assert s.camera_horizontal.invert and not s.camera_vertical.invert
    assert s.watchdog_timeout_s == 1.0
    assert not s.ultrasonic_enabled
    assert s.auto_update


def test_start_angle_defaults_to_center():
    s = load_settings()
    assert s.camera_vertical.start_angle == (5 + 135) / 2
    assert s.camera_horizontal.start_angle == (5 + 175) / 2


def test_reads_env_file(tmp_path):
    (tmp_path / ".env").write_text("SERVER_PORT=6000\nULTRASONIC_ENABLED=true\nGPIO_BACKEND=PIGPIO\n")
    s = load_settings()
    assert s.port == 6000
    assert s.ultrasonic_enabled
    assert s.gpio_chip is None
    assert s.gpio_backend == "pigpio"


def test_legacy_portuguese_keys(monkeypatch):
    monkeypatch.setenv("PORTA_MOTOR_DIREITA_FRENTE", "5")
    monkeypatch.setenv("PORTA_SERVO_VERTICAL", "12")
    monkeypatch.setenv("PORTA_ULTRASSONICO_ECHO", "21")
    s = load_settings()
    assert s.motor_right_forward_pin == 5
    assert s.camera_vertical.pin == 12
    assert s.ultrasonic_echo_pin == 21


def test_new_key_wins_over_legacy(monkeypatch):
    monkeypatch.setenv("PORTA_MOTOR_DIREITA_FRENTE", "5")
    monkeypatch.setenv("MOTOR_RIGHT_FORWARD_PIN", "6")
    assert load_settings().motor_right_forward_pin == 6


@pytest.mark.parametrize(("raw", "expected"), [("true", True), ("1", True), ("sim", True), ("false", False), ("0", False)])
def test_bool_parsing(monkeypatch, raw, expected):
    monkeypatch.setenv("AUTO_UPDATE", raw)
    assert load_settings().auto_update is expected


def test_blank_value_uses_default(monkeypatch):
    monkeypatch.setenv("SERVER_PORT", "  ")
    assert load_settings().port == 5001


def test_create_backend_mock():
    assert isinstance(create_backend("mock"), MockBackend)


def test_create_backend_invalid_name():
    with pytest.raises(ValueError):
        create_backend("arduino")


def test_create_backend_auto_without_gpio_libraries(monkeypatch):
    # None em sys.modules faz o import falhar com ImportError
    monkeypatch.setitem(sys.modules, "pigpio", None)
    monkeypatch.setitem(sys.modules, "lgpio", None)
    monkeypatch.setitem(sys.modules, "RPi", None)
    monkeypatch.setitem(sys.modules, "RPi.GPIO", None)
    with pytest.raises(RuntimeError, match="--simulate"):
        create_backend("auto")


def test_gpio_chip(monkeypatch):
    monkeypatch.setenv("GPIO_CHIP", "4")
    assert load_settings().gpio_chip == 4
