import pytest

from robot_server.camera import Camera, ServoAxis, angle_to_pulse
from robot_server.settings import CameraAxisSettings

PIN = 18


def make_axis(backend, *, start=90.0, invert=False, release=0.5, speed=100.0, lo=5.0, hi=135.0):
    config = CameraAxisSettings(pin=PIN, min_angle=lo, max_angle=hi, start_angle=start, invert=invert)
    return ServoAxis(backend, config, speed_dps=speed, release_after_s=release)


@pytest.mark.parametrize(("angle", "pulse"), [(0, 500), (90, 1500), (180, 2500), (45, 1000)])
def test_angle_to_pulse(angle, pulse):
    assert angle_to_pulse(angle) == pulse


def test_writes_start_position_on_init(backend):
    make_axis(backend, start=90)
    assert backend.servo_writes == [(PIN, 1500)]


def test_start_angle_is_clamped(backend):
    axis = make_axis(backend, start=170, hi=135)
    assert axis.angle == 135


def test_moves_at_constant_speed(backend):
    axis = make_axis(backend, start=90)
    axis.set_direction(1, now=0.0)
    axis.update(now=0.1, dt=0.1)
    assert axis.angle == pytest.approx(100)
    axis.set_direction(-1, now=0.1)
    axis.update(now=0.3, dt=0.2)
    assert axis.angle == pytest.approx(80)
    assert backend.servos[PIN] == angle_to_pulse(80)


def test_stops_at_limits(backend):
    axis = make_axis(backend, start=130, lo=5, hi=135)
    axis.set_direction(1, now=0.0)
    axis.update(now=1.0, dt=1.0)
    assert axis.angle == 135
    axis.set_direction(-1, now=1.0)
    axis.update(now=10.0, dt=9.0)
    assert axis.angle == 5


def test_invert_flips_direction(backend):
    axis = make_axis(backend, start=90, invert=True)
    axis.set_direction(1, now=0.0)
    axis.update(now=0.1, dt=0.1)
    assert axis.angle == pytest.approx(80)


def test_does_not_rewrite_same_pulse(backend):
    axis = make_axis(backend, start=135, hi=135)
    axis.set_direction(1, now=0.0)
    writes = len(backend.servo_writes)
    axis.update(now=0.1, dt=0.1)  # já está no limite
    assert len(backend.servo_writes) == writes


def test_releases_servo_after_idle_time(backend):
    axis = make_axis(backend, release=0.5)
    axis.set_direction(1, now=0.0)
    axis.update(now=0.1, dt=0.1)
    axis.set_direction(0, now=1.0)
    assert axis.needs_update
    axis.update(now=1.4, dt=0.3)
    assert backend.servos[PIN] != 0
    axis.update(now=1.6, dt=0.2)
    assert backend.servos[PIN] == 0
    assert not axis.needs_update


def test_initial_position_is_released_after_idle_time(backend):
    axis = make_axis(backend, release=0.5)
    assert axis.needs_update
    axis.update(now=100.0, dt=0.0)  # inicia o relógio
    axis.update(now=100.6, dt=0.6)
    assert backend.servos[PIN] == 0


def test_release_disabled_keeps_pulse(backend):
    axis = make_axis(backend, release=0)
    assert not axis.needs_update
    axis.set_direction(1, now=0.0)
    axis.set_direction(0, now=0.1)
    axis.update(now=10.0, dt=0.1)
    assert backend.servos[PIN] != 0


def test_moves_again_after_release(backend):
    axis = make_axis(backend, release=0.1)
    axis.release()
    axis.set_direction(1, now=0.0)
    axis.update(now=0.1, dt=0.1)
    assert backend.servos[PIN] == angle_to_pulse(axis.angle)


def test_camera_controls_both_axes(backend):
    vertical = CameraAxisSettings(pin=18, min_angle=5, max_angle=135, start_angle=70, invert=False)
    horizontal = CameraAxisSettings(pin=23, min_angle=5, max_angle=175, start_angle=90, invert=True)
    camera = Camera(backend, vertical, horizontal, speed_dps=100, release_after_s=0.5)
    camera.set_direction(1, 1, now=0.0)
    camera.update(now=0.1, dt=0.1)
    assert camera.vertical.angle == pytest.approx(80)
    assert camera.horizontal.angle == pytest.approx(80)  # invertido
    camera.release()
    assert backend.servos == {18: 0, 23: 0}
