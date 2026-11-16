"""Testes do LgpioBackend com um módulo `lgpio` falso (roda fora do Pi)."""

from __future__ import annotations

import sys
import types

import pytest

from robot_server import gpio_backend
from robot_server.gpio_backend import LgpioBackend, create_backend


class FakeLgpioError(Exception):
    pass


class FakeCallback:
    def __init__(self, lg: FakeLgpio, gpio: int, func) -> None:
        self.lg, self.gpio, self.func, self.cancelled = lg, gpio, func, False

    def cancel(self) -> None:
        self.cancelled = True


class FakeLgpio(types.ModuleType):
    BOTH_EDGES = 3
    SET_PULL_DOWN = 64
    error = FakeLgpioError

    def __init__(self, chips: dict[int, str] | None = None) -> None:
        super().__init__("lgpio")
        # número do chip -> label
        self.chips = chips if chips is not None else {0: "pinctrl-bcm2835", 1: "raspberrypi-exp-gpio"}
        self.calls: list[tuple] = []
        self.levels: dict[int, int] = {}
        self.callbacks: list[FakeCallback] = []
        self.closed: list[int] = []
        # Simula o eco: ao baixar o trigger, gera as bordas com esta duração (ns)
        self.echo_duration_ns: int | None = None
        self.echo_pin: int | None = None

    def gpiochip_open(self, chip: int) -> int:
        if chip not in self.chips:
            raise FakeLgpioError("can not open gpiochip")
        return 100 + chip

    def gpio_get_chip_info(self, handle: int) -> list:
        chip = handle - 100
        return [0, 54, f"gpiochip{chip}", self.chips[chip]]

    def gpiochip_close(self, handle: int) -> None:
        self.closed.append(handle)

    def gpio_claim_output(self, handle, gpio, level=0, lFlags=0):
        self.calls.append(("claim_output", gpio))
        self.levels[gpio] = level

    def gpio_claim_alert(self, handle, gpio, eFlags, lFlags=0, notify_handle=None):
        self.calls.append(("claim_alert", gpio, eFlags, lFlags))

    def gpio_write(self, handle, gpio, level):
        previous = self.levels.get(gpio)
        self.levels[gpio] = level
        self.calls.append(("write", gpio, level))
        if previous == 1 and level == 0 and self.echo_duration_ns is not None:
            self._emit_echo()

    def gpio_free(self, handle, gpio):
        self.calls.append(("free", gpio))

    def tx_servo(self, handle, gpio, pulse_width, servo_frequency=50, pulse_offset=0, pulse_cycles=0):
        self.calls.append(("servo", gpio, pulse_width, servo_frequency))

    def callback(self, handle, gpio, edge=1, func=None):
        cb = FakeCallback(self, gpio, func)
        self.callbacks.append(cb)
        return cb

    def _emit_echo(self) -> None:
        for cb in self.callbacks:
            if cb.gpio == self.echo_pin and not cb.cancelled:
                cb.func(0, cb.gpio, 1, 5_000_000)
                cb.func(0, cb.gpio, 0, 5_000_000 + self.echo_duration_ns)


@pytest.fixture
def fake_lgpio(monkeypatch) -> FakeLgpio:
    module = FakeLgpio()
    monkeypatch.setitem(sys.modules, "lgpio", module)
    return module


def test_auto_detects_processor_chip(monkeypatch):
    module = FakeLgpio({1: "raspberrypi-exp-gpio", 4: "pinctrl-rp1"})
    monkeypatch.setitem(sys.modules, "lgpio", module)
    backend = LgpioBackend()
    assert backend._handle == 104
    assert 101 in module.closed  # chip que não é do processador é fechado


def test_explicit_chip(fake_lgpio):
    assert LgpioBackend(chip=1)._handle == 101


def test_no_processor_chip_raises(monkeypatch):
    monkeypatch.setitem(sys.modules, "lgpio", FakeLgpio({1: "raspberrypi-exp-gpio"}))
    with pytest.raises(RuntimeError, match="GPIO_CHIP"):
        LgpioBackend()


def test_outputs(fake_lgpio):
    backend = LgpioBackend()
    backend.setup_output(27)
    backend.write(27, True)
    backend.write(27, False)
    assert fake_lgpio.calls == [("claim_output", 27), ("write", 27, 1), ("write", 27, 0)]


def test_servo_claims_pin_once(fake_lgpio):
    backend = LgpioBackend()
    backend.servo_pulse(18, 1500)
    backend.servo_pulse(18, 1600)
    backend.servo_pulse(18, 0)
    assert fake_lgpio.calls == [
        ("claim_output", 18),
        ("servo", 18, 1500, 50),
        ("servo", 18, 1600, 50),
        ("servo", 18, 0, 50),
    ]


def test_input_uses_alerts_with_pull_down(fake_lgpio):
    LgpioBackend().setup_input(26)
    assert fake_lgpio.calls == [("claim_alert", 26, FakeLgpio.BOTH_EDGES, FakeLgpio.SET_PULL_DOWN)]


def test_measure_echo_uses_kernel_timestamps(fake_lgpio):
    fake_lgpio.echo_pin = 26
    fake_lgpio.echo_duration_ns = 2_500_000  # 2.5 ms
    backend = LgpioBackend()
    backend.setup_output(19)
    backend.setup_input(26)
    assert backend.measure_echo(19, 26, timeout_s=0.1) == pytest.approx(0.0025)
    assert backend.measure_echo(19, 26, timeout_s=0.1) == pytest.approx(0.0025)
    assert len(fake_lgpio.callbacks) == 1  # callback persistente, criado uma vez


def test_measure_echo_timeout(fake_lgpio):
    backend = LgpioBackend()
    backend.setup_output(19)
    backend.setup_input(26)
    assert backend.measure_echo(19, 26, timeout_s=0.01) is None


def test_cleanup_releases_everything(fake_lgpio):
    fake_lgpio.echo_pin = 26
    fake_lgpio.echo_duration_ns = 1_000
    backend = LgpioBackend()
    backend.setup_output(27)
    backend.write(27, True)
    backend.servo_pulse(18, 1500)
    backend.setup_output(19)
    backend.setup_input(26)
    backend.measure_echo(19, 26, timeout_s=0.1)
    fake_lgpio.calls.clear()

    backend.cleanup()
    assert ("servo", 18, 0, 50) in fake_lgpio.calls
    assert ("write", 27, 0) in fake_lgpio.calls
    assert {call[1] for call in fake_lgpio.calls if call[0] == "free"} == {27, 18, 19, 26}
    assert fake_lgpio.callbacks[0].cancelled
    assert fake_lgpio.closed == [100]


def test_create_backend_lgpio_by_name(fake_lgpio):
    assert isinstance(create_backend("lgpio"), LgpioBackend)


def test_auto_prefers_lgpio_when_pigpio_unavailable(fake_lgpio, monkeypatch):
    monkeypatch.setitem(sys.modules, "pigpio", None)
    backend = create_backend("auto")
    assert backend.name == "lgpio"


def test_auto_falls_back_to_rpigpio(monkeypatch):
    monkeypatch.setitem(sys.modules, "pigpio", None)
    monkeypatch.setitem(sys.modules, "lgpio", None)
    sentinel = object()
    monkeypatch.setattr(gpio_backend, "RPiGpioBackend", lambda: sentinel)
    assert create_backend("auto") is sentinel
