"""Sensor ultrassônico (HC-SR04) medido em uma thread separada."""

from __future__ import annotations

import logging
import threading
import time

from .gpio_backend import GpioBackend

log = logging.getLogger(__name__)


class UltrasonicSensor(threading.Thread):
    def __init__(
        self,
        backend: GpioBackend,
        trig_pin: int,
        echo_pin: int,
        rate_hz: float,
        max_distance_m: float,
        speed_of_sound_mps: float,
    ) -> None:
        super().__init__(name="ultrasonic", daemon=True)
        self._backend = backend
        self._trig = trig_pin
        self._echo = echo_pin
        self._period = 1.0 / rate_hz
        self._speed_of_sound = speed_of_sound_mps
        # Ida e volta até a distância máxima, com pequena folga
        self._timeout = 2 * max_distance_m / speed_of_sound_mps + 0.005
        self._stop_event = threading.Event()
        # Última distância em centímetros; None quando fora de alcance
        self.distance_cm: float | None = None

        backend.setup_output(trig_pin)
        backend.setup_input(echo_pin)

    def run(self) -> None:
        next_tick = time.monotonic()
        while not self._stop_event.is_set():
            echo_s = self._backend.measure_echo(self._trig, self._echo, self._timeout)
            self.distance_cm = (
                None if echo_s is None else round(echo_s * self._speed_of_sound * 50, 2)
            )
            log.debug("distância: %s cm", self.distance_cm)

            next_tick += self._period
            delay = next_tick - time.monotonic()
            if delay > 0:
                self._stop_event.wait(delay)
            else:
                next_tick = time.monotonic()

    def stop(self) -> None:
        self._stop_event.set()
