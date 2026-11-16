"""Movimento da câmera (pan/tilt) com dois servomotores.

O cliente envia apenas a direção (-1, 0, +1). O servidor move o servo a uma
velocidade constante enquanto a direção estiver ativa, independentemente da
taxa de pacotes da rede.
"""

from __future__ import annotations

import logging

from .gpio_backend import GpioBackend
from .settings import CameraAxisSettings

log = logging.getLogger(__name__)

PULSE_MIN_US = 500  # 0°
PULSE_MAX_US = 2500  # 180°


def angle_to_pulse(angle: float) -> int:
    return round(PULSE_MIN_US + angle / 180.0 * (PULSE_MAX_US - PULSE_MIN_US))


class ServoAxis:
    def __init__(
        self,
        backend: GpioBackend,
        config: CameraAxisSettings,
        speed_dps: float,
        release_after_s: float,
    ) -> None:
        self._backend = backend
        self._config = config
        self._speed = speed_dps
        self._release_after = release_after_s
        self._direction = 0
        self.angle = min(max(config.start_angle, config.min_angle), config.max_angle)
        self._written_pulse: int | None = None
        # Liberação do servo pendente; o relógio começa no próximo update()
        self._release_pending = release_after_s > 0
        self._idle_since: float | None = None
        self._write()

    @property
    def needs_update(self) -> bool:
        """Indica se o loop de controle precisa continuar chamando update()."""
        return self._direction != 0 or self._release_pending

    def set_direction(self, direction: int, now: float) -> None:
        if self._config.invert:
            direction = -direction
        if direction == self._direction:
            return
        self._direction = direction
        self._release_pending = direction == 0 and self._release_after > 0
        self._idle_since = now

    def update(self, now: float, dt: float) -> None:
        if self._direction:
            cfg = self._config
            angle = self.angle + self._direction * self._speed * dt
            self.angle = min(max(angle, cfg.min_angle), cfg.max_angle)
            self._write()
        elif self._release_pending:
            if self._idle_since is None:
                self._idle_since = now
            elif now - self._idle_since >= self._release_after:
                # Para de gerar pulsos com o servo parado: elimina tremor e consumo
                self.release()

    def release(self) -> None:
        self._release_pending = False
        if self._written_pulse is not None:
            self._backend.servo_pulse(self._config.pin, 0)
            self._written_pulse = None

    def _write(self) -> None:
        pulse = angle_to_pulse(self.angle)
        if pulse != self._written_pulse:
            self._backend.servo_pulse(self._config.pin, pulse)
            self._written_pulse = pulse


class Camera:
    def __init__(
        self,
        backend: GpioBackend,
        vertical: CameraAxisSettings,
        horizontal: CameraAxisSettings,
        speed_dps: float,
        release_after_s: float,
    ) -> None:
        self.vertical = ServoAxis(backend, vertical, speed_dps, release_after_s)
        self.horizontal = ServoAxis(backend, horizontal, speed_dps, release_after_s)

    @property
    def needs_update(self) -> bool:
        return self.vertical.needs_update or self.horizontal.needs_update

    def set_direction(self, vertical: int, horizontal: int, now: float) -> None:
        self.vertical.set_direction(vertical, now)
        self.horizontal.set_direction(horizontal, now)

    def update(self, now: float, dt: float) -> None:
        self.vertical.update(now, dt)
        self.horizontal.update(now, dt)

    def release(self) -> None:
        self.vertical.release()
        self.horizontal.release()
