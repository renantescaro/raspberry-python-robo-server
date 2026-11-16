"""Controle dos motores DC através de uma ponte H (4 pinos)."""

from __future__ import annotations

import enum
import logging

from . import protocol
from .gpio_backend import GpioBackend

log = logging.getLogger(__name__)


class DriveState(enum.Enum):
    # Valores: (direita frente, direita trás, esquerda frente, esquerda trás)
    STOP = (False, False, False, False)
    FORWARD = (True, False, True, False)
    BACKWARD = (False, True, False, True)
    LEFT = (False, True, True, False)
    RIGHT = (True, False, False, True)


def resolve_drive_state(flags: int) -> DriveState:
    """Converte as flags do protocolo em um estado. Curvas têm prioridade."""
    if flags & protocol.LEFT:
        return DriveState.LEFT
    if flags & protocol.RIGHT:
        return DriveState.RIGHT
    if flags & protocol.FORWARD:
        return DriveState.FORWARD
    if flags & protocol.BACKWARD:
        return DriveState.BACKWARD
    return DriveState.STOP


class Drive:
    def __init__(
        self,
        backend: GpioBackend,
        right_forward: int,
        right_backward: int,
        left_forward: int,
        left_backward: int,
    ) -> None:
        self._backend = backend
        self._pins = (right_forward, right_backward, left_forward, left_backward)
        for pin in self._pins:
            backend.setup_output(pin)
        self._state = DriveState.STOP

    @property
    def state(self) -> DriveState:
        return self._state

    def apply(self, flags: int) -> None:
        self.set_state(resolve_drive_state(flags))

    def stop(self) -> None:
        self.set_state(DriveState.STOP)

    def set_state(self, state: DriveState) -> None:
        # Só escreve no GPIO quando o estado realmente muda
        if state is self._state:
            return
        pattern = state.value
        # Desliga primeiro e liga depois, evitando os dois lados da ponte H ativos
        for pin, value, old in zip(self._pins, pattern, self._state.value):
            if old and not value:
                self._backend.write(pin, False)
        for pin, value, old in zip(self._pins, pattern, self._state.value):
            if value and not old:
                self._backend.write(pin, True)
        self._state = state
        log.debug("motores: %s", state.name)
