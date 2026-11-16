"""Protocolo binário entre cliente e servidor.

IMPORTANTE: mantenha este arquivo em sincronia com
raspberry-python-robo-client/robot_client/protocol.py.

Cada pacote tem tamanho fixo de 4 bytes (sem necessidade de delimitador):

    byte 0  MAGIC     0xA5, usado para validar o fluxo
    byte 1  flags     bits de movimento (FORWARD, BACKWARD, LEFT, RIGHT)
    byte 2  camera_v  direção do eixo vertical da câmera  (-1, 0, +1)
    byte 3  camera_h  direção do eixo horizontal da câmera (-1, 0, +1)

O cliente envia um pacote sempre que o estado muda e, além disso, repete o
último estado periodicamente (heartbeat) para o watchdog do servidor.
"""

from __future__ import annotations

import struct
from typing import NamedTuple

MAGIC = 0xA5
PACKET = struct.Struct("<BBbb")
PACKET_SIZE = PACKET.size

FORWARD = 0x01
BACKWARD = 0x02
LEFT = 0x04
RIGHT = 0x08


class ProtocolError(ValueError):
    """Pacote inválido (fluxo corrompido ou cliente incompatível)."""


class ControlState(NamedTuple):
    flags: int = 0
    camera_v: int = 0
    camera_h: int = 0


def encode(state: ControlState) -> bytes:
    return PACKET.pack(MAGIC, state.flags, state.camera_v, state.camera_h)


def decode(buffer: bytes | bytearray | memoryview, offset: int = 0) -> ControlState:
    magic, flags, camera_v, camera_h = PACKET.unpack_from(buffer, offset)
    if magic != MAGIC:
        raise ProtocolError(f"magic inválido: 0x{magic:02X}")
    # Normaliza para -1/0/+1 mesmo que o cliente envie outros valores
    return ControlState(flags & 0x0F, _sign(camera_v), _sign(camera_h))


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)
