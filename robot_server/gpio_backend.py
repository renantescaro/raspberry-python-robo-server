"""Camada de acesso ao GPIO com três implementações intercambiáveis.

- pigpio:   recomendado. PWM dos servos e medição do ultrassônico com
            temporização por hardware (DMA), sem jitter e sem busy-wait.
            Requer o daemon rodando: `sudo systemctl enable --now pigpiod`.
- rpigpio:  fallback com RPi.GPIO (PWM por software, pode ter jitter).
- mock:     não toca no hardware; apenas registra no log. Usado no modo
            simulador (`python main.py --simulate`) em qualquer máquina.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Protocol

log = logging.getLogger(__name__)

SERVO_FREQUENCY_HZ = 50
SERVO_PERIOD_US = 1_000_000 // SERVO_FREQUENCY_HZ


class GpioBackend(Protocol):
    name: str

    def setup_output(self, pin: int) -> None: ...

    def write(self, pin: int, value: bool) -> None: ...

    def servo_pulse(self, pin: int, pulse_us: int) -> None:
        """Define a largura do pulso do servo em µs; 0 desliga o sinal."""

    def setup_input(self, pin: int) -> None: ...

    def measure_echo(self, trig_pin: int, echo_pin: int, timeout_s: float) -> float | None:
        """Dispara o trigger e retorna a duração do pulso de eco em segundos."""

    def cleanup(self) -> None: ...


class PigpioBackend:
    name = "pigpio"

    def __init__(self) -> None:
        import pigpio  # import tardio: só existe no Raspberry Pi

        self._pigpio = pigpio
        self._pi = pigpio.pi()
        if not self._pi.connected:
            raise RuntimeError("daemon pigpiod não está rodando")
        self._outputs: set[int] = set()
        self._servos: set[int] = set()
        self._echo_listeners: dict[int, _PigpioEchoListener] = {}

    def setup_output(self, pin: int) -> None:
        self._pi.set_mode(pin, self._pigpio.OUTPUT)
        self._pi.write(pin, 0)
        self._outputs.add(pin)

    def write(self, pin: int, value: bool) -> None:
        self._pi.write(pin, 1 if value else 0)

    def servo_pulse(self, pin: int, pulse_us: int) -> None:
        self._servos.add(pin)
        self._pi.set_servo_pulsewidth(pin, pulse_us)

    def setup_input(self, pin: int) -> None:
        self._pi.set_mode(pin, self._pigpio.INPUT)
        self._pi.set_pull_up_down(pin, self._pigpio.PUD_DOWN)

    def measure_echo(self, trig_pin: int, echo_pin: int, timeout_s: float) -> float | None:
        listener = self._echo_listeners.get(echo_pin)
        if listener is None:
            listener = _PigpioEchoListener(self._pi, self._pigpio, echo_pin)
            self._echo_listeners[echo_pin] = listener
        listener.arm()
        self._pi.gpio_trigger(trig_pin, 10, 1)
        return listener.wait(timeout_s)

    def cleanup(self) -> None:
        for listener in self._echo_listeners.values():
            listener.cancel()
        for pin in self._servos:
            self._pi.set_servo_pulsewidth(pin, 0)
        for pin in self._outputs:
            self._pi.write(pin, 0)
        self._pi.stop()


class _PigpioEchoListener:
    """Callback persistente que mede o pulso de eco com o tick (µs) do pigpio."""

    def __init__(self, pi, pigpio_module, echo_pin: int) -> None:
        self._pigpio = pigpio_module
        self._done = threading.Event()
        self._rise_tick: int | None = None
        self._duration_s: float | None = None
        self._callback = pi.callback(echo_pin, pigpio_module.EITHER_EDGE, self._on_edge)

    def _on_edge(self, _gpio: int, level: int, tick: int) -> None:
        if level == 1:
            self._rise_tick = tick
        elif level == 0 and self._rise_tick is not None:
            self._duration_s = self._pigpio.tickDiff(self._rise_tick, tick) / 1_000_000
            self._done.set()

    def arm(self) -> None:
        self._rise_tick = None
        self._duration_s = None
        self._done.clear()

    def wait(self, timeout_s: float) -> float | None:
        return self._duration_s if self._done.wait(timeout_s) else None

    def cancel(self) -> None:
        self._callback.cancel()


class RPiGpioBackend:
    name = "rpigpio"

    def __init__(self) -> None:
        import RPi.GPIO as GPIO  # import tardio: só existe no Raspberry Pi

        self._gpio = GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        # Um único objeto PWM por pino, criado uma vez e reaproveitado
        self._pwm: dict[int, object] = {}

    def setup_output(self, pin: int) -> None:
        self._gpio.setup(pin, self._gpio.OUT, initial=self._gpio.LOW)

    def write(self, pin: int, value: bool) -> None:
        self._gpio.output(pin, value)

    def servo_pulse(self, pin: int, pulse_us: int) -> None:
        pwm = self._pwm.get(pin)
        if pwm is None:
            self._gpio.setup(pin, self._gpio.OUT, initial=self._gpio.LOW)
            pwm = self._gpio.PWM(pin, SERVO_FREQUENCY_HZ)
            pwm.start(0)
            self._pwm[pin] = pwm
        pwm.ChangeDutyCycle(pulse_us * 100 / SERVO_PERIOD_US)

    def setup_input(self, pin: int) -> None:
        self._gpio.setup(pin, self._gpio.IN, pull_up_down=self._gpio.PUD_DOWN)

    def measure_echo(self, trig_pin: int, echo_pin: int, timeout_s: float) -> float | None:
        # RPi.GPIO não tem timestamp de borda; a espera ativa é limitada pelo timeout
        gpio = self._gpio
        gpio.output(trig_pin, True)
        time.sleep(0.00001)
        gpio.output(trig_pin, False)

        deadline = time.perf_counter() + timeout_s
        start = time.perf_counter()
        while gpio.input(echo_pin) == 0:
            start = time.perf_counter()
            if start > deadline:
                return None
        while gpio.input(echo_pin) == 1:
            if time.perf_counter() > deadline:
                return None
        return time.perf_counter() - start

    def cleanup(self) -> None:
        for pwm in self._pwm.values():
            pwm.stop()
        self._gpio.cleanup()


class MockBackend:
    name = "mock"

    def __init__(self) -> None:
        self._state: dict[int, bool] = {}

    def setup_output(self, pin: int) -> None:
        self._state[pin] = False

    def write(self, pin: int, value: bool) -> None:
        self._state[pin] = value
        log.info("[mock] GPIO %d -> %d", pin, value)

    def servo_pulse(self, pin: int, pulse_us: int) -> None:
        log.info("[mock] servo GPIO %d -> %d µs", pin, pulse_us)

    def setup_input(self, pin: int) -> None:
        pass

    def measure_echo(self, trig_pin: int, echo_pin: int, timeout_s: float) -> float | None:
        time.sleep(timeout_s)
        return None

    def cleanup(self) -> None:
        pass


def create_backend(name: str) -> GpioBackend:
    if name == "mock":
        return MockBackend()
    if name == "pigpio":
        return PigpioBackend()
    if name == "rpigpio":
        return RPiGpioBackend()
    if name != "auto":
        raise ValueError(f"GPIO_BACKEND inválido: {name!r} (use auto, pigpio, rpigpio ou mock)")

    try:
        return PigpioBackend()
    except Exception as exc:  # pigpio ausente ou daemon parado
        log.warning("pigpio indisponível (%s); usando RPi.GPIO", exc)
    try:
        return RPiGpioBackend()
    except ImportError as exc:
        raise RuntimeError(
            "Nenhuma biblioteca de GPIO encontrada. Fora do Raspberry Pi use --simulate."
        ) from exc
