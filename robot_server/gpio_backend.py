"""Camada de acesso ao GPIO com implementações intercambiáveis.

- pigpio:   PWM dos servos e medição do ultrassônico com temporização por
            hardware (DMA). Requer o daemon `pigpiod`, que não existe mais
            no Raspberry Pi OS Trixie.
- lgpio:    padrão no Raspberry Pi OS Bookworm/Trixie (pacote python3-lgpio).
            Pulsos de servo gerados pela thread em C da biblioteca e bordas
            do ultrassônico com timestamp do kernel, sem busy-wait.
- rpigpio:  fallback com RPi.GPIO (PWM por software em Python, pode ter jitter).
- mock:     não toca no hardware; apenas registra no log. Usado no modo
            simulador (`python main.py --simulate`) em qualquer máquina.
"""

from __future__ import annotations

import contextlib
import io
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
        # pigpio.pi() imprime um aviso longo no stdout quando o daemon não existe
        with contextlib.redirect_stdout(io.StringIO()):
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


class LgpioBackend:
    name = "lgpio"

    def __init__(self, chip: int | None = None) -> None:
        import lgpio  # import tardio: só existe no Raspberry Pi

        self._lg = lgpio
        self._handle = self._open_chip(chip)
        self._claimed: set[int] = set()
        self._outputs: set[int] = set()
        self._servos: set[int] = set()
        self._echo_listeners: dict[int, _LgpioEchoListener] = {}

    def _open_chip(self, chip: int | None) -> int:
        lg = self._lg
        if chip is not None:
            return lg.gpiochip_open(chip)
        # Procura o chip do processador (pinctrl-bcm2835 no Pi 3, pinctrl-rp1 no Pi 5)
        for candidate in range(8):
            try:
                handle = lg.gpiochip_open(candidate)
            except lg.error:
                continue
            if str(lg.gpio_get_chip_info(handle)[3]).startswith("pinctrl-"):
                return handle
            lg.gpiochip_close(handle)
        raise RuntimeError("nenhum gpiochip do processador encontrado (defina GPIO_CHIP)")

    def _claim_output(self, pin: int) -> None:
        if pin not in self._claimed:
            self._lg.gpio_claim_output(self._handle, pin, 0)
            self._claimed.add(pin)

    def setup_output(self, pin: int) -> None:
        self._claim_output(pin)
        self._outputs.add(pin)

    def write(self, pin: int, value: bool) -> None:
        self._lg.gpio_write(self._handle, pin, 1 if value else 0)

    def servo_pulse(self, pin: int, pulse_us: int) -> None:
        self._claim_output(pin)
        if pulse_us == 0:
            # lgpio só aceita 0 (parar) com o servo ativo; senão erro 'bad PWM micros'
            if pin in self._servos:
                self._lg.tx_servo(self._handle, pin, 0, SERVO_FREQUENCY_HZ)
                self._servos.discard(pin)
            return
        self._lg.tx_servo(self._handle, pin, pulse_us, SERVO_FREQUENCY_HZ)
        self._servos.add(pin)

    def setup_input(self, pin: int) -> None:
        # Entrada com alertas: as bordas chegam com timestamp do kernel
        self._lg.gpio_claim_alert(self._handle, pin, self._lg.BOTH_EDGES, self._lg.SET_PULL_DOWN)
        self._claimed.add(pin)

    def measure_echo(self, trig_pin: int, echo_pin: int, timeout_s: float) -> float | None:
        listener = self._echo_listeners.get(echo_pin)
        if listener is None:
            listener = _LgpioEchoListener(self._lg, self._handle, echo_pin)
            self._echo_listeners[echo_pin] = listener
        listener.arm()
        self._lg.gpio_write(self._handle, trig_pin, 1)
        time.sleep(0.00001)
        self._lg.gpio_write(self._handle, trig_pin, 0)
        return listener.wait(timeout_s)

    def cleanup(self) -> None:
        lg = self._lg
        for listener in self._echo_listeners.values():
            listener.cancel()
        for pin in list(self._servos):
            self.servo_pulse(pin, 0)
        for pin in self._outputs:
            lg.gpio_write(self._handle, pin, 0)
        for pin in self._claimed:
            lg.gpio_free(self._handle, pin)
        lg.gpiochip_close(self._handle)


class _LgpioEchoListener:
    """Callback persistente que mede o pulso de eco com timestamps em ns."""

    def __init__(self, lgpio_module, handle: int, echo_pin: int) -> None:
        self._done = threading.Event()
        self._rise_ns: int | None = None
        self._duration_s: float | None = None
        self._callback = lgpio_module.callback(handle, echo_pin, lgpio_module.BOTH_EDGES, self._on_edge)

    def _on_edge(self, _chip: int, _gpio: int, level: int, timestamp_ns: int) -> None:
        if level == 1:
            self._rise_ns = timestamp_ns
        elif level == 0 and self._rise_ns is not None:
            self._duration_s = (timestamp_ns - self._rise_ns) / 1_000_000_000
            self._done.set()

    def arm(self) -> None:
        self._rise_ns = None
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


def create_backend(name: str, chip: int | None = None) -> GpioBackend:
    if name == "mock":
        return MockBackend()
    if name == "pigpio":
        return PigpioBackend()
    if name == "lgpio":
        return LgpioBackend(chip)
    if name == "rpigpio":
        return RPiGpioBackend()
    if name != "auto":
        raise ValueError(
            f"GPIO_BACKEND inválido: {name!r} (use auto, pigpio, lgpio, rpigpio ou mock)"
        )

    # Ordem de preferência: temporização por hardware > lgpio > RPi.GPIO
    for factory in (PigpioBackend, lambda: LgpioBackend(chip), RPiGpioBackend):
        try:
            return factory()
        except Exception as exc:  # biblioteca ausente, daemon parado, chip indisponível
            log.info("backend de GPIO indisponível: %s", exc)
    raise RuntimeError("Nenhuma biblioteca de GPIO encontrada. Fora do Raspberry Pi use --simulate.")
