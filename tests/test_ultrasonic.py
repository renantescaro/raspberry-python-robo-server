import pytest

from robot_server.ultrasonic import UltrasonicSensor


def make_sensor(backend):
    return UltrasonicSensor(
        backend, trig_pin=19, echo_pin=26, rate_hz=200, max_distance_m=4.0, speed_of_sound_mps=343.0
    )


def test_configures_pins(backend):
    make_sensor(backend)
    assert backend.pins == {19: False}
    assert backend.inputs == {26}


def test_converts_echo_to_centimeters(backend, wait):
    backend.echo_s = 0.01  # 10 ms ida e volta = 171.5 cm a 343 m/s
    sensor = make_sensor(backend)
    sensor.start()
    try:
        assert wait(lambda: sensor.distance_cm is not None)
        assert sensor.distance_cm == pytest.approx(171.5)
    finally:
        sensor.stop()
        sensor.join(timeout=2)
    assert not sensor.is_alive()


def test_out_of_range_is_none(backend, wait):
    backend.echo_s = None
    sensor = make_sensor(backend)
    sensor.distance_cm = 1.0
    sensor.start()
    try:
        assert wait(lambda: sensor.distance_cm is None)
    finally:
        sensor.stop()
        sensor.join(timeout=2)
